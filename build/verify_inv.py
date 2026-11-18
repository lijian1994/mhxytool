# -*- coding: utf-8 -*-
"""库存管理（r86：进货/盘点都用「标签+卡片」）验收。"""
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
PORT = int(sys.argv[2]) if len(sys.argv) > 2 else 9274
PROF = os.path.join(WS, "shots", "preprof_inv")
OUTD = os.path.join(WS, "shots", "inv_r86")
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


def txt(i):
    return ev(f"(document.getElementById('{i}')||{{}}).textContent")


def cell(r, c):
    return ev(f"((document.querySelectorAll('#inv_body tr')[{r}]||{{children:[]}}).children[{c}]||{{}}).textContent")


def rowidx(cat):
    return ev("""(function(){
      var nm=%s;
      var rs=document.querySelectorAll('#inv_body tr');
      for(var i=0;i<rs.length;i++){ if(rs[i].children[0].textContent.trim()===nm) return i; }
      return -1;})()""" % json.dumps(cat.split(' ')[-1]))


def eq(name, got, want):
    ok = str(got) == str(want)
    print(("  PASS  " if ok else "  FAIL  ") + name + "  got=" + repr(got) + " want=" + repr(want))
    if not ok: FAIL.append(name)


def ok_(name, cond, extra=""):
    print(("  PASS  " if cond else "  FAIL  ") + name + ("  " + str(extra) if extra else ""))
    if not cond: FAIL.append(name)


def shot(name, full=True):
    h = ev("Math.max(document.body.scrollHeight, document.documentElement.scrollHeight)")
    pr = {"format": "png"}
    if full:
        pr["captureBeyondViewport"] = True
        pr["clip"] = {"x": 0, "y": 0, "width": ev("innerWidth"), "height": min(4200, int(h)), "scale": 1}
    rid = send("Page.captureScreenshot", pr)
    while True:
        m = recv()
        if m.get("id") == rid:
            open(os.path.join(OUTD, name), "wb").write(base64.b64decode(m["result"]["data"]))
            return


def setv(i, v):
    ev("(function(){var e=document.getElementById('%s');e.value=%s;"
       "e.dispatchEvent(new Event('input',{bubbles:true}));})()" % (i, json.dumps(str(v))))


def pick(i, v):
    ev("(function(){var e=document.getElementById('%s');e.value=%s;"
       "e.dispatchEvent(new Event('change',{bubbles:true}));})()" % (i, json.dumps(v)))


def pick_group(key, grp):
    ev("""(function(){
      var gs=[].slice.call(document.querySelectorAll('#%s_gtabs .tb'));
      for(var i=0;i<gs.length;i++){ if(gs[i].textContent.trim()===%s){ gs[i].click(); return; } }
    })()""" % (key, json.dumps(grp)))
    time.sleep(0.2)


def pick_cat(key, cat):
    pick_group(key, cat.split(' ')[0])
    ev("""(function(){
      var cs=[].slice.call(document.querySelectorAll('#%s_chips .cd'));
      for(var i=0;i<cs.length;i++){ if(cs[i].getAttribute('data-k')===%s){ cs[i].click(); return; } }
    })()""" % (key, json.dumps(cat)))
    time.sleep(0.2)


def buy(cat, price, num):
    pick_cat("buy", cat)
    setv("inv_in_price", price); setv("inv_in_num", num)
    ev("document.querySelectorAll('#daomai .inv-entry .line .btn')[0].click()")
    time.sleep(0.25)


def pan_add(cat, real):
    pick_cat("pan", cat)
    setv("inv_pan_num", real)
    ev("document.querySelectorAll('#daomai .inv-count .line .btn')[0].click()")
    time.sleep(0.25)


def pan_go():
    ev("document.querySelectorAll('#daomai .inv-count .line .btn')[1].click()")
    time.sleep(0.3)


HJ = "环装 80武器"
HJN = "80武器"

send("Page.enable"); send("Runtime.enable")
send("Emulation.setDeviceMetricsOverride", {"width": 1400, "height": 1000, "deviceScaleFactor": 1, "mobile": False})
send("Page.navigate", {"url": URL})
time.sleep(3.5)
ev("document.querySelector('#tabs button[data-t=\"daomai\"]').click()")
time.sleep(0.4)
ev("try{localStorage.removeItem('mz.sy.inv.v1');}catch(e){}")
send("Page.reload"); time.sleep(3.0)
ev("document.querySelector('#tabs button[data-t=\"daomai\"]').click()")
time.sleep(0.5)

print("\n== 1. 进货 / 盘点 都是标签 + 卡片 ==")
eq("进货分组数", ev("document.querySelectorAll('#buy_gtabs .tb').length"), 5)
eq("盘点分组数", ev("document.querySelectorAll('#pan_gtabs .tb').length"), 5)
ok_("进货没有下拉框了", ev("!document.getElementById('inv_in_cat')"))
ok_("盘点没有下拉框了", ev("!document.getElementById('inv_pan_cat')"))
eq("进货默认分组卡片（环装 6）", ev("document.querySelectorAll('#buy_chips .cd').length"), 6)
pick_group("buy", "宝石")
eq("切到宝石 9 张卡", ev("document.querySelectorAll('#buy_chips .cd').length"), 9)
pick_group("buy", "兽诀")
eq("兽诀 7 张卡", ev("document.querySelectorAll('#buy_chips .cd').length"), 7)
pick_group("buy", "珍珠")
eq("珍珠 7 张卡", ev("document.querySelectorAll('#buy_chips .cd').length"), 7)
pick_group("buy", "常规消耗")
eq("常规消耗 7 张卡", ev("document.querySelectorAll('#buy_chips .cd').length"), 7)
pick_group("buy", "环装")
shot("01_进货卡片.png")

print("\n== 2. 进货 ==")
buy(HJ, 12, 50)
eq("库存表 1 行", ev("document.querySelectorAll('#inv_body tr').length"), 1)
eq("品类（短名）", cell(0, 0), HJN)
eq("账面", cell(0, 1), "50")
eq("平均成本", cell(0, 2), "12.00")
eq("库存金额", cell(0, 3), "600.00")
eq("合计库存占用", txt("inv_amt"), "600.00")
ok_("记完清空选中（名字回占位）", txt("buy_name") == "先点一个品类", txt("buy_name"))
buy(HJ, 15, 50)
eq("二次进货后均价 13.50", cell(0, 2), "13.50")
eq("库存金额 1,350.00", cell(0, 3), "1,350.00")

print("\n== 3. 进货走势：同一天同价合并 ==")
buy(HJ, 12, 10)
pick("inv_trend_cat", HJ)
time.sleep(0.3)
eq("价格点数（12 / 15 两点）", ev("document.querySelectorAll('#inv_chart svg circle').length"), 2)
ok_("统计里注明「同价合并」", "同价合并" in (ev("document.getElementById('inv_stats').textContent") or ""),
    ev("document.getElementById('inv_stats').textContent"))
ok_("件数包含合并的那笔（50+50+10）", "110" in (ev("document.getElementById('inv_stats').textContent") or ""))
ev("document.querySelectorAll('#inv_log .inv-x')[0].click()")
time.sleep(0.3)
eq("撤销后库存回 100", cell(0, 1), "100")

print("\n== 4. 盘点：点卡片 → 填实盘 → 加入盘点单 ==")
pick_cat("pan", HJ)
eq("点卡片后显示账面 100", txt("inv_pan_book"), "100")
ok_("已选显示品类名", txt("pan_name") == HJN, txt("pan_name"))
setv("inv_pan_num", 80)
time.sleep(0.2)
eq("出库实时算 20", txt("inv_pan_out"), "20")
ev("document.querySelectorAll('#daomai .inv-count .line .btn')[0].click()")
time.sleep(0.25)
eq("盘点单 1 项", ev("document.querySelectorAll('#inv_pans .r').length"), 1)
ok_("盘点单里写着出库 20", "出库 20" in (ev("document.getElementById('inv_pans').textContent") or ""),
    ev("document.getElementById('inv_pans').textContent"))
eq("加入后库存还没变（要等确认）", cell(0, 1), "100")
shot("02_盘点单.png")
pan_go()
eq("确认后库存变 80", cell(0, 1), "80")
eq("确认后库存金额 1,080.00", cell(0, 3), "1,080.00")
eq("确认后盘点单清空", ev("document.querySelectorAll('#inv_pans .r').length"), 0)
ok_("流水最新一条标「盘」", "盘" == (ev("document.querySelector('#inv_log .r .k').textContent") or "").strip())

print("\n== 5. 多个品类一起确认 ==")
buy("珍珠 150", 2, 100)
pan_add(HJ, 85)
pan_add("珍珠 150", 90)
eq("盘点单 2 项", ev("document.querySelectorAll('#inv_pans .r').length"), 2)
ok_("汇总行", "共 2 项" in (ev("document.getElementById('inv_pans_hint').textContent") or ""),
    ev("document.getElementById('inv_pans_hint').textContent"))
pan_go()
eq("盘盈后环装 85", cell(rowidx(HJ), 1), "85")
eq("环装金额 1,147.50", cell(rowidx(HJ), 3), "1,147.50")
eq("珍珠出库后 90", cell(rowidx("珍珠 150"), 1), "90")

print("\n== 6. 没差异的不让加 ==")
n0 = ev("document.querySelectorAll('#inv_log .r').length")
pick_cat("pan", HJ); setv("inv_pan_num", 85)
ev("document.querySelectorAll('#daomai .inv-count .line .btn')[0].click()")
time.sleep(0.25)
ok_("提示没差异", "没有差异" in (ev("document.getElementById('inv_cmsg').textContent") or ""),
    ev("document.getElementById('inv_cmsg').textContent"))
eq("盘点单仍是 0 项", ev("document.querySelectorAll('#inv_pans .r').length"), 0)
eq("流水条数没变", ev("document.querySelectorAll('#inv_log .r').length"), n0)

print("\n== 7. 现金 + 资产快照 ==")
setv("inv_cash", 400)
time.sleep(0.2)
eq("总资产 = 400 + (1147.50 + 180)", txt("inv_asset"), "1,727.50")
pan_add(HJ, 80)
pan_go()
eq("盘点记录 1 条", ev("document.querySelectorAll('#inv_snaps .r').length"), 1)
ok_("快照里有总资产 1,660.00",
    "1,660.00" in (ev("document.querySelector('#inv_snaps .r').textContent") or ""),
    ev("document.querySelector('#inv_snaps .r').textContent"))
shot("03_盘点记录.png")

print("\n== 8. 刷新保持 ==")
send("Page.reload"); time.sleep(3.0)
ev("document.querySelector('#tabs button[data-t=\"daomai\"]').click()")
time.sleep(0.5)
eq("刷新后环装库存 80", cell(rowidx(HJ), 1), "80")
eq("刷新后现金 400", txt("inv_cash_v"), "400.00")
eq("刷新后盘点记录 1 条", ev("document.querySelectorAll('#inv_snaps .r').length"), 1)

print("\n== 9. 窄屏 ==")
for w, h, name in ((760, 900, "04_w760.png"), (390, 844, "05_w390.png")):
    send("Emulation.setDeviceMetricsOverride", {"width": w, "height": h, "deviceScaleFactor": 1, "mobile": w < 500})
    time.sleep(0.8)
    dw = ev("document.documentElement.clientWidth"); sw = ev("document.documentElement.scrollWidth")
    ok_(f"{w}px 无横向溢出", sw <= dw, f"{sw}/{dw}")
    ok_(f"{w}px 品类卡片可见", ev("""(function(){
        var e=document.querySelector('#pan_chips .cd'); if(!e) return false;
        var r=e.getBoundingClientRect(); return r.left>=0 && r.right<=innerWidth;})()"""))
    shot(name, full=False)
send("Emulation.setDeviceMetricsOverride", {"width": 1400, "height": 1000, "deviceScaleFactor": 1, "mobile": False})
time.sleep(0.5)

print("\n== 10. 清空 ==")
ev("invClear()")
time.sleep(0.4)
ok_("清空后库存空", "还没有库存" in (cell(0, 0) or ""), cell(0, 0))
eq("清空后合计 —", txt("inv_amt"), "—")

print("\n== 11. JS 异常 ==")
ok_("无 JS 异常", len(EXC) == 0, EXC[:3])

print("\n截图: " + OUTD)
kill_tree(p.pid)
kill_stale(verbose=True)
print("\nFAILED: %d" % len(FAIL))
for f in FAIL:
    print("  - " + f)
sys.exit(1 if FAIL else 0)
