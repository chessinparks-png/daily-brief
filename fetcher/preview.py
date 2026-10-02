"""Local preview of the app: python fetcher/preview.py  ->  http://localhost:8765
Serves the app and data/latest.json only; data/raw (full text) is never served."""
import http.server, pathlib, functools

ROOT = pathlib.Path(__file__).resolve().parent.parent


class Handler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        p = self.path.split("?")[0].lstrip("/")
        if p.startswith(("data/raw", "fetcher", "config", ".git", ".venv", ".claude")) or p.endswith((".md", ".py")):
            return self.send_error(404)
        super().do_GET()

    def end_headers(self):
        self.send_header("Cache-Control", "no-cache")
        super().end_headers()


if __name__ == "__main__":
    h = functools.partial(Handler, directory=str(ROOT))
    print("Preview at http://localhost:8765  (Ctrl+C to stop)")
    http.server.ThreadingHTTPServer(("127.0.0.1", 8765), h).serve_forever()
