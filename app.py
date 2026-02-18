import os
import threading
import time
import shutil
import cv2
from flask import Flask, render_template, redirect, url_for, request, flash, Response, session

from config import CONFIG
from services.db import DB
from services.camera import Camera
from services.face_recognizer import FaceRecognizer
from services.emailer import Emailer
from services.MotionDetector import MotionDetector


app = Flask(__name__)
app.secret_key = "change-me"

db = DB(CONFIG.DB_PATH)
camera = Camera(CONFIG.CAMERA_INDEX)

# Global motion detector
try:
    motion_detector = MotionDetector(area_threshold=2500)
    warm = camera.capture_frame()
    motion_detector.detect(warm)
    print("Motion detector ready")
except Exception as e:
    print("Motion disabled:", e)
    motion_detector = None


recognizer_lock = threading.Lock()
recognizer = FaceRecognizer(
    CONFIG.MODEL_PATH,
    CONFIG.LABELS_PATH,
    threshold=0.0
)

emailer = Emailer(
    CONFIG.SMTP_HOST,
    CONFIG.SMTP_PORT,
    CONFIG.SMTP_USERNAME,
    CONFIG.SMTP_PASSWORD,
    CONFIG.EMAIL_FROM,
    CONFIG.EMAIL_TO,
)

status_lock = threading.Lock()
status = {
    "camera": "standby",
    "last_result": "N/A",
    "last_name": None,
    "last_confidence": None,
    "note": "",
}

last_email_sent_ts = 0.0


def get_threshold() -> float:
    v = db.get_setting("threshold", str(CONFIG.DEFAULT_THRESHOLD))
    try:
        return float(v)
    except Exception:
        return CONFIG.DEFAULT_THRESHOLD


def get_notifications_enabled() -> bool:
    v = db.get_setting("email_enabled", "1" if CONFIG.EMAIL_ENABLED_DEFAULT else "0")
    return v == "1"


def get_email_on_granted() -> bool:
    v = db.get_setting("email_on_granted", "0")
    return v == "1"


def get_attach_photo() -> bool:
    v = db.get_setting("attach_photo", "1")
    return v == "1"


def get_email_cooldown_sec() -> int:
    v = db.get_setting("email_cooldown_sec", "30")
    try:
        n = int(v)
        if n < 0:
            n = 0
        if n > 3600:
            n = 3600
        return n
    except Exception:
        return 30


def get_notify_email() -> str:
    v = db.get_setting("notify_email", "")
    return (v or "").strip()


def set_notify_email(email: str):
    db.set_setting("notify_email", (email or "").strip())


def _maybe_encode_frame_jpg(frame):
    if not get_attach_photo():
        return None
    try:
        ok, buf = cv2.imencode(".jpg", frame)
        if ok:
            return buf.tobytes()
    except Exception:
        return None
    return None


def _can_send_email(now_ts: float) -> bool:
    global last_email_sent_ts
    cooldown = get_email_cooldown_sec()
    if cooldown == 0:
        return True
    return (now_ts - last_email_sent_ts) >= cooldown


def _mark_email_sent(now_ts: float):
    global last_email_sent_ts
    last_email_sent_ts = now_ts


def _make_emailer_for_current_recipient() -> Emailer:
    to_email = get_notify_email() or CONFIG.EMAIL_TO
    from_email = getattr(CONFIG, "EMAIL_FROM", CONFIG.SMTP_USERNAME)
    return Emailer(
        CONFIG.SMTP_HOST,
        CONFIG.SMTP_PORT,
        CONFIG.SMTP_USERNAME,
        CONFIG.SMTP_PASSWORD,
        from_email,
        to_email,
    )


def process_one_attempt(source: str = "manual", frame=None):
    global status

    with status_lock:
        status["camera"] = "capturing"
        status["note"] = f"Triggered by {source}"

    try:
        if frame is None:
            frame = camera.capture_frame()

        with recognizer_lock:
            recognizer.set_threshold(get_threshold())
            result, name, confidence, note = recognizer.detect_and_recognize(frame)

        if result == "GRANTED":
            db.add_event(name=name, result="GRANTED", confidence=confidence, note=note)
        elif result == "DENIED":
            db.add_event(name=name, result="DENIED", confidence=confidence, note=note)
        else:
            db.add_event(name=None, result="NO_FACE", confidence=None, note=note)

        if get_notifications_enabled():
            if not get_notify_email():
                db.add_event(name=name, result="EMAIL_SKIP", confidence=confidence, note="No notify_email set")
            else:
                now = time.time()
                if _can_send_email(now):
                    image_bytes = _maybe_encode_frame_jpg(frame)
                    try:
                        emailer_local = _make_emailer_for_current_recipient()

                        if result == "DENIED":
                            emailer_local.send_access_denied(
                                f"Access denied.\nName guess: {name}\nConfidence: {confidence}\nNote: {note}",
                                image_jpg_bytes=image_bytes,
                            )
                            _mark_email_sent(now)

                        elif result == "GRANTED" and get_email_on_granted():
                            emailer_local.send_access_granted(
                                f"Access granted.\nName: {name}\nConfidence: {confidence}\nNote: {note}",
                                image_jpg_bytes=image_bytes,
                            )
                            _mark_email_sent(now)

                    except Exception as e:
                        db.add_event(name=name, result="EMAIL_FAIL", confidence=confidence, note=str(e))

        with status_lock:
            status["last_result"] = result
            status["last_name"] = name
            status["last_confidence"] = confidence
            status["note"] = note

    except Exception as e:
        db.add_event(name=None, result="ERROR", confidence=None, note=str(e))
        with status_lock:
            status["last_result"] = "ERROR"
            status["note"] = str(e)
    finally:
        with status_lock:
            status["camera"] = "standby"


def motion_loop():
    global motion_detector

    print("Motion detection loop started")
    if motion_detector is None:
        print("Motion detector disabled")
        return

    while True:
        try:
            frame = camera.capture_frame()

            if motion_detector.detect(frame):
                process_one_attempt(source="MOTION", frame=frame)
                time.sleep(2.0)
            else:
                time.sleep(0.1)

        except Exception as e:
            db.add_event(name=None, result="MOTION_ERROR", confidence=None, note=str(e))
            time.sleep(1.0)


def capture_samples(person_name: str, num_samples: int):
    person_name = person_name.strip()
    if not person_name:
        raise ValueError("Person name required")

    save_dir = os.path.join(CONFIG.FACES_DIR, person_name)
    os.makedirs(save_dir, exist_ok=True)

    face_cascade = cv2.CascadeClassifier(
        cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    )

    saved = 0
    attempts = 0

    while saved < num_samples and attempts < num_samples * 8:
        attempts += 1
        frame = camera.capture_frame()
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = face_cascade.detectMultiScale(gray, 1.2, 5, minSize=(80, 80))
        if len(faces) == 0:
            time.sleep(0.08)
            continue
        faces = sorted(faces, key=lambda r: r[2] * r[3], reverse=True)
        x, y, w, h = faces[0]
        roi = gray[y:y + h, x:x + w]
        cv2.imwrite(os.path.join(save_dir, f"{int(time.time()*1000)}_{saved}.jpg"), roi)
        saved += 1
        time.sleep(0.08)

    if saved == 0:
        raise RuntimeError("No face samples captured")

    return saved


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip()

        if not email or "@" not in email or "." not in email:
            flash("Please enter a valid email address.")
            return redirect(url_for("login"))

        set_notify_email(email)
        session["configured"] = True
        flash("Done! Notifications will be sent to this email address.")
        return redirect(url_for("index"))

    current_email = get_notify_email()
    return render_template("login.html", current_email=current_email)


@app.route("/logout", methods=["POST"])
def logout():
    set_notify_email("")
    session.pop("configured", None)
    flash("The notification email has been cleared.")
    return redirect(url_for("login"))


@app.route("/")
def index():
    if not get_notify_email():
        return redirect(url_for("login"))

    events = db.latest_events(30)
    with status_lock:
        st = dict(status)

    persons = []
    if os.path.isdir(CONFIG.FACES_DIR):
        persons = sorted(
            d for d in os.listdir(CONFIG.FACES_DIR)
            if os.path.isdir(os.path.join(CONFIG.FACES_DIR, d))
        )

    return render_template("index.html", status=st, events=events, persons=persons)


@app.route("/trigger", methods=["POST"])
def trigger():
    threading.Thread(target=process_one_attempt, args=("MANUAL",), daemon=True).start()
    flash("Started recognition attempt.")
    return redirect(url_for("index"))

@app.route("/status_json")
def status_json():
    with status_lock:
        return {
            "status": status,
            "events": db.latest_events(10)
        }

@app.route("/train", methods=["POST"])
def train():
    global recognizer
    try:
        with recognizer_lock:
            total, used = FaceRecognizer.train_from_folder(
                CONFIG.FACES_DIR,
                CONFIG.MODEL_PATH,
                CONFIG.LABELS_PATH
            )
            recognizer = FaceRecognizer(
                CONFIG.MODEL_PATH,
                CONFIG.LABELS_PATH,
                threshold=get_threshold()
            )
        flash(f"Training complete. Images: {total}, Faces used: {used}.")
    except Exception as e:
        flash(f"Training failed: {e}")
    return redirect(url_for("index"))


@app.route("/delete_person", methods=["POST"])
def delete_person():
    global recognizer

    person = request.form.get("person", "").strip()
    if not person:
        flash("No person specified.")
        return redirect(url_for("index"))

    person_dir = os.path.join(CONFIG.FACES_DIR, person)
    if not os.path.isdir(person_dir):
        flash(f"Person '{person}' not found.")
        return redirect(url_for("index"))

    try:
        shutil.rmtree(person_dir)

        remaining = []
        if os.path.isdir(CONFIG.FACES_DIR):
            remaining = [
                d for d in os.listdir(CONFIG.FACES_DIR)
                if os.path.isdir(os.path.join(CONFIG.FACES_DIR, d))
            ]

        if len(remaining) == 0:
            try:
                if os.path.exists(CONFIG.MODEL_PATH):
                    os.remove(CONFIG.MODEL_PATH)
                if os.path.exists(CONFIG.LABELS_PATH):
                    os.remove(CONFIG.LABELS_PATH)
            except Exception:
                pass

            with recognizer_lock:
                recognizer = FaceRecognizer(
                    CONFIG.MODEL_PATH,
                    CONFIG.LABELS_PATH,
                    threshold=get_threshold()
                )

            flash(f"Person '{person}' deleted. No persons left, model cleared.")
            return redirect(url_for("index"))

        total, used = FaceRecognizer.train_from_folder(
            CONFIG.FACES_DIR,
            CONFIG.MODEL_PATH,
            CONFIG.LABELS_PATH
        )

        with recognizer_lock:
            recognizer = FaceRecognizer(
                CONFIG.MODEL_PATH,
                CONFIG.LABELS_PATH,
                threshold=get_threshold()
            )

        flash(f"Person '{person}' deleted. Model retrained (images: {total}, faces used: {used}).")

    except Exception as e:
        flash(f"Delete failed: {e}")

    return redirect(url_for("index"))


@app.route("/capture", methods=["POST"])
def capture():
    person = request.form.get("person", "").strip()
    n_raw = request.form.get("num", "20")
    try:
        n = int(n_raw)
    except Exception:
        n = 20

    try:
        saved = capture_samples(person, max(5, min(60, n)))
        flash(f"Captured {saved} samples for {person}.")
    except Exception as e:
        flash(f"Capture failed: {e}")
    return redirect(url_for("index"))


def gen_frames():
    while True:
        try:
            frame = camera.capture_frame()
            ok, buffer = cv2.imencode(".jpg", frame)
            if not ok:
                time.sleep(0.05)
                continue
            yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + buffer.tobytes() + b"\r\n"
        except Exception:
            time.sleep(0.2)


@app.route("/preview")
def preview():
    return Response(gen_frames(), mimetype="multipart/x-mixed-replace; boundary=frame")


@app.route("/settings", methods=["GET", "POST"])
def settings():
    if request.method == "POST":
        threshold = request.form.get("threshold", str(CONFIG.DEFAULT_THRESHOLD)).strip()
        email_enabled = "1" if request.form.get("email_enabled") == "on" else "0"
        email_on_granted = "1" if request.form.get("email_on_granted") == "on" else "0"
        attach_photo = "1" if request.form.get("attach_photo") == "on" else "0"
        email_cooldown_sec = request.form.get("email_cooldown_sec", "30").strip()

        db.set_setting("threshold", threshold)
        db.set_setting("email_enabled", email_enabled)
        db.set_setting("email_on_granted", email_on_granted)
        db.set_setting("attach_photo", attach_photo)
        db.set_setting("email_cooldown_sec", email_cooldown_sec)

        flash("Settings saved.")
        return redirect(url_for("settings"))

    current_threshold = db.get_setting("threshold", str(CONFIG.DEFAULT_THRESHOLD))
    email_enabled = (db.get_setting("email_enabled", "1" if CONFIG.EMAIL_ENABLED_DEFAULT else "0") == "1")
    email_on_granted = (db.get_setting("email_on_granted", "0") == "1")
    attach_photo = (db.get_setting("attach_photo", "1") == "1")
    email_cooldown_sec = db.get_setting("email_cooldown_sec", "30")

    return render_template(
        "settings.html",
        threshold=current_threshold,
        email_enabled=email_enabled,
        email_on_granted=email_on_granted,
        attach_photo=attach_photo,
        email_cooldown_sec=email_cooldown_sec,
    )


def start_background_threads():
    threading.Thread(target=motion_loop, daemon=True).start()

@app.route("/reset_model", methods=["POST"])
def reset_model():
    global recognizer
    try:
        try:
            if os.path.exists(CONFIG.MODEL_PATH):
                os.remove(CONFIG.MODEL_PATH)
            if os.path.exists(CONFIG.LABELS_PATH):
                os.remove(CONFIG.LABELS_PATH)
        except Exception:
            pass

        with recognizer_lock:
            recognizer = FaceRecognizer(
                CONFIG.MODEL_PATH,
                CONFIG.LABELS_PATH,
                threshold=get_threshold()
            )

        flash("Model reset: lbph.yml and labels.json cleared.")
    except Exception as e:
        flash(f"Reset model failed: {e}")

    return redirect(url_for("settings"))


@app.route("/clear_events", methods=["POST"])
def clear_events():
    try:
        db.clear_events()
        flash("All events cleared.")
    except Exception as e:
        flash(f"Clear events failed: {e}")
    return redirect(url_for("settings"))


if __name__ == "__main__":
    start_background_threads()
    app.run(host="0.0.0.0", port=5000, debug=True, use_reloader=False)
