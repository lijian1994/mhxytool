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

        # 3) 任务板：新增 + 生成 prompt
        r = t.ev(r"""(function(){
          var t=function(id){var e=document.getElementById(id); return e? e.textContent: null;};
          document.getElementById('tk_title').value='自检任务';
          document.getElementById('tk_detail').value='来自 selfcheck.py';
          document.getElementById('tk_add').click();
          document.getElementById('tk_gen').click();
          var p = t('tk_prompt') || '';
          return { stat: (t('tk_stat')||'').trim(), hasTitle: p.indexOf('自检任务')>=0,
                   hasRule: p.indexOf('先复述你的实施计划')>=0,
                   hasExeRule: p.indexOf('不要执行 make_exe.py --publish')>=0 };
        })()""")
        check("任务板：新增 + prompt 含规则", r and r.get("hasTitle") and r.get("hasRule") and r.get("hasExeRule"), r)

        # 4) 交互式标注：开标注 → 点元素 → 填备注 → 保存 → 进 prompt
        r = t.ev(r"""(function(){
          var tabBtn = document.querySelector('#tabs button[data-t="shouyi"]');
          if(tabBtn) tabBtn.click();
          document.getElementById('annoBtn').click();
          var target = document.querySelector('#shouyi .sy-big .k');
          target.dispatchEvent(new MouseEvent('click', {bubbles:true, clientX:400, clientY:300}));
          var opened = document.getElementById('annoPanel').classList.contains('on');
          document.getElementById('annoNote').value = '这里要改成显示万两';
          document.getElementById('annoSave').click();
          var items = window.annoList ? window.annoList() : [];
          var badges = document.querySelectorAll('.anno-badge').length;
          document.getElementById('annoBtn').click();   // 先退出标注模式再点生成
          document.getElementById('tk_gen').click();
          var p = document.getElementById('tk_prompt').textContent || '';
          return { opened: opened, count: items.length,
                   note: items[0] && items[0].note, page: items[0] && items[0].page,
                   sel: items[0] && items[0].sel, badges: badges,
                   inPrompt: p.indexOf('页面标注') >= 0 && p.indexOf('这里要改成显示万两') >= 0,
                   rows: document.querySelectorAll('.anno-row').length };
        })()""")
        check("标注：点元素加备注 → 气泡 + 清单 + prompt",
              r and r.get("opened") and r.get("count") == 1 and r.get("badges") == 1
              and r.get("inPrompt") and r.get("rows") == 1, r)

        # 4) 页签记忆：点任务进度 → 重新加载 → 仍在任务进度
        t.ev("document.querySelector('#tabs button[data-t=\"task\"]').click()")
        time.sleep(1.0)
        t.send("Page.reload", {})
        time.sleep(3.0)
        r = t.ev("(function(){var s=document.querySelector('section.on'); return s && s.id;})()")
        check("页签记忆：重载后仍在「任务进度」", r == "task", r)

        # 5) 无 JS 异常
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
