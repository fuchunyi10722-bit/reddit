"""
Reddit Proxy Feasibility Probe.

Standalone tool. Not part of Phase 1 production code.
Configurable proxy (HTTP/HTTPS/SOCKS5/SOCKS4) + 7-endpoint probe + failure-layer classifier.

Usage:
  # No external proxy (baseline through direct / egress only)
  python3 reddit_proxy_probe.py

  # With external proxy
  python3 reddit_proxy_probe.py \\
      --protocol socks5 --host 1.2.3.4 --port 1080 --username u --password p

  # Or via env (matches SourceAdapter convention)
  REDDIT_PROXY_PROTOCOL=socks5 REDDIT_PROXY_HOST=1.2.3.4 REDDIT_PROXY_PORT=1080 \\
      python3 reddit_proxy_probe.py
"""

from __future__ import annotations

import argparse
import json
import socket
import ssl
import sys
import time
import traceback
import urllib.error
import urllib.request
from dataclasses import dataclass, asdict, field
from typing import Optional

# --- Proxy config -----------------------------------------------------------

@dataclass
class ProxyConfig:
    protocol: str = "none"          # none | http | https | socks5 | socks4
    host: str = ""
    port: int = 0
    username: str = ""
    password: str = ""

    def is_configured(self) -> bool:
        return self.protocol not in ("none", "", None) and bool(self.host) and bool(self.port)

    def describe(self) -> str:
        if not self.is_configured():
            return "no-external-proxy (direct + sandbox egress only)"
        auth = f"{self.username}:***@" if self.username else ""
        return f"{self.protocol}://{auth}{self.host}:{self.port}"


def build_urllib_opener(cfg: ProxyConfig):
    """Build a urllib opener honoring the proxy config.

    For HTTP/HTTPS proxy: use ProxyHandler.
    For SOCKS5/SOCKS4: monkeypatch socket (PySocks) — isolated to this process.
    Returns (opener, restore_fn).
    """
    restore_fn = None

    if not cfg.is_configured():
        return urllib.request.build_opener(), restore_fn

    if cfg.protocol in ("http", "https"):
        auth = ""
        if cfg.username:
            auth = f"{cfg.username}:{cfg.password}@"
        proxy_url = f"http://{auth}{cfg.host}:{cfg.port}"
        handler = urllib.request.ProxyHandler({"http": proxy_url, "https": proxy_url})
        opener = urllib.request.build_opener(handler)
        return opener, restore_fn

    if cfg.protocol in ("socks5", "socks4"):
        try:
            import socks  # PySocks
        except ImportError:
            raise RuntimeError("SOCKS proxy requires PySocks (pip install pysocks)")

        # Save originals so we can restore.
        orig_socket = socket.socket
        orig_create_connection = socket.create_connection

        socks_type = socks.SOCKS5 if cfg.protocol == "socks5" else socks.SOCKS4
        socks.set_default_proxy(
            socks_type,
            cfg.host,
            cfg.port,
            username=cfg.username or None,
            password=cfg.password or None,
        )
        socket.socket = socks.socksocket

        def _create_connection(address, timeout=socket._GLOBAL_DEFAULT_TIMEOUT, source_address=None):
            return socks.create_connection(address, timeout=timeout, source_address=source_address)
        socket.create_connection = _create_connection

        def restore():
            socket.socket = orig_socket
            socket.create_connection = orig_create_connection
            try:
                socks.set_default_proxy()  # reset to no proxy
            except Exception:
                pass
        restore_fn = restore

        opener = urllib.request.build_opener()  # no ProxyHandler — socket level handles it
        return opener, restore_fn

    raise ValueError(f"Unsupported proxy protocol: {cfg.protocol}")


# --- Failure layer classifier -----------------------------------------------

def classify_failure(exc: BaseException) -> str:
    """Map an exception to a failure-layer label.

    Layers: dns | tls | proxy_connect | proxy_auth | reddit_reject |
            ip_limited | http_status | api_permission | sandbox_net | unknown
    """
    msg = str(exc).lower()

    # DNS
    if isinstance(exc, socket.gaierror) or "gaierror" in msg or "name or service not known" in msg:
        return "dns"

    # TLS / SSL handshake
    if isinstance(exc, ssl.SSLError) or "ssl" in msg or "tls" in msg or "ssl_error" in msg:
        return "tls"
    if "certificate" in msg or "handshake" in msg:
        return "tls"

    # Proxy auth
    if "407" in msg or "proxy authentication" in msg or "proxy auth" in msg:
        return "proxy_auth"

    # Proxy connect (refused / can't reach proxy host:port)
    if isinstance(exc, ConnectionRefusedError) or "connection refused" in msg:
        return "proxy_connect"
    if "tunneling failed" in msg or "proxy" in msg and ("refused" in msg or "reset" in msg):
        return "proxy_connect"

    # Reddit HTTP-level rejections
    if isinstance(exc, urllib.error.HTTPError):
        code = exc.code
        if code == 401 or code == 403:
            return "api_permission" if code == 401 else "reddit_reject"
        if code == 429:
            return "ip_limited"
        return f"http_status_{code}"

    # Timeouts — if Reddit-specific but other hosts work, sandbox net policy
    if isinstance(exc, (socket.timeout, TimeoutError)) or "timed out" in msg:
        return "sandbox_net_or_ip_block"

    # Connection reset / SYSCALL often = TLS killed mid-handshake
    if "ssl_error_syscall" in msg or "connection reset" in msg:
        return "tls"

    return "unknown"


# --- Probe ------------------------------------------------------------------

@dataclass
class ProbeResult:
    endpoint: str
    url: str
    http_status: Optional[int] = None
    size_bytes: int = 0
    elapsed_ms: int = 0
    failure_layer: Optional[str] = None
    error_detail: str = ""
    parsed: dict = field(default_factory=dict)  # extracted facts if JSON parsed

    def ok(self) -> bool:
        return self.failure_layer is None and 200 <= (self.http_status or 0) < 300


def _request(opener, url, timeout=25) -> ProbeResult:
    r = ProbeResult(endpoint="", url=url)
    t0 = time.time()
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "CommunityContentBot/0.1 (+feasibility-test)",
            "Accept": "application/json,text/html,*/*",
        },
    )
    try:
        with opener.open(req, timeout=timeout) as resp:
            body = resp.read()
        r.http_status = resp.status
        r.size_bytes = len(body)
        r.elapsed_ms = int((time.time() - t0) * 1000)
        r._body = body  # transient; not serialized
        return r
    except Exception as e:
        r.failure_layer = classify_failure(e)
        r.error_detail = f"{type(e).__name__}: {e}"[:300]
        r.elapsed_ms = int((time.time() - t0) * 1000)
        return r


def probe_all(cfg: ProxyConfig, sub="learnprogramming", post_id="qs8a6d") -> dict:
    opener, restore = build_urllib_opener(cfg)
    results = {}
    try:
        # 1. Reddit home
        r = _request(opener, "https://www.reddit.com/")
        r.endpoint = "1_reddit_home"
        results["1_reddit_home"] = r

        # 2. Post HTML
        r = _request(opener, f"https://www.reddit.com/r/{sub}/comments/{post_id}/")
        r.endpoint = "2_post_html"
        results["2_post_html"] = r

        # 3. Post JSON (post body + comments in one array)
        r = _request(opener, f"https://www.reddit.com/r/{sub}/comments/{post_id}.json")
        r.endpoint = "3_post_json"
        if r.ok() and r.size_bytes > 0:
            try:
                d = json.loads(r._body)
                if isinstance(d, list) and len(d) >= 1:
                    p = d[0]["data"]["children"][0]["data"]
                    r.parsed = {
                        "title": p.get("title"),
                        "subreddit": p.get("subreddit"),
                        "ups": p.get("ups"),
                        "score": p.get("score"),
                        "num_comments": p.get("num_comments"),
                        "created_utc": p.get("created_utc"),
                        "author": p.get("author"),
                        "selftext_len": len(p.get("selftext") or ""),
                    }
                    # comments present?
                    if len(d) >= 2 and d[1].get("data", {}).get("children"):
                        r.parsed["comment_forest_count"] = len(d[1]["data"]["children"])
            except Exception as pe:
                r.parsed = {"parse_error": str(pe)[:200]}
        results["3_post_json"] = r

        # 4. Subreddit page
        r = _request(opener, f"https://www.reddit.com/r/{sub}/")
        r.endpoint = "4_subreddit_page"
        results["4_subreddit_page"] = r

        # 5. Subreddit rules JSON
        r = _request(opener, f"https://www.reddit.com/r/{sub}/about/rules.json")
        r.endpoint = "5_subreddit_rules"
        if r.ok() and r.size_bytes > 0:
            try:
                d = json.loads(r._body)
                rules = d.get("rules") or d.get("data", {}).get("rules") or []
                r.parsed = {"rules_count": len(rules) if isinstance(rules, list) else 0}
            except Exception as pe:
                r.parsed = {"parse_error": str(pe)[:200]}
        results["5_subreddit_rules"] = r

        # 6 & 7: post comments + engagement metrics come from endpoint #3
        # — recorded under the post_json result above.
    finally:
        if restore:
            restore()
    return results


# --- Verdict ----------------------------------------------------------------

def verdict(results: dict) -> tuple[str, str]:
    """Return (letter, rationale). A/B/C/D per user spec."""
    ok_count = sum(1 for r in results.values() if r.ok())
    layers = {r.failure_layer for r in results.values() if r.failure_layer}

    # All 5 endpoints reachable + post JSON parsed with body+comments+metrics
    post_json = results.get("3_post_json")
    parsed_ok = bool(post_json and post_json.ok() and post_json.parsed
                      and post_json.parsed.get("title")
                      and post_json.parsed.get("num_comments") is not None
                      and post_json.parsed.get("created_utc"))

    if ok_count == 5 and parsed_ok:
        return "A", "All endpoints 200; post body + comments + engagement metrics + community rules all retrievable."
    if ok_count >= 2 and (post_json and post_json.ok() and post_json.parsed.get("title")):
        return "B", "Connection works and post body/comments retrievable; some endpoints missing or rules incomplete."
    if ok_count >= 1 and not (post_json and post_json.ok()):
        return "C", "Connection to Reddit HTML works but JSON/data endpoints unavailable."
    if layers.issubset({"tls", "sandbox_net_or_ip_block", "unknown"}):
        return "D", "Reddit unreachable at TLS/network layer even via proxy; appears sandbox/IP block, not Reddit-side API limit."
    return "D", f"Failed across endpoints; layers={sorted(layers)}"


# --- Report -----------------------------------------------------------------

def serialize(results: dict, cfg: ProxyConfig) -> dict:
    out = {
        "proxy_config": {
            "protocol": cfg.protocol,
            "host": cfg.host,
            "port": cfg.port,
            "username": cfg.username or "",
            "password_present": bool(cfg.password),
        },
        "proxy_describe": cfg.describe(),
        "endpoints": {k: asdict(v) for k, v in results.items()},
    }
    letter, rationale = verdict(results)
    out["verdict"] = {"letter": letter, "rationale": rationale}
    return out


def print_human_report(results: dict, cfg: ProxyConfig):
    print("=" * 78)
    print(f"PROXY: {cfg.describe()}")
    print("=" * 78)
    for key, r in results.items():
        status = f"HTTP {r.http_status}" if r.http_status else "—"
        size = f"{r.size_bytes}B" if r.size_bytes else "0B"
        layer = r.failure_layer or "OK"
        print(f"[{r.endpoint}] {status} | {size} | {r.elapsed_ms}ms | layer={layer}")
        if r.error_detail:
            print(f"    ↳ {r.error_detail}")
        if r.parsed:
            for pk, pv in r.parsed.items():
                val = (str(pv)[:80] + "…") if isinstance(pv, str) and len(str(pv)) > 80 else pv
                print(f"    ✓ {pk}: {val}")
    letter, rationale = verdict(results)
    print("=" * 78)
    print(f"VERDICT: {letter} — {rationale}")
    print("=" * 78)


# --- CLI --------------------------------------------------------------------

def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--protocol", default=None,
                   help="none | http | https | socks5 | socks4")
    p.add_argument("--host", default=None)
    p.add_argument("--port", type=int, default=None)
    p.add_argument("--username", default=None)
    p.add_argument("--password", default=None)
    p.add_argument("--sub", default="learnprogramming")
    p.add_argument("--post-id", default="qs8a6d")
    p.add_argument("--json-out", default=None, help="write structured JSON to path")
    return p.parse_args()


def cfg_from_args_and_env(args) -> ProxyConfig:
    protocol = args.protocol or os_env("REDDIT_PROXY_PROTOCOL", "none")
    host = args.host or os_env("REDDIT_PROXY_HOST", "")
    port = args.port or int(os_env("REDDIT_PROXY_PORT", "0") or "0")
    username = args.username or os_env("REDDIT_PROXY_USERNAME", "")
    password = args.password or os_env("REDDIT_PROXY_PASSWORD", "")
    return ProxyConfig(protocol=protocol, host=host, port=port, username=username, password=password)


def os_env(key, default=""):
    import os
    return os.environ.get(key, default)


def main():
    args = parse_args()
    cfg = cfg_from_args_and_env(args)
    print(f"# Probe target subreddit=r/{args.sub} post_id={args.post_id}")
    results = probe_all(cfg, sub=args.sub, post_id=args.post_id)
    print_human_report(results, cfg)
    if args.json_out:
        with open(args.json_out, "w") as f:
            json.dump(serialize(results, cfg), f, indent=2, default=str)
        print(f"# JSON report → {args.json_out}")
    letter, _ = verdict(results)
    sys.exit(0 if letter in ("A", "B") else 1)


if __name__ == "__main__":
    main()
