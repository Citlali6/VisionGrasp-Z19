"""PC loopback viewer for the Z19 camera, bypassing proxies only for this app.

Run on the PC, with no board-targeted packages. Open http://127.0.0.1:8766/.
Only camera routes are forwarded to the fixed board, with no SSH forwarding or
changes to Windows proxy settings. Ctrl+C stops this viewer, not the board.
"""
import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import socket
import urllib.error
import urllib.request


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=8766)
    args = parser.parse_args()
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    class Handler(BaseHTTPRequestHandler):
        def forward(self, post=False):
            path = self.path.split('?', 1)[0]
            allowed = {'/start', '/stop', '/focus'} if post else {'/', '/status.json', '/frame.jpg', '/stream.mjpg'}
            if path not in allowed:
                self.send_error(404)
                return
            body = None
            if post:
                try:
                    size = int(self.headers.get('Content-Length', '0'))
                    if not 0 <= size <= 1024:
                        raise ValueError('request too large')
                except ValueError:
                    self.send_error(400)
                    return
                # Same-origin browser controls only; reject a foreign Origin.
                origin = self.headers.get('Origin')
                if origin and origin not in {'http://127.0.0.1:%d' % args.port,
                                             'http://localhost:%d' % args.port}:
                    self.send_error(403)
                    return
                body = self.rfile.read(size)
            request = urllib.request.Request('http://127.0.0.1:9000' + self.path,
                                             data=body, method='POST' if post else 'GET',
                                             headers={'Content-Type': 'application/json'})
            try:
                try:
                    remote = opener.open(request, timeout=5)
                except urllib.error.HTTPError as error:
                    remote = error
                with remote:
                    self.send_response(remote.status)
                    for key in ('Content-Type', 'Content-Length'):
                        if remote.headers.get(key):
                            self.send_header(key, remote.headers[key])
                    self.send_header('Cache-Control', 'no-store')
                    self.end_headers()
                    self.connection.settimeout(3)
                    while True:
                        chunk = remote.read1(65536)
                        if not chunk:
                            break
                        self.wfile.write(chunk)
                        self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError, socket.timeout):
                pass
            except urllib.error.URLError:
                self.send_error(502, 'Z19 camera is unreachable')

        def do_GET(self):
            self.forward()

        def do_POST(self):
            self.forward(post=True)

        def log_message(self, fmt, *values):
            pass

    server = ThreadingHTTPServer(('127.0.0.1', args.port), Handler)
    print('CAMERA_VIEW_URL http://127.0.0.1:%d/' % args.port, flush=True)
    try:
        server.serve_forever(poll_interval=.2)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
