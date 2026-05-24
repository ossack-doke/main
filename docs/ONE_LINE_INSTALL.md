# 一条命令在线安装（自维护 fork）

本仓库在官方包（Xray、资源文件）基础上，从你的 **GitHub 分叉** **在服务器上 `go build`（CGO=1）** 编译主程序，因此 **SQLite 正常**，并写入 **`XUI_API_ONLY` / `XUI_API_SECRET`**（`/etc/default/x-ui`）。

## 你需要先做的事

1. 在 GitHub 上建好 **公开或私有分叉**（`git remote` 指到你的仓库）。
2. **把这里的改动完整 push 上去**，尤其包括：
   - `install-online.sh`
   - `web/dist/`（至少要有 `index.html` 占位，否则会 `go:embed` 失败）
   - `x-ui.rc`（若你需要 Alpine，可以后再扩展脚本；当前脚本面向 **Ubuntu/Debian + systemd**）
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

脚本会 **`apt install`** 编译依赖，并把 **官方 Go（版本与分叉里 `go.mod` 一致）** 解压到 **`/usr/local/go`**（可能覆盖该机已有 Go 目录，注意）。

## 装好后

```bash
systemctl status x-ui --no-pager
grep XUI_ /etc/default/x-ui
/usr/local/x-ui/x-ui setting -show true
```

API：`Authorization: Bearer <XUI_API_SECRET>`，路径为 `http(s)://IP:端口/webBase路径/panel/api/...`。

## 常见问题

- **私有仓库**：`git clone https://...` 需 token，可在 `XUI_GIT_REPO` 里使用 `https://USER:TOKEN@github.com/org/repo.git`（注意安全，用后换 token）。
- **非 Debian/Ubuntu**：当前脚本只做 `apt`，其它发行版可自行改脚本或在本机 Dockerfile 内执行。
- **与 upstream 的差别**：一条命令等价于「官方离线包骨架 + **你的 Go 源码现场编译替换 `x-ui` 主二进制**」，避免再用 `CGO_ENABLED=0` 的跨界二进制导致 SQLite stub。
