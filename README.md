# 小建哥的工具箱（梦幻西游）

自用的梦幻西游辅助工具箱：**一份 HTML 页面**，同时以两种形态提供 ——

| 形态 | 用途 | 数据 |
|---|---|---|
| **exe（单文件，WebView2）** | **实际使用**：记账、统计、挂机测算都在这里 | 存在 exe 自己的便携目录里，长期保留 |
| **html（单文件，浏览器直接打开）** | **开发预览 / 快速验证**：改功能先在这里跑 | 存在当前浏览器里，与 exe **不互通** |

> 两者数据不通是浏览器的同源策略决定的（exe 内是 `https://mztool.local`，本地 html 是 `file://`），
> 不是 bug。需要搬家时用页面里的「导出 / 导入 JSON」。

---

## 功能（11 个页签）

| 页签 | 做什么 |
|---|---|
| 库存管理 | 进货入库、盘点出库；总资产 = 现金 + 库存；带进货价走势 |
| 挂机体活 | ① 体活信息 → ② 炼药统计 → ③ 今日收支（按当天炼药 + 角色数×在线小时）→ ④ 收益明细（理论值）→ ⑤ 计算过程 |
| 智能答题 | 截图搜题：本地 OCR + 3,240 条题库 |
| 常用查询 | 11 张速查卡（经验/技能/修炼/帮派/红蓝秘制…）；「梦幻常识」合并为同页第二个选项卡；支持按使用频率排序 |
| 模拟加点 | 选门派、填属性，算气血/魔法/命中/伤害/防御/速度 |
| 刷子记账 | 摆摊物品价格、今日战绩、计时与每小时收益 |
| 宝石合成 | 宝石、星辉石、五色灵尘的合成消耗 |
| 跑商 / 倒卖 | 跑商路线与倒卖价差速查 |
| 收支记账 | 卖币 / 卖物品 / 充点卡；自动扣 5% 手续费；按月汇总 + 卖币单价走势 |
| 任务进度 | 任务板（进行中/待办/已解决）+ 历史进度 + 页面标注 + 一键生成给 agent 的 prompt |
| 关于 | 版本与数据说明 |

全局能力：顶部金价换算（藏宝阁单价 → 到手价）、浮窗计算器、**✏️ 页面标注**（点元素写备注，自动并入 prompt）、托盘最小化、定时关机。

---

## 快速开始

```bat
:: 1) 生成网页版
set MZ_OUT=shots\dist\梦幻西游实用工具箱-复刻版.html
python build\build.py

:: 2) 无头自检（不弹窗、不留进程）
python build\selfcheck.py

:: 3) 打包 exe（产物在 build\exe\out）
python build\make_exe.py

:: 4) 铺到桌面（会关掉正在运行的 exe）
python build\make_exe.py --publish
```

依赖：

- Windows + .NET Framework 4.x（自带 `csc.exe`，路径 `%WINDIR%\Microsoft.NET\Framework64\v4.0.30319\csc.exe`）
- WebView2 运行时；打包用的 SDK 放在 `build\exe\_sdk`（未入库，可用 nuget 重新取）
- Python 3（只用标准库）
- 可选：Node.js（`build\jscheck.py` 做内联脚本语法检查）

---

## 目录结构

```
build/
  template2.html        页面源码（模板，含 {{EXP}} / {{TASKS}} 等占位符）
  build.py              注入经验表、题库、任务数据 → 生成成品 html
  make_exe.py           csc 打包单文件 exe（--publish 铺到桌面，检测到同级 index.html 时拒绝覆盖）
  exe/MzToolbox.cs      exe 宿主：开窗、内存供给页面、托盘、定时关机、自检、任务板落盘
  exe/make_icon.py      生成 ico
  selfcheck.py          无人值守交互自检（http 服务 + 无头 Edge，点控件并断言，退出码 0/1）
  smoke_tabs.py         逐页签烟测（渲染 + JS 异常）
  shots_tabs.py         逐页签截图（含滚动、手机宽度）
  jscheck.py            抽出内联 <script> 交给 node --check
  edge_guard.py         无头 Edge 守卫（只清自己开的，支持 --check / --purge）
  edge_guard_selftest.py 守卫的 12 条反例（改守卫后必须跑）
  _eval.py              在页面里执行一段 JS 并打印结果（临时探针）
  test_exe.py           用 exe 内核跑自检（会开窗口，仅发布前用）
  prerender.py          预渲染：把首帧算好的 DOM 存成 index.html
  inline_jiadian.py     历史重构脚本：把模拟加点的 data: iframe 内联
  audit_*.py / verify_*.py / probe_*.py  历史一次性校验脚本（留档，不再使用）
```

---

## 数据存储

页面侧只有一层：`localStorage`，前缀 `mz3:`，**一域一键**，每次整域原子写。

```json
// mz3:ledger
{ "v": 3, "at": 1750000000000, "data": { "months": { "2026-11": [ ... ] } } }
```

- 域：`global / bodywork / inventory / ledger / alchemy / tasks / notes / usage / common / clock / shot / jzb / ui`
- API：`MZ3.read(d)` / `MZ3.write(d, obj)` / `MZ3.patch(d, fn)` / `MZ3.migrate()`
- 迁移：首次运行把旧键（`mz.sy.v1`、`mz.sy.inv.v1`、`mz.common.v1`、`mz.ps.v1`、`mz.shotRegions.v1`、`jzb.*`、`mz.lastTab`…）搬进新域，**旧键原样保留**，可回滚
- 记账与炼药按自然月分桶，只保留最近 24 个月（更早的压成月汇总）

exe 额外落盘（写在 exe 旁边，方便 agent / 人直接读）：

| 文件 | 谁写 | 说明 |
|---|---|---|
| `任务板.json` | 每次任务变更**自动**写（也可手点「保存到文件」） | `{tasks, seq, notes}`，可直接改完再「从文件导入」 |
| `收支记账.json` | 点「导出 JSON」 | 全量流水，可再导入合并（按 id 去重） |

---

## exe 宿主行为

- 页面从**内存**供给到 `https://mztool.local`（不往磁盘解 www），启动快、无残留
- 最小化 → 收进托盘并**释放 WebView2**（内存 430MB → ~44MB WS），恢复时重建（~0.9s）
- 第二个实例启动 → 给已运行窗口发 `WM_APP+1`，唤醒并前置
- 定时关机只走 `shutdown.exe -s -t N`（`-a` 取消），**不使用 ExitWindowsEx**；计时器在宿主里，托盘状态下照常触发
- 环境变量：`MZ_HOME`（数据目录）、`MZ_HTML`（外部页面）、`MZ_BROWSER_ARGS`（追加 WebView2 参数）、`MZ_STARTUP_LOG`（启动日志）
- 页面优先级：`MZ_HTML` > exe 同级 `index.html`（热更）> 内嵌资源

页面 ↔ 宿主消息（`chrome.webview.postMessage`，管道符分隔）：

页面 → 宿主：

```
TB|save|<json>                       手点「保存到文件」写任务板
TBA|save|<json>                      任务变更自动保存（安静，不回状态）
LG|save|<json>                       导出收支记账
SD|schedule|<action>|<force>|<ts>    定时关机 / 取消 / 查询剩余
```

宿主 → 页面（回执）：

```
TBOK|<msg>   TBERR|<msg>             任务板保存结果
LGOK|<msg>   LGERR|<msg>             记账导出结果
SDOK|  SDERR|<msg>  SDREMAIN|<ms>|<action>   关机调度回执
```

---

## 开发约定

1. **改动先落 HTML**，用无头自检确认；确认后再编译进 exe（exe 自检会弹窗，影响打游戏）。
2. **无头浏览器四条**：`--user-data-dir` 只放 `shots\` 下；收尾 `kill_tree` 杀整棵树；`--noerrdialogs --disable-crash-reporter --disable-breakpad`；跑完 `python build\edge_guard.py --check` 必须是 0。
3. **不删用户数据**：旧 `localStorage` 键保留，迁移只增不减。
4. **关机只走 `shutdown.exe`**。
5. 每次改完跑 `selfcheck.py` 并截图。

---

## 版本（近期）

| 版本 | 内容 |
|---|---|
| r93 | 存储层重写（`mz3` 分域 + 旧键迁移）；启动优化（首屏 2.29s → 0.34s） |
| r94 | 收支记账、炼药统计、任务板、常用查询/梦幻常识合并、按使用频率排序、浮窗计算器 |
| r95 | 体活页重排（② 可折叠、①②④ 左列、③ 今日收支上右栏） |
| r96 | 收支记账导出/导入；任务板从文件导入 |
| r97 | 页签记忆修复（新页签没进白名单，刷新会回落到常用查询） |
| r98 | 撤销「排序切回默认不刷新」的改动，恢复原行为 |
| r99 | 修「本月支出」数字撞全局 `.out` 样式被顶下去；笔数拆成 收/支 |
| r100 | 交互式标注阶段一（点元素加备注、编号气泡、任务板清单、并入 prompt） |
| r101 | 任务板变更自动写盘；历史进度视图；网页版定位说明 |

---

## 已知限制

- 网页版与 exe 数据不互通（见上），仅用于开发预览
- 常用查询卡片顺序不记忆，「按使用频率」只在本会话生效（切回默认会刷新）
- 页面标注依赖 CSS 选择器，页面结构大改后旧标注可能定位不到（列表里仍在，可手动删）
- 收支记账的走势图需要当月至少 2 笔卖币记录才绘制

---

## 仓库

私有仓库：<https://github.com/lijian1994/mhxytool>

入库：`build/` 下的源码与脚本、`README.md`、`AGENTS.md`、几份交接文档。
不入库：`shots/`（截图与临时舞台）、`build/exe/_sdk`（WebView2 SDK）、`build/exe/out`（产物）、`*.exe`、`任务板.json`、`收支记账.json`、游戏字符串 dump。
