#!/usr/bin/env bash
#
# jobfindsme 一键安装
# 本地求职雷达 · 聚合四大招聘平台 · 确定性匹配 · 增量岗位追踪
#
# 用法（推荐，只安装本地运行时）:
#   curl -fsSL https://github.com/russeell/jobfindsme/releases/latest/download/install.sh \
#     | bash
#
# 国内备选（jsdelivr CDN，push 后缓存可能滞后 12h）:
#   curl -fsSL https://cdn.jsdelivr.net/gh/russeell/jobfindsme@main/scripts/install.sh \
#     | bash
#
# 设计原则:
#   - 默认只完成「检测 Python → 建运行时 → 装包 → 注入 PATH → 打印接入方式」
#   - 版本动态取自 GitHub 最新 Release；API 不可用时回退到内置 PIN 版本
#   - 依赖默认走 PyPI（尊重 PIP_INDEX_URL / UV_INDEX_URL），失败时自动换清华镜像
#   - Release wheel 必须通过 SHA-256 校验
#   - 检测到 uv 则用 uv pip 加速；运行时布局与 venv 一致，可重复执行
#   - 不克隆源码、不装开发依赖、不下载浏览器

set -euo pipefail

PINNED_VERSION="0.11.0"
MIRROR="https://pypi.tuna.tsinghua.edu.cn/simple"
RUNTIME="$HOME/.jobfindsme/runtime"
LAUNCHER_DIR="$HOME/.local/bin"
LAUNCHER="$LAUNCHER_DIR/jobfindsme"
DOWNLOAD_DIR="$(mktemp -d)"
trap 'rm -rf "$DOWNLOAD_DIR"' EXIT

red()    { printf '\033[31m%s\033[0m\n' "$*"; }
green()  { printf '\033[32m%s\033[0m\n' "$*"; }
yellow() { printf '\033[33m%s\033[0m\n' "$*"; }
bold()   { printf '\033[1m%s\033[0m\n' "$*"; }
dim()    { printf '\033[2m%s\033[0m\n' "$*"; }

# ── 0. 解析最新版本号（GitHub API，失败回退 PINNED_VERSION）───────────────────
VERSION="$PINNED_VERSION"
LATEST_TAG="$(curl -fsSL --connect-timeout 8 --max-time 15 \
    https://api.github.com/repos/russeell/jobfindsme/releases/latest \
    2>/dev/null | python3 -c '
import json, sys
try:
    d = json.load(sys.stdin)
    tag = d.get("tag_name", "")
    sys.stdout.write(tag[1:] if tag.startswith("v") else tag)
except Exception:
    pass
')"
if printf '%s' "$LATEST_TAG" | grep -qE '^[0-9]+\.[0-9]+\.[0-9]+$'; then
  VERSION="$LATEST_TAG"
fi

WHEEL_GH="https://github.com/russeell/jobfindsme/releases/download/v${VERSION}/jobfindsme-${VERSION}-py3-none-any.whl"
CHECKSUM_GH="${WHEEL_GH}.sha256"
WHEEL_FILE="$DOWNLOAD_DIR/jobfindsme-${VERSION}-py3-none-any.whl"
CHECKSUM_FILE="${WHEEL_FILE}.sha256"

echo
bold "🤖 jobfindsme v${VERSION} · AI 求职雷达"
dim  "   一个 MCP Server，同时搜 BOSS直聘/猎聘/智联/前程无忧，本地筛选排序"
echo

# ── 1. Python ────────────────────────────────────────────────────────────────
if ! command -v python3 >/dev/null 2>&1; then
  red "✗ 未找到 python3，请先安装 Python 3.11+"
  dim  "   macOS:  brew install python@3.12"
  dim  "   Ubuntu: sudo apt install python3.12 python3.12-venv"
  exit 1
fi
if ! python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3,11) else 1)' 2>/dev/null; then
  red "✗ 需要 Python 3.11+，当前: $(python3 --version 2>&1)"
  exit 1
fi
green "✓ Python $(python3 --version 2>&1)"

# ── 2. 下载并校验官方 Release wheel ─────────────────────────────────────────
yellow "· 下载 jobfindsme v${VERSION} 官方 Release…"
curl -fL --retry 3 --retry-all-errors \
  --connect-timeout 10 --max-time 120 \
  -o "$WHEEL_FILE" "$WHEEL_GH"
curl -fL --retry 3 --retry-all-errors \
  --connect-timeout 10 --max-time 30 \
  -o "$CHECKSUM_FILE" "$CHECKSUM_GH"

expected_checksum="$(awk 'NR == 1 {print $1}' "$CHECKSUM_FILE")"
if command -v shasum >/dev/null 2>&1; then
  actual_checksum="$(shasum -a 256 "$WHEEL_FILE" | awk '{print $1}')"
elif command -v sha256sum >/dev/null 2>&1; then
  actual_checksum="$(sha256sum "$WHEEL_FILE" | awk '{print $1}')"
else
  red "✗ 无法校验安装包：需要 shasum 或 sha256sum"
  exit 1
fi
if [[ ! "$expected_checksum" =~ ^[0-9a-fA-F]{64}$ ]] || \
   [[ "$actual_checksum" != "$expected_checksum" ]]; then
  red "✗ Release wheel SHA-256 校验失败，安装已停止"
  exit 1
fi
green "✓ Release wheel 校验通过"

# ── 3. 建运行时 + 装包（uv 加速 if available）─────────────────────────────────
mkdir -p "$HOME/.jobfindsme"
python3 -m venv "$RUNTIME" >/dev/null 2>&1 || python3 -m venv "$RUNTIME"

PIP=( "$RUNTIME/bin/python" -m pip install )
if command -v uv >/dev/null 2>&1; then
  green "✓ 检测到 uv，加速依赖下载"
  PIP=( uv pip install --python "$RUNTIME/bin/python" )
fi

# 依赖默认走 PyPI，尊重用户环境变量；失败时自动换清华镜像重试一次。
INDEX_URL="${PIP_INDEX_URL:-https://pypi.org/simple}"
# 注意：macOS 自带 bash 3.2 会把变量名后紧跟的全角字符并入变量名，
# 因此所有后面跟非 ASCII 字符的变量一律使用 ${VAR} 花括号形式。
yellow "· 安装 jobfindsme[browser]（index: ${INDEX_URL}）…"
if ! "${PIP[@]}" --quiet \
    --index-url "$INDEX_URL" --upgrade \
    "$WHEEL_FILE[browser]"; then
  if [ "$INDEX_URL" != "$MIRROR" ]; then
    yellow "· 默认源失败，改用清华镜像重试…"
    INDEX_URL="$MIRROR"
    "${PIP[@]}" --quiet \
      --index-url "$INDEX_URL" --upgrade \
      "$WHEEL_FILE[browser]"
  else
    red "✗ pip 安装失败（index: ${INDEX_URL}），请检查网络后重试"
    exit 1
  fi
fi

green "✓ 安装完成: $("$RUNTIME/bin/python" -m jobfindsme --version 2>&1)"

# ── 4. 注入 PATH（~/.local/bin/jobfindsme）───────────────────────────────────
mkdir -p "$LAUNCHER_DIR"
ln -sf "$RUNTIME/bin/jobfindsme" "$LAUNCHER"
if [ "$(command -v jobfindsme 2>/dev/null || true)" = "$LAUNCHER" ]; then
  green "✓ jobfindsme 已加入 PATH（${LAUNCHER}）"
else
  yellow "· 提示: 命令 jobfindsme 当前不可用或指向其他版本（PATH 里已有同名程序？）"
  yellow "  可用全路径执行:"
  yellow "    $LAUNCHER"
  yellow "  或临时加入: export PATH=\"\$HOME/.local/bin:\$PATH\""
fi

# ── 5. 接入 Agent ────────────────────────────────────────────────────────────
echo
bold "📎 接入你的 Agent:"
echo
echo "  Codex / Claude Code（原生插件）:"
echo "    codex plugin marketplace add russeell/jobfindsme --ref main"
echo "    codex plugin add jobfindsme@jobfindsme"
echo "    claude plugin marketplace add russeell/jobfindsme"
echo "    claude plugin install jobfindsme@jobfindsme"
echo
echo "  其他 MCP 客户端:"
echo "    jobfindsme connect            # 自动探测当前 Agent"
echo "    jobfindsme connect cursor     # 显式指定宿主"
echo "    jobfindsme config             # 打印标准 MCP JSON 手动粘贴"
echo
bold "🚀 两步启动:"
echo
echo "  ① jobfindsme setup   # 登录 BOSS直聘（猎聘不需要，可跳过）"
echo "  ② 重启 Agent 后说：用 jobfindsme 根据简历找上海 AI 应用工程师，20K以上"
echo
dim  "故障排查: 搜索无结果？运行 jobfindsme doctor 自检"
dim  "完整文档: https://github.com/russeell/jobfindsme"
