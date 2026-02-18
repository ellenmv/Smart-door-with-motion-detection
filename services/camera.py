import cv2
import os
import time
import threading

class Camera:
    def __init__(self, index: int = 0):
        self.index = index
        self.cap = None
        self.lock = threading.Lock()

    def open(self) -> None:
        if self.cap is not None:
            return

        if os.name == "nt":
            cap = cv2.VideoCapture(self.index, cv2.CAP_DSHOW)
        else:
            cap = cv2.VideoCapture(self.index, cv2.CAP_V4L2)

        if not cap.isOpened():
            cap.release()
            raise RuntimeError(f"Camera open failed (index={self.index})")

        for _ in range(10):
            cap.read()
            time.sleep(0.03)

        self.cap = cap

    def close(self) -> None:
        with self.lock:
            if self.cap is not None:
                self.cap.release()
                self.cap = None

    def capture_frame(self):
        with self.lock:
            if self.cap is None:
                self.open()

            ok, frame = self.cap.read()
            if not ok or frame is None:
                raise RuntimeError("Camera frame capture failed")

            return frame.copy()
