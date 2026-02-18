#  Smart Door – Face Recognition Access Validation

Smart Door is a smart access control system based on face recognition, designed as a Ubiquitous / Pervasive Computing project.  
The system detects motion near a door, captures an image, performs face recognition using OpenCV, and decides whether access should be granted or denied.

If an unknown person is detected, the system logs the event and sends an email notification to the owner.


##  Project Overview

Traditional access methods such as keys or PIN codes can be lost, copied, or shared.  
Smart Door provides a more natural and automated approach by using biometric identification.

Core ideas of the project:

- Context-aware activation using a PIR motion sensor
- Autonomous decision-making (Access Granted / Access Denied)
- Local processing on Raspberry Pi
- Event logging and notifications
- Simple web interface for monitoring and management


##  Features

- Real-time face detection and recognition (OpenCV)
- PIR sensor based motion triggering
- Automatic camera activation
- Access control decision logic
- Event logging with timestamp (SQLite)
- Email notifications for unauthorized access
- Web dashboard (Flask UI)
- Capture and training of new users
- Delete authorized users from UI
- Live camera preview
- Adjustable recognition threshold


##  System Architecture

The system consists of the following modules:

1. **Motion Detection**
   - PIR sensor detects movement near the door.

2. **Image Capture**
   - Camera captures visitor image when triggered.

3. **Face Recognition**
   - OpenCV detects and compares faces with trained data.

4. **Decision Engine**
   - Generates Access Granted or Access Denied.

5. **Notification & Logging**
   - Stores events in SQLite database.
   - Sends email alerts for denied access.

6. **Web Interface**
   - Displays system status and event history.
   - Allows training, triggering, and management.


##  Hardware

- Raspberry Pi 4
- USB Camera (or Pi Camera)
- PIR Motion Sensor
- microSD card (256GB used during development)

> During development and testing, the system was fully validated using a laptop camera before hardware deployment.



##  Software Stack

- Python
- OpenCV
- Flask
- SQLite
- SMTP (Email notifications)



##  Installation

### 1. Clone repository

git clone 
cd smart-door

2. Create virtual environment
python -m venv .venv


Activate:

Windows:

.venv\Scripts\activate


Linux / Mac:

source .venv/bin/activate

3. Install dependencies
pip install -r requirements.txt

 Running the System
python app.py


### Open browser:

http://localhost:5000


or from another device in the same network:

http://<raspberry-pi-ip>:5000

### Training a New Person

Open Web UI

Enter person name

Capture samples

Press Train Model

Person is added to authorized list

### Delete Authorized Person

Use the Delete button in the UI.
The model automatically retrains after deletion.

### Email Notifications

The system supports SMTP notifications.

Configure in config.py:

SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587
SMTP_USERNAME = "your_email@gmail.com"
SMTP_PASSWORD = "your_app_password"
EMAIL_TO = "receiver_email@gmail.com"

## Performance (Experimental Results)

Response time: ~0.5 – 1.0 sec

Recognition accuracy: ~85 – 95%

Stable operation during continuous testing

Performance depends on lighting and camera angle.

## Current Limitations

Supports one face at a time

No liveness detection

Recognition affected by poor lighting

Designed for local network usage

## Future Improvements

Liveness detection

Multi-face recognition

Mobile application

Push notifications

Cloud storage for events

## References

OpenCV Documentation

Flask Documentation

Raspberry Pi Documentation

# Author

Eleni Mavrogianni


