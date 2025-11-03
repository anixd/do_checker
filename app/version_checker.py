import threading
import time
import os
import requests
from logging_.engine_logger import get_engine_logger

log = get_engine_logger()

REMOTE_VERSION_URL = "https://raw.githubusercontent.com/anixd/do_checker/master/VERSION"

LOCAL_VERSION_FILE = os.path.abspath("./VERSION")

# Глобальное состояние
UPDATE_AVAILABLE = False
_lock = threading.Lock()


def get_update_status() -> bool:
    """
    Безопасно получает текущий статус обновления.
    """
    with _lock:
        return UPDATE_AVAILABLE


def _set_update_status(status: bool):
    """
    Безопасно устанавливает статус обновления.
    """
    global UPDATE_AVAILABLE
    with _lock:
        UPDATE_AVAILABLE = status


def check_for_updates_thread():
    """
    Функция для запуска в фоновом потоке (daemon thread).
    Проверяет обновления при старте и каждые 6 часов.
    """
    log.info("Update checker thread started. Initial check in 10 seconds...")
    time.sleep(10)  # Даем приложению запуститься

    while True:
        try:
            log.info("Checking for new version...")

            # 1. Получаем удаленный хэш
            try:
                response = requests.get(REMOTE_VERSION_URL, timeout=15)
                response.raise_for_status()
                remote_hash = response.text.strip()
            except requests.exceptions.RequestException as e:
                log.warning(f"Failed to fetch remote VERSION file: {e}")
                # Пропускаем эту проверку, попробуем через 6 часов
                time.sleep(21600)
                continue

            # 2. Получаем локальный хэш
            try:
                with open(LOCAL_VERSION_FILE, "r") as f:
                    local_hash = f.read().strip()
            except FileNotFoundError:
                log.error(f"FATAL: Local VERSION file not found at {LOCAL_VERSION_FILE}. Update check disabled.")
                # Файла нет, проверять бессмысленно.
                _set_update_status(False)
                return  # Завершаем поток
            except Exception as e:
                log.error(f"Failed to read local VERSION file: {e}")
                time.sleep(21600)  # 24 hours
                continue

            # 3. Сравниваем хеши
            if local_hash != remote_hash and remote_hash:
                log.info(f"Update available! Local={local_hash}, Remote={remote_hash}")
                _set_update_status(True)
            else:
                log.info(f"App is up to date (Local={local_hash})")
                _set_update_status(False)

            # 4. спим 6 часов
            time.sleep(21600)

        except Exception as e:
            # Общий логер, чтобы поток никогда не падал
            log.error(f"Unhandled error in update checker thread: {e}", exc_info=True)
            log.info("Retrying update check in 24 hours...")
            time.sleep(21600)
