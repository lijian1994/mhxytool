import base64, urllib.request
BASE = r"F:\Documents\deepseek-harness\default-workspace"
REF = {"User-Agent": "Mozilla/5.0", "Referer": "http://xyq.yzz.cn/special/tools/rwsxmn.html"}

def g(n):
    return urllib.request.urlopen(
        urllib.request.Request("http://xyq.yzz.cn/special/tools/img/rwsxmn/" + n, headers=REF),
        timeout=30).read()

dlg = "data:image/png;base64," + base64.b64encode(g("dialog.png")).decode()
ico = "data:image/png;base64," + base64.b64encode(g("icon.png")).decode()
js = open(BASE + r"\shots\app5.js", encoding="utf-8").read()

ROWS = [("jibie", 49, 34, 39, ""), ("mingcheng", 132, 34, 115, ""),
        ("chengwei", 50, 56, 114, ""), ("renqi", 203, 56, 45, "0"),
        ("bangpai", 49, 79, 114, ""), ("banggong", 203, 79, 45, "0"),
        ("menpai", 49, 102, 115, ""), ("gongxian", 203, 102, 45, "0"),
        ("qixue", 49, 133, 199, ""), ("mofa", 49, 156, 199, ""), ("fennu", 49, 179, 199, "0/150"),
        ("huoli", 49, 202, 199, ""), ("tili", 49, 225, 199, ""),
        ("mingzhong", 49, 256, 45, ""), ("tizhi", 144, 256, 53, ""),
        ("shanghai", 49, 279, 45, ""), ("moli", 144, 279, 53, ""),
        ("fangyu", 49, 302, 45, ""), ("liliang", 144, 302, 53, ""),
        ("sudu", 49, 325, 45, ""), ("naili", 144, 325, 53, ""),
        ("fashang", 49, 348, 45, ""), ("minjie", 144, 348, 53, ""),
        ("fafang", 49, 371, 45, ""), ("qianli", 133, 371, 39, "0"),
        ("shengji-jingyan", 79, 402, 93, ""), ("huode-jingyan", 79, 425, 93, "")]
READONLY = {"qixue", "mofa", "mingzhong", "shanghai", "fangyu", "sudu", "fashang", "fafang",
            "shengji-jingyan", "huode-jingyan", "fennu", "huoli", "tili", "qianli"}
SCHOOLS = [("ren", "大唐官府"), ("ren", "化生寺"), ("ren", "方寸山"), ("ren", "女儿村"),
           ("ren", "神木林"), ("ren", "天机城"), ("xian", "天宫"), ("xian", "龙宫"),
           ("xian", "五庄观"), ("xian", "普陀山"), ("xian", "凌波城"), ("xian", "花果山"),
           ("mo", "魔王寨"), ("mo", "狮驼岭"), ("mo", "阴曹地府"), ("mo", "盘丝洞"),
           ("mo", "无底洞"), ("mo", "女魃墓")]


def panel(pid):
    out = []
    for n, x, y, w, v in ROWS:
        if n == "menpai":
            # value 用门派名（唯一），种族放 data-race：以前 value 只有 ren/xian/mo，
            # 存档恢复时「凌波城」和「天宫」都存成 xian，回来就落到第一个仙族门派 → 见 r63 修复
            opts = "".join("<option value='%s' data-race='%s'%s>%s</option>" % (b, a, " selected" if b == "普陀山" else "", b) for a, b in SCHOOLS)
            out.append("<select name='menpai' style='left:%dpx;top:%dpx;width:%dpx'>%s</select>" % (x, y, w, opts))
        else:
            ro = " readonly" if n in READONLY else ""
            out.append("<input name='%s'%s value='%s' style='left:%dpx;top:%dpx;width:%dpx'>" % (n, ro, v, x, y, w))
    for k, y in [("tizhi", 256), ("moli", 279), ("liliang", 302), ("naili", 325), ("minjie", 348)]:
        out.append("<div class='add' data-k='%s' style='left:203px;top:%dpx'></div>" % (k, y - 2))
        out.append("<div class='dec' data-k='%s' style='left:223px;top:%dpx'></div>" % (k, y - 2))
    return "<div class='pwrap'><div class='panel' id='%s'>" % pid + "".join(out) + "</div></div>"


SKILLS = [("qs", "强身术"), ("mx", "冥想"), ("qz", "强壮"),
          ("ss", "神速"), ("shengyang", "养生之道"), ("jianshen", "健身术")]
SKILL_DEF = {}
skill_html = "".join(
    "<label><span>%s</span><input id='%s' type='number' min='0' max='160' value='%d'><em>级</em></label>"
    % (n, i, SKILL_DEF.get(i, 0))
    for i, n in SKILLS)

ATTRS = [("tizhi", "体质"), ("moli", "魔力"), ("liliang", "力量"), ("naili", "耐力"), ("minjie", "敏捷")]
OATTR = [("tizhi","体质"),("moli","魔力"),("liliang","力量"),("naili","耐力"),("minjie","敏捷")]
OTHERS = [("qixue","气血"),("mofa","魔法"),("mingzhong","命中"),("shanghai","伤害"),
          ("fangyu","防御"),("sudu","速度"),("lingli","灵力"),("fashang","法伤"),("fafang","法防")]
ODEF = {}
OC = (
    '<div class="fwrap">'
    '<div class="fcol"><div class="sk-sub">基础属性</div><div class="flist">' +
    "".join("<label><span>%s</span><input class='eq' data-t='%s' type='number' value='%d'></label>"
            % (n, a, ODEF.get(a, 0)) for a, n in OATTR) +
    '</div></div>'
    '<div class="fcol"><div class="sk-sub">面板属性</div><div class="flist">' +
    "".join("<label><span>%s</span><input class='eq' data-a='%s' type='number' value='%d'></label>"
            % (n, a, ODEF.get(a, 0)) for a, n in OTHERS) +
    '</div></div>'
    '</div>')

EQ = [
    ("武器", [("mingzhong", "命中", "a"), ("shanghai", "伤害", "a"), ("fashang", "法伤", "a")], True),
    ("衣服", [("fangyu", "防御", "a"), ("qixue", "气血", "a"), ("lingli", "灵力", "a"), ("fafang", "法防", "a")], True),
    ("头盔", [("fangyu", "防御", "a"), ("mofa", "魔法", "a"), ("shanghai", "伤害", "a"), ("mingzhong", "命中", "a"), ("fafang", "法防", "a")], False),
    ("项链", [("lingli", "灵力", "a"), ("fashang", "法伤", "a")], False),
    ("腰带", [("fangyu", "防御", "a"), ("qixue", "气血", "a"), ("sudu", "速度", "a"), ("fafang", "法防", "a")], False),
    ("鞋子", [("fangyu", "防御", "a"), ("minjie", "敏捷", "t"), ("sudu", "速度", "a"), ("fafang", "法防", "a")], False),
]

EQ_DEF = {}
AFFIX_DEF = {}
SHOE_MINJIE = 0
rows_html = ""
for nm, base, has_affix in EQ:
    base_cells = "".join(
        "<label><span>%s</span><input class='eq' data-%s='%s' type='number' value='%d'></label>"
        % (n, kind, a, SHOE_MINJIE if (nm == "鞋子" and a == "minjie") else EQ_DEF.get((nm, n), 0))
        for a, n, kind in base)
    if has_affix:
        affix_cells = "".join(
            "<label><span>%s</span><input class='eq' data-t='%s' type='number' value='%d'></label>"
            % (n, a, AFFIX_DEF.get((nm, n), 0))
            for a, n in ATTRS)
    else:
        affix_cells = "<span class='none'>该部位无附加</span>"
    rows_html += ("<tr><th>%s</th><td><div class='f'>%s</div></td>"
                  "<td><div class='f'>%s</div></td></tr>"
                  % (nm, base_cells, affix_cells))

doc = '''<!DOCTYPE html><html><head><meta charset="utf-8"><style>
html,body{margin:0;padding:0;background:#eef4f6;font-family:"Microsoft YaHei",SimSun;color:#1f3d4d}
.tabs{position:relative;display:flex;gap:10px;justify-content:center;padding:16px 0 12px}
.tools{position:absolute;right:0;bottom:12px;display:flex;gap:8px}
.tools button{height:28px;padding:0 13px;border-radius:14px;border:1px solid #cfe0e6;background:#fff;
 color:#3f96a6;font-size:12.5px;font-family:inherit;cursor:pointer;transition:.15s}
.tools button:hover{background:#e8f4f6;border-color:#9fd0d8}
.tools button.warn{color:#c0392b;border-color:#e6c3bd}
.tools button.warn:hover{background:#fdf0ee}
#mz-toast{position:fixed;left:50%;top:64px;transform:translateX(-50%);background:rgba(31,61,77,.92);color:#fff;
 padding:8px 16px;border-radius:16px;font-size:13px;opacity:0;transition:.2s;pointer-events:none;z-index:9}
#mz-toast.show{opacity:1}
.tab{width:120px;height:36px;line-height:36px;text-align:center;color:#4a7a86;font-size:14px;background:#fff;
 border:1px solid #cfe0e6;border-radius:18px;cursor:pointer;transition:.15s}
.tab.on{background:linear-gradient(180deg,#5fb3c0,#3f96a6);color:#fff;border-color:#3f96a6;box-shadow:0 3px 10px rgba(63,150,166,.25)}

.layout{display:grid;grid-template-columns:430px 700px;gap:24px;align-items:start;width:1200px;margin:0 auto;padding:8px 0 18px}
.layout.cmp{grid-template-columns:1fr;justify-items:center}
.layout.cmp .left,.layout.cmp .eqbox{display:none}
.col{display:flex;flex-direction:column;gap:14px}

.card{background:#fff;border:1px solid #dbe9ee;border-radius:12px;box-shadow:0 2px 10px rgba(31,61,77,.05);padding:14px 16px}
.card-t{font-size:13px;font-weight:700;color:#2c5a6c;margin-bottom:12px;display:flex;align-items:center;gap:6px}
.card-t:before{content:"";width:3px;height:13px;background:#5fb3c0;border-radius:2px}
.skills{display:grid;grid-template-columns:1fr 1fr;gap:12px 14px}
.skills label{display:grid;grid-template-columns:54px 54px 12px;align-items:center;gap:5px;font-size:12.5px;color:#4a6b7a}
.skills input{width:54px;height:28px;border:1px solid #cfe0e6;border-radius:7px;text-align:center;font-size:13px;
 font-family:inherit;color:#1f3d4d;background:#f9fcfd}
.skills input:focus{outline:none;border-color:#5fb3c0;box-shadow:0 0 0 3px rgba(95,179,192,.15)}
.skills em{font-style:normal;color:#9ab;font-size:11px}
#tl-info{margin-top:12px;padding-top:10px;border-top:1px dashed #e3eef1;font-size:12px;color:#5a7d8c;line-height:1.9}
#tl-info b{color:#1a6b7c}
.sum{display:flex;justify-content:space-between;align-items:baseline;padding:6px 0;border-bottom:1px dashed #eef4f6;font-size:12.5px;color:#5a7d8c}
.sum:last-child{border-bottom:0}
.sum b{font-size:16px;color:#1a6b7c;font-variant-numeric:tabular-nums}
.tips{font-size:11.5px;color:#6b8b98;line-height:2}
.center{display:flex;justify-content:center;align-items:center;padding-top:4px}
.wrap{display:flex;justify-content:center;gap:48px}
.pwrap{width:258px;height:453px;flex:0 0 auto}#view0 .pwrap{width:439px;height:770px}#view0 .panel{transform:scale(1.7);transform-origin:top left;visibility:hidden}.panel{position:relative;width:258px;height:453px;background:url("''' + dlg + '''") no-repeat 0 0;flex:0 0 258px}
.panel input,.panel select{position:absolute;height:17px;line-height:17px;border:0;background:transparent;font-size:13px;
 font-family:SimSun;color:#1a2430;text-align:center;padding:0;outline:none;box-sizing:border-box}
.panel select{-webkit-appearance:none;appearance:none;text-align:left;padding-left:4px}
.panel .add,.panel .dec{position:absolute;width:18px;height:18px;cursor:pointer;background:url("''' + ico + '''") no-repeat}
.panel .add{background-position:0 top}
.panel .dec{background-position:-22px top}
.eqbox{grid-column:1 / -1;width:1200px;margin:16px auto 24px}
.eqtable{width:100%;border-collapse:separate;border-spacing:0;font-size:12px}
.eqtable thead th{background:#f4fafb;color:#4a7a86;font-weight:600;padding:9px 12px;border-bottom:1px solid #dbe9ee;text-align:left;font-size:12px}
.eqtable thead th:first-child{border-radius:10px 0 0 0}
.eqtable thead th:last-child{border-radius:0 10px 0 0}
.eqtable tbody th{width:64px;color:#2c5a6c;font-weight:600;padding:10px 12px;border-bottom:1px solid #f0f6f8;text-align:left}
.eqtable tbody td{padding:8px 12px;border-bottom:1px solid #f0f6f8;vertical-align:middle}
.eqtable tbody tr:last-child td,.eqtable tbody tr:last-child th{border-bottom:0}
.f{display:flex;flex-wrap:wrap;gap:8px 12px}
.f label{display:flex;align-items:center;gap:4px;font-size:11.5px;color:#7b96a3}
.f input{width:64px;height:26px;border:1px solid #cfe0e6;border-radius:7px;text-align:center;font-size:12.5px;
 font-family:inherit;color:#1f3d4d;background:#f9fcfd}
.f input:focus{outline:none;border-color:#5fb3c0;box-shadow:0 0 0 3px rgba(95,179,192,.15)}
.none{color:#c2d2d8;font-size:11.5px}
.eq-tip{margin-top:12px;font-size:11px;color:#8aa3ae;line-height:1.8}

.skh{display:flex;flex-wrap:wrap;gap:10px 20px}.skh label{display:flex;align-items:center;gap:5px;grid-template-columns:none}.frow{display:flex;flex-wrap:wrap;gap:8px 2px;margin-bottom:2px}.frow label{display:inline-flex;align-items:center;gap:3px;font-size:12.5px;color:#4a6b7a;width:auto}.frow input{width:40px;height:25px;border:1px solid #cfe0e6;border-radius:6px;text-align:center;font-size:13px;font-family:inherit;color:#1f3d4d;background:#f9fcfd}.frow input:focus{outline:none;border-color:#5fb3c0;box-shadow:0 0 0 3px rgba(95,179,192,.15)}.fwrap{display:flex;flex-direction:column;gap:12px}.fcol{flex:0 0 auto;min-width:0}.flist{display:flex;flex-wrap:wrap;gap:10px 22px}.flist label{display:inline-flex;align-items:center;gap:6px;font-size:12.5px;color:#4a6b7a}.flist input{width:58px;height:25px;border:1px solid #cfe0e6;border-radius:6px;text-align:center;font-size:13px;font-family:inherit;color:#1f3d4d;background:#f9fcfd}.flist input:focus{outline:none;border-color:#5fb3c0;box-shadow:0 0 0 3px rgba(95,179,192,.15)}.sk-sub{grid-column:1 / -1;margin:8px 0 2px;font-size:12px;color:#4a7a86;font-weight:600;border-bottom:1px dashed #dbe9ee;padding-bottom:2px}
</style></head><body>
<div class="tabs"><div class="tab on">模拟属性</div><div class="tab">开启对比</div>
  <div class="tools"><button id="mz-save">保存</button><button id="mz-clear" class="warn">清空</button></div></div>
<div class="layout">
  <div class="col left">
    <div class="card"><div class="card-t">辅助技能</div><div class="skills">''' + skill_html + '''</div><div id="tl-info"></div></div>
    <div class="card"><div class="card-t">师门技能</div><div class="skills" id="skbox"></div><div id="sk-note" style="margin-top:8px;font-size:11px;color:#8aa3ae"></div></div>
<div class="card"><div class="card-t">坐骑（骑乘）</div>
      <div class="sk-sub">骑乘属性（直接加给人物）</div><div class="skills">
        <label><span>体质</span><input id="mt_tizhi" type="number" value=""></label>
        <label><span>魔力</span><input id="mt_moli" type="number" value=""></label>
        <label><span>力量</span><input id="mt_liliang" type="number" value=""></label>
        <label><span>耐力</span><input id="mt_naili" type="number" value=""></label>
        <label><span>敏捷</span><input id="mt_minjie" type="number" value=""></label>
      </div>
      <div id="mt-info" style="margin-top:8px;font-size:11px;color:#8aa3ae"></div></div>
  </div>
  <div class="center">
    <div id="view0" class="wrap">''' + panel('p0') + '''</div>
    <div id="view1" class="wrap" style="display:none">''' + panel('p1') + panel('p2') + '''</div>
  </div>
  </div>
<div class="eqbox"><div class="card">
  <div class="card-t">符石（含其它加成）</div>
  ''' + OC + '''
</div></div>
<div class="eqbox"><div class="card">
  <div class="card-t">装备附加属性</div>
  <table class="eqtable">
    <thead><tr><th>部位</th><th>基础属性（含宝石）</th><th>附加属性</th></tr></thead>
    <tbody>''' + rows_html + '''</tbody>
  </table>
  <div class="eq-tip">基础属性直接填「装备基础 + 宝石」的合计值；附加属性仅武器与衣服可打造出（体质/魔力/力量/耐力/敏捷）。</div>
</div></div>
<div class="eqbox"><div class="card">
  <div class="card-t">计算说明</div>
  <div class="tips">
    <b style="color:#2f8f5b">✔ 与你面板逐项验证</b><br>
    气血 =（体质×4.5 + 100 + 装备）×（1+强身%）<br>
    魔法 =（魔力×3.5 + 80 + 装备）×（1+冥想%）<br>
    命中 = 力量×1.7 + 30 + 装备 + 师门命中技能<br>
    伤害 = 力量×0.6 + 40 + 装备伤害 + 装备命中÷3 + 师门命中÷3 + 师门伤害技能<br>
    防御 = 耐力×1.6 + 装备 + 师门防御技能<br>
    速度 = 敏×0.7 + 体/力/耐×0.1 + 装备 + 神速/师门速度<br>
    灵力 = 0.3体+0.7魔+0.4力+0.2耐 + 装备 + 师门灵力技能<br>
    法伤 = 灵力 + 武器伤害÷4；法防 = 灵力<br>
    活力/体力上限 = 50 + 等级×5 + 养生/健身×4
  </div>
</div></div>
<script>''' + js + '''</script>
<script>
(function(){
  /* 保存 / 恢复的是「整页所有输入项」：门派、等级、技能、骑乘、符石、装备、面板全要 */
  var KEY='mz.common.v1';
  function allFields(){ return [].slice.call(document.querySelectorAll('input,select')); }
  function keyOf(el, i, seen){
    var base;
    if(el.id) base = '#'+el.id;
    else if(el.name) base = '@'+el.name;
    else {
      /* 装备表/符石这类没有 id/name 的：用「所在行的部位 + data-a/data-t」做稳定键，
         不能用下标——切换门派时师门技能栏会重建，下标会整体错位 */
      var da = el.getAttribute('data-a') || el.getAttribute('data-t') || '';
      var row = el.closest ? el.closest('tr') : null;
      var part = (row && row.querySelector('th')) ? row.querySelector('th').textContent.trim() : '';
      base = '%' + part + '/' + da;
    }
    var n = seen[base] = (seen[base] || 0) + 1;
    return base + '|' + n;
  }
  function snap(){
    var seen={}, out=[];
    allFields().forEach(function(el,i){ out.push([keyOf(el,i,seen), el.value]); });
    return out;
  }
  function mapOf(){
    var seen={}, m={};
    allFields().forEach(function(el,i){ m[keyOf(el,i,seen)] = el; });
    return m;
  }
  function apply(list){
    if(!list || !list.length) return false;
    var saved={};
    list.forEach(function(p){ saved[p[0]] = p[1]; });
    /* 1) 先门派/等级：师门技能栏是按门派现生成的，必须先重建 */
    var mps=[].slice.call(document.querySelectorAll('select[name=menpai]'));
    var lvs=[].slice.call(document.querySelectorAll('input[name=jibie]'));
    mps.forEach(function(el,i){
      var v=saved['@menpai|'+(i+1)];
      if(v==null) return;
      el.value = v;                       /* 新格式：存的是门派名 */
      if(el.value !== v){
        /* 旧存档：值只有 ren/xian/mo，取该种族第一个门派（会丢具体门派，但至少能起来） */
        for(var j=0;j<el.options.length;j++){
          if(el.options[j].getAttribute('data-race')===v){ el.selectedIndex=j; break; }
        }
      }
    });
    lvs.forEach(function(el,i){ var v=saved['@jibie|'+(i+1)]; if(v!=null) el.value=v; });
    mps.forEach(function(el){ el.dispatchEvent(new Event('change',{bubbles:true})); });
    /* 2) 全量覆盖（此时技能栏已经是存档门派的） */
    var m=mapOf();
    Object.keys(saved).forEach(function(k){ if(m[k]) m[k].value=saved[k]; });
    /* 3) 五维走一遍 input，让加点/潜力按存档重算 */
    ['tizhi','moli','liliang','naili','minjie'].forEach(function(n){
      document.querySelectorAll('[name='+n+']').forEach(function(el){
        el.dispatchEvent(new Event('input',{bubbles:true}));
      });
    });
    if(typeof refreshAll==='function') refreshAll();
    return true;
  }
  function toast(t){
    var d=document.getElementById('mz-toast');
    if(!d){ d=document.createElement('div'); d.id='mz-toast'; document.body.appendChild(d); }
    d.textContent=t; d.className='show';
    clearTimeout(d._t); d._t=setTimeout(function(){ d.className=''; }, 1600);
  }
  var INIT=snap();               /* 刚打开时的默认值，给「清除」用 */
  window.addEventListener('message',function(e){
    var d=e.data||{};
    if(d.mz==='state' && apply(d.data)) toast('已载入上次保存的输入');
  });
  try{ parent.postMessage({mz:'get'},'*'); }catch(err){}
  document.getElementById('mz-save').onclick=function(){
    var o=snap();
    try{ parent.postMessage({mz:'save',data:o},'*'); }catch(err){}
    toast('已保存全部输入（'+o.length+' 项）');
  };
  document.getElementById('mz-clear').onclick=function(){
    try{ parent.postMessage({mz:'clear'},'*'); }catch(err){}
    /* 真·清空：数字框全部归 0，文本框清空，门派下拉保留（选不了空） */
    allFields().forEach(function(el){
      if(el.tagName === 'SELECT') return;
      if(el.readOnly) return;
      if(el.type === 'number') el.value = 0;
      else if(el.type === 'text' || !el.type) el.value = '';
    });
    /* 门派/等级变更后技能栏要重建，再重新清一遍新生成的输入 */
    document.querySelectorAll('select[name=menpai]').forEach(function(el){
      el.dispatchEvent(new Event('change',{bubbles:true}));
    });
    allFields().forEach(function(el){
      if(el.tagName === 'SELECT' || el.readOnly) return;
      if(el.type === 'number') el.value = 0;
      else if(el.type === 'text' || !el.type) el.value = '';
    });
    ['tizhi','moli','liliang','naili','minjie'].forEach(function(n){
      document.querySelectorAll('[name='+n+']').forEach(function(el){
        el.dispatchEvent(new Event('input',{bubbles:true}));
      });
    });
    if(typeof refreshAll==='function') refreshAll();
    toast('已清空所有输入');
  };
})();
</script></body></html>'''

# ===== 深色化（r59 拍板「都统一深色」，r62 从一次性脚本内置到这里）=====
# 上面 doc 里的颜色是照抄原站的浅色版；这里统一换成站点深色配色。
# 以前流程是「跑完 ui.py 再手工跑 darken_jiadian.ps1」，漏跑就会把 iframe 打回浅色，所以内置。
DARK = [
    ("background:linear-gradient(180deg,#5fb3c0,#3f96a6)", "background:linear-gradient(180deg,#2c3a68,#1c2a4d)"),
    ("background:#eef4f6", "background:#0e1424"),
    ("background:#f9fcfd", "background:#232b47"),
    ("background:#e8f4f6", "background:#232b47"),
    ("background:#fdf0ee", "background:#2c2030"),
    ("background:#f4fafb", "background:#1b2440"),
    ("background:#5fb3c0", "background:#e8c37a"),
    ("background:#fff", "background:#1b2440"),
    ("color:#1f3d4d", "color:#cdd6f4"),
    ("color:#3f96a6", "color:#8fa8ff"),
    ("color:#c0392b", "color:#ff8f8f"),
    ("color:#4a7a86", "color:#8b96b8"),
    ("color:#2c5a6c", "color:#e8c37a"),
    ("color:#4a6b7a", "color:#8b96b8"),
    ("color:#1a6b7c", "color:#e8c37a"),
    ("color:#5a7d8c", "color:#8b96b8"),
    ("color:#6b8b98", "color:#8b96b8"),
    ("color:#8aa3ae", "color:#8b96b8"),
    ("color:#7b96a3", "color:#8b96b8"),
    ("color:#c2d2d8", "color:#6f7ba3"),
    ("color:#9ab;", "color:#6f7ba3;"),
    ("color:#2f8f5b", "color:#66e4a5"),
    ("border:1px solid #cfe0e6", "border:1px solid #3d486e"),
    ("border:1px solid #dbe9ee", "border:1px solid #2b3456"),
    ("border-color:#9fd0d8", "border-color:#6f8ff5"),
    ("border-color:#3f96a6", "border-color:#6f8ff5"),
    ("border-color:#e6c3bd", "border-color:#6b3a3a"),
    ("border-top:1px dashed #e3eef1", "border-top:1px dashed #26304f"),
    ("border-bottom:1px dashed #eef4f6", "border-bottom:1px dashed #26304f"),
    ("border-bottom:1px solid #dbe9ee", "border-bottom:1px solid #2b3456"),
    ("border-bottom:1px solid #f0f6f8", "border-bottom:1px solid #26304f"),
    ("rgba(95,179,192,.15)", "rgba(232,195,122,.18)"),
    ("rgba(63,150,166,.25)", "rgba(232,195,122,.25)"),
]
for _a, _b in DARK:
    doc = doc.replace(_a, _b)
_light = [ln for ln in doc.split("\n") if any(k in ln for k in ("#eef4f6", "#f9fcfd", "background:#fff", "color:#1f3d4d"))]
if _light:
    raise SystemExit("深色化后仍有浅色残留 %d 行：%s" % (len(_light), _light[:2]))

b64 = base64.b64encode(doc.encode("utf-8")).decode()
p = BASE + r"\build\template2.html"
t = open(p, encoding="utf-8").read()
a = t.index('<section id="jiadian">')
b = t.index('</section>', a) + len('</section>')
sec = ('<section id="jiadian"><iframe src="data:text/html;base64,' + b64 +
       '" style="width:100%;height:2120px;border:0;display:block"></iframe></section>')
t = t[:a] + sec + t[b:]
open(p, "w", encoding="utf-8").write(t)
print("ok", len(doc))
