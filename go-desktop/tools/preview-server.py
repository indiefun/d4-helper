"""Local layout preview only; no write API and no input injection."""
import http.server
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT / 'frontend'), **kwargs)

    def do_GET(self):
        if self.path == '/config.json':
            data = (ROOT.parent / 'config.json').read_bytes()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Content-Length', str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        else:
            super().do_GET()


if __name__ == '__main__':
    print('Layout preview: http://127.0.0.1:8765', flush=True)
    http.server.ThreadingHTTPServer(('127.0.0.1', 8765), Handler).serve_forever()
