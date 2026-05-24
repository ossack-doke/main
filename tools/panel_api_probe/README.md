# Panel `/panel/api` probe (Bearer secret)

Smoke-tests JSON APIs behind `Authorization: Bearer <XUI_API_SECRET>`.

## Install (Python)

```bash
cd tools/panel_api_probe
pip install -r requirements.txt
python panel_api_probe.py --base-url http://YOUR_IP:2053 --secret YOUR_SECRET \
  --web-base-path /
```

Use your real **`webBasePath`** (often random, for example `/DJEi.../`).

## Behaviour

- **Default**: probes **safe GET** routes under `/panel/api` plus harmless POST **`/clients/onlines`** and **`/clients/lastOnline`** (`"risk":"read"` in manifest).
- **`--include-get-db`**: adds **GET `/panel/api/server/getDb`** (downloads the SQLite file).
- **`--also-panel-routes`**: tries **`/panel/setting/*`** / **`/panel/xray/*`**. Those usually **require a browser session**, not Bearer alone unless you patched the fork — expect failures in **`XUI_API_ONLY`** mode.
- **`--also-ui-login-routes`**: root **`/login`**, **`/logout`**, etc. — usually missing in API-only installs.
- **`--include-post-destructive`**: allows **unsafe POST** (mutations); use only on throwaway VMs.

Endpoints are listed in **`endpoints_manifest.json`** (extend freely).

## Build a Windows `.exe` (PyInstaller)

From this directory on Windows (same Python env with `requests` installed):

```bat
pip install pyinstaller requests
pyinstaller --onefile --console --name PanelApiProbe ^
  --add-data "endpoints_manifest.json;." panel_api_probe.py
```

生成的 **`dist\PanelApiProbe.exe`** 与同目录解压包中的 **`endpoints_manifest.json`** 已通过 `--add-data` 打进程序，**无需再手动拷贝 manifest**。

Linux/macOS PyInstaller：`--add-data` 改用冒号：`--add-data "endpoints_manifest.json:."`。
