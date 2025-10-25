import os, yaml
from dataclasses import dataclass

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
    type: str           # http | socks5
    dns_mode: str       # local | proxy
    sticky_policy: str  # auto | on | off
    sticky_ttl_sec: int

@dataclass
class ShotsCfg:
    enabled_default: bool
    max_workers: int
    width: int
    height: int

@dataclass
class AppCfg:
    host: str
    port: int

@dataclass
class RootCfg:
    app: AppCfg
    paths: PathsCfg
    execution: ExecCfg
    proxy: ProxyCfg
    screenshots: ShotsCfg

class ConfigStore:
    _cfg: RootCfg = None
    _yaml_text: str = ""

    @classmethod
    def init(cls):
        data_dir = os.environ.get("DATA_DIR", "/data")
        app_yaml = os.path.join(data_dir, "config", "app.yaml")
        with open(app_yaml, "r", encoding="utf-8") as f:
            text = f.read()
            cls._yaml_text = text
            data = yaml.safe_load(text)

        def gv(path, default=None):
            cur = data
            for k in path.split("."):
                cur = cur.get(k, {})
            return cur if cur != {} else default

        cls._cfg = RootCfg(
            app=AppCfg(**data["app"]),
            paths=PathsCfg(**data["paths"]),
            execution=ExecCfg(**data["execution"]),
            proxy=ProxyCfg(**data["proxy"]),
            screenshots=ShotsCfg(**data["screenshots"]),
        )

    @classmethod
    def get(cls) -> RootCfg:
        return cls._cfg

    @classmethod
    def raw_yaml(cls) -> str:
        return cls._yaml_text

    @classmethod
    def save_yaml(cls, text: str):
        data_dir = os.environ.get("DATA_DIR", "/data")
        app_yaml = os.path.join(data_dir, "config", "app.yaml")
        # простая валидация
        yaml.safe_load(text)
        with open(app_yaml, "w", encoding="utf-8") as f:
            f.write(text)
        cls._yaml_text = text
        cls.init()

