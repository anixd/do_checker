import os
import markdown
from config.loader import ConfigStore
from logging_.engine_logger import get_engine_logger

log = get_engine_logger()

# Кеш для MD-файла, чтобы не читать его с диска при каждом запросе
_md_cache: dict[str, tuple[float, str]] = {}


def render_markdown_file(file_name: str) -> str:
    """
    Reads a markdown file from the data/help directory,
    converts it to HTML, and returns the HTML.
    Uses a simple cache based on file modification time.
    """
    cfg = ConfigStore.get()
    file_path = os.path.join(cfg.paths.data_dir, "help", file_name)

    try:
        mtime = os.path.getmtime(file_path)

        # Проверяем кеш
        if file_name in _md_cache:
            cached_mtime, cached_html = _md_cache[file_name]
            if mtime == cached_mtime:
                log.debug(f"Serving cached version of {file_name}")
                return cached_html

        # Если кеша нет или файл изменился
        log.info(f"Loading and rendering {file_path} from disk...")
        with open(file_path, "r", encoding="utf-8") as f:
            text = f.read()

        # extensions=['fenced_code', 'tables'] - для подсветки кода и таблиц
        html = markdown.markdown(text, extensions=['fenced_code', 'tables'])

        _md_cache[file_name] = (mtime, html)
        return html

    except FileNotFoundError:
        log.warning(f"Help file not found at: {file_path}")
        return f"<h1>Ошибка</h1><p>Файл справки не найден: <code>{file_path}</code></p>"
    except Exception as e:
        log.error(f"Error rendering markdown file {file_path}: {e}", exc_info=True)
        return f"<h1>Ошибка</h1><p>Не удалось обработать файл справки: {e}</p>"
