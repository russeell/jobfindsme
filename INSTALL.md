# Install jobfindsme

Run these two commands:

```bash
pip install "jobfindsme @ git+https://github.com/russeell/jobfindsme.git@v0.2.0-rc.5"
jobfindsme config
```

Then paste the JSON output into the user's MCP config file. Or use a shortcut:

```bash
jobfindsme install --path ~/.your-agent/mcp.json
```

For known agents, replace `--path` with the agent name: `claude`, `codex`, `zcode`, `kimi`, `trae`, `workbuddy`.

Finally, tell the user to restart their agent.
