from __future__ import annotations
import requests
from typing import Any, Dict, List
from config.loader import ConfigStore
from logging_.engine_logger import get_engine_logger

log = get_engine_logger()

BASE_URL = "https://api.soax.com/api/"


class SoaxApiClient:
    """
    Клиент для API SOAX (api.soax.com) для получения каталогов Гео.
    Это НЕ клиент для *использования* прокси (proxy.soax.com).
    """

    def __init__(self):
        cfg = ConfigStore.get()
        self.api_key = cfg.soax.api_key
        self.package_key = cfg.soax.package_key

        if not self.api_key or not self.package_key:
            log.error("SOAX_API_KEY or SOAX_PACKAGE_KEY are not set in .env")
            # не падаем, но is_configured() вернет False

        self.user_agent = cfg.http_client.user_agent
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": self.user_agent})

    def is_configured(self) -> bool:
        """Проверяет, установлены ли ключи API."""
        return bool(self.api_key and self.package_key)

    def _make_request(self, endpoint: str, params: Dict[str, Any]) -> Any | None:
        """Хелпер для выполнения GET-запросов к API."""
        if not self.is_configured():
            log.error(f"SOAX API call to {endpoint} skipped: API keys not configured.")
            return None

        # добавляем ключи в каждый запрос
        params["api_key"] = self.api_key
        params["package_key"] = self.package_key

        try:
            response = self.session.get(f"{BASE_URL}{endpoint}", params=params, timeout=30)

            # 1. проверяем на ошибки 4xx/5xx
            response.raise_for_status()

            # 2. пытаемся парсить json
            try:
                data = response.json()
                return data

            except requests.exceptions.JSONDecodeError as e:
                log.error(
                    f"SOAX API invalid JSON response for {endpoint}. Status: {response.status_code}, Text: {response.text[:200]}...")
                return None

        except requests.exceptions.HTTPError as e:
            # Ошибка 4xx/5xx
            log.error(
                f"SOAX API HTTP error for {endpoint}. Status: {e.response.status_code}, Response: {e.response.text[:200]}...")
            return None
        except requests.exceptions.RequestException as e:
            # Ошибка сети
            log.error(f"SOAX API request failed for {endpoint}: {e}")
            return None

    def get_regions(self, country_code: str, conn_type: str = "wifi") -> List[Dict[str, str]] | None:
        """
        Получает список регионов для страны.
        (https://helpcenter.soax.com/en/articles/6227864-getting-a-list-of-regions)

        Возвращает: [{"region": "moscow", "region_slug": "moscow"}, ...]
        """
        params = {
            "country_iso": country_code,
            "conn_type": conn_type,
        }
        return self._make_request("get-country-regions", params)

    def get_cities(self, country_code: str, region: str | None = None, conn_type: str = "wifi") -> List[Dict[
        str, str]] | None:
        """
        Получает список городов для страны (опционально - региона).
        (https://helpcenter.soax.com/en/articles/6228092-getting-a-list-of-cities)

        Возвращает: [{"city": "Moscow", "city_slug": "moscow"}, ...]
        """
        params = {
            "country_iso": country_code,
            "conn_type": conn_type,
        }
        if region:
            params["region"] = region

        return self._make_request("get-country-cities", params)

    def get_isps(self, country_code: str, region: str | None = None, city: str | None = None) -> List[Dict[
        str, str]] | None:
        """
        Получает список ISP для страны (опционально - региона/города).
        (https://helpcenter.soax.com/en/articles/6228391-getting-a-list-of-wifi-isps)

        Возвращает: [{"isp": "Some ISP", "isp_slug": "some-isp"}, ...]
        """
        params = {
            "country_iso": country_code,
        }
        if region:
            params["region"] = region
        if city:
            params["city"] = city

        return self._make_request("get-country-isp", params)
