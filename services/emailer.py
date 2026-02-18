import smtplib
from email.message import EmailMessage
from typing import Optional

class Emailer:
    def __init__(self, host, port, username, password, email_from, email_to):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.email_from = email_from
        self.email_to = email_to

    def send(self, subject: str, body: str, image_jpg_bytes: Optional[bytes] = None):
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = self.email_from
        msg["To"] = self.email_to
        msg.set_content(body)

        if image_jpg_bytes:
            msg.add_attachment(
                image_jpg_bytes,
                maintype="image",
                subtype="jpeg",
                filename="visitor.jpg"
            )

        with smtplib.SMTP(self.host, self.port, timeout=20) as s:
            s.ehlo()
            s.starttls()
            s.ehlo()
            s.login(self.username, self.password)
            s.send_message(msg)

    def send_access_denied(self, body: str, image_jpg_bytes: Optional[bytes] = None):
        self.send("Smart Door Alert: Access Denied", body, image_jpg_bytes)

    def send_access_granted(self, body: str, image_jpg_bytes: Optional[bytes] = None):
        self.send("Smart Door: Access Granted", body, image_jpg_bytes)
