"""Small Linux camera bench UI; serves genuine frames and explicit stale/errors.

Uses the board's existing Python 3.7. Capture runs independently and
publishes immutable full-resolution JPEGs in RAM. This is a camera preview, with no inference or
hand-control actions. SIGTERM/exit stops the owned capture process.
"""
import argparse
import ctypes
import datetime
import fcntl
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import threading
import time

HTML = '''<!doctype html><html lang="zh-CN"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Z19 相机实时预览</title><style>
body{font:16px system-ui;background:#101722;color:#e7eef8;margin:0;padding:24px}
main{max-width:1440px;margin:auto}h1{font-size:24px}img{width:100%;background:#080d15;border-radius:12px;object-fit:contain}img:fullscreen{height:100vh;width:100vw;border-radius:0}
button,input{font:inherit}button{padding:9px 18px;margin:6px;border:0;border-radius:8px;cursor:pointer}
#state{font-weight:700;color:#f8ca70}#detail{color:#b2c2d7}section{padding:16px 0}
</style><main><h1>Z19 相机实时预览</h1><p id="state">正在连接…</p>
<p id="detail">1080p 高清实时视频 · 正在连接</p><img id="image" alt="等待相机画面" hidden>
<section><button onclick="action('start')">启动</button><button onclick="action('stop')">停止</button>
<button onclick="document.getElementById('image').requestFullscreen()">全屏</button>
<p>手动焦距 <input id="focus" type="range" min="0" max="1023" value="300" oninput="document.getElementById('label').textContent=this.value">
<span id="label">300</span><button onclick="action('focus',{position:Number(document.getElementById('focus').value)})">应用</button></p>
<p id="message"></p></section></main><script>
const image=document.getElementById('image'),state=document.getElementById('state'),detail=document.getElementById('detail');
let streaming=false,busy=false;
async function action(name,data={}){try{let r=await fetch('/'+name,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});let j=await r.json();document.getElementById('message').textContent=j.message||'';}catch(e){document.getElementById('message').textContent='连接失败';}}
async function update(){if(busy)return;busy=true;try{let r=await fetch('/status.json',{cache:'no-store'});let j=await r.json();state.textContent=j.message;state.style.color=j.state==='LIVE'?'#79e5b2':'#f8ca70';if(j.state==='LIVE'){detail.textContent='1080p 高清视频 · '+j.preview_width+'×'+j.preview_height+' · '+(j.preview_fps||0).toFixed(1)+' 帧/秒 · 最新帧 '+Math.round(j.age_seconds*1000)+' ms 前';if(!streaming){image.src='/stream.mjpg?t='+Date.now();streaming=true;}image.hidden=false;}else{image.hidden=true;streaming=false;image.removeAttribute('src');detail.textContent='1080p 高清视频 · 等待画面';}}catch(e){state.textContent='连接中断';image.hidden=true;streaming=false;image.removeAttribute('src');}finally{busy=false;}}
image.onerror=()=>{image.hidden=true;streaming=false};setInterval(update,500);update();
</script></html>'''


class Camera:
    def __init__(self, executable, log_dir, ram_dir):
        self.executable = executable
        self.log_dir = log_dir
        self.ram_dir = ram_dir
        self.proc = None
        self.log = None
        self.preview_dir = None
        self.focus = 300
        self.counter = 0
        self.cache_sequence = None
        self.jpeg = None
        self.lock = threading.RLock()
        self.rate_sample = None
        self.preview_fps = 0.0

    def start(self):
        with self.lock:
            if self.proc is not None and self.proc.poll() is None:
                return '相机已在运行'
            if self.log is not None:
                self.log.close()
            self.counter += 1
            name = 'camera0-preview-' + datetime.datetime.now().strftime('%Y%m%d-%H%M%S') + '-%d' % self.counter
            self.preview_dir = self.ram_dir / name
            self.log = (self.log_dir / (name + '.txt')).open('xb')
            raw = self.log_dir / (name + '.raw')
            self.cache_sequence = None
            self.rate_sample = None
            self.preview_fps = 0.0
            self.proc = subprocess.Popen([str(self.executable), '3600', str(raw), str(self.focus), str(self.preview_dir)],
                                         stdout=self.log, stderr=subprocess.STDOUT, close_fds=True)
            return '相机正在启动，请等待画面'

    def stop(self):
        with self.lock:
            if self.proc is not None and self.proc.poll() is None:
                self.proc.terminate()
                try:
                    self.proc.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    self.proc.kill()
                    self.proc.wait(timeout=3)
            self.proc = None
            self.jpeg = None
            if self.log is not None:
                self.log.close()
                self.log = None
            return '相机已停止'

    def apply_focus(self, position):
        if isinstance(position, bool) or not isinstance(position, int) or not 0 <= position <= 1023:
            raise ValueError('焦距必须是 0～1023 的整数')
        with self.lock:
            if self.proc is None or self.proc.poll() is not None:
                self.focus = position
                return '下次启动将应用焦距 %d' % position

            class Msg(ctypes.Structure):
                _fields_ = [('addr', ctypes.c_ushort), ('flags', ctypes.c_ushort),
                            ('length', ctypes.c_ushort), ('buf', ctypes.POINTER(ctypes.c_ubyte))]

            class Transfer(ctypes.Structure):
                _fields_ = [('msgs', ctypes.POINTER(Msg)), ('nmsgs', ctypes.c_uint)]

            data = (ctypes.c_ubyte * 2)(position >> 4, (position & 15) << 4)
            messages = (Msg * 1)(Msg(0x0c, 0, 2, data))
            command = Transfer(messages, 1)
            fd = os.open('/dev/i2c-0', os.O_RDWR)
            try:
                payload = bytearray(ctypes.string_at(ctypes.addressof(command), ctypes.sizeof(command)))
                result = fcntl.ioctl(fd, 0x0707, payload, True)
                if result != 1:
                    raise RuntimeError('镜头调整失败')
            finally:
                os.close(fd)
            self.focus = position
            return '已应用手动焦距 %d' % position

    def snapshot(self, image=False):
        with self.lock:
            result = {'state': 'STOPPED', 'message': '相机已停止', 'focus': self.focus}
            if self.proc is None:
                return result, None
            code = self.proc.poll()
            if code is not None:
                result.update(state='ERROR' if code else 'STOPPED',
                              message='采集异常，请检查连接后重新启动' if code else '相机已停止')
                return result, None
            try:
                meta = json.loads((self.preview_dir / 'metadata.json').read_text())
                if not re.fullmatch(r'preview-[0-9]{8}\.jpg', meta['file']):
                    raise ValueError('unexpected frame name')
                if (meta['preview_width'], meta['preview_height']) != (1920, 1080):
                    raise ValueError('unexpected resolution')
                age = time.monotonic() - meta['monotonic']
                if age < 0 or age > .8:
                    result.update(state='STALE', message='画面已停止更新', age_seconds=age)
                    return result, None
                if image and self.cache_sequence != meta['sequence']:
                    encoded = (self.preview_dir / meta['file']).read_bytes()
                    if not encoded.startswith(b'\xff\xd8') or not encoded.endswith(b'\xff\xd9'):
                        raise ValueError('invalid JPEG')
                    self.jpeg = encoded
                    self.cache_sequence = meta['sequence']
                stamp = meta['monotonic']
                if self.rate_sample is None:
                    self.rate_sample = (stamp, meta['sequence'])
                elif stamp - self.rate_sample[0] >= 1:
                    self.preview_fps = (meta['sequence'] - self.rate_sample[1]) / (stamp - self.rate_sample[0])
                    self.rate_sample = (stamp, meta['sequence'])
                result.update(state='LIVE', message='实时画面', age_seconds=age, sequence=meta['sequence'],
                              preview_fps=self.preview_fps, capture_monotonic=stamp,
                              preview_width=meta['preview_width'], preview_height=meta['preview_height'],
                              copy_ms=meta['copy_ms'], encode_ms=meta['encode_ms'],
                              copy_discards=meta['copy_discards'], busy_skips=meta['busy_skips'],
                              obsolete_discards=meta['obsolete_discards'])
                return result, self.jpeg if image else None
            except (OSError, ValueError, KeyError):
                result.update(state='STARTING', message='正在等待相机画面')
                return result, None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--capture', type=Path, default=Path(__file__).with_name('capture_camera0'))
    parser.add_argument('--bind', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=9000)
    parser.add_argument('--log-dir', type=Path, default=Path('/var/lib/amazinghand/log'))
    parser.add_argument('--ram-dir', type=Path, default=Path('/run/amazinghand-preview'))
    args = parser.parse_args()
    if not args.capture.is_file():
        raise RuntimeError('capture executable missing')
    args.ram_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    camera = Camera(args.capture, args.log_dir, args.ram_dir)

    class Handler(BaseHTTPRequestHandler):
        def reply(self, code, body, mime='application/json; charset=utf-8'):
            self.send_response(code)
            self.send_header('Content-Type', mime)
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            try:
                self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError):
                pass

        def do_GET(self):
            path = self.path.split('?', 1)[0]
            if path == '/':
                self.reply(200, HTML.encode(), 'text/html; charset=utf-8')
            elif path == '/status.json':
                self.reply(200, json.dumps(camera.snapshot()[0], ensure_ascii=False).encode())
            elif path == '/frame.jpg':
                result, jpeg = camera.snapshot(image=True)
                if result['state'] != 'LIVE' or jpeg is None:
                    self.reply(503, b'{"error":"no fresh frame"}')
                else:
                    self.reply(200, jpeg, 'image/jpeg')
            elif path == '/stream.mjpg':
                result, jpeg = camera.snapshot(image=True)
                if result['state'] != 'LIVE' or jpeg is None:
                    self.reply(503, b'{"error":"no fresh frame"}')
                    return
                self.send_response(200)
                self.send_header('Content-Type', 'multipart/x-mixed-replace; boundary=frame')
                self.send_header('Cache-Control', 'no-store')
                self.end_headers()
                self.connection.settimeout(3)
                last = None
                try:
                    while True:
                        result, jpeg = camera.snapshot(image=True)
                        if result['state'] != 'LIVE' or jpeg is None:
                            break
                        if result['sequence'] != last:
                            header = ('--frame\r\nContent-Type: image/jpeg\r\nContent-Length: %d\r\n'
                                      'X-Sequence: %d\r\nX-Capture-Monotonic: %.6f\r\n\r\n' %
                                      (len(jpeg), result['sequence'], result['capture_monotonic'])).encode()
                            self.wfile.write(header + jpeg + b'\r\n')
                            self.wfile.flush()
                            last = result['sequence']
                        time.sleep(.003)
                except (BrokenPipeError, ConnectionResetError, TimeoutError, OSError):
                    pass
            else:
                self.reply(404, b'{}')

        def do_POST(self):
            try:
                size = int(self.headers.get('Content-Length', '0'))
                if size < 0 or size > 1024:
                    raise ValueError('invalid request')
                data = json.loads(self.rfile.read(size) or b'{}')
                if self.path == '/start': message = camera.start()
                elif self.path == '/stop': message = camera.stop()
                elif self.path == '/focus': message = camera.apply_focus(data.get('position'))
                else: self.reply(404, b'{}'); return
                self.reply(200, json.dumps({'message': message}, ensure_ascii=False).encode())
            except (ValueError, AttributeError, OSError, RuntimeError) as error:
                self.reply(400, json.dumps({'message': str(error)}, ensure_ascii=False).encode())

        def log_message(self, fmt, *values):
            pass  # Frame requests do not flood persistent logs.

    server = ThreadingHTTPServer((args.bind, args.port), Handler)
    # Raise in the main thread so finally always stops the capture.
    def terminate(sig, frame):
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, terminate)
    signal.signal(signal.SIGHUP, terminate)
    try:
        print(camera.start(), flush=True)
        print('PREVIEW_URL http://%s:%d/' % (args.bind, args.port), flush=True)
        server.serve_forever(poll_interval=.2)
    except KeyboardInterrupt:
        pass
    finally:
        camera.stop()
        server.server_close()


if __name__ == '__main__':
    main()
