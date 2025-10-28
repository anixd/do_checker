import logging, os
from datetime import datetime
from logging import Formatter
from logging import FileHandler
from flask import Flask, request, Response
from config.loader import ConfigStore

_engine_logger = None


def get_engine_logger():
    """
    Gets the singleton logger instance.
    Setup is handled by setup_loggers().
    """
    global _engine_logger
    if _engine_logger is None:
        _engine_logger = logging.getLogger("engine")
        # Уровень будет установлен в setup_loggers()
    return _engine_logger


def setup_loggers(app: Flask):
    """
    Initializes and configures both 'engine' and 'access' loggers
    based on the global config.
    """
    cfg = ConfigStore.get()
    log_dir = cfg.paths.logs_dir
    os.makedirs(log_dir, exist_ok=True)

    # Получаем уровень лога из конфига
    log_level_str = cfg.logging.level.upper()
    log_level = getattr(logging, log_level_str, logging.INFO)

    # Настраиваем логер для "engine"
    engine_logger = get_engine_logger()  # Получаем/создаем инстанс
    engine_logger.setLevel(log_level)

    # formatter (%(asctime)s по умолчанию использует localtime, что уважает TZ)
    engine_fmt = Formatter(
        "%(asctime)s [%(levelname)s] %(message)s",
        "%Y-%m-%d %H:%M:%S"  # Формат времени
    )
    engine_handler = FileHandler(os.path.join(log_dir, "engine.log"))
    engine_handler.setFormatter(engine_fmt)
    engine_logger.addHandler(engine_handler)

    # Запрещаем логам "всплывать" к Gunicorn
    engine_logger.propagate = False

    # логгер access.log
    access_logger = logging.getLogger("access")
    access_logger.setLevel(logging.INFO)  # access.log приложения всегда уровня INFO

    access_handler = FileHandler(os.path.join(log_dir, "access.log"))
    # Форматтер здесь простой, т.к. мы сами формируем сообщение
    access_fmt = Formatter('%(message)s')
    access_handler.setFormatter(access_fmt)
    access_logger.addHandler(access_handler)
    access_logger.propagate = False

    # регистрируем хук Flask для логирования доступа
    @app.after_request
    def log_access(response: Response):
        # не логируем SSE (слишком дофуя шумно) и статику
        if request.path.startswith('/events/') or request.path.startswith('/static/'):
            return response

        # Формируем строку лога (asctime добавит сам Formatter, но нам нужно свое время)
        # Используем datetime.now(), который также уважает TZ
        ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        access_logger.info(
            f'[{ts}] {request.remote_addr} - "{request.method} {request.full_path}" '
            f'{response.status_code}'
        )
        return response

    engine_logger.info(f"Loggers initialized. Engine log level set to {log_level_str}.")
