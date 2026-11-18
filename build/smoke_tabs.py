# -*- coding: utf-8 -*-
"""逐页签烟测：点每个页签，看内容区是否渲染出来了、有没有 JS 异常。
用法: python build\\smoke_tabs.py <url> [port]
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
PORT = int(sys.argv[2]) if len(sys.argv) > 2 else 9240
PROF = os.path.join(WS, "shots", "preprof_smoke")
OUTD = os.path.join(WS, "shots", "smoke_tabs")
shutil.rmtree(PROF, ignore_errors=True)
shutil.rmtree(OUTD, ignore_errors=True)
os.makedirs(OUTD, exist_ok=True)

kill_stale(verbose=False)
p = subprocess.Popen([EDGE, "--headless=new", "--disable-gpu", "--hide-scrollbars",
                      "--noerrdialogs", "--disable-crash-reporter", "--disable-breakpad",
                      f"--remote-debugging-port={PORT}", f"--user-data-dir={PROF}",
                      "--window-size=1300,1000", "about:blank"],
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
EV = []


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
    msg = json.loads(pay.decode())
    if msg.get("method") == "Runtime.exceptionThrown":
        EV.append(json.dumps(msg["params"]["exceptionDetails"].get("exception", {}), ensure_ascii=False)[:300])
    return msg


def evaluate(expr):
    rid = send("Runtime.evaluate", {"expression": expr, "returnByValue": True})
    while True:
        m = recv()
        if m.get("id") == rid:
            return m.get("result", {}).get("result", {}).get("value")


send("Page.enable"); send("Runtime.enable")
send("Page.navigate", {"url": URL})
time.sleep(3.5)
tabs = evaluate("[...document.querySelectorAll('#tabs button')].map(b=>b.dataset.t)")
print("tabs:", tabs)
bad = []
for t in tabs:
    evaluate(f"document.querySelector('#tabs button[data-t=\"{t}\"]').click()")
    time.sleep(0.45)
    vis = evaluate("[...document.querySelectorAll('section')].filter(s=>getComputedStyle(s).display!=='none').map(s=>s.id).join(',')")
    txt = evaluate(f"var s=document.getElementById('{t}'); s? s.innerText.replace(/\\s+/g,' ').trim().length : -1")
    has_frame = evaluate(f"!!document.querySelector('#{t} iframe')")
    # iframe 页（模拟加点）的正文在子文档里，innerText 数不到，改成看 iframe 在不在
    ok = (vis == t and (txt and txt > 60 or has_frame))
    print("%-9s visible=%-9s textlen=%-6s %s" % (t, vis, txt, "ok" if ok else "!! CHECK"))
    if not ok:
        bad.append(t)
# 人物页截图（确认别的页没被弄坏）
evaluate("document.querySelector('#tabs button[data-t=\"renwu\"]').click()")
time.sleep(0.5)
send("Emulation.setDeviceMetricsOverride", {"width": 1300, "height": 1000, "deviceScaleFactor": 1, "mobile": False})
rid = send("Page.captureScreenshot", {"format": "png"})
while True:
    m = recv()
    if m.get("id") == rid:
        open(os.path.join(OUTD, "renwu.png"), "wb").write(base64.b64decode(m["result"]["data"]))
        break
print("exceptions:", EV[:5], "count", len(EV))
print("bad tabs:", bad)
kill_tree(p.pid)
kill_stale(verbose=True)
sys.exit(0 if not bad and not EV else 1)
