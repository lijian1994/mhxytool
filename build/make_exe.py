# -*- coding: utf-8 -*-
"""把 staging 页面打包成单文件桌面 exe（WebView2 宿主）。

用法：
    python build\\make_exe.py            # 编译（要求 shots\\dist 里的产物已是最新）
    python build\\make_exe.py --publish  # 编译并铺到桌面

产物：build\\exe\\out\\梦幻西游实用工具箱.exe
依赖：.NET Framework 4.x 自带 csc.exe + build\\exe\\_sdk 里的 WebView2 SDK
"""
import hashlib
import os
import re
import shutil
import subprocess
import sys

WS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXE_DIR = os.path.join(WS, "build", "exe")
SDK = os.path.join(EXE_DIR, "_sdk", "x")
CSC = r"C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe"

STAGING = os.path.join(WS, "shots", "dist", "梦幻西游实用工具箱-复刻版.html")
TEMPLATE = os.path.join(WS, "build", "template2.html")
OUT_DIR = os.path.join(EXE_DIR, "out")
OUT_EXE = os.path.join(OUT_DIR, "梦幻西游实用工具箱.exe")
DESKTOP = r"F:\Desktop\梦幻西游工具\梦幻西游实用工具箱.exe"


def emit(text):
    """控制台是 GBK 时，csc 的中文警告会编码失败；这里按当前编码替换输出。"""
    enc = sys.stdout.encoding or "utf-8"
    sys.stdout.write(text.encode(enc, "replace").decode(enc) + "\n")


def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def read_version():
    with open(TEMPLATE, "r", encoding="utf-8") as f:
        text = f.read()
    m = re.search(r'class="ver">\s*V(\d+)\.(\d+)\s*·\s*r(\d+)\s*<', text)
    if not m:
        raise SystemExit("模板里找不到版本号（class=\"ver\"）")
    major, minor, rev = m.group(1), m.group(2), m.group(3)
    return "V%s.%s · r%s" % (major, minor, rev), "%s.%s.%s.0" % (major, minor, rev)


def main():
    if not os.path.isfile(CSC):
        raise SystemExit("找不到 csc.exe: " + CSC)
    if not os.path.isfile(STAGING):
        raise SystemExit("staging 产物不存在，先跑 build.py 构建链:\n  " + STAGING)

    ver_text, ver_num = read_version()
    print("版本: %s (%s)" % (ver_text, ver_num))
    print("页面: %d 字节  sha=%s" % (os.path.getsize(STAGING), sha(STAGING)[:12]))

    core = os.path.join(SDK, "lib", "net462", "Microsoft.Web.WebView2.Core.dll")
    wf = os.path.join(SDK, "lib", "net462", "Microsoft.Web.WebView2.WinForms.dll")
    loader = os.path.join(SDK, "runtimes", "win-x64", "native", "WebView2Loader.dll")
    for p in (core, wf, loader):
        if not os.path.isfile(p):
            raise SystemExit("缺少 SDK 文件: " + p)

    # csc 资源名用 ASCII，避免路径里的中文
    payload = os.path.join(EXE_DIR, "payload.html")
    shutil.copyfile(STAGING, payload)

    ver_cs = os.path.join(EXE_DIR, "_ver.cs")
    with open(ver_cs, "w", encoding="utf-8-sig") as f:
        f.write('using System.Reflection;\n')
        f.write('[assembly: AssemblyTitle("梦幻西游实用工具箱")]\n')
        f.write('[assembly: AssemblyProduct("梦幻西游实用工具箱")]\n')
        f.write('[assembly: AssemblyDescription("梦幻西游实用工具箱 %s 桌面版")]\n' % ver_text)
        f.write('[assembly: AssemblyCompany("自用")]\n')
        f.write('[assembly: AssemblyFileVersion("%s")]\n' % ver_num)
        f.write('[assembly: AssemblyVersion("%s")]\n' % ver_num)
        f.write('[assembly: AssemblyInformationalVersion("%s")]\n' % ver_text)

    os.makedirs(OUT_DIR, exist_ok=True)
    cmd = [
        CSC, "/nologo", "/target:winexe", "/platform:x64", "/optimize+", "/warn:4",
        "/codepage:65001",
        "/out:" + OUT_EXE,
        "/win32icon:" + os.path.join(EXE_DIR, "app.ico"),
        "/r:" + core,
        "/r:" + wf,
        "/res:" + payload + ",index.html",
        "/res:" + core + ",WebView2Core.dll",
        "/res:" + wf + ",WebView2WinForms.dll",
        "/res:" + loader + ",WebView2Loader.dll",
        "/res:" + os.path.join(EXE_DIR, "app.ico") + ",app.ico",
        os.path.join(EXE_DIR, "MzToolbox.cs"),
        ver_cs,
    ]
    print("编译中…")
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.stdout.strip():
        emit(r.stdout.strip())
    if r.returncode != 0 or not os.path.isfile(OUT_EXE):
        emit(r.stderr.strip())
        raise SystemExit("编译失败 (exit %d)" % r.returncode)

    size = os.path.getsize(OUT_EXE)
    print("产物: %s" % OUT_EXE)
    print("大小: %d 字节 (%.2f MB)  sha=%s" % (size, size / 1048576.0, sha(OUT_EXE)[:12]))

    if "--publish" in sys.argv:
        # exe 会优先加载同级的 index.html；留着它会让成品跑旧页面，发布前先拦住
        stray = os.path.join(os.path.dirname(DESKTOP), "index.html")
        if os.path.isfile(stray) and "--force" not in sys.argv:
            raise SystemExit(
                "目标目录里有 index.html：%s\n"
                "exe 启动时会优先用它，发布出去等于发旧页面。\n"
                "先删掉它（或改名），确认要这样发再加 --force。" % stray)
        shutil.copyfile(OUT_EXE, DESKTOP)
        print("已铺到: %s  sha=%s" % (DESKTOP, sha(DESKTOP)[:12]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
