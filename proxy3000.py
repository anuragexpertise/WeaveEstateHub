"""
Simple proxy server to forward port 3000 → 8001 (Dash app).
The Emergent platform routes:
  - /api/* → port 8001
  - everything else → port 3000
Since our Dash app serves both, this proxy bridges port 3000 to 8001.
"""
from http.server import HTTPServer, BaseHTTPRequestHandler
import urllib.request
import urllib.error

TARGET = "http://127.0.0.1:8001"

class ProxyHandler(BaseHTTPRequestHandler):
    def do_request(self):
        url = TARGET + self.path
        headers = {}
        for key, val in self.headers.items():
            if key.lower() not in ('host',):
                headers[key] = val

        body = None
        content_length = self.headers.get('Content-Length')
        if content_length:
            body = self.rfile.read(int(content_length))

        req = urllib.request.Request(url, data=body, headers=headers, method=self.command)
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                self.send_response(resp.status)
                for key, val in resp.getheaders():
                    if key.lower() not in ('transfer-encoding', 'connection'):
                        self.send_header(key, val)
                self.end_headers()
                self.wfile.write(resp.read())
        except urllib.error.HTTPError as e:
            self.send_response(e.code)
            for key, val in e.headers.items():
                if key.lower() not in ('transfer-encoding', 'connection'):
                    self.send_header(key, val)
            self.end_headers()
            self.wfile.write(e.read())
        except Exception as e:
            self.send_response(502)
            self.send_header('Content-Type', 'text/plain')
            self.end_headers()
            self.wfile.write(f"Proxy error: {e}".encode())

    def do_GET(self):    self.do_request()
    def do_POST(self):   self.do_request()
    def do_PUT(self):    self.do_request()
    def do_DELETE(self): self.do_request()
    def do_PATCH(self):  self.do_request()
    def do_OPTIONS(self):self.do_request()

    def log_message(self, format, *args):
        pass  # suppress logs

if __name__ == "__main__":
    print("🔀 Proxy: 0.0.0.0:3000 → 127.0.0.1:8001")
    HTTPServer(("0.0.0.0", 3000), ProxyHandler).serve_forever()
