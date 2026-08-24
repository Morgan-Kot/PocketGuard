import asyncio
import threading
from datetime import datetime
import cv2
import qrcode
from PIL import Image
import customtkinter as ctk

from server import StreamServer, HTTPS_PORT, HTTP_MJPEG_PORT
from cast_manager import CastController

class DashboardApp(ctk.CTk):
    def __init__(self, server, cast_mgr):
        super().__init__()
        self.server = server
        self.cast_mgr = cast_mgr

        self.title("Security Camera Dashboard")
        self.geometry("1100x620")
        self.configure(fg_color="#182c4d")

        self.local_ip = self.server.get_local_ip()
        self.mobile_connect_url = f"https://{self.local_ip}:{HTTPS_PORT}"
        self.tv_url = f"http://{self.local_ip}:{HTTP_MJPEG_PORT}/cast_feed.mp4"

        self.audio_state = "ON"
        self.is_fullscreen = False

        self.setup_ui()
        self.update_video_loop()

    def setup_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=2)
        self.grid_rowconfigure(0, weight=0)
        self.grid_rowconfigure(1, weight=1)

        self.title_label = ctk.CTkLabel(
            self, text="Dashboard", font=ctk.CTkFont(size=42, weight="bold"),
            text_color="#ffffff", anchor="w"
        )
        self.title_label.grid(row=0, column=0, padx=35, pady=(20, 10), sticky="w")

        top_right_frame = ctk.CTkFrame(self, fg_color="transparent")
        top_right_frame.grid(row=0, column=1, padx=30, pady=(15, 5), sticky="e")

        qr_box = ctk.CTkFrame(top_right_frame, fg_color="transparent")
        qr_box.pack(side="left", padx=15)
        ctk.CTkLabel(qr_box, text="Quick-Connect", font=ctk.CTkFont(size=12, weight="bold"), text_color="#ffffff").pack()
        qr_img = self.generate_qr(self.mobile_connect_url)
        ctk.CTkLabel(qr_box, image=qr_img, text="").pack(pady=2)

        dev_box = ctk.CTkFrame(top_right_frame, fg_color="transparent")
        dev_box.pack(side="left", padx=10)
        ctk.CTkLabel(dev_box, text="Available Devices:", font=ctk.CTkFont(size=18, weight="bold"), text_color="#ffffff").pack(anchor="w")

        self.device_list_frame = ctk.CTkFrame(dev_box, fg_color="#1f4477", corner_radius=8)
        self.device_list_frame.pack(fill="both", expand=True, pady=4)

        left_panel = ctk.CTkFrame(self, fg_color="transparent")
        left_panel.grid(row=1, column=0, padx=35, pady=10, sticky="nw")

        ctk.CTkLabel(left_panel, text="Video Settings", font=ctk.CTkFont(size=24, weight="bold"), text_color="#ffffff").pack(anchor="w", pady=(10, 20))

        fps_frame = ctk.CTkFrame(left_panel, fg_color="transparent")
        fps_frame.pack(anchor="w", pady=6)
        ctk.CTkLabel(fps_frame, text="FPS:", font=ctk.CTkFont(size=16, weight="bold"), text_color="#ffffff").pack(side="left", padx=(0, 10))
        self.fps_dropdown = ctk.CTkOptionMenu(
            fps_frame, values=["4 fps", "15 fps", "30 fps", "60 fps"],
            command=self.sync_settings, fg_color="#274f87", button_color="#1b3963"
        )
        self.fps_dropdown.set("30 fps")
        self.fps_dropdown.pack(side="left")

        res_frame = ctk.CTkFrame(left_panel, fg_color="transparent")
        res_frame.pack(anchor="w", pady=6)
        ctk.CTkLabel(res_frame, text="Resolution:", font=ctk.CTkFont(size=16, weight="bold"), text_color="#ffffff").pack(side="left", padx=(0, 10))
        self.res_dropdown = ctk.CTkOptionMenu(
            res_frame, values=["640x480 (480p)", "1280x720 (720p)", "1920x1080 (1080p)"],
            command=self.sync_settings, fg_color="#274f87", button_color="#1b3963"
        )
        self.res_dropdown.set("1280x720 (720p)")
        self.res_dropdown.pack(side="left")

        audio_frame = ctk.CTkFrame(left_panel, fg_color="transparent")
        audio_frame.pack(anchor="w", pady=6)
        ctk.CTkLabel(audio_frame, text="Audio:", font=ctk.CTkFont(size=16, weight="bold"), text_color="#ffffff").pack(side="left", padx=(0, 10))
        self.audio_btn = ctk.CTkButton(audio_frame, text="ON", width=45, height=24, fg_color="#1f4477", command=self.toggle_audio)
        self.audio_btn.pack(side="left")

        self.cast_btn = ctk.CTkButton(
            left_panel, text="CAST TO TV", fg_color="#d97706", hover_color="#b45309",
            font=ctk.CTkFont(size=14, weight="bold"), command=self.handle_cast_click
        )
        self.cast_btn.pack(anchor="w", pady=(15, 5))

        ctk.CTkButton(
            left_panel, text="ADVANCED SETTINGS...", fg_color="#274f87",
            font=ctk.CTkFont(size=14, weight="bold")
        ).pack(anchor="w", pady=(10, 0))

        self.video_container = ctk.CTkFrame(self, fg_color="#0b1726", corner_radius=18)
        self.video_container.grid(row=1, column=1, padx=(10, 35), pady=(10, 30), sticky="nsew")
        self.video_container.grid_rowconfigure(0, weight=1)
        self.video_container.grid_columnconfigure(0, weight=1)

        self.video_viewport = ctk.CTkLabel(
            self.video_container, text="WAITING FOR VIDEO STREAM...",
            font=ctk.CTkFont(size=20, weight="bold"), text_color="#71829e"
        )
        self.video_viewport.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)

        overlay = ctk.CTkFrame(self.video_container, fg_color="transparent")
        overlay.place(relx=0.98, rely=0.95, anchor="se")
        ctk.CTkButton(overlay, text="⛶", width=32, height=32, fg_color="#1f4477", command=self.toggle_fullscreen).pack(side="right")

    def generate_qr(self, url):
        qr = qrcode.QRCode(version=1, box_size=2, border=1)
        qr.add_data(url)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        return ctk.CTkImage(light_image=img.get_image(), size=(65, 65))

    def update_device_list_ui(self):
        for widget in self.device_list_frame.winfo_children():
            widget.destroy()

        if not self.server.connected_devices:
            lbl = ctk.CTkLabel(self.device_list_frame, text="No mobile devices connected", font=ctk.CTkFont(size=12), text_color="#cbd5e1")
            lbl.pack(padx=10, pady=6)
            return

        for dev_id in list(self.server.connected_devices.keys()):
            row = ctk.CTkFrame(self.device_list_frame, fg_color="transparent")
            row.pack(fill="x", padx=6, pady=2)

            name = ctk.CTkLabel(row, text=dev_id, font=ctk.CTkFont(size=13), text_color="#ffffff")
            name.pack(side="left", padx=5)

            is_active = (dev_id == self.server.selected_device_id)
            btn_color = "#16a34a" if is_active else "#475569"
            btn_text = "STREAMING" if is_active else "CONNECT"

            btn = ctk.CTkButton(
                row, text=btn_text, width=70, height=22, font=ctk.CTkFont(size=11, weight="bold"),
                fg_color=btn_color, command=lambda d=dev_id: self.select_device(d)
            )
            btn.pack(side="right", padx=5)

    def select_device(self, dev_id):
        self.server.selected_device_id = dev_id
        self.update_device_list_ui()

    def toggle_audio(self):
        self.audio_state = "OFF" if self.audio_state == "ON" else "ON"
        self.audio_btn.configure(text=self.audio_state)

    def toggle_fullscreen(self):
        self.is_fullscreen = not self.is_fullscreen
        self.attributes("-fullscreen", self.is_fullscreen)

    def sync_settings(self, _=None):
        fps_val = int(self.fps_dropdown.get().split()[0])
        res_val = self.res_dropdown.get().split()[0].split("x")
        w, h = int(res_val[0]), int(res_val[1])
        self.server.send_broadcast_config(fps_val, w, h)

    def handle_cast_click(self):
        if self.cast_mgr.is_casting:
            self.cast_mgr.stop_cast()
            self.cast_btn.configure(text="CAST TO TV", fg_color="#d97706")
            return

        self.cast_btn.configure(text="SEARCHING...", fg_color="#64748b")
        self.cast_mgr.discover_devices(self.show_cast_selection_dialog)

    def show_cast_selection_dialog(self, device_names):
        if not device_names:
            self.cast_btn.configure(text="NO TV FOUND", fg_color="#dc2626")
            self.after(3000, lambda: self.cast_btn.configure(text="CAST TO TV", fg_color="#d97706"))
            return

        dialog = ctk.CTkToplevel(self)
        dialog.title("Select Cast Device")
        dialog.geometry("320x240")
        dialog.attributes("-topmost", True)

        ctk.CTkLabel(dialog, text="Select Target TV / Device:", font=ctk.CTkFont(size=15, weight="bold")).pack(pady=10)

        selected_tv = ctk.StringVar(value=device_names[0])
        opt = ctk.CTkOptionMenu(dialog, values=device_names, variable=selected_tv)
        opt.pack(pady=15)

        def confirm():
            target = selected_tv.get()
            dialog.destroy()
            self.cast_mgr.start_cast(target, self.tv_url)
            self.cast_btn.configure(text=f"CASTING: {target[:10]}", fg_color="#16a34a")

        ctk.CTkButton(dialog, text="Start Casting", fg_color="#16a34a", command=confirm).pack(pady=10)

    def update_video_loop(self):
        self.update_device_list_ui()

        if self.server.latest_frame is not None:
            view_w = max(self.video_container.winfo_width() - 20, 320)
            view_h = max(self.video_container.winfo_height() - 20, 240)

            rgb_frame = cv2.cvtColor(self.server.latest_frame, cv2.COLOR_BGR2RGB)
            h, w, _ = rgb_frame.shape

            fps_str = self.fps_dropdown.get()
            res_str = f"{w}x{h}"
            date_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            cv2.putText(rgb_frame, f"FPS: {fps_str}", (w - 180, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (220, 220, 220), 1, cv2.LINE_AA)
            cv2.putText(rgb_frame, f"Resolution: {res_str}", (w - 180, 55), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (220, 220, 220), 1, cv2.LINE_AA)
            cv2.putText(rgb_frame, f"Audio: {self.audio_state}", (w - 180, 80), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (220, 220, 220), 1, cv2.LINE_AA)
            cv2.putText(rgb_frame, f"Date: {date_str}", (w - 240, 105), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (220, 220, 220), 1, cv2.LINE_AA)

            pil_img = Image.fromarray(rgb_frame)
            ctk_img = ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=(view_w, view_h))
            self.video_viewport.configure(image=ctk_img, text="")
        else:
            self.video_viewport.configure(image=None, text="SCAN QR CODE TO START STREAM")

        self.after(30, self.update_video_loop)

if __name__ == "__main__":
    server = StreamServer()
    cast_mgr = CastController()

    server_loop = asyncio.new_event_loop()
    threading.Thread(target=server.run, args=(server_loop,), daemon=True).start()

    app = DashboardApp(server, cast_mgr)
    app.mainloop()