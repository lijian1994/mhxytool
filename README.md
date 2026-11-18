# 小建哥的工具箱（梦幻西游）

自用的梦幻西游辅助工具箱：一份 HTML 页面，同时提供**网页版**和**单文件 exe（WebView2）**。

## 目录结构

```
build/
  template2.html      页面源码（模板，带 {{EXP}} 等占位符）
  build.py            注入经验表/任务/题库等数据，生成成品 html
  make_exe.py         用 csc + WebView2 打包成单个 exe
  exe/MzToolbox.cs    exe 宿主：开窗、内存供给页面、托盘、定时关机
  test_exe.py         用真实 exe 内核跑自检（会开窗口）
  smoke_tabs.py       无头 Edge 逐页签烟测（查渲染 / JS 异常）
  shots_tabs.py       无头 Edge 逐页签截图
  _eval.py            无头 Edge 执行一段 JS 并打印结果（临时探针用）
  selfcheck.py        无人值守交互自检（起 http 服务 + 无头 Edge，点控件并断言，7 项）
  edge_guard.py       无头 Edge 进程守卫（只清本工作区的配置目录）
  jscheck.py          页面内联脚本语法检查（node --check）
```

## 构建

```bat
set MZ_OUT=shots\dist\梦幻西游实用工具箱-复刻版.html
python build\build.py          :: 生成成品 html
python build\smoke_tabs.py <url>   :: 无头自检
python build\make_exe.py --publish :: 打包并铺到桌面
```

依赖：.NET Framework 4.x 自带 `csc.exe`、WebView2 SDK（`build/exe/_sdk`，未入库）、
Python 3（`numpy`/`pandas` 不需要）。

## 约定

- 改动先落 HTML，用无头浏览器自检；确认后再编译进 exe（exe 自检会弹窗）。
- 数据存在 `localStorage`（`mz3:` 命名空间，分域存储）；旧键迁移时原样保留，可回滚。
- 关机只走 `shutdown.exe`，不使用系统函数关机。
