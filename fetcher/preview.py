"""Local preview of the app: python fetcher/preview.py  ->  http://localhost:8765/site/
Serves the app and data/latest.json only; data/raw (full text) is never served."""
import http.server, pathlib, functools

ROOT = pathlib.Path(__file__).resolve().parent.parent
BLOCKED_DIRS = {"fetcher", "config", ".git", ".venv", ".claude", ".github"}


def private(path):
    """True for anything that must not be served. Checks the real file the server
    would open, so tricks like %2F, ../ or Data/raw (macOS ignores case) don't get through."""
    try:
        rel = pathlib.Path(path).resolve().relative_to(ROOT)
    except ValueError:
        return True  # outside the project
    parts = [p.lower() for p in rel.parts]
    return (
        (parts and parts[0] in BLOCKED_DIRS)
        or parts[:2] == ["data", "raw"]
        or rel.suffix.lower() in (".md", ".py")
    )


class Handler(http.server.SimpleHTTPRequestHandler):
    def send_head(self):
        if private(self.translate_path(self.path)):
            self.send_error(404)
            return None
        return super().send_head()

    def end_headers(self):
        self.send_header("Cache-Control", "no-cache")
        super().end_headers()


if __name__ == "__main__":
    h = functools.partial(Handler, directory=str(ROOT))
    print("Preview at http://localhost:8765/site/  (Ctrl+C to stop)")
    http.server.ThreadingHTTPServer(("127.0.0.1", 8765), h).serve_forever()
