# 求职助手技能来源

这三个中文技能是针对 JobFindsMe 本地岗位、脱敏简历和受控研究工具的适配，未引入外部框架、爬虫、导出系统或依赖。仅参考下列 MIT 项目的工作流与组织方法；原许可证完整保留在 licenses/，随桌面包分发。

- 简历定制：varunr89/resume-tailoring-skill，参考真实经历与岗位要求匹配、缺口追问和草稿审阅。
  https://github.com/varunr89/resume-tailoring-skill/blob/9a4a0f20f5983d1b533627b8c5191acd1ca0cd89/skills/resume-tailoring/SKILL.md
  许可证：licenses/resume-tailoring-MIT.txt。
- 面试准备：yangshun/tech-interview-handbook，参考行为面试中的 STAR、项目故事和复盘准备；不复制题库或参考答案。
  https://github.com/yangshun/tech-interview-handbook/blob/e1d28e8886c0b6ff3e50da991ce0e895134ddc59/apps/website/contents/behavioral-interview.md
  许可证：licenses/tech-interview-handbook-MIT.txt。
- 深度研究：dzhng/deep-research，参考研究方向拆解、已有发现引导下一步查询与保留来源；不复制它的 Firecrawl/递归执行器。
  https://github.com/dzhng/deep-research/blob/1f8f3e285bbc23e80b98a66a64effab9069f3ad4/src/deep-research.ts
  许可证：licenses/deep-research-MIT.txt。

不能将这些来源中的公开示例、数字或经历当作用户自身材料。

本轮补充参考：MadsLorentzen/ai-job-search（MIT）的岗位材料范围与逐轮面试组织方式，未复制其个人档案或自动写入 Git 的流程。
https://github.com/MadsLorentzen/ai-job-search/tree/d7287ec83493102f253282fab07bd88412e7dd50/.claude/skills/job-application-assistant
许可证：licenses/ai-job-search-MIT.txt。

联网检索能力：参考 Panniantong/Agent-Reach（MIT）的能力路由、搜索/原文分层和不把配置当作健康证明的做法，自行实现固定只读服务适配，不加载其运行时、全局配置或用户凭据。
https://github.com/Panniantong/Agent-Reach/tree/a19a171fa980a0785849596492e0af4db800c82f
许可证：licenses/agent-reach-MIT.txt。

Exa 官方托管搜索接口的格式与工具协议参考官方 exa-labs/exa-mcp-server，未复制服务器源码、Agent 或客户端框架。仅通过固定 HTTPS 远程接口调用 web_search_exa；不恢复 JobFindsMe 旧 MCP 服务器。
https://github.com/exa-labs/exa-mcp-server/blob/f3d71fb6b0ff4b4683f108f05bc2bae61a9f7e97/src/tools/webSearch.ts
服务配额及可用性受提供方限制；搜索内容只用于发现，不能成为已核验原文。
