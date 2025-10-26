from flask import Blueprint, send_from_directory
from config.loader import ConfigStore
import os

static_bp = Blueprint('static_logs', __name__)

@static_bp.route('/logs/<path:filename>')
def serve_log_file(filename):
    """Раздает файлы из директории логов."""
    cfg = ConfigStore.get()
    # Flask требует абсолютный путь
    log_directory = os.path.abspath(cfg.paths.logs_dir)
    # Разбиваем filename на директорию (YYYY-MM-DD) и имя файла
    try:
        # Пытаемся безопасно отправить файл
        # send_from_directory защищает от выхода за пределы log_directory
        return send_from_directory(log_directory, filename)
    except FileNotFoundError:
        return "File not found", 404

# Можно добавить еще роуты, например, для /data/, если понадобится
# @static_bp.route('/data/<path:filename>')
# def serve_data_file(filename):
#     cfg = ConfigStore.get()
#     data_directory = os.path.abspath(cfg.paths.data_dir)
#     # ОСТОРОЖНО: Раздавать все из /data может быть небезопасно!
#     # Лучше ограничить конкретными подпапками, если нужно.
#     try:
#         return send_from_directory(data_directory, filename)
#     except FileNotFoundError:
#         return "File not found", 404
