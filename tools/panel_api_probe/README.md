# 3x-ui Panel API 自检（CLI + GUI）

清单 **`endpoints_manifest.json`** 由 **`generate_manifest.py`** 生成，对齐本仓库 **`web/controller/*`**（`api.go`、`inbound.go`、`client.go`、`server.go`、`node.go`、`custom_geo.go`）。

[官方 Wiki · API Documentation](https://github.com/MHSanaei/3x-ui/wiki/Configuration#api-documentation) 中部分「入站」相关路由在本 fork **已合并到 **`/panel/api/clients`**；请以当前仓库源码为准。**另有少数 Wiki 条目（例如旧版 **`/panel/api/inbounds/getClientTraffics/:email`**）若未在源码中注册，本工具不会探测。

**`/panel/api/backuptotgbot`**：Wiki 写的是 **GET**，本仓库 **`api.go`** 注册为 **`POST`**；工具已与源码一致。**默认不会在 GUI/CLI 中调用**，以免误触发 Telegram 备份。

## GUI（Tk）

```text
cd tools/panel_api_probe
pip install -r requirements.txt
python panel_probe_gui.py
```

填写 **服务器 / 端口**，可选 **HTTPS**、**webBasePath**、**密钥**，按需勾选「破坏性 POST」「下载 DB」「Telegram 备份」等，再点击 **「全部路由」**或各 **分组按钮**。

## CLI

```text
python panel_api_probe.py --base-url http://127.0.0.1:2053 --secret YOUR_SECRET ...
```

常用参数：

| 参数 | 说明 |
|------|------|
| `--only-categories` | 逗号分隔：`inbounds,clients,server,nodes,geo,extra,panel,ui` |
| `--log-count` | `POST …/logs/:log_count`、`xraylogs/:log_count` 中的行数占位 |
| `--include-backup-tgbot` | 允许 **`POST …/backuptotgbot`** |
| `--include-post-destructive` | 含可能影响业务的 POST（重置流量、停 Xray、`updateGeofile`、删节点等） |

维护清单：**`python generate_manifest.py`**

## 打成 Windows exe（单文件、无控制台）

双击 **`build_gui_exe.bat`**。生成：**`dist\PanelApiProbeGUI.exe`**。**`endpoints_manifest.json`** 必须与 exe 一并打包：`--add-data "endpoints_manifest.json;."`（Windows；Linux 改用 `:`）。

手动 PyInstaller：**`panel_probe_gui.py`** 入口，**`--windowed`**，并 **`--hidden-import panel_api_probe`**。
