import csv, json, re, io, os

BASE = r"F:\Documents\deepseek-harness\default-workspace"
DATA = os.path.join(BASE, "data")
OUT = os.environ.get("MZ_OUT") or r"F:\Desktop\梦幻西游工具\梦幻西游实用工具箱-复刻版.html"

def read_csv(name):
    with open(os.path.join(DATA, name), encoding="utf-8-sig") as f:
        return list(csv.reader(f))


# 经验表
exp = [0] * 176
for row in read_csv("exp_table.csv")[1:]:
    if len(row) >= 2 and row[0].strip().isdigit():
        lv = int(row[0]); v = row[1].strip().replace(",", "")
        exp[lv] = int(v) if v.isdigit() else 0

# 修炼累计经验 0..24
xiu = [0] * 25
for row in read_csv("xiulian.csv"):
    row = row[0].split("|")
    if len(row) >= 2 and row[0].isdigit():
        n = int(row[0])
        if 0 <= n <= 24:
            xiu[n] = int(row[1])

# 师门技能 0..160 [exp, money]
shi = [[0, 0] for _ in range(161)]
for row in read_csv("shimen.csv"):
    row = row[0].split("|")
    if len(row) >= 3 and row[0].isdigit():
        n = int(row[0])
        if 1 <= n <= 160:
            shi[n] = [int(row[1] or 0), int(row[2] or 0)]

# 官方接口数据（优先）
off = json.load(open(os.path.join(DATA, "official.json"), encoding="utf-8-sig"))
exp = off["exp"]
shi = off["shimen"]
LIFE = off["life"]
# 师门转为累计值，便于区间相减
_cum = 0
for i in range(len(shi)):
    _cum += shi[i][0] or 0
    shi[i][0] = _cum
_cum2 = 0
for i in range(len(shi)):
    _cum2 += shi[i][1] or 0
    shi[i][1] = _cum2
for k in LIFE:
    LIFE[k]["exp"] = [0 if v is None else v for v in LIFE[k]["exp"]]
    LIFE[k]["cash"] = [0 if v is None else v for v in LIFE[k]["cash"]]
    LIFE[k]["bg"] = [0 if v is None else v for v in LIFE[k]["bg"]]
    # 注意：bg 是「累计消耗的帮贡」，页面直接用：需要帮贡 = bg[到]-bg[从]，学习需求帮贡（总）= bg[到]。
    # official.json 里的 req 是接口的 req_bg（每级 5×等级，单级门槛），跟「总帮贡」不是一回事，别拿来当总需求。

tpl = open(os.path.join(BASE, "build", "template2.html"), encoding="utf-8").read()
tpl = tpl.replace("{{EXP}}", json.dumps(exp, separators=(",", ":")))
tpl = tpl.replace("{{XIULIAN}}", json.dumps(xiu, separators=(",", ":")))
tpl = tpl.replace("{{SHIMEN}}", json.dumps(shi, separators=(",", ":")))

# 任务数据
task_rows = read_csv("task_all.csv")[1:]
TASK = {"sm": [[None, None] for _ in range(176)], "ql": [[] for _ in range(176)], "xw": [[] for _ in range(176)],
        "kjxs": [None]*176, "kjhs": [None]*176, "df": [None]*176, "jre": [None]*176, "jrm": [None]*176, "rwl": [None]*176}
for r in task_rows:
    if len(r) < 4: continue
    kind, lv, rnd, val = r[0], int(r[1]), int(r[2]), r[3].strip()
    if not val: continue
    v = int(val)
    if kind == "smexp":
        if TASK["sm"][lv][0] is None: TASK["sm"][lv][0] = v
    elif kind == "smmoney":
        TASK["sm"][lv][1] = v
    elif kind == "qlrw":
        while len(TASK["ql"][lv]) < rnd: TASK["ql"][lv].append(None)
        TASK["ql"][lv][rnd-1] = v
    elif kind == "xwrw":
        while len(TASK["xw"][lv]) < rnd: TASK["xw"][lv].append(None)
        TASK["xw"][lv][rnd-1] = v
    else:
        key = {"kjxs":"kjxs","kjhs":"kjhs","dfrw":"df","jrexp":"jre","jrmoney":"jrm","rwl":"rwl"}.get(kind)
        if key: TASK[key][lv] = v

tpl = tpl.replace("{{TASK}}", json.dumps(TASK, ensure_ascii=False, separators=(",", ":")))
tpl = tpl.replace("{{LIFE}}", json.dumps(LIFE, ensure_ascii=False, separators=(",", ":")))
MP = json.load(open(os.path.join(DATA, "menpai.json"), encoding="utf-8-sig"))
FURN = json.load(open(os.path.join(DATA, "furniture.json"), encoding="utf-8-sig"))
NPCD = json.load(open(os.path.join(DATA, "npc_level.json"), encoding="utf-8-sig"))
KEJU = json.load(open(os.path.join(DATA, "keju.json"), encoding="utf-8-sig"))
tpl = tpl.replace("{{KEJU}}", json.dumps(KEJU, ensure_ascii=False, separators=(",", ":")))
tpl = tpl.replace("{{NPC}}", json.dumps(NPCD, separators=(",", ":")))
tpl = tpl.replace("{{FURN}}", json.dumps(FURN, ensure_ascii=False, separators=(",", ":")))
tpl = tpl.replace("{{MENPAI}}", json.dumps(MP, separators=(",", ":")))

os.makedirs(os.path.dirname(OUT), exist_ok=True)
open(OUT, "w", encoding="utf-8").write(tpl)
print("written", OUT, len(tpl), "bytes")
print("exp[0..4]", exp[:5], "exp[175]", exp[175])
print("xiu[24]", xiu[24], "shi[160]", shi[160])
