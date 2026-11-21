# -*- coding: utf-8 -*-
"""答题器实时识别回归：用真实游戏截图轮播当「画面」，跑 autoTick 全链路并断言答案。

用法:
    python build\\verify_quiz_live.py [html路径]

依赖:
    shots\\quiz_seq\\q*.png   已统一的答题截图（812x663）
    build\\template2.html      页面源码

它会：起本地 http 服务 → 无头 Edge → 把 grabFrame 换成「裁当前测试图的答题框」
→ 打开自动识别 → 每张图停留若干秒 → 断言每张图都识别出预期答案。
无头浏览器走 edge_guard 收整棵树，不弹窗、不留孤儿。
"""
import base64, http.server, json, os, socket, socketserver, struct, subprocess, sys, threading, time, urllib.parse, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
WS = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from edge_guard import kill_stale, kill_tree

try:
    import ctypes
    ctypes.windll.kernel32.SetErrorMode(0x0001 | 0x0002)
except Exception:
    pass

EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
HTML_REL = "shots/dist/梦幻西游实用工具箱-复刻版.html"
SEQ_DIR = "shots/quiz_seq"

EXPECT = {
    "q1_guandang": "官当",
    "q2_bianyi": "颜色不同",
    "q3_caocao": "曹操",
    "q4_chaodai": "唐朝",
    "q5_liangqichao": "梁启超",
}
NAMES = list(EXPECT)


def serve():
    os.chdir(WS)

    class H(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a):
            pass

    httpd = socketserver.TCPServer(("127.0.0.1", 0), H)
    port = httpd.server_address[1]
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd, port


class CDP:
    def __init__(self, port):
        tg = json.load(urllib.request.urlopen(f"http://127.0.0.1:{port}/json/list"))
        ws = [t for t in tg if t.get("type") == "page"][0]["webSocketDebuggerUrl"]
        host, p = ws.split("//")[1].split("/")[0].split(":")
        path = "/" + ws.split("//")[1].split("/", 1)[1]
        self.s = socket.create_connection((host, int(p)), timeout=60)
        key = base64.b64encode(os.urandom(16)).decode()
        self.s.sendall((f"GET {path} HTTP/1.1\r\nHost: {host}:{p}\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
                        f"Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n").encode())
        b = b""
        while b"\r\n\r\n" not in b:
            b += self.s.recv(4096)
        self.mid = 0

    def send(self, m, pr=None):
        self.mid += 1
        pay = json.dumps({"id": self.mid, "method": m, "params": pr or {}}).encode()
        mask = os.urandom(4)
        h = bytes([0x81]); ln = len(pay)
        if ln < 126:
            h += bytes([0x80 | ln])
        elif ln < 65536:
            h += bytes([0x80 | 126]) + struct.pack(">H", ln)
        else:
            h += bytes([0x80 | 127]) + struct.pack(">Q", ln)
        self.s.sendall(h + mask + bytes(x ^ mask[i % 4] for i, x in enumerate(pay)))
        return self.mid

    def rd(self, n):
        d = b""
        while len(d) < n:
            c = self.s.recv(n - len(d))
            if not c:
                raise EOFError
            d += c
        return d

    def recv(self):
        pay = b""
        while True:
            h = self.rd(2); fin = h[0] & 0x80; op = h[0] & 0x0f; ln = h[1] & 0x7f
            if ln == 126:
                ln = struct.unpack(">H", self.rd(2))[0]
            elif ln == 127:
                ln = struct.unpack(">Q", self.rd(8))[0]
            pay += self.rd(ln)
            if op == 9:
                continue
            if fin:
                break
        return json.loads(pay.decode())

    def ev(self, expr, timeout=240):
        rid = self.send("Runtime.evaluate", {"expression": expr, "returnByValue": True, "awaitPromise": True})
        end = time.time() + timeout
        while time.time() < end:
            m = self.recv()
            if m.get("id") == rid:
                r = m.get("result", {})
                if r.get("exceptionDetails"):
                    return {"__exception": r["exceptionDetails"].get("text")}
                return r.get("result", {}).get("value")
        return {"__timeout": True}


JS = """
(async function(){
  const out = { ok: true, per: [], timeline: [] };
  try{
    const names = %s;
    const imgs = [];
    for(const n of names){
      imgs.push(await new Promise(function(res, rej){
        const i = new Image();
        i.onload = function(){ res(i); };
        i.onerror = function(){ rej(new Error('load fail ' + n)); };
        i.src = '/%s/' + n + '.png';
      }));
    }
    const BOX = { x: 0.17, y: 0.50, w: 0.67, h: 0.30 };
    let FRAME = 0;
    grabFrame = function(pad){
      const img = imgs[FRAME];
      if(!img) return null;
      const c = shotEl('shot_canvas');
      let x = BOX.x, y = BOX.y, w = BOX.w, h = BOX.h;
      if(pad){
        x = Math.max(0, x - w * pad); y = Math.max(0, y - h * pad);
        w = Math.min(1 - x, w * (1 + pad * 2)); h = Math.min(1 - y, h * (1 + pad * 2));
      }
      const sx = Math.round(x * img.width), sy = Math.round(y * img.height);
      const sw = Math.max(8, Math.round(w * img.width)), sh = Math.max(8, Math.round(h * img.height));
      const scale = Math.min(5, Math.max(1.5, 1800 / sw));
      c.width = Math.round(sw * scale); c.height = Math.round(sh * scale);
      const g = c.getContext('2d');
      g.imageSmoothingQuality = 'high';
      g.drawImage(img, sx, sy, sw, sh, 0, 0, c.width, c.height);
      return c;
    };
    SHOT_STREAM = { getTracks: function(){ return []; } };
    SHOT_VIDEO = { videoWidth: 812, videoHeight: 663 };
    const realRun = runOcr;
    runOcr = async function(c){
      const frame = FRAME;
      const t0 = Date.now();
      const r = await realRun(c);
      out.per.push({ frame: frame, name: names[frame], ms: Date.now() - t0,
        answer: (document.getElementById('shot_answer').textContent || '').replace(/\\s+/g, ' ').trim() });
      return r;
    };
    toggleAuto();
    out.auto_on = !!AUTO_TIMER;
    const sleep = function(ms){ return new Promise(function(r){ setTimeout(r, ms); }); };
    for(let k = 0; k < imgs.length; k++){
      FRAME = k;
      await sleep(k === 0 ? 14000 : 9000);
      out.timeline.push({ frame: k, name: names[k],
        answer: (document.getElementById('shot_answer').textContent || '').replace(/\\s+/g, ' ').trim() });
    }
    stopAuto(true);
    out.auto_after_stop = !!AUTO_TIMER;
  }catch(e){
    out.ok = false; out.err = String(e && e.message || e);
  }
  return out;
})()
"""


def main():
    html = sys.argv[1] if len(sys.argv) > 1 else os.path.join(WS, HTML_REL)
    if not os.path.exists(html):
        print("!! 找不到 html:", html)
        return 2
    for n in NAMES:
        if not os.path.exists(os.path.join(WS, SEQ_DIR, n + ".png")):
            print("!! 缺少测试图:", n)
            return 2

    httpd, web_port = serve()
    rel = os.path.relpath(html, WS).replace("\\", "/")
    url = "http://127.0.0.1:%d/%s" % (web_port, urllib.parse.quote(rel))

    PROF = os.path.join(WS, "shots", "preprof_quizlive")
    import shutil
    shutil.rmtree(PROF, ignore_errors=True)
    kill_stale(verbose=False)

    port = 9360
    p = subprocess.Popen([EDGE, "--headless=new", "--disable-gpu", "--hide-scrollbars",
                          "--noerrdialogs", "--disable-crash-reporter", "--disable-breakpad",
                          f"--remote-debugging-port={port}", f"--user-data-dir={PROF}",
                          "--window-size=1300,900", "about:blank"],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        time.sleep(3.0)
        c = CDP(port)
        c.send("Page.enable"); c.send("Runtime.enable")
        c.send("Emulation.setDeviceMetricsOverride",
               {"width": 1300, "height": 900, "deviceScaleFactor": 1, "mobile": False})
        c.send("Page.navigate", {"url": url})
        time.sleep(3.5)
        res = c.ev(JS % (json.dumps(NAMES), SEQ_DIR))
    finally:
        kill_tree(p.pid)
        kill_stale(verbose=False)
        httpd.shutdown()

    if not isinstance(res, dict) or not res.get("ok"):
        print("!! 测试异常:", json.dumps(res, ensure_ascii=False))
        return 1

    bad = []
    print("自动识别已启动:", res.get("auto_on"), "· 停止后:", res.get("auto_after_stop"))
    for item in res.get("timeline", []):
        name = item["name"]
        ans = item["answer"]
        want = EXPECT.get(name, "")
        ok = want and want in ans
        print("  %-18s %-5s %s" % (name, "ok" if ok else "!! CHECK", ans[:70]))
        if not ok:
            bad.append(name)

    # 每张图只应识别一次（不重复空转）
    counts = {}
    for it in res.get("per", []):
        counts[it["name"]] = counts.get(it["name"], 0) + 1
    dup = {k: v for k, v in counts.items() if v > 1}
    if dup:
        print("  !! 重复识别:", dup)
        bad.append("dup")

    if not res.get("auto_on") or res.get("auto_after_stop"):
        print("  !! 自动识别开关状态异常")
        bad.append("toggle")

    print("bad:", bad if bad else "无")
    return 0 if not bad else 1


if __name__ == "__main__":
    sys.exit(main())
