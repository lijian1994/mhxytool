# -*- coding: utf-8 -*-
"""逐页签整页截图（含滚动后侧边栏是否跟手、手机宽度）。
用法: python build\\shots_tabs.py <url> [port] [tag]
"""
import atexit, base64, json, os, socket, struct, subprocess, sys, time, urllib.request, shutil

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
PORT = int(sys.argv[2]) if len(sys.argv) > 2 else 9250
TAG = sys.argv[3] if len(sys.argv) > 3 else "r36"
W = int(os.environ.get("SHOT_W", "1300"))
PROF = os.path.join(WS, "shots", "preprof_shots")
OUTD = os.path.join(WS, "shots", "tabs_" + TAG)
shutil.rmtree(PROF, ignore_errors=True)
shutil.rmtree(OUTD, ignore_errors=True)
os.makedirs(OUTD, exist_ok=True)

kill_stale(verbose=False)
p = subprocess.Popen([EDGE, "--headless=new", "--disable-gpu", "--hide-scrollbars",
                      "--noerrdialogs", "--disable-crash-reporter", "--disable-breakpad",
                      f"--remote-debugging-port={PORT}", f"--user-data-dir={PROF}",
                      "--window-size=1300,900", "about:blank"],
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
atexit.register(lambda: kill_tree(p.pid))
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
    if ln < 126: h += bytes([0x80 | ln])
    elif ln < 65536: h += bytes([0x80 | 126]) + struct.pack(">H", ln)
    else: h += bytes([0x80 | 127]) + struct.pack(">Q", ln)
    s.sendall(h + mask + bytes(x ^ mask[i % 4] for i, x in enumerate(pay)))
    return mid[0]


def rd(n):
    d = b""
    while len(d) < n:
        c = s.recv(n - len(d))
        if not c: raise EOFError
        d += c
    return d


def recv():
    pay = b""
    while True:
        h = rd(2); fin = h[0] & 0x80; op = h[0] & 0x0f; ln = h[1] & 0x7f
        if ln == 126: ln = struct.unpack(">H", rd(2))[0]
        elif ln == 127: ln = struct.unpack(">Q", rd(8))[0]
        pay += rd(ln)
        if op == 9: continue
        if fin: break
    return json.loads(pay.decode())


def ev(expr):
    rid = send("Runtime.evaluate", {"expression": expr, "returnByValue": True})
    while True:
        m = recv()
        if m.get("id") == rid:
            r = m.get("result", {})
            return r.get("result", {}).get("value")


def shot(name, full=True):
    # 注意：headless=new 下 captureBeyondViewport + clip 会渲染走形（尺寸全乱），
    # 改成「把视口高度调到内容高度再截」这条路才正常。
    if full:
        h = ev("Math.max(600, Math.min(4000, Math.max(document.body.scrollHeight, document.documentElement.scrollHeight)))")
        send("Emulation.setDeviceMetricsOverride",
             {"width": W, "height": int(h), "deviceScaleFactor": 1, "mobile": False})
        time.sleep(0.35)
    params = {"format": "png", "fromSurface": True}
    rid = send("Page.captureScreenshot", params)
    while True:
        m = recv()
        if m.get("id") == rid:
            open(os.path.join(OUTD, name), "wb").write(base64.b64decode(m["result"]["data"]))
            return


send("Page.enable"); send("Runtime.enable")
send("Emulation.setDeviceMetricsOverride", {"width": W, "height": 900, "deviceScaleFactor": 1, "mobile": False})
send("Page.navigate", {"url": URL})
time.sleep(3.5)

tabs = ev("[...document.querySelectorAll('#tabs button')].map(b=>b.dataset.t)")
only = sys.argv[4] if len(sys.argv) > 4 else None
if only:
    tabs = [t for t in tabs if t in only.split(",")]
for t in tabs:
    ev(f"document.querySelector('#tabs button[data-t=\"{t}\"]').click()")
    time.sleep(0.6)
    shot(t + ".png")
    print("shot", t)

# 侧边栏 sticky：滚到 700px 再截一张
ev("document.querySelector('#tabs button[data-t=\"renwu\"]').click()")
time.sleep(0.4)
ev("window.scrollTo(0,700)")
time.sleep(0.4)
print("scrollY=", ev("window.scrollY"), "tabsTop=", ev("document.getElementById('tabs').getBoundingClientRect().top"))
send("Emulation.setDeviceMetricsOverride", {"width": 1300, "height": 760, "deviceScaleFactor": 1, "mobile": False})
shot("_scrolled.png", full=False)

# 手机宽度
send("Emulation.setDeviceMetricsOverride", {"width": 390, "height": 844, "deviceScaleFactor": 1, "mobile": True})
ev("window.scrollTo(0,0)")
time.sleep(0.6)
shot("_mobile390.png", full=False)
print("tabsTop mobile=", ev("document.getElementById('tabs').getBoundingClientRect().top"))

kill_tree(p.pid)
kill_stale(verbose=True)
