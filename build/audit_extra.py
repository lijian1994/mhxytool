# -*- coding: utf-8 -*-
"""补充定向检查：速查按钮、宝石数值、复制、答题器窗口选择、记账本 localStorage 记忆。"""
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
PORT = int(sys.argv[2]) if len(sys.argv) > 2 else 9280
PROF = os.path.join(WS, "shots", "preprof_extra")
shutil.rmtree(PROF, ignore_errors=True)
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


def tab(t):
    ev("document.querySelector('#tabs button[data-t=\"%s\"]').click()" % t)
    time.sleep(0.45)


def vis():
    return ev("[...document.querySelectorAll('section')].filter(s=>getComputedStyle(s).display!=='none').map(s=>s.id).join(',')")


send("Page.enable"); send("Runtime.enable")
send("Page.navigate", {"url": URL})
time.sleep(3.5)
R = []


def chk(name, got, want):
    R.append({"name": name, "got": got, "want": want, "ok": str(got) == str(want)})


# 1) 速查按钮
tab("renwu")
ev("document.querySelector('#renwu button[onclick=\"quick(69)\"]').click()")
time.sleep(0.5)
chk("人物·速查「69 级」-> 人物等级", ev("document.getElementById('c1').value"), "69")
chk("人物·速查后停在人物页", vis(), "renwu")

# 2) 宝石三个计算器
tab("baoshi")
ev("""(function(){var t=document.getElementById('b_type'); t.value='2';
      document.getElementById('b_lv').value='10'; document.getElementById('b_price').value='100';
      calcGemB();})()""")
time.sleep(0.2)
chk("宝石·红玛瑙 2^9 个", ev("document.getElementById('b_cnt').textContent"), "512")
chk("宝石·红玛瑙 总价", ev("document.getElementById('b_cost').textContent"), "51,200")
ev("""(function(){document.getElementById('x_lv').value='5'; document.getElementById('x_price').value='10'; calcGemX();})()""")
time.sleep(0.2)
chk("宝石·星辉石 3^4 个", ev("document.getElementById('x_cnt').textContent"), "81")
ev("""(function(){document.getElementById('w_lv').value='10'; document.getElementById('w_price').value='1'; calcGemW();})()""")
time.sleep(0.2)
chk("宝石·五色石第 10 级颗数", ev("document.getElementById('w_cnt').textContent"), "2,378")
ev("""(function(){document.getElementById('w_lv').value='16'; calcGemW();})()""")
time.sleep(0.2)
chk("宝石·超上限提示", ev("document.getElementById('w_cnt').textContent"), "上限 15 级")

# 3) 攻略：点句子复制（走 data-copy + toast）
tab("gonglue")
dc = ev("document.querySelector('#gonglue [data-copy]').getAttribute('data-copy')")
ev("document.querySelector('#gonglue [data-copy]').click()")
time.sleep(0.4)
chk("攻略·复制句子的提示", ev("document.querySelector('#gonglue .gl-toast').textContent").strip(), "已复制")
R.append({"name": "攻略·被复制的句子", "got": dc, "ok": bool(dc), "detail": "data-copy 长度 %d" % len(dc or "")})
ev("document.getElementById('fj-copy-all').click()")
time.sleep(0.4)
chk("攻略·复制全部 16 句", ev("document.querySelectorAll('#gonglue .fj-line').length"), 16)

# 4) 答题器：窗口选择（无头环境应给出提示而不是把页面搞崩）
tab("quiz")
n0 = len(EXC)
ev("document.getElementById('qsearch').value=''; pickWindow()")
time.sleep(1.2)
R.append({"name": "答题器·选窗口后提示", "got": ev("document.getElementById('shot_state').textContent"), "ok": True})
R.append({"name": "答题器·选窗口未抛未捕获异常", "got": len(EXC) - n0, "want": 0, "ok": (len(EXC) - n0) == 0})
chk("答题器·页面仍可用（能搜索）", bool(ev("(function(){var q=document.getElementById('qsearch'); q.value='师门'; searchQuiz(); return document.querySelectorAll('#qlist .quizitem').length>0;})()")), True)

# 5) 记账本：localStorage 记忆（记录 + 价格）
tab("jzb")
ev("document.querySelector('#item1 .item_list li').click()")
time.sleep(0.3)
ev("""(function(){var ta=document.querySelector('#jzb-pop textarea'); if(!ta) return; ta.value='33';
      document.querySelector('#jzb-pop .ok').click();})()""")
time.sleep(0.3)
ev("document.querySelector('#item1 .item_list li').click()")
time.sleep(0.3)
rows_before = ev("document.querySelectorAll('#jzb .record_table tbody tr').length")
send("Page.reload", {"ignoreCache": False})
time.sleep(3.0)
tab("jzb")
time.sleep(0.4)
chk("记账本·刷新后记录还在", ev("document.querySelectorAll('#jzb .record_table tbody tr').length"), rows_before)
chk("记账本·刷新后价格标记还在", ev("document.querySelectorAll('#item1 .item_list li.i_set').length") > 0, True)
R.append({"name": "记账本·刷新后记录条数", "got": rows_before, "ok": rows_before >= 1})

out = {"checks": R, "exceptions": EXC}
open(os.path.join(WS, "shots", "audit_extra.json"), "w", encoding="utf-8").write(
    json.dumps(out, ensure_ascii=False, indent=1))
for c in R:
    print(("  OK  " if c["ok"] else "  FAIL"), c["name"], "->", str(c.get("got"))[:60],
          ("期望 " + str(c.get("want"))) if "want" in c else "", c.get("detail", ""))
print("exceptions:", len(EXC), EXC[:3])
kill_tree(p.pid)
kill_stale(verbose=True)
