# JobFindsMe

A local desktop workspace for finding jobs and researching company and role reputation, with resume maintenance and an embedded browser. Electron/React provides the interface; Python provides the local API, search, matching and storage.

[中文说明](README.md)

## Features

- **Job search**: select platforms and company career sites, search using keywords and a confirmed resume, filter results, and track read, saved and application status. Bulk source checks distinguish login from extraction capability.
- **Reputation research**: choose company feedback, role information, or both. Reports cover public feedback, responsibilities, workload, leave and benefits, with source links and explicit evidence gaps. Saved reports can be revisited and historical reports deleted.
- **Resume maintenance**: import PDF, DOCX, Markdown or TXT; review content, maintain versions, preview and export. Current and referenced versions are protected from deletion.
- **Embedded browser**: retain app-specific login sessions and open original pages when automated collection is unavailable. Applications are submitted manually.

## Status and limitations

This is a local macOS development build, not a fully verified release. The catalog includes four hiring platforms and sixteen company career sites; registration or successful login does not establish working search, pagination and full job descriptions.

Zhilian's authenticated extraction still needs verification, and Alibaba detail resources have known access issues. Platforms may require reauthentication or verification; browser fallback does not guarantee extraction. See the [handoff](docs/desktop/HANDOFF.md) and [task records](docs/desktop/tasks.json).

PDF import extracts text; scanned PDFs have no OCR support yet. Convert old DOC files to DOCX. The interface focuses on resume maintenance rather than conversational or JD-specific rewriting. Scheduled searches require the app to remain running and do not wake a sleeping or powered-off machine.

Research presents attributed public statements, not verified company-wide facts, ratings or recommendations. Experiences may differ by team, role and date; consult the original sources.

## Run locally

Requires Python 3.11+ and Node.js/npm. From the repository root:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev,browser]"
cd apps/desktop
npm ci
npm run build
npm start
```

The desktop app defaults to `.venv/bin/python`; set `JFM_PYTHON` to use another interpreter. Normal startup uses existing application data. Use an isolated preview package for testing.

See the [Chinese README](README.md) for test and packaging commands, the [directory map](docs/desktop/STRUCTURE.md) for module ownership, and the [technical documentation](docs/desktop/TECHNICAL.md) for architecture.

## Compatibility

The Python distribution is still named `agent-job-search`. Existing CLI/MCP entrypoints and resources remain for compatibility and are not required to launch the desktop app. Plugin marketplace manifests have been retired. [Legacy documentation](docs/legacy/README.en.md) describes those compatibility interfaces.

[Contributing](CONTRIBUTING.md) · [Security](SECURITY.md) · [MIT License](LICENSE)
