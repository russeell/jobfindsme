from __future__ import annotations

import argparse
import os
from pathlib import Path

import uvicorn

from jobfindsme.desktop_api import create_app


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="JobFindsMe desktop loopback API")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--database", type=Path, required=True)
    return parser


def main() -> int:
    args = _parser().parse_args()
    if args.host not in {"127.0.0.1", "::1", "localhost"}:
        raise SystemExit("desktop API must bind to a loopback host")
    token = os.environ.get("JFM_DESKTOP_TOKEN", "")
    if not token:
        raise SystemExit("JFM_DESKTOP_TOKEN is required")
    uvicorn.run(
        create_app(token=token, database_path=args.database),
        host=args.host,
        port=args.port,
        access_log=False,
        log_level="warning",
        loop="asyncio",
        http="h11",
        ws="none",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
