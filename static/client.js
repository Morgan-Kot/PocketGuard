const video = document.getElementById('preview');
const toggleBtn = document.getElementById('toggleBtn');
const statusDiv = document.getElementById('status');

let ws = null;
let stream = null;
let streaming = false;
let isProcessingFrame = false;
let streamTimeout = null;

let targetFps = 30;
let targetWidth = 1280;
let targetHeight = 720;
let jpegQuality = 0.5;

async function initCamera() {
    try {
        if (stream) {
            stream.getTracks().forEach(track => track.stop());
        }
        stream = await navigator.mediaDevices.getUserMedia({
            video: {
                width: { ideal: targetWidth },
                height: { ideal: targetHeight },
                facingMode: "environment"
            },
            audio: false
        });
        video.srcObject = stream;
        statusDiv.innerText = "Camera ready.";
    } catch (err) {
        statusDiv.innerText = "Camera error: " + err.message;
    }
}

function connectWS() {
    const loc = window.location;
    const wsUrl = "wss://" + loc.host + "/ws";
    ws = new WebSocket(wsUrl);

    ws.onopen = () => {
        statusDiv.innerText = "Connected to Dashboard";
    };

    ws.onmessage = (event) => {
        const config = JSON.parse(event.data);
        if (config.fps) {
            targetFps = config.fps;
        }
        if (config.width && config.height) {
            targetWidth = config.width;
            targetHeight = config.height;
            jpegQuality = (targetWidth >= 1920) ? 0.35 : 0.5;
            initCamera();
        }
    };

    ws.onclose = () => {
        statusDiv.innerText = "Disconnected from Dashboard";
        stopStreaming();
    };
}

function processAndSend() {
    if (!streaming || !ws || ws.readyState !== WebSocket.OPEN) return;

    if (isProcessingFrame) {
        streamTimeout = setTimeout(processAndSend, 1000 / targetFps);
        return;
    }

    isProcessingFrame = true;
    const canvas = document.createElement('canvas');
    canvas.width = video.videoWidth || targetWidth;
    canvas.height = video.videoHeight || targetHeight;
    const ctx = canvas.getContext('2d');
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

    canvas.toBlob((blob) => {
        if (blob && ws.readyState === WebSocket.OPEN) {
            blob.arrayBuffer().then(buf => {
                ws.send(buf);
                isProcessingFrame = false;
                streamTimeout = setTimeout(processAndSend, 1000 / targetFps);
            }).catch(() => { isProcessingFrame = false; });
        } else {
            isProcessingFrame = false;
            streamTimeout = setTimeout(processAndSend, 1000 / targetFps);
        }
    }, 'image/jpeg', jpegQuality);
}

function startStreaming() {
    streaming = true;
    toggleBtn.innerText = "Stop Streaming";
    toggleBtn.classList.add("stop");
    processAndSend();
}

function stopStreaming() {
    streaming = false;
    toggleBtn.innerText = "Start Streaming";
    toggleBtn.classList.remove("stop");
    if (streamTimeout) clearTimeout(streamTimeout);
    isProcessingFrame = false;
}

toggleBtn.addEventListener('click', () => {
    if (!streaming) {
        startStreaming();
    } else {
        stopStreaming();
    }
});

initCamera().then(connectWS);