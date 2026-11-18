# -*- coding: utf-8 -*-
"""把页面跑一遍、把「渲染完的 DOM」取回来，作为新的 index.html：
这样浏览器首帧就带着算好的数值，不再出现"空壳 → 内容"的中间态。"""
import atexit, base64, json, os, socket, struct, subprocess, sys, time, urllib.request, shutil

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from edge_guard import kill_stale, kill_tree   # 收尾必须连子进程一起收，见 edge_guard.py

# 关键：无头 Edge 崩了会弹「msedge 已停止工作」+「Error launching CrashSender.exe」窗口，
# 那是 Windows 对子进程的错误框，会直接怼到用户桌面上。这里把子进程的错误框关掉。
try:
    import ctypes
    _SEM = 0x0001 | 0x0002          # SEM_FAILCRITICALERRORS | SEM_NOGPFAULTERRORBOX
    ctypes.windll.kernel32.SetErrorMode(_SEM)
except Exception:
    pass

EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
INDEX = sys.argv[1] if len(sys.argv) > 1 else r"F:\Desktop\梦幻西游工具\梦幻西游实用工具箱-复刻版.html"
PORT = sys.argv[2] if len(sys.argv) > 2 else "9226"
PROF = rf"F:\Documents\deepseek-harness\default-workspace\shots\preprof_{PORT}"
shutil.rmtree(PROF, ignore_errors=True)
SRC_LEN = len(open(INDEX, encoding="utf-8").read())   # 只用来打印覆盖率，不再留 .src 备份（旧备份会变成误导人的旧版本）

def ws_connect(url):
    ws = url
    host, port = ws.split("//")[1].split("/")[0].split(":")
    path = "/" + ws.split("//")[1].split("/", 1)[1]
    s = socket.create_connection((host, int(port)), timeout=30)
    key = base64.b64encode(os.urandom(16)).decode()
    s.sendall((f"GET {path} HTTP/1.1\r\nHost: {host}:{port}\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
               f"Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n").encode())
    buf = b""
    while b"\r\n\r\n" not in buf: buf += s.recv(4096)
    return s

kill_stale(verbose=False)          # 开工前先清一遍上一轮漏下的无头 Edge

p = subprocess.Popen([EDGE, "--headless=new", "--disable-gpu", "--hide-scrollbars",
                      "--noerrdialogs", "--disable-crash-reporter", "--disable-breakpad",
                      f"--remote-debugging-port={PORT}", f"--user-data-dir={PROF}",
                      "--window-size=1300,900", "about:blank"],
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
atexit.register(lambda: kill_tree(p.pid))   # 正常结束/异常/中途 exit 都会收整棵树
time.sleep(2.5)
tg = json.load(urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json/list"))
s = ws_connect([t for t in tg if t.get("type") == "page"][0]["webSocketDebuggerUrl"])
mid = [0]
def send(m, pr=None):
    mid[0] += 1
    pay = json.dumps({"id": mid[0], "method": m, "params": pr or {}}).encode()
    mask = os.urandom(4); h = bytes([0x81]); ln = len(pay)
    if ln < 126: h += bytes([0x80 | ln])
    elif ln < 65536: h += bytes([0x80 | 126]) + struct.pack(">H", ln)
    else: h += bytes([0x80 | 127]) + struct.pack(">Q", ln)
    s.sendall(h + mask + bytes(b ^ mask[i % 4] for i, b in enumerate(pay)))
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
        if op == 0x9: continue
        if fin: break
    return json.loads(pay.decode())

send("Page.enable")
send("Runtime.enable")
url = "file:///" + INDEX.replace("\\", "/")
send("Page.navigate", {"url": url})
time.sleep(3.0)

rid = send("Runtime.evaluate", {"expression": "document.documentElement.outerHTML", "returnByValue": True})
html = None
while True:
    m = recv()
    if m.get("id") == rid:
        html = m["result"]["result"]["value"]; break
kill_tree(p.pid)     # 连 gpu/utility/renderer 子进程一起收（p.kill() 会留孤儿）

if not html:
    print("!! 取 DOM 失败"); sys.exit(1)
if not html.startswith("<!DOCTYPE"):
    html = "<!DOCTYPE html>\n" + html

# 去掉抓到的 DOM 里"上次运行时"留下的选中态：让首帧完全由 #boot-tab 规则决定
import re as _re
html = _re.sub(r'(<button data-t="[^"]+")\s+class="on"', r"\1", html)
html = _re.sub(r'(<section id="[^"]+")\s+class="on"', r"\1", html)
open(INDEX, "w", encoding="utf-8").write(html)
print("预渲染完成，index.html =", len(html), "字符（源", SRC_LEN, "）")
