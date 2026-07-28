# Install JobFindsMe

An AI agent reading this file should execute the following steps to install
JobFindsMe for the current user.

## Steps

1. **Install the package:**

```bash
python3 -m pip install \
  "jobfindsme @ git+https://github.com/russeell/jobfindsme.git@v0.2.0-rc.5"
```

2. **Run doctor to verify:**

```bash
jobfindsme doctor
```

3. **Install for the current agent host:**

Determine which agent host is in use and run ONE of:

```bash
jobfindsme install zcode     # ZCode
jobfindsme install codex     # Codex
jobfindsme install claude    # Claude Code
jobfindsme install qwen      # Qwen Code
jobfindsme install kimi      # Kimi Code
jobfindsme install trae      # TRAE (international)
jobfindsme install trae-cn   # TRAE CN
jobfindsme install qoder     # Qoder
jobfindsme install workbuddy # WorkBuddy
```

4. **Inform the user:**

Tell the user to restart their agent. After restart, they can say:

> "Use JobFindsMe to search for jobs."

## Notes

- `jobfindsme doctor` diagnoses: database, permissions, MCP connectivity,
  connector health, and secret storage.
- The installer backs up existing config files before modifying them.
- Supported agents: ZCode, Codex, Claude Code, Qwen Code, Kimi Code,
  TRAE, TRAE CN, Qoder, WorkBuddy.
