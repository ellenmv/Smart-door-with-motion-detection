import json
import cv2
import numpy as np
from pathlib import Path
from typing import Optional, Tuple


class FaceRecognizer:
    def __init__(
        self,
        model_path: str,
        labels_path: str,
        threshold: float = 60.0,
        min_labels_required: int = 1,
    ):
        self.model_path = model_path
        self.labels_path = labels_path
        self.threshold = float(threshold)
        self.min_labels_required = int(min_labels_required)

        self.face_cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        )

        self.recognizer = cv2.face.LBPHFaceRecognizer_create()
        self.labels = {}
        self._load()

    def _load(self):
        if Path(self.labels_path).exists():
            with open(self.labels_path, "r", encoding="utf-8") as f:
                self.labels = json.load(f) or {}
        else:
            self.labels = {}

        if Path(self.model_path).exists():
            self.recognizer.read(self.model_path)

    def set_threshold(self, value: float):
        self.threshold = float(value)

    def detect_and_recognize(self, frame) -> Tuple[str, Optional[str], Optional[float], str]:

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.equalizeHist(gray)

        faces = self.face_cascade.detectMultiScale(
            gray, scaleFactor=1.2, minNeighbors=5, minSize=(80, 80)
        )

        if len(faces) == 0:
            return "NO_FACE", None, None, "No face detected"

        faces = sorted(faces, key=lambda r: r[2] * r[3], reverse=True)
        (x, y, w, h) = faces[0]
        roi = gray[y:y + h, x:x + w]

        if len(self.labels) < self.min_labels_required:
            return "DENIED", None, None, f"Insufficient trained persons ({len(self.labels)})"

        try:
            label_id, confidence = self.recognizer.predict(roi)
        except cv2.error:
            return "DENIED", None, None, "Model not trained yet"

        name = self.labels.get(str(label_id), None)

        if confidence <= self.threshold and name is not None:
           return "GRANTED", name, float(confidence), "Match"
        
        return "DENIED", None, float(confidence), "Unknown or above threshold"


    @staticmethod
    def train_from_folder(faces_dir: str, model_path: str, labels_path: str) -> Tuple[int, int]:
        faces_path = Path(faces_dir)
        if not faces_path.exists():
            raise RuntimeError("faces_dir does not exist")

        face_cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        )
        recognizer = cv2.face.LBPHFaceRecognizer_create()

        X = []
        y = []
        labels = {}
        label_to_id = {}
        next_id = 0

        total_imgs = 0
        used_faces = 0

        for person_dir in sorted([p for p in faces_path.iterdir() if p.is_dir()]):
            person = person_dir.name
            if person not in label_to_id:
                label_to_id[person] = next_id
                labels[str(next_id)] = person
                next_id += 1

            for img_path in person_dir.glob("*.*"):
                total_imgs += 1
                img = cv2.imread(str(img_path))
                if img is None:
                    continue

                gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
                faces = face_cascade.detectMultiScale(gray, 1.2, 5, minSize=(80, 80))
                if len(faces) == 0:
                    continue

                faces = sorted(faces, key=lambda r: r[2] * r[3], reverse=True)
                x, y0, w, h = faces[0]
                roi = gray[y0:y0 + h, x:x + w]

                X.append(roi)
                y.append(label_to_id[person])
                used_faces += 1

        if used_faces < 2:
            raise RuntimeError("Not enough training samples")

        labels_np = np.array(y, dtype=np.int32).reshape(-1, 1)
        recognizer.train(X, labels_np)

        Path(model_path).parent.mkdir(parents=True, exist_ok=True)
        Path(labels_path).parent.mkdir(parents=True, exist_ok=True)

        recognizer.write(model_path)
        with open(labels_path, "w", encoding="utf-8") as f:
            json.dump(labels, f, ensure_ascii=False, indent=2)

        return total_imgs, used_faces
