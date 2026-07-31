#!/usr/bin/env bash
#
# jobfindsme 一键安装
# 本地求职雷达 · 聚合 BOSS直聘 / 猎聘 / 前程无忧 / 智联招聘
#
# 用法（人类用户）:
#   curl -fsSL https://cdn.jsdelivr.net/gh/russeell/jobfindsme@main/scripts/install.sh \
#     | bash -s -- <agent>
#
#   <agent>: claude | codex | kimi | qwen | trae | trae-cn | zcode | qoder | workbuddy
#
# 也可直接: bash scripts/install.sh <agent>
#
# 设计原则:
#   - 一条命令完成「检测 Python → 建运行时 → 装包 → 接入 Agent → 打印下一步」
#   - 清华镜像加速依赖下载；GitHub 直连失败自动回退镜像
#   - 检测到 uv 则用 uv pip 加速；运行时布局与 venv 一致，可重复执行
#   - 不克隆源码、不装开发依赖、不下载浏览器

set -euo pipefail

VERSION="0.3.0"
WHEEL_GH="https://github.com/russeell/jobfindsme/releases/download/v${VERSION}/jobfindsme-${VERSION}-py3-none-any.whl"
WHEEL_PROXY="https://mirror.ghproxy.com/${WHEEL_GH}"
MIRROR="https://pypi.tuna.tsinghua.edu.cn/simple"
RUNTIME="$HOME/.jobfindsme/runtime"
AGENTS=(claude codex kimi qwen trae trae-cn zcode qoder workbuddy)
AGENT="${1:-}"

red()    { printf '\033[31m%s\033[0m\n' "$*"; }
green()  { printf '\033[32m%s\033[0m\n' "$*"; }
yellow() { printf '\033[33m%s\033[0m\n' "$*"; }
bold()   { printf '\033[1m%s\033[0m\n' "$*"; }

echo; bold "jobfindsme 一键安装 · 本地求职雷达"; echo

# ── 1. Python ────────────────────────────────────────────────────────────────
if ! command -v python3 >/dev/null 2>&1; then
  red "✗ 未找到 python3，请先安装 Python 3.11+"; exit 1
fi
if ! python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3,11) else 1)' 2>/dev/null; then
  red "✗ 需要 Python 3.11+，当前: $(python3 --version 2>&1)"; exit 1
fi
green "✓ Python $(python3 --version 2>&1)"

# ── 2. 选 wheel 源（GitHub 直连优先，失败回退 ghproxy）────────────────────────
WHEEL_URL="$WHEEL_GH"
if ! curl -fsSLI --max-time 8 -o /dev/null "$WHEEL_GH" 2>/dev/null; then
  yellow "· GitHub 直连较慢，切换镜像源"
  WHEEL_URL="$WHEEL_PROXY"
fi

# ── 3. 建运行时 + 装包（uv 加速 if available）─────────────────────────────────
mkdir -p "$HOME/.jobfindsme"
python3 -m venv "$RUNTIME" >/dev/null 2>&1 || python3 -m venv "$RUNTIME"

PIP=( "$RUNTIME/bin/python" -m pip )
if command -v uv >/dev/null 2>&1; then
  green "✓ 检测到 uv，加速依赖下载"
  PIP=( uv pip --python "$RUNTIME/bin/python" )
fi

yellow "· 安装 jobfindsme[browser]（依赖走清华镜像）…"
"${PIP[@]}" install --quiet \
  --index-url "$MIRROR" --upgrade \
  "jobfindsme[browser] @ $WHEEL_URL"

BIN=( "$RUNTIME/bin/python" -m jobfindsme )
green "✓ 安装完成: $("${BIN[@]}" --version 2>&1)"

# ── 4. 接入 Agent ────────────────────────────────────────────────────────────
if [ -z "$AGENT" ]; then
  echo
  bold "下一步 · 接入你的 AI Agent（任选其一，再重启 Agent）:"
  for a in "${AGENTS[@]}"; do
    printf '  %s\n' "~/.jobfindsme/runtime/bin/python -m jobfindsme connect $a"
  done
  echo
  yellow "接入后运行 setup 登录 BOSS直聘:  ~/.jobfindsme/runtime/bin/python -m jobfindsme setup"
  exit 0
fi

if [[ ! " ${AGENTS[*]} " == *" $AGENT "* ]]; then
  red "✗ 未知 Agent: $AGENT"; yellow "可选: ${AGENTS[*]}"; exit 1
fi

"${BIN[@]}" connect "$AGENT"
green "✓ 已接入 $AGENT · 重启该 Agent 即可使用"
echo
bold "最后一步 · 登录 BOSS直聘:"
yellow "  ~/.jobfindsme/runtime/bin/python -m jobfindsme setup"
echo "(在打开的专用 Chrome 中扫码登录，保持窗口运行)"
echo
bold "然后对 Agent 说:"
echo "  用 jobfindsme 根据我的简历找上海和杭州的 AI 应用工程师岗位，20K以上"
