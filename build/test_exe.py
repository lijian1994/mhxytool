# -*- coding: utf-8 -*-
"""拿最新的 html 直接跑 exe 自检 —— 改内容时的快速回路，不用重编 exe。

原理：新版 exe 会优先加载**同级目录的 index.html**（没有才用内嵌页面）。
所以这里把产物 html 摆到 shots\\exe-test\\index.html，旁边放一份 exe，
跑一次 --selftest，就能在真实的 WebView2 内核 + https://mztool.local 源下验证。

用法：
    python build\\test_exe.py                 # 用 shots\\dist 里的产物，截「模拟加点」页签
    python build\\test_exe.py --tab about     # 指定截图页签
    python build\\test_exe.py --html <路径>    # 指定别的 html

通过时退出码 0；不通过打印 problems 并返回 1。
"""
import json
import os
import shutil
import subprocess
import sys
import time

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXE = os.path.join(BASE, "build", "exe", "out", "梦幻西游实用工具箱.exe")
STAGING = os.path.join(BASE, "shots", "dist", "梦幻西游实用工具箱-复刻版.html")
STAGE = os.path.join(BASE, "shots", "exe-test")
JSON_OUT = os.path.join(STAGE, "selftest.json")
PNG_OUT = os.path.join(STAGE, "selftest.png")

DETACHED_PROCESS = 0x00000008


def main():
    html = STAGING
    tab = "jiadian"
    args = sys.argv[1:]
    scroll = None
    i = 0
    while i < len(args):
        if args[i] == "--html" and i + 1 < len(args):
            html = args[i + 1]
            i += 2
        elif args[i] == "--tab" and i + 1 < len(args):
            tab = args[i + 1]
            i += 2
        elif args[i] == "--scroll" and i + 1 < len(args):
            scroll = args[i + 1]
            i += 2
        else:
            i += 1

    for p in (EXE, html):
        if not os.path.isfile(p):
            raise SystemExit("缺文件: " + p)

    os.makedirs(STAGE, exist_ok=True)
    shutil.copyfile(EXE, os.path.join(STAGE, "梦幻西游实用工具箱.exe"))
    shutil.copyfile(html, os.path.join(STAGE, "index.html"))
    for stale in (JSON_OUT, PNG_OUT):
        if os.path.isfile(stale):
            os.remove(stale)

    print("页面: %s (%d 字节)" % (html, os.path.getsize(html)))
    print("舞台: %s" % STAGE)

    cmd = [os.path.join(STAGE, "梦幻西游实用工具箱.exe"),
           "--selftest", JSON_OUT, "--shot", PNG_OUT, "--tab", tab]
    if scroll:
        cmd += ["--scroll", scroll]
    # 分离进程：不占用本进程的 stdio，否则 GUI 子进程会把调用方挂住
    proc = subprocess.Popen(cmd, cwd=STAGE, stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL,
                            creationflags=DETACHED_PROCESS)

    deadline = time.time() + 45
    while time.time() < deadline and not os.path.isfile(JSON_OUT):
        time.sleep(0.5)

    if not os.path.isfile(JSON_OUT):
        print("超时：没有等到自检结果（进程 %d）" % proc.pid)
        return 2

    report = json.load(open(JSON_OUT, encoding="utf-8"))
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if os.path.isfile(PNG_OUT):
        print("截图: %s (%d 字节)" % (PNG_OUT, os.path.getsize(PNG_OUT)))
    print()
    if report.get("ok"):
        print("通过 · 要发布就再跑: python build\\make_exe.py --publish，然后删掉同级 index.html")
        return 0
    print("未通过，先改页面再来")
    return 1


if __name__ == "__main__":
    sys.exit(main())
