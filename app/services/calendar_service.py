import requests
import urllib.request
from pathlib import Path

def load_ics(source: str) -> str:
    """Загружает ICS из файла или URL."""
    if source.startswith("http://") or source.startswith("https://"):
        
        with urllib.request.urlopen(source, timeout=15) as resp:
            raw = resp.read()
        return raw.decode("utf-8", errors="replace")
    else:
        return Path(source).read_text(encoding="utf-8")
