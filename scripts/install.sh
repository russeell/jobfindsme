#!/usr/bin/env bash
#
# jobfindsme 一键安装
# 本地求职雷达 · 聚合四大招聘平台 · Agent 语义匹配 · 增量岗位追踪
#
# 用法（人类用户）:
#   curl -fsSL https://cdn.jsdelivr.net/gh/russeell/jobfindsme@main/scripts/install.sh \
#     | bash -s -- <agent>
#
#   <agent>: codex | claude | cursor | zcode
#   （其他 Agent 用 jobfindsme config 输出标准 JSON 手动配置）
#
# 也可直接: bash scripts/install.sh <agent>
#
# 设计原则:
#   - 一条命令完成「检测 Python → 建运行时 → 装包 → 接入 Agent → 打印下一步」
#   - 清华镜像加速依赖下载；GitHub 直连失败自动回退镜像
#   - 检测到 uv 则用 uv pip 加速；运行时布局与 venv 一致，可重复执行
#   - 不克隆源码、不装开发依赖、不下载浏览器

set -euo pipefail

VERSION="0.8.0"
WHEEL_GH="https://github.com/russeell/jobfindsme/releases/download/v${VERSION}/jobfindsme-${VERSION}-py3-none-any.whl"
WHEEL_PROXY="https://mirror.ghproxy.com/${WHEEL_GH}"
MIRROR="https://pypi.tuna.tsinghua.edu.cn/simple"
RUNTIME="$HOME/.jobfindsme/runtime"
AGENTS=(codex claude cursor zcode)
AGENT="${1:-}"

red()    { printf '\033[31m%s\033[0m\n' "$*"; }
green()  { printf '\033[32m%s\033[0m\n' "$*"; }
yellow() { printf '\033[33m%s\033[0m\n' "$*"; }
bold()   { printf '\033[1m%s\033[0m\n' "$*"; }
dim()    { printf '\033[2m%s\033[0m\n' "$*"; }

echo
bold "🤖 jobfindsme v${VERSION} · AI 求职雷达"
dim  "   一个 MCP Server，同时搜 BOSS直聘/猎聘/智联/前程无忧，Agent 做语义匹配"
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

# ── 2. 选 wheel 源（GitHub 直连优先，失败回退 ghproxy，再失败回退直连）────────
WHEEL_URL="$WHEEL_GH"
if ! curl -fsSLI --max-time 8 -o /dev/null "$WHEEL_GH" 2>/dev/null; then
  yellow "· GitHub 直连较慢，切换镜像源"
  WHEEL_URL="$WHEEL_PROXY"
  if ! curl -fsSLI --max-time 8 -o /dev/null "$WHEEL_URL" 2>/dev/null; then
    yellow "· 镜像也不可达，回退 GitHub 直连"
    WHEEL_URL="$WHEEL_GH"
  fi
fi

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
  "jobfindsme[browser] @ $WHEEL_URL"

BIN=( "$RUNTIME/bin/python" -m jobfindsme )
green "✓ 安装完成: $("${BIN[@]}" --version 2>&1)"

# ── 4. 接入 Agent ────────────────────────────────────────────────────────────
if [ -z "$AGENT" ]; then
  echo
  bold "📎 接入你的 AI Agent（任选其一）:"
  for a in "${AGENTS[@]}"; do
    printf '    %s\n' "~/.jobfindsme/runtime/bin/python -m jobfindsme connect $a"
  done
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
  echo "  │    用 jobfindsme 根据简历找上海 AI 应用工程师           │"
  echo "  └─────────────────────────────────────────────────────┘"
  echo
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
