from datetime import datetime
from typing import Literal


class Timings:
    dns_ms: int | None
    tcp_ms: int | None
    tls_ms: int | None
    ttfb_ms: int | None
    total_ms: int | None

class ProxySession:
    type: Literal["http","socks5"]
    host: str
    port: int
    username: str
    password: str
    session_id: str | None
    ext_ip: str | None

class CheckInput:
    url: str                # как введено юзером (может быть без schema)
    country: str            # ISO2
    region_code: str | None
    isp: str | None
    proxy_type: Literal["http","socks5"]
    dns_mode: Literal["local","proxy"]
    sticky: bool
    sticky_ttl_sec: int
    timeout_sec: int
    make_screenshot: bool

class CheckResult:
    classification: Literal[
        "success","http_error",
        "dns_error","connect_error",
        "tls_error","timeout"
    ]
    http_code: int | None
    bytes_count: int | None
    timings: Timings
    redirects: list[tuple[int,str,str]]  # [(code, from, to)]
    proxy_ext_ip: str | None
    md_path: str
    png_path: str | None

class RunConfig:
    run_id: str
    started_at: datetime
    sticky_policy: Literal["auto","on","off"]
    sticky_ttl_sec: int
    proxy_type: Literal["http","socks5"]
    dns_mode: Literal["local","proxy"]
    timeout_sec: int
    make_screenshot: bool

class RunState:
    run_id: str
    checks_total: int
    checks_done: int

