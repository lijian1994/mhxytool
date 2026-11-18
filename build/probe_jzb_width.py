# -*- coding: utf-8 -*-
"""量记账本页在不同窗口宽度下有没有被挤掉/裁掉：横向溢出、列宽、表格宽度。"""
import base64, json, os, socket, struct, subprocess, sys, time, urllib.request, shutil

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from edge_guard import kill_stale, kill_tree

try:
    import ctypes
    ctypes.windll.kernel32.SetErrorMode(0x0001 | 0x0002)
except Exception:
    pass

EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
URL = sys.argv[1]
PORT = int(sys.argv[2]) if len(sys.argv) > 2 else 9290
PROF = r"F:\Documents\deepseek-harness\default-workspace\shots\preprof_w"
shutil.rmtree(PROF, ignore_errors=True)
kill_stale(verbose=False)
p = subprocess.Popen([EDGE, "--headless=new", "--disable-gpu", "--noerrdialogs",
                      "--disable-crash-reporter", "--disable-breakpad",
                      f"--remote-debugging-port={PORT}", f"--user-data-dir={PROF}",
                      "--window-size=1300,900", "about:blank"],
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
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
    rid = send("Runtime.evaluate", {"expression": expr, "returnByValue": True})
    while True:
        m = recv()
        if m.get("id") == rid:
            r = m.get("result", {})
            if "exceptionDetails" in r:
                return "__ERR__"
            return r.get("result", {}).get("value")


send("Page.enable"); send("Runtime.enable")
PROBE = r"""(function(){
  function r(sel){ var e=document.querySelector(sel); if(!e) return null;
    var b=e.getBoundingClientRect(); return {w:Math.round(b.width),right:Math.round(b.right),sw:e.scrollWidth,cw:e.clientWidth}; }
  var g=list=>list;
  return {
    vw: innerWidth, docSW: document.documentElement.scrollWidth,
    body: r('.body'), tbx: r('#jzb .tbx'), left: r('#jzb .tbx-left'), right: r('#jzb .tbx-right'),
    item1: r('#item1 .item_list'), item2: r('#item2 .item_list'),
    rec: r('#jzb .record_box'), table: r('#jzb .record_table'),
    cols1: getComputedStyle(document.querySelector('#item1 .item_list')).gridTemplateColumns,
    cols2: getComputedStyle(document.querySelector('#item2 .item_list')).gridTemplateColumns,
    grpOverflow: getComputedStyle(document.querySelector('#jzb .grp')||document.body).overflow
  };
})()"""
send("Page.navigate", {"url": URL})
time.sleep(3.0)
ev("document.querySelector('#tabs button[data-t=\"jzb\"]').click()")
time.sleep(0.6)
OVER = """(function(){
  var out=[];
  document.querySelectorAll('#jzb *').forEach(function(el){
    if(el.clientWidth > 0 && el.scrollWidth > el.clientWidth + 2){
      out.push(el.tagName+'#'+(el.id||'')+'.'+((el.className||'').toString().split(' ')[0])+' sw='+el.scrollWidth+' cw='+el.clientWidth);
    }
  });
  return out;
})()"""
print("overflowing elements:", json.dumps(ev(OVER), ensure_ascii=False))
for w in (1600, 1440, 1300, 1200, 1100, 1000, 900):
    send("Emulation.setDeviceMetricsOverride", {"width": w, "height": 900, "deviceScaleFactor": 1, "mobile": False})
    time.sleep(0.45)
    print(w, json.dumps(ev(PROBE), ensure_ascii=False))
kill_tree(p.pid)
kill_stale(verbose=True)
