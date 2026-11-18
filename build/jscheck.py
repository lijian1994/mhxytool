# -*- coding: utf-8 -*-
"""抽出页面里的每段 <script> 存成 .js，交给 node --check 做语法检查。"""
import os, re, shutil, subprocess, sys

HTML = sys.argv[1]
# node 路径：新版 DSH 把运行时放在安装目录（旧版在 ~\.dsh\dsh-runtimes，已不存在）。
# 依次尝试 DSH_RUNTIME_NODE、新版安装目录、旧版位置、PATH，取第一个真实存在的。
_NODE_CANDIDATES = [
    os.environ.get("DSH_RUNTIME_NODE", ""),
    r"E:\DeepSeek Harness\resources\runtime\primary-runtime\dependencies\node\bin\node.exe",
    r"C:\Users\Administrator\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\node\bin\node.exe",
    shutil.which("node") or "",
]
NODE = next((p for p in _NODE_CANDIDATES if p and os.path.isfile(p)), "")
if not NODE:
    sys.exit("找不到 node.exe：设置 DSH_RUNTIME_NODE，或把 node 放进 PATH")
OUTDIR = r"F:\Documents\deepseek-harness\default-workspace\shots\jscheck"
os.makedirs(OUTDIR, exist_ok=True)

s = open(HTML, encoding="utf-8").read()
blocks = re.findall(r"<script([^>]*)>(.*?)</script>", s, re.S)
print("script blocks:", len(blocks))
bad = 0
for i, (attrs, body) in enumerate(blocks):
    if "src=" in attrs:
        continue
    if not body.strip():
        continue
    fn = os.path.join(OUTDIR, "block%02d.js" % i)
    open(fn, "w", encoding="utf-8").write(body)
    r = subprocess.run([NODE, "--check", fn], capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        bad += 1
        print("FAIL block", i, "len", len(body))
        print(r.stderr[:1200])
    else:
        print("ok   block %-2d len %d" % (i, len(body)))
print("bad:", bad)
sys.exit(1 if bad else 0)
