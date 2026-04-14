from ultralytics import YOLO
import cv2
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

MODEL_PATH = os.path.join(BASE_DIR, "model", "best.pt")

model = YOLO(MODEL_PATH)


def process_image(input_path, output_path):
    results = model(input_path)[0]
    img = cv2.imread(input_path)

    img_h, img_w = img.shape[:2]
    img_area = img_h * img_w

    highest_level = "LOW"

    for box in results.boxes:
        x1, y1, x2, y2 = map(int, box.xyxy[0])

        area = (x2 - x1) * (y2 - y1)
        norm_area = area / img_area

        if norm_area < 0.01:
            level = "LOW"
            color = (0, 255, 0)
        elif norm_area < 0.05:
            level = "MEDIUM"
            color = (0, 255, 255)
        else:
            level = "HIGH"
            color = (0, 0, 255)

        if level == "HIGH":
            highest_level = "HIGH"
        elif level == "MEDIUM" and highest_level != "HIGH":
            highest_level = "MEDIUM"

        cv2.rectangle(img, (x1, y1), (x2, y2), color, 2)
        cv2.putText(img, level, (x1, y1 - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)

    cv2.imwrite(output_path, img)

    return highest_level