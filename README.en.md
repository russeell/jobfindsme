<div align="center">

# JobFindsMe

**Spend less time switching job sites. Get to know your next opportunity.**

Search **4 recruiting platforms + 16 company career sites**, find roles with your resume, and research companies in one desktop app.

[Download](https://github.com/russeell/jobfindsme/releases/latest) · [Sources](#supported-sources) · [Get started](#get-started) · [简体中文](README.md)

[![MIT License](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Release](https://img.shields.io/github/v/release/russeell/jobfindsme)](https://github.com/russeell/jobfindsme/releases)

</div>

![Job results, details and original listings side by side](docs/images/jobfindsme-search.png)

*Interface example with isolated test data.*

## What you can do

- **Search in one place.** Choose sources, enter a role or skill, and filter by city without switching between websites.
- **Use your resume.** Import and confirm your experience to inform searches and matching, or search without a resume.
- **Read the original listing.** Keep the job description and recruiting page side by side to check responsibilities, requirements and pay.
- **Research a company.** Ask a question or provide a job link. The assistant reads public material and brings answers and citations together.
- **Keep your progress.** Save jobs, track read and application status, and reopen previous research conversations.

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
| macOS · Intel / Windows / Linux | No installers available yet |

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

![Research report with source references](docs/images/jobfindsme-research.jpg)

*Synthetic report example. Actual answers depend on readable sources and your chosen model; unsupported information is marked as unknown.*

## Data and models

Jobs, resumes, conversations and reports are stored locally. Model keys use system secure storage. Chat and research send relevant input to the model service you configure, which may charge for requests. Local storage does not mean offline processing. Web searches also require internet access; avoid putting private information in public search questions.

Resume import supports PDF, DOCX, Markdown and TXT. Scanned PDFs do not have OCR support yet. The app does not submit applications automatically, and scheduled searches are currently disabled. Research keeps references for you to inspect; sources can be outdated, and a citation alone does not establish that a conclusion is correct.

## Run from source

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

## Contribute

Built with Electron, React, TypeScript, Python and SQLite, with Pi Agent powering research conversations. Report issues or suggest improvements through [Issues](https://github.com/russeell/jobfindsme/issues). For source failures, include the source name, steps and error message; leave out keys, cookies and personal resumes.

[Contributing](CONTRIBUTING.md) · [Project structure](docs/desktop/STRUCTURE.md) · [Development](docs/desktop/README.md) · [Current status](docs/desktop/HANDOFF.md) · [Security](SECURITY.md)

## License

[MIT](LICENSE) · Copyright © 2026 Russell. Third-party dependencies retain their own licenses.
