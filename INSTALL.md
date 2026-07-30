# Install jobfindsme

This file is an installation recipe for coding agents. Complete only the steps
below. Do not clone the repository, inspect the source, run the test suite,
install development dependencies, or download a separate browser.

## 1. Check Python

```bash
python3 --version
```

Python 3.11 or newer is required. If it is unavailable, stop and tell the user.

## 2. Install

Create a dedicated runtime and install the prebuilt release package. The mirror
keeps dependency downloads fast on networks where the default Python index is
slow.

```bash
python3 -m venv ~/.jobfindsme/runtime
~/.jobfindsme/runtime/bin/python -m pip install \
  --index-url https://pypi.tuna.tsinghua.edu.cn/simple \
  --timeout 20 --retries 1 --upgrade \
  "jobfindsme[browser] @ https://github.com/russeell/jobfindsme/releases/download/v0.2.1/jobfindsme-0.2.1-py3-none-any.whl"
```

Do not replace this command with `git clone`, an editable install, or
`playwright install`.

## 3. Connect the current agent

Use the name of the Agent that is reading this file:

```bash
~/.jobfindsme/runtime/bin/python -m jobfindsme connect workbuddy
```

Replace `workbuddy` with `codex`, `claude`, `qwen`, `zcode`, `kimi`, `trae`,
`trae-cn`, or `qoder` when appropriate. The runtime is identical for every
Agent; only the MCP configuration path changes. `connect` is safe to run again.

For an unknown MCP client:

```bash
~/.jobfindsme/runtime/bin/python -m jobfindsme config
```

## 4. Verify

```bash
~/.jobfindsme/runtime/bin/python -m jobfindsme --version
~/.jobfindsme/runtime/bin/python -m jobfindsme doctor
```

The browser and BOSS login checks may be marked optional until the user runs
`jobfindsme setup`. They do not make installation fail.

Restart the agent after configuration. Installation should normally finish
within three minutes. If one command runs for more than five minutes, stop it
and report the command and its latest output instead of trying unrelated fixes.
