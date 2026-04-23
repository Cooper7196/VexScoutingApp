"""
Local dev server with SPA fallback. Python's built-in http.server 404s on
client-side routes like /team/XXX/; this wrapper serves index.html for any
missing file so routing works when you type a deep URL in the address bar.

Usage: python serve.py [port]   (default 8765)
"""
import os
import sys
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer


class SPAHandler(SimpleHTTPRequestHandler):
    def do_GET(self):
        fs_path = self.translate_path(self.path.split("?", 1)[0].split("#", 1)[0])
        if not os.path.isfile(fs_path) and not os.path.isdir(fs_path):
            self.path = "/index.html"
        return super().do_GET()


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8765
    print(f"serving http://localhost:{port}/  (SPA fallback on)")
    ThreadingHTTPServer(("0.0.0.0", port), SPAHandler).serve_forever()
