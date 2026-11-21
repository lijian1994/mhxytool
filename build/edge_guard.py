# -*- coding: utf-8 -*-
"""无头 Edge 守卫：只清「自己开的」无头浏览器，绝不碰用户自己开的 Edge。

判定标准只有一个：进程命令行里带着 --user-data-dir 指向本工作区 shots\\ 下。
用户日常开的 Edge 用的是默认配置目录，命令行里没有这条，所以永远不会被误杀。

为什么要它：Edge 无头模式会派生 gpu / utility / renderer / crashpad 一串子进程。
脚本末尾只写 p.kill() 的话，主进程死了，子进程变孤儿继续吃内存（实测漏 24 个进程）。
正确做法是 taskkill /T 连整棵树一起收掉 —— 本脚本就是干这个的。

用法：
    python build\\edge_guard.py            # 杀掉全部遗留进程（保留配置目录）
    python build\\edge_guard.py --check    # 只体检，不动手
    python build\\edge_guard.py --purge    # 杀进程 + 删掉遗留下来的配置目录

在别的脚本里复用：
    from edge_guard import kill_stale, kill_tree
    kill_stale()          # 开工前先清一遍
    kill_tree(p.pid)      # 收工时连子进程一起收
"""
import glob
import os
import shutil
import subprocess
import sys

try:                                   # 控制台是 936，但上层按 UTF-8 读；统一按 UTF-8 输出
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHOTS = os.path.join(ROOT, "shots")

# 只取「所有 msedge 进程的 pid/parent/是否无头/user-data-dir」，判定放到 Python 里做，
# 这样规则写死成一条：--user-data-dir 必须落在 SHOTS 目录树内才算自己的进程。
# 用户自己的 Edge、别的项目起的无头 Edge（配置目录在别处、或者用默认配置）都不会被选中。
PS_LIST = r"""
Get-CimInstance Win32_Process -Filter "Name='msedge.exe' or Name='msedgewebview2.exe'" | ForEach-Object {
  $d = ''
  if ($_.CommandLine) {
    $m = [regex]::Match($_.CommandLine, '--user-data-dir=(?:"([^"]+)"|(\S+))')
    if ($m.Success) { if ($m.Groups[1].Value) { $d = $m.Groups[1].Value } else { $d = $m.Groups[2].Value } }
  }
  $h = '0'
  if ($_.CommandLine -and $_.CommandLine -match '--headless') { $h = '1' }
  "$($_.ProcessId)`t$($_.ParentProcessId)`t$h`t$d"
}
"""


def _ps():
    """这台机器上只有 Windows PowerShell 5.1（没有 pwsh 7），按绝对路径调。"""
    for cand in (os.path.join(os.environ.get("SystemRoot", r"C:\WINDOWS"),
                              r"System32\WindowsPowerShell\v1.0\powershell.exe"),
                 "powershell.exe"):
        if os.path.exists(cand) or cand == "powershell.exe":
            return cand
    return "powershell.exe"

PROFILE_PATTERNS = ("edgeprof*", "preprof_*", "rtprof_*", "scprof*", "cdpprof", "evprof", "preprof", "rtprof")
KEEP_DIRS = {"jzb_assets", "jzb_mirror", "sc"}


def _norm_path(p):
    return os.path.normcase(os.path.normpath(p.strip().strip('"'))).rstrip("\\")


def is_own_profile(d):
    """唯一判定标准：--user-data-dir 落在本工作区 shots\\ 目录树内。

    用户自己的 Edge（默认配置，命令行里没有 --user-data-dir）→ False
    别的项目起的无头 Edge（配置目录在它自己项目里 / 在 %TEMP%）→ False
    """
    if not d:
        return False
    try:
        target = _norm_path(d)
    except (OSError, ValueError):
        return False
    root = _norm_path(SHOTS)
    return target == root or target.startswith(root + os.sep)


def filter_own(rows):
    """从进程清单里挑出属于本工作区的，独立成函数方便单独测。"""
    return [r for r in rows if is_own_profile(r.get("dir", ""))]


def list_stale():
    """返回本工作区遗留的无头/测试用 Edge 进程列表（每项含 pid/parent/dir/headless）。"""
    script = PS_LIST
    out = subprocess.run([_ps(), "-NoProfile", "-NonInteractive", "-Command", script],
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=120)
    text = out.stdout.decode("utf-8", "ignore")
    if not text.strip():
        text = out.stdout.decode("mbcs", "ignore")     # PS 5.1 管道默认 ANSI，兜底
    procs = []
    for line in text.splitlines():
        parts = line.rstrip("\r").split("\t")
        if len(parts) < 4 or not parts[0].strip().isdigit():
            continue
        procs.append({"pid": int(parts[0]), "parent": int(parts[1]),
                      "headless": parts[2].strip() == "1", "dir": parts[3].strip()})
    return filter_own(procs)


def kill_tree(pid):
    """taskkill /T 连子进程一起收，避免留下孤儿。"""
    r = subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                       creationflags=0x08000000)   # CREATE_NO_WINDOW
    return r.returncode == 0


_PS_ONE = r"""
$p = Get-CimInstance Win32_Process -Filter "ProcessId=__PID__"
if ($p -and $p.CommandLine) {
  $m = [regex]::Match($p.CommandLine, '--user-data-dir=(?:"([^"]+)"|(\S+))')
  if ($m.Success) { if ($m.Groups[1].Value) { $m.Groups[1].Value } else { $m.Groups[2].Value } }
}
"""


def _dir_of(pid):
    """杀掉之前再确认一次这个 pid 的 --user-data-dir（防 pid 复用时误杀别人）。"""
    script = _PS_ONE.replace("__PID__", str(int(pid)))
    try:
        out = subprocess.run([_ps(), "-NoProfile", "-NonInteractive", "-Command", script],
                             stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=60)
    except Exception:
        return ""
    return out.stdout.decode("utf-8", "ignore").strip()


def kill_if_ours(pid):
    """确认 pid 现在仍属于本工作区的配置目录，才动手。"""
    if not is_own_profile(_dir_of(pid)):
        return False
    return kill_tree(pid)


def kill_stale(verbose=True):
    """清一遍遗留进程，返回 (杀掉的主进程数, 剩余遗留数)。"""
    procs = list_stale()
    if not procs:
        if verbose:
            print("无头 Edge 泄漏检查：0 个遗留，干净。")
        return 0, 0
    pids = {p["pid"] for p in procs}
    # 先杀树根（父进程不在清单里的），子进程会跟着死
    roots = [p["pid"] for p in procs if p["parent"] not in pids]
    killed = sum(1 for pid in (roots or list(pids)) if kill_if_ours(pid))
    left = list_stale()
    if verbose:
        print("清掉遗留无头 Edge：%d 个进程（%d 棵树，实际操作 %d 棵）%s"
              % (len(procs), len(roots), killed,
                 "" if not left else "；仍有 %d 个残留" % len(left)))
        for p in procs[:6]:
            print("   pid %-6d %-8s %s" % (p["pid"], "headless" if p["headless"] else "child", p["dir"]))
        if len(procs) > 6:
            print("   …… 另有 %d 个" % (len(procs) - 6))
    return len(procs), len(left)


def purge_profiles(verbose=True):
    """删掉遗留的测试用 Edge 配置目录（浏览器缓存的坑）。"""
    dirs = []
    for pat in PROFILE_PATTERNS:
        dirs += [d for d in glob.glob(os.path.join(SHOTS, pat)) if os.path.isdir(d)]
    dirs = [d for d in dirs if os.path.basename(d) not in KEEP_DIRS]
    freed = 0
    failed = []
    for d in dirs:
        size = 0
        for base, _dirs, files in os.walk(d):
            for f in files:
                try:
                    size += os.path.getsize(os.path.join(base, f))
                except OSError:
                    pass
        if shutil.rmtree(d, ignore_errors=True) or not os.path.exists(d):
            freed += size
        else:
            failed.append(os.path.basename(d))
    if verbose:
        print("删除遗留配置目录 %d 个，回收 %.0f MB%s"
              % (len(dirs) - len(failed), freed / 1048576.0,
                 "" if not failed else "；清理不掉 %d 个（文件被占用，重启后再来）：%s"
                 % (len(failed), ", ".join(failed))))
    return freed, failed


def main():
    args = sys.argv[1:]
    if "--check" in args:
        procs = list_stale()
        if not procs:
            print("体检通过：没有本工作区遗留的无头 Edge。")
            return 0
        print("发现 %d 个遗留进程：" % len(procs))
        for p in procs:
            print("   pid %-6d %-8s %s" % (p["pid"], "headless" if p["headless"] else "child", p["dir"]))
        return 1
    n, left = kill_stale()
    if "--purge" in args:
        purge_profiles()
    return 0 if left == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
