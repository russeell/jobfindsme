<p align="center">
  <img src="docs/images/logo.svg" width="64" height="64" alt="JobFindsMe logo">
</p>
<h1 align="center">JobFindsMe</h1>
<p align="center"><strong>Search across job boards. Connect your resume, interviews and applications.</strong><br>Open-source AI job-search desktop assistant · macOS / Windows · Local data storage</p>
<p align="center">
  <a href="https://github.com/russeell/jobfindsme/releases/latest/download/mac-arm64.zip"><strong>Download for macOS (Apple Silicon)</strong></a> ·
  <a href="https://github.com/russeell/jobfindsme/releases/latest/download/windows-x64.zip"><strong>Download for Windows (x64)</strong></a> ·
  <a href="https://github.com/russeell/jobfindsme/issues">Report an issue</a>
</p>
<p align="center"><a href="README.md">中文</a> · <strong>English</strong></p>

Spend your time evaluating opportunities and preparing for interviews. JobFindsMe brings job boards, resumes and preparation materials into one workspace: **choose a role, then keep using its JD and your linked resume, with less searching, copying and repeating yourself.**

**Start searching without a resume or model configuration.** Connect your own model service when you want AI tailoring, interview practice or research. The supported job boards primarily serve China-based jobs.

## What you can do

| Your goal | How JobFindsMe helps |
| --- | --- |
| **Find relevant roles** | Search four platforms together. Filter by city, salary, experience and job type. Use your saved resume for local matching, with matches, gaps and unknowns. |
| **Check the original listing** | Fetch the JD when you select a job; inspect its original page in the built-in browser. Sign-in, verification and preparation share one window. |
| **Prepare a tailored resume** | Keep your original file, edit a copy, review AI suggestions against the JD, and save a separate version. |
| **Practice this interview** | Reuse the job and resume for questions, feedback and follow-ups. Save weak points for review; start without a JD too. |
| **Research the company** | Investigate roles, companies and industries through original sources, citations and explicit evidence gaps. |
| **Prepare and follow up** | Reuse your resume, edit or polish an opening message, copy it and open the listing. Record materials used, application outcomes and next steps. |

## Four platforms, one search

Search **BOSS Zhipin, Liepin, Zhaopin and 51job** together. Results arrive incrementally, with the list and job details available in the same workspace.

- **Your conditions**: city, salary, experience and unrestricted / full-time / part-time work. Experience options include students and recent graduates.
- **Resume reuse**: matching information is extracted in the background for recommendations and ranking. Your original file is retained; private contact details stay out of search keywords.
- **Details on demand**: read the JD when you choose a role, reuse saved details, and continue searching for subsequent results.
- **Visible source status**: sign-in, verification, connection failures and partial coverage are reported separately. Results already retrieved remain available if another source fails.

![Four platforms searched together, with a job list and JD](docs/images/jobfindsme-four-platforms.jpg)

<sub>Actual app screenshot from an earlier version. Availability varies with accounts, verification and website changes; it does not imply that all four platforms are always available.</sub>

## The original page, right beside your work

The built-in browser supports **tabs, web search, bookmarks and split view**. Keep job details and preparation materials on the left, and the recruitment page on the right. Sign in, handle verification and inspect original sources inside the app.

![Job details alongside the original recruitment page](docs/images/jobfindsme-browser.jpg)

<sub>Actual app screenshot. Opening a page and automatically extracting listings, subsequent pages or a full JD are separate capabilities. Status reflects actual extraction results.</sub>

## One resume, different opportunities

My Resume is the central place to maintain and improve your resume. Import **PDF / DOCX**, view the original, and let matching information be extracted in the background. Open an editable copy when you want to make changes. MD / TXT text imports are also supported. Readable text colors, sizes and styles carry into the copy; the original file stays unchanged.

- **Focus on writing**: grouped controls for undo, bold, font size, color, alignment and lists. Clear selected formatting and restore it with one undo. Focus mode gives the document more space; `Esc` returns.
- **Resume interrupted work**: unsaved drafts stay on your computer and recover after restarting. Save with `⌘S / Ctrl+S` and keep typing; page preview and Word / PDF exports use your saved edits.
- **AI beside your document**: a collapsible resume assistant helps with selected text or the whole resume, reusing the JD and your experience. Unchanged selected-text suggestions leave the original in place; changes to numbers, dates and some explicit facts are blocked, but your review is still needed. An outdated suggestion cannot overwrite text you have since edited. Keep your base resume and job-specific drafts separately.
- **Layouts for different stages**: professional, graduate and compact layouts change section order and density. Each version saves its layout, which carries into page previews and Word / PDF exports.
- **Reuse with each job**: the linked resume continues into interview preparation and application materials. Older materials retain their chosen version and layout; archived originals can still be exported unchanged.

![My Resume: text colors, font sizes, paragraph alignment and direct editing](docs/images/jobfindsme-resume-editor.png)

<sub>Actual editor (v0.15.2), using a fictional resume. Shows imported styles, editing and saving; no user data is included.</sub>

## Continue into interviews and research

Start from a job to bring its saved JD, linked resume and existing materials into preparation. Open the Assistant directly for independent practice or research.

<table>
  <tr><th width="33%">Resume tailoring</th><th width="33%">Interview practice</th><th width="33%">Deep research</th></tr>
  <tr>
    <td><a href="docs/images/jobfindsme-resume.png"><img src="docs/images/jobfindsme-resume.png" alt="Review AI resume changes against the original text"></a></td>
    <td><a href="docs/images/jobfindsme-interview.png"><img src="docs/images/jobfindsme-interview.png" alt="Interview questions, feedback and follow-ups"></a></td>
    <td><a href="docs/images/jobfindsme-deep-research.png"><img src="docs/images/jobfindsme-deep-research.png" alt="Original sources, citations and evidence gaps"></a></td>
  </tr>
  <tr>
    <td>Retain real experience; review and save a job-specific draft.</td>
    <td>Practice for the role and revisit saved weak points.</td>
    <td>Check originals and distinguish supported findings from open questions.</td>
  </tr>
</table>

<sub>Click to enlarge. The resume image uses fictional data and a local mock response to demonstrate review. Interview and research images are from earlier versions. Screenshots are not a guarantee of model quality.</sub>

The Assistant also supports **separate conversations, pin icons, history search, archiving and branches**. Continue each company or topic separately, and attach relevant materials to the conversation.

## Save, prepare, apply and follow up

Job Management brings **all, saved and applied jobs** together. Arrange your next step directly in the list, with quick dates for today, tomorrow or three days later. Due tasks appear together and can be rescheduled, completed or restored with undo.

Choose a resume and an opening message before applying; reopen the job to restore your saved materials. Save reusable message templates with company and role placeholders. AI polishing can use the current JD and the explicitly selected, redacted experience; edit the result directly or undo it. **Copy the message and open the job**, then confirm and send on the recruitment platform yourself.

Record the outcome to see which resume and message you used, for which company and when. Applied jobs lead to their application records. Opening a page is recorded as opening it, **never as a successful application**. The app supports assisted preparation, without bulk applications.

**Single-job BOSS applications are experimental**: restore your chosen resume and message, review the specific job, account and actual attachment, then confirm execution once. Message and attachment results are checked separately; duplicate clicks are coalesced and reservations survive restarts. Verification, rate limits or uncertain results stop execution without automatic retries. Confirmation, stopping and restart recovery passed in an isolated macOS window, and the read-only preview passed on a real BOSS page. Actual uploads, delivery and platform receipts have not completed live acceptance. Prefer assisted applications; a successful preview does not prove that a message or resume was sent.

## Get started in three steps

1. **Download**: [macOS (Apple Silicon)](https://github.com/russeell/jobfindsme/releases/latest/download/mac-arm64.zip) · [Windows (x64)](https://github.com/russeell/jobfindsme/releases/latest/download/windows-x64.zip). Fully extract and open `JobFindsMe.app` or `JobFindsMe.exe`. No separate Python / Node.js installation required.
2. **Find a role first**: enter a direction, choose a city and platforms, and sign in or complete verification when prompted. Import your resume whenever you are ready.
3. **Prepare with AI**: connect your own model in Settings. Resume changes stay in My Resume; start interview preparation or research from a job or the Assistant.

This README describes current source functionality. Downloaded builds follow their [release notes](https://github.com/russeell/jobfindsme/releases/latest). Packages are unsigned / unnotarized; first-launch instructions, exact source commits and SHA256 checksums are provided on the release page.

<details>
<summary><strong>Before you start</strong></summary>

- **Local data and models**: resumes, conversations and records are stored locally. AI features send the required materials to your selected model service, which may charge for requests. Resume analysis and matching use a redacted copy, without replacing the original file.
- **Resume formatting**: original preview and download retain the file. Editable copies preserve supported text styles and reflow the document; complex columns, decorative graphics and original fonts are not guaranteed. Scanned PDFs do not yet have OCR support.
- **Platforms and results**: sign-in, verification, networking and website changes can affect extraction. Verify availability, salary and AI output against original sources.
- **You confirm sending**: opening a listing does not mark it as applied. There is no default unattended bulk application workflow.

</details>

**Disclaimer: This project is intended for learning and personal use only. Follow each platform's usage rules and independently verify job information and AI-generated output.**

For bugs, open an [issue](https://github.com/russeell/jobfindsme/issues) with the app version, platform, reproduction steps and a redacted screenshot.

[Development](docs/desktop/README.md) · [Contributing](CONTRIBUTING.md) · [Security](SECURITY.md) · [MIT license](LICENSE)
