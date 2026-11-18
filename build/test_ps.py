# -*- coding: utf-8 -*-
"""跑商页（V5.3 r56）回归：未校准 → 校准 → 开始/暂停 → 加/减秒 → 捉妖香 → 迷你版 → 计算器 → 刷新保持。
用法: python build\\test_ps.py <file-url> [port]
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
PORT = int(sys.argv[2]) if len(sys.argv) > 2 else 9360
W = int(os.environ.get("SHOT_W", "1300"))
PROF = os.path.join(WS, "shots", "preprof_ps")
OUTD = os.path.join(WS, "shots", "ps_r56")
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
    rid = send("Runtime.evaluate", {"expression": expr, "returnByValue": True, "awaitPromise": False})
    while True:
        m = recv()
        if m.get("id") == rid:
            r = m.get("result", {})
            if r.get("exceptionDetails"):
                return {"__err": r["exceptionDetails"].get("text", "err")}
            return r.get("result", {}).get("value")


def shot(name, full=True):
    h = ev("Math.max(document.body.scrollHeight, document.documentElement.scrollHeight)")
    params = {"format": "png"}
    if full:
        params["captureBeyondViewport"] = True
        params["clip"] = {"x": 0, "y": 0, "width": W, "height": min(4200, int(h or 900)), "scale": 1}
    rid = send("Page.captureScreenshot", params)
    while True:
        m = recv()
        if m.get("id") == rid:
            open(os.path.join(OUTD, name), "wb").write(base64.b64decode(m["result"]["data"]))
            return


FAILS = []


def check(name, cond, detail=""):
    print(("PASS " if cond else "FAIL ") + name + ("" if cond else "  -> " + str(detail)))
    if not cond:
        FAILS.append(name)


def txt(jid):
    return ev('document.getElementById("%s").textContent' % jid)


def inum(jid):
    v = txt(jid)
    try:
        return float(v)
    except Exception:
        return None


send("Page.enable")
send("Runtime.enable")
send("Page.addScriptToEvaluateOnNewDocument", {
    "source": "window.__errs=[];window.addEventListener('error',function(e){window.__errs.push(String(e.message)+' @'+String(e.lineno))});"
              "window.addEventListener('unhandledrejection',function(e){window.__errs.push('rej:'+String(e.reason))});"})
send("Emulation.setDeviceMetricsOverride", {"width": W, "height": 900, "deviceScaleFactor": 1, "mobile": False})
send("Page.navigate", {"url": URL})
time.sleep(3.5)
ev("localStorage.removeItem('mz.ps.v1')")
send("Page.reload")
time.sleep(3.0)
ev("document.querySelector('#tabs button[data-t=\"paoshang\"]').click()")
time.sleep(0.5)

# 1 初始
check("初始 离下个时辰 = 0", inum("ps-cd-sc") == 0, txt("ps-cd-sc"))
check("初始 离下次刷价 = 0", inum("ps-cd-price") == 0, txt("ps-cd-price"))
check("初始 捉妖香 = —", txt("ps-cd-xiang") == "—", txt("ps-cd-xiang"))
check("初始 无高亮时辰", ev("document.querySelectorAll('#ps-strip .on').length") == 0)
shot("ps_01_initial.png")

# 2 未校准点开始
ev("document.getElementById('ps-start').click()")
time.sleep(0.3)
check("未校准点开始 → 弹出校准", ev("document.getElementById('ps-cal').classList.contains('on')") is True)
check("未校准点开始 → 没开始跑", ev("JSON.parse(localStorage.getItem('mz.ps.v1')).at === null"))
shot("ps_02_needcal.png")

# 3 校准到 辰时 30 秒
ev('document.getElementById("ps-cal-sc").value="4";'
   'document.getElementById("ps-cal-sec").value="30";'
   'document.getElementById("ps-cal-ok").click()')
time.sleep(0.3)
check("校准后 离下个时辰 = 120", inum("ps-cd-sc") == 120, txt("ps-cd-sc"))
check("校准后 离下次刷价 = 580", inum("ps-cd-price") == 580, txt("ps-cd-price"))
check("校准后高亮辰", ev("document.querySelector('#ps-strip .c.on').dataset.i") == "4",
      ev("document.querySelector('#ps-strip .c.on') && document.querySelector('#ps-strip .c.on').dataset.i"))
check("校准后 提示收起", ev("document.getElementById('ps-cal').classList.contains('on')") is False)
shot("ps_03_cal.png")

# 4 开始 → 走秒
ev("document.getElementById('ps-start').click()")
time.sleep(3.2)
run_sc = inum("ps-cd-sc")
run_pr = inum("ps-cd-price")
check("开始后 3.2s 剩余 116~119", run_sc is not None and 116 <= run_sc <= 119, run_sc)
check("开始后 刷价倒计时 575~580", run_pr is not None and 574 <= run_pr <= 580, run_pr)
shot("ps_04_running.png")

# 5 暂停后冻结
ev("document.getElementById('ps-pause').click()")
time.sleep(0.2)
p1 = inum("ps-cd-sc")
time.sleep(2.2)
p2 = inum("ps-cd-sc")
check("暂停后 2.2s 不再走", p1 == p2, (p1, p2))

# 6 加/减 1 秒
ev("document.getElementById('ps-add').click()"); time.sleep(0.2)
p3 = inum("ps-cd-sc")
check("加1秒 → 剩余少 1", p3 == p2 - 1, (p2, p3))
ev("document.getElementById('ps-sub').click()"); time.sleep(0.2)
p4 = inum("ps-cd-sc")
check("减1秒 → 回到原值", p4 == p2, (p2, p4))

# 7 捉妖香
ev("document.getElementById('ps-xiang-use').click()"); time.sleep(0.4)
check("捉妖香 使用 → 30 分", inum("ps-cd-xiang") == 30, txt("ps-cd-xiang"))
ev("document.getElementById('ps-xiang-clear').click()"); time.sleep(0.3)
check("捉妖香 清除 → —", txt("ps-cd-xiang") == "—", txt("ps-cd-xiang"))

# 8 迷你版 / 原版
ev("document.getElementById('ps-mini-on').click()"); time.sleep(0.3)
check("迷你版 → 价目表隐藏", ev("getComputedStyle(document.querySelector('#paoshang .ps-price')).display") == "none")
shot("ps_05_mini.png")
ev("document.getElementById('ps-mini-off').click()"); time.sleep(0.3)
check("原版 → 价目表回来", ev("getComputedStyle(document.querySelector('#paoshang .ps-price')).display") != "none")

# 9 计算器
ev("document.getElementById('ps-calc-open').click()"); time.sleep(0.3)
check("计算器打开", ev("document.getElementById('ps-calc').classList.contains('on')") is True)
ev('document.getElementById("ps-calc-in").value="(3000-2800)*2";'
   'document.getElementById("ps-calc-do").click()')
time.sleep(0.2)
check("计算器 (3000-2800)*2 = 400", txt("ps-calc-r") == "400", txt("ps-calc-r"))
shot("ps_06_calc.png")
ev("document.getElementById('ps-calc-x').click()"); time.sleep(0.2)

# 10 刷新后状态保持
before = inum("ps-cd-sc")
send("Page.reload"); time.sleep(3.0)
ev("document.querySelector('#tabs button[data-t=\"paoshang\"]').click()")
time.sleep(0.5)
check("刷新后 剩余秒数保持", inum("ps-cd-sc") == before, (before, inum("ps-cd-sc")))
check("刷新后 高亮辰保持", ev("document.querySelector('#ps-strip .c.on').dataset.i") == "4")
check("刷新后 提示已校准", "已校准" in (txt("ps-tip-hi") or ""), txt("ps-tip-hi"))
check("刷新后 开始可用 / 暂停置灰",
      ev("document.getElementById('ps-start').disabled") is False
      and ev("document.getElementById('ps-pause').disabled") is True)

# 10b 刷价提醒：校准到子时 5 秒，跑 7 秒必须穿过 子时+10 秒 的刷价点
ev("document.getElementById('ps-reset').click()"); time.sleep(0.3)
ev('document.getElementById("ps-sync-open").click()'); time.sleep(0.2)
ev('document.getElementById("ps-cal-sc").value="0";'
   'document.getElementById("ps-cal-sec").value="5";'
   'document.getElementById("ps-cal-ok").click()')
time.sleep(0.2)
ev("document.getElementById('ps-start').click()"); time.sleep(0.4)
check("开始后 开始置灰 / 暂停可用",
      ev("document.getElementById('ps-start').disabled") is True
      and ev("document.getElementById('ps-pause').disabled") is False)
time.sleep(6.6)
check("穿过子时刷价点 → 记录里有刷买价",
      "刷买价" in (ev("document.getElementById('ps-log').textContent") or ""),
      ev("document.getElementById('ps-log').textContent"))
check("穿过子时刷价点 → 弹提示",
      "刷买价" in (ev("document.getElementById('ps-toast').textContent") or "")
      and ev("document.getElementById('ps-toast').classList.contains('on')") is True,
      ev("document.getElementById('ps-toast').textContent"))
shot("ps_08_price_toast.png")
ev("document.getElementById('ps-pause').click()"); time.sleep(0.2)

# 11 窄屏
send("Emulation.setDeviceMetricsOverride", {"width": 760, "height": 900, "deviceScaleFactor": 1, "mobile": False})
time.sleep(0.6)
cols = ev("getComputedStyle(document.querySelector('#ps-strip')).gridTemplateColumns.split(' ').length")
check("760px 时辰条 6 列", cols == 6, cols)
check("760px 无横向溢出", ev("document.documentElement.scrollWidth - document.documentElement.clientWidth") <= 0,
      ev("document.documentElement.scrollWidth - document.documentElement.clientWidth"))
shot("ps_07_760.png", full=False)

# 11b 手机宽度
send("Emulation.setDeviceMetricsOverride", {"width": 390, "height": 844, "deviceScaleFactor": 1, "mobile": True})
time.sleep(0.6)
check("390px 无横向溢出", ev("document.documentElement.scrollWidth - document.documentElement.clientWidth") <= 0,
      ev("document.documentElement.scrollWidth - document.documentElement.clientWidth"))
shot("ps_09_390.png", full=False)

# 12 控制台异常
errs = ev("JSON.stringify(window.__errs || [])")
check("无 JS 异常", errs in ("[]", None), errs)

send("Emulation.setDeviceMetricsOverride", {"width": 1300, "height": 900, "deviceScaleFactor": 1, "mobile": False})
print("FAILS:", FAILS)
kill_tree(p.pid)
kill_stale(verbose=True)
sys.exit(0 if not FAILS else 1)
