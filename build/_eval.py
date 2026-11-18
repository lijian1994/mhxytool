# -*- coding: utf-8 -*-
"""无头自检小工具：打开页面 → 等加载 → 执行一段 JS → 打印返回值。

用法: python build\\_eval.py <url> <js文件> [port]
说明: 用独立 profile（shots\\preprof_eval），跑完整棵树收掉，不弹窗。
"""
import base64, json, os, socket, struct, subprocess, sys, time, urllib.request, shutil

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from edge_guard import kill_stale, kill_tree

try:
    import ctypes
    ctypes.windll.kernel32.SetErrorMode(0x0001 | 0x0002)
except Exception:
    pass

WS = r"F:\Documents\deepseek-harness\default-workspace"
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
URL = sys.argv[1]
JS_FILE = sys.argv[2]
PORT = int(sys.argv[3]) if len(sys.argv) > 3 else 9270
PROF = os.path.join(WS, "shots", "preprof_eval")
if not os.environ.get('MZ_KEEP_PROFILE'):
    shutil.rmtree(PROF, ignore_errors=True)
kill_stale(verbose=False)

p = subprocess.Popen([EDGE, "--headless=new", "--disable-gpu", "--hide-scrollbars",
                      "--noerrdialogs", "--disable-crash-reporter", "--disable-breakpad",
                      f"--remote-debugging-port={PORT}", f"--user-data-dir={PROF}",
                      "--window-size=1300,900", "about:blank"],
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(3.0)
tg = json.load(urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json/list"))
ws = [t for t in tg if t.get("type") == "page"][0]["webSocketDebuggerUrl"]
host, port = ws.split("//")[1].split("/")[0].split(":")
path = "/" + ws.split("//")[1].split("/", 1)[1]
s = socket.create_connection((host, int(port)), timeout=60)
key = base64.b64encode(os.urandom(16)).decode()
s.sendall((f"GET {path} HTTP/1.1\r\nHost: {host}:{port}\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
           f"Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n").encode())
b = b""
while b"\r\n\r\n" not in b:
    b += s.recv(4096)
mid = [0]


def send(m, pr=None):
    mid[0] += 1
    pay = json.dumps({"id": mid[0], "method": m, "params": pr or {}}).encode()
    mask = os.urandom(4)
    h = bytes([0x81]); ln = len(pay)
    if ln < 126:
        h += bytes([0x80 | ln])
    elif ln < 65536:
        h += bytes([0x80 | 126]) + struct.pack(">H", ln)
    else:
        h += bytes([0x80 | 127]) + struct.pack(">Q", ln)
    s.sendall(h + mask + bytes(x ^ mask[i % 4] for i, x in enumerate(pay)))
    return mid[0]


def rd(n):
    d = b""
    while len(d) < n:
        c = s.recv(n - len(d))
        if not c:
            raise EOFError
        d += c
    return d


def recv():
    pay = b""
    while True:
        h = rd(2); fin = h[0] & 0x80; op = h[0] & 0x0f; ln = h[1] & 0x7f
        if ln == 126:
            ln = struct.unpack(">H", rd(2))[0]
        elif ln == 127:
            ln = struct.unpack(">Q", rd(8))[0]
        pay += rd(ln)
        if op == 9:
            continue
        if fin:
            break
    return json.loads(pay.decode())


def ev(expr, timeout=20):
    rid = send("Runtime.evaluate", {"expression": expr, "returnByValue": True, "awaitPromise": True})
    end = time.time() + timeout
    while time.time() < end:
        m = recv()
        if m.get("id") == rid:
            r = m.get("result", {})
            if r.get("exceptionDetails"):
                return {"__exception": r["exceptionDetails"].get("text")}
            return r.get("result", {}).get("value")
    return {"__timeout": True}


send("Page.enable"); send("Runtime.enable")
send("Emulation.setDeviceMetricsOverride", {"width": 1300, "height": 900, "deviceScaleFactor": 1, "mobile": False})
send("Page.navigate", {"url": URL})
time.sleep(3.5)

js = open(JS_FILE, encoding="utf-8").read()
result = ev(js)
print(json.dumps(result, ensure_ascii=False, indent=2) if not isinstance(result, str) else result)
time.sleep(2.5)   # 给 Chromium 落盘 localStorage 的时间，否则 taskkill 会丢掉写入

try:
    kill_tree(p.pid)
except Exception:
    pass
