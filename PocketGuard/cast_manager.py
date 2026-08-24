import threading

class CastController:
    def __init__(self):
        self.is_casting = False
        self.browser = None
        self.devices = []
        self.selected_cast = None

    def discover_devices(self, on_found_callback):
        def _scan():
            try:
                import pychromecast
                chromecasts, browser = pychromecast.get_chromecasts()
                self.devices = chromecasts
                self.browser = browser
                names = [c.name for c in chromecasts]
                on_found_callback(names)
            except Exception as e:
                print(f"Discovery error: {e}")
                on_found_callback([])

        threading.Thread(target=_scan, daemon=True).start()

    def start_cast(self, target_name, stream_url):
        self.is_casting = True
        threading.Thread(target=self._cast_worker, args=(target_name, stream_url), daemon=True).start()

    def stop_cast(self):
        self.is_casting = False
        if self.selected_cast:
            try:
                self.selected_cast.media_controller.stop()
            except Exception:
                pass
        if self.browser:
            try:
                import pychromecast
                pychromecast.discovery.stop_discovery(self.browser)
            except Exception:
                pass

    def _cast_worker(self, target_name, stream_url):
        try:
            for cast in self.devices:
                if cast.name == target_name:
                    self.selected_cast = cast
                    break

            if self.selected_cast:
                self.selected_cast.wait()
                mc = self.selected_cast.media_controller
                mc.play_media(stream_url, 'video/mp4', stream_type='LIVE')
                mc.block_until_active()
        except Exception as e:
            print(f"Chromecast streaming error: {e}")