import os
import ssl
import socket
import asyncio
import shutil
from datetime import datetime, timedelta
import numpy as np
import cv2
from aiohttp import web
from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization

HTTPS_PORT = 8080
HTTP_MJPEG_PORT = 8081

def resolve_ffmpeg_binary():
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return shutil.which("ffmpeg")

class StreamServer:
    def __init__(self):
        self.connected_devices = {}
        self.selected_device_id = None
        self.latest_frame = None
        self.loop = None
        self.cert_file = "cert.pem"
        self.key_file = "key.pem"
        self.ffmpeg_path = resolve_ffmpeg_binary()

    def get_local_ip(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(('8.8.8.8', 80))
            ip = s.getsockname()[0]
        except Exception:
            ip = '127.0.0.1'
        finally:
            s.close()
        return ip

    def ensure_ssl_certs(self):
        if os.path.exists(self.cert_file) and os.path.exists(self.key_file):
            return

        print("[DEBUG][SERVER] Generating self-signed SSL certificate...")
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, self.get_local_ip())])
        cert = (
            x509.CertificateBuilder()
            .subject_name(name)
            .issuer_name(name)
            .public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(datetime.utcnow())
            .not_valid_after(datetime.utcnow() + timedelta(days=365))
            .sign(key, hashes.SHA256())
        )

        with open(self.key_file, "wb") as f:
            f.write(key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.TraditionalOpenSSL,
                encryption_algorithm=serialization.NoEncryption()
            ))

        with open(self.cert_file, "wb") as f:
            f.write(cert.public_bytes(serialization.Encoding.PEM))
        print("[DEBUG][SERVER] SSL certificate ready.")

    async def index_handler(self, request):
        file_path = os.path.join(os.path.dirname(__file__), 'static', 'index.html')
        with open(file_path, 'r', encoding='utf-8') as f:
            return web.Response(text=f.read(), content_type='text/html')

    async def ws_handler(self, request):
        ws = web.WebSocketResponse(max_msg_size=10 * 1024 * 1024)
        await ws.prepare(request)

        device_ip = request.remote
        device_id = f"Mobile_{device_ip.replace('.', '')[-6:]}"
        self.connected_devices[device_id] = ws
        print(f"[DEBUG][SERVER] Phone connected: {device_id} from {device_ip}")

        if not self.selected_device_id:
            self.selected_device_id = device_id

        try:
            async for msg in ws:
                if msg.type == web.WSMsgType.BINARY:
                    if self.selected_device_id == device_id:
                        nparr = np.frombuffer(msg.data, np.uint8)
                        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                        if frame is not None:
                            self.latest_frame = frame
                elif msg.type == web.WSMsgType.ERROR:
                    print(f"[DEBUG][SERVER] WS error from {device_id}: {ws.exception()}")
                    break
        finally:
            print(f"[DEBUG][SERVER] Phone disconnected: {device_id}")
            if device_id in self.connected_devices:
                del self.connected_devices[device_id]
            if self.selected_device_id == device_id:
                self.selected_device_id = next(iter(self.connected_devices.keys())) if self.connected_devices else None

        return ws

    async def cast_mp4_handler(self, request):
        print(f"[DEBUG][SERVER] Cast device requested stream. Client IP: {request.remote}")

        if request.method == 'HEAD':
            return web.Response(
                headers={
                    'Content-Type': 'video/mp4',
                    'Access-Control-Allow-Origin': '*',
                    'Accept-Ranges': 'none'
                }
            )

        if not self.ffmpeg_path:
            print("[ERROR][SERVER] FFmpeg binary could not be resolved.")
            return web.Response(status=500, text="FFmpeg not found")

        response = web.StreamResponse(
            status=200,
            headers={
                'Content-Type': 'video/mp4',
                'Access-Control-Allow-Origin': '*',
                'Connection': 'keep-alive'
            }
        )
        await response.prepare(request)

        w, h = 1280, 720
        if self.latest_frame is not None:
            h, w, _ = self.latest_frame.shape

        cmd = [
            self.ffmpeg_path,
            '-y',
            '-f', 'rawvideo',
            '-vcodec', 'rawvideo',
            '-pix_fmt', 'bgr24',
            '-s', f'{w}x{h}',
            '-r', '25',
            '-i', '-',
            '-f', 'lavfi',
            '-i', 'anullsrc=channel_layout=stereo:sample_rate=44100',
            '-c:v', 'libx264',
            '-preset', 'ultrafast',
            '-tune', 'zerolatency',
            '-pix_fmt', 'yuv420p',
            '-g', '25',
            '-c:a', 'aac',
            '-b:a', '64k',
            '-shortest',
            '-movflags', 'frag_keyframe+empty_moov+default_base_moof',
            '-f', 'mp4',
            '-'
        ]

        print(f"[DEBUG][SERVER] Launching FFmpeg at: {self.ffmpeg_path}")
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        async def feed_frames():
            blank = np.zeros((h, w, 3), dtype=np.uint8)
            try:
                while proc.returncode is None:
                    frame = self.latest_frame if self.latest_frame is not None else blank
                    if frame.shape[0] != h or frame.shape[1] != w:
                        frame = cv2.resize(frame, (w, h))
                    proc.stdin.write(frame.tobytes())
                    await proc.stdin.drain()
                    await asyncio.sleep(0.04)
            except Exception as e:
                print(f"[DEBUG][SERVER] Feed loop stopped: {e}")
            finally:
                if proc.stdin and not proc.stdin.is_closing():
                    proc.stdin.close()

        feed_task = asyncio.create_task(feed_frames())

        try:
            bytes_sent = 0
            while True:
                chunk = await proc.stdout.read(32768)
                if not chunk:
                    break
                await response.write(chunk)
                bytes_sent += len(chunk)
        except Exception as e:
            print(f"[DEBUG][SERVER] Cast delivery interrupted: {e}")
        finally:
            feed_task.cancel()
            if proc.returncode is None:
                try:
                    proc.kill()
                except Exception:
                    pass
            print(f"[DEBUG][SERVER] Feed ended. Bytes sent: {bytes_sent}")

        return response

    def send_broadcast_config(self, fps, width, height):
        msg = f'{{"fps": {fps}, "width": {width}, "height": {height}}}'
        for ws in self.connected_devices.values():
            if self.loop and self.loop.is_running():
                asyncio.run_coroutine_threadsafe(ws.send_str(msg), self.loop)

    def run(self, loop):
        self.loop = loop
        asyncio.set_event_loop(self.loop)
        self.ensure_ssl_certs()

        print(f"[DEBUG][SERVER] Using FFmpeg executable: {self.ffmpeg_path}")

        app_https = web.Application()
        app_https.router.add_get('/', self.index_handler)
        app_https.router.add_get('/ws', self.ws_handler)
        app_https.router.add_static('/static/', path=os.path.join(os.path.dirname(__file__), 'static'), name='static')

        ssl_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ssl_ctx.load_cert_chain(self.cert_file, self.key_file)

        runner_https = web.AppRunner(app_https)
        self.loop.run_until_complete(runner_https.setup())
        site_https = web.TCPSite(runner_https, '0.0.0.0', HTTPS_PORT, ssl_context=ssl_ctx)
        self.loop.run_until_complete(site_https.start())
        print(f"[DEBUG][SERVER] Mobile Capture URL: https://{self.get_local_ip()}:{HTTPS_PORT}")

        app_http = web.Application()
        app_http.router.add_route('*', '/cast_feed.mp4', self.cast_mp4_handler)
        runner_http = web.AppRunner(app_http)
        self.loop.run_until_complete(runner_http.setup())
        site_http = web.TCPSite(runner_http, '0.0.0.0', HTTP_MJPEG_PORT)
        self.loop.run_until_complete(site_http.start())
        print(f"[DEBUG][SERVER] Chromecast Stream URL: http://{self.get_local_ip()}:{HTTP_MJPEG_PORT}/cast_feed.mp4")

        self.loop.run_forever()

# End of server.py