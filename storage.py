import pickle
from collections import deque
from pathlib import Path

# Путь к файлу для хранения обработанных ID
DATA_FILE = Path("processed_ids.pkl")
MAX_IDS = 10000

def load_processed_ids():
    """Загружает обработанные ID из файла."""
    if DATA_FILE.exists():
        with open(DATA_FILE, "rb") as file:
            return pickle.load(file)
    return deque(maxlen=MAX_IDS)

def save_processed_ids(processed_ids):
    """Сохраняет обработанные ID в файл."""
    with open(DATA_FILE, "wb") as file:
        pickle.dump(processed_ids, file)
