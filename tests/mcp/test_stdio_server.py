from __future__ import annotations

import io
import json

from jobfindsme.app import jobfindsmecore
from jobfindsme.importing import parse_json
from jobfindsme.mcp.registry import ToolRegistry
from jobfindsme.mcp.server import StdioMcpServer


def request(request_id: int, method: str, params=None) -> str:
    return json.dumps(
        {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": method,
            "params": params or {},
        }
    )


def test_stdio_protocol_initializes_lists_and_calls_tools(tmp_path) -> None:
    core = jobfindsmecore(tmp_path / "jobfindsme.db")
    workspace = core.create_workspace("MCP")
    input_stream = io.StringIO(
        "\n".join(
            [
                request(
                    1,
                    "initialize",
                    {
                        "protocolVersion": "2025-11-25",
                        "clientInfo": {"name": "test", "version": "1"},
                        "capabilities": {},
                    },
                ),
                json.dumps(
                    {
                        "jsonrpc": "2.0",
                        "method": "notifications/initialized",
                    }
                ),
                request(2, "tools/list"),
                request(
                    3,
                    "tools/call",
                    {
                        "name": "get_jobs",
                        "arguments": {"workspace_id": workspace.workspace_id},
                    },
                ),
            ]
        )
        + "\n"
    )
    output_stream = io.StringIO()

    StdioMcpServer(ToolRegistry(core)).run(input_stream, output_stream)

    responses = [json.loads(line) for line in output_stream.getvalue().splitlines()]
    assert [response["id"] for response in responses] == [1, 2, 3]
    assert responses[0]["result"]["protocolVersion"] == "2025-11-25"
    assert len(responses[1]["result"]["tools"]) == 5
    assert responses[2]["result"]["structuredContent"] == {
        "jobs": [],
        "count": 0,
        "offset": 0,
        "limit": 20,
        "next_offset": None,
    }
    assert isinstance(responses[2]["result"]["structuredContent"], dict)


def test_get_jobs_with_records_is_json_serializable(tmp_path) -> None:
    """Regression: get_jobs returning JobSummary objects used to crash
    json.dumps and kill the stdio server mid-session."""
    core = jobfindsmecore(tmp_path / "jobfindsme.db")
    workspace = core.create_workspace("MCP")
    core.job_imports.import_records(
        workspace.workspace_id,
        parse_json(
            json.dumps(
                [
                    {
                        "id": "job-1",
                        "title": "AI应用工程师",
                        "company": "示例科技",
                        "description": "Python RAG Agent 大模型 3-5年 25-40K",
                        "location": "上海",
                        "url": "https://example.com/jobs/1",
                    }
                ],
                ensure_ascii=False,
            ),
            source_name="测试来源",
        ),
    )
    input_stream = io.StringIO(
        "\n".join(
            [
                request(
                    1,
                    "initialize",
                    {
                        "protocolVersion": "2025-11-25",
                        "clientInfo": {"name": "test", "version": "1"},
                        "capabilities": {},
                    },
                ),
                json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}),
                request(
                    2,
                    "tools/call",
                    {
                        "name": "get_jobs",
                        "arguments": {"workspace_id": workspace.workspace_id},
                    },
                ),
            ]
        )
        + "\n"
    )
    output_stream = io.StringIO()

    StdioMcpServer(ToolRegistry(core)).run(input_stream, output_stream)

    lines = output_stream.getvalue().splitlines()
    assert len(lines) == 2, lines
    result = json.loads(lines[1])["result"]
    jobs = result["structuredContent"]["jobs"]
    assert result["structuredContent"]["count"] == 1
    assert jobs[0]["job_id"].startswith("job_")
    assert jobs[0]["title"] == "AI应用工程师"


def test_unknown_rpc_method_returns_json_rpc_error(tmp_path) -> None:
    server = StdioMcpServer(ToolRegistry(jobfindsmecore(tmp_path / "jobfindsme.db")))

    response = server.handle({"jsonrpc": "2.0", "id": 1, "method": "unsupported"})

    assert response["error"]["code"] == -32601


def test_initialize_instructions_carry_the_output_contract(tmp_path) -> None:
    """Spec-compliant clients inject server instructions into the context —
    the strongest default-skill guarantee. They must cover the contract."""
    core = jobfindsmecore(tmp_path / "jobfindsme.db")
    server = StdioMcpServer(ToolRegistry(core))

    response = server.handle(
        json.loads(
            request(
                1,
                "initialize",
                {
                    "protocolVersion": "2025-11-25",
                    "clientInfo": {"name": "test", "version": "1"},
                    "capabilities": {},
                },
            )
        )
    )

    instructions = response["result"]["instructions"]
    assert "five sections" in instructions
    assert "bare URL" in instructions
    assert "stored confirmed profile is loaded automatically" in instructions
    assert "include_seen=true" in instructions
    assert "never paste complete resumes" in instructions
    assert "never rebuild results as a table" in instructions
    assert "not duplicates" in instructions
    assert "Never invent a CLI fallback command" in instructions
