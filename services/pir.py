import time

try:
    import RPi.GPIO as GPIO
except Exception:
    GPIO = None

class PIRSensor:
    def __init__(self, pin: int):
        self.pin = pin
        self.enabled = GPIO is not None

    def setup(self):
        if not self.enabled:
            return
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(self.pin, GPIO.IN)

    def cleanup(self):
        if not self.enabled:
            return
        GPIO.cleanup()

    def wait_for_motion(self, poll_interval: float = 0.1) -> bool:
        if not self.enabled:
            time.sleep(1.0)
            return True

        while True:
            if GPIO.input(self.pin) == 1:
                return True
            time.sleep(poll_interval)
