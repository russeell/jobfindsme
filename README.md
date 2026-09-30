<p align="center">
  <img src="docs/images/logo.svg" width="72" height="72" alt="JobFindsMe 标志">
</p>
<h1 align="center">JobFindsMe</h1>
<p align="center"><strong>找岗位，改简历，准备面试。</strong></p>
<p align="center">一个桌面AI求职助手，欢迎Star和PR。</p>
<p align="center">
  <a href="https://github.com/russeell/jobfindsme/releases/latest"><img src="https://img.shields.io/github/v/release/russeell/jobfindsme?style=flat-square&color=2563eb" alt="最新发布版"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/许可证-MIT-2563eb?style=flat-square" alt="MIT 许可证"></a>
</p>
<p align="center">
  <a href="https://github.com/russeell/jobfindsme/releases/latest">下载应用</a> ·
  <a href="#开始使用">开始使用</a> ·
  <a href="https://github.com/russeell/jobfindsme/issues">反馈问题</a>
</p>

![岗位搜索与详情](docs/images/jobfindsme-search.png)

<sub>截图来自当前开发版，岗位与对话均为示例数据；下载版本以发布页为准。</sub>

## 能帮你做什么

- **找岗位**：搜索 BOSS直聘、猎聘、智联招聘和前程无忧，按城市、薪资等条件筛选；导入并确认简历，辅助岗位匹配。
- **聊求职**：选择简历定制、面试准备或深度研究；结合 JD 和真实经历生成修改草稿，了解公司时提供原文引用。
- **记进展**：收藏岗位，记录已读与投递状态，保留对话，方便下次接着聊。

![求职助手对话](docs/images/jobfindsme-research.png)

## 下载

| 系统 | 下载与打开 |
| --- | --- |
| macOS · Apple Silicon（M 系列） | [下载 mac-arm64.zip](https://github.com/russeell/jobfindsme/releases/latest/download/mac-arm64.zip)，解压后打开 `JobFindsMe.app` |
| Windows · x64 | [下载 windows-x64.zip](https://github.com/russeell/jobfindsme/releases/latest/download/windows-x64.zip)，完整解压后运行 `JobFindsMe.exe` |

无需另装 Python 或 Node.js。安装包尚未签名，首次打开可能出现系统安全提示，说明与 SHA-256 校验信息见[发布页](https://github.com/russeell/jobfindsme/releases/latest)。其他系统暂未提供安装包。

## 开始使用

1. 在「设置 → 岗位来源」选择平台，需要登录时使用内置浏览器。
2. 在「找工作」输入岗位方向，例如 `Python 后端` 或 `Agent 开发`，查看详情和招聘原页。
3. 在「设置 → 模型设置」配置模型，然后打开「求职助手」，点「＋」添加技能或资料，粘贴 JD 或直接提问。

> 这份 JD 最看重哪些能力？我应该怎样准备面试？

部分平台的检索、详情和翻页会受登录、验证码及网站改版影响，不保证覆盖全部岗位。公司研究也可能缺少材料，请结合引用核对。

岗位、简历和对话保存在本机。使用模型时，相关内容会发送给你配置的服务，并可能产生费用。应用不会自动投递。

<details>
<summary>开发与贡献</summary>

使用 Electron、React、Python、SQLite 和 Pi Agent。需要 Python 3.11+、Node.js/npm；运行方式见[开发说明](docs/desktop/README.md)。

欢迎提交 [Issue](https://github.com/russeell/jobfindsme/issues) 或 PR。反馈时请附操作步骤和错误提示，勿上传简历、密钥或 Cookie。

[贡献指南](CONTRIBUTING.md) · [项目结构](docs/desktop/STRUCTURE.md) · [安全说明](SECURITY.md)

</details>

[MIT 许可证](LICENSE)
