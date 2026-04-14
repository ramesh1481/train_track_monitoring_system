import os
import time
from datetime import datetime

import cv2
import requests


# --- Configure these manually for debugging ---
API_URL = os.getenv("TRACKCRACK_API_URL", "https://train-track-monitoring-system.onrender.com/api/pi-capture")
API_TOKEN = os.getenv("TRACKCRACK_API_TOKEN", "changeme-token")
CAMERA_INDEX = int(os.getenv("CAMERA_INDEX", "0"))
REQUEST_CONNECT_TIMEOUT = float(os.getenv("REQUEST_CONNECT_TIMEOUT", "15"))
REQUEST_READ_TIMEOUT = float(os.getenv("REQUEST_READ_TIMEOUT", "180"))
REQUEST_RETRIES = int(os.getenv("REQUEST_RETRIES", "3"))

# Fixed coordinates for manual testing (edit as needed)
FIXED_LATITUDE = os.getenv("DEBUG_LATITUDE", "12.971598")
FIXED_LONGITUDE = os.getenv("DEBUG_LONGITUDE", "77.594566")
# ---------------------------------------------


def capture_webcam_frame(output_path):
    cam = cv2.VideoCapture(CAMERA_INDEX)
    if not cam.isOpened():
        raise RuntimeError("Unable to access laptop webcam.")

    ok, frame = cam.read()
    cam.release()
    if not ok:
        raise RuntimeError("Failed to capture frame from webcam.")

    cv2.imwrite(output_path, frame)


def upload_capture(image_path):
    headers = {"X-API-Token": API_TOKEN}
    data = {
        "ir_triggered": "true",
        "description": "Manual debug capture from laptop webcam",
        "latitude": FIXED_LATITUDE,
        "longitude": FIXED_LONGITUDE,
    }

    last_error = None
    for attempt in range(1, REQUEST_RETRIES + 1):
        try:
            with open(image_path, "rb") as file_obj:
                files = {"image": (os.path.basename(image_path), file_obj, "image/jpeg")}
                response = requests.post(
                    API_URL,
                    headers=headers,
                    data=data,
                    files=files,
                    timeout=(REQUEST_CONNECT_TIMEOUT, REQUEST_READ_TIMEOUT),
                )
            print(f"Status: {response.status_code}")
            # print(response.text)
            return
        except requests.exceptions.ReadTimeout as exc:
            last_error = exc
            wait_seconds = attempt * 5
            print(
                f"Read timeout on attempt {attempt}/{REQUEST_RETRIES}. "
                f"Waiting {wait_seconds}s and retrying..."
            )
            time.sleep(wait_seconds)
        except requests.exceptions.RequestException as exc:
            last_error = exc
            break

    raise RuntimeError(f"Upload failed after {REQUEST_RETRIES} attempts: {last_error}")


def main():
    os.makedirs("captures", exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    image_path = os.path.join("captures", f"manual_debug_{timestamp}.jpg")

    print(f"Using fixed coordinates: {FIXED_LATITUDE}, {FIXED_LONGITUDE}")
    print("Capturing image from webcam...")
    capture_webcam_frame(image_path)
    print(f"Saved capture: {image_path}")

    print("Uploading to backend...")
    upload_capture(image_path)


if __name__ == "__main__":
    main()
