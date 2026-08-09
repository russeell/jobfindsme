#!/usr/bin/env bash
#
# jobfindsme 一键安装
# 本地求职雷达 · 聚合四大招聘平台 · 确定性匹配 · 增量岗位追踪
#
# 用法（推荐，只安装本地运行时）:
#   curl -fsSL https://cdn.jsdelivr.net/gh/russeell/jobfindsme@main/scripts/install.sh \
#     | bash
#
# 兼容旧式 MCP 配置:
#   bash scripts/install.sh <agent>
#   <agent>: codex | claude | cursor | zcode
#
# 也可直接: bash scripts/install.sh <agent>
#
# 设计原则:
#   - 默认只完成「检测 Python → 建运行时 → 装包 → 打印原生插件命令」
#   - 只有显式传入 <agent> 才写旧式 MCP 配置
#   - 清华镜像加速依赖下载；Release wheel 必须通过 SHA-256 校验
#   - 检测到 uv 则用 uv pip 加速；运行时布局与 venv 一致，可重复执行
#   - 不克隆源码、不装开发依赖、不下载浏览器

set -euo pipefail

VERSION="0.10.0"
WHEEL_GH="https://github.com/russeell/jobfindsme/releases/download/v${VERSION}/jobfindsme-${VERSION}-py3-none-any.whl"
CHECKSUM_GH="${WHEEL_GH}.sha256"
MIRROR="https://pypi.tuna.tsinghua.edu.cn/simple"
RUNTIME="$HOME/.jobfindsme/runtime"
AGENTS=(codex claude cursor zcode)
AGENT="${1:-}"
DOWNLOAD_DIR="$(mktemp -d)"
WHEEL_FILE="$DOWNLOAD_DIR/jobfindsme-${VERSION}-py3-none-any.whl"
CHECKSUM_FILE="${WHEEL_FILE}.sha256"
trap 'rm -rf "$DOWNLOAD_DIR"' EXIT

red()    { printf '\033[31m%s\033[0m\n' "$*"; }
green()  { printf '\033[32m%s\033[0m\n' "$*"; }
yellow() { printf '\033[33m%s\033[0m\n' "$*"; }
bold()   { printf '\033[1m%s\033[0m\n' "$*"; }
dim()    { printf '\033[2m%s\033[0m\n' "$*"; }

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

yellow "· 安装 jobfindsme[browser]（依赖走清华镜像）…"
"${PIP[@]}" --quiet \
  --index-url "$MIRROR" --upgrade \
  "$WHEEL_FILE[browser]"

BIN=( "$RUNTIME/bin/python" -m jobfindsme )
green "✓ 安装完成: $("${BIN[@]}" --version 2>&1)"

# ── 4. 接入 Agent ────────────────────────────────────────────────────────────
if [ -z "$AGENT" ]; then
  echo
  bold "📎 安装当前 Agent 的原生插件:"
  echo
  echo "  Codex:"
  echo "    codex plugin marketplace add russeell/jobfindsme --ref main"
  echo "    codex plugin add jobfindsme@jobfindsme"
  echo
  echo "  Claude Code:"
  echo "    claude plugin marketplace add russeell/jobfindsme"
  echo "    claude plugin install jobfindsme@jobfindsme"
  echo
  echo "  Cursor（市场上架前兼容入口）:"
  echo "    ~/.jobfindsme/runtime/bin/python -m jobfindsme connect cursor"
  echo
  bold "🚀 两步启动:"
  echo
  echo "  ┌─────────────────────────────────────────────────────┐"
  echo "  │ ① 登录 BOSS直聘（猎聘不需要）                         │"
  echo "  │    ~/.jobfindsme/runtime/bin/python -m jobfindsme setup │"
  echo "  │    在打开的专用 Chrome 窗口扫码，保持窗口运行            │"
  echo "  │                                                     │"
  echo "  │ 💡 不想装浏览器？跳过这步也能用 ——                     │"
  echo "  │    猎聘纯 HTTP 直连，不需要登录，先试试看结果             │"
  echo "  │    觉得岗位不够再加 BOSS                                │"
  echo "  │                                                     │"
  echo "  │ ② 重启 Agent，然后说：                                 │"
  echo "  │    用 jobfindsme 根据本地简历路径找上海 AI 应用工程师   │"
  echo "  └─────────────────────────────────────────────────────┘"
  echo
  dim  "其他 MCP 客户端: jobfindsme config"
  dim  "故障排查: 搜索无结果？运行 jobfindsme doctor 自检"
  exit 0
fi

if [[ ! " ${AGENTS[*]} " == *" $AGENT "* ]]; then
  red "✗ 未知 Agent: $AGENT"; yellow "可选: ${AGENTS[*]}"; exit 1
fi

"${BIN[@]}" connect "$AGENT"
green "✓ 已接入 $AGENT"
echo
bold "🚀 三步启动:"
echo
echo "  ┌─────────────────────────────────────────────────────┐"
echo "  │ ① 登录 BOSS直聘（猎聘不需要）                         │"
echo "  │    ~/.jobfindsme/runtime/bin/python -m jobfindsme setup │"
echo "  │    在专用 Chrome 扫码，保持窗口运行                      │"
echo "  │                                                     │"
echo "  │ 💡 跳过 BOSS 也能搜 —— 猎聘纯 HTTP 直连不需要浏览器      │"
echo "  │                                                     │"
echo "  │ ② 重启 $AGENT                                        │"
echo "  │                                                     │"
echo "  │ ③ 对 Agent 说：                                      │"
echo "  │    用 jobfindsme 根据简历找上海 AI 应用工程师，20K以上   │"
echo "  └─────────────────────────────────────────────────────┘"
echo
dim  "故障排查: 搜索无结果？运行 jobfindsme doctor 自检"
dim  "完整文档: https://github.com/russeell/jobfindsme"
