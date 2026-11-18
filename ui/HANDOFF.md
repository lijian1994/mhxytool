# 交接：mzui —— 通用 UI 框架（新项目）

> 这份文档是给**新会话**看的，目标是让你在不了解上下文的情况下直接开工。
> 写于 2026-11-18，来源项目：「小建哥的工具箱」（`F:\Documents\deepseek-harness\default-workspace`）。

---

## 1. 为什么要做这个项目

工具箱里现在堆了一堆**通用的 UI 能力**（深色主题变量、页签切换与记忆、浮窗、标注、现在还要加拖拽排序和元素级 DIY）。
这些能力跟"梦幻西游"没有任何关系，每次新工具都要重写一遍。

**目标**：抽出一个**只做 UI 布局框架 + 交互原语**的基础项目，以后做任何小工具（网页或 exe）都基于它，
只写业务页面，不再重复造轮子。

**边界（很重要）**

| 负责 | 不负责 |
|---|---|
| 布局骨架（顶栏/侧栏/内容区/卡片栅格） | 任何具体业务逻辑（体活、记账、跑商…） |
| 主题变量与控件样式（深色为主，预留浅色） | 图表组件（以后真需要再加） |
| 交互原语：页签+记忆、拖拽排序、元素级 DIY、标注、浮窗、toast/弹窗/抽屉 | 表单校验、表格这类偏业务的组件 |
| 存储适配层（localStorage / 宿主 postMessage 可切换） | 后端、网络请求 |

---

## 2. 硬约束（不要破坏）

1. **零依赖**：纯原生 JS + CSS，**不引任何框架或库**（不引 React/Vue/SortableJS/lit）。原因是最终产物要能塞进一个单文件 html。
2. **可内联**：产出两个文件 `mzui.css` + `mzui.js`，能被构建脚本直接内联进 html（工具箱现在是 98 万字符的单文件）。
3. **体积预算**：`mzui.js` + `mzui.css` 合计 **≤ 80 KB**（未压缩）。
4. **不联网**：运行时不发任何请求，不加载 CDN 字体/图标。图标用内联 SVG 或 emoji。
5. **Windows 优先**：目标环境是 Windows 10/11 + Edge/WebView2（Chromium 110+）。不追求旧浏览器。
6. **不改宿主**：框架不能假设自己跑在浏览器里 —— 它要能在 WebView2 里工作（`window.chrome.webview` 可能存在），有宿主时存储/导出走宿主，没有就退回 localStorage。

---

## 3. 现有可复用资产（直接抄，不要重新发明）

来源项目路径：`F:\Documents\deepseek-harness\default-workspace`

| 资产 | 位置 | 说明 |
|---|---|---|
| 主题变量 | `build/template2.html` 搜 `:root{` | 已有 13 个变量：`--bg --win --win2 --grp --line --text --dim --gold --accent --green --ok --warn` |
| 存储层 | 同文件搜 `window.MZ3` | 分域存 `localStorage`，信封 `{v, at, data}`，带 `read/write/patch/migrate` 与旧键迁移 |
| 页签切换 + 记忆 | 搜 `function showTab(t)`、`boot-tab`、`mz.lastTab` | 首帧用 `<style id="boot-tab">` 抢先显示，避免闪一下再跳；页签白名单在启动脚本里 |
| 浮窗计算器 | 搜 `id="mzCalc"` | 拖动、键盘输入、位置记忆的现成实现 |
| 页面标注（阶段一） | 搜 `id="annoPanel"` / `annBtn` | 高亮框 + 编号气泡 + 面板 + 存 `{page, sel, text, note, ts}`；**高亮用浮层不改原元素样式** |
| 任务板 / 历史视图 | 搜 `<section id="task">` | 分组列表 + 按日期归档的写法 |
| 无头交互自检 | `build/selfcheck.py` | 起本地 http 服务 + CDP 驱动 Edge，点真实控件并断言，退出码 0/1 —— **直接改成 mzui 的回归测试** |
| 逐页截图 | `build/shots_tabs.py` | 改动后视觉对比用（注意：`captureBeyondViewport` 在 headless=new 下会渲染错乱，现文件里已改成"调视口高度再截"） |
| 内联脚本语法检查 | `build/jscheck.py` | 把页面里的 `<script>` 抽出来交给 `node --check` |
| 无头浏览器守卫 | `build/edge_guard.py` | 只清理 `--user-data-dir` 落在本工作区 `shots\` 下的进程；改它必须跑 `edge_guard_selftest.py`（12 条反例） |
| 构建占位替换 | `build/build.py` | `{{XXX}}` 占位符注入的模式，适合把 `mzui.js/css` 内联进去 |

---

## 4. 目录规划（建议）

先在工作区内做，稳定后再拆成独立仓库。

```
ui/
  HANDOFF.md            本文档
  mzui.css              主题变量 + 布局 + 控件样式
  mzui.js               交互原语（IIFE，挂 window.MZUI）
  demo.html             演示页：把每个原语都放一遍，作为回归入口
  build_bundle.py       把 css/js 合成单文件 demo（可选）
  selfcheck.py          无头交互自检（从工具箱那份改）
  README.md             用法（新会话做完首版再写）
```

之后拆仓库：`mzui`（私有即可），工具箱按版本号内联。

---

## 5. MVP 清单（按顺序做，每项都要能演示 + 自检）

| # | 能力 | 验收标准 |
|---|---|---|
| 1 | **布局骨架** | 顶栏 / 侧栏 / 内容区 / 卡片栅格；窄屏（≤760px）自动变上下布局；视觉与工具箱现状一致 |
| 2 | **主题** | 全部颜色走 CSS 变量；提供 `[data-theme="light"]` 一套浅色（可先粗做）；切换即时生效并记忆 |
| 3 | **页签 + 记忆** | 点页签切内容区、选中态、URL hash `#tab=x`、刷新后回到上次页签；白名单外的名字不允许 |
| 4 | **拖拽排序** | Pointer Events 自实现（不引库）：卡片/列表项可拖，拖拽时占位、放下落位、顺序写存储、下次打开保持；键盘也能调（Alt+↑/↓） |
| 5 | **元素级 DIY** | 每个可 DIY 元素有 `data-ui-id`；支持 隐藏 / 改文案 / 改颜色；按 id 存；**id 找不到时进"待重绑"列表，不静默失效**；提供一键还原 |
| 6 | **浮窗** | 可拖、可缩放、记住位置；多个浮窗 z-index 递进；点外部不关闭（除非配置） |
| 7 | **toast / 确认框 / 抽屉** | `UI.toast(msg, type)`、`UI.confirm({title, text}) => Promise<boolean>`、抽屉从右侧滑出 |
| 8 | **存储适配层** | `UI.store` 接口：`read/write/patch`；后端可切 `localStorage` 或 `host`（`chrome.webview.postMessage('UI|save|')`）；没宿主自动退化 |

**每项都要在 `demo.html` 里有可点的演示，并在 `selfcheck.py` 里有一条断言。**

---

## 6. 数据模型（建议）

命名空间 `mzui:`，一域一键，信封沿用工具箱的做法（便于以后互相迁移）：

```json
{ "v": 1, "at": 1750000000000, "data": { ... } }
```

| 域 | 内容 |
|---|---|
| `mzui:ui` | `{ tab, theme, win: {x,y,w,h} }` 界面状态 |
| `mzui:order` | `{ "<容器id>": ["ui-id1","ui-id2", ...] }` 拖拽顺序 |
| `mzui:overrides` | `{ "<ui-id>": { hidden?: true, text?: "...", color?: "#fff" } }` DIY 覆盖 |
| `mzui:notes` | `{ items: [{ id, page, uiId, sel, text, note, ts }] }` 标注（沿用工具箱格式，便于直接复用） |

**关键设计**：DIY 和标注都优先生成并引用 `data-ui-id`（稳定），`sel`（CSS 路径）只作为兜底与展示；两者都找不到时进"待重绑"。

---

## 7. 与工具箱的集成方式

1. 工具箱 `build/template2.html` 里加占位：`/* {{MZUI_CSS}} */` 与 `/* {{MZUI_JS}} */`；
2. `build/build.py` 读 `ui/mzui.css|js` 替换进去，并在页面里写死版本号 `<meta name="mzui-version" content="0.1.0">`；
3. 工具箱启动时校验版本，不一致就在控制台报错（避免"改了框架没内联"）；
4. **试点只接一个原语**：拖拽排序（用在「常用查询」的卡片上），跑通再谈全面迁移。

---

## 8. 开发流程（跟工具箱保持一致）

```bat
:: 环境
set PY=E:\DeepSeek Harness\resources\runtime\primary-runtime\dependencies\python\python.exe
:: Edge
C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe

:: 演示页（本地起服务，localStorage 才会落盘）
%PY% -m http.server 8799 --bind 127.0.0.1 --directory ui

:: 无头自检
%PY% ui\selfcheck.py

:: 截图
%PY% ..\build\shots_tabs.py http://127.0.0.1:8799/demo.html 9310 demo

:: 收尾必须干净
%PY% build\edge_guard.py --check
```

**无头浏览器四条铁律（必须遵守）**

1. `--user-data-dir` 只能指向工作区 `shots\` 下的临时目录，绝不用默认配置；
2. 收尾用 `kill_tree`（`taskkill /T /F`），禁止只 `p.kill()`；
3. 启动加 `--noerrdialogs --disable-crash-reporter --disable-breakpad`，父进程设 `SetErrorMode(0x0003)`；
4. 跑完 `edge_guard.py --check` 必须是 0。

---

## 9. 风险与对策

| 风险 | 对策 |
|---|---|
| DIY 的选择器随 DOM 变化失效 | 强制 `data-ui-id`；失效进"待重绑"；DIY 只允许白名单属性（显隐/文案/颜色），不允许改结构 |
| 拖拽与点击冲突（点一下被当成拖） | 移动阈值 4px 以上才算拖；拖拽中 `pointer-events` 与 `preventDefault` 要精确处理 |
| 抽样式把工具箱视觉搞乱 | 视觉必须逐页截图对比；一次只迁一类样式 |
| 体积膨胀 | 每次提交记录 `mzui.js/css` 字节数，超预算就说明设计有问题 |
| 双仓库同步 | 页面里写死版本号 + 启动校验；工具箱只在发布时同步一次 |
| 在 WebView2 里跑不动（CSP/内联脚本） | 工具箱就是内联脚本模式，保持同一种写法；不要用 `eval`/`new Function`（WebView2 默认禁止） |

---

## 10. 开工建议（第一批提交）

1. `chore: 建 ui/ 目录 + demo.html 骨架 + selfcheck.py 空壳`
2. `feat: 主题变量与布局骨架（顶栏/侧栏/内容区/卡片）`
3. `feat: 页签 + 记忆（含 hash 与白名单）`
4. `feat: 拖拽排序（Pointer Events，顺序持久化）`
5. `feat: 元素级 DIY（data-ui-id + 覆盖层 + 待重绑）`
6. `feat: 浮窗 / toast / confirm / 抽屉`
7. `feat: 存储适配层（localStorage + host）`

每提交都要：`selfcheck.py` 全过 + 截图 + 更新 `ui/README.md` 的用法。

---

## 11. 环境备忘

- Python：`E:\DeepSeek Harness\resources\runtime\primary-runtime\dependencies\python\python.exe`
- Node（可选，语法检查用）：`E:\DeepSeek Harness\resources\runtime\primary-runtime\dependencies\node\bin\node.exe`
- git 已装（2.54），**GitHub 凭据已缓存**（GCM，用户已登录），可直接 `git push`
- 本机走代理 `http://127.0.0.1:7897`（git 全局配了 http/https proxy）
- 工具箱仓库：<https://github.com/lijian1994/mhxytool>（私有，最近提交 `fe4d849`）
- 工具箱当前版本：**r101**，exe `5.3.101.0`

---

## 12. 新会话开场建议

1. 读这份文档 + 工具箱的 `README.md`（了解现有做法）；
2. `git status` 确认工作区干净；
3. 建 `ui/` 骨架，先做第 1–3 项（布局/主题/页签），跑通 `selfcheck.py` 再往下；
4. **每一步都先出计划、说风险，等确认再动手**（用户明确要求这个流程）。
