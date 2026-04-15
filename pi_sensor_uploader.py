import os
import time
from datetime import datetime

import cv2
import requests

try:
    import serial
    import pynmea2
except Exception:
    serial = None
    pynmea2 = None

try:
    from gpiozero import DigitalInputDevice
except Exception:
    DigitalInputDevice = None


API_URL = os.getenv("TRACKCRACK_API_URL", "https://train-track-monitoring-system.onrender.com/api/pi-capture")
API_TOKEN = os.getenv("TRACKCRACK_API_TOKEN", "changeme-token")
IR_GPIO_PIN = int(os.getenv("IR_GPIO_PIN", "17"))
GPS_SERIAL_PORT = os.getenv("GPS_SERIAL_PORT", "/dev/ttyAMA0")
GPS_BAUD = int(os.getenv("GPS_BAUD", "9600"))
CAMERA_INDEX = int(os.getenv("CAMERA_INDEX", "0"))
COOLDOWN_SECONDS = float(os.getenv("IR_COOLDOWN_SECONDS", "5"))


def read_gps_coordinates(timeout_seconds=3.0):
    if serial is None or pynmea2 is None:
        return None, None
    try:
        with serial.Serial(GPS_SERIAL_PORT, GPS_BAUD, timeout=0.5) as gps:
            deadline = time.time() + timeout_seconds
            while time.time() < deadline:
                raw = gps.readline().decode("ascii", errors="ignore").strip()
                if not raw or not raw.startswith("$"):
                    continue
                if "GGA" not in raw and "RMC" not in raw:
                    continue
                msg = pynmea2.parse(raw)
                lat = getattr(msg, "latitude", None)
                lon = getattr(msg, "longitude", None)
                if lat and lon:
                    return f"{lat:.6f}", f"{lon:.6f}"
    except Exception:
        return None, None
    return None, None


def capture_frame(output_path):
    cam = cv2.VideoCapture(CAMERA_INDEX)
    if not cam.isOpened():
        raise RuntimeError("Unable to access webcam.")
    ok, frame = cam.read()
    cam.release()
    if not ok:
        raise RuntimeError("Failed to capture image from webcam.")
    cv2.imwrite(output_path, frame)


def post_capture(image_path, lat=None, lon=None):
    headers = {"X-API-Token": API_TOKEN}
    data = {
        "ir_triggered": "true",
        "description": "Auto-captured from Raspberry Pi IR trigger",
    }
    if lat and lon:
        data["latitude"] = lat
        data["longitude"] = lon
    with open(image_path, "rb") as fh:
        files = {"image": (os.path.basename(image_path), fh, "image/jpeg")}
        response = requests.post(API_URL, headers=headers, data=data, files=files, timeout=30)
    print(f"[{datetime.now()}] Upload status: {response.status_code} {response.text}")


def run_polling():
    if DigitalInputDevice is None:
        raise RuntimeError("gpiozero is not installed. Install on Raspberry Pi first.")

    ir_sensor = DigitalInputDevice(IR_GPIO_PIN, pull_up=False)
    os.makedirs("captures", exist_ok=True)
    print(f"Watching IR sensor on GPIO {IR_GPIO_PIN}...")

    while True:
        if ir_sensor.value:
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            image_path = os.path.join("captures", f"{stamp}.jpg")
            lat, lon = read_gps_coordinates()
            try:
                capture_frame(image_path)
                post_capture(image_path, lat=lat, lon=lon)
            except Exception as exc:
                print(f"[{datetime.now()}] Capture/upload failed: {exc}")
            time.sleep(COOLDOWN_SECONDS)
        else:
            time.sleep(0.1)


if __name__ == "__main__":
    run_polling()
