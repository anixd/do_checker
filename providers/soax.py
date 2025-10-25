from __future__ import annotations
import os, json
from dataclasses import dataclass, field
from typing import Any, Dict

from config.loader import ConfigStore
from logging_.engine_logger import get_engine_logger

log = get_engine_logger()

CATALOG_PATH = None


def _catalog_path() -> str:
    """Gets the path to the geo catalog, respecting config."""
    global CATALOG_PATH
    if CATALOG_PATH:
        return CATALOG_PATH

    try:
        data_dir = ConfigStore.get().paths.data_dir
        CATALOG_PATH = os.path.join(data_dir, "catalog", "soax_geo.json")
        return CATALOG_PATH
    except Exception as e:
        # This might happen if ConfigStore failed, which is fatal anyway
        log.error(f"Failed to resolve CATALOG_PATH: {e}")
        return "./data/catalog/soax_geo.json"  # Fallback


class CatalogStore:
    _cache: dict | None = None

    @classmethod
    def _load_or_cache(cls) -> dict:
        if cls._cache:
            return cls._cache
        try:
            with open(_catalog_path(), "r", encoding="utf-8") as f:
                cls._cache = json.load(f)
                return cls._cache
        except Exception as e:
            log.error(f"Failed to load soax_geo.json from {_catalog_path()}: {e}")
            return {"version": 0, "countries": []}

    @classmethod
    def get_countries(cls) -> list[dict]:
        data = cls._load_or_cache()
        # Return simplified list: [{"code": "TR", "name": "Turkey"}, ...]
        return [{"code": c.get("code"), "name": c.get("name")}
                for c in data.get("countries", [])
                if c.get("code") and c.get("name")]

    @classmethod
    def get_regions(cls, country_code: str) -> list[dict]:
        data = cls._load_or_cache()
        for c in data.get("countries", []):
            if c.get("code") == country_code:
                # Return [{"code": "TR-35", "name": "Izmir"}, ...]
                return c.get("regions", [])
        return []

    @classmethod
    def get_cities(cls, country_code: str, region_code: str | None = None) -> list[dict]:
        # TBD: Current JSON structure doesn't support cities nested by region.
        # For MVP, we'll assume cities (if any) are top-level to the country.
        data = cls._load_or_cache()
        for c in data.get("countries", []):
            if c.get("code") == country_code:
                # Return [{"code": "ankara", "name": "Ankara"}, ...]
                return c.get("cities", [])
        return []

    @classmethod
    def get_isps(cls, country_code: str) -> list[str]:
        data = cls._load_or_cache()
        for c in data.get("countries", []):
            if c.get("code") == country_code:
                # Return ["Turk Telekom", "Vodafone TR", ...]
                return c.get("isps", [])
        return []

    @classmethod
    def save(cls, data: dict):
        """Saves data back to the JSON file."""
        try:
            with open(_catalog_path(), "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            cls._cache = None  # Invalidate cache
        except Exception as e:
            log.error(f"Failed to save soax_geo.json to {_catalog_path()}: {e}")


@dataclass
class ProxySession:
    type: str
    host: str
    port: int
    username: str
    password: str
    session_id: str | None
    ext_ip: str | None
    debug_info: Dict[str, Any] = field(default_factory=dict)


def get_session(params: dict[str, Any]) -> ProxySession:
    """
    Конструируем параметры SOAX прокси на основе выбранного режима.
    Пока реализован только 'Port-mode'.
    """
    cfg = ConfigStore.get().soax

    # TBD: Здесь будет логика выбора (if mode == 'port' vs if mode == 'session')
    # Пока жестко используем Port-mode

    # 1. Login (Берется только из .env)
    login = cfg.port_login
    if not login:
        raise ValueError("SOAX_PORT_LOGIN is not set in .env")

    # 2. Host (Приоритет: Форма > .env)
    host = params.get("proxy_host") or cfg.host

    # 3. Port (Приоритет: Форма > .env)
    port_str = params.get("proxy_port")
    port = int(port_str) if port_str else cfg.port_default_port

    # 4. Password (Собирается из формы)
    # Формат: <connection> ; <country> ; <isp> ; <region> ; <city>
    # (См. §4.1 в project_tech_spec.md)

    # Заглушка, т.к. в форме пока нет 'slug' для isp, region, city
    # Мы используем 'code' для region/city и 'slug' для isp

    p_conn = params.get("connection_type", "wifi")  # 'wifi' по умолчанию
    p_country = params.get("country")
    p_isp = params.get("isp") or ""
    p_region = params.get("region_code") or ""
    p_city = params.get("city") or ""

    # SOAX требует '+' вместо пробелов в ISP, если они есть
    p_isp = p_isp.replace(" ", "+")

    password_string = f"{p_conn};{p_country};{p_isp};{p_region};{p_city}"

    debug_data = {
        "mode": "Port-mode",
        "raw_login": f"{login[:4]}...{login[-4:]}" if login else "(not set)",
        "raw_password": password_string,
        "raw_host": host,
        "raw_port": port,
        "source_params": {
            "country": p_country,
            "region": p_region,
            "city": p_city,
            "isp": p_isp,
            "conn_type": p_conn,
            "host_override": params.get("proxy_host"),
            "port_override": params.get("proxy_port"),
        }
    }

    return ProxySession(
        type=params.get("proxy_type", "http"),
        host=host,
        port=port,
        username=login,
        password=password_string,
        session_id=None,  # В Port-режиме session_id не используется
        ext_ip=None,  # TBD: Можно получить, сделав запрос к http://checker.soax.com/api/ipinfo
        debug_info=debug_data
    )
