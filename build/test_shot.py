# -*- coding: utf-8 -*-
"""测「截图搜题」链路：在页面里画一张带题目的图 → runOcr → 看答案/选项是否对。
用法: python build\\test_shot.py <url> [port]
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
PORT = int(sys.argv[2]) if len(sys.argv) > 2 else 9410
PROF = os.path.join(WS, "shots", "preprof_shot")
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
s = socket.create_connection((host, int(port)), timeout=180)
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


def ev(expr, timeout=180):
    rid = send("Runtime.evaluate", {"expression": expr, "returnByValue": True, "awaitPromise": True})
    t0 = time.time()
    while True:
        if time.time() - t0 > timeout: return "__TIMEOUT__"
        m = recv()
        if m.get("id") == rid:
            r = m.get("result", {})
            if "exceptionDetails" in r:
                return "__ERR__:" + str((r["exceptionDetails"].get("exception", {}) or {}).get("description", ""))[:300]
            return r.get("result", {}).get("value")


send("Page.enable"); send("Runtime.enable")
send("Page.navigate", {"url": URL})
time.sleep(3.2)
print("页面载入:", ev("document.title"), "| 有截图卡:", ev("!!document.getElementById('shot_stage')"))

QUESTIONS = [
    ("梦幻西游中有多少个种族？", ["A、2个", "B、3个", "C、4个"], "3"),
    ("等级达到多少级可以在长安城的副本官员处发起副本", ["A、30级", "B、50级", "C、60级"], "50级"),
]

for i, (q, opts, want) in enumerate(QUESTIONS):
    js = """(async function(){
      var lines = %s;
      var c = document.createElement('canvas');
      c.width = 900; c.height = 60 + lines.length*52;
      var g = c.getContext('2d');
      g.fillStyle = '#1b2233'; g.fillRect(0,0,c.width,c.height);
      g.fillStyle = '#ffffff'; g.font = '30px "Microsoft YaHei", "SimHei", sans-serif';
      g.textBaseline = 'top';
      lines.forEach(function(t, i){ g.fillText(t, 24, 24 + i*52); });
      prepForOcr(c);
      showShotPreview(c);
      await runOcr(c);
      return {
        answer: (document.getElementById('shot_answer').textContent||'').replace(/\\s+/g,' ').trim(),
        ocr: (document.getElementById('shot_ocr').textContent||'').replace(/\\s+/g,' ').trim().slice(0,200)
      };
    })()""" % json.dumps([q] + opts)
    t0 = time.time()
    r = ev(js)
    print("\n--- Q%d (%.1fs) ---" % (i + 1, time.time() - t0))
    if isinstance(r, dict):
        print("识别:", r["ocr"])
        print("结果:", r["answer"])
        print("期望:", "答案：" + want)
    else:
        print("ERR", r)

print("\nexceptions:", len(EXC), EXC[:2])
kill_tree(p.pid)
kill_stale(verbose=False)
