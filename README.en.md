<p align="center">
  <img src="docs/images/logo.svg" width="80" height="80" alt="JobFindsMe logo">
</p>
<h1 align="center">JobFindsMe</h1>
<p align="center"><strong>Your job search, in one workspace.</strong></p>
<p align="center">Search 4 recruiting platforms and 16 company career sites. Bring your resume. Keep the evidence.</p>

<p align="center">
  <a href="https://github.com/russeell/jobfindsme/releases/latest"><img src="https://img.shields.io/github/v/release/russeell/jobfindsme?style=flat-square&color=27272a" alt="Latest release"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-27272a?style=flat-square" alt="MIT license"></a>
  <img src="https://img.shields.io/badge/macOS-Apple_Silicon-27272a?style=flat-square" alt="macOS Apple Silicon">
</p>

<div align="center">

[Download for macOS](https://github.com/russeell/jobfindsme/releases/latest) · [Sources](#supported-sources) · [Get started](#get-started) · [简体中文](README.md)

</div>

<br>

<p align="center">
  <img src="docs/images/jobfindsme-search.png" width="100%" alt="JobFindsMe — job search and details">
</p>
<p align="center"><sub>Actual interface in an isolated build. Results and source availability reflect that session.</sub></p>

## From finding a role to understanding it

<table>
<tr>
<td width="33%" valign="top"><h3>01 · Find</h3><p>Search by role, skill and city across recruiting platforms and company sites. Optionally use your confirmed resume to inform matching.</p></td>
<td width="33%" valign="top"><h3>02 · Understand</h3><p>Read the original listing, ask about the company and follow research citations. Missing information stays unknown.</p></td>
<td width="33%" valign="top"><h3>03 · Keep</h3><p>Save interesting roles, track read and application status, and return to earlier conversations without starting over.</p></td>
</tr>
</table>

## Supported sources

The app includes **20 job search sources: 4 recruiting platforms and 16 company career sites**.

| Platform | Access |
| --- | --- |
| BOSS Zhipin | Sign in within the app and check the source before searching |
| Liepin | Public listing search can be attempted without signing in |
| Zhaopin | Sign in within the app and check the source before searching |
| 51job | Sign in within the app and check the source before searching |

| Company career sites | | | |
| --- | --- | --- | --- |
| Tencent | ByteDance | Alibaba | Meituan |
| Baidu | JD.com | NetEase | Kuaishou |
| Xiaomi | DiDi | Pinduoduo | DeepSeek |
| MiniMax | Zhipu | Moonshot AI | StepFun |

Check **Settings → Job sources** for current access, listing, full-description and pagination status. Expired sessions, verification challenges, rate limits and website changes can interrupt searches. Inclusion here does not guarantee continuous access or complete coverage of current openings.

## Install

Download the desktop app from **[GitHub Releases](https://github.com/russeell/jobfindsme/releases/latest)**.

| System | Available package |
| --- | --- |
| macOS · Apple Silicon | Download `mac-arm64.zip`, unzip it and move `JobFindsMe.app` to Applications |
| Windows · x64 | Download `windows-x64.zip`, extract the entire folder, then run `JobFindsMe.exe`. Python and Node.js are bundled. |
| macOS · Intel / Windows ARM / Linux | No packages available yet |

The macOS package is not Developer ID signed or notarized. On first launch, macOS may block it; follow the prompts in **System Settings → Privacy & Security**. Releases include SHA-256 checksums. **Settings → Version updates** checks for releases and opens the download page; installation is not automatic.

Data from earlier isolated test builds remains in its original directory and is not automatically merged into the regular app.

## Get started

1. **Choose sources.** Open **Settings → Job sources**, sign in where required, check access and select the sources you want to search.
2. **Find roles.** Enter a keyword such as `Python 后端` or `Agent 开发`, then set city and other filters. Use the resume button to import and confirm your resume if you want it to inform matching.
3. **Read the details.** Open a role, compare its description with the original listing and save opportunities you want to explore.
4. **Research.** Configure a model in **Settings → Model settings**, then ask in **Job research** or start from a job's details.

Try questions such as:

> What do Tencent's public disclosures say about its business?
>
> Which skills does this role require? Explain using its job description.
>
> Which sources support the previous answer, and what is still unknown?

<p align="center">
  <img src="docs/images/jobfindsme-research.png" width="100%" alt="JobFindsMe — research conversation">
</p>
<p align="center"><sub>Start a conversation with a company, a question or a job link. Select a model before sending.</sub></p>

## Data and models

Jobs, resumes, conversations and reports are stored locally. Model keys use system secure storage. Chat and research send relevant input to the model service you configure, which may charge for requests. Local storage does not mean offline processing. Web searches also require internet access; avoid putting private information in public search questions.

Resume import supports PDF, DOCX, Markdown and TXT. Scanned PDFs do not have OCR support yet. The app does not submit applications automatically, and scheduled searches are currently disabled. Research keeps references for you to inspect; sources can be outdated, and a citation alone does not establish that a conclusion is correct.

<details>
<summary><strong>Developers · Run from source</strong></summary>

Requires Python 3.11+, Node.js/npm and Git. The current desktop development workflow primarily targets macOS.

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

The app uses `.venv/bin/python` by default. Set `JFM_PYTHON` to use another interpreter.

</details>

## Contribute

Built with Electron, React, TypeScript, Python and SQLite, with Pi Agent powering research conversations. Report issues or suggest improvements through [Issues](https://github.com/russeell/jobfindsme/issues). For source failures, include the source name, steps and error message; leave out keys, cookies and personal resumes.

[Contributing](CONTRIBUTING.md) · [Project structure](docs/desktop/STRUCTURE.md) · [Development](docs/desktop/README.md) · [Current status](docs/desktop/HANDOFF.md) · [Security](SECURITY.md)

## License

[MIT](LICENSE) · Copyright © 2026 Russell. Third-party dependencies retain their own licenses.
