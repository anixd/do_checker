import logging, os
from config.loader import ConfigStore

_engine_logger = None

def get_engine_logger():
    global _engine_logger
    if _engine_logger:
        return _engine_logger
    cfg = ConfigStore.get()
    log_dir = cfg.paths.logs_dir
    os.makedirs(log_dir, exist_ok=True)
    logger = logging.getLogger("engine")
    logger.setLevel(logging.INFO)
    fh = logging.FileHandler(os.path.join(log_dir, "engine.log"))
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    fh.setFormatter(fmt)
    logger.addHandler(fh)
    _engine_logger = logger
    return logger
