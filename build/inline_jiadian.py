# -*- coding: utf-8 -*-
"""把「模拟加点」页签的 data: iframe 内联进 template2.html（一次性重构）。

做的事情：
1. 解出 iframe 里的 data: URL，拆出 <style> 和 <body>
2. CSS 全部加上 `#jiadian ` 作用域前缀（html/body 映射到 #jiadian）
3. body 内两段脚本合并成一个 IIFE，避免和宿主页的全局变量打架
4. document.querySelectorAll('...') 全部加上 #jiadian 前缀（input,select 单独处理）
5. 状态存取从 postMessage 桥接改成直接 localStorage
6. 删掉宿主侧那份 postMessage 桥接脚本、showTab 里的 iframe 延迟加载分支
7. 版本号 r89 -> r90
"""
import base64
import re
import sys

TPL = r"F:\Documents\deepseek-harness\default-workspace\build\template2.html"
ROOT = "#jiadian"

t = open(TPL, encoding="utf-8").read()
orig_len = len(t)

# ---------- 1) 解出 iframe 负载 ----------
i = t.find('<iframe src="data:text/html;base64,')
if i < 0:
    sys.exit("找不到 jiadian 的 base64 iframe")
j = t.find("</iframe>", i)
b64_start = t.find(",", i) + 1
b64_end = t.find('"', b64_start)
raw = base64.b64decode(t[b64_start:b64_end]).decode("utf-8")

style = re.search(r"<style[^>]*>(.*?)</style>", raw, re.S).group(1)
body = re.search(r"<body[^>]*>(.*?)</body>", raw, re.S).group(1)

# ---------- 2) CSS 作用域化 ----------
def scope_css(css):
    out = []
    pos = 0
    for m in re.finditer(r"([^{}]+)\{([^{}]*)\}", css):
        gap = css[pos:m.start()]
        if gap.strip():
            sys.exit("CSS 里有解析不了的内容: %r" % gap[:80])
        prelude, decl = m.group(1), m.group(2)
        if prelude.strip().startswith("@"):
            sys.exit("CSS 里出现 at-rule，不支持: " + prelude[:40])
        sels = []
        for sel in prelude.split(","):
            sel = sel.strip()
            if not sel:
                continue
            if sel in ("html", "body"):
                sels.append(ROOT)
            else:
                sels.append(ROOT + " " + sel)
        # 去重（html,body 会重复成两遍 #jiadian）
        seen = []
        for s in sels:
            if s not in seen:
                seen.append(s)
        out.append(",".join(seen) + "{" + decl + "}")
        pos = m.end()
    if css[pos:].strip():
        sys.exit("CSS 尾部有解析不了的内容: %r" % css[pos:][:80])
    return "".join(out)

scoped_css = scope_css(style)

# ---------- 3) 脚本：合并 + 作用域 + localStorage ----------
scripts = re.findall(r"<script[^>]*>(.*?)</script>", body, re.S)
if len(scripts) != 2:
    sys.exit("预期 body 里两段脚本，实际 %d" % len(scripts))
logic, bridge = scripts[0], scripts[1]

# 从 body 里摘掉脚本，保留纯标记
markup = re.sub(r"<script[^>]*>.*?</script>", "", body, flags=re.S).strip()

# 3a) 桥接改写：postMessage -> localStorage
bridge = bridge.replace(
    "try{ parent.postMessage({mz:'get'},'*'); }catch(err){}",
    "try{ var __saved = localStorage.getItem(KEY); if(__saved) apply(JSON.parse(__saved)); }catch(err){}")
bridge = bridge.replace(
    "try{ parent.postMessage({mz:'save',data:o},'*'); }catch(err){}",
    "try{ localStorage.setItem(KEY, JSON.stringify(o)); }catch(err){}")
bridge = bridge.replace(
    "try{ parent.postMessage({mz:'clear'},'*'); }catch(err){}",
    "try{ localStorage.removeItem(KEY); }catch(err){}")
bridge = bridge.replace(
    "window.addEventListener('message',function(e){\n    var d=e.data||{};\n    if(d.mz==='state' && apply(d.data)) toast",
    "window.addEventListener('message',function(e){\n    var d=e.data||{};\n    if(d.mz==='state' && apply(d.data)) toast")

merged = logic + "\n" + bridge

# 3b) 所有查询限死在 #jiadian 里
merged = merged.replace("document.querySelectorAll('input,select')",
                        "document.querySelectorAll('#jiadian input,#jiadian select')")
merged = merged.replace("document.querySelectorAll('", "document.querySelectorAll('#jiadian ")
merged = merged.replace("document.querySelector('", "document.querySelector('#jiadian ")
# 已经带前缀的别重复加
merged = merged.replace("document.querySelectorAll('#jiadian #jiadian ", "document.querySelectorAll('#jiadian ")
merged = merged.replace("document.querySelector('#jiadian #jiadian ", "document.querySelector('#jiadian ")

# 3c) toast 挂在页签容器里，别挂到宿主 body
merged = merged.replace("document.body.appendChild(d)",
                        "(document.getElementById('jiadian')||document.body).appendChild(d)")

# ---------- 4) 组装内联块 ----------
inline = ('<style>' + scoped_css + '</style>\n' + markup +
          '\n<script>(function(){\n' + merged + '\n})();</script>')
t = t[:i] + inline + t[j + len("</iframe>"):]

# ---------- 5) 删宿主侧 postMessage 桥接脚本 ----------
m = re.search(r"[ \t]*<script>\s*/\*\s*模拟加点：保存/恢复常规属性.*?</script>", t, re.S)
if not m:
    m = re.search(r"[ \t]*<script>\s*/\*[^*]*postMessage[^*]*\*/.*?</script>", t, re.S)
if not m:
    sys.exit("找不到宿主侧的 postMessage 桥接脚本")
t = t[:m.start()] + t[m.end():]

# ---------- 6) 删 showTab 里的 iframe 延迟加载分支 ----------
m = re.search(r"[ \t]*if\(t==='jiadian'\)\{\s*var f=document\.querySelector\('#jiadian iframe'\);\s*"
              r"if\(f && !f\.getAttribute\('src'\) && f\.dataset\.src\) f\.setAttribute\('src', f\.dataset\.src\);\s*\}\n?", t)
if not m:
    sys.exit("找不到 showTab 里的 iframe 分支")
t = t[:m.start()] + t[m.end():]

# ---------- 7) 版本号 ----------
assert t.count("r89") == 1, "r89 出现次数异常: %d" % t.count("r89")
t = t.replace("V5.3 · r89", "V5.3 · r90")

open(TPL, "w", encoding="utf-8").write(t)
print("template: %d -> %d chars" % (orig_len, len(t)))
print("inlined block: %d chars (css %d / markup %d / js %d)" % (len(inline), len(scoped_css), len(markup), len(merged)))
print("iframe left:", t.count("<iframe"))
print("postMessage left:", t.count("postMessage"))
print("r90:", t.count("V5.3 · r90"))
