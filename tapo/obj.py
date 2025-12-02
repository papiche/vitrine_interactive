import cv2
import os
import urllib.request
import time
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision
from ultralytics import YOLO

# ==============================
# Settings
# ==============================
MODEL_DIR = r"C:\obj_det"  # Folder to store Mediapipe model
MODEL_PATH = os.path.join(MODEL_DIR, "efficientdet_lite0.tflite")
MODEL_URL = "https://storage.googleapis.com/mediapipe-models/object_detector/efficientdet_lite0/int8/1/efficientdet_lite0.tflite"

# ==============================
# Helper Functions
# ==============================
def download_model():
    """Download Mediapipe model if not exists"""
    os.makedirs(MODEL_DIR, exist_ok=True)
    if not os.path.exists(MODEL_PATH):
        print("[INFO] Downloading Mediapipe model...")
        urllib.request.urlretrieve(MODEL_URL, MODEL_PATH)
        print("[INFO] Model downloaded successfully.")
    else:
        print("[INFO] Mediapipe model already exists.")

def visualize_mediapipe(image, detection_result):
    """Draw bounding boxes + labels for Mediapipe"""
    TEXT_COLOR = (0, 255, 0)
    FONT_SIZE = 1
    FONT_THICKNESS = 2

    for detection in detection_result.detections:
        bbox = detection.bounding_box
        start = (bbox.origin_x, bbox.origin_y)
        end = (bbox.origin_x + bbox.width, bbox.origin_y + bbox.height)
        cv2.rectangle(image, start, end, TEXT_COLOR, 2)

        category = detection.categories[0]
        text = f"{category.category_name} ({round(category.score, 2)})"
        cv2.putText(image, text, (bbox.origin_x, bbox.origin_y - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, FONT_SIZE, TEXT_COLOR, FONT_THICKNESS)
    return image

def find_working_camera(max_index=5):
    """Automatically find working webcam index"""
    for i in range(max_index):
        cap = cv2.VideoCapture(i, cv2.CAP_DSHOW)
        if cap.isOpened():
            print(f"[INFO] Using camera index {i}")
            return cap
        cap.release()
    print("[ERROR] No working webcam found.")
    exit()

# ==============================
# Initialize Models
# ==============================
print("[INFO] Initializing models...")
download_model()

# Mediapipe Detector
base_options = python.BaseOptions(model_asset_path=MODEL_PATH)
mp_options = vision.ObjectDetectorOptions(base_options=base_options, score_threshold=0.5)
mp_detector = vision.ObjectDetector.create_from_options(mp_options)

# YOLOv8 Detector
yolo_model = YOLO("yolov8n.pt")
yolo_model.overrides['verbose'] = False  # Disable logs

# ==============================
# Camera Loop
# ==============================
cap = find_working_camera()
active_model = "YOLO"  # Default model
prev_time = time.time()

print("[INFO] Press 'Y' for YOLO, 'M' for Mediapipe, ESC to exit.")

while True:
    ret, frame = cap.read()
    if not ret:
        print("[ERROR] Failed to access camera.")
        break

    start_time = time.time()

    # Detect objects
    if active_model == "YOLO":
        results = yolo_model(frame, verbose=False)
        annotated_frame = results[0].plot()
    else:
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=frame)
        detection_result = mp_detector.detect(mp_image)
        annotated_frame = visualize_mediapipe(frame.copy(), detection_result)

    # Calculate FPS
    fps = 1 / (time.time() - start_time)

    # Overlay info
    cv2.putText(annotated_frame, f"Active Model: {active_model}", (20, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
    cv2.putText(annotated_frame, f"FPS: {fps:.2f}", (20, 70),
                cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 0), 2)

    # Show camera
    cv2.imshow("Object Detection", annotated_frame)

    key = cv2.waitKey(1) & 0xFF
    if key == 27:  # ESC
        break
    elif key == ord("y") or key == ord("Y"):
        active_model = "YOLO"
        print("[INFO] Switched to YOLOv8")
    elif key == ord("m") or key == ord("M"):
        active_model = "Mediapipe"
        print("[INFO] Switched to Mediapipe EfficientDet")

cap.release()
cv2.destroyAllWindows()
