# -*- coding: utf-8 -*-
"""r88 新增验收：盘点单草稿持久化。
   刷新后草稿还在、账面/差异按当前流水重算；确认盘点后草稿清掉；再刷新不再恢复。
   用法: python build\\verify_pan_draft.py <file-url> [port]"""
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
PORT = int(sys.argv[2]) if len(sys.argv) > 2 else 9233
PROF = os.path.join(WS, "shots", "preprof_pandraft")
shutil.rmtree(PROF, ignore_errors=True)
kill_stale(verbose=False)
p = subprocess.Popen([EDGE, "--headless=new", "--disable-gpu", "--hide-scrollbars",
                      "--noerrdialogs", "--disable-crash-reporter", "--disable-breakpad",
                      f"--remote-debugging-port={PORT}", f"--user-data-dir={PROF}",
                      "--window-size=1400,1000", "about:blank"],
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
EXC = []
FAIL = []
PAN_KEY = "mz.sy.inv.pan.v1"


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
        d = msg["params"]["exceptionDetails"]
        EXC.append((d.get("exception", {}) or {}).get("description", str(d))[:300])
    return msg


def ev(expr):
    rid = send("Runtime.evaluate", {"expression": expr, "returnByValue": True})
    while True:
        m = recv()
        if m.get("id") == rid:
            r = m.get("result", {})
            if "exceptionDetails" in r:
                return {"__error__": (r["exceptionDetails"].get("exception", {}) or {}).get("description", "error")}
            return r.get("result", {}).get("value")


def eq(name, got, want):
    ok = str(got) == str(want)
    print(("  PASS  " if ok else "  FAIL  ") + name + "  got=" + repr(got) + " want=" + repr(want))
    if not ok: FAIL.append(name)


def ok_(name, cond, extra=""):
    print(("  PASS  " if cond else "  FAIL  ") + name + ("  " + str(extra) if extra else ""))
    if not cond: FAIL.append(name)


def setv(i, v):
    ev("(function(){var e=document.getElementById('%s');e.value=%s;"
       "e.dispatchEvent(new Event('input',{bubbles:true}));})()" % (i, json.dumps(str(v))))


def pick_cat(key, cat):
    ev("""(function(){
      var gs=[].slice.call(document.querySelectorAll('#%s_gtabs .tb'));
      var g=%s.split(' ')[0];
      for(var i=0;i<gs.length;i++){ if(gs[i].textContent.trim()===g){ gs[i].click(); break; } }
    })()""" % (key, json.dumps(cat)))
    time.sleep(0.15)
    ev("""(function(){
      var cs=[].slice.call(document.querySelectorAll('#%s_chips .cd'));
      for(var i=0;i<cs.length;i++){ if(cs[i].getAttribute('data-k')===%s){ cs[i].click(); return; } }
    })()""" % (key, json.dumps(cat)))
    time.sleep(0.15)


def buy(cat, price, num):
    pick_cat("buy", cat)
    setv("inv_in_price", price); setv("inv_in_num", num)
    ev("document.querySelectorAll('#daomai .inv-entry .line .btn')[0].click()")
    time.sleep(0.3)


def pan_add(cat, real):
    pick_cat("pan", cat)
    setv("inv_pan_num", real)
    ev("document.querySelectorAll('#daomai .inv-count .line .btn')[0].click()")
    time.sleep(0.25)


def pan_go():
    ev("document.querySelectorAll('#daomai .inv-count .line .btn')[1].click()")
    time.sleep(0.4)


def rows():
    return ev("document.querySelectorAll('#inv_pans .r').length")


def pans_text():
    return ev("(document.getElementById('inv_pans')||{}).textContent || ''")


def hint():
    return ev("(document.getElementById('inv_pans_hint')||{}).textContent || ''")


def cmsg():
    return ev("(document.getElementById('inv_cmsg')||{}).textContent || ''")


def draft():
    return ev("(function(){try{var s=localStorage.getItem('%s');return s?JSON.parse(s):null;}catch(e){return 'ERR';}})()" % PAN_KEY)


def open_tab():
    ev("document.querySelector('#tabs button[data-t=\"daomai\"]').click()")
    time.sleep(0.4)


def reload_page():
    send("Page.reload"); time.sleep(3.2); open_tab()


HJ = "环装 80武器"

send("Page.enable"); send("Runtime.enable")
send("Page.navigate", {"url": URL})
time.sleep(3.5)
open_tab()
ev("try{localStorage.removeItem('mz.sy.inv.v1');localStorage.removeItem('%s');}catch(e){}" % PAN_KEY)
reload_page()

print("\n== 1. 加两笔到盘点单，草稿落 localStorage ==")
buy(HJ, 10, 100)
pan_add(HJ, 80)                 # 账面 100 → 实盘 80，出库 20
pan_add("珍珠 150", 5)           # 账面 0 → 实盘 5，盘盈 5
eq("盘点单 2 项", rows(), 2)
ok_("汇总行是「共 2 项」", "共 2 项" in (hint() or ""), hint())
d = draft()
eq("草稿条数", len(d) if isinstance(d, list) else d, 2)
ok_("草稿只存品类 + 实盘", isinstance(d, list) and set(d[0].keys()) == {"cat", "real"}, d)

print("\n== 2. 再进一笔（账面变 120），刷新后草稿还在、差异按新流水重算 ==")
buy(HJ, 10, 20)
reload_page()
eq("刷新后盘点单仍是 2 项", rows(), 2)
t = pans_text() or ""
ok_("80武器 按新账面重算：账面 120 → 实盘 80", "账面 120 → 实盘 80" in t, t[:160])
ok_("80武器 出库 40", "出库 40" in t, t[:160])
ok_("珍珠 盘盈 5 还在", "盘盈 5" in t, t[:160])
ok_("恢复时有提示", "恢复 2 项" in (cmsg() or ""), cmsg())

print("\n== 3. 确认盘点 → 草稿清掉、再刷新不再恢复 ==")
pan_go()
eq("确认后盘点单 0 项", rows(), 0)
eq("确认后草稿键已删", draft(), None)
reload_page()
eq("再刷新 0 项", rows(), 0)
ok_("不再提示恢复", "恢复" not in (cmsg() or ""), cmsg())
eq("流水照常落账（2 进 + 出库 40 + 盘盈 5）", ev("INV.log.length"), 4)

print("\nexceptions:", len(EXC), EXC[:3])
kill_tree(p.pid)
print("\nFAILED:", len(FAIL), FAIL)
sys.exit(1 if FAIL else 0)
