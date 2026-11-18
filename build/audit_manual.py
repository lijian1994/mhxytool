# -*- coding: utf-8 -*-
"""交接文档「待办 8」里剩下的人工验收项，脚本化。

  1) 攻略「点击复制」：无头 Edge 的剪贴板是沙箱内的假剪贴板（实测 writeText 即使 resolve，
     系统剪贴板也不变），所以这里验的是**页面的代码路径**：writeText 拿到的文本是否等于
     data-copy；writeText 失败时是否走 textarea + execCommand 兜底，兜底拿到的文本对不对。
  2) 其它页「白熊怪」在 audit_tabs 里显示 IDLE，确认是快照截断还是真没内容。
  3) 答题器基础状态：自动识别（开）-> 点「停止」后按钮/定时器/提示/流 全部归零（r52 回归）。
  4) 模拟加点 iframe：面板联动（加点/装备/坐骑）、保存 -> localStorage、刷新恢复、清空归零。

用法: python build\\audit_manual.py <file-url> [port]
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
PORT = int(sys.argv[2]) if len(sys.argv) > 2 else 9295
PROF = os.path.join(WS, "shots", "preprof_manual")
OUTD = os.path.join(WS, "shots", "audit_shots")
shutil.rmtree(PROF, ignore_errors=True)
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
w = [t for t in tg if t.get("type") == "page"][0]["webSocketDebuggerUrl"]
hostport, path = w.split("//")[1].split("/", 1)
host, port = hostport.split(":")
s = socket.create_connection((host, int(port)), timeout=60)
key = base64.b64encode(os.urandom(16)).decode()
s.sendall((f"GET /{path} HTTP/1.1\r\nHost: {hostport}\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
           f"Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n").encode())
b = b""
while b"\r\n\r\n" not in b:
    b += s.recv(4096)
mid = [0]
EXC = []


def send(m, pr=None):
    mid[0] += 1
    pay = json.dumps({"id": mid[0], "method": m, "params": pr or {}}).encode()
    mk = os.urandom(4)
    h = bytes([0x81]); ln = len(pay)
    if ln < 126: h += bytes([0x80 | ln])
    elif ln < 65536: h += bytes([0x80 | 126]) + struct.pack(">H", ln)
    else: h += bytes([0x80 | 127]) + struct.pack(">Q", ln)
    s.sendall(h + mk + bytes(x ^ mk[i % 4] for i, x in enumerate(pay)))
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
    m = json.loads(pay.decode())
    if m.get("method") == "Runtime.exceptionThrown":
        EXC.append((m["params"]["exceptionDetails"].get("exception", {}) or {}).get("description", "")[:300])
    return m


def call(m, pr=None):
    rid = send(m, pr)
    while True:
        x = recv()
        if x.get("id") == rid:
            return {"__err__": x["error"]} if "error" in x else x.get("result", {})


def ev(expr, ctx=None):
    pr = {"expression": expr, "returnByValue": True, "awaitPromise": True}
    if ctx: pr["contextId"] = ctx
    r = call("Runtime.evaluate", pr)
    if "__err__" in r: return "__CDPERR__:" + str(r["__err__"])[:120]
    if "exceptionDetails" in r:
        return "__ERR__:" + str((r["exceptionDetails"].get("exception") or {}).get("description"))[:180]
    return (r.get("result") or {}).get("value")


def shot(name):
    r = call("Page.captureScreenshot", {"format": "png"})
    if r.get("data"):
        open(os.path.join(OUTD, name), "wb").write(base64.b64decode(r["data"]))


def tab(t):
    ev("document.querySelector('#tabs button[data-t=\"%s\"]').click()" % t)
    time.sleep(0.5)


R = []


def chk(name, got, want=True, detail=""):
    ok = bool(got) if want is True else (str(got) == str(want))
    R.append({"name": name, "got": str(got)[:200], "want": str(want)[:200], "ok": ok, "detail": detail})
    print(("  OK  " if ok else "  FAIL"), name, "->", str(got)[:100],
          ("" if want is True else "（期望 %s）" % want), detail)


call("Page.enable"); call("Runtime.enable")
call("Page.navigate", {"url": URL})
time.sleep(3.5)

# ================= 1) 攻略复制：验代码路径 =================
tab("gonglue")
ev("""(function(){var t=document.getElementById('gl-toggle');
   if(t && t.textContent.trim()==='全部展开') t.click();})()""")
time.sleep(0.6)
want = ev("document.querySelector('#gonglue [data-copy]').getAttribute('data-copy')") or ""

# 1a. clipboard.writeText 正常时：文本必须一字不差
ev("""window.__wrote=null; window.__execs=[];
  try{ Object.defineProperty(navigator,'clipboard',{configurable:true,
      get:function(){return {writeText:function(t){ window.__wrote=t; return Promise.resolve(); }};}}); }catch(e){ window.__wrote='DEFINE_FAILED'; }""")
ev("document.querySelector('#gonglue [data-copy]').click()")
time.sleep(0.5)
chk("攻略·writeText 收到的文本 = data-copy", ev("window.__wrote") == want, True,
    "实际 %r" % (ev("window.__wrote"),))
chk("攻略·复制成功后有「已复制」提示",
    (ev("(document.querySelector('#gonglue .gl-toast')||{}).textContent") or "").strip(), "已复制")
shot("m1_gonglue_toast.png")

# 1b. writeText 被拒时：必须走 textarea+execCommand 兜底，且兜底文本正确
ev("""window.__wrote=null; window.__execs=[];
  try{ Object.defineProperty(navigator,'clipboard',{configurable:true,
      get:function(){return {writeText:function(){ return Promise.reject(new Error('denied')); }};}}); }catch(e){}
  window.__origExec=document.execCommand;
  document.execCommand=function(){ window.__execs.push(document.activeElement && document.activeElement.value);
      return true; };""")
ev("document.querySelector('#gonglue [data-copy]').click()")
time.sleep(0.7)
fb = ev("window.__execs && window.__execs.length ? window.__execs[0] : null")
chk("攻略·writeText 被拒时走 execCommand 兜底", ev("(window.__execs||[]).length"), 1)
chk("攻略·兜底写入的文本也 = data-copy", fb == want, True, "实际 %r" % (fb,))

# 1c. 复制全部 16 句：join('\n')
ev("""window.__wrote=null;
  document.execCommand=window.__origExec;
  try{ Object.defineProperty(navigator,'clipboard',{configurable:true,
      get:function(){return {writeText:function(t){ window.__wrote=t; return Promise.resolve(); }};}}); }catch(e){}""")
ev("document.getElementById('fj-copy-all').click()")
time.sleep(0.7)
allw = ev("window.__wrote") or ""
lines = ev("[...document.querySelectorAll('#gonglue .fj-line')].map(function(e){return e.getAttribute('data-copy');})") or []
chk("攻略·复制全部 = 16 句用换行连起来", allw.split("\n"), lines, "%d 行" % len(allw.split("\n")))
shot("m2_gonglue_all.png")

# ================= 2) 其它：白熊怪 =================
tab("qita")


def pane_text(name):
    ev("""(function(){var b=[...document.querySelectorAll('#qita .hg-item')]
        .filter(function(x){return x.textContent.trim()==='%s';})[0]; if(b) b.click();})()""" % name)
    time.sleep(0.3)
    return ev("(document.querySelector('#qita .hg-pane.on')||{}).innerText") or ""


t_ye, t_bai = pane_text("野猪王"), pane_text("白熊怪")
chk("其它·白熊怪面板有正文且与野猪王不同", len(t_bai.strip()) > 20 and t_bai != t_ye, True,
    "白熊怪 %d 字 / 野猪王 %d 字" % (len(t_bai), len(t_ye)))
chk("其它·白熊怪标题", (ev("(document.querySelector('#qita .hg-pane.on .hg-name')||{}).textContent") or "").strip(),
    "[白熊怪]")
shot("m3_qita_bai.png")

# ================= 3) 答题器基础状态 =================
tab("quiz")
chk("答题器·初始按钮文案", (ev("document.getElementById('shot_auto').textContent") or "").strip(), "自动识别")
chk("答题器·初始无定时器", bool(ev("AUTO_TIMER")), False)
chk("答题器·未选窗口点自动识别只提示", ev("""(function(){document.getElementById('shot_auto').click();
        return document.getElementById('shot_state').textContent;})()"""), "先点「选择窗口」")
chk("答题器·未选窗口不会点亮自动识别", bool(ev("AUTO_TIMER")), False)
ev("SHOT_STREAM = {getTracks:function(){return [{stop:function(){}}];}};")
ev("document.getElementById('shot_auto').click()")
time.sleep(0.3)
chk("答题器·有流后点自动识别 -> 定时器起来", bool(ev("AUTO_TIMER")), True)
chk("答题器·按钮文案变「自动识别（开）」", (ev("document.getElementById('shot_auto').textContent") or "").strip(), "自动识别（开）")
chk("答题器·开启时有绿色高亮", "linear-gradient" in (ev("document.getElementById('shot_auto').style.background") or ""), True)
shot("m4_quiz_auto_on.png")
chk("答题器·点「停止」", ev("""(function(){var b=[...document.querySelectorAll('#quiz button')]
        .filter(function(x){return x.textContent.trim()==='停止';})[0]; if(!b) return 'NOT_FOUND'; b.click(); return 'clicked';})()"""),
    "clicked")
time.sleep(0.4)
chk("答题器·停止后定时器清空", bool(ev("AUTO_TIMER")), False)
chk("答题器·停止后按钮文案归位", (ev("document.getElementById('shot_auto').textContent") or "").strip(), "自动识别")
chk("答题器·停止后高亮清掉", (ev("document.getElementById('shot_auto').style.background") or ""), "")
chk("答题器·停止后状态栏归位", (ev("document.getElementById('shot_state').textContent") or "").strip(), "未选择窗口")
chk("答题器·停止后 SHOT_STREAM 释放", bool(ev("!!SHOT_STREAM")), False)
shot("m5_quiz_stopped.png")

# ================= 4) 模拟加点 =================
tab("jiadian")
time.sleep(1.5)


def jd_ctx():
    ft = call("Page.getFrameTree").get("frameTree", {})
    for k in ft.get("childFrames") or []:
        fr = k.get("frame", {})
        if (fr.get("url") or "").startswith("data:"):
            return call("Page.createIsolatedWorld",
                        {"frameId": fr["id"], "worldName": "audit"}).get("executionContextId")
    return None


def panel(attr, ctx):
    return (ev("(document.querySelector('[name=%s]')||{}).value" % attr, ctx) or "").strip()


C = jd_ctx()
chk("模拟加点·iframe 执行上下文", bool(C), True, str(C))
if C:
    chk("模拟加点·输入项 138 个", ev("document.querySelectorAll('input').length", C), 138,
        "select 另有 %s" % ev("document.querySelectorAll('select').length", C))
    chk("模拟加点·面板初始气血 100（体质 0 + 基础 100）", panel("qixue", C), "100")

    # 4a 加点属性 -> 面板联动（注意：app 会按等级/潜力点钳制，所以只看“有没有变”）
    before = panel("qixue", C)
    ev("""(function(){var e=document.querySelector('[name=tizhi]'); e.value='100';
        e.dispatchEvent(new Event('input',{bubbles:true})); e.dispatchEvent(new Event('change',{bubbles:true}));})()""", C)
    time.sleep(0.4)
    after = panel("qixue", C)
    chk("模拟加点·改「加点·体质」面板立刻联动", after != before, True, "气血 %s -> %s" % (before, after))
    tz_now = int((ev("(document.querySelector('[name=tizhi]')||{}).value", C) or "0").strip() or 0)
    chk("模拟加点·加点值被钳到「基础+潜力点」上限（不能凭空给 100）", 0 < tz_now < 100, True, "输入 100 -> 实际 %d" % tz_now)
    chk("模拟加点·面板气血 = 100 + 4.5×体质", int(after or 0), int(100 + 4.5 * tz_now),
        "%d vs %d" % (int(after or 0), int(100 + 4.5 * tz_now)))

    # 4b 装备附加 -> 面板联动
    b2 = panel("qixue", C)
    ev("""(function(){var e=document.querySelector('input.eq[data-a="qixue"]'); e.value='500';
        e.dispatchEvent(new Event('input',{bubbles:true}));})()""", C)
    time.sleep(0.4)
    chk("模拟加点·改「衣服·气血」面板立刻 +500", int(panel("qixue", C) or 0) - int(b2 or 0), 500,
        "%s -> %s" % (b2, panel("qixue", C)))
    ev("""(function(){var e=document.querySelector('input.eq[data-a="qixue"]'); e.value='0';
        e.dispatchEvent(new Event('input',{bubbles:true}));})()""", C)
    time.sleep(0.3)

    # 4c 坐骑（骑乘）属性 -> 面板联动（交接文档没测过这一条）
    b3 = panel("qixue", C)
    ev("""(function(){var e=document.getElementById('mt_tizhi'); e.value='50';
        e.dispatchEvent(new Event('input',{bubbles:true})); e.dispatchEvent(new Event('change',{bubbles:true}));})()""", C)
    time.sleep(0.5)
    after3 = panel("qixue", C)
    chk("模拟加点·改「坐骑·体质」面板立刻联动", after3 != b3, True, "气血 %s -> %s" % (b3, after3))
    shot("m6_jiadian_panel.png")

    # 4d 保存 -> localStorage['mz.common.v1']
    ev("document.getElementById('mz-save').click()", C)
    time.sleep(0.7)
    raw = ev("localStorage.getItem('mz.common.v1')")
    try:
        saved = dict((str(k), str(v)) for k, v in json.loads(raw or "[]"))
    except Exception:
        saved = {}
    tz_save = (ev("(document.querySelector('[name=tizhi]')||{}).value", C) or "").strip()
    chk("模拟加点·保存写了父窗口 localStorage", len(saved) >= 40, True, "%d 项" % len(saved))
    chk("模拟加点·保存内容含 坐骑体质=50", saved.get("#mt_tizhi|1"), "50")
    chk("模拟加点·保存内容含 加点体质（保存那一刻框里的值）", tz_save in set(saved.values()), True,
        "保存时框里是 %s" % tz_save)

    # 4e 刷新恢复
    call("Page.reload", {"ignoreCache": False})
    time.sleep(3.5)
    tab("jiadian")
    time.sleep(1.8)
    C = jd_ctx()
    tz2 = int((ev("(document.querySelector('[name=tizhi]')||{}).value", C) or "0").strip() or 0)
    mt2 = int((ev("(document.getElementById('mt_tizhi')||{}).value", C) or "0").strip() or 0)
    chk("模拟加点·刷新后 坐骑体质 恢复", mt2, 50)
    chk("模拟加点·刷新后 加点框显示 加点+骑乘（17+50）", tz2, tz_now + 50,
        "刷新后显示 %d" % tz2)
    chk("模拟加点·刷新后面板按恢复值重算", int(panel("qixue", C) or 0), int(100 + 4.5 * tz2),
        "气血 %s = 100+4.5×%d" % (panel("qixue", C), tz2))
    shot("m7_jiadian_reload.png")

    # 4f 清空
    ev("document.getElementById('mz-clear').click()", C)
    time.sleep(0.8)
    chk("模拟加点·清空后 加点体质 回到基础 12（不是 0）",
        (ev("(document.querySelector('[name=tizhi]')||{}).value", C) or "0").strip(), "12",
        "没选门派时 race()=xian，仙族基础体质 12")
    chk("模拟加点·清空后 localStorage 键已删", ev("localStorage.getItem('mz.common.v1')"), None)
    call("Page.reload", {"ignoreCache": False})
    time.sleep(3.5)
    tab("jiadian")
    time.sleep(1.8)
    C = jd_ctx()
    chk("模拟加点·清空后刷新仍是空白",
        (ev("(document.querySelector('[name=tizhi]')||{}).value", C) or "0").strip(), "0")

    # 4g 门派保存/恢复 + 师门命中→伤害（r62/r63 回归：用户报过「刷新变回天宫」和「命中不折伤害」）
    ev("""(function(){var s=document.querySelector('[name=menpai]');
        for(var i=0;i<s.options.length;i++){ if(s.options[i].text==='凌波城'){ s.selectedIndex=i; break; } }
        s.dispatchEvent(new Event('change',{bubbles:true}));})()""", C)
    time.sleep(0.6)
    ev("""(function(){var e=document.getElementById('sk_hit'); e.value='0';
        e.dispatchEvent(new Event('input',{bubbles:true}));})()""", C)
    time.sleep(0.4)
    hit0 = int(panel("shanghai", C) or 0)
    ev("""(function(){var e=document.getElementById('sk_hit'); e.value='60';
        e.dispatchEvent(new Event('input',{bubbles:true}));})()""", C)
    time.sleep(0.5)
    chk("模拟加点·命中技能 60 级让面板伤害涨 ⌊108/3⌋=36",
        int(panel("shanghai", C) or 0) - hit0, 36,
        "%d -> %d" % (hit0, int(panel("shanghai", C) or 0)))
    ev("document.getElementById('mz-save').click()", C)
    time.sleep(0.8)
    call("Page.reload", {"ignoreCache": False})
    time.sleep(4.0)
    tab("jiadian")
    time.sleep(2.0)
    C = jd_ctx()
    school = ev("""(function(){var s=document.querySelector('[name=menpai]');
        return s&&s.options[s.selectedIndex]?s.options[s.selectedIndex].text:'';})()""", C)
    chk("模拟加点·保存后刷新门派仍是凌波城（r63 修：以前只存 ren/xian/mo）", school, "凌波城")
    chk("模拟加点·刷新后命中技能等级还在", (ev("(document.getElementById('sk_hit')||{}).value", C) or "").strip(), "60")
    ev("document.getElementById('mz-clear').click()", C)
    time.sleep(0.8)

    # 4h 真实面板核对：用户 2026-11-17 截图（普陀山 90 级、不穿装备、
    #    强身40 冥想20 养生13 健体13、护法金刚20 五行扭转70 灵性90、全敏 555）
    ev("""(function(){var s=document.querySelector('[name=menpai]');
        for(var i=0;i<s.options.length;i++){ if(s.options[i].text==='普陀山'){ s.selectedIndex=i; break; } }
        s.dispatchEvent(new Event('change',{bubbles:true}));})()""", C)
    time.sleep(0.5)

    def setin(sel, val):
        ev("(function(){var e=document.querySelector(%s); if(!e) return; e.value='%d';"
           "e.dispatchEvent(new Event('input',{bubbles:true}));"
           "e.dispatchEvent(new Event('change',{bubbles:true}));})()" % (json.dumps(sel), val), C)
        time.sleep(0.12)

    setin("input[name=jibie]", 90)
    setin("#qs", 40); setin("#mx", 20); setin("#shengyang", 13); setin("#jianshen", 13)
    setin("#sk_damage", 20); setin("#sk_defense", 70); setin("#sk_spirit", 90)
    setin("input[name=minjie]", 555)          # 455 潜力全点敏捷 → 10+90+455
    for k, want in [("qixue", "782"), ("mofa", "494"), ("mingzhong", "201"), ("shanghai", "166"),
                    ("fangyu", "267"), ("sudu", "419"), ("fashang", "238"), ("fafang", "238")]:
        chk("真实面板·普陀90·" + k, panel(k, C), want)
    tl = ev("document.getElementById('tl-info')?document.getElementById('tl-info').textContent:''", C) or ""
    chk("真实面板·普陀90·活力/体力上限 552", "552" in tl, True, tl.replace("\n", " ")[:60])

    ev("document.getElementById('mz-clear').click()", C)
    time.sleep(0.6)

out = {"url": URL, "exceptions": EXC, "checks": R,
       "fail": [c["name"] for c in R if not c["ok"]]}
json.dump(out, open(os.path.join(WS, "shots", "audit_manual.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
print("\nexceptions:", len(EXC), EXC[:2])
print("FAIL:", out["fail"] or "无")
print("%d/%d 通过" % (sum(1 for c in R if c["ok"]), len(R)))
kill_tree(p.pid)
kill_stale(verbose=True)
sys.exit(0 if not out["fail"] and not EXC else 1)
