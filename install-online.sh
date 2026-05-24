#!/usr/bin/env bash
#
# Online one-liner install (Ubuntu/Debian + systemd): official release tarball for
# assets/xray + your Git fork compiled on-server with CGO (SQLite OK).
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

XUI_FOLDER="${XUI_MAIN_FOLDER:=/usr/local/x-ui}"
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
case "${ID:-}${ID_LIKE:-}" in *debian*|*ubuntu*) ;;
    *)
        echo -e "${yellow}This script targets apt-based Debian/Ubuntu; continuing.${plain}"
        ;;
esac

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

ensure_x_ui_api_env_defaults() {
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
}

github_raw_prefix() {
    local u="$1"
    local b="$2"
    u="${u%.git}"
    if [[ "$u" =~ github\.com[:/]([^/]+)/([^/.]+)$ ]]; then
        echo "https://raw.githubusercontent.com/${BASH_REMATCH[1]}/${BASH_REMATCH[2]}/$b"
    fi
}

echo -e "${green}[1/6] Apt dependencies (build + sqlite dev)...${plain}"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq curl ca-certificates tar git gcc g++ libc6-dev pkg-config \
    sqlite3 libsqlite3-dev openssl make xz-utils >/dev/null

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

install -m 755 "${WORKDIR}/x-ui-panel-custom" "${XUI_FOLDER}/x-ui"

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

mkdir -p /var/log/x-ui

ensure_x_ui_api_env_defaults

echo -e "${green}[6/6] migrate + systemd...${plain}"
"${XUI_FOLDER}/x-ui" migrate
systemctl daemon-reload
systemctl enable x-ui >/dev/null
systemctl restart x-ui

RAW_BASE="$(github_raw_prefix "${XUI_GIT_REPO}" "${XUI_GIT_BRANCH}")"
if [[ -n "${RAW_BASE:-}" ]] && curl -fsSL "${RAW_BASE}/x-ui.sh" -o /usr/bin/x-ui 2>/dev/null; then
    chmod +x /usr/bin/x-ui
else
    echo -e "${yellow}(info) Installing upstream x-ui menu script (fork x-ui.sh not at ${RAW_BASE:-N/A})${plain}"
    curl -fsSL -o /usr/bin/x-ui https://raw.githubusercontent.com/MHSanaei/3x-ui/main/x-ui.sh
    chmod +x /usr/bin/x-ui
fi

echo ""
echo -e "${green}Done.${plain} systemctl status x-ui --no-pager"
echo -e "${yellow}API env (${plain}/etc/default/x-ui${yellow}):${plain}"
grep -E '^XUI_API' /etc/default/x-ui || true
echo ""
"${XUI_FOLDER}/x-ui" setting -show true 2>/dev/null || echo -e "${yellow}(setting -show unavailable until DB settles — check journalctl -u x-ui)${plain}"
