# -*- coding: utf-8 -*-
"""帮贡两个口径的回归验收（原 check_r43.py，r89 改成永久脚本名）：
  需要帮贡     = 这一段实际消耗 = bg[到]-bg[从]
  学习需求帮贡 = 本段消耗 + 5×目标等级 − 目标等级（点最后一级前要有的余额门槛）
用法: python build\\verify_banggong.py <url> [port]
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
PORT = int(sys.argv[2]) if len(sys.argv) > 2 else 9322
PROF = os.path.join(WS, "shots", "preprof_banggong")
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


send("Page.enable"); send("Runtime.enable")
send("Page.navigate", {"url": URL})
time.sleep(3.5)
ev("document.querySelector('#tabs button[data-t=\"renwu\"]').click()")
time.sleep(0.6)
R = []


def run(skill, a, b):
    ev("""(function(){
      document.getElementById('life_skill').value='%s';
      document.getElementById('life_a').value='%d';
      document.getElementById('life_b').value='%d';
      calcLife();
    })()""" % (skill, a, b))
    time.sleep(0.15)
    return ev("document.getElementById('life_bg').textContent"), ev("document.getElementById('life_req').textContent")


def chk(name, got, want):
    R.append({"name": name, "got": got, "want": want, "ok": str(got) == str(want)})


for skill, a, b, need, req, label in [
    ("201", 0, 1, "1 点", "5 点", "强身术 0→1"),
    ("201", 99, 100, "100 点", "500 点", "强身术 99→100（单级）"),
    ("201", 0, 100, "5,050 点", "5,450 点", "强身术 0→100"),
    ("201", 100, 140, "4,820 点", "5,380 点", "强身术 100→140"),
    ("203", 100, 120, "2,210 点", "2,690 点", "暗器技巧 100→120"),
    ("203", 100, 160, "7,830 点", "8,470 点", "暗器技巧 100→160"),
]:
    got_need, got_req = run(skill, a, b)
    chk(label + " 需要帮贡", got_need, need)
    chk(label + " 需求帮贡", got_req, req)

out = {"checks": R, "exceptions": EXC}
open(os.path.join(WS, "shots", "verify_banggong.json"), "w", encoding="utf-8").write(json.dumps(out, ensure_ascii=False, indent=1))
FAILS = [c for c in R if not c["ok"]]
for c in R:
    print(("  OK  " if c["ok"] else "  FAIL"), c["name"], "->", c["got"], "期望", c["want"])
print("exceptions:", len(EXC))
print("FAILED:", len(FAILS), [c["name"] for c in FAILS])
kill_tree(p.pid)
kill_stale(verbose=True)
sys.exit(1 if FAILS or EXC else 0)
