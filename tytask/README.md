# mztask

## 1. 定位

**一个自带界面和持久化的任务板组件，给任何网页项目用。**

解决三件事：不用自己画任务列表的 UI、不用自己写增删改和完成记录、不用自己接存储（浏览器、文件、后端都行）。引入一个 js 文件，放一个空 div，就有一块能用的任务板。

给谁用：想在自己项目里加「待办 / 进行中 / 已解决」三态任务列表，并且希望任务数据能存在本地或文件里的人。

版本 1.2.0，零依赖，63 KB。

---

## 2. 快速开始

```html
<div id="tasks"></div>
<script src="mztask.js"></script>
<script>MZTask.mount('#tasks');</script>
```

打开后你会得到：

- 一条输入框 + 「需求/问题」分类 + 添加按钮
- 三栏列表：进行中、待办、已解决
- 点「完成」时弹框填「问题原因」和「解决方案」
- 历史进度（按天统计）
- 「给 agent 的 prompt」生成区

数据自动存在 localStorage，刷新、关掉重开都还在。

---

## 3. 引入方式

```html
<script src="mztask.js"></script>
<!-- 或者 CommonJS -->
<script>const MZTask = require('./mztask.js');</script>
```

| 项 | 说明 |
|---|---|
| 文件 | 只需要 `mztask.js` 一个 |
| 依赖 | 无 |
| 样式 | 库自己注入，不污染你的 CSS（全部 `.mzt-*` 前缀） |
| 全局名 | `MZTask` |
| 环境 | 现代浏览器（Chrome/Edge/Firefox/Safari 都行） |

**特殊环境要求**：用到文件类持久化（`jsfile` / `file` / `dir`）时，页面必须跑在 `http://localhost` 或 https 下，双击 `file://` 打开会拿不到 File System Access API。其余 6 种方式 `file://` 也能用。

浏览器支持：

| 能力 | Chrome/Edge | Firefox | Safari |
|---|---|---|---|
| 基础界面、`local`、`idb` | ✅ | ✅ | ✅ |
| `opfs` | ✅ | 111+ | 15.2+ |
| `jsfile` / `file` / `dir` | ✅ | ❌ | ❌ |
| `host`（WebView2） | ✅ | ❌ | ❌ |

---

## 4. 核心概念

### 任务（Task）
最小单位，有一条标题、一个状态、可选的细节和完成记录。结构见第 6 章。

### 状态（State）
整块板的数据就是 `{ tasks, seq, promptTpl? }`。`seq` 是下一个可用的任务序号，用来生成 `t1`、`t2` 这样的 id。

### 适配器（Adapter）
**持久化的实现**。一个适配器就是一个对象，负责把 State 读出来、写回去。库不自带"存储"，只调用适配器。

内置 9 种：

| 方式 | 纯前端离线 | 要宿主/服务端 | 要用户选文件 | 跨设备 | 浏览器 |
|---|---|---|---|---|---|
| `local`（默认） | ✅ | ❌ | ❌ | ❌ | 所有 |
| `idb` | ✅ | ❌ | ❌ | ❌ | 所有 |
| `opfs` | ✅ | ❌ | ❌ | ❌ | Chromium / Safari 15.2+ / FF 111+ |
| `jsfile` | ✅（本机文件） | ❌ | ✅ 选一次 | ✅ 可拷 | 仅 Chromium，需 localhost/https |
| `file` | ✅（本机文件） | ❌ | ✅ 选一次 | ✅ 可拷 | 仅 Chromium，需 localhost/https |
| `dir` | ✅（本机目录） | ❌ | ✅ 选一次 | ✅ 可拷 | 仅 Chromium，需 localhost/https |
| `http` | ❌ 要联网 | ✅ **要自己写后端** | ❌ | ✅ | 所有 |
| `host` | ❌ 要有 exe | ✅ **要 exe 宿主配合** | ❌ | ✅ | WebView2 |
| `memory` | ✅ | ❌ | ❌ | ❌ | 所有 |

「离线」= 不需要网络、不需要服务端、不需要宿主。**7 种纯前端可用，2 种必须有人配合。**

**怎么选**：

- 开箱即用、什么都不配 → `local`
- 要单条改、数据量大 → `idb`
- 要能被别的程序读、能拷走 → `jsfile` / `file` / `dir`
- 多设备同步 → `http` 或 `host`，都要自己搭

**默认规则**：检测到 `window.chrome.webview` 用 `host`，否则用 `local`。

### 板子（board）
`MZTask.mount()` 的返回值，代表一块任务板。所有增删改查都通过它。

---

## 5. 配置参数

### `MZTask.mount(target, opts)`

| 参数 | 类型 | 必填 | 默认 | 说明 |
|---|---|---|---|---|
| `target` | string \| Element | ✅ | — | CSS 选择器或容器元素 |
| `title` | string | | `'任务'` | 标题，纯文本 |
| `adapter` | string \| object | | 自动 | 持久化方式，见第 4 章 |
| `storageKey` | string | | `'mztask.v1'` | localStorage 的 key |
| `dbName` | string | | `mztask_<storageKey 转义>` | IndexedDB 库名 |
| `baseUrl` | string | | `'/api/tasks'` | http 适配器地址 |
| `loadUrl` | string | | `'/board.json'` | host 适配器读地址 |
| `saveTag` | string | | `'TBA\|save\|'` | host 适配器写入前缀 |
| `dirName` | string | | `'mztask'` | opfs 目录名 |
| `enablePrompt` | boolean | | `true` | 是否显示 prompt 区 |
| `promptTpl` | string | | 内置 | prompt 模板，占位符 `{count}` `{tasks}` `{rules}` |
| `promptRule` | string | | 内置 | 模板里的规则段 |
| `onChange` | `(tasks) => void` | | — | 每次改动回调 |

返回 board 实例。

### `MZTask.config(opts)`

参数同 `mount`（除 `target`）。设置后，所有 `mount` 没显式传的项都用它。返回当前全局配置副本。

```js
MZTask.config({ adapter: 'idb', storageKey: 'myapp.tasks' });
MZTask.mount('#a');                 // 用 idb
MZTask.mount('#b', { adapter: 'local' });   // 单独覆盖
```

优先级：`mount` 参数 > `config` 全局 > 库内默认。

### `MZTask.annotate(opts)`

| 参数 | 类型 | 必填 | 默认 | 说明 |
|---|---|---|---|---|
| `board` | board | | — | 标注结果写进这块板 |
| `onAdd` | `(task) => void` | | — | 没有 board 时走回调 |
| `trigger` | string \| Element \| Array | | — | 自己的按钮，库自动绑定并豁免 |
| `onStart` / `onStop` | `() => void` | | — | 开关标注时的回调 |

`board` 和 `onAdd` 至少要有一个。

---

## 6. 数据与接口契约

### 6.1 任务对象（Task）

| 字段 | 类型 | 必填 | 默认 | 说明 |
|---|---|---|---|---|
| `id` | string | ✅ | `t` + 序号 | 同板内唯一 |
| `title` | string | ✅ | — | 一句话标题 |
| `detail` | string | | `''` | 细节 |
| `kind` | `'需求'` \| `'问题'` | | `'需求'` | 分类 |
| `status` | `'todo'` \| `'doing'` \| `'done'` | ✅ | `'todo'` | 待办 / 进行中 / 已解决 |
| `created` | number | ✅ | 当前毫秒 | 创建时间 |
| `updated` | number | ✅ | 当前毫秒 | 最后修改 |
| `cause` | string | | — | 问题原因（完成时填） |
| `fix` | string | | — | 解决方案（完成时填） |
| `source` | string | | — | 标注来源的 CSS 选择器 |

```js
{
  id: 't1',
  title: '换题卡死',
  detail: '连续点下一题会卡住',
  kind: '问题',
  status: 'done',
  created: 1700000000000,
  updated: 1700000100000,
  cause: 'finally 里无条件写回签名，形成竞态',
  fix: '把写回移到成功分支',
  source: 'div#quiz > button.next'
}
```

存储层不认识业务字段，除 `id` 外都可以缺，渲染时按默认值补。

### 6.2 状态（State）

```js
{
  tasks: Task[],        // 必填，可以是空数组
  seq: number,          // 必填，下一个可用序号，从 1 开始
  promptTpl?: string    // 可选，用户改过模板才有
}
```

### 6.3 增量操作（Op）

```js
{ type: 'put', task: Task }   // 新增或覆盖一条
{ type: 'del', id: string }   // 删一条
```

### 6.4 适配器接口

| 成员 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `name` | string | ✅ | 适配器名，`board.adapter` 返回它 |
| `load` | `() => Promise<State>` | ✅ | 读全部 |
| `save` | `(state) => Promise` | ✅ | 整体保存 |
| `apply` | `(op) => Promise` | | 有它就走增量，不再调 `save` |
| `saveMeta` | `(meta) => Promise` | | 增量模式下写 `{seq, promptTpl?}` |

**行为约定**：

- 全部返回 Promise；库不 `await` 也不会崩
- `load` 失败应返回 `{tasks: [], seq: 1}`，不要 reject
- 有 `apply` 时库只调 `apply` + `saveMeta`

例子：

```js
var myAdapter = {
  name: 'myBackend',
  load: function () { return fetch('/api/tasks').then(r => r.json()); },
  save: function (s) { return fetch('/api/tasks', { method:'PUT', body: JSON.stringify(s) }); },
  apply: function (op) {
    return op.type === 'put'
      ? fetch('/api/tasks/' + op.task.id, { method:'PUT', body: JSON.stringify(op.task) })
      : fetch('/api/tasks/' + op.id, { method:'DELETE' });
  },
  saveMeta: function (m) {
    return fetch('/api/tasks/_meta', { method:'PUT', body: JSON.stringify(m) });
  }
};
```

### 6.5 data.js 文件格式

```js
window.__MZTASK_DATA__ = {
  tasks: Task[],
  seq: number,
  promptTpl?: string
};
```

必须是合法 JS，能被 `<script src>` 直接引入。读取时用 `new Function` 求值，允许注释和任意缩进。

### 6.6 jsonl 文件格式

一行一条 JSON：

| `t` | 其它字段 | 含义 |
|---|---|---|
| `add` | `task` | 新增（快照行） |
| `upsert` | `task` | 有就覆盖，没有就新增 |
| `update` | `id`, `fields` | 只改指定字段 |
| `delete` | `id` | 删一条 |

```jsonl
{"t":"add","at":1700000000000,"task":{"id":"t1","title":"测试","status":"todo"}}
{"t":"upsert","at":1700000000001,"task":{"id":"t1","title":"测试","status":"done"}}
```

读取时按顺序重放，`at` 可省略。

### 6.7 目录模式布局

```
你选的目录/
  t1.json      {"id":"t1","title":"...","status":"todo"}
  t2.json
  _meta.json   {"seq":3,"promptTpl":"..."}
```

### 6.8 句柄存储

IndexedDB 库 `mztask_handles`，仓库 `handles`，主键 `k`：

```js
{ k: 'jsfile', h: FileSystemFileHandle, at: 1700000000000 }
```

### 6.9 宿主协议（`host` 适配器）

宿主 exe 必须做两件事：

1. 提供 `/board.json`，返回 `{tasks, seq}`
2. 监听 `chrome.webview.message`，收到 `TBA|save|<json>` 就落盘

```csharp
webView.WebMessageReceived += (s, e) => {
    var msg = e.TryGetWebMessageAsString();
    if (msg.StartsWith("TBA|save|")) {
        File.WriteAllText("任务板.json", msg.Substring(9), Encoding.UTF8);
    }
};
```

### 6.10 后端契约（`http` 适配器）

| 方法 | 路径 | 请求体 | 响应 |
|---|---|---|---|
| GET | `/api/tasks` | — | `{tasks, seq, promptTpl?}` |
| PUT | `/api/tasks` | `{tasks, seq, promptTpl?}` | 任意 |
| PUT | `/api/tasks/{id}` | Task | 任意 |
| DELETE | `/api/tasks/{id}` | — | 任意 |
| PUT | `/api/tasks/_meta` | `{seq, promptTpl?}` | 任意 |

---

## 7. API 参考

### 模块级

| 方法 | 返回 | 说明 |
|---|---|---|
| `MZTask.mount(target, opts)` | board | 挂载 |
| `MZTask.config(opts)` | object | 设/取全局默认 |
| `MZTask.annotate(opts)` | annotator | 页面标注（全局单例） |
| `MZTask.adapters` | object | 9 个内置适配器 |
| `MZTask.pickFile(name)` | Promise\<handle\> | 保存对话框（新建） |
| `MZTask.openFile()` | Promise\<handle\> | 打开对话框 |
| `MZTask.pickDir()` | Promise\<handle\> | 选/建目录 |
| `MZTask.saveHandle(key, handle)` | Promise | 存句柄 |
| `MZTask.loadHandle(key)` | Promise\<handle\|null\> | 取句柄 |
| `MZTask.clearHandle(key)` | Promise | 清句柄 |
| `MZTask.ensurePermission(handle)` | Promise\<boolean\> | 查/请求读写权限 |
| `MZTask.replay(text)` | State | 重放 jsonl 文本 |
| `MZTask.diffTasks(prev, next)` | Op[] | 算差异 |
| `MZTask.version` | string | `'1.2.0'` |
| `MZTask.DEFAULT_TPL` / `DEFAULT_RULE` | string | 内置模板 |

### board 实例

| 成员 | 类型 | 说明 |
|---|---|---|
| `ready` | Promise | 存储加载完成 |
| `adapter` | string | 当前适配器名 |
| `el` | Element | 容器元素 |
| `add(task)` | Task | 加一条，返回带 id 的任务 |
| `getTasks()` | Task[] | 全部任务 |
| `setStatus(id, status)` | — | 改状态 |
| `remove(id)` | — | 删一条 |
| `replace(tasks)` | — | 整体替换 |
| `prompt()` | string | 生成 prompt |
| `exportJson()` | string | 导出 JSON |
| `importJson(str)` | — | 导入 JSON |
| `exportDataJs()` | string | 导出成 data.js 文本 |
| `refresh()` | — | 重渲染 |
| `clear()` | — | 清空 |

### annotator 实例

| 方法 | 说明 |
|---|---|
| `start()` / `stop()` / `toggle()` | 开关标注模式 |
| `isOn()` | 是否在标注中 |
| `destroy()` | 销毁，移除 DOM 和监听 |

### 错误约定

- 参数错（如缺 `handle`）抛 `Error`
- 用户取消对话框抛 `name === 'AbortError'`
- 存储失败**不** reject，静默降级

---

## 8. 行为与边界

| 场景 | 行为 |
|---|---|
| `mount` 后立刻 `add` | 先渲染空板，`ready` 完成后补数据。依赖已有数据请先 `await board.ready` |
| 存储加载失败 | 静默降级为空板，不弹错 |
| 写入失败（配额满、权限失效） | 静默忽略，界面不报错 |
| 同一页面多块板 | 传不同 `storageKey` 或 `adapter`，互不干扰 |
| 切换适配器 | **不自动迁移数据**。要迁移：先 `getTasks()`，挂新板后 `replace()` |
| 清浏览器数据 | `local`/`idb`/`opfs` 全丢；文件型的还在 |
| 文件模式刷新 | 可能要重新确认一次权限（浏览器规定）；`local`/`idb`/`opfs` 不需要 |
| 多标签页同时开 | 没有跨页同步，后写的覆盖先写的 |
| 数据量 | `local` 约 5MB 上限；`idb`/`opfs` 几百 MB 起 |
| 标注模式 | 会接管页面点击；`trigger` 按钮和标注弹框内部豁免 |

---

## 9. 常见问题

**Q：为什么不选文件也能用？**
默认 `local`，什么都不用选。文件模式是可选的升级。

**Q：刷新后要重新授权？**
只有文件类（`jsfile`/`file`/`dir`）可能，因为浏览器规定刷新后权限要重新确认。`local`/`idb`/`opfs` 不需要。

**Q：换浏览器或换电脑数据还在吗？**
`local`/`idb`/`opfs` 不跟走。要迁移就导出 `data.js` 或 jsonl 文件。

**Q：一个页面能放几块任务板？**
不限。各自传不同 `storageKey` / `adapter` 即可。

**Q：能改配色吗？**

```css
.mzt { --mzt-gold:#e8c37a; --mzt-accent:#6f8ff5; --mzt-bg:#151d33; --mzt-text:#e6ecff; }
```

**Q：能只显示部分区块吗？**
目前只有 `enablePrompt` 开关。其他区块需要自己写 CSS 隐藏。

**Q：能接后端吗？**
能。写一个带 `load`/`save` 的对象，传给 `adapter` 就行，见第 6.4 节。

**Q：数据会不会悄悄丢？**
唯一会悄悄丢的情况：写入失败（存储满、权限被收回）且你没处理。库不报错，因为任务板不该因为存不进去就崩。要感知失败，在 `onChange` 里做一致性校验，或者用文件模式（文件写失败你能自己检查）。
