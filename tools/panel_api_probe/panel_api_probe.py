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
from typing import Any
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
    ctx: ProbeContext,
) -> str | None:
    p = path_tmpl
    if ":bucket" in p:
        p = p.replace(":bucket", bucket)
    if ":metric" in p:
        p = p.replace(":metric", metric)
    if ":tag" in p:
        p = p.replace(":tag", url_quote(tag, safe=""))
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
    return data


PANEL_ROUTES = [
    # Session / CSRF routes (typically absent in API-only mode)
    {"method": "POST", "path": "/login", "body": {}, "risk": "ui"},
    {"method": "POST", "path": "/logout", "body": {}, "risk": "ui"},
    {"method": "GET", "path": "/csrf-token", "risk": "ui"},
    {"method": "POST", "path": "/getTwoFactorEnable", "body": {}, "risk": "ui"},
]


def merge_panel_setting_xray_manifest() -> list[dict[str, Any]]:
    """Optional routes from frontend api-docs (/panel/setting*, /panel/xray*). Mostly POST."""
    return [
        {"method": "POST", "path": "/panel/setting/all", "body": {}, "risk": "panel"},
        {"method": "POST", "path": "/panel/setting/defaultSettings", "body": {}, "risk": "panel"},
        {"method": "GET", "path": "/panel/setting/getDefaultJsonConfig", "risk": "panel"},
        {"method": "GET", "path": "/panel/setting/apiTokens", "risk": "panel"},
        {"method": "GET", "path": "/panel/xray/", "risk": "panel"},
        {"method": "GET", "path": "/panel/xray/getDefaultJsonConfig", "risk": "panel"},
        {"method": "GET", "path": "/panel/xray/getOutboundsTraffic", "risk": "panel"},
        {"method": "GET", "path": "/panel/xray/getXrayResult", "risk": "panel"},
    ]



def looks_destructive(entry: dict[str, Any], path_resolved: str) -> bool:
    if entry.get("method", "").upper() != "POST":
        return False
    if entry.get("risk") == "read":
        return False
    if entry.get("safe_post"):
        return False
    return True


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
        help="Include undocumented POST mutate endpoints (CAUTION — can restart/stop/delete).",
    )
    ns = ap.parse_args()

    base = normalize_base(ns.base_url)
    sess = requests.Session()
    sess.headers.update(bearer_headers(ns.secret))

    wb = "/" + ns.web_base_path.strip("/") + "/" if ns.web_base_path.strip("/") else ""
    prefix = base + wb.rstrip("/") if wb else base

    ctx = fetch_context(sess, prefix)
    manifest = load_manifest()
    extras: list[dict[str, Any]] = []

    if ns.also_panel_routes:
        extras.extend(merge_panel_setting_xray_manifest())
    if ns.also_ui_login_routes:
        extras.extend(PANEL_ROUTES)

    all_entries = manifest + extras
    ok_count = skip_count = fail_count = 0

    print(f"# base={prefix!r}")
    print(f"# context inbound_id={ctx.inbound_id} client={ctx.client_email!r} node={ctx.node_id} geo={ctx.geo_id}")

    for entry in all_entries:
        method = entry["method"].upper()
        path_tmpl = entry["path"]

        resolved = resolve_path(
            path_tmpl,
            bucket=ns.bucket,
            metric=ns.metric,
            tag=entry.get("tag_placeholder") or ns.observatory_tag,
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
            print(f"SKIP {method} {path_tmpl}  ({skip_reason})")
            continue

        url_path = join_paths(ns.web_base_path, resolved)

        full_url = base + url_path

        if "/server/getDb" in resolved and not ns.include_get_db:
            skip_count += 1
            print(f"SKIP {method} {path_tmpl}  (pass --include-get-db to download DB)")
            continue

        risk = entry.get("risk")
        if risk == "ui" and not ns.also_ui_login_routes:
            skip_count += 1
            print(f"SKIP {method} {resolved} (UI route — pass --also-ui-login-routes)")
            continue
        if risk == "panel" and not ns.also_panel_routes:
            skip_count += 1
            print(f"SKIP {method} {resolved} (setting/xray routes — pass --also-panel-routes)")
            continue

        if not ns.include_post_destructive and method == "POST" and looks_destructive(entry, resolved):
            skip_count += 1
            print(f"SKIP POST {resolved} (destructive; use --include-post-destructive)")
            continue

        kwargs: dict[str, Any] = {"timeout": ns.timeout}
        if method == "POST":
            hdr = dict(sess.headers)
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
            print(f"{flag} {method} {full_url} -> HTTP {r.status_code}{body_hint}")
        except requests.RequestException as e:
            fail_count += 1
            print(f"FAIL {method} {full_url} :: {e!r}")

    print(f"# summary OK={ok_count} FAIL={fail_count} SKIP={skip_count}")
    return 1 if fail_count else 0


if __name__ == "__main__":
    sys.exit(run())
