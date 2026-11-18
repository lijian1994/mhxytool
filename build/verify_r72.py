# -*- coding: utf-8 -*-
"""r72 结构自查：页签改名/顺序、常用查询卡片弹层、红蓝秘制/环怪卡、切页签关浮层。"""
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
PROF = os.path.join(WS, "shots", "preprof_r72")
OUTD = os.path.join(WS, "shots", "r72")
shutil.rmtree(PROF, ignore_errors=True)
shutil.rmtree(OUTD, ignore_errors=True)
os.makedirs(OUTD, exist_ok=True)
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


def shot(name):
    h = ev("Math.max(document.body.scrollHeight, document.documentElement.scrollHeight)")
    rid = send("Page.captureScreenshot", {"format": "png", "captureBeyondViewport": True,
                                          "clip": {"x": 0, "y": 0, "width": ev("innerWidth"),
                                                   "height": min(4200, int(h)), "scale": 1}})
    while True:
        m = recv()
        if m.get("id") == rid:
            open(os.path.join(OUTD, name), "wb").write(base64.b64decode(m["result"]["data"]))
            return


def tab(t):
    ev("document.querySelector('#tabs button[data-t=\"%s\"]').click()" % t)
    time.sleep(0.45)


send("Page.enable"); send("Runtime.enable")
send("Emulation.setDeviceMetricsOverride", {"width": 1400, "height": 1000, "deviceScaleFactor": 1, "mobile": False})
send("Page.navigate", {"url": URL})
time.sleep(3.5)

print("\n== 页签 ==")
labels = ev("[...document.querySelectorAll('#tabs button')].map(b=>b.dataset.t+':'+b.textContent.trim())")
print("   ", labels)
eq("页签数量", ev("document.querySelectorAll('#tabs button').length"), 10)
eq("顺序", "|".join(x.split(":")[0] for x in labels),
   "daomai|shouyi|quiz|renwu|jiadian|jzb|baoshi|gonglue|paoshang|about")
for t, name in (("daomai", "库存管理"), ("shouyi", "挂机体活"), ("quiz", "智能答题"), ("renwu", "常用查询"),
                ("jiadian", "模拟加点"), ("jzb", "刷子记账"), ("baoshi", "宝石合成"), ("gonglue", "梦幻常识"),
                ("paoshang", "梦幻时钟"), ("about", "关于")):
    ok_("标签 " + t + " = " + name, (name in (ev("document.querySelector('#tabs button[data-t=\"%s\"]').textContent" % t) or "")))

print("\n== 常用查询：卡片网格 ==")
tab("renwu")
eq("卡片数（10 张查询 + 红蓝秘制）", ev("document.querySelectorAll('#renwu .pc').length"), 11)
eq("没有遗留的旧列布局", ev("document.querySelectorAll('#renwu .mz').length"), 0)
ok_("卡片默认收起", ev("document.querySelectorAll('#renwu .pc.open').length") == 0)
shot("01_常用查询.png")

print("\n== 打开卡片 → 弹层 ==")
ev("document.querySelectorAll('#renwu .pc')[0].click()")
time.sleep(0.35)
ok_("第一张卡打开", ev("document.querySelectorAll('#renwu .pc.open').length") == 1)
ok_("遮罩显示", ev("document.getElementById('qc_mask').classList.contains('on')"))
ok_("面板是 fixed", ev("getComputedStyle(document.querySelector('#renwu .pc.open .pc-body')).position") == "fixed")
ok_("面板里有标题条", ev("!!document.querySelector('#renwu .pc.open .pc-ph')"))
ok_("面板里的输入框可用", ev("!!document.querySelector('#renwu .pc.open #e1')"))
# 实际算一次
ev("(function(){var a=document.getElementById('e1'),b=document.getElementById('e2');a.value='0';b.value='100';})()")
ev("document.querySelector('#renwu .pc.open .btn').click()")
time.sleep(0.3)
val = ev("document.getElementById('e_out').textContent")
ok_("计算按钮在弹层里能用", val not in (None, "", "—"), val)
shot("02_卡片弹层.png")


print("\n== 只能开一个 / 关闭方式 ==")
ev("document.querySelectorAll('#renwu .pc')[3].click()")
time.sleep(0.3)
eq("同时只开一个", ev("document.querySelectorAll('#renwu .pc.open').length"), 1)
ok_("开的是第 4 张", ev("document.querySelectorAll('#renwu .pc')[3].classList.contains('open')"))
ev("document.querySelector('#renwu .pc.open .pc-x').click()")
time.sleep(0.25)
eq("× 关闭", ev("document.querySelectorAll('#renwu .pc.open').length"), 0)
ok_("遮罩收起", not ev("document.getElementById('qc_mask').classList.contains('on')"))
ev("dispatchEvent(new KeyboardEvent('keydown',{key:'Escape'}))")
time.sleep(0.2)

print("\n== 红蓝秘制卡片 ==")
ev("document.querySelector('#renwu #mizhi').click()")
time.sleep(0.35)
ok_("红蓝秘制卡打开", ev("document.querySelector('#renwu #mizhi').classList.contains('open')"))
ok_("里面有 mz_p 输入", ev("!!document.querySelector('#renwu #mizhi #mz_p')"))
ev("(function(){var p=document.getElementById('mz_p');p.value='6500';p.dispatchEvent(new Event('input',{bubbles:true}));"
   "var w=document.getElementById('mz_w');w.value='4';w.dispatchEvent(new Event('input',{bubbles:true}));})()")
time.sleep(0.4)
eq("第 4 周红储量", ev("document.getElementById('mz_hr').textContent"), "119,000")
shot("03_红蓝秘制卡.png")
ev("document.querySelector('#renwu #mizhi .pc-x').click()")
time.sleep(0.2)

print("\n== 梦幻常识：环怪卡 ==")
tab("gonglue")
eq("攻略卡数量（6 + 环怪）", ev("document.querySelectorAll('#gonglue .cg').length"), 7)
ok_("环怪卡在网格里", ev("!!document.querySelector('#gonglue .gl-grid #qita')"))
ev("document.querySelector('#gonglue #qita .cg-head').click()")
time.sleep(0.4)
ok_("环怪面板打开", ev("document.querySelector('#gonglue #qita').classList.contains('open')"))
ok_("环怪列表在", ev("document.querySelectorAll('#qita .hg-item').length") > 0,
    ev("document.querySelectorAll('#qita .hg-item').length"))
eq("环怪数量", ev("document.querySelectorAll('#qita .hg-item').length"), 23)
ev("document.querySelectorAll('#qita .hg-item')[0].click()")
time.sleep(0.3)
ok_("点环怪出详情", (ev("document.querySelector('#qita .hg-title').textContent") or "").strip() != "")
shot("04_环怪卡.png")
ev("dispatchEvent(new KeyboardEvent('keydown',{key:'Escape'}))")
time.sleep(0.3)

print("\n== 切页签关浮层 ==")
ev("document.querySelector('#gonglue #qita .cg-head').click()")
time.sleep(0.3)
tab("baoshi")
ok_("切页签后环怪面板关闭", not ev("document.querySelector('#gonglue #qita').classList.contains('open')"))
tab("renwu")
ev("document.querySelectorAll('#renwu .pc')[1].click()")
time.sleep(0.3)
tab("daomai")
ok_("切页签后常用查询弹层关闭", ev("document.querySelectorAll('#renwu .pc.open').length") == 0)
ok_("遮罩也关了", not ev("document.getElementById('qc_mask').classList.contains('on')"))

print("\n== 关于页：不再是「复刻」口吻 ==")
tab("about")
ok_("关于页正文没有「复刻」", "复刻" not in (ev("document.getElementById('about').textContent") or ""))
ok_("页头没有「复刻」", "复刻" not in (ev("document.querySelector('.tbar').textContent") or ""), ev("document.querySelector('.tbar').textContent"))
ok_("页脚没有「复刻」", "复刻" not in (ev("document.querySelector('.sbar').textContent") or ""), ev("document.querySelector('.sbar').textContent"))
ok_("浏览器标题没有「复刻」", "复刻" not in (ev("document.title") or ""), ev("document.title"))
ok_("关于页正文没有「原工具」", "原工具" not in (ev("document.getElementById('about').textContent") or ""))
eq("关于页有 9 行页签一览", ev("document.querySelectorAll('#about .ab-tbl tr').length"), 9)
shot("05_关于.png")

print("\n== JS 异常 ==")
ok_("无 JS 异常", len(EXC) == 0, EXC[:3])

print("\n截图: " + OUTD)
kill_tree(p.pid)
kill_stale(verbose=True)
print("\nFAILED: %d" % len(FAIL))
for f in FAIL:
    print("  - " + f)
sys.exit(1 if FAIL else 0)
