import threading
import time
import os
import requests
from logging_.engine_logger import get_engine_logger
from packaging import version

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
    Проверяет обновления при старте и каждые 3 часа.
    """
    log.info("Update checker thread started. Initial check in 20 seconds...")
    time.sleep(20)  # Даем приложению запуститься

    while True:
        try:
            log.info("Checking for new version...")

            # 1. Получаем удаленный текст версии
            try:
                response = requests.get(REMOTE_VERSION_URL, timeout=15)
                response.raise_for_status()
                remote_version_str = response.text.strip()
            except requests.exceptions.RequestException as e:
                log.warning(f"Failed to fetch remote VERSION file: {e}")
                time.sleep(10800)
                continue

            # 2. Получаем локальный текст версии
            try:
                with open(LOCAL_VERSION_FILE, "r") as f:
                    local_version_str = f.read().strip()
            except FileNotFoundError:
                log.error(f"FATAL: Local VERSION file not found at {LOCAL_VERSION_FILE}. Update check disabled.")
                _set_update_status(False)
                return
            except Exception as e:
                log.error(f"Failed to read local VERSION file: {e}")
                time.sleep(10800)
                continue

            # 3. Сравниваем версии (SemVer)
            try:
                v_remote = version.parse(remote_version_str)
                v_local = version.parse(local_version_str)

                if v_remote > v_local:
                    log.info(f"Update available! Local={local_version_str}, Remote={remote_version_str}")
                    _set_update_status(True)
                else:
                    log.info(f"App is up to date (Local={local_version_str}, Remote={remote_version_str})")
                    _set_update_status(False)
            except Exception as e:
                log.error(f"Failed to parse version strings: {e}")
                # Fallback к обычному сравнению, если формат строк не соответствует SemVer
                _set_update_status(local_version_str != remote_version_str and remote_version_str != "")

            # 4. спим 3 часа
            time.sleep(10800)

        except Exception as e:
            log.error(f"Unhandled error in update checker thread: {e}", exc_info=True)
            log.info("Retrying update check in 3 hours...")
            time.sleep(10800)
