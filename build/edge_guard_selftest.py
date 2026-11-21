# -*- coding: utf-8 -*-
"""edge_guard 判定规则自测：不启动任何浏览器，纯逻辑 + 一次只读进程扫描。

它回答一个关键问题：**会不会误杀用户自己的 / 别的项目的 Edge？**
用例全部是「不该动」的进程形态，任何一条失败都说明守卫的边界出了问题。

路径全部从 edge_guard.ROOT 推导，所以复制到任何工作区都能跑。

跑法：python build\\edge_guard_selftest.py   （退出码 0 = 全部通过）
"""
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import edge_guard as g

R = g.ROOT
S = g.SHOTS
R_FWD = R.replace("\\", "/")

CASES = [
    (os.path.join(S, "preprof_9331"), True, "本工作区(反斜杠)"),
    (R_FWD + "/shots/_tmp_x", True, "本工作区(正斜杠)"),
    (S.upper() + "\\rtprof_a", True, "本工作区(大小写不同)"),
    (S, True, "刚好是 shots 本身"),
    ('"' + os.path.join(S, "preprof_1") + '"', True, "带引号"),
    (r"D:\work\myproj\.edge-headless", False, "别的项目"),
    ("", False, "无 user-data-dir（用户默认配置）"),
    (r"C:\Users\Administrator\AppData\Local\Temp\edge_prof_123", False, "别的项目用 %TEMP%"),
    (S + "2\\prof", False, "shots2 相似前缀"),
    (S + "_old\\prof", False, "shots_old 相似前缀"),
    (os.path.join(os.path.dirname(R), "other-workspace", "shots", "prof"), False, "另一个工作区的 shots"),
    (os.path.join(R, "build"), False, "本工作区但不是 shots"),
]


def main():
    fails = 0
    print("ROOT  = %s" % R)
    print("SHOTS = %s" % S)
    print("=== 判定规则（is_own_profile）===")
    for d, want, note in CASES:
        got = g.is_own_profile(d)
        ok = got == want
        fails += 0 if ok else 1
        print("%s  %-20s want=%-5s got=%-5s  %s"
              % ("PASS" if ok else "FAIL", note, want, got, d or "(空)"))
    print("规则用例: %d/%d 通过" % (len(CASES) - fails, len(CASES)))

    rows = [{"pid": 1, "parent": 0, "headless": True,
             "dir": os.path.join(S, "a")},
            {"pid": 2, "parent": 0, "headless": True, "dir": r"D:\work\myproj\prof"},
            {"pid": 3, "parent": 0, "headless": False, "dir": ""}]
    picked = [r["pid"] for r in g.filter_own(rows)]
    print("过滤混合清单 -> %s （应为 [1]）" % picked)
    if picked != [1]:
        fails += 1

    # 只读扫描：机器上真实存在的 Edge 进程应该被看到，但一个都不该被选中
    out = subprocess.run([g._ps(), "-NoProfile", "-NonInteractive", "-Command", g.PS_LIST],
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=120)
    raw = [l for l in out.stdout.decode("utf-8", "ignore").splitlines() if l.strip()]
    mine = g.list_stale()
    print("本机 msedge 进程 %d 个；被判为本工作区的 %d 个" % (len(raw), len(mine)))
    for line in raw:
        parts = line.split("\t")
        if len(parts) >= 4:
            print("   pid %-6s headless=%s dir=%s" % (parts[0], parts[2], parts[3] or "(默认配置)"))

    # 杀之前二次确认：用打桩的 kill_tree，绝不真的杀
    calls = []
    real_kill, real_dir = g.kill_tree, g._dir_of
    g.kill_tree = lambda pid: (calls.append(pid), True)[1]
    if raw:
        user_pid = int(raw[0].split("\t")[0])
        ok = g.kill_if_ours(user_pid)
        print("kill_if_ours(用户进程 %d) = %s；kill_tree 调用 %d 次 （应 False / 0）"
              % (user_pid, ok, len(calls)))
        if ok or calls:
            fails += 1
    g._dir_of = lambda pid: os.path.join(S, "_x")
    ok2 = g.kill_if_ours(999999)
    print("kill_if_ours(本工作区 pid) = %s；kill_tree 收到 %s （应 True / [999999]）" % (ok2, calls))
    if not ok2 or calls != [999999]:
        fails += 1
    g.kill_tree, g._dir_of = real_kill, real_dir

    print("=== %s ===" % ("全部通过" if not fails else "有 %d 项失败" % fails))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
