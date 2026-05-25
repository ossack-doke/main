#!/usr/bin/env bash
#
# Online one-liner install (apt or dnf/yum + systemd): official release tarball for
# assets/xray + your Git fork compiled on-server with CGO (SQLite OK).
#
# Defaults (API-only, low profile on disk):
#   XUI_MAIN_FOLDER=/usr/local/panel-srv   XUI_PANEL_BINARY=svc-core
#   XUI_DB_FOLDER=/etc/panel-srv          XUI_LOG_FOLDER=/var/log/panel-srv
#   XUI_INSTALL_CLI_MENU=1  (install /usr/bin/x-ui menu; set 0/false to skip)
#   XUI_WEB_BASE_PATH=adV5YHG8JvMcm4rm5y  (URL segment; becomes /SEGMENT/ in DB; override or set empty to skip)
#
# Usage (replace YOUR_REPO):
#   export XUI_GIT_REPO='https://github.com/YOUR_ACCOUNT/3x-ui.git'
#   export XUI_GIT_BRANCH='main'
#   bash <(curl -fsSL https://raw.githubusercontent.com/YOUR_ACCOUNT/3x-ui/main/install-online.sh)
#
# Alternative: bash install-online.sh https://github.com/you/fork.git [branch]

set -euo pipefail

red='\033[0;31m'
green='\033[0;32m'
yellow='\033[0;33m'
plain='\033[0m'

[[ $EUID -eq 0 ]] || {
    echo -e "${red}Run as root (sudo -i).${plain}"
    exit 1
}

# Neutral on-disk layout (no "x-ui" in paths). Override any time before running.
XUI_FOLDER="${XUI_MAIN_FOLDER:-/usr/local/panel-srv}"
XUI_DB_FOLDER="${XUI_DB_FOLDER:-/etc/panel-srv}"
XUI_LOG_FOLDER="${XUI_LOG_FOLDER:-/var/log/panel-srv}"
# Installed daemon binary basename (executable file name under XUI_FOLDER).
XUI_PANEL_BINARY="${XUI_PANEL_BINARY:-svc-core}"
# Interactive menu at /usr/bin/x-ui (set XUI_INSTALL_CLI_MENU=0 to skip).
XUI_INSTALL_CLI_MENU="${XUI_INSTALL_CLI_MENU:-1}"
# Fixed web URL prefix (no leading/trailing slashes here). Results in webBasePath /SEGMENT/ in DB.
XUI_WEB_BASE_PATH="${XUI_WEB_BASE_PATH:-adV5YHG8JvMcm4rm5y}"

XUI_SERVICE_DIR="${XUI_SERVICE:=/etc/systemd/system}"

if [[ "${1:-}" =~ ^https?:// ]]; then
    export XUI_GIT_REPO="$1"
fi
if [[ "${2:-}" != "" ]]; then
    export XUI_GIT_BRANCH="$2"
fi

XUI_GIT_BRANCH="${XUI_GIT_BRANCH:-main}"

if [[ -z "${XUI_GIT_REPO:-}" ]]; then
    echo -e "${red}Set XUI_GIT_REPO to your fork URL, example:${plain}"
    echo "  export XUI_GIT_REPO='https://github.com/you/your-fork.git'"
    echo -e "${yellow}Or: bash install-online.sh https://github.com/you/fork.git [branch]${plain}"
    exit 1
fi

if [[ ! -f /etc/os-release ]]; then
    echo -e "${red}/etc/os-release missing${plain}"
    exit 1
fi
# shellcheck source=/dev/null
source /etc/os-release

if ! command -v apt-get >/dev/null 2>&1 &&
   ! command -v dnf >/dev/null 2>&1 &&
   ! command -v yum >/dev/null 2>&1 &&
   ! command -v microdnf >/dev/null 2>&1 &&
   ! command -v apk >/dev/null 2>&1
then
    echo -e "${red}No supported package manager found (need apt-get, dnf, yum, microdnf, or apk).${plain}" >&2
    exit 1
fi

install_build_dependencies() {
    echo -e "${green}[1/6] Build dependencies (C toolchain + SQLite for CGO)...${plain}"
    if command -v apt-get >/dev/null 2>&1; then
        export DEBIAN_FRONTEND=noninteractive
        apt-get update -qq
        apt-get install -y -qq curl ca-certificates tar git gcc g++ libc6-dev pkg-config \
            sqlite3 libsqlite3-dev openssl make xz-utils >/dev/null
    elif command -v dnf >/dev/null 2>&1; then
        dnf install -y curl ca-certificates tar git gcc gcc-c++ pkg-config \
            sqlite sqlite-devel openssl make xz >/dev/null
        command -v openssl >/dev/null 2>&1 || dnf install -y openssl >/dev/null 2>&1
    elif command -v yum >/dev/null 2>&1; then
        yum install -y curl ca-certificates tar git gcc gcc-c++ pkg-config \
            sqlite sqlite-devel openssl make xz >/dev/null
        command -v openssl >/dev/null 2>&1 || yum install -y openssl >/dev/null 2>&1
    elif command -v microdnf >/dev/null 2>&1; then
        microdnf install -y curl ca-certificates tar git gcc gcc-c++ pkg-config \
            sqlite sqlite-devel openssl make xz >/dev/null
        command -v openssl >/dev/null 2>&1 || microdnf install -y openssl >/dev/null 2>&1
    elif command -v apk >/dev/null 2>&1; then
        apk update -q
        apk add --no-cache curl ca-certificates tar git gcc musl-dev g++ pkgconf \
            sqlite sqlite-dev openssl make xz >/dev/null
    else
        echo -e "${red}No supported package manager found.${plain}" >&2
        exit 1
    fi

    command -v git >/dev/null 2>&1 && command -v gcc >/dev/null 2>&1 && command -v curl >/dev/null 2>&1 || {
        echo -e "${red}Dependency install incomplete (need git, gcc, curl). Re-run manually or inspect repo mirrors.${plain}" >&2
        exit 1
    }
}

arch_slug() {
    case "$(uname -m)" in
        x86_64 | amd64) echo amd64 ;;
        aarch64 | arm64) echo arm64 ;;
        armv7l) echo armv7 ;;
        *) echo -e "${red}Unsupported CPU: $(uname -m)${plain}" >&2 ; exit 1 ;;
    esac
}

map_go_arch() {
    case "$(uname -m)" in
        x86_64 | amd64) echo amd64 ;;
        aarch64 | arm64) echo arm64 ;;
        *) echo amd64 ;;
    esac
}

gen_random_string() {
    local length="$1"
    openssl rand -base64 $((length * 2)) 2>/dev/null | tr -dc 'a-zA-Z0-9' | head -c "$length"
}

ensure_x_ui_env_file() {
    local env_file="/etc/default/x-ui"
    umask 077
    mkdir -p /etc/default 2>/dev/null || true
    touch "$env_file"
    chmod 600 "$env_file" 2>/dev/null || true
    if ! grep -qs '^[[:space:]]*XUI_API_ONLY=' "$env_file" 2>/dev/null; then
        printf '%s\n' 'XUI_API_ONLY=true' >> "$env_file"
    fi
    if ! grep -qs '^[[:space:]]*XUI_API_SECRET=' "$env_file" 2>/dev/null; then
        local api_secret=""
        api_secret="$(openssl rand -hex 32 2>/dev/null)"
        [[ -z "$api_secret" ]] && api_secret="$(gen_random_string 64)"
        printf '%s\n' "XUI_API_SECRET=${api_secret}" >> "$env_file"
        echo -e "${green}XUI_API_SECRET written to ${env_file}${plain}"
    fi
    if ! grep -qs '^[[:space:]]*XUI_DB_FOLDER=' "$env_file" 2>/dev/null; then
        printf '%s\n' "XUI_DB_FOLDER=${XUI_DB_FOLDER}" >> "$env_file"
    fi
    if ! grep -qs '^[[:space:]]*XUI_LOG_FOLDER=' "$env_file" 2>/dev/null; then
        printf '%s\n' "XUI_LOG_FOLDER=${XUI_LOG_FOLDER}" >> "$env_file"
    fi
    if ! grep -qs '^[[:space:]]*XUI_MAIN_FOLDER=' "$env_file" 2>/dev/null; then
        printf '%s\n' "XUI_MAIN_FOLDER=${XUI_FOLDER}" >> "$env_file"
    fi
    if ! grep -qs '^[[:space:]]*XUI_PANEL_BINARY=' "$env_file" 2>/dev/null; then
        printf '%s\n' "XUI_PANEL_BINARY=${XUI_PANEL_BINARY}" >> "$env_file"
    fi
}

patch_systemd_unit_paths() {
    local unit="$1"
    [[ -f "$unit" ]] || return 0
    # shellcheck disable=SC2016
    sed -i \
        -e 's/^Description=.*/Description=Panel core service/' \
        -e "s|^WorkingDirectory=.*|WorkingDirectory=${XUI_FOLDER}/|" \
        -e "s|^ExecStart=.*|ExecStart=${XUI_FOLDER%/}/${XUI_PANEL_BINARY}|" \
        "$unit"
}

github_raw_prefix() {
    local u="$1"
    local b="$2"
    u="${u%.git}"
    if [[ "$u" =~ github\.com[:/]([^/]+)/([^/.]+)$ ]]; then
        echo "https://raw.githubusercontent.com/${BASH_REMATCH[1]}/${BASH_REMATCH[2]}/$b"
    fi
}

install_build_dependencies

WORKDIR="$(mktemp -d /tmp/xui-build-online.XXXXXX)"
cleanup() { rm -rf "$WORKDIR" ; }
trap cleanup EXIT

echo -e "${green}[2/6] Clone fork: ${XUI_GIT_REPO} (branch ${XUI_GIT_BRANCH}) ...${plain}"
git clone --depth 1 --branch "${XUI_GIT_BRANCH}" "${XUI_GIT_REPO}" "${WORKDIR}/src"

GO_MOD_VER="$(grep '^go ' "${WORKDIR}/src/go.mod" | awk '{print $2}')"
if [[ -z "$GO_MOD_VER" ]]; then
    echo -e "${red}Could not read Go version from go.mod${plain}"
    exit 1
fi

GO_DL_ARCH="$(map_go_arch)"
GO_ARCHIVE="go${GO_MOD_VER}.linux-${GO_DL_ARCH}.tar.gz"
GO_URL="https://go.dev/dl/${GO_ARCHIVE}"

echo -e "${green}[3/6] Go toolchain ${GO_MOD_VER} (from fork go.mod)...${plain}"
curl -fsSL "${GO_URL}" -o "${WORKDIR}/${GO_ARCHIVE}"
rm -rf /usr/local/go 2>/dev/null || true
tar -C /usr/local -xzf "${WORKDIR}/${GO_ARCHIVE}"

export GOTOOLCHAIN=auto
export CGO_ENABLED=1
export PATH="/usr/local/go/bin:${PATH}"

if [[ ! -d "${WORKDIR}/src/web/dist" ]] || [[ ! -f "${WORKDIR}/src/web/dist/index.html" ]]; then
    echo -e "${red}Fork must include web/dist/index.html so go:embed matches. Push stubs from this repo.${plain}"
    exit 1
fi

SLUG="$(arch_slug)"

REL_TAG="${XUI_OFFICIAL_RELEASE:-}"
if [[ -z "$REL_TAG" ]]; then
    REL_TAG="$(curl -fsSL https://api.github.com/repos/MHSanaei/3x-ui/releases/latest | grep '"tag_name":' | head -1 | cut -d'"' -f4)"
fi
if [[ -z "$REL_TAG" ]]; then
    echo -e "${red}Could not resolve upstream release tag. Set XUI_OFFICIAL_RELEASE=vX.Y.Z${plain}"
    exit 1
fi

echo -e "${green}[4/6] Upstream tarball ${REL_TAG} (${SLUG}) for Xray/assets...${plain}"
TGZ_URL="https://github.com/MHSanaei/3x-ui/releases/download/${REL_TAG}/x-ui-linux-${SLUG}.tar.gz"

systemctl stop x-ui 2>/dev/null || true
cd "${WORKDIR}"
curl -fsSL -o "${WORKDIR}/upstream.tgz" "${TGZ_URL}"
tar zxf upstream.tgz >/dev/null
rm -rf "${XUI_FOLDER}" 2>/dev/null || true
mv "${WORKDIR}/x-ui" "${XUI_FOLDER}"

echo -e "${green}[5/6] go build fork with CGO (several minutes)...${plain}"
cd "${WORKDIR}/src"
if [[ -n "${XUI_LDFLAGS:-}" ]]; then
    go build -trimpath -buildvcs=false -ldflags "${XUI_LDFLAGS}" \
        -o "${WORKDIR}/x-ui-panel-custom" .
else
    go build -trimpath -buildvcs=false \
        -o "${WORKDIR}/x-ui-panel-custom" .
fi

install -m 755 "${WORKDIR}/x-ui-panel-custom" "${XUI_FOLDER}/${XUI_PANEL_BINARY}"

if [[ "${SLUG}" == armv5 || "${SLUG}" == armv6 || "${SLUG}" == armv7 ]]; then
    if [[ -f "${XUI_FOLDER}/bin/xray-linux-${SLUG}" ]]; then
        cp -fa "${XUI_FOLDER}/bin/xray-linux-${SLUG}" "${XUI_FOLDER}/bin/xray-linux-arm" 2>/dev/null || true
        chmod +x "${XUI_FOLDER}/bin/xray-linux-arm" 2>/dev/null || true
    fi
fi
chmod +x "${XUI_FOLDER}/bin/"xray-linux-* 2>/dev/null || true

if [[ -f "${XUI_FOLDER}/x-ui.service.debian" ]]; then
    install -m 644 "${XUI_FOLDER}/x-ui.service.debian" "${XUI_SERVICE_DIR}/x-ui.service"
elif [[ -f "${XUI_FOLDER}/x-ui.service" ]]; then
    install -m 644 "${XUI_FOLDER}/x-ui.service" "${XUI_SERVICE_DIR}/x-ui.service"
else
    curl -fsSL -o "${XUI_SERVICE_DIR}/x-ui.service" \
        "https://raw.githubusercontent.com/MHSanaei/3x-ui/${REL_TAG}/x-ui.service.debian"
    chmod 644 "${XUI_SERVICE_DIR}/x-ui.service"
fi

patch_systemd_unit_paths "${XUI_SERVICE_DIR}/x-ui.service"

mkdir -p "${XUI_LOG_FOLDER}"
chmod 755 "${XUI_LOG_FOLDER}" 2>/dev/null || true
mkdir -p "${XUI_DB_FOLDER}"
chmod 700 "${XUI_DB_FOLDER}" 2>/dev/null || true

ensure_x_ui_env_file

strip_web_segment() {
    local s="${1:-}"
    s="${s#/}"
    s="${s%/}"
    printf '%s' "$s"
}

echo -e "${green}[6/6] migrate + fixed webBasePath + systemd...${plain}"
"${XUI_FOLDER}/${XUI_PANEL_BINARY}" migrate

WB_SEGMENT="$(strip_web_segment "${XUI_WEB_BASE_PATH:-}")"
if [[ -n "${WB_SEGMENT}" ]]; then
    echo -e "${green}webBasePath -> /${WB_SEGMENT}/${plain}"
    "${XUI_FOLDER}/${XUI_PANEL_BINARY}" setting -webBasePath "${WB_SEGMENT}"
else
    echo -e "${yellow}(info) XUI_WEB_BASE_PATH empty — leaving existing webBasePath in DB.${plain}"
fi

systemctl daemon-reload
systemctl enable x-ui >/dev/null
systemctl restart x-ui

if [[ "${XUI_INSTALL_CLI_MENU}" == "1" || "${XUI_INSTALL_CLI_MENU}" == "true" ]]; then
    RAW_BASE="$(github_raw_prefix "${XUI_GIT_REPO}" "${XUI_GIT_BRANCH}")"
    if [[ -n "${RAW_BASE:-}" ]] && curl -fsSL "${RAW_BASE}/x-ui.sh" -o /usr/bin/x-ui 2>/dev/null; then
        chmod +x /usr/bin/x-ui
    else
        echo -e "${yellow}(info) Installing upstream x-ui menu script (fork x-ui.sh not at ${RAW_BASE:-N/A})${plain}"
        curl -fsSL -o /usr/bin/x-ui https://raw.githubusercontent.com/MHSanaei/3x-ui/main/x-ui.sh
        chmod +x /usr/bin/x-ui
    fi
else
    rm -f /usr/bin/x-ui 2>/dev/null || true
    echo -e "${yellow}(info) Skipped interactive CLI (/usr/bin/x-ui). Defaults install it; omit XUI_INSTALL_CLI_MENU or set to 1 to install next run.${plain}"
fi

echo ""
echo -e "${green}Done.${plain} systemctl status x-ui --no-pager"
if [[ -n "${WB_SEGMENT}" ]]; then
    echo -e "${yellow}API example:${plain} http://<IP>:<端口>/${WB_SEGMENT}/panel/api/server/status"
else
    echo -e "${yellow}API example:${plain} http://<IP>:<端口>/panel/api/server/status ${yellow}(webBasePath '/')${plain}"
fi
echo -e "${yellow}Install: ${plain}${XUI_FOLDER}/${XUI_PANEL_BINARY}${yellow} (DB dir ${XUI_DB_FOLDER}, logs ${XUI_LOG_FOLDER})${plain}"
echo -e "${yellow}API env (${plain}/etc/default/x-ui${yellow}):${plain}"
grep -E '^XUI_' /etc/default/x-ui || true
echo ""
"${XUI_FOLDER}/${XUI_PANEL_BINARY}" setting -show true 2>/dev/null || echo -e "${yellow}(setting -show unavailable until DB settles — check journalctl -u x-ui)${plain}"
