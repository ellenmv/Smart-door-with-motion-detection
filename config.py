from dataclasses import dataclass
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

@dataclass
class Config:
    DB_PATH: str = str(BASE_DIR / "data" / "smartdoor.db")
    MODEL_PATH: str = str(BASE_DIR / "data" / "models" / "lbph.yml")
    LABELS_PATH: str = str(BASE_DIR / "data" / "models" / "labels.json")
    FACES_DIR: str = str(BASE_DIR / "data" / "faces")
    LOG_PATH: str = str(BASE_DIR / "logs" / "smartdoor.log")

    CAMERA_INDEX: int = 0

    PIR_ENABLED: bool = False
    PIR_GPIO_PIN: int = 17

    EMAIL_ENABLED_DEFAULT: bool =  True
    EMAIL_TO: str = "ellenmavrogianni@gmail.com"
    EMAIL_FROM: str = "ellenmavrogianni@gmail.com"
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USERNAME: str = "ellenmavrogianni@gmail.com"
    SMTP_PASSWORD: str = "xvevnjwegrguftzr"

    DEFAULT_THRESHOLD: float = 60.0

CONFIG = Config()
