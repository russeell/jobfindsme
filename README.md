<div align="center">

# JobFindsMe

**少切几个招聘网站，多了解一个好机会。**

在一个桌面应用里，检索 **4 个招聘平台 + 16 家公司官网**，结合简历筛选岗位，继续研究公司与职位。

[下载安装](https://github.com/russeell/jobfindsme/releases/latest) · [支持的来源](#支持的来源) · [开始使用](#开始使用) · [English](README.en.md)

[![MIT License](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Release](https://img.shields.io/github/v/release/russeell/jobfindsme)](https://github.com/russeell/jobfindsme/releases)

</div>

![JobFindsMe：岗位列表、职位详情与招聘原页并排查看](docs/images/jobfindsme-search.png)

*界面示例使用隔离测试数据。*

## 用它做什么

- **集中找岗位。** 输入岗位、技能或方向，选择来源与城市，在同一处查看结果，不用来回切换网站。
- **带着简历找。** 导入并确认简历，让经历参与检索和匹配；也可以不上传简历，直接搜索。
- **边看岗位，边看原文。** 职位详情与招聘原页并排显示，薪资、职责和要求回到原页面核对。
- **聊清楚一家公司。** 输入公司名、岗位链接或具体问题，研究助手检索公开资料、读取原文，把回答和引用放在一起。
- **留住看过的机会。** 收藏岗位、记录已读和投递状态，重开历史对话，继续之前的研究。

## 支持的来源

目前提供 **20 个岗位检索来源：4 个招聘平台和 16 家公司招聘官网**。

| 招聘平台 | 使用方式 |
| --- | --- |
| BOSS直聘 | 在应用内登录并完成来源检查后检索 |
| 猎聘 | 可尝试公开岗位检索，无需预先登录 |
| 智联招聘 | 在应用内登录并完成来源检查后检索 |
| 前程无忧 | 在应用内登录并完成来源检查后检索 |

| 公司招聘官网 | | | |
| --- | --- | --- | --- |
| 腾讯 | 字节跳动 | 阿里巴巴 | 美团 |
| 百度 | 京东 | 网易 | 快手 |
| 小米 | 滴滴 | 拼多多 | DeepSeek |
| MiniMax | 智谱 | 月之暗面 | 阶跃星辰 |

来源是否能返回岗位、读取完整 JD 或继续翻页，以「设置 → 岗位来源」的检查结果为准。登录失效、验证码、限流和网站改版可能影响检索；这份列表不代表所有来源随时可用，也不代表能获取全部在招岗位。

## 安装

从 **[GitHub Releases](https://github.com/russeell/jobfindsme/releases/latest)** 下载桌面安装包。

| 系统 | 当前安装包 |
| --- | --- |
| macOS · Apple Silicon（M 系列） | 下载 `mac-arm64.zip`，解压后将 `JobFindsMe.app` 放入「应用程序」 |
| macOS · Intel / Windows / Linux | 暂未提供安装包 |

当前 macOS 包尚未签名、公证，首次打开可能被系统拦截，请按「系统设置 → 隐私与安全性」提示处理。发布页提供 SHA-256 校验文件。后续可在应用的「设置 → 版本更新」检查新版本并前往下载；暂不自动安装。

如果你用过隔离测试版，原有数据仍留在原测试目录，不会自动合并到正式版。

## 开始使用

1. **选来源。** 打开「设置 → 岗位来源」，按需登录并检查，再勾选要检索的平台或公司。
2. **找岗位。** 回到「找工作」，输入如 `Python 后端`、`Agent 开发`，设置城市等筛选条件。想用简历匹配，可先通过简历按钮导入并确认内容。
3. **看详情。** 打开感兴趣的岗位，核对 JD 和招聘原页，收藏值得继续了解的机会。
4. **做研究。** 在「设置 → 模型设置」配置模型，再进入「岗位研究」提问，或从岗位详情带入研究对象。

可以这样问：

> 帮我了解腾讯的经营与公开披露情况。
>
> 这个岗位主要要求哪些能力？结合 JD 说明。
>
> 刚才的结论有哪些原文支持？还有哪些信息没有查到？

![JobFindsMe：研究报告与来源引用](docs/images/jobfindsme-research.jpg)

*合成报告示例。实际回答取决于可读取的来源与所选模型；没有证据的部分会说明未知。*

## 数据与模型

岗位、简历、对话和报告保存在本机，模型密钥使用系统安全存储。聊天和研究使用你配置的模型服务，相关输入会发送给该服务，并可能产生费用；本地保存不等于全程离线。网页检索也需要联网，请勿把隐私信息写进公开检索问题。

支持导入 PDF、DOCX、Markdown 和 TXT 简历，扫描 PDF 暂不支持 OCR。应用不会自动投递，定时检索目前停用。研究报告保留来源与引用，帮助你核对信息；来源可能过时，引用也不等于结论一定正确。

## 从源码运行

需要 Python 3.11+、Node.js/npm 和 Git。当前桌面开发流程以 macOS 为主。

```bash
git clone https://github.com/russeell/jobfindsme.git
cd jobfindsme
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev,browser]"
cd apps/desktop
npm ci
npm run build
npm start
```

默认使用仓库内的 `.venv/bin/python`，其他解释器可通过 `JFM_PYTHON` 指定。

## 参与开发

项目使用 Electron、React、TypeScript、Python 和 SQLite，研究对话基于 Pi Agent。欢迎通过 [Issues](https://github.com/russeell/jobfindsme/issues) 反馈问题或提交改进；反馈来源异常时，请附上来源名称、操作步骤和错误提示，不要上传密钥、Cookie 或个人简历。

[贡献指南](CONTRIBUTING.md) · [项目结构](docs/desktop/STRUCTURE.md) · [开发说明](docs/desktop/README.md) · [当前进度](docs/desktop/HANDOFF.md) · [安全说明](SECURITY.md)

## 许可证

[MIT](LICENSE) · Copyright © 2026 Russell。第三方依赖保留各自许可证。
