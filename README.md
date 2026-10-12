<p align="center">
  <img src="docs/images/logo.svg" width="56" height="56" alt="JobFindsMe 标志">
</p>
<h1 align="center">JobFindsMe</h1>
<p align="center"><strong>找岗位、改简历、练面试，一个工作台。</strong><br>开源 AI 求职桌面助手 · macOS / Windows</p>
<p align="center">
  <strong>中文</strong> · <a href="README.en.md">English</a>
</p>

## 四个平台，一次搜索

一键检索 **BOSS直聘、猎聘、智联招聘、前程无忧**，结果陆续出现，不必逐个平台搜索。按城市、薪资、经验筛选，选中岗位后按需补全 JD。**搜索无需配置模型，也无需上传简历。**

![一次选择四个平台，在同一工作台查看岗位结果和 JD](docs/images/jobfindsme-four-platforms.jpg)

## 内嵌浏览器，原页就在旁边

在应用内完成登录、验证和原文核对。支持 **多标签、网页搜索、书签与分栏浏览**，少在窗口之间来回切换。

![左侧岗位详情，右侧内嵌浏览器打开对应招聘原页](docs/images/jobfindsme-browser.jpg)

<sub>实际应用截图。各平台可用性受登录、验证和网站变化影响；某一来源失败，已取得的结果仍可使用。</sub>

## 材料带上，接着准备

导入一次简历，岗位 JD、关联简历与面试准备持续复用，少重复粘贴。

<table>
  <tr>
    <th width="33%">修改简历</th><th width="33%">模拟面试</th><th width="33%">深度研究</th>
  </tr>
  <tr>
    <td><a href="docs/images/jobfindsme-resume.png"><img src="docs/images/jobfindsme-resume.png" alt="我的简历：AI 修改前后对照，逐项审阅后保存"></a></td>
    <td><a href="docs/images/jobfindsme-interview.png"><img src="docs/images/jobfindsme-interview.png" alt="无 JD 的模拟面试：逐题提问、点评和追问"></a></td>
    <td><a href="docs/images/jobfindsme-deep-research.png"><img src="docs/images/jobfindsme-deep-research.png" alt="深度研究：核实原文、引用来源并说明证据缺口"></a></td>
  </tr>
  <tr>
    <td>在「我的简历」对照 JD 修改，逐项审阅后保存，原稿保留。</td>
    <td>逐题练习、点评追问；没有 JD 也能开始。</td>
    <td>岗位、公司与行业背调，附来源和证据缺口。</td>
  </tr>
</table>

<sub>点击查看大图。简历图为新版实际界面与虚构资料，本机模拟输出仅演示审阅交互；面试与研究图来自早期版本。</sub>

- **我的简历**：保留 PDF / Word 原文件，后台提取匹配信息；编辑副本、AI 修改、社招 / 校招 / 紧凑模板，导出 Word 或 PDF。
- **岗位管理**：收藏、已投递集中查看；带入岗位简历，编辑或 AI 润色招呼语，复制并打开原页，记录使用的材料与投递结果。
- **求职助手**：实时查岗位、模拟面试、深度研究；支持多对话、搜索、归档与分支。

## 三步开始

1. **下载安装**：[macOS（M 系列）](https://github.com/russeell/jobfindsme/releases/latest/download/mac-arm64.zip) · [Windows（x64）](https://github.com/russeell/jobfindsme/releases/latest/download/windows-x64.zip)。解压后打开 `JobFindsMe.app` 或 `JobFindsMe.exe`，无需另装运行环境。
2. **搜索岗位**：输入关键词，选择一个城市或不限城市；勾选平台，按提示登录或验证。
3. **用 AI 准备**：在设置中配置自己的模型；简历修改去「我的简历」，面试和背调从岗位或「求职助手」开始。

安装包未签名，首次打开说明、版本对应的源码提交与 SHA256 校验信息见[发布页](https://github.com/russeell/jobfindsme/releases/latest)。

数据保存在本机；使用 AI 时，相关材料会发送给所选模型服务，可能产生费用。PDF 编辑副本会重新排版，不保证还原原版式。投递由你在平台确认发送，打开原页不算已投递。

**免责声明：本项目仅供学习和个人使用。请遵守相关平台的使用规则，岗位信息与 AI 输出请自行核实。**

[开发说明](docs/desktop/README.md) · [贡献与反馈](CONTRIBUTING.md) · [安全说明](SECURITY.md) · [MIT 许可证](LICENSE)
