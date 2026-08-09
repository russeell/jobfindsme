# jobfindsme 安装指南

> jobfindsme 是本地 MCP Server：聚合 BOSS直聘、猎聘、智联招聘、前程无忧，
> 提取结构化岗位信号并返回固定格式推荐。**不需要注册任何服务、不需要 API Key。**
>
> - 猎聘：纯 HTTP 直连，**不需要浏览器、不需要登录**
> - BOSS直聘：需要一次扫码登录（可选，见 [登录 BOSS直聘](#登录-boss直聘可选)）
> - 智联招聘 / 前程无忧：优先 HTTP，遇到安全校验时降级到浏览器桥或明确标注失败原因

---

## ✨ 最简单的方式：和 Agent 聊天安装（推荐）

**你什么都不用装。** 把下面这段话复制，发给你的 AI Agent
（Claude Code / Codex / Cursor / ZCode）：

```text
请严格按说明快速安装 jobfindsme。请识别你当前是哪一种 Agent；
不要克隆仓库或运行测试：
https://github.com/russeell/jobfindsme/blob/main/INSTALL.md
```

**Agent 会自动完成：**

```text
① 检测 Python 环境
② 创建独立运行空间（~/.jobfindsme/runtime）
③ 安装 jobfindsme 本体
④ 自动写入它自己的 MCP 配置
⑤ 告诉你下一步
```

**你只需要做两件事：**

1. **重启 Agent**
2. 对 Agent 说：`用 jobfindsme，根据我的简历找上海的 AI 应用工程师，20K以上，社招。`

> 整个过程通常 3 分钟内完成。你不需要打开终端、不需要了解 MCP 是什么、
> 不需要手动编辑任何配置文件——全部由 Agent 代劳。

---

## 方式二：一行命令（想自己动手）

把 `codex` 换成你的 Agent（`claude` / `cursor` / `zcode`）：

```bash
curl -fsSL https://cdn.jsdelivr.net/gh/russeell/jobfindsme@main/scripts/install.sh \
  | bash -s -- codex
```

脚本自动完成：检测 Python 3.11+ → 建独立 venv（`~/.jobfindsme/runtime`）→
装包（清华镜像加速，GitHub 直连失败自动回退）→ 写入该 Agent 的 MCP 配置 →
打印下一步。可重复执行。

---

## 安装后三步启动

### 1. 接入 Agent（脚本已自动完成）

| Agent | 命令 |
|-------|------|
| Codex | `jobfindsme connect codex` |
| Claude（Desktop/Code 共用） | `jobfindsme connect claude` |
| Cursor | `jobfindsme connect cursor` |
| ZCode（开发者用） | `jobfindsme connect zcode` |
| 其他 MCP 客户端 | `jobfindsme config`（打印标准 JSON，手动粘贴到任意客户端） |

> `connect` 只写 MCP 配置文件路径，幂等可重复执行。每个 Agent 共用同一个运行时。
> 其他客户端（Kimi/Qwen/TRAE/Cherry Studio 等）同样支持标准 JSON——用 `jobfindsme config`
> 输出后粘贴到对应配置文件的 `mcpServers` 即可，或 `connect --path <配置文件路径>` 自动写入。

### 2. 登录 BOSS直聘（可选）

对 Agent 说 **「帮我登录 BOSS直聘」**——Agent 会运行 `jobfindsme setup`，
几秒内弹出**专用 Chrome 窗口**，扫码登录后保持窗口运行。

> 💡 **跳过这步也能搜**——猎聘纯 HTTP 直连，不需要浏览器也不需要登录。
> 先搜起来，觉得岗位不够再补 BOSS。

### 3. 开始搜

**重启 Agent**，然后对它说：

```text
用 jobfindsme，根据我的简历找上海的 AI 应用工程师，20K以上，社招。
```

---

## 验证安装

```bash
# 版本检查
jobfindsme --version            # 期望输出 jobfindsme 0.4.0+

# 自检
jobfindsme doctor
```

`doctor` 输出 JSON，关注两个字段：

```json
{"name": "python", "ok": true, "required": true}
{"name": "mcp", "ok": true, "message": "9 tools", "required": true}
```

- `required: true` 的项必须全为 `ok: true`（版本、Python、数据库、权限、MCP、连接器）
- `browser_connectors` / `boss_login` 为 `ok: false` 且 `required: false` 属**正常**
  —— 表示 BOSS 浏览器尚未启动，安装不算失败，猎聘搜索不受影响

---

## Agent 安装配方（给 AI Agent 的严格指令）

只做以下步骤，**不要**克隆仓库、查看源码、运行测试套件、安装开发依赖或下载浏览器。

### 第 1 步：检查 Python

```bash
python3 --version
```

需要 3.11 及以上。不满足则停止并告知用户（macOS: `brew install python@3.12`；
Ubuntu: `sudo apt install python3.12 python3.12-venv`）。

### 第 2 步：安装（GitHub Release wheel）

```bash
python3 -m venv ~/.jobfindsme/runtime
~/.jobfindsme/runtime/bin/python -m pip install --upgrade \
  --index-url https://pypi.tuna.tsinghua.edu.cn/simple \
  "jobfindsme[browser] @ https://github.com/russeell/jobfindsme/releases/download/v0.9.0/jobfindsme-0.9.0-py3-none-any.whl"
```

> 版本号与仓库最新 Release 保持一致（当前 v0.9.0）。PyPI 安装会在项目
> 成熟后开放，届时此配方自动切换到 `pip install jobfindsme[browser]`。

### 第 3 步：接入当前 Agent

识别正在读本文件的 Agent 名称，用 `connect` 写入 MCP 配置（如正在读的是
Codex，则用 `codex`）：

```bash
~/.jobfindsme/runtime/bin/python -m jobfindsme connect codex
```

Agent 名与上表一致。未知客户端用 `config` 输出 JSON。

### 第 4 步：验证

```bash
~/.jobfindsme/runtime/bin/python -m jobfindsme --version
~/.jobfindsme/runtime/bin/python -m jobfindsme doctor
```

BOSS 登录检查标为"可选/未配置"不构成失败，不要因此重试安装。

### 第 5 步：告知用户

告诉用户：重启 Agent 后说第一句话（见「开始搜」）。BOSS 登录是可选增强。

> 时间预算：正常 3 分钟内完成。任一命令超过 5 分钟，停止并上报该命令及其
> 最后输出，不要尝试无关的修复。

---

## 常见问题

**Q：搜索结果为什么是 0？**
先 `jobfindsme doctor`。看来源状态：猎聘直连失败通常是被限流，稍后再试；
BOSS 显示"未登录"就去 `jobfindsme setup` 扫码。系统不会把失败伪装成"没有岗位"。

**Q：安装脚本卡在下载？**
Release wheel 只从 GitHub 官方下载，并使用随 Release 发布的 SHA-256
校验文件验证完整性；Python 依赖走清华 PyPI 镜像。
仍失败时重试一次，或改用方式三的 pip 安装。

**Q：可以用 conda / pyenv 的 Python 吗？**
可以。脚本用系统 `python3` 建独立 venv，不干扰现有环境。

**Q：macOS 提示 Chrome 无法打开？**
`jobfindsme setup` 会启动专用 Chrome profile（`~/.jobfindsme/chrome-profile`），
与你的个人 Chrome 完全隔离。若系统拦截，到「系统设置 → 隐私与安全性」允许。

**Q：会关闭我自己的 Chrome 吗？**
不会。连接器只管理自己启动的专用 profile 进程（PID 记录在
`~/.jobfindsme/chrome-profile/chrome.pid`），绝不触碰其他 Chrome 窗口。

---

## 更新

```bash
# 重跑原命令即可（脚本带 --upgrade）
curl -fsSL https://cdn.jsdelivr.net/gh/russeell/jobfindsme@main/scripts/install.sh \
  | bash -s -- codex
```

数据库自动迁移，历史岗位、状态和搜索计划全部保留。

---

## 卸载

```bash
# ① 移除 Agent 的 MCP 配置（各 Agent 配置文件中的 jobfindsme 条目被清除）
jobfindsme uninstall codex        # 换成你接入的 Agent

# ② 删除运行时与全部本地数据（岗位、状态、简历事实）
rm -rf ~/.jobfindsme
```

> `jobfindsme uninstall <agent>` 只移除配置、**保留全部数据**；想彻底清除数据
> 再执行第二步 `rm -rf ~/.jobfindsme`。删除后不可恢复，先 `jobfindsme export
> --workspace <id>` 备份。

---

## 数据与隐私

- 简历只在本地解析，完整文本不进 Agent 上下文，只存结构化事实到本地 SQLite
- 岗位描述按不可信外部数据处理，不作为指令执行
- 不自动投递、不绕过验证码、不做批量抓取
- 所有数据可随时导出与清除：`jobfindsme export --workspace <id>`（或让 Agent 调用
  `export_local_data` / `delete_local_data`）

有问题或发现失效来源，请到
[Issues](https://github.com/russeell/jobfindsme/issues) 反馈。
