"""Quick test of FaceLandmarker Tasks API."""
import mediapipe as mp
from mediapipe.tasks.python import vision, BaseOptions
import cv2
import numpy as np

opts = vision.FaceLandmarkerOptions(
    base_options=BaseOptions(model_asset_path="face_landmarker.task"),
    running_mode=vision.RunningMode.IMAGE,
    num_faces=1,
    output_face_blendshapes=True,
    output_facial_transformation_matrixes=True,
)
landmarker = vision.FaceLandmarker.create_from_options(opts)

cap = cv2.VideoCapture(0)
ret, frame = cap.read()
cap.release()
if not ret:
    print("No frame")
    exit()

rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
mp_img = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
result = landmarker.detect(mp_img)

print(f"Faces: {len(result.face_landmarks)}")
if result.face_landmarks:
    lm = result.face_landmarks[0]
    print(f"Landmarks: {len(lm)}")
    print(f"LM[0]: x={lm[0].x:.4f} y={lm[0].y:.4f} z={lm[0].z:.4f}")
    if len(lm) > 468:
        print(f"LM[468] iris: x={lm[468].x:.4f} y={lm[468].y:.4f}")
    else:
        print(f"Only {len(lm)} landmarks (no iris)")

if result.face_blendshapes:
    bs = result.face_blendshapes[0]
    print(f"Blendshapes: {len(bs)}")
    for b in bs[:5]:
        print(f"  {b.category_name}: {b.score:.3f}")
    names = [b.category_name for b in bs]
    print(f"All: {names}")

if result.facial_transformation_matrixes:
    mat = result.facial_transformation_matrixes[0]
    print(f"Transform: {type(mat)}")

landmarker.close()
print("DONE")
