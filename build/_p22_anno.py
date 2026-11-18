# -*- coding: utf-8 -*-
"""第一阶段：交互式标注（点元素加备注 + 编号气泡 + 任务板清单 + 并入 prompt）。"""
import io

P = r"F:\Documents\deepseek-harness\default-workspace\build\template2.html"
s = io.open(P, encoding="utf-8").read()


def rep(old, new, cnt=1):
    global s
    assert s.count(old) == cnt, (old[:70], s.count(old))
    s = s.replace(old, new)


# ---------- 1) 顶栏按钮 ----------
rep('<button class="btn gray" id="calcBtn"',
    '<button class="btn gray" id="annoBtn" title="标注模式：点页面任意位置加备注">✏️ 标注</button>\n'
    '        <button class="btn gray" id="calcBtn"')

# ---------- 2) 覆盖层 + 面板 + 脚本 ----------
ANNO = r'''
<div id="annoHi"></div>
<div id="annoBadges"></div>
<div id="annoPanel">
  <div class="ap-h"><span>添加标注</span><span class="ap-x" id="annoClose">✕</span></div>
  <div class="ap-meta"><b id="annoPage">—</b> · <span id="annoText">—</span></div>
  <textarea id="annoNote" placeholder="这条要改什么？说清楚就行，比如：这里的单位要显示成万两"></textarea>
  <div class="ap-b"><button class="btn" id="annoSave">保存标注</button>
    <button class="btn gray" id="annoDel" style="display:none">删除</button>
    <button class="btn gray" id="annoCancel">取消</button>
    <span class="ap-tip" id="annoTip"></span></div>
</div>

<script>
/* ===== 交互式标注（阶段一）===== */
(function(){
  const $ = function(id){ return document.getElementById(id); };
  const KEY = 'notes';
  const PAGE_NAME = { daomai:'库存管理', shouyi:'挂机体活', quiz:'智能答题', renwu:'常用查询',
    jiadian:'模拟加点', jzb:'刷子记账', baoshi:'宝石合成', paoshang:'跑商/倒卖',
    ledger:'收支记账', task:'任务进度', about:'关于', global:'全局（顶栏/侧栏）' };
  let mode = false, editing = null;

  function data(){ var d = MZ3.read(KEY); if(!d || !d.items) d = { items: [] }; return d; }
  function save(d){ MZ3.write(KEY, d); }

  function pageOf(el){
    var sec = el.closest && el.closest('section');
    return sec && sec.id ? sec.id : 'global';
  }
  function cssPath(el){
    var page = pageOf(el);
    var root = page === 'global' ? document.body : document.getElementById(page);
    var parts = [];
    var cur = el;
    while(cur && cur !== root && cur.nodeType === 1 && parts.length < 6){
      var tag = cur.tagName.toLowerCase();
      if(cur.id){ parts.unshift('#' + cur.id); break; }
      var idx = 1, sib = cur;
      while((sib = sib.previousElementSibling)){ if(sib.tagName === cur.tagName) idx++; }
      parts.unshift(tag + ':nth-of-type(' + idx + ')');
      cur = cur.parentElement;
    }
    return parts.join(' > ');
  }
  function labelOf(el){
    var t = (el.textContent || '').replace(/\s+/g, ' ').trim();
    if(t) return t.slice(0, 40);
    return '<' + el.tagName.toLowerCase() + '>';
  }
  function findEl(n){
    var sel = (n.page === 'global' ? '' : '#' + n.page + ' ') + n.sel;
    try{ return document.querySelector(sel); }catch(e){ return null; }
  }

  /* 高亮框（不动原元素样式） */
  var hi = $('annoHi');
  function moveHi(el){
    if(!el || !mode){ hi.style.display = 'none'; return; }
    var r = el.getBoundingClientRect();
    hi.style.display = 'block';
    hi.style.left = (r.left - 2) + 'px';
    hi.style.top = (r.top - 2) + 'px';
    hi.style.width = (r.width + 4) + 'px';
    hi.style.height = (r.height + 4) + 'px';
  }

  /* 编号气泡 */
  function paintBadges(){
    var host = $('annoBadges');
    host.innerHTML = '';
    if(!mode) return;
    var list = data().items;
    list.forEach(function(n, i){
      var el = findEl(n);
      if(!el) return;
      var r = el.getBoundingClientRect();
      if(r.width < 1 && r.height < 1) return;
      var b = document.createElement('div');
      b.className = 'anno-badge';
      b.textContent = String(i + 1);
      b.style.left = Math.max(2, r.left - 9) + 'px';
      b.style.top = Math.max(2, r.top - 9) + 'px';
      b.title = n.note || '';
      b.onclick = function(ev){ ev.stopPropagation(); openPanel(n, true); };
      host.appendChild(b);
    });
  }

  /* 面板 */
  function openPanel(n, existing){
    editing = existing ? n : null;
    $('annoPage').textContent = PAGE_NAME[n.page] || n.page;
    $('annoText').textContent = n.text || n.sel;
    $('annoNote').value = n.note || '';
    $('annoDel').style.display = existing ? '' : 'none';
    $('annoTip').textContent = n.sel ? '' : '';
    $('annoPanel').dataset.sel = n.sel || '';
    $('annoPanel').dataset.page = n.page || 'global';
    $('annoPanel').dataset.text = n.text || '';
    $('annoPanel').classList.add('on');
    $('annoPanel').style.left = Math.min(window.innerWidth - 330, Math.max(12, (n.x || 200))) + 'px';
    $('annoPanel').style.top = Math.min(window.innerHeight - 220, Math.max(12, (n.y || 200))) + 'px';
    setTimeout(function(){ $('annoNote').focus(); }, 30);
    hi.style.display = 'none';
  }
  function closePanel(){ editing = null; $('annoPanel').classList.remove('on'); }

  function commit(){
    var note = $('annoNote').value.trim();
    if(!note){ $('annoTip').textContent = '写点内容再保存'; return; }
    var d = data();
    if(editing){
      editing.note = note; editing.updated = Date.now();
    } else {
      d.items.push({
        id: 'n' + Date.now().toString(36) + Math.floor(Math.random() * 1000),
        page: $('annoPanel').dataset.page,
        sel: $('annoPanel').dataset.sel,
        text: $('annoPanel').dataset.text,
        note: note, ts: Date.now()
      });
    }
    save(d);
    closePanel();
    paintBadges();
    if(window.annoRenderList) window.annoRenderList();
  }
  function remove(){
    if(!editing) return;
    var d = data();
    d.items = d.items.filter(function(x){ return x.id !== editing.id; });
    save(d);
    closePanel();
    paintBadges();
    if(window.annoRenderList) window.annoRenderList();
  }

  /* 模式切换 */
  function setMode(on){
    mode = on;
    document.body.classList.toggle('anno-mode', on);
    $('annoBtn').classList.toggle('on', on);
    $('annoBtn').textContent = on ? '✏️ 标注中（点元素）' : '✏️ 标注';
    if(!on){ hi.style.display = 'none'; closePanel(); }
    paintBadges();
  }
  $('annoBtn').addEventListener('click', function(e){ e.stopPropagation(); setMode(!mode); });
  $('annoSave').addEventListener('click', function(e){ e.stopPropagation(); commit(); });
  $('annoDel').addEventListener('click', function(e){ e.stopPropagation(); remove(); });
  $('annoCancel').addEventListener('click', function(e){ e.stopPropagation(); closePanel(); });
  $('annoClose').addEventListener('click', function(e){ e.stopPropagation(); closePanel(); });

  document.addEventListener('mousemove', function(e){
    if(!mode || $('annoPanel').classList.contains('on')) return;
    var el = e.target;
    if(!el || el.closest('#annoPanel') || el.closest('#annoBadges')) { hi.style.display = 'none'; return; }
    if(el.closest('#tabs') || el.closest('.tbar')) { moveHi(null); return; }
    moveHi(el);
  }, true);

  document.addEventListener('click', function(e){
    if(!mode) return;
    if(e.target.closest('#annoPanel') || e.target.closest('#annoBadges') || e.target.closest('#annoBtn')) return;
    var el = e.target;
    if(el.closest('#tabs') || el.closest('.tbar')){
      var page = el.closest('#tabs') ? 'global' : 'global';
    }
    e.preventDefault(); e.stopPropagation();
    var n = { page: pageOf(el), sel: cssPath(el), text: labelOf(el), note: '', x: e.clientX, y: e.clientY };
    var cur = data().items.filter(function(x){ return x.page === n.page && x.sel === n.sel; })[0];
    openPanel(cur || n, !!cur);
  }, true);

  window.addEventListener('scroll', function(){ if(mode) paintBadges(); }, true);
  window.addEventListener('resize', function(){ if(mode) paintBadges(); });
  document.addEventListener('keydown', function(e){
    if(e.key === 'Escape' && mode) setMode(false);
  });

  /* 任务板清单 */
  function renderList(){
    var host = $('anno_list');
    if(!host) return;
    var items = data().items;
    if(!items.length){ host.innerHTML = '<div class="anno-empty">还没有标注。点顶栏「✏️ 标注」，再点页面上任意位置就能加。</div>'; return; }
    host.innerHTML = items.map(function(n, i){
      return '<div class="anno-row" data-id="' + n.id + '">'
        + '<span class="anno-n">' + (i + 1) + '</span>'
        + '<span class="anno-p">' + (PAGE_NAME[n.page] || n.page) + '</span>'
        + '<span class="anno-t">' + (n.text || n.sel) + '</span>'
        + '<span class="anno-note">' + escHtml(n.note) + '</span>'
        + '<span class="anno-x" title="删除">✕</span>'
        + '</div>';
    }).join('');
    Array.prototype.forEach.call(host.querySelectorAll('.anno-x'), function(x){
      x.onclick = function(){
        var id = x.parentElement.getAttribute('data-id');
        var d = data();
        d.items = d.items.filter(function(v){ return v.id !== id; });
        save(d); paintBadges(); renderList();
      };
    });
  }
  function escHtml(t){
    return String(t == null ? '' : t).replace(/[&<>"]/g, function(c){
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c];
    });
  }
  window.annoRenderList = renderList;
  window.annoList = function(){ return data().items; };
  window.annoGoto = function(id){
    var n = data().items.filter(function(x){ return x.id === id; })[0];
    if(!n) return;
    if(n.page && n.page !== 'global' && window.showTab) showTab(n.page);
    setTimeout(function(){ var el = findEl(n); if(el && el.scrollIntoView) el.scrollIntoView({ block: 'center' }); }, 60);
  };
  renderList();
})();
</script>

<style>
#annoHi{position:fixed;z-index:9990;pointer-events:none;display:none;border:2px solid #6f8ff5;
  border-radius:6px;background:rgba(111,143,245,.10);box-shadow:0 0 0 9999px rgba(0,0,0,0)}
#annoBadges{position:fixed;inset:0;z-index:9991;pointer-events:none}
.anno-badge{position:fixed;width:18px;height:18px;border-radius:50%;background:#e8b45f;color:#1a1205;
  font-size:11px;font-weight:800;line-height:18px;text-align:center;pointer-events:auto;cursor:pointer;
  box-shadow:0 2px 6px rgba(0,0,0,.5)}
body.anno-mode #app,body.anno-mode .tbar,body.anno-mode #tabs{cursor:crosshair}
#annoPanel{position:fixed;z-index:9993;width:310px;display:none;background:#151b2b;border:1px solid #6f8ff5;
  border-radius:12px;box-shadow:0 18px 48px rgba(0,0,0,.6);padding:12px}
#annoPanel.on{display:block}
#annoPanel .ap-h{display:flex;align-items:center;color:#cdd6f4;font-size:12.5px;font-weight:700;margin-bottom:6px}
#annoPanel .ap-h span:first-child{flex:1}
#annoPanel .ap-x{cursor:pointer;color:#8b96b8}
#annoPanel .ap-meta{color:#8b96b8;font-size:11px;margin-bottom:7px;line-height:1.6;word-break:break-all}
#annoPanel textarea{width:100%;height:78px;resize:vertical;background:#0f1320;border:1px solid #3d486e;
  border-radius:8px;color:#fff;font-size:12.5px;padding:7px 9px;font-family:inherit}
#annoPanel .ap-b{display:flex;gap:7px;align-items:center;margin-top:8px;flex-wrap:wrap}
#annoPanel .ap-tip{color:#ff8b8b;font-size:11px}
.anno-list{display:flex;flex-direction:column;gap:6px}
.anno-empty{color:var(--dim);font-size:12px}
.anno-row{display:flex;gap:8px;align-items:center;background:#171d2e;border:1px solid #2b3456;
  border-radius:9px;padding:7px 9px;font-size:12px}
.anno-row .anno-n{flex:0 0 18px;height:18px;border-radius:50%;background:#e8b45f;color:#1a1205;
  font-weight:800;font-size:11px;line-height:18px;text-align:center}
.anno-row .anno-p{flex:0 0 74px;color:#9fb0d8}
.anno-row .anno-t{flex:0 0 150px;color:#cdd6f4;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.anno-row .anno-note{flex:1;color:#e8e3d6;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.anno-row .anno-x{color:#8b96b8;cursor:pointer}
.anno-row .anno-x:hover{color:#ff8b8b}
</style>
'''

rep('</body>', ANNO + '\n</body>')

# ---------- 3) 任务板：标注清单卡片（插在「任务清单」和「生成 prompt」之间） ----------
_cap = s.find('<div class="cap">给 agent 的 prompt')
assert _cap > 0, 'prompt cap not found'
_grp = s.rfind('<div class="grp"', 0, _cap)
assert _grp > 0, 'prompt grp not found'
CARD = '''<div class="grp" style="margin-top:12px">
  <div class="cap">页面标注 <span class="tag ok">点顶栏「✏️ 标注」添加</span></div>
  <div class="anno-list" id="anno_list"></div>
  <div class="sy-note" style="margin-top:8px">标注会一起写进「生成 prompt」，agent 能按选择器直接定位到元素。</div>
</div>

'''
s = s[:_grp] + CARD + s[_grp:]

# ---------- 4) prompt 里并入标注 ----------
rep("""    if(!doing.length && !todo.length) lines.push('（暂无未完成任务）');""",
    """    if(!doing.length && !todo.length) lines.push('（暂无未完成任务）');
    const notes = (window.annoList ? window.annoList() : []) || [];
    if(notes.length){
      lines.push('', '【页面标注】共 ' + notes.length + ' 处（page + CSS 选择器，直接用 querySelector 定位）：');
      notes.forEach(function(n, i){
        lines.push((i + 1) + '. [' + n.page + '] ' + (n.text || n.sel) + '\\n   选择器：' + (n.page === 'global' ? '' : '#' + n.page + ' ') + n.sel + '\\n   要改：' + n.note);
      });
    }""")

# ---------- 5) 导出 / 导入带上标注 ----------
rep("""  function saveFile(){
    const d = data();
    const json = JSON.stringify(d, null, 2);""",
    """  function saveFile(){
    const d = data();
    d.notes = (window.annoList ? window.annoList() : []);
    const json = JSON.stringify(d, null, 2);""")

rep("""    cur.seq = Math.max(cur.seq || 1, obj.seq || 1, cur.tasks.length + 1);
    save(cur);
    render();
    return { added: added, updated: updated };""",
    """    cur.seq = Math.max(cur.seq || 1, obj.seq || 1, cur.tasks.length + 1);
    if(Array.isArray(obj.notes) && obj.notes.length){
      var nd = MZ3.read('notes') || { items: [] };
      nd.items = nd.items || [];
      var seenN = {};
      nd.items.forEach(function(n){ seenN[n.id] = 1; });
      obj.notes.forEach(function(n){ if(n && n.id && !seenN[n.id]) { nd.items.push(n); seenN[n.id] = 1; } });
      MZ3.write('notes', nd);
      if(window.annoRenderList) window.annoRenderList();
    }
    save(cur);
    render();
    return { added: added, updated: updated };""")

# 切到任务进度时刷新标注清单
rep("""    if(t==='jzb'){""",
    """    if(t==='task' && window.annoRenderList){ try{ window.annoRenderList(); }catch(e){} }
    if(t==='jzb'){""")

io.open(P, "w", encoding="utf-8").write(s)
print("标注阶段一已写入；字符数:", len(s))
