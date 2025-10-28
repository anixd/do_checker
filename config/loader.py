from __future__ import annotations
import os, yaml
from dataclasses import dataclass, fields, field
from typing import Any, Dict

@dataclass
class AppCfg:
    host: str
    port: int


@dataclass
class LoggingCfg:
    level: str


@dataclass
class PathsCfg:
    logs_dir: str
    data_dir: str


@dataclass
class ExecCfg:
    max_concurrency: int
    timeout_sec: int


@dataclass
class ProxyCfg:
    type: str
    dns_mode: str
    sticky_policy: str
    sticky_ttl_sec: int


@dataclass
class ShotsCfg:
    enabled_default: bool
    max_workers: int
    width: int
    height: int
    timeout_sec: int
    wait_after_load_sec: int


@dataclass
class SoaxCfg:
    host: str
    port_default_port: int
    port_login: str
    port_sticky: int
    package_id: str | None
    session_password: str | None
    api_key: str | None
    package_key: str | None


@dataclass
class HttpCfg:
    user_agent: str
    accept: str
    accept_language: str
    custom_headers: Dict[str, str] = field(default_factory=dict)


@dataclass
class RootCfg:
    app: AppCfg
    logging: LoggingCfg
    paths: PathsCfg
    execution: ExecCfg
    proxy: ProxyCfg
    screenshots: ShotsCfg
    soax: SoaxCfg
    http_client: HttpCfg


class ConfigStore:
    _cfg: RootCfg = None
    _yaml_text: str = ""

    @classmethod
    def init(cls):
        data_dir = os.environ.get("DATA_DIR", "/data")
        app_yaml = os.path.join(data_dir, "config", "app.yaml")

        try:
            with open(app_yaml, "r", encoding="utf-8") as f:
                text = f.read()
                cls._yaml_text = text
                data = yaml.safe_load(text)
        except FileNotFoundError:
            print(f"FATAL: Config file not found at {app_yaml}")
            print(f"       (Make sure ./data/config/app.yaml exists locally)")
            raise

        # defaults для logger
        if "logging" not in data:
            data["logging"] = {"level": "INFO"}

        # defaults для screenshots
        if "screenshots" not in data:
            data["screenshots"] = {
                "enabled_default": False,
                "max_workers": 1,
                "width": 1366,
                "height": 768,
                "timeout_sec": 30,
                "wait_after_load_sec": 0
            }

        # defaults для soax и http_client
        if "soax" not in data:
            data["soax"] = {
                "host": "proxy.soax.com",
                "port_default_port": 9001,
                "port_login": "",
                "port_sticky": 5000,
                "package_id": None,
                "session_password": None,
                "api_key": None,
                "package_key": None
            }
        if "http_client" not in data:
            data["http_client"] = {
                "user_agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36",
                "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "accept_language": "en-US,en;q=0.5"

            }
        elif "custom_headers" not in data["http_client"]:
            # Для обратной совместимости, если http_client есть, а ключа нет
            data["http_client"]["custom_headers"] = {}

        cls._cfg = RootCfg(
            app=AppCfg(**data["app"]),
            logging=LoggingCfg(**data["logging"]),
            paths=PathsCfg(**data["paths"]),
            execution=ExecCfg(**data["execution"]),
            proxy=ProxyCfg(**data["proxy"]),
            screenshots=ShotsCfg(**data["screenshots"]),
            soax=SoaxCfg(**data["soax"]),
            http_client=HttpCfg(**data["http_client"])
        )

        cls._override_from_env(cls._cfg)

        os.makedirs(cls._cfg.paths.data_dir, exist_ok=True)
        os.makedirs(cls._cfg.paths.logs_dir, exist_ok=True)

    @classmethod
    def _override_from_env(cls, cfg: RootCfg):
        env_map = {
            "APP_HOST": (cfg.app, "host"),
            "APP_PORT": (cfg.app, "port", int),
            "LOG_LEVEL": (cfg.logging, "level"),
            "LOG_DIR": (cfg.paths, "logs_dir"),
            "DATA_DIR": (cfg.paths, "data_dir"),
            "MAX_CONCURRENCY": (cfg.execution, "max_concurrency", int),
            "CHECK_TIMEOUT_SEC": (cfg.execution, "timeout_sec", int),
            "PROXY_TYPE": (cfg.proxy, "type"),
            "DNS_MODE": (cfg.proxy, "dns_mode"),
            "STICKY_POLICY": (cfg.proxy, "sticky_policy"),
            "STICKY_TTL_SEC": (cfg.proxy, "sticky_ttl_sec", int),
            "MAX_SCREENSHOT_WORKERS": (cfg.screenshots, "max_workers", int),
            "SCREENSHOT_TIMEOUT_SEC": (cfg.screenshots, "timeout_sec", int),
            "SCREENSHOT_WAIT_AFTER_LOAD_SEC": (cfg.screenshots, "wait_after_load_sec", int),

            "SOAX_HOST": (cfg.soax, "host"),
            "SOAX_PORT_DEFAULT_PORT": (cfg.soax, "port_default_port", int),
            "SOAX_PORT_LOGIN": (cfg.soax, "port_login"),
            "SOAX_PORT_STICKY": (cfg.soax, "port_sticky", int),
            "SOAX_PACKAGE_ID": (cfg.soax, "package_id"),
            "SOAX_SESSION_PASSWORD": (cfg.soax, "session_password"),
            "SOAX_API_KEY": (cfg.soax, "api_key"),
            "SOAX_PACKAGE_KEY": (cfg.soax, "package_key"),
            "USER_AGENT": (cfg.http_client, "user_agent"),
        }

        for env_key, info in env_map.items():
            val = os.environ.get(env_key)
            if val is not None:
                obj, attr_name = info[0], info[1]
                cast_func = info[2] if len(info) > 2 else str

                try:
                    setattr(obj, attr_name, cast_func(val))
                except (ValueError, TypeError):
                    print(f"Warning: Could not cast env var {env_key}={val} to {cast_func}")

    @classmethod
    def get(cls) -> RootCfg:
        if cls._cfg is None:
            cls.init()
        return cls._cfg

    @classmethod
    def raw_yaml(cls) -> str:
        return cls._yaml_text

    @classmethod
    def save_yaml(cls, text: str):
        data_dir = cls.get().paths.data_dir
        app_yaml = os.path.join(data_dir, "config", "app.yaml")

        try:
            yaml.safe_load(text)
            with open(app_yaml, "w", encoding="utf-8") as f:
                f.write(text)
            cls._yaml_text = text
            cls.init()
        except Exception as e:
            print(f"Error saving YAML to {app_yaml}: {e}")
