## IMPORTANT!
### THIS README is in writing and is not done

# PocketGuard

Use your phone as a security camera.

---

## Overview

PocketGuard transforms any smartphone into a wireless local security camera with real-time desktop monitoring and TV casting. Connect your mobile device via local Wi-Fi without installing third-party apps, monitor feeds directly from your desktop, and cast streams to Chromecast-enabled displays.

---

## Features

* Zero-Install Mobile Capture — Stream directly from any modern mobile browser.
* Quick Pairing — Connect instantly by scanning an on-screen QR code.
* Live Stream Controls — Adjust FPS (4 to 60 fps) and resolution (up to 1080p) dynamically.
* Chromecast Support — Cast the live video feed directly to smart TVs and displays.
* Local & Private — All streams stay strictly within your local network.

---

## Getting Started

### Prerequisites

* Python 3.10+
* Local Wi-Fi connection shared across devices

### Installation

1. Clone the repository:
   git clone https://github.com/your-username/PocketGuard.git
   cd PocketGuard

2. Install dependencies:
   pip install customtkinter pillow opencv-python aiohttp qrcode pychromecast cryptography imageio-ffmpeg

3. Launch the application:
   python main.py

---

## Usage

1. Open PocketGuard on your PC.
2. Scan the Quick-Connect QR code using your smartphone.
3. Accept the local certificate prompt in your mobile browser to grant camera access.
4. Tap "Start Streaming" on your phone.
5. (Optional) Select "CAST TO TV" on the desktop dashboard to route the feed to a Chromecast.

---

## License

Copyright (c) 2026 Morgan Kot

This work is licensed under the Creative Commons Attribution-NoDerivatives 4.0 International License.

YOU ARE FREE TO:
* Share — copy and redistribute the material in any medium or format.
* Use — run and execute the software for any purpose.

UNDER THE FOLLOWING TERMS:
* Attribution — You must give appropriate credit, provide a link to the license, and indicate if changes were made.
* NoDerivatives — If you remix, transform, or build upon the material, you may not distribute the modified material.
* No additional restrictions — You may not apply legal terms or technological measures that legally restrict others from doing anything the license permits.

To view a copy of this license, visit http://creativecommons.org
