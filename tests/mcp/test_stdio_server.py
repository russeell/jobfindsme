from __future__ import annotations

import io
import json

from jobfindsme.core import jobfindsmecore
from jobfindsme.mcp.server import StdioMcpServer
from jobfindsme.mcp.tools import ToolRegistry


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
    assert len(responses[1]["result"]["tools"]) == 9
    assert responses[2]["result"]["structuredContent"] == {
        "jobs": [],
        "count": 0,
        "offset": 0,
        "limit": 20,
        "next_offset": None,
    }
    assert isinstance(responses[2]["result"]["structuredContent"], dict)


def test_unknown_rpc_method_returns_json_rpc_error(tmp_path) -> None:
    server = StdioMcpServer(ToolRegistry(jobfindsmecore(tmp_path / "jobfindsme.db")))

    response = server.handle({"jsonrpc": "2.0", "id": 1, "method": "unsupported"})

    assert response["error"]["code"] == -32601
