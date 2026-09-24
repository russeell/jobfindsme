# JobFindsMe

**Find a promising job. Then find out whether it is right for you.**

JobFindsMe is a local-first desktop workspace for job search and role research. Search for openings, read the original hiring page alongside the result, and investigate the company and role with traceable public evidence. You make the decision.

[中文](README.md) · [Get started](#get-started) · [Current status](docs/desktop/HANDOFF.md)

![JobFindsMe search: results and details on the left, original hiring website on the right](docs/images/jobfindsme-search.png)

*Desktop interface in an isolated QA profile. Listings, counts and source availability shown here may have changed.*

## From an opening to an informed choice

1. **Find jobs.** Enter a role or skill. With a confirmed resume, you may also search with an empty input and let your experience suggest a bounded set of terms. Filter city, experience and sources on the results page.
2. **Read the original.** Results, details and the hiring website sit side by side. Missing descriptions, salaries and publication dates are marked unknown; retrieval time is never passed off as publication time.
3. **Research the role.** Check company business and listing information, positive and negative accounts, workload, benefits, role content and development clues. Reports link to evidence and show dates and scope. What cannot be verified remains unknown.

Save interesting roles and keep read and application states separate. Applications happen on the hiring website; opening a page does not mark a job as applied.

### What does role research look like?

Start from a selected job, with or without a question. Reports organize company and role findings; follow-ups save new versions while earlier reports remain available. Official disclosures and personal accounts are kept distinct.

![JobFindsMe role research report with sectioned company findings and linked evidence](docs/images/jobfindsme-research.jpg)

*Report for a synthetic company in an isolated QA profile. Missing evidence does not become an invented conclusion.*

## Get started

This is currently a **macOS development build from source**, not a general-audience installer. Install Git, Python 3.11+ and Node.js/npm:

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

On first launch:

- Choose sources under **Settings → Job sources**, sign in through the app browser where needed, and check each source's status.
- Search with a keyword. A resume is optional; the small button beside the **Find jobs** title opens PDF, DOCX, Markdown and TXT import and review. Scanned PDFs do not yet support OCR.
- Open a promising result, read the original page, then choose **Research role**.

The desktop uses the repository's `.venv/bin/python` by default. Set `JFM_PYTHON` to select another interpreter.

## Important limits

- The catalog contains **four hiring platforms and sixteen company career sites**. A site opening in the browser does not mean automated search works. Login, listing, pagination and full-description capabilities are checked separately. Verification prompts, rate limits and website changes can interrupt retrieval; consult the app's source status.
- **Scheduled search is disabled.** Historical plans and runs remain on your device. The app never submits applications automatically.
- Jobs, resumes and reports are stored locally, while hiring sites and public evidence require network access. A free-form question may become a public search term; do not enter private information. Ordinary search and research do not automatically call a paid model.
- Public accounts can be old, incomplete or contradictory. Reports help you check evidence; they do not score companies or promise career outcomes.

See the [development handoff](docs/desktop/HANDOFF.md) for known gaps.

## Development and contributions

The desktop uses Electron, React and TypeScript; local services and storage use Python and SQLite. Main code lives in `apps/desktop/` and `src/jobfindsme/`, with tests in `apps/desktop/tests/` and `tests/`.

[Directory map](docs/desktop/STRUCTURE.md) · [Development notes](docs/desktop/README.md) · [Contributing](CONTRIBUTING.md) · [Security](SECURITY.md)

Older CLI/MCP entry points remain for compatibility; see the [legacy documentation](docs/legacy/README.en.md). They are not needed for desktop use.

## License

The current version uses [PolyForm Noncommercial 1.0.0](LICENSE): learning, personal use and other noncommercial uses are allowed under its terms, as are noncommercial modification and distribution. **Commercial use of this version requires separate permission.** This is a source-available noncommercial license, not an OSI-approved open-source license. Third-party dependencies retain their own licenses.

Earlier versions were published under [MIT](LICENSE-MIT-PRIOR). Rights already granted for those versions are not retroactively withdrawn. Contact the maintainers about licensing or commercial permission.
