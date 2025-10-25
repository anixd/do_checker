import os, json
from dataclasses import dataclass
from config.loader import ConfigStore

CATALOG_PATH = None

def _catalog_path():
    global CATALOG_PATH
    if CATALOG_PATH: return CATALOG_PATH
    data_dir = ConfigStore.get().paths.data_dir
    CATALOG_PATH = os.path.join(data_dir, "catalog", "soax_geo.json")
    return CATALOG_PATH

class CatalogStore:
    @staticmethod
    def load() -> dict:
        try:
            with open(_catalog_path(), "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {"version":1,"generated_at":None,"countries":[]}

    @staticmethod
    def save(data: dict):
        with open(_catalog_path(), "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)

def refresh_catalog() -> dict:
    """
    Заглушка v0.2 — реальная интеграция с SOAX API позже.
    """
    data = CatalogStore.load()
    if not data.get("countries"):
        # Добавим минимальный пример, чтобы форма была пригодна
        data = {
            "version": 1,
            "generated_at": None,
            "countries": [
                {"code":"TR","name":"Turkey","regions":[{"code":"TR-35","name":"Izmir Province"}],"isps":["Turk Telekom","Vodafone TR","Turkcell"]},
                {"code":"KZ","name":"Kazakhstan","regions":[{"code":"KZ-ALA","name":"Almaty"}],"isps":["Kazakhtelecom"]}
            ]
        }
        CatalogStore.save(data)
    return data

@dataclass
class ProxySession:
    type: str
    host: str
    port: int
    username: str
    password: str
    session_id: str | None
    ext_ip: str | None

def get_session(country: str, region_code: str | None, isp: str | None,
                sticky: bool, ttl_sec: int, proxy_type: str, dns_mode: str) -> ProxySession:
    """
    Конструируем параметры SOAX прокси. Sticky — через username-сессию (условно).
    """
    cfg = ConfigStore.get()
    host = os.environ.get("SOAX_HOST", cfg and "proxy.soax.com" or "proxy.soax.com")
    port = int(os.environ.get("SOAX_PORT", "5000"))
    user = os.environ.get("SOAX_USER", "")
    pwd  = os.environ.get("SOAX_PASS", "")

    # в username добавляем параметры (как это обычно делает SOAX).
    # Конкретную схему подправим позже.
    params = []
    if country: params.append(f"country-{country}")
    if region_code: params.append(f"region-{region_code}")
    if isp: params.append(f"isp-{isp}")
    session_id = None
    if sticky:
        session_id = f"sess{os.getpid()}"
        params.append(f"session-{session_id}")

    if params:
        user_effective = user + ":" + ";".join(params)
    else:
        user_effective = user

    return ProxySession(
        type=proxy_type,
        host=host,
        port=port,
        username=user_effective,
        password=pwd,
        session_id=session_id,
        ext_ip=None,  # можно определить позже отдельным запросом
    )
