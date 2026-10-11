"""Offline release gate for the frozen job-search HTTP runtime."""

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread

import certifi

from jobfindsme.connectors.pure_http import _default_session_factory


def check_runtime() -> dict:
    if not Path(certifi.where()).is_file():
        raise RuntimeError("runtime_check: bundled CA certificates missing")

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            body = b'{"runtime":"ready"}'
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *_args):
            pass

    with ThreadingHTTPServer(("127.0.0.1", 0), Handler) as server:
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        session = None
        try:
            session = _default_session_factory()
            # This test endpoint must not traverse a user's proxy.
            session.trust_env = False
            response = session.get(f"http://127.0.0.1:{server.server_port}/", timeout=5)
            if response.status_code != 200 or response.json() != {"runtime": "ready"}:
                raise RuntimeError("runtime_check: HTTP transport failed")
            return {"curl_http": "ok", "ca_bundle": "ok"}
        finally:
            if session is not None:
                session.close()
            server.shutdown()
            thread.join(timeout=5)
