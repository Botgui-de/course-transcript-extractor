"""Local HTTP receiver for course-transcript extraction (see AGENT-GUIDE.md).

Endpoints (all on 127.0.0.1, CORS-open, with the Private-Network-Access header
Chrome requires for public-page -> localhost fetches):
  POST /save  {"name": "...", "text": "..."}   -> writes <out>/<slug>.md
  POST /urls  {"name", "master", "child"}      -> queues <queue>/<slug>.json for hotmart_captions.py
  GET  /list                                    -> JSON list of saved .md filenames

Usage:  python tools/transcript_receiver.py [--port 8765] [--out transcripts] [--queue queue]
Paths are relative to the repo root (parent of tools/). Ctrl+C to stop.
"""
import argparse
import json
import re
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def slugify(name: str) -> str:
    s = re.sub(r"[^A-Za-z0-9]+", "-", name).strip("-").lower()
    return s[:120] or "untitled"


def make_handler(out_dir: Path, queue_dir: Path):
    class Handler(BaseHTTPRequestHandler):
        def _cors(self):
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            # Chrome Private Network Access: public page -> localhost needs this on preflight
            self.send_header("Access-Control-Allow-Private-Network", "true")

        def do_OPTIONS(self):
            self.send_response(204)
            self._cors()
            self.end_headers()

        def do_GET(self):
            body = json.dumps(sorted(p.name for p in out_dir.glob("*.md"))).encode()
            self.send_response(200)
            self._cors()
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self):
            try:
                length = int(self.headers.get("Content-Length", 0))
                data = json.loads(self.rfile.read(length))
                if self.path == "/urls":
                    queue_dir.mkdir(parents=True, exist_ok=True)
                    path = queue_dir / f"{slugify(data['name'])}.json"
                    path.write_text(json.dumps(data), encoding="utf-8")
                    resp, code = {"queued": path.name}, 200
                else:
                    name, text = data["name"], data["text"]
                    path = out_dir / f"{slugify(name)}.md"
                    path.write_text(f"# {name}\n\n{text}\n", encoding="utf-8")
                    resp, code = {"saved": path.name, "chars": len(text)}, 200
            except Exception as e:  # noqa: BLE001 - report any failure to the browser
                resp, code = {"error": str(e)}, 400
            body = json.dumps(resp).encode()
            self.send_response(code)
            self._cors()
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, fmt, *args):  # quiet
            pass

    return Handler


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--out", default="transcripts")
    ap.add_argument("--queue", default="queue")
    args = ap.parse_args()
    out_dir = (ROOT / args.out).resolve()
    queue_dir = (ROOT / args.queue).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"transcripts -> {out_dir}\nqueue       -> {queue_dir}\nlistening on 127.0.0.1:{args.port}")
    HTTPServer(("127.0.0.1", args.port), make_handler(out_dir, queue_dir)).serve_forever()
