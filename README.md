# 梦幻西游实用工具箱

## 1. 定位

**梦幻西游的本地计算器 + 工具集，单文件 HTML，可打包成 exe。**

解决的是：游戏里那些算起来烦的东西（练级经验、修炼消耗、师门技能花费、炼药收益、宝石合成、押镖时间、体活恢复），以及查资料、答题、记账、记任务。

给谁用：玩梦幻、想在本地随时算一算、不想开网页也不想要账号的人。

- 11 个标签页，全部离线可用
- 一份 HTML（约 850 KB），双击即开
- 一个 exe（约 2.2 MB），用 WebView2 承载，可放任务栏
- 数据存本机 localStorage，不上传

当前版本 **V5.3 · r128**。

---

## 2. 快速开始

### 用现成的 exe

双击 `梦幻西游实用工具箱.exe`。首次打开会创建 `任务板.json` 在同目录，任务数据存在这里。

### 用 HTML

双击 `梦幻西游实用工具箱-复刻版.html`。不需要服务、不需要联网。

### 自己构建

```bat
python build\build.py
```

产物默认写到 `F:\Desktop\梦幻西游工具\梦幻西游实用工具箱-复刻版.html`，可用环境变量 `MZ_OUT` 改：

```bat
set MZ_OUT=shots\dist\梦幻西游实用工具箱-复刻版.html
python build\build.py
```

打包 exe：

```bat
python build\make_exe.py            # 只编译，产物在 build\exe\out\
python build\make_exe.py --publish  # 编译并复制到桌面
```

依赖：Python 3（只用标准库）、.NET Framework 4.x 自带的 `csc.exe`、`build\exe\_sdk` 里的 WebView2 SDK。不需要装 node、npm、构建工具链。

---

## 3. 引入方式

这个项目不是给别人引用的库，是本地应用。三种使用形态：

| 形态 | 文件 | 适合 |
|---|---|---|
| exe | `梦幻西游实用工具箱.exe` | 日常用，双击即开，能固定到任务栏 |
| 单文件 HTML | `梦幻西游实用工具箱-复刻版.html` | 想拷走、想改、不想装东西 |
| 源码 | `build\template2.html` | 二次开发 |

**环境要求**：

- exe：Windows 10/11，需要 WebView2 运行时（Win10/11 一般自带，没有会提示安装）
- HTML：任意现代浏览器
- 构建：Python 3.8+，Windows（`make_exe.py` 用 `csc.exe`，是 Windows 专有）

---

## 4. 核心概念

### 标签页（Tab）

整个应用按功能分 11 个页签，切换用顶部的按钮，也支持 URL hash 直达（`#quiz`、`#task` 等）。

| `data-t` | 图标 | 名称 | 干什么 |
|---|---|---|---|
| `daomai` | 🏪 | 库存管理 | 环装/三药/金创等库存与炼药统计 |
| `shouyi` | 💰 | 挂机体活 | 体力活力的恢复与消耗计算 |
| `quiz` | 🎯 | 智能答题 | 截图框选 → OCR 识别 → 匹配答案 |
| `renwu` | 🔎 | 常用查询 | 人物、NPC、门派、任务资料 |
| `jiadian` | 🎮 | 模拟加点 | 属性点分配到具体数值 |
| `jzb` | 📒 | 刷子记账 | 打金流水记录与统计 |
| `baoshi` | 💎 | 宝石合成 | 宝石等级、花费、成功率 |
| `paoshang` | ⏱ | 梦幻时钟 | 押镖、双倍、活动时间轴 |
| `ledger` | 💰 | 收支记账 | 日常收支流水 |
| `task` | 📋 | 任务进度 | 三态任务板 + 完成记录 + 生成 prompt |
| `about` | ℹ️ | 关于 | 版本、说明 |

### 数据存储

所有数据在本机 localStorage，键以 `mz3:` 开头，统一信封格式：

```js
{ v: 1, at: 1700000000000, data: { ... } }
```

| 键 | 内容 |
|---|---|
| `mz3:tasks` | 任务板（任务数组 + seq + prompt 模板） |
| `mz3:alchemy` | 炼药记录（按天、按方式统计） |
| `mz3:bodywork` | 挂机体活记录 |
| `mz3:ui` | 界面状态（上次停在哪个页签、折叠状态等） |
| `mz3:notes` | 页面标注 |
| `mz3:usage` | 功能使用频次（用于排序） |

**升级不清数据**：新版本只加键、不删旧键，旧数据会自动兼容读取。

### exe 宿主

exe 是一个 C# WebView2 外壳（`build\exe\MzToolbox.cs`），负责：

1. 启动时把 `任务板.json` 通过 `/board.json` 交给页面
2. 接收页面发来的 `TBA|save|<json>` 消息，写回 `任务板.json`
3. 最小化到托盘（不销毁 WebView，所以切回来是瞬间的）

### 构建管线

```
shots\*.csv（数据源）
      ↓  build\build.py 读表、算表、填模板
build\template2.html（模板，含 {{EXP}} 等占位符）
      ↓  替换占位符
shots\dist\...html（HTML 产物）
      ↓  build\make_exe.py 内嵌进 C# 源码、csc 编译
build\exe\out\...exe（exe 产物）
      ↓  --publish
F:\Desktop\梦幻西游工具\...exe
```

---

## 5. 配置参数

### 环境变量

| 变量 | 默认 | 说明 |
|---|---|---|
| `MZ_OUT` | 桌面路径 | `build.py` 的输出文件 |
| `MZ_KEEP_PROFILE` | 空 | 自检脚本设为 `1` 时保留浏览器 profile（调试用） |

### 构建命令参数

| 命令 | 参数 | 说明 |
|---|---|---|
| `build.py` | 无 | 生成 HTML |
| `make_exe.py` | 无 | 编译 exe 到 `build\exe\out\` |
| `make_exe.py` | `--publish` | 编译并复制到桌面 |
| `make_exe.py` | `--force` | 同目录有 `index.html` 时强制覆盖 |
| `smoke_tabs.py` | `<url> [port]` | 逐页签冒烟，默认端口 9240 |
| `shots_tabs.py` | `<url> [port]` | 逐页签截图，默认端口 9250 |

### 模板占位符

`template2.html` 里的占位符，构建时被替换成生成的数据：

| 占位符 | 内容 |
|---|---|
| `{{EXP}}` | 0–175 级经验表 |
| `{{XIULIAN}}` | 0–24 修炼累计经验 |
| `{{SHIMEN}}` | 0–160 师门技能花费 |
| `{{TASK}}` | 任务板初始数据 |
| `{{LIFE}}` | 生活技能数据 |
| `{{KEJU}}` | 科举题目 |
| `{{NPC}}` | NPC 数据 |
| `{{FURN}}` | 家具数据 |
| `{{MENPAI}}` | 门派数据 |

---

## 6. 数据与接口契约

### 6.1 localStorage 信封

```js
{
  v: 1,                      // 版本号
  at: 1700000000000,         // 写入时间（毫秒）
  data: { ... }              // 各键自己的结构
}
```

读写通过页面内的 `MZ3.read(key)` / `MZ3.write(key, data)` / `MZ3.patch(key, fn)`，不要直接 `JSON.parse(localStorage.getItem(...))`。

### 6.2 任务结构

```js
{
  id: 't1',                  // t + 序号
  title: '换题卡死',
  detail: '细节（可空）',
  kind: '需求' | '问题',
  status: 'todo' | 'doing' | 'done',
  created: 1700000000000,
  updated: 1700000000000,
  cause: '问题原因',          // 完成时填
  fix: '解决方案',            // 完成时填
  source: 'div#quiz'         // 标注来的才有
}
```

### 6.3 任务板存储对象

```js
{
  tasks: Task[],
  seq: number,               // 下一个可用序号
  promptTpl?: string         // 用户改过的 prompt 模板
}
```

### 6.4 exe 通信协议

| 方向 | 内容 | 说明 |
|---|---|---|
| exe → 页面 | `GET /board.json` | 启动时读取任务板数据 |
| 页面 → exe | `TBA\|save\|{"tasks":[...],"seq":2}` | 保存任务板 |
| 页面 → exe | `TB\|save\|{"tasks":[...],"seq":2}` | 整板 JSON 保存 |
| exe → 页面 | `TBOK\|` / `TBERR\|<原因>` | 保存结果回执 |

消息通过 `window.chrome.webview.postMessage()` 发送。页面监听 `chrome.webview.addEventListener('message', ...)` 收结果。

### 6.5 炼药统计结构

```js
{
  days: {
    '2026-11-21': {
      n: 12,                          // 当天总次数
      n3: 27,                         // 当天总三药数
      byMethod: {                     // 按方式拆
        '2+2': { n: 6, n3: 12 },
        '3+1': { n: 6, n3: 15 }
      }
    }
  }
}
```

`byMethod` 缺失时（老数据），渲染为一行 `混合`，不做除法换算，避免出现小数。

---

## 7. 脚本参考

全部在 `build\` 下，用 Python 直接跑。

### 构建

| 脚本 | 作用 |
|---|---|
| `build.py` | 模板 + 数据 → 单文件 HTML |
| `make_exe.py` | HTML → exe（内嵌 + csc 编译） |
| `prerender.py` | 预渲染静态快照（调试用） |

### 自检

| 脚本 | 作用 | 通过标准 |
|---|---|---|
| `smoke_tabs.py <url>` | 逐页签点击，检查渲染和 JS 异常 | 11 个页签全部有内容、0 异常 |
| `shots_tabs.py <url>` | 逐页签截图 | 截图落在 `shots\` |
| `selfcheck.py` | 内置自检项 | 退出码 0 |
| `audit_tabs.py` | 页签体检 | 退出码 0 |
| `verify_quiz_live.py` | 答题器真实 5 连测 | 退出码 0 |

### 无头浏览器守卫（必须用）

| 脚本 | 作用 |
|---|---|
| `edge_guard.py --check` | 检查本工作区有没有遗留无头 Edge |
| `edge_guard.py --purge` | 清掉长期不用的临时 profile |
| `edge_guard_selftest.py` | 守卫自身的 12 条反例，退出码 0 才算过 |

**规则**：任何无头浏览器都必须带 `--user-data-dir` 指向 `shots\` 下的临时目录，收尾用 `kill_tree()` 杀整棵树，不许只 `p.kill()`。

---

## 8. 行为与边界

| 场景 | 行为 |
|---|---|
| 数据存哪 | 本机 localStorage，键 `mz3:*`，不上传 |
| 换浏览器 / 换电脑 | 数据不跟走，需要手动迁移 `任务板.json` |
| 清浏览器数据 | localStorage 全丢；exe 的 `任务板.json` 还在 |
| 版本升级 | 只加键不删旧键，旧数据兼容读取 |
| exe 最小化 | 只 `Hide()`，不销毁 WebView，恢复是瞬间的 |
| exe 关掉 | `任务板.json` 留在 exe 同目录 |
| 答题器 | 需要手动框选一次答案区域并校准基色，之后自动识别 |
| OCR | 识别超时 25 秒，超时走低置信度兜底 |
| 离线 | 除答题器 OCR 外全部离线；答题器也只在本机处理截图 |
| 发版 | `make_exe.py --publish` 会覆盖桌面 exe；exe 正在运行时先改名再复制 |

**已知边界**：

- exe 用 `csc.exe`（.NET Framework 4.x），所以只能 Windows
- 答题器依赖屏幕截图，需要窗口可见
- 炼药数据老记录只有总次数、没有分方式，这类历史日只能显示「混合」

---

## 9. 常见问题

**Q：双击 exe 提示缺 WebView2？**
装一下 [WebView2 Runtime](https://developer.microsoft.com/microsoft-edge/webview2/)（Win10/11 通常自带）。或者改用 HTML 版。

**Q：改了 `template2.html` 怎么生效？**
要重新跑 `build.py` 生成 HTML，再 `make_exe.py` 打包。直接改 `shots\dist` 里的产物会被下次构建覆盖。

**Q：数据会丢吗？**
localStorage 清缓存就丢。重要数据用任务板的「导出」存一份，或者用 exe（`任务板.json` 在磁盘上）。

**Q：能同时开 exe 和 HTML 吗？**
能，但两者数据不互通（一个在 localStorage，一个在 `任务板.json`）。

**Q：为什么不用打包工具（pyinstaller 之类）？**
exe 是个 C# WebView2 外壳，页面全内嵌，产物只有 2 MB 左右，启动快。用打包工具反而更大更慢。

**Q：想加一个页签怎么做？**
1. 在 `template2.html` 的 `#tabs` 里加 `<button data-t="xxx">`
2. 加 `<section id="xxx">` 内容
3. 在 `showTab()` 的分支里接上
4. 跑 `smoke_tabs.py` 确认不报错
