# JobFindsMe

JobFindsMe 是一个面向中国技术求职者和 AI 工具用户的
Agent-native、Local-first 职位发现与跟踪引擎。

> 让现有 AI Agent 根据本地简历或自然语言描述，在合规和用户授权范围内，
> 从企业招聘官网、公开招聘接口和招聘平台导入数据中，找到真正值得投递的岗位。

## 产品边界

V0.1 由以下部分组成：

- 不依赖模型的确定性 Python Core；
- 本地 SQLite Workspace；
- 可靠的 CLI 降级入口；
- 本地 `stdio` MCP Server；
- Qwen Code、Codex 和 Claude Code 首批集成；
- 企业官网、公开 ATS、URL、CSV 和 JSON 岗位来源；
- 可复现的离线评测。

设计目标是兼容所有遵循 MCP `stdio` 协议且支持当前工具 Schema 的 Agent，
但只有通过兼容测试的客户端才会列入官方支持矩阵。后续候选包括 Cherry Studio、
Cursor、Cline、Roo Code 和 OpenCode。

V0.1 不要求模型 API，不建设公共 Web SaaS，也不自研 Agent Runtime。
此前完成的 Web 版本已归档为同级目录 `jobfindsme-web-prototype`。

## 开发

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -e ".[dev]"
pytest
ruff check .
ruff format --check .
```

初始化本地 Workspace：

```bash
jobfindsme workspace init
jobfindsme plan add --name "杭州 AI 应用工程师" --role "AI应用工程师" --city "杭州"
jobfindsme plan list
```

完整产品定位、架构、安全边界和里程碑位于 `PROJECT_SPEC.md`，
可执行开发任务位于 `specs/feature_list.json`。
