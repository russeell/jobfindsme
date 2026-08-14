from __future__ import annotations

import json
import os
import sys

from jobfindsme.cli import run
from jobfindsme.installer import detect_host


def touch(path, mtime) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{}", encoding="utf-8")
    os.utime(path, (mtime, mtime))


def test_detect_host_uses_env_signal(monkeypatch) -> None:
    monkeypatch.setenv("CLAUDE_CODE_ENTRYPOINT", "/usr/local/bin/claude")
    assert detect_host("/nonexistent/home") == ("claude", ["claude"])


def test_detect_host_uses_config_file(tmp_path) -> None:
    touch(tmp_path / ".codex" / "config.toml", 1000)
    assert detect_host(tmp_path) == ("codex", ["codex"])


def test_detect_host_prefers_most_recent_config(tmp_path) -> None:
    touch(tmp_path / ".codex" / "config.toml", 1000)
    touch(tmp_path / ".cursor" / "mcp.json", 2000)
    host, candidates = detect_host(tmp_path)
    assert host == "cursor"
    assert candidates == ["codex", "cursor"]


def test_detect_host_returns_none_without_evidence(tmp_path) -> None:
    assert detect_host(tmp_path) == (None, [])


def test_bare_connect_detects_env_and_writes_config(
    tmp_path, capsys, monkeypatch
) -> None:
    monkeypatch.setenv("CLAUDE_CODE_ENTRYPOINT", "/usr/local/bin/claude")
    assert run(["connect", "--home", str(tmp_path)]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["host"] == "claude"
    assert result["action"] == "connect"
    assert (tmp_path / ".claude.json").exists()
    assert (tmp_path / ".claude" / "skills" / "jobfindsme" / "SKILL.md").exists()


def test_bare_connect_detects_config_and_writes_it(tmp_path, capsys) -> None:
    touch(tmp_path / ".codex" / "config.toml", 1000)
    assert run(["connect", "--home", str(tmp_path)]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["host"] == "codex"
    assert (tmp_path / ".codex" / "config.toml").exists()


def test_bare_connect_without_evidence_fails_cleanly(
    tmp_path, capsys, monkeypatch
) -> None:
    monkeypatch.delenv("CLAUDE_CODE_ENTRYPOINT", raising=False)
    monkeypatch.delenv("CURSOR_TRACE_ID", raising=False)
    assert run(["connect", "--home", str(tmp_path)]) == 1
    result = json.loads(capsys.readouterr().out)
    assert result["ok"] is False
    assert "未检测到当前 Agent" in result["error"]
    assert "connect <codex|claude|cursor|zcode>" in result["hint"]


def test_bare_connect_prompt_accepts_numbered_choice(
    tmp_path, capsys, monkeypatch
) -> None:
    monkeypatch.delenv("CLAUDE_CODE_ENTRYPOINT", raising=False)
    monkeypatch.delenv("CURSOR_TRACE_ID", raising=False)
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr("builtins.input", lambda _prompt: "3")
    assert run(["connect", "--home", str(tmp_path)]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["host"] == "cursor"
    assert (tmp_path / ".cursor" / "mcp.json").exists()
