"""Small same-origin local server; binds to loopback, never a public listener."""

from __future__ import annotations
from datetime import datetime, timezone
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit
import json
import logging
import threading
import time
import uuid

from .engine import AnalysisError, analyze, symbol_input
from .example import example_inputs
from .provider import fetch_inputs

ROOT = Path(__file__).resolve().parent.parent
log = logging.getLogger(__name__)


class LabServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address=("127.0.0.1", 8765), storage: Path | None = None):
        self.storage = storage or ROOT / ".local" / "snapshots"
        self.analyses: dict[str, dict] = {}
        self.cache: dict[str, tuple[float, dict]] = {}
        self.guard = threading.Lock()
        self.analysis_slots = threading.BoundedSemaphore(2)
        super().__init__(address, Handler)

    def remember(self, result: dict) -> dict:
        with self.guard:
            self.analyses[result["id"]] = result
            if len(self.analyses) > 100:
                self.analyses.pop(next(iter(self.analyses)))
        return result


class Handler(SimpleHTTPRequestHandler):
    server: LabServer

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT / "dist"), **kwargs)

    def log_message(self, fmt, *args):
        log.info(fmt, *args)

    def end_headers(self):
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; font-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'")
        super().end_headers()

    def json_response(self, body: dict | list, status: int = 200):
        data = json.dumps(body, allow_nan=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def local_request(self) -> bool:
        allowed_hosts = {"127.0.0.1", "localhost", "[::1]"}
        try:
            host = urlsplit("http://" + self.headers.get("Host", "")).hostname
            if host not in allowed_hosts:
                self.json_response({"error": "Only localhost requests are accepted."}, 403)
                return False
            origin = self.headers.get("Origin")
            if origin:
                parsed = urlsplit(origin)
                if parsed.scheme != "http" or parsed.hostname not in allowed_hosts or parsed.port not in {self.server.server_port, 5173}:
                    self.json_response({"error": "This request did not come from the local app."}, 403)
                    return False
        except ValueError:
            self.json_response({"error": "Invalid request origin."}, 403)
            return False
        return True

    def do_GET(self):
        if not self.local_request():
            return
        path = urlsplit(self.path).path
        try:
            if path == "/api/health":
                self.json_response({"status": "ok", "version": "0.1.3", "local_only": True})
            elif path == "/api/example":
                self.json_response(self.server.remember(analyze(example_inputs())))
            elif path == "/api/snapshots":
                items = []
                for file in sorted(self.server.storage.glob("*.json"), reverse=True):
                    try:
                        record = json.loads(file.read_text())
                        items.append({"id": record["id"], "symbol": record["symbol"], "source": record["source"],
                                      "classification": record["classification"], "saved_at": record["saved_at"], "retrieved_at": record["retrieved_at"]})
                    except (ValueError, KeyError, OSError):
                        log.warning("Skipping unreadable saved snapshot")
                self.json_response(sorted(items, key=lambda item: item["saved_at"], reverse=True))
            elif path.startswith("/api/snapshots/"):
                identifier = str(uuid.UUID(path.rsplit("/", 1)[-1]))
                file = self.server.storage / f"{identifier}.json"
                if not file.exists():
                    self.json_response({"error": "Snapshot not found."}, 404)
                else:
                    self.json_response(self.server.remember(json.loads(file.read_text())))
            elif path.startswith("/api/"):
                self.json_response({"error": "Unknown endpoint."}, 404)
            elif path in ["/", "/index.html"] and not (ROOT / "dist/index.html").exists():
                self.json_response({"error": "Build the interface first with npm run build."}, 503)
            else:
                super().do_GET()
        except (ValueError, OSError):
            self.json_response({"error": "The saved snapshot could not be opened."}, 404)

    def list_directory(self, path):
        self.send_error(404)
        return None

    def do_POST(self):
        if not self.local_request():
            return
        try:
            if self.headers.get_content_type() != "application/json":
                raise AnalysisError("invalid_content", "Send a JSON request.", 415)
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= 16_384:
                raise AnalysisError("invalid_length", "The request is empty or too large.", 413)
            body = json.loads(self.rfile.read(length))
            if not isinstance(body, dict):
                raise AnalysisError("invalid_request", "Send a JSON object.", 400)
            path = urlsplit(self.path).path
            if path == "/api/analyze":
                symbol = symbol_input(body.get("symbol"))
                override = body.get("event")
                if override is not None:
                    if not isinstance(override, dict):
                        raise AnalysisError("invalid_event", "The event must contain a date and session.", 400)
                    if override.get("date"):
                        try:
                            from datetime import date
                            date.fromisoformat(override["date"])
                        except (ValueError, TypeError):
                            raise AnalysisError("invalid_event", "Enter a valid earnings date.", 400) from None
                cache_key = json.dumps([symbol, override], sort_keys=True)
                cached = self.server.cache.get(cache_key)
                if cached and time.monotonic() - cached[0] < 60:
                    self.json_response(cached[1])
                    return
                if not self.server.analysis_slots.acquire(blocking=False):
                    raise AnalysisError("busy", "Two analyses are already running. Please try again shortly.", 429)
                try:
                    result = self.server.remember(analyze(fetch_inputs(symbol, override)))
                    self.server.cache[cache_key] = time.monotonic(), result
                    if len(self.server.cache) > 100:
                        self.server.cache.pop(next(iter(self.server.cache)))
                    self.json_response(result)
                finally:
                    self.server.analysis_slots.release()
            elif path == "/api/snapshots":
                identifier = str(uuid.UUID(body.get("analysis_id", "")))
                result = self.server.analyses.get(identifier)
                if result is None:
                    raise AnalysisError("expired_analysis", "Reopen or rerun this analysis before saving it.", 409)
                record = {**result, "saved_at": datetime.now(timezone.utc).isoformat()}
                self.server.storage.mkdir(parents=True, exist_ok=True)
                file = self.server.storage / f"{identifier}.json"
                temporary = file.with_suffix(".tmp")
                temporary.write_text(json.dumps(record, indent=2, allow_nan=False))
                temporary.replace(file)
                self.json_response({"id": identifier, "saved_at": record["saved_at"]}, 201)
            else:
                self.json_response({"error": "Unknown endpoint."}, 404)
        except AnalysisError as exc:
            self.json_response({"error": str(exc), "code": exc.code}, exc.status)
        except (ValueError, TypeError, json.JSONDecodeError):
            self.json_response({"error": "The request contains invalid data.", "code": "invalid_request"}, 400)
        except Exception:
            log.exception("Local API error")
            self.json_response({"error": "Something went wrong in the local app. Try again.", "code": "internal_error"}, 500)


def serve(port: int = 8765):
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    server = LabServer(("127.0.0.1", port))
    print(f"Earnings Lab: http://127.0.0.1:{server.server_port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8765)
    serve(parser.parse_args().port)

