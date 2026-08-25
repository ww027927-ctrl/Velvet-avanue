import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATABASE = BASE_DIR / "velvet_avenue.db"
SECRET_KEY = os.getenv("SECRET_KEY", "velvet-avenue-demo-secret")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5.6")
