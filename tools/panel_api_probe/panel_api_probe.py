#!/usr/bin/env python3
"""HTTP smoke tests for 3x-ui /panel/api/* (Bearer XUI_API_SECRET).

Examples:
  python panel_api_probe.py --base-url http://127.0.0.1:2053 --secret YOUR_HEX \\
      --web-base-path /Dj.../

  python panel_api_probe.py --base-url http://127.0.0.1:2053 --secret YOUR_HEX \\
      --also-panel-routes --include-post-destructive
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable
from urllib.parse import quote as url_quote

try:
    import requests
except ImportError:
    print("Install dependencies: pip install -r requirements.txt", file=sys.stderr)
    sys.exit(1)


@dataclass
class ProbeContext:
    inbound_id: int | None = None
    client_email: str | None = None
    sub_id: str | None = None
    node_id: int | None = None
    geo_id: int | None = None


def normalize_base(base: str) -> str:
    return base.rstrip("/")


def join_paths(web_base_path: str, api_path: str) -> str:
    """web_base_path starts with '/', api_path starts with '/' -> full URI path."""
    w = "/" + web_base_path.strip("/")
    if w == "/":
        return api_path
    return f"{w.rstrip('/')}{api_path}"


def bearer_headers(secret: str) -> dict[str, str]:
    token = secret.strip()
    auth = token if token.lower().startswith("bearer ") else f"Bearer {token}"
    return {"Authorization": auth, "Accept": "application/json"}


def probe_root() -> Path:
    """Directory containing bundled manifest — supports PyInstaller onefile."""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(getattr(sys, "_MEIPASS"))
    return Path(__file__).resolve().parent


def resolve_path(
    path_tmpl: str,
    *,
    bucket: str,
    metric: str,
    tag: str,
    log_count: str,
    ctx: ProbeContext,
) -> str | None:
    p = path_tmpl
    if ":bucket" in p:
        p = p.replace(":bucket", bucket)
    if ":metric" in p:
        p = p.replace(":metric", metric)
    if ":tag" in p:
        p = p.replace(":tag", url_quote(tag, safe=""))
    if ":log_count" in p:
        p = p.replace(":log_count", log_count)
    if ":fileName" in p:
        p = p.replace(":fileName", "geoip.dat")
    if ":id" in p:
        pid = None
        tmpl = path_tmpl
        if "/inbounds/" in tmpl:
            pid = ctx.inbound_id
        elif "/nodes/" in tmpl:
            pid = ctx.node_id
        elif "/custom-geo/" in tmpl:
            pid = ctx.geo_id
        if pid is None:
            return None
        p = p.replace(":id", str(pid))
    if ":email" in p:
        if not ctx.client_email:
            return None
        p = p.replace(":email", url_quote(ctx.client_email, safe=""))
    if ":subId" in p:
        if not ctx.sub_id:
            return None
        p = p.replace(":subId", url_quote(ctx.sub_id, safe=""))
    return p


def entry_category(entry: dict[str, Any], path_tmpl: str) -> str:
    c = entry.get("category")
    if isinstance(c, str) and c.strip():
        return c.strip()
    if "/panel/api/inbounds/" in path_tmpl:
        return "inbounds"
    if "/panel/api/clients/" in path_tmpl:
        return "clients"
    if "/panel/api/server/" in path_tmpl:
        return "server"
    if "/panel/api/nodes/" in path_tmpl:
        return "nodes"
    if "/panel/api/custom-geo/" in path_tmpl:
        return "geo"
    return "other"


def fetch_context(sess: requests.Session, full_prefix: str) -> ProbeContext:
    ctx = ProbeContext()
    try:
        r = sess.get(f"{full_prefix}/panel/api/inbounds/list", timeout=30)
        if r.ok:
            js = r.json()
            arr = js.get("obj") or []
            if arr and isinstance(arr[0].get("id"), int):
                ctx.inbound_id = arr[0]["id"]
    except (requests.RequestException, ValueError, TypeError, KeyError):
        pass
    try:
        r = sess.get(f"{full_prefix}/panel/api/clients/list", timeout=30)
        if r.ok:
            js = r.json()
            arr = js.get("obj") or []
            if arr:
                ctx.client_email = arr[0].get("email")
                ctx.sub_id = arr[0].get("subId") or None
    except (requests.RequestException, ValueError, TypeError, KeyError):
        pass
    try:
        r = sess.get(f"{full_prefix}/panel/api/nodes/list", timeout=30)
        if r.ok:
            js = r.json()
            arr = js.get("obj") or []
            if arr and isinstance(arr[0].get("id"), int):
                ctx.node_id = arr[0]["id"]
    except (requests.RequestException, ValueError, TypeError, KeyError):
        pass
    try:
        r = sess.get(f"{full_prefix}/panel/api/custom-geo/list", timeout=30)
        if r.ok:
            js = r.json()
            arr = js.get("obj") or []
            if arr and isinstance(arr[0].get("id"), int):
                ctx.geo_id = arr[0]["id"]
    except (requests.RequestException, ValueError, TypeError, KeyError):
        pass
    return ctx


def load_manifest() -> list[dict[str, Any]]:
    here = probe_root()
    data = json.loads((here / "endpoints_manifest.json").read_text(encoding="utf-8"))
    return [e for e in data if not e.get("omit_from_probe")]


PANEL_ROUTES = [
    # Session / CSRF routes (typically absent in API-only mode)
    {"method": "POST", "path": "/login", "body": {}, "risk": "ui", "category": "ui"},
    {"method": "POST", "path": "/logout", "body": {}, "risk": "ui", "category": "ui"},
    {"method": "GET", "path": "/csrf-token", "risk": "ui", "category": "ui"},
    {"method": "POST", "path": "/getTwoFactorEnable", "body": {}, "risk": "ui", "category": "ui"},
]


def merge_panel_setting_xray_manifest() -> list[dict[str, Any]]:
    """Optional routes from frontend api-docs (/panel/setting*, /panel/xray*). Mostly POST."""
    rows: list[dict[str, Any]] = [
        {"method": "POST", "path": "/panel/setting/all", "body": {}, "risk": "panel"},
        {"method": "POST", "path": "/panel/setting/defaultSettings", "body": {}, "risk": "panel"},
        {"method": "GET", "path": "/panel/setting/getDefaultJsonConfig", "risk": "panel"},
        {"method": "GET", "path": "/panel/setting/apiTokens", "risk": "panel"},
        {"method": "GET", "path": "/panel/xray/", "risk": "panel"},
        {"method": "GET", "path": "/panel/xray/getDefaultJsonConfig", "risk": "panel"},
        {"method": "GET", "path": "/panel/xray/getOutboundsTraffic", "risk": "panel"},
        {"method": "GET", "path": "/panel/xray/getXrayResult", "risk": "panel"},
    ]
    for r in rows:
        r.setdefault("category", "panel")
    return rows



def looks_destructive(entry: dict[str, Any], path_resolved: str) -> bool:
    del path_resolved
    if entry.get("method", "").upper() != "POST":
        return False
    if entry.get("risk") == "read":
        return False
    if entry.get("safe_post"):
        return False
    return True


def _say(emit: Callable[[str], None] | None, line: str) -> None:
    if emit:
        emit(line)
    else:
        print(line)


@dataclass
class ProbeConfig:
    base_url: str
    secret: str
    web_base_path: str = "/"
    bucket: str = "60"
    metric: str = "cpu"
    observatory_tag: str = "direct"
    log_line_count: str = "50"
    timeout: float = 60.0
    include_get_db: bool = False
    also_panel_routes: bool = False
    also_ui_login_routes: bool = False
    include_post_destructive: bool = False
    include_backup_tgbot: bool = False


def run_probe_lines(
    cfg: ProbeConfig,
    *,
    emit: Callable[[str], None] | None = None,
    categories: frozenset[str] | None = None,
) -> tuple[int, list[str]]:
    lines: list[str] = []

    def out(s: str) -> None:
        lines.append(s)
        _say(emit, s)

    base = normalize_base(cfg.base_url)
    sess = requests.Session()
    sess.headers.update(bearer_headers(cfg.secret))

    wb = "/" + cfg.web_base_path.strip("/") + "/" if cfg.web_base_path.strip("/") else ""
    prefix = base + wb.rstrip("/") if wb else base

    ctx = fetch_context(sess, prefix)
    manifest = load_manifest()
    extras: list[dict[str, Any]] = []

    want_panel = cfg.also_panel_routes or (categories is not None and "panel" in categories)
    want_ui = cfg.also_ui_login_routes or (categories is not None and "ui" in categories)

    if want_panel:
        extras.extend(merge_panel_setting_xray_manifest())
    if want_ui:
        extras.extend(PANEL_ROUTES)

    all_entries = manifest + extras
    ok_count = skip_count = fail_count = 0

    out(f"# base={prefix!r}")
    out(f"# context inbound_id={ctx.inbound_id} client={ctx.client_email!r} node={ctx.node_id} geo={ctx.geo_id}")

    for entry in all_entries:
        method = entry["method"].upper()
        path_tmpl = entry["path"]
        cat = entry_category(entry, path_tmpl)
        if categories is not None and cat not in categories:
            continue

        resolved = resolve_path(
            path_tmpl,
            bucket=cfg.bucket,
            metric=cfg.metric,
            tag=entry.get("tag_placeholder") or cfg.observatory_tag,
            log_count=cfg.log_line_count.strip() or "50",
            ctx=ctx,
        )

        skip_reason = None
        if resolved is None:
            if entry.get("need_inbound_id") and ctx.inbound_id is None:
                skip_reason = "no inbound id"
            elif entry.get("need_client_email") and not ctx.client_email:
                skip_reason = "no client email"
            elif entry.get("need_sub_id") and not ctx.sub_id:
                skip_reason = "no subId"
            elif entry.get("need_node_id") and ctx.node_id is None:
                skip_reason = "no node id"
            elif entry.get("need_geo_id") and ctx.geo_id is None:
                skip_reason = "no custom-geo id"
            else:
                skip_reason = "unresolved placeholders"

        if skip_reason:
            skip_count += 1
            out(f"SKIP {method} {path_tmpl}  ({skip_reason})")
            continue

        url_path = join_paths(cfg.web_base_path, resolved)

        full_url = base + url_path

        if "/server/getDb" in resolved and not cfg.include_get_db:
            skip_count += 1
            out(f"SKIP {method} {path_tmpl}  (pass --include-get-db to download DB)")
            continue

        risk = entry.get("risk")
        if risk == "ui" and not want_ui:
            skip_count += 1
            out(f"SKIP {method} {resolved} (UI route — pass --also-ui-login-routes or probe category ui)")
            continue
        if risk == "panel" and not want_panel:
            skip_count += 1
            out(f"SKIP {method} {resolved} (setting/xray routes — pass --also-panel-routes or probe category panel)")
            continue
        if risk == "tg_backup" and not cfg.include_backup_tgbot:
            skip_count += 1
            out(f"SKIP {method} {path_tmpl} (Telegram backup — --include-backup-tgbot)")
            continue

        if not cfg.include_post_destructive and method == "POST" and looks_destructive(entry, resolved):
            skip_count += 1
            out(f"SKIP POST {resolved} (destructive; use --include-post-destructive)")
            continue

        kwargs: dict[str, Any] = {"timeout": cfg.timeout}
        if method == "POST":
            hdr = dict(sess.headers)
            if entry.get("body_kind") == "form":
                hdr.pop("Content-Type", None)
                kwargs["headers"] = hdr
                kwargs["data"] = dict(entry.get("form") or {})
            else:
                hdr.setdefault("Content-Type", "application/json")
                kwargs["headers"] = hdr
                kwargs["json"] = entry.get("body") if isinstance(entry.get("body"), dict) else {}

        try:
            r = sess.request(method, full_url, **kwargs)
            ok = r.status_code == 200
            body_hint = ""
            if resolved.rstrip("/").endswith("/server/getDb") and method == "GET":
                ok = ok and len(r.content) > 48
                if not ok:
                    body_hint = f" (SQLite/file size; {len(r.content)} bytes)"
                flag = "OK " if ok else "FAIL"
            elif entry.get("non_json_success"):
                body_hint = f" ({len(r.content)} bytes body)" if r.content else " (empty body)"
                flag = "OK " if ok else "FAIL"
            else:
                try:
                    j = r.json()
                    ok = ok and isinstance(j.get("success"), bool) and j["success"]
                except ValueError:
                    body_hint = f" ({len(r.content)} bytes non-JSON)"
                flag = "OK " if ok else "FAIL"

            if ok:
                ok_count += 1
            else:
                fail_count += 1
            out(f"{flag} {method} [{cat}] {full_url} -> HTTP {r.status_code}{body_hint}")
        except requests.RequestException as e:
            fail_count += 1
            out(f"FAIL {method} [{cat}] {full_url} :: {e!r}")

    out(f"# summary OK={ok_count} FAIL={fail_count} SKIP={skip_count}")
    return (1 if fail_count else 0), lines


def run() -> int:
    ap = argparse.ArgumentParser(description="3x-ui /panel/api Bearer smoke tester")
    ap.add_argument("--base-url", required=True, help="http://host:port (no trailing path)")
    ap.add_argument("--secret", required=True, help="XUI_API_SECRET (Bearer prefix optional)")
    ap.add_argument(
        "--web-base-path",
        default="/",
        help="Panel webBasePath, e.g. /abcXYZ/ — default /",
    )
    ap.add_argument("--bucket", default="60")
    ap.add_argument("--metric", default="cpu")
    ap.add_argument("--observatory-tag", default="direct")
    ap.add_argument("--timeout", type=float, default=60.0)
    ap.add_argument(
        "--include-get-db",
        action="store_true",
        help="Also GET /panel/api/server/getDb (downloads database binary).",
    )
    ap.add_argument(
        "--also-panel-routes",
        action="store_true",
        help="Probe /panel/setting/* and /panel/xray/* (need full UI + cookie in practice).",
    )
    ap.add_argument(
        "--also-ui-login-routes",
        action="store_true",
        help="Probe /login /logout root paths (almost always useless with API-only mode).",
    )
    ap.add_argument(
        "--include-post-destructive",
        action="store_true",
        help="Include destructive POST probes (restart/stop/delete/import/etc.) — use only on test panels.",
    )
    ap.add_argument(
        "--only-categories",
        default="",
        help="Comma list: inbounds,clients,server,nodes,geo,extra,panel,ui (default: all from manifest extras).",
    )
    ap.add_argument(
        "--log-count",
        default="50",
        help="Substitute for paths like POST /panel/api/server/logs/:log_count.",
    )
    ap.add_argument(
        "--include-backup-tgbot",
        action="store_true",
        help="Actually call POST /panel/api/backuptotgbot (sends Telegram backup when bot is configured).",
    )
    ns = ap.parse_args()

    cats: frozenset[str] | None = None
    if ns.only_categories.strip():
        cats = frozenset(p.strip() for p in ns.only_categories.split(",") if p.strip())

    cfg = ProbeConfig(
        base_url=ns.base_url,
        secret=ns.secret,
        web_base_path=ns.web_base_path,
        bucket=ns.bucket or "60",
        metric=ns.metric or "cpu",
        observatory_tag=ns.observatory_tag or "direct",
        log_line_count=ns.log_count or "50",
        timeout=ns.timeout,
        include_get_db=ns.include_get_db,
        also_panel_routes=ns.also_panel_routes,
        also_ui_login_routes=ns.also_ui_login_routes,
        include_post_destructive=ns.include_post_destructive,
        include_backup_tgbot=ns.include_backup_tgbot,
    )
    code, _lines = run_probe_lines(cfg, emit=None, categories=cats)
    return code


if __name__ == "__main__":
    sys.exit(run())
