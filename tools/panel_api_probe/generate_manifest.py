#!/usr/bin/env python3
"""Vendor-local: emit endpoints_manifest.json from web/controller snapshots + wiki-aligned notes."""

from __future__ import annotations

import json
from pathlib import Path

# Mirrors web/controller routers (fork). Wiki groups some under /inbounds — here they live under /clients.
ENTRIES: list[dict] = []

def add(**kw: object) -> None:
    ENTRIES.append(kw)


# --- Inbounds (see web/controller/inbound.go) ---
add(method="GET", path="/panel/api/inbounds/list", category="inbounds")
add(method="GET", path="/panel/api/inbounds/options", category="inbounds")
add(method="GET", path="/panel/api/inbounds/get/:id", category="inbounds", need_inbound_id=True)
add(method="GET", path="/panel/api/inbounds/:id/fallbacks", category="inbounds", need_inbound_id=True)
add(method="POST", path="/panel/api/inbounds/add", category="inbounds")
add(method="POST", path="/panel/api/inbounds/del/:id", category="inbounds", need_inbound_id=True)
add(method="POST", path="/panel/api/inbounds/update/:id", category="inbounds", need_inbound_id=True)
add(method="POST", path="/panel/api/inbounds/setEnable/:id", category="inbounds", need_inbound_id=True)
add(method="POST", path="/panel/api/inbounds/:id/resetTraffic", category="inbounds", need_inbound_id=True)
add(method="POST", path="/panel/api/inbounds/resetAllTraffics", category="inbounds")
add(method="POST", path="/panel/api/inbounds/import", category="inbounds")  # form data key "data"; empty JSON probes fail safely
add(method="POST", path="/panel/api/inbounds/:id/fallbacks", category="inbounds", need_inbound_id=True)

# --- Clients (Wiki "Inbounds API" overlaps; see web/controller/client.go) ---
add(method="GET", path="/panel/api/clients/list", category="clients")
add(method="GET", path="/panel/api/clients/get/:email", category="clients", need_client_email=True)
add(method="GET", path="/panel/api/clients/traffic/:email", category="clients", need_client_email=True)
add(method="GET", path="/panel/api/clients/subLinks/:subId", category="clients", need_sub_id=True)
add(method="GET", path="/panel/api/clients/links/:email", category="clients", need_client_email=True)
add(method="POST", path="/panel/api/clients/onlines", category="clients", risk="read", body={})
add(method="POST", path="/panel/api/clients/lastOnline", category="clients", risk="read", body={})
add(method="POST", path="/panel/api/clients/ips/:email", category="clients", risk="read", need_client_email=True, body={})
add(method="POST", path="/panel/api/clients/add", category="clients")
add(method="POST", path="/panel/api/clients/update/:email", category="clients", need_client_email=True)
add(method="POST", path="/panel/api/clients/del/:email", category="clients", need_client_email=True)
add(method="POST", path="/panel/api/clients/:email/attach", category="clients", need_client_email=True)
add(method="POST", path="/panel/api/clients/:email/detach", category="clients", need_client_email=True)
add(method="POST", path="/panel/api/clients/resetAllTraffics", category="clients")
add(method="POST", path="/panel/api/clients/delDepleted", category="clients")
add(method="POST", path="/panel/api/clients/resetTraffic/:email", category="clients", need_client_email=True)
add(method="POST", path="/panel/api/clients/updateTraffic/:email", category="clients", need_client_email=True, body={"upload": 0, "download": 0})
add(method="POST", path="/panel/api/clients/clearIps/:email", category="clients", need_client_email=True)

# --- Server ---
add(method="GET", path="/panel/api/server/status", category="server")
add(method="GET", path="/panel/api/server/cpuHistory/:bucket", category="server", bucket=True)
add(method="GET", path="/panel/api/server/history/:metric/:bucket", category="server", metric=True, bucket=True)
add(method="GET", path="/panel/api/server/xrayMetricsState", category="server")
add(method="GET", path="/panel/api/server/xrayMetricsHistory/:metric/:bucket", category="server", metric=True, bucket=True)
add(method="GET", path="/panel/api/server/xrayObservatory", category="server")
add(method="GET", path="/panel/api/server/xrayObservatoryHistory/:tag/:bucket", category="server", tag_placeholder="__direct__", bucket=True)
add(method="GET", path="/panel/api/server/getXrayVersion", category="server")
add(method="GET", path="/panel/api/server/getPanelUpdateInfo", category="server")
add(method="GET", path="/panel/api/server/getConfigJson", category="server")
add(method="GET", path="/panel/api/server/getDb", category="server", notes="downloads sqlite"),  # guarded by CLI flag
add(method="GET", path="/panel/api/server/getNewUUID", category="server", risk="read")
add(method="GET", path="/panel/api/server/getNewX25519Cert", category="server", risk="read")
add(method="GET", path="/panel/api/server/getNewmldsa65", category="server", risk="read")
add(method="GET", path="/panel/api/server/getNewmlkem768", category="server", risk="read")
add(method="GET", path="/panel/api/server/getNewVlessEnc", category="server", risk="read")
add(method="POST", path="/panel/api/server/logs/:log_count", category="server", risk="read", body_kind="form", form={"level": "", "syslog": ""})
add(method="POST", path="/panel/api/server/xraylogs/:log_count", category="server", risk="read", body_kind="form", form={
    "filter": "", "showDirect": "true", "showBlocked": "", "showProxy": "true"})
add(method="POST", path="/panel/api/server/getNewEchCert", category="server", risk="read", body_kind="form", form={"sni": "probe.invalid"})
add(method="POST", path="/panel/api/server/stopXrayService", category="server")
add(method="POST", path="/panel/api/server/restartXrayService", category="server")
add(method="POST", path="/panel/api/server/updateGeofile", category="server")  # may download all geofiles
add(method="POST", path="/panel/api/server/updateGeofile/:fileName", category="server")  # resolved to geoip.dat
add(method="POST", path="/panel/api/server/updatePanel", category="server")
add(method="POST", path="/panel/api/server/importDB", category="server", omit_from_probe=True)
add(method="POST", path="/panel/api/server/installXray/:version", category="server", omit_from_probe=True)


# --- Nodes ---
add(method="GET", path="/panel/api/nodes/list", category="nodes")
add(method="GET", path="/panel/api/nodes/get/:id", category="nodes", need_node_id=True)
add(method="GET", path="/panel/api/nodes/history/:id/:metric/:bucket", category="nodes", need_node_id=True, metric=True, bucket=True)
add(method="POST", path="/panel/api/nodes/add", category="nodes", omit_from_probe=True)  # needs full JSON
add(method="POST", path="/panel/api/nodes/update/:id", category="nodes", need_node_id=True, omit_from_probe=True)
add(method="POST", path="/panel/api/nodes/del/:id", category="nodes", need_node_id=True)
add(method="POST", path="/panel/api/nodes/setEnable/:id", category="nodes", need_node_id=True)
add(method="POST", path="/panel/api/nodes/test", category="nodes", omit_from_probe=True)
add(method="POST", path="/panel/api/nodes/probe/:id", category="nodes", risk="read", need_node_id=True, body={})


# --- Custom geo ---
add(method="GET", path="/panel/api/custom-geo/list", category="geo")
add(method="GET", path="/panel/api/custom-geo/aliases", category="geo")
add(method="POST", path="/panel/api/custom-geo/add", category="geo", omit_from_probe=True)
add(method="POST", path="/panel/api/custom-geo/update/:id", category="geo", need_geo_id=True, omit_from_probe=True)
add(method="POST", path="/panel/api/custom-geo/delete/:id", category="geo", need_geo_id=True)
add(method="POST", path="/panel/api/custom-geo/download/:id", category="geo", need_geo_id=True)
add(method="POST", path="/panel/api/custom-geo/update-all", category="geo")


# Wiki shows GET but web/controller/api.go wires POST — match the codebase.
add(method="POST", path="/panel/api/backuptotgbot", category="extra", risk="tg_backup", body={}, non_json_success=True)


def main() -> None:
    out = Path(__file__).resolve().parent / "endpoints_manifest.json"
    merged = sorted(ENTRIES, key=lambda e: (e["category"], e["method"], e["path"]))
    merged = [e for e in merged]
    out.write_text(json.dumps(merged, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    ok_ct = sum(1 for e in merged if not e.get("omit_from_probe"))
    print(f"Wrote {out} ({len(merged)} entries, {ok_ct} actively probed)")


if __name__ == "__main__":
    main()
