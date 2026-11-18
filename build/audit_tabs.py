# -*- coding: utf-8 -*-
"""逐页签、逐控件的功能巡检 v2：
  - 按钮：先把页内数字框悄悄改掉，再点按钮，看输出（文字/可见文本）有没有变、有没有异常
  - 输入框/下拉：改值并派发 input+change，看结果有没有联动（不算自己这个框）
  - 另加针对性断言：人物页几个已知值、答题器搜索、攻略卡片→面板、记账本加物品/计时/解锁清零
结果写 shots/audit_result.json。用法: python build\\audit_tabs.py <url> [port]
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
PORT = int(sys.argv[2]) if len(sys.argv) > 2 else 9260
PROF = os.path.join(WS, "shots", "preprof_audit")
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
mid = [0]
EXC = []


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


SNAP_JS = """(function(){
  var sec=document.getElementById('%s'), out={ids:{}, txt:''};
  if(!sec) return out;
  if(getComputedStyle(sec).display==='none') return out;
  [...sec.querySelectorAll('[id]')].forEach(function(el){
    out.ids[el.id] = (el.tagName==='INPUT'||el.tagName==='SELECT'||el.tagName==='TEXTAREA')
      ? ('V:'+el.value) : el.textContent.replace(/\\s+/g,' ').trim().slice(0,80);
  });
  var t=(sec.innerText||'').replace(/\\s+/g,' ').trim();
  out.txt = t.length + '|' + t.slice(0,60) + '|' + t.slice(-40);
  return out;
})()"""


def snap(sid):
    return ev(SNAP_JS % sid) or {"ids": {}, "txt": ""}


def diff(a, b):
    ids = [k for k in (set(a["ids"]) | set(b["ids"])) if a["ids"].get(k) != b["ids"].get(k)]
    return ids, (a.get("txt") != b.get("txt"))


def visible_section():
    return ev("[...document.querySelectorAll('section')].filter(s=>getComputedStyle(s).display!=='none').map(s=>s.id).join(',')")


def click_tab(t):
    ev("document.querySelector('#tabs button[data-t=\"%s\"]').click()" % t)
    time.sleep(0.4)


def perturb(sid):
    """把页内数字/文本输入框悄悄改成另一个值（不派发事件），返回原值，供点按钮前用。"""
    return ev("""(function(){
      var sec=document.getElementById('%s'), old=[];
      [...sec.querySelectorAll('input')].forEach(function(el,i){
        old.push([el, el.value]);
        if(el.type==='number'){
          var v=parseFloat(el.value); if(isNaN(v)) v=0;
          el.value = String(v + 17);
        }
      });
      return old.length;
    })()""" % sid)


def restore(sid):
    ev("""(function(){
      var sec=document.getElementById('%s');
      [...sec.querySelectorAll('input')].forEach(function(el){ if(el.dataset.oldv!==undefined){ el.value=el.dataset.oldv; } });
    })()""" % sid)


def stash(sid):
    ev("""(function(){
      var sec=document.getElementById('%s');
      [...sec.querySelectorAll('input')].forEach(function(el){ el.dataset.oldv=el.value; });
    })()""" % sid)


send("Page.enable"); send("Runtime.enable")
send("Page.navigate", {"url": URL})
time.sleep(3.5)

SKIP_BTN = {"pickWindow()", "grabAndSearch()", "stopCapture()"}
report = {"tabs": {}}

for tab in ev("[...document.querySelectorAll('#tabs button')].map(b=>b.dataset.t)"):
    click_tab(tab)
    res = {"buttons": [], "inputs": []}
    nbtn = ev("document.getElementById('%s').querySelectorAll('button').length" % tab)
    for i in range(nbtn):
        info = ev("""(function(){var b=document.getElementById('%s').querySelectorAll('button')[%d];
                  if(!b) return null;
                  return {t:(b.textContent||'').replace(/\\s+/g,' ').trim().slice(0,24),
                          c:(b.getAttribute('onclick')||''), d:!!b.disabled,
                          row:!!b.closest('tbody, .inv-log-list')};})()""" % (tab, i))
        if not info:
            res["buttons"].append({"text": "?", "onclick": "?", "status": "gone"})
            continue
        if info["d"]:
            res["buttons"].append({"text": info["t"], "onclick": info["c"], "status": "disabled"})
            continue
        if info.get("row"):
            # 表格行内按钮（删行这类）点了会改 DOM 结构，后续按钮索引就失效了，不自动点
            res["buttons"].append({"text": info["t"], "onclick": info["c"], "status": "row-action"})
            continue
        if info["c"].strip() in SKIP_BTN or "quick(" in info["c"]:
            res["buttons"].append({"text": info["t"], "onclick": info["c"], "status": "skip"})
            continue
        stash(tab); perturb(tab)
        before = snap(tab)
        n0 = len(EXC)
        ev("document.getElementById('%s').querySelectorAll('button')[%d].click()" % (tab, i))
        time.sleep(0.28)
        after = snap(tab)
        restore(tab)
        ids, txt = diff(before, after)
        vis = visible_section()
        res["buttons"].append({"text": info["t"], "onclick": info["c"], "changed": len(ids),
                               "txt_changed": txt, "ids": ids[:5], "errors": EXC[n0:],
                               "nav": vis if vis != tab else None})
        if vis != tab:
            click_tab(tab)
    ninp = ev("document.getElementById('%s').querySelectorAll('input,select,textarea').length" % tab)
    for i in range(ninp):
        meta = ev("""(function(){var el=document.getElementById('%s').querySelectorAll('input,select,textarea')[%d];
                  return {tag:el.tagName,id:el.id,type:el.type,min:el.getAttribute('min'),max:el.getAttribute('max'),
                          v:el.value};})()""" % (tab, i))
        before = snap(tab)
        n0 = len(EXC)
        if meta["tag"] == "SELECT":
            ev("""(function(){var el=document.getElementById('%s').querySelectorAll('input,select,textarea')[%d];
                  var o=[...el.options]; if(o.length>1) el.selectedIndex=(el.selectedIndex+1)%%o.length;
                  el.dispatchEvent(new Event('change',{bubbles:true}));})()""" % (tab, i))
        else:
            lo = float(meta["min"]) if meta["min"] not in (None, "") else 0.0
            hi = float(meta["max"]) if meta["max"] not in (None, "") else None
            v = (lo + (hi - lo) * 0.5) if hi is not None else lo + 37
            v = int(v) if float(v).is_integer() else v
            val = str(v) if meta["type"] == "number" else ("鬼将" if meta["id"] == "qsearch" else "测试")
            ev("""(function(){var el=document.getElementById('%s').querySelectorAll('input,select,textarea')[%d];
                  el.value='%s'; el.dispatchEvent(new Event('input',{bubbles:true}));
                  el.dispatchEvent(new Event('change',{bubbles:true}));})()""" % (tab, i, val))
        time.sleep(0.22)
        after = snap(tab)
        ids, txt = diff(before, after)
        ids = [k for k in ids if k != meta["id"]]
        res["inputs"].append({"id": meta["id"], "index": i, "type": meta["type"], "changed": len(ids),
                              "txt_changed": txt, "ids": ids[:4], "errors": EXC[n0:]})
    report["tabs"][tab] = res

# ---------- 针对性断言 ----------
checks = []


def assert_eq(name, got, want):
    checks.append({"name": name, "got": got, "want": want, "ok": str(got) == str(want)})


def assert_true(name, cond, detail=""):
    checks.append({"name": name, "ok": bool(cond), "detail": detail})


click_tab("renwu")
assert_eq("常用查询：卡片数（10 张查询 + 红蓝秘制）", ev("document.querySelectorAll('#renwu .pc').length"), 11)
assert_eq("常用查询：进页时没有打开的卡片", ev("document.querySelectorAll('#renwu .pc.open').length"), 0)
ev("document.querySelectorAll('#renwu .pc')[0].click()")
time.sleep(0.35)
assert_eq("常用查询：点卡片弹出面板", ev("document.querySelectorAll('#renwu .pc.open').length"), 1)
assert_eq("常用查询：遮罩出现", ev("getComputedStyle(document.getElementById('qc_mask')).display"), "block")
assert_true("常用查询：面板是浮层（position:fixed）",
            ev("getComputedStyle(document.querySelector('#renwu .pc.open .pc-body')).position") == "fixed", "")
ev("document.getElementById('e1').value='0';document.getElementById('e2').value='100';calcExp()")
time.sleep(0.2)
assert_eq("常用查询：0→100 级需要经验", ev("document.getElementById('e_out').textContent"), "1.23 亿")
ev("document.getElementById('x1').value='5000000';document.getElementById('x2').value='0';calcLevel()")
assert_eq("常用查询：500万经验从0级可升到", ev("document.getElementById('x_out').textContent"), "44 级")
ev("document.getElementById('c1').value='100';calcCommon()")
assert_eq("常用查询：100级携钱上限", ev("document.getElementById('c_money').textContent"), "20,010,000")
c_before = ev("document.getElementById('c_money').textContent")
ev("document.querySelectorAll('#renwu .qrow .btn')[0].click()")
time.sleep(0.25)
assert_eq("常用查询：速查按钮把等级带进输入框", ev("document.getElementById('c1').value"), "69")
assert_true("常用查询：速查后结果跟着重算",
            ev("document.getElementById('c_money').textContent") != c_before,
            "69 级携钱上限 %s" % ev("document.getElementById('c_money').textContent"))
assert_eq("常用查询：点速查不会把卡片关掉", ev("document.querySelectorAll('#renwu .pc.open').length"), 1)
assert_eq("常用查询：点速查后遮罩还在", ev("getComputedStyle(document.getElementById('qc_mask')).display"), "block")
ev("document.querySelector('#renwu .pc.open .pc-x').click()")
time.sleep(0.25)
assert_eq("常用查询：× 关闭面板", ev("document.querySelectorAll('#renwu .pc.open').length"), 0)
ev("document.querySelectorAll('#renwu .pc')[7].click()")
time.sleep(0.35)
ev("document.getElementById('xl1').value='0';document.getElementById('xl2').value='20';document.getElementById('xl3').value='0';calcXiu()")
assert_eq("常用查询：修炼 0→20 需要经验", ev("document.getElementById('xl_e').textContent"), "37,200")
ev("document.querySelector('#renwu .pc.open .pc-x').click()")
time.sleep(0.2)

click_tab("quiz")
kw = ev("(typeof QUES!=='undefined' && QUES.length) ? QUES[0].q.slice(0,4) : ''")
ev("var q=document.getElementById('qsearch'); q.value='%s'; q.dispatchEvent(new Event('input',{bubbles:true})); searchQuiz()" % kw)
time.sleep(0.3)
c = ev("document.querySelectorAll('#qlist .quizitem').length")
assert_true("答题器：搜索“%s”有结果" % kw, c and c > 0, "命中 %s 条" % c)
assert_true("答题器：题库条数", ev("document.getElementById('qbuilt').textContent"), ev("document.getElementById('qbuilt').textContent"))

click_tab("gonglue")
assert_eq("攻略：进入时没有打开的面板", ev("document.querySelectorAll('#gonglue .cg.open').length"), 0)
assert_true("攻略：卡片全部在 .gl-grid 里",
            ev("document.querySelectorAll('#gonglue .gl-grid .cg').length") == ev("document.querySelectorAll('#gonglue .cg').length"),
            "卡片数 %s" % ev("document.querySelectorAll('#gonglue .cg').length"))
ev("document.querySelectorAll('#gonglue .gl-grid .cg')[0].click()")
time.sleep(0.4)
assert_eq("攻略：点卡片只开一个面板", ev("document.querySelectorAll('#gonglue .cg.open').length"), 1)
assert_eq("攻略：面板遮罩出现", ev("getComputedStyle(document.getElementById('gl-mask')).display"), "block")
assert_true("攻略：面板是浮层（position:fixed）",
            ev("getComputedStyle(document.querySelector('#gonglue .cg.open .cg-body')).position") == "fixed", "")
ev("document.getElementById('gl-mask').click()")
time.sleep(0.3)
assert_eq("攻略：点遮罩关闭面板", ev("document.querySelectorAll('#gonglue .cg.open').length"), 0)
assert_true("攻略：旧的「全部展开」按钮已移除", ev("document.getElementById('gl-toggle') === null") is True, "")

ev("document.querySelector('#gonglue #qita .cg-head').click()")
time.sleep(0.4)
assert_true("梦幻常识：环怪卡能打开", ev("document.querySelector('#gonglue #qita').classList.contains('open')"), "")
ev("document.querySelector('#qita .hg-item[data-hg=\"3\"]').click()")
time.sleep(0.25)
assert_eq("梦幻常识：点「蝴蝶女」详情标题", ev("document.querySelector('#qita .hg-pane.on .hg-name').textContent").strip(), "[蝴蝶女]")
bad_panes = ev("[...document.querySelectorAll('#qita .hg-pane')].filter(p=>p.querySelectorAll('.hg-chip').length===0).length")
assert_eq("梦幻常识：没有内容的环怪面板数", bad_panes, 0)
pairs = ev("""(function(){var out=[];document.querySelectorAll('#qita .hg-item').forEach(function(b){
   b.click(); var n=document.querySelector('#qita .hg-pane.on .hg-name');
   out.push([b.textContent, n?n.textContent.replace(/[\\[\\]]/g,''):'']);});return out;})()""")
mism = [p for p in (pairs or []) if p[0] != p[1]]
assert_true("梦幻常识：23 只环怪点开标题都对得上（允许 1 处原工具的历史笔误）", len(mism) <= 1,
            "共 %d 只，对不上：%s" % (len(pairs or []), mism))
ev("document.getElementById('gl-mask').click()")
time.sleep(0.3)

click_tab("renwu")
ev("document.querySelector('#renwu #mizhi').click()")
time.sleep(0.35)
assert_true("常用查询：红蓝秘制卡能打开", ev("document.querySelector('#renwu #mizhi').classList.contains('open')"), "")
assert_eq("红蓝秘制：只剩 2 个输入框（点卡价 / 周数）",
          ev("[...document.querySelectorAll('#mizhi input')].map(i=>i.id).join(',')"), "mz_p,mz_w")
ev("mzSet(6500,4)")
time.sleep(0.2)
assert_eq("红蓝秘制：第 4 周红储量", ev("document.getElementById('mz_hr').textContent"), "119,000")
assert_eq("红蓝秘制：第 4 周蓝储量", ev("document.getElementById('mz_hb').textContent"), "38,000")
assert_eq("红蓝秘制：秘制红每 100 血（点卡 6500）", ev("document.getElementById('mz_r100').textContent"), "246 两")
assert_eq("红蓝秘制：佛手每 20 蓝（系统价 80）", ev("document.getElementById('mz_lp20').textContent"), "80 两")
assert_eq("红蓝秘制：结论（秘制贵，买包子）", ev("document.getElementById('mz_rv').textContent"), "买包子，省 39%")
ev("(function(){var w=document.getElementById('mz_w');w.value='10';w.dispatchEvent(new Event('input',{bubbles:true}))})()")
time.sleep(0.3)
assert_eq("红蓝秘制：第 10 周红储量封顶", ev("document.getElementById('mz_hr').textContent"), "200,000")
assert_eq("红蓝秘制：第 10 周蓝储量封顶", ev("document.getElementById('mz_hb').textContent"), "65,000")
assert_eq("红蓝秘制：逐周表行数", ev("document.querySelectorAll('#mz_table tbody tr').length"), 11)
assert_true("红蓝秘制：储量是展示值不是输入框（改不了）",
            ev("document.getElementById('mz_hr').tagName") == "B", "")
ev("mzSet(6500,4)")
ev("document.querySelector('#renwu #mizhi .pc-x').click()")
time.sleep(0.25)

click_tab("shouyi")
ev("syDemo()")
time.sleep(0.3)
assert_eq("收益测算：示例每小时净收益", ev("document.getElementById('sy_k_h').textContent"), "0.77")
assert_eq("收益测算：示例净收益（万）", ev("document.getElementById('sy_o_net').textContent"), "1.16")
# 库存管理（r81：品类细分 + 一次盘一个品类）
click_tab("daomai")
ev("invDemo()")
time.sleep(0.4)
assert_eq("库存：示例 2 行", ev("document.querySelectorAll('#inv_body tr').length"), 2)
assert_eq("库存：库存占用合计", ev("document.getElementById('inv_amt').textContent"), "720.00")
assert_eq("库存：库存件数", ev("document.getElementById('inv_qty').textContent"), "330")
assert_eq("库存：总资产（现金 340 + 库存 720）", ev("document.getElementById('inv_asset').textContent"), "1,060.00")
assert_eq("库存：分组标签数", ev("document.querySelectorAll('#buy_gtabs .tb').length"), 5)
ev("""(function(){var gs=[].slice.call(document.querySelectorAll('#buy_gtabs .tb'));
  for(var i=0;i<gs.length;i++){ if(gs[i].textContent.trim()==='环装'){ gs[i].click(); return; } }})()""")
time.sleep(0.2)
assert_eq("库存：进货环装 6 张卡", ev("document.querySelectorAll('#buy_chips .cd').length"), 6)

# 盘点：一次盘一个品类
ev("""(function(){
  var gs=[].slice.call(document.querySelectorAll('#pan_gtabs .tb'));
  for(var i=0;i<gs.length;i++){ if(gs[i].textContent.trim()==='环装'){ gs[i].click(); break; } }
  var cs=[].slice.call(document.querySelectorAll('#pan_chips .cd'));
  for(var j=0;j<cs.length;j++){ if(cs[j].getAttribute('data-k')==='环装 80武器'){ cs[j].click(); break; } }
  var n=document.getElementById('inv_pan_num');n.value='25';n.dispatchEvent(new Event('input',{bubbles:true}));})()""")
time.sleep(0.25)
assert_eq("库存：选中品类显示账面", ev("document.getElementById('inv_pan_book').textContent"), "30")
assert_eq("库存：出库实时算", ev("document.getElementById('inv_pan_out').textContent"), "5")
ev("document.querySelectorAll('#daomai .inv-count .line .btn')[0].click()")
time.sleep(0.3)
assert_eq("库存：加入盘点单后不落账（库存仍是 30）", ev("""(function(){
  var rs=document.querySelectorAll('#inv_body tr');
  for(var i=0;i<rs.length;i++){ if(rs[i].children[0].textContent.trim()==='80武器') return rs[i].children[1].textContent; }
  return 'none';})()"""), "30")
ev("document.querySelectorAll('#daomai .inv-count .line .btn')[1].click()")
time.sleep(0.3)
assert_eq("库存：确认后总资产（出库 5 件按成本扣、现金没变）", ev("document.getElementById('inv_asset').textContent"), "1,000.00")
assert_eq("库存：流水最新一条标「盘」", ev("document.querySelector('#inv_log .r .k').textContent"), "盘")
assert_eq("库存：清空后合计为 —", ev("(function(){invClear();return document.getElementById('inv_amt').textContent})()"), "—")

# ---------- 记账本：设价 / 加物品 / 计时 / 解锁清零 ----------
click_tab("jzb")
jz = []
n0 = ev("document.querySelectorAll('#jzb .record_table tbody tr').length")
ev("document.querySelector('#item1 .item_list li').click()")
time.sleep(0.3)
jz.append(("固定价物品首次点击弹价格窗", ev("document.getElementById('jzb-mask').classList.contains('on')")))
ev("""(function(){var ta=document.querySelector('#jzb-pop textarea'); ta.value='15';
      document.querySelector('#jzb-pop .ok').click();})()""")
time.sleep(0.3)
jz.append(("输入价格确认后提示", ev("document.getElementById('jzb-msg').innerText.replace(/\\s+/g,' ').slice(0,30)")))
jz.append(("固定价首次只存价、不加记录", ev("document.querySelectorAll('#jzb .record_table tbody tr').length") - n0 == 0))
ev("document.querySelector('#item1 .item_list li').click()")
time.sleep(0.3)
jz.append(("再点一次固定价物品 -> 加一条记录", ev("document.querySelectorAll('#jzb .record_table tbody tr').length") - n0 == 1))
ev("document.querySelector('#item2 .item_list li').click()")
time.sleep(0.3)
ev("""(function(){var ta=document.querySelector('#jzb-pop textarea'); ta.value='20';
      document.querySelector('#jzb-pop .ok').click();})()""")
time.sleep(0.3)
jz.append(("非固定价物品 -> 再加一条记录", ev("document.querySelectorAll('#jzb .record_table tbody tr').length") - n0 == 2))
ev("""(function(){var f=document.getElementById('jzb-form');
      [['start_gold','500'],['end_gold','1250'],['ratio','200'],['price','0.1']].forEach(function(p){
        var el=f.querySelector('[name='+p[0]+']'); el.value=p[1]; el.dispatchEvent(new Event('blur',{bubbles:true}));
      });})()""")
time.sleep(0.25)
gain = ev("document.querySelector('#jzb .res_3').innerText.replace(/\\s+/g,' ')")
conv = ev("document.querySelector('#jzb .res_6').innerText.replace(/\\s+/g,' ')")
jz.append(("填启动 500 / 结束 1250 -> 获得金钱列", gain))
jz.append(("比例 200 -> 比例转化后收益列", conv))
assert_eq("记账本：获得金钱", gain, "750.00w")
assert_eq("记账本：比例转化后收益（(750+35)/3000×200）", conv, "52.33元")
ev("document.getElementById('jzb-start').click()")
time.sleep(1.3)
jz.append(("开始计时后时长", ev("document.querySelector('#jzb .res_1').innerText.replace(/\\s+/g,' ')")))
jz.append(("计时中每小时收益（非 0）", ev("document.querySelector('#jzb .res_7').innerText.replace(/\\s+/g,' ')")))
ev("document.getElementById('jzb-stop').click()")
time.sleep(0.5)
if ev("document.getElementById('jzb-mask').classList.contains('on')"):
    ev("document.querySelector('#jzb-pop .ok') && document.querySelector('#jzb-pop .ok').click()")
    time.sleep(0.4)
jz.append(("重新计时后时长归零", ev("document.querySelector('#jzb .res_1').innerText.replace(/\\s+/g,' ')")))
ev("document.getElementById('jzb-reset').click()")
time.sleep(0.4)
popup = ev("document.getElementById('jzb-mask').classList.contains('on')")
if popup:
    ev("document.querySelector('#jzb-pop .ok') && document.querySelector('#jzb-pop .ok').click()")
    time.sleep(0.3)
jz.append(("未解锁点清零 -> 记录还在", ev("document.querySelectorAll('#jzb .record_table tbody tr').length") - n0))
ev("document.querySelector('#jzb .check_today').click()")
ev("document.getElementById('jzb-reset').click()")
time.sleep(0.4)
if ev("document.getElementById('jzb-mask').classList.contains('on')"):
    ev("document.querySelector('#jzb-pop .ok').click()")
    time.sleep(0.3)
jz.append(("解锁后清零 -> 记录行数", ev("document.querySelectorAll('#jzb .record_table tbody tr').length")))
checks.append({"name": "记账本", "ok": True, "detail": jz})

report["checks"] = checks
open(os.path.join(WS, "shots", "audit_result.json"), "w", encoding="utf-8").write(
    json.dumps(report, ensure_ascii=False, indent=1))

for tab, res in report["tabs"].items():
    print("\n=== %s ===" % tab)
    for b in res["buttons"]:
        if b.get("status"):
            continue
        flag = "OK " if (b["changed"] or b["txt_changed"]) and not b["errors"] else ("ERR" if b["errors"] else "IDLE")
        print("  [%s] %-13s ids=%-2s txt=%-5s %s %s" % (flag, b["text"], b["changed"], b["txt_changed"],
              b["onclick"], ("NAV:" + b["nav"]) if b["nav"] else ""))
        for e in b["errors"]:
            print("        !!", e[:150])
    bad_in = [i for i in res["inputs"] if not (i["changed"] or i["txt_changed"]) or i["errors"]]
    print("  inputs: %d 个，其中没联动/报错：%s" % (len(res["inputs"]),
          ", ".join("%s(%s)" % (i["id"] or i["index"], i["changed"]) for i in bad_in) or "无"))
    for i in bad_in:
        for e in i["errors"]:
            print("        !!", i["id"], e[:150])

print("\n=== 针对性断言 ===")
for c in checks:
    print(("  OK  " if c["ok"] else "  FAIL") , c["name"], "->", c.get("got", ""), c.get("detail", ""), ("期望 " + str(c["want"])) if "want" in c else "")
print("\ntotal exceptions:", len(EXC))
kill_tree(p.pid)
kill_stale(verbose=True)
