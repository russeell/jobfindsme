<p align="center">
  <img src="docs/images/logo.svg" width="72" height="72" alt="JobFindsMe 标志">
</p>
<h1 align="center">JobFindsMe</h1>
<p align="center"><strong>一次搜索四个平台，从找岗位到准备面试。</strong></p>
<p align="center">开源 AI 求职桌面助手 · macOS / Windows</p>
<p align="center">
  <a href="https://github.com/russeell/jobfindsme/releases/latest"><img src="https://img.shields.io/github/v/release/russeell/jobfindsme?style=flat-square&color=2563eb" alt="最新版本"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/许可证-MIT-2563eb?style=flat-square" alt="MIT 许可证"></a>
</p>
<p align="center">
  <a href="https://github.com/russeell/jobfindsme/releases/latest">下载应用</a> ·
  <a href="#开始使用">开始使用</a> ·
  <a href="https://github.com/russeell/jobfindsme/issues">反馈问题</a>
</p>

## 四件事，一个工作台

| 功能 | 能帮你做什么 |
| --- | --- |
| **一键检索四平台** | 同时搜索 **BOSS直聘、猎聘、智联招聘、前程无忧**，结果陆续展示；筛选、继续查找、阅读完整 JD。岗位搜索无需配置模型。 |
| **修改简历** | 结合岗位要求和真实经历生成修改草稿，逐项审阅后保存，不编造经历。 |
| **模拟面试** | 按岗位方向给准备重点，再逐题练习、点评与追问。**没有 JD 也能开始。** |
| **深度研究** | 围绕目标岗位、公司与行业做背景调研，读取原文、追查缺口，并附来源供核对。 |

收藏岗位、记录投递进展，聊天支持搜索、归档和从某条回复创建分支。

![岗位检索、筛选与 JD 详情](docs/images/jobfindsme-search.png)

![求职助手中的面试准备示例](docs/images/jobfindsme-research.png)

<sub>界面示例使用虚构岗位与演示对话；平台覆盖受登录、验证码及网站变化影响，研究结论请结合原文核对。</sub>

## 下载

| 系统 | 下载 |
| --- | --- |
| macOS · Apple Silicon（M 系列） | [mac-arm64.zip](https://github.com/russeell/jobfindsme/releases/latest/download/mac-arm64.zip) |
| Windows · x64 | [windows-x64.zip](https://github.com/russeell/jobfindsme/releases/latest/download/windows-x64.zip) |

解压后打开 `JobFindsMe.app` 或 `JobFindsMe.exe`，无需另装 Python 或 Node.js。安装包尚未签名，首次打开提示与校验信息见[发布页](https://github.com/russeell/jobfindsme/releases/latest)。

## 开始使用

1. **选平台**：在「设置 → 岗位来源」选择平台，需要登录时使用内置浏览器。
2. **找岗位**：输入岗位方向，选择一个城市或不限城市，点击「找岗位」。
3. **用 AI 准备**：配置自己的模型，在「求职助手 → ＋」选择「修改简历」「模拟面试」或「深度研究」。

> 帮我准备 Agent 开发面试。 / 结合这份 JD 修改简历。 / 研究这家公司和岗位，给出原文依据。

岗位、简历和对话保存在本机；使用 AI 时，相关材料会发送给你配置的模型服务，可能产生费用。联网检索只应使用公开查询词。应用不会自动投递。

<details>
<summary>开发与贡献</summary>

Electron · React · Python · SQLite · Pi Agent。开发需要 Python 3.11+、Node.js/npm，见[开发说明](docs/desktop/README.md)。

欢迎 Star、[Issue](https://github.com/russeell/jobfindsme/issues) 和 PR；反馈时请勿上传简历、密钥或 Cookie。

[贡献指南](CONTRIBUTING.md) · [项目结构](docs/desktop/STRUCTURE.md) · [安全说明](SECURITY.md) · [MIT 许可证](LICENSE)

</details>
