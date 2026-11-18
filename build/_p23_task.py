# -*- coding: utf-8 -*-
"""任务板 r101：自动写盘（exe）、网页版定位说明、历史进度视图。"""
import io

P = r"F:\Documents\deepseek-harness\default-workspace\build\template2.html"
s = io.open(P, encoding="utf-8").read()

beg = s.find('<section id="task">')
end = s.find('</section>', beg)
assert beg > 0 and end > beg
seg = s[beg:end]


def rep(old, new, cnt=1):
    global seg
    assert seg.count(old) == cnt, (old[:70], seg.count(old))
    seg = seg.replace(old, new)


# ---------- 1) 保存后自动写盘（只在 exe 里发） ----------
rep("  function save(d){ MZ3.write(KEY, d); }",
    """  function save(d){
    MZ3.write(KEY, d);
    // exe 里每次变更自动同步到 exe 旁边的 任务板.json，agent 随时能读到最新状态
    var host = (window.chrome && window.chrome.webview) ? window.chrome.webview : null;
    if(host){
      try{
        host.postMessage('TBA|save|' + JSON.stringify({
          tasks: d.tasks || [], seq: d.seq || 1,
          notes: (window.annoList ? window.annoList() : [])
        }));
      }catch(e){}
    }
  }""")

# ---------- 2) 历史进度卡片 ----------
card_anchor = '<div class="grp" style="margin-top:12px">\n  <div class="cap">页面标注'
assert seg.count(card_anchor) == 1, seg.count(card_anchor)
HIST = '''<div class="grp" style="margin-top:12px">
  <div class="cap">历史进度 <span class="tag ok">按完成日期</span></div>
  <div id="tk_hist"></div>
</div>

'''
seg = seg.replace(card_anchor, HIST + card_anchor)

# ---------- 3) 网页版定位说明 ----------
k = seg.find('</style>')
assert k > 0
seg = seg[:k + len('</style>')] + '''
<div class="tk-webnote" id="tk_webnote">网页版是<b>开发预览版</b>：数据存在你当前浏览器里，与 exe 不互通；实际记账/统计请在 exe 里做。</div>
''' + seg[k + len('</style>'):]

# ---------- 4) renderHistory ----------
rep("""  function render(){
    const d = data();""",
    """  function renderHistory(){
    const host = $('tk_hist');
    if(!host) return;
    const done = (data().tasks || []).filter(function(t){ return t.status === 'done'; });
    if(!done.length){ host.innerHTML = '<div class="tk-empty">还没有已完成的任务</div>'; return; }
    function dayKey(ts){
      const d = new Date(ts || Date.now());
      return d.getFullYear() + '-' + ('0' + (d.getMonth() + 1)).slice(-2) + '-' + ('0' + d.getDate()).slice(-2);
    }
    const now = new Date();
    const weekAgo = new Date(now.getFullYear(), now.getMonth(), now.getDate() - 6).getTime();
    const week = done.filter(function(t){ return (t.updated || 0) >= weekAgo; }).length;
    const byDay = {};
    done.forEach(function(t){ const kk = dayKey(t.updated || t.created); (byDay[kk] = byDay[kk] || []).push(t); });
    const days = Object.keys(byDay).sort().reverse();
    let html = '<div class="tk-hist-sum">累计完成 <b>' + done.length + '</b> 条 · 近 7 天 <b>' + week + '</b> 条</div>';
    days.forEach(function(kk){
      const arr = byDay[kk].slice().sort(function(a, b){ return (b.updated || 0) - (a.updated || 0); });
      html += '<div class="tk-hist-day"><span class="d">' + kk + '</span><span class="n">' + arr.length + ' 条</span></div>';
      html += '<ul class="tk-hist-ul">';
      arr.forEach(function(t){
        html += '<li>' + esc(t.title) + (t.kind ? '<span class="k">' + esc(t.kind) + '</span>' : '') + '</li>';
      });
      html += '</ul>';
    });
    host.innerHTML = html;
  }

  function render(){
    const d = data();
    renderHistory();""")

# ---------- 5) 样式 ----------
rep('</style>\n<div class="tk-webnote"',
    '''.tk-webnote{background:rgba(232,180,95,.08);border:1px solid rgba(232,180,95,.35);border-radius:9px;
  padding:7px 11px;font-size:12px;color:#d8c9a8;margin-bottom:10px}
.tk-webnote b{color:#e8b45f}
.tk-hist-sum{color:var(--dim);font-size:12px;margin:2px 0 8px}
.tk-hist-sum b{color:#e8b45f}
.tk-hist-day{display:flex;align-items:center;gap:8px;margin:9px 0 4px;font-size:12px}
.tk-hist-day .d{color:#9fb0d8;font-weight:700}
.tk-hist-day .n{color:var(--dim)}
.tk-hist-ul{margin:0;padding-left:18px;color:#cdd6f4;font-size:12px;line-height:1.9}
.tk-hist-ul .k{color:var(--dim);font-size:11px;margin-left:6px}
</style>

<div class="tk-webnote"''')

# ---------- 6) 网页版才显示那条说明 ----------
rep("""  render();
})();
</script>""",
    """  render();
  var inExe = !!(window.chrome && window.chrome.webview);
  if(inExe){ var wn = $('tk_webnote'); if(wn) wn.style.display = 'none'; }
})();
</script>""")

s = s[:beg] + seg + s[end:]
io.open(P, "w", encoding="utf-8").write(s)
print("任务板 r101 改造完成；字符数:", len(s))
