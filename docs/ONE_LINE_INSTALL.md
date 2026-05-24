# 一条命令在线安装（自维护 fork）

本仓库在官方包（Xray、资源文件）基础上，从你的 **GitHub 分叉** **在服务器上 `go build`（CGO=1）** 编译主程序，因此 **SQLite 正常**，并写入 **`XUI_API_ONLY` / `XUI_API_SECRET`**（`/etc/default/x-ui`）。

## 你需要先做的事

1. 在 GitHub 上建好 **公开或私有分叉**（`git remote` 指到你的仓库）。
2. **把这里的改动完整 push 上去**，尤其包括：
   - `install-online.sh`
   - `web/dist/`（至少要有 `index.html` 占位，否则会 `go:embed` 失败）
   - `x-ui.rc`（Alpine/OpenRC 可配合 `x-ui.rc`；一键脚本还支持 **dnf/yum、apk**，仍是 **systemd** 启动）
3. 确认默认分支名（多为 **`main`**），与下方 `XUI_GIT_BRANCH` 一致。

## 一条命令（把 URL 换成你的仓库）

```bash
sudo -i

export XUI_GIT_REPO='https://github.com/你的用户名/你的仓库.git'
export XUI_GIT_BRANCH='main'

bash <(curl -fsSL https://raw.githubusercontent.com/你的用户名/你的仓库/main/install-online.sh)
```

若 GitHub RAW 与你的分支名不同，把 `main` 改成你的分支路径。

等价写法：

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/你的用户名/你的仓库/main/install-online.sh) \
  'https://github.com/你的用户名/你的仓库.git' main
```

## 与环境变量有关的选项

| 变量 | 含义 |
|------|------|
| `XUI_GIT_REPO` | 必选，fork 的 `https://github.com/...git` |
| `XUI_GIT_BRANCH` | 默认 `main` |
| `XUI_OFFICIAL_RELEASE` | 不设置则从 **MHSanaei/3x-ui latest** 取 tag；若要固定：`export XUI_OFFICIAL_RELEASE=v3.1.0` |
| `XUI_LDFLAGS` | 可选，`go build -ldflags "..."`，例如以后要加 `-X` 版本号时用 |
| `XUI_MAIN_FOLDER` | 默认 **`/usr/local/panel-srv`**（不含 `x-ui` 的安装目录前缀） |
| `XUI_PANEL_BINARY` | 默认 **`svc-core`**（`${XUI_MAIN_FOLDER}` 下的主程序文件名） |
| `XUI_DB_FOLDER` / `XUI_LOG_FOLDER` | 默认 **`/etc/panel-srv`** / **`/var/log/panel-srv`**，并写入 **`/etc/default/x-ui`** 供 systemd 读取 |
| `XUI_INSTALL_CLI_MENU` | 默认 **`0`**：**不安装** **`/usr/bin/x-ui`** 交互菜单；需要菜单时：`export XUI_INSTALL_CLI_MENU=1` |
| `XUI_WEB_BASE_PATH` | 默认 **`adV5YHG8JvMcm4rm5y`**（仅路径中间段；库内 **`webBasePath`** 为 **`/adV5YHG8JvMcm4rm5y/`**）。若保持 **`/`**：`export XUI_WEB_BASE_PATH=''` |

脚本会通过 **`apt-get` / `dnf` / `yum` / `microdnf` / `apk`** 安装编译依赖，并把 **官方 Go（版本与分叉里 `go.mod` 一致）** 解压到 **`/usr/local/go`**（可能覆盖该机已有 Go 目录，注意）。

面板仍使用 systemd 单元名 **`x-ui.service`**（与官方兼容）；`/etc/default/x-ui` 文件名保持不变，但其中 **`XUI_DB_FOLDER`/`XUI_LOG_FOLDER`** 会指向中性目录。**SQLite 库文件名**仍是程序内置的 **`x-ui.db`**（仅落在新的数据目录里）。

本地 API 自检工具见仓库 **`tools/panel_api_probe/`**。

## 装好后

```bash
systemctl status x-ui --no-pager
grep XUI_ /etc/default/x-ui
/usr/local/panel-srv/svc-core setting -show true
```

API：`Authorization: Bearer <XUI_API_SECRET>`。

**URL 前缀**由 **`webBasePath`** 决定。本仓库一键安装默认将路径段设为 **`adV5YHG8JvMcm4rm5y`**（见 `install-online.sh`）。例如 **`http(s)://IP:端口/adV5YHG8JvMcm4rm5y/panel/api/server/status`**。  
注意：须在路径里保留 **`panel/api`**。

## 常见问题

- **私有仓库**：`git clone https://...` 需 token，可在 `XUI_GIT_REPO` 里使用 `https://USER:TOKEN@github.com/org/repo.git`（注意安全，用后换 token）。
- **非 Debian**：若系统有 **`dnf`、`yum` 或 `apk`**，脚本会安装对应 RPM/Alpine 依赖；均无则退出并提示。**OpenSUSE/Zypper** 等暂未内置，可自行按依赖列表安装后改脚本。**无 systemd** 的环境需自行管理服务。
- **与 upstream 的差别**：一条命令等价于「官方离线包骨架 + **你的 Go 源码现场编译替换 `x-ui` 主二进制**」，避免再用 `CGO_ENABLED=0` 的跨界二进制导致 SQLite stub。
