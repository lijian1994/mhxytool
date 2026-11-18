# -*- coding: utf-8 -*-
"""模拟加点 iframe 页（单独抽出来当独立页面跑）的功能巡检。

用法: python build\\audit_jiadian.py <url> [port]
  url 指向一份独立的 jiadian.html。文件夹版已删除、不再产出这个文件，
  需要时先抽一份出来（抽完记得删，别把它当交付物）：
    python build\\_extract_jiadian.py        # 从 build\\template2.html 的 data: URL 抽出 shots\\_jiadian.html
  逐项面板联动 + 保存/刷新/清空的正式验收见 audit_manual.py（直接在单文件里操作 iframe，不需要抽文件）。
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
PORT = int(sys.argv[2]) if len(sys.argv) > 2 else 9270
OUTD = os.path.join(WS, "shots", "jiadian_shots")
shutil.rmtree(OUTD, ignore_errors=True); os.makedirs(OUTD, exist_ok=True)
PROF = os.path.join(WS, "shots", "preprof_jiadian")
shutil.rmtree(PROF, ignore_errors=True)
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
mid = [0]; EXC = []


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
        EXC.append((msg["params"]["exceptionDetails"].get("exception", {}) or {}).get("description", "")[:300])
    return msg


def ev(expr):
    rid = send("Runtime.evaluate", {"expression": expr, "returnByValue": True})
    while True:
        m = recv()
        if m.get("id") == rid:
            r = m.get("result", {})
            if "exceptionDetails" in r:
                return "__ERR__:" + str((r["exceptionDetails"].get("exception", {}) or {}).get("description", ""))[:200]
            return r.get("result", {}).get("value")


def shot(name, full=True):
    h = ev("Math.max(document.body.scrollHeight, document.documentElement.scrollHeight)")
    params = {"format": "png", "captureBeyondViewport": True}
    if full:
        params["clip"] = {"x": 0, "y": 0, "width": 1300, "height": min(4000, int(h)), "scale": 1}
    rid = send("Page.captureScreenshot", params)
    while True:
        m = recv()
        if m.get("id") == rid:
            open(os.path.join(OUTD, name), "wb").write(base64.b64decode(m["result"]["data"]))
            return


send("Page.enable"); send("Runtime.enable")
send("Page.navigate", {"url": URL})
time.sleep(3.0)
print("title:", ev("document.title"))
print("inputs:", ev("document.querySelectorAll('input').length"),
      "selects:", ev("document.querySelectorAll('select').length"),
      "save/clear:", ev("!!document.getElementById('mz-save')"), ev("!!document.getElementById('mz-clear')"))
print("body text head:", (ev("document.body.innerText") or "")[:400].replace("\n", " | "))
shot("01_blank.png")

# 填 体质 100，看面板 气血 是否变成 550（体质×4.5 + 100）
ev("""(function(){var el=document.getElementById('mt_tizhi'); el.value='100';
      el.dispatchEvent(new Event('input',{bubbles:true})); el.dispatchEvent(new Event('change',{bubbles:true}));})()""")
time.sleep(0.5)
txt = ev("document.body.innerText") or ""
import re
m = re.search(r"气血\s*([0-9.]+)", txt)
print("气血 after 体质=100:", m.group(1) if m else "(未找到)")
m2 = re.search(r"魔法\s*([0-9.]+)", txt)
print("魔法:", m2.group(1) if m2 else "?")

# 门派 / 等级
ev("""(function(){var el=document.querySelector("select"); if(el){el.selectedIndex=Math.min(2,el.options.length-1);
      el.dispatchEvent(new Event('change',{bubbles:true}));}})()""")
time.sleep(0.3)
ev("""(function(){var el=document.querySelector("input[name=jibie]"); if(el){el.value='150';
      el.dispatchEvent(new Event('input',{bubbles:true})); el.dispatchEvent(new Event('change',{bubbles:true}));
      el.dispatchEvent(new Event('blur',{bubbles:true}));}})()""")
time.sleep(0.4)
print("after 等级=150, body head:", (ev("document.body.innerText") or "")[:200].replace("\n", " | "))
shot("02_filled.png")

n0 = len(EXC)
ev("document.getElementById('mz-save').click()")
time.sleep(0.3)
print("save 后有异常:", EXC[n0:])

# 「开启对比」页签
before_txt = ev("document.body.innerText") or ""
tab2 = ev("""(function(){var bs=[...document.querySelectorAll('button,input[type=button],.tab')];
  var t=bs.filter(function(b){return (b.textContent||'').indexOf('开启对比')>=0;})[0]; if(t){t.click();return true;} return false;})()""")
time.sleep(0.6)
after_txt = ev("document.body.innerText") or ""
print("对比页签按钮找到:", tab2, "| 文本变化:", before_txt != after_txt,
      "| 长度", len(before_txt), "->", len(after_txt))
shot("04_compare.png")
# 切回模拟属性
ev("""(function(){var bs=[...document.querySelectorAll('button,input[type=button],.tab')];
  var t=bs.filter(function(b){return (b.textContent||'').indexOf('模拟属性')>=0;})[0]; if(t) t.click();})()""")
time.sleep(0.4)
print("切回后文本恢复:", (ev("document.body.innerText") or "")[:40].replace("\n", " | "))
n0 = len(EXC)
ev("document.getElementById('mz-clear').click()")
time.sleep(0.4)
print("clear 后有异常:", EXC[n0:])
print("clear 后 体质 值:", ev("document.getElementById('mt_tizhi').value"))
shot("03_cleared.png")
print("total exceptions:", len(EXC))
kill_tree(p.pid)
kill_stale(verbose=True)
