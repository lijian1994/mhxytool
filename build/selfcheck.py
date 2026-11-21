# -*- coding: utf-8 -*-
"""无人值守交互自检：起本地 http 服务 + 无头 Edge，点真实控件并断言结果。

用法: python build\\selfcheck.py [html路径]
退出码 0 = 全过；1 = 有失败。
不弹窗、不留进程：独立 profile 在 shots\\preprof_selfcheck，跑完 kill 整棵树。
"""
import base64
import functools
import http.server
import json
import os
import shutil
import socket
import struct
import subprocess
import sys
import threading
import time
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from edge_guard import kill_stale, kill_tree

try:
    import ctypes
    ctypes.windll.kernel32.SetErrorMode(0x0001 | 0x0002)
except Exception:
    pass

WS = r"F:\Documents\deepseek-harness\default-workspace"
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
DIST = os.path.join(WS, "shots", "dist")
HTML = sys.argv[1] if len(sys.argv) > 1 else os.path.join(DIST, "梦幻西游实用工具箱-复刻版.html")
PROF = os.path.join(WS, "shots", "preprof_selfcheck")
PORT_WEB = 8799
PORT_CDP = 9295


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def handle(self):
        try:
            super().handle()
        except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError):
            pass


def start_web():
    handler = functools.partial(QuietHandler, directory=DIST)
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", PORT_WEB), handler)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    return srv


class Cdp:
    def __init__(self):
        self.mid = 0
        self.s = socket.create_connection(("127.0.0.1", PORT_CDP), timeout=60)
        key = base64.b64encode(os.urandom(16)).decode()
        self.s.sendall(
            (f"GET /devtools/browser HTTP/1.1\r\nHost: 127.0.0.1:{PORT_CDP}\r\n"
             f"Upgrade: websocket\r\nConnection: Upgrade\r\n"
             f"Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n").encode())
        b = b""
        while b"\r\n\r\n" not in b:
            b += self.s.recv(4096)

    def _rd(self, n):
        d = b""
        while len(d) < n:
            c = self.s.recv(n - len(d))
            if not c:
                raise EOFError
            d += c
        return d

    def send(self, method, params=None):
        self.mid += 1
        pay = json.dumps({"id": self.mid, "method": method, "params": params or {}}).encode()
        mask = os.urandom(4)
        h = bytes([0x81])
        ln = len(pay)
        if ln < 126:
            h += bytes([0x80 | ln])
        elif ln < 65536:
            h += bytes([0x80 | 126]) + struct.pack(">H", ln)
        else:
            h += bytes([0x80 | 127]) + struct.pack(">Q", ln)
        self.s.sendall(h + mask + bytes(x ^ mask[i % 4] for i, x in enumerate(pay)))
        return self.mid

    def recv(self):
        pay = b""
        while True:
            h = self._rd(2)
            fin = h[0] & 0x80
            op = h[0] & 0x0f
            ln = h[1] & 0x7f
            if ln == 126:
                ln = struct.unpack(">H", self._rd(2))[0]
            elif ln == 127:
                ln = struct.unpack(">Q", self._rd(8))[0]
            pay += self._rd(ln)
            if op == 9:
                continue
            if fin:
                break
        return json.loads(pay.decode())

    def wait(self, rid, timeout=25):
        end = time.time() + timeout
        while time.time() < end:
            m = self.recv()
            if m.get("id") == rid:
                return m
        return None


def page_ws_url():
    tg = json.load(urllib.request.urlopen(f"http://127.0.0.1:{PORT_CDP}/json/list"))
    for t in tg:
        if t.get("type") == "page":
            return t["webSocketDebuggerUrl"]
    return None


class Tab:
    """连到页面 target 的 CDP 会话"""

    def __init__(self, ws_url):
        host, port = ws_url.split("//")[1].split("/")[0].split(":")
        path = "/" + ws_url.split("//")[1].split("/", 1)[1]
        self.s = socket.create_connection((host, int(port)), timeout=60)
        key = base64.b64encode(os.urandom(16)).decode()
        self.s.sendall(
            (f"GET {path} HTTP/1.1\r\nHost: {host}:{port}\r\nUpgrade: websocket\r\n"
             f"Connection: Upgrade\r\nSec-WebSocket-Key: {key}\r\n"
             f"Sec-WebSocket-Version: 13\r\n\r\n").encode())
        b = b""
        while b"\r\n\r\n" not in b:
            b += self.s.recv(4096)
        self.mid = 0

    send = Cdp.send
    _rd = Cdp._rd
    recv = Cdp.recv
    wait = Cdp.wait

    def ev(self, expr):
        rid = self.send("Runtime.evaluate", {"expression": expr, "returnByValue": True, "awaitPromise": True})
        m = self.wait(rid)
        if not m:
            return {"__timeout": True}
        r = m.get("result", {})
        if r.get("exceptionDetails"):
            return {"__exception": r["exceptionDetails"].get("text")}
        return r.get("result", {}).get("value")


def js(path):
    return open(os.path.join(WS, "shots", path), encoding="utf-8").read()


def main():
    checks = []

    def check(name, ok, detail=""):
        checks.append((name, bool(ok), detail))
        print(("PASS  " if ok else "FAIL  ") + name + (("  :: " + str(detail)) if detail else ""))

    shutil.rmtree(PROF, ignore_errors=True)
    kill_stale(verbose=False)
    srv = start_web()
    proc = subprocess.Popen([EDGE, "--headless=new", "--disable-gpu", "--hide-scrollbars",
                             "--noerrdialogs", "--disable-crash-reporter", "--disable-breakpad",
                             f"--remote-debugging-port={PORT_CDP}", f"--user-data-dir={PROF}",
                             "--window-size=1300,900", "about:blank"],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        time.sleep(3.0)
        ws_url = page_ws_url()
        if not ws_url:
            raise SystemExit("拿不到页面 target")
        t = Tab(ws_url)
        t.send("Page.enable")
        t.send("Runtime.enable")
        t.send("Emulation.setDeviceMetricsOverride",
               {"width": 1300, "height": 900, "deviceScaleFactor": 1, "mobile": False})
        url = f"http://127.0.0.1:{PORT_WEB}/" + urllib.parse.quote(os.path.basename(HTML))
        t.send("Page.navigate", {"url": url})
        time.sleep(3.5)

        # 0) 页面基础
        info = t.ev("""(function(){
          var on = document.querySelector('section.on');
          return { tabs: document.querySelectorAll('#tabs button').length,
                   secs: document.querySelectorAll('section').length,
                   first: on && on.id,
                   ver: (document.querySelector('.ver')||{}).textContent };
        })()""")
        check("页面加载：11 个页签 / 11 个 section", info and info.get("tabs") == 11 and info.get("secs") == 11, info)

        # 1) 体活 + 炼药：4+0、20 次、10 个三药
        r = t.ev(r"""(function(){
          function set(id,v){var e=document.getElementById(id); if(!e) return;
            e.value=v; e.dispatchEvent(new Event('input',{bubbles:true})); e.dispatchEvent(new Event('change',{bubbles:true}));}
          set('sy_lv',120); set('sy_cap',900); set('sy_p3',2.5); set('sy_pjc',0.2);
          var m=document.getElementById('al_method'); m.value='4+0'; m.dispatchEvent(new Event('change',{bubbles:true}));
          set('al_n',20); set('al_n3',10); document.getElementById('al_add').click();
          function t(id){var e=document.getElementById(id); return e? e.textContent.trim(): null;}
          return { today_net: t('sy_today_net'), today_in: t('sy_today_in'),
                   today_mat: t('sy_today_mat'), today_pt: t('sy_today_pt'),
                   rate: t('sy_rate_view'), cost: t('sy_cost_view'), al: t('al_now') };
        })()""")
        check("炼药成本按配方 4+0 = 0.60 万", r and r.get("cost") == "0.60", r and r.get("cost"))
        check("今日收支：收入 2.00 / 材料 0.89 / 点卡 4.80 / 净 -3.69",
              r and r.get("today_in") == "2.00" and r.get("today_mat") == "0.89"
              and r.get("today_pt") == "4.80" and r.get("today_net") == "-3.69", r)

        # 1b) ② 收益：改单价后表格立即按新单价重算
        r = t.ev(r"""(function(){
          var tabBtn = document.querySelector('#tabs button[data-t="shouyi"]');
          if(tabBtn) tabBtn.click();
          function set(id,v){var e=document.getElementById(id); if(!e) return;
            e.value=v; e.dispatchEvent(new Event('input',{bubbles:true}));}
          function row(){ var tr=document.querySelector('#al_body tr'); return tr? tr.innerText.replace(/\s+/g,' ').trim(): ''; }
          var before = row();
          set('sy_p3', 3.0);
          var after = row();
          set('sy_p3', 2.5);
          return { before: before, after: after };
        })()""")
        check("② 收益按页面当前单价重算：2.5→15.00，改 3.0→20.00",
              r and "15.00" in (r.get("before") or "") and "20.00" in (r.get("after") or ""), r)

        # 1c) 本周合计跨月：起点在上个月时，上月最后几天也要算进来
        r = t.ev(r"""(function(){
          var months = {
            '2026-10': { days: { '2026-10-30': {n:10,n3:5,njc:5,cost:3,income:0},
                                '2026-10-31': {n:2,n3:1,njc:1,cost:0.6,income:0} } },
            '2026-11': { days: { '2026-11-01': {n:4,n3:2,njc:2,cost:1.2,income:0},
                                '2026-11-02': {n:3,n3:1,njc:2,cost:0.9,income:0} } }
          };
          var w = window.__alWeekSumOf(months, '2026-10-26', '2026-11-02');
          return { n: w.n, n3: w.n3, njc: w.njc,
                   cost: Math.round(w.cost * 100) / 100, days: w.days };
        })()""")
        check("② 本周合计跨月：上月 10/30~31 也并进来",
              r and r.get("n") == 19 and r.get("n3") == 9 and r.get("njc") == 10
              and r.get("cost") == 5.7 and r.get("days") == 4, r)

        # 2) 收支记账：1000 万两 @0.078 → 实收 74.10
        r = t.ev(r"""(function(){
          function set(id,v){var e=document.getElementById(id); if(!e) return;
            e.value=v; e.dispatchEvent(new Event('input',{bubbles:true})); e.dispatchEvent(new Event('change',{bubbles:true}));}
          set('lg_type','coin'); document.getElementById('lg_type').dispatchEvent(new Event('change',{bubbles:true}));
          set('lg_zone','上海1区'); set('lg_char','自检'); set('lg_wan',1000); set('lg_price',0.078);
          document.getElementById('lg_add').click();
          function t(id){var e=document.getElementById(id); return e? e.textContent.trim(): null;}
          return { inc: t('lg_in'), net: t('lg_net'), cnt: t('lg_cnt'),
                   row: (document.querySelector('#lg_body tr')||{}).innerText };
        })()""")
        check("记账：卖币 1000 万两 @0.078 → 实收 74.10",
              r and r.get("inc", "").endswith("74.10") and r.get("row", "").find("74.10") >= 0, r)

        # 3) 任务板：新增 + 生成 prompt（面板可编辑、复制有提示）
        r = t.ev(r"""(function(){
          var t=function(id){var e=document.getElementById(id); return e? e.textContent: null;};
          document.getElementById('tk_title').value='自检任务';
          document.getElementById('tk_detail').value='来自 selfcheck.py';
          document.getElementById('tk_add').click();
          document.getElementById('tk_gen').click();
          var pe = document.getElementById('tk_prompt');
          var p = pe.value || '';
          var hasTitle = p.indexOf('自检任务')>=0;
          var hasRule = p.indexOf('先复述你的实施计划')>=0;
          var hasExeRule = p.indexOf('不要执行 make_exe.py --publish')>=0;
          pe.value = '手改后的 prompt 内容';
          document.getElementById('tk_copy').click();
          return new Promise(function(res){
            setTimeout(function(){
              var ts = document.getElementById('tk_toast');
              res({ stat: (t('tk_stat')||'').trim(), hasTitle: hasTitle, hasRule: hasRule,
                    hasExeRule: hasExeRule, tag: pe.tagName,
                    kept: pe.value === '手改后的 prompt 内容',
                    toastOn: !!(ts && ts.classList.contains('on')),
                    toastText: ts ? ts.textContent : '' });
            }, 500);
          });
        })()""")
        check("任务板：新增 + prompt 含规则", r and r.get("hasTitle") and r.get("hasRule") and r.get("hasExeRule"), r)
        check("prompt 面板可编辑 + 复制有提示（提示不覆盖原文本）",
              r and r.get("tag") == "TEXTAREA" and r.get("kept")
              and r.get("toastOn") and ("复制" in (r.get("toastText") or "")), r)

        # 3b) 浮窗计算器键位：清空/⌫ 在第一行，+ 与 = 对调
        r = t.ev(r"""(function(){
          var btn = document.getElementById('calcBtn'); if(btn) btn.click();
          var bs = document.querySelectorAll('#mzCalc .pad button');
          function k(i){ return bs[i] ? bs[i].getAttribute('data-k') : null; }
          function hit(kk){ var b=document.querySelector('#mzCalc .pad button[data-k="'+kk+'"]'); if(b) b.click(); }
          hit('C'); hit('1'); hit('2'); hit('+'); hit('3'); hit('=');
          var scr = document.getElementById('mzCalcScr').textContent;
          hit('C');
          if(btn) btn.click();
          return { first: k(0), second: k(1), b15: k(bs.length-2), b16: k(bs.length-1), scr: scr };
        })()""")
        check("计算器：清空/⌫ 置顶，+ 与 = 对调且仍能算 12+3=15",
              r and r.get("first") == "C" and r.get("second") == "B"
              and r.get("b15") == "=" and r.get("b16") == "+" and r.get("scr") == "15", r)

        # 4) 标注 → 任务：点元素、写一句、保存直接生成待办任务（不再存标注）
        r = t.ev(r"""(function(){
          var tabBtn = document.querySelector('#tabs button[data-t="shouyi"]');
          if(tabBtn) tabBtn.click();
          document.getElementById('annoBtn').click();
          var target = document.querySelector('#shouyi .sy-big .k');
          target.dispatchEvent(new MouseEvent('click', {bubbles:true, clientX:400, clientY:300}));
          var opened = document.getElementById('annoPanel').classList.contains('on');
          document.getElementById('annoNote').value = '这里要改成显示万两';
          document.getElementById('annoSave').click();
          var tasks = (MZ3.read('tasks') || {tasks:[]}).tasks || [];
          var made = tasks.filter(function(t){ return t.title.indexOf('这里要改成显示万两') >= 0; })[0];
          var notes = ((MZ3.read('notes') || {items:[]}).items || []).filter(function(n){ return !n.converted; });
          document.getElementById('annoBtn').click();
          document.getElementById('tk_gen').click();
          var p = document.getElementById('tk_prompt').value || '';
          return { opened: opened, made: !!made, detail: made ? made.detail : '',
                   notes: notes.length,
                   inPrompt: p.indexOf('这里要改成显示万两') >= 0,
                   hasAnnoSection: p.indexOf('【页面标注】') >= 0,
                   hasBlock: !!document.getElementById('anno_list') };
        })()""")
        check("标注→任务：保存直接生成待办任务（带页面+选择器），不再存标注",
              r and r.get("opened") and r.get("made") and not r.get("hasAnnoSection")
              and not r.get("hasBlock") and r.get("notes") == 0
              and "shouyi" in (r.get("detail") or "") and "div:nth-of-type" in (r.get("detail") or "")
              and r.get("inPrompt"), r)

        # 4b) 任务板自动同步（__boardMerge）：合并 board.json 新任务
        r = t.ev(r"""(function(){
          var td = MZ3.read('tasks') || {tasks:[]};
          var before = (td.tasks||[]).length;
          var changed = window.__boardMerge({
            tasks: [{id:'t99', title:'同步进来的任务', detail:'来自 board.json', kind:'问题',
                     status:'done', created:1, updated:Date.now()}],
            seq: 100
          });
          var td2 = MZ3.read('tasks') || {tasks:[]};
          return { changed: !!changed, before: before, after: (td2.tasks||[]).length,
                   hasT99: (td2.tasks||[]).some(function(t){ return t.id === 't99'; }) };
        })()""")
        check("任务板自动同步：合并 board.json 新任务",
              r and r.get("changed") and r.get("hasT99") and r.get("after") == r.get("before") + 1, r)

        # 4c) 任务清单三组分开：各自限高、各自滚
        r = t.ev(r"""(function(){
          var tb = document.querySelector('#tabs button[data-t="task"]');
          if(tb) tb.click();
          var tasks = [];
          for(var i=0;i<8;i++) tasks.push({id:'t8'+i, title:'长列表测试 '+i, detail:'细节 '+i,
                                            kind:'问题', status:'done', created:i+1, updated:i+1});
          window.__boardMerge({tasks: tasks, seq: 200});
          var lists = document.querySelectorAll('#tk_list .tk-sec-list');
          var done = lists[lists.length - 1];
          var st = getComputedStyle(done);
          return { groups: document.querySelectorAll('#tk_list .tk-sec-h').length,
                   overflow: st.overflowY, maxH: st.maxHeight,
                   sh: done.scrollHeight, ch: done.clientHeight };
        })()""")
        check("任务清单：三组分开、已解决组限高可滚",
              r and r.get("groups") == 3 and r.get("overflow") == "auto"
              and r.get("maxH") not in (None, "none") and r.get("sh") > r.get("ch"), r)

        # 4) 页签记忆：点任务进度 → 重新加载 → 仍在任务进度
        t.ev("document.querySelector('#tabs button[data-t=\"task\"]').click()")
        time.sleep(1.0)
        t.send("Page.reload", {})
        time.sleep(3.0)
        r = t.ev("(function(){var s=document.querySelector('section.on'); return s && s.id;})()")
        check("页签记忆：重载后仍在「任务进度」", r == "task", r)

        # 5) 开页回归：单价存在 bodywork 里，登录后 ② 必须按这个单价算
        #    （用户报的 -18：② 先渲染、单价后回填，被当成 0）
        t.ev(r"""(function(){
          MZ3.write('bodywork', {chars:1, hours:8, sy_lv:120, sy_cap:900,
                                 sy_p3:2.5, sy_pjc:0.25, sy_rate:42.5, sy_cost:0.45});
          var now = new Date();
          var mk = now.getFullYear() + '-' + ('0' + (now.getMonth() + 1)).slice(-2);
          var dk = mk + '-' + ('0' + now.getDate()).slice(-2);
          var months = {}; months[mk] = { days: {} };
          months[mk].days[dk] = { n:40, n3:17, njc:23, cost:18, income:0, methods: {'3+1':40} };
          MZ3.write('alchemy', { months: months });
          return 1;
        })()""")
        t.send("Page.reload", {})
        time.sleep(3.0)
        r = t.ev(r"""(function(){
          var tr = document.querySelector('#al_body tr');
          return { row: tr ? tr.textContent.replace(/\s+/g, ' ').trim() : null };
        })()""")
        check("② 收益：登录后按 17×2.5 + 23×0.25 − 18 = 30.25",
              r and "30.25" in (r.get("row") or ""), r)

        # 6) 无 JS 异常
        errs = t.ev("(function(){ try{ return JSON.stringify(window.__errs||[]); }catch(e){ return '[]'; } })()")
        check("无 JS 运行异常", errs in (None, "[]"), errs)

    finally:
        try:
            kill_tree(proc.pid)
        except Exception:
            pass
        srv.shutdown()
        shutil.rmtree(PROF, ignore_errors=True)

    bad = [c for c in checks if not c[1]]
    print()
    print(f"共 {len(checks)} 项，通过 {len(checks) - len(bad)}，失败 {len(bad)}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
