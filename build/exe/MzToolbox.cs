// 梦幻西游实用工具箱 · 桌面宿主（WebView2）
// 编译：build\make_exe.py（csc /target:winexe /platform:x64）
// 说明：页面与 HTML 版逐字节一致；本文件只负责开窗、提供 https 源、解包内嵌资源。
//
// 重要：入口 Boot.Main 里**不能出现任何 WebView2 类型**。
// 因为 JIT 编译 Main 时会解析它引用的类型，那时内嵌 DLL 的 AssemblyResolve 钩子还没装上，
// 会直接以 0xe0434352 崩掉。所以真正启动放在 AppRunner.Run()，通过 NoInlining 隔开。

using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Drawing;
using System.Drawing.Imaging;
using System.IO;
using System.Reflection;
using System.Runtime.CompilerServices;
using System.Runtime.InteropServices;
using System.Text;
using System.Threading;
using System.Threading.Tasks;
using System.Windows.Forms;
using Microsoft.Web.WebView2.Core;
using Microsoft.Web.WebView2.WinForms;

namespace MzToolbox
{
    internal static class Boot
    {
        internal const string AppTitle = "小建哥的工具箱";
        internal const string HostName = "mztool.local";
        internal const int WmShowWindow = 0x8001;   // 第二个实例叫回已缩到托盘的窗口
        internal static string RootDir;
        internal static string BinDir;
        internal static string DataDir;

        private static Mutex appMutex;

        [STAThread]
        [MethodImpl(MethodImplOptions.NoInlining)]
        private static int Main(string[] args)
        {
            EnableDpi();

            // 数据目录：默认 <exe 同级>\data（绿色便携，不写 C 盘）；MZ_HOME 可覆盖。
            // 若 exe 所在目录不可写（Program Files、只读介质、沙箱），按顺序退到 %TEMP%\MzToolbox、
            // 最后才用 %LOCALAPPDATA%\MzToolbox —— 每一档都实测能建目录才采用。
            string home = Environment.GetEnvironmentVariable("MZ_HOME");
            List<string> candidates = new List<string>();
            if (!string.IsNullOrEmpty(home)) candidates.Add(home);
            string exeDir = ExeDir();
            if (!string.IsNullOrEmpty(exeDir)) candidates.Add(Path.Combine(exeDir, "MzToolbox"));
            try { candidates.Add(Path.Combine(Path.GetTempPath(), "MzToolbox")); } catch { }
            try
            {
                candidates.Add(Path.Combine(
                    Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "MzToolbox"));
            }
            catch { }

            Exception lastError = null;
            foreach (string candidate in candidates)
            {
                if (string.IsNullOrEmpty(candidate)) continue;
                string bin = Path.Combine(candidate, "bin");
                string data = Path.Combine(candidate, "data");
                try
                {
                    Directory.CreateDirectory(bin);
                    Directory.CreateDirectory(data);
                    RootDir = candidate;
                    BinDir = bin;
                    DataDir = data;
                    lastError = null;
                    break;
                }
                catch (Exception ex)
                {
                    lastError = ex;
                }
            }

            if (RootDir != null && (Environment.GetEnvironmentVariable("MZ_STARTUP_LOG") == "1" ||
                Array.IndexOf(args, "--startup-log") >= 0))
            {
                StartupLogPath = Path.Combine(RootDir, "startup.log");
                try { File.WriteAllText(StartupLogPath, "", Encoding.UTF8); } catch { StartupLogPath = null; }
            }
            Mark("boot: data dir");

            if (RootDir == null)
            {
                CrashLog(lastError);
                try
                {
                    MessageBox.Show("无法创建数据目录，以下位置都不可写：\n" + string.Join("\n", candidates) +
                        "\n\n" + (lastError == null ? "" : lastError.Message),
                        AppTitle, MessageBoxButtons.OK, MessageBoxIcon.Error);
                }
                catch { }
                return 3;
            }

            // 1) 装内嵌程序集钩子 + 解出原生装载器（必须在任何 WebView2 类型被 JIT 之前）
            AppDomain.CurrentDomain.AssemblyResolve += ResolveManagedDll;
            TryExtract("WebView2Loader.dll", Path.Combine(BinDir, "WebView2Loader.dll"));
            Mark("boot: loader extracted");
            SetDllDirectory(BinDir);

            try
            {
                return AppRunner.Run(args, ref appMutex);
            }
            catch (Exception ex)
            {
                CrashLog(ex);
                return 4;
            }
        }

        private static void EnableDpi()
        {
            try { SetProcessDpiAwarenessContext(new IntPtr(-4)); return; } catch { }
            try { SetProcessDPIAware(); } catch { }
        }

        // exe 所在目录（便携数据目录的基准）。注意不能引用 WebView2 类型。
        internal static string ExeDir()
        {
            try
            {
                string path = Application.ExecutablePath;
                if (!string.IsNullOrEmpty(path)) return Path.GetDirectoryName(path);
            }
            catch { }
            try
            {
                Assembly asm = Assembly.GetExecutingAssembly();
                if (!string.IsNullOrEmpty(asm.Location)) return Path.GetDirectoryName(asm.Location);
            }
            catch { }
            return null;
        }

        private delegate bool EnumWindowsProc(IntPtr hWnd, IntPtr lParam);
        [DllImport("user32.dll")]
        private static extern bool EnumWindows(EnumWindowsProc proc, IntPtr lParam);
        [DllImport("user32.dll")]
        private static extern uint GetWindowThreadProcessId(IntPtr hWnd, out uint pid);
        [DllImport("user32.dll", CharSet = CharSet.Unicode)]
        private static extern int GetClassName(IntPtr hWnd, StringBuilder buffer, int size);

        // 缩到托盘的窗口是隐藏状态，Process.MainWindowHandle 会是 0，这里按进程枚举顶层窗口。
        // WinForms 还会有几个同类的隐藏辅助窗口，所以全部返回，让消息发到每一个。
        private static List<IntPtr> FindAppWindows(int pid)
        {
            List<IntPtr> found = new List<IntPtr>();
            try
            {
                EnumWindows(delegate (IntPtr h, IntPtr l)
                {
                    uint owner;
                    GetWindowThreadProcessId(h, out owner);
                    if (owner != (uint)pid) return true;
                    StringBuilder cls = new StringBuilder(256);
                    GetClassName(h, cls, cls.Capacity);
                    if (cls.ToString().StartsWith("WindowsForms10.Window", StringComparison.Ordinal))
                        found.Add(h);
                    return true;
                }, IntPtr.Zero);
            }
            catch { }
            return found;
        }

        internal static void ActivateExisting()
        {
            try
            {
                Process cur = Process.GetCurrentProcess();
                foreach (Process p in Process.GetProcessesByName(cur.ProcessName))
                {
                    if (p.Id == cur.Id) continue;
                    // 窗口可能正缩在托盘里（Hide 之后 ShowWindow 叫不回来），让它自己恢复并重建页面
                    foreach (IntPtr h in FindAppWindows(p.Id))
                        PostMessage(h, WmShowWindow, IntPtr.Zero, IntPtr.Zero);
                }
            }
            catch { }
        }

        private static Assembly ResolveManagedDll(object sender, ResolveEventArgs e)
        {
            string simple = new AssemblyName(e.Name).Name;
            if (simple == "Microsoft.Web.WebView2.Core") return LoadEmbeddedAssembly("WebView2Core.dll");
            if (simple == "Microsoft.Web.WebView2.WinForms") return LoadEmbeddedAssembly("WebView2WinForms.dll");
            return null;
        }

        private static Assembly LoadEmbeddedAssembly(string res)
        {
            using (Stream s = Assembly.GetExecutingAssembly().GetManifestResourceStream(res))
            {
                if (s == null) return null;
                byte[] buf = new byte[s.Length];
                int off = 0;
                while (off < buf.Length) off += s.Read(buf, off, buf.Length - off);
                return Assembly.Load(buf);
            }
        }

        private static void TryExtract(string res, string dest)
        {
            try
            {
                using (Stream s = Assembly.GetExecutingAssembly().GetManifestResourceStream(res))
                {
                    if (s == null) throw new InvalidOperationException("缺少内嵌资源: " + res);
                    byte[] buf = new byte[s.Length];
                    int off = 0;
                    while (off < buf.Length) off += s.Read(buf, off, buf.Length - off);
                    if (File.Exists(dest) && SameBytes(dest, buf)) return;
                    if (File.Exists(dest)) File.SetAttributes(dest, FileAttributes.Normal);
                    File.WriteAllBytes(dest, buf);
                }
            }
            catch (IOException) { }
            catch (UnauthorizedAccessException) { }
        }

        private static bool SameBytes(string path, byte[] buf)
        {
            try
            {
                FileInfo fi = new FileInfo(path);
                if (fi.Length != buf.Length) return false;
                byte[] old = File.ReadAllBytes(path);
                for (int i = 0; i < buf.Length; i++) if (old[i] != buf[i]) return false;
                return true;
            }
            catch { return false; }
        }

        internal static readonly Stopwatch Clock = Stopwatch.StartNew();
        internal static string StartupLogPath;

        // 启动耗时打点：只在 MZ_STARTUP_LOG=1 时写，默认不产生文件
        internal static void Mark(string stage)
        {
            if (StartupLogPath == null) return;
            try
            {
                long sinceProcess = -1;
                try { sinceProcess = (long)(DateTime.Now - Process.GetCurrentProcess().StartTime).TotalMilliseconds; } catch { }
                string line = string.Format("{0:HH:mm:ss.fff}\t{1,6}\t{2,6}\t{3}",
                    DateTime.Now, (long)Clock.Elapsed.TotalMilliseconds, sinceProcess, stage);
                File.AppendAllText(StartupLogPath, line + Environment.NewLine, Encoding.UTF8);
            }
            catch { }
        }

        private static byte[] cachedPage;

        // 页面从内存喂给 WebView2，不落盘。
        // 顺序：MZ_HTML 环境变量 > exe 同级的 index.html（热更）> 内嵌资源（单文件发布）。
        internal static byte[] PageBytes()
        {
            if (cachedPage != null) return cachedPage;

            try
            {
                string overridePath = Environment.GetEnvironmentVariable("MZ_HTML");
                if (!string.IsNullOrEmpty(overridePath) && File.Exists(overridePath))
                {
                    cachedPage = File.ReadAllBytes(overridePath);
                    return cachedPage;
                }
            }
            catch { }

            try
            {
                string dir = ExeDir();
                if (!string.IsNullOrEmpty(dir))
                {
                    string externalHtml = Path.Combine(dir, "index.html");
                    if (File.Exists(externalHtml))
                    {
                        cachedPage = File.ReadAllBytes(externalHtml);
                        return cachedPage;
                    }
                }
            }
            catch { }

            try
            {
                using (Stream s = Assembly.GetExecutingAssembly().GetManifestResourceStream("index.html"))
                {
                    if (s != null)
                    {
                        byte[] buf = new byte[s.Length];
                        int off = 0;
                        while (off < buf.Length) off += s.Read(buf, off, buf.Length - off);
                        cachedPage = buf;
                        return cachedPage;
                    }
                }
            }
            catch { }
            return null;
        }

        internal static void CrashLog(Exception ex)
        {
            try
            {
                string dir = RootDir ?? Path.GetTempPath();
                StringBuilder sb = new StringBuilder();
                sb.AppendLine(DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss"));
                try { sb.AppendLine(ex.GetType().FullName); } catch { }
                try { sb.AppendLine(ex.Message); } catch { }
                try { sb.AppendLine(ex.StackTrace); } catch { }
                File.AppendAllText(Path.Combine(dir, "crash.log"), sb.ToString(), Encoding.UTF8);
            }
            catch { }
        }

        [DllImport("user32.dll")]
        private static extern bool SetProcessDpiAwarenessContext(IntPtr value);
        [DllImport("user32.dll")]
        private static extern bool SetProcessDPIAware();
        [DllImport("kernel32.dll", SetLastError = true, CharSet = CharSet.Unicode)]
        private static extern bool SetDllDirectory(string path);
        [DllImport("user32.dll")]
        private static extern bool SetForegroundWindow(IntPtr h);
        [DllImport("user32.dll")]
        private static extern bool ShowWindow(IntPtr h, int cmd);
        [DllImport("user32.dll", CharSet = CharSet.Unicode)]
        private static extern bool PostMessage(IntPtr h, int msg, IntPtr wParam, IntPtr lParam);
    }

    internal static class AppRunner
    {
        [MethodImpl(MethodImplOptions.NoInlining)]
        internal static int Run(string[] args, ref Mutex appMutex)
        {
            bool selftest = false;
            string jsonOut = null;
            string shot = null;
            string shotTab = null;
            string shotScroll = null;
            int debugPort = 0;
            for (int i = 0; i < args.Length; i++)
            {
                string a = args[i];
                if (a == "--selftest") { selftest = true; jsonOut = Next(args, ref i); }
                else if (a == "--shot") { shot = Next(args, ref i); }
                else if (a == "--tab") { shotTab = Next(args, ref i); }
                else if (a == "--scroll") { shotScroll = Next(args, ref i); }
                else if (a == "--debug-port") { int.TryParse(Next(args, ref i), out debugPort); }
            }

            if (!selftest)
            {
                bool isNew;
                appMutex = new Mutex(true, "MzToolbox_SingleInstance_v1", out isNew);
                if (!isNew)
                {
                    Thread.Sleep(600);
                    Boot.ActivateExisting();
                    return 0;
                }
            }

            Application.EnableVisualStyles();
            Application.SetCompatibleTextRenderingDefault(false);
            MainForm frm = new MainForm(selftest, jsonOut, shot, debugPort, shotTab, shotScroll);
            Application.Run(frm);
            return frm.ExitCode;
        }

        private static string Next(string[] args, ref int i)
        {
            if (i + 1 < args.Length) { i++; return args[i]; }
            return null;
        }
    }

    internal sealed class MainForm : Form
    {
        private const string SelftestJs = @"
(function(){
  if (!window.chrome || !chrome.webview) return;
  window.__errs = [];
  addEventListener('error', function(e){
    try { window.__errs.push(String(e.message) + ' @' + (e.filename||'') + ':' + (e.lineno||0)); } catch(_){}
  });
  addEventListener('unhandledrejection', function(e){
    try { window.__errs.push('rejection: ' + String((e.reason && e.reason.message) || e.reason)); } catch(_){}
  });
  function run(){
    try {
      var btns = [].slice.call(document.querySelectorAll('#tabs button'));
      var rows = [];
      var winHeights = [];
      for (var i = 0; i < btns.length; i++) {
        btns[i].click();
        var on = document.querySelector('section.on');
        try {
          var winEl = document.querySelector('.win');
          if (winEl) winHeights.push(Math.round(winEl.getBoundingClientRect().height));
        } catch (_) {}
        var txt = on ? (on.innerText || '').replace(/\s+/g, '') : '';
        rows.push(btns[i].getAttribute('data-t') + ':' + (on ? on.id : 'null') + ':' + txt.length + ':' +
          (on && on.querySelector('iframe') ? '1' : '0'));
      }
      if (btns.length) btns[0].click();

      /* r90：模拟加点已从 data: iframe 内联进页面，这里做一次交互回归：
         页签能切、保存写进 localStorage、清空能删掉。 */
      try {
        var jd = document.getElementById('jiadian');
        if (!jd) window.__errs.push('jiadian 容器不存在');
        else {
          var jt = jd.querySelectorAll('.tab');
          if (jt.length !== 2) window.__errs.push('jiadian 页签数=' + jt.length);
          else {
            jt[1].click();
            var cmp = (jd.querySelector('.layout') || {}).className || '';
            jt[0].click();
            if (cmp.indexOf('cmp') < 0) window.__errs.push('jiadian 对比页签没切换');
          }
          var qsInput = jd.querySelector('#qs');
          if (!qsInput) window.__errs.push('jiadian 缺 #qs 输入框');
          else {
            qsInput.value = '42';
            jd.querySelector('#mz-save').click();
            var savedRaw = localStorage.getItem('mz.common.v1') || '';
            if (savedRaw.indexOf(""42"") < 0) window.__errs.push('jiadian 保存没写进 localStorage');
            jd.querySelector('#mz-clear').click();
            if (localStorage.getItem('mz.common.v1') !== null) window.__errs.push('jiadian 清空没删掉 localStorage');
          }
        }
      } catch (e) { window.__errs.push('jiadian 自检异常: ' + e.message); }

      /* r91：切页签时外壳高度必须不变，否则就是又回到「窗口伸缩」 */
      if (winHeights.length > 1) {
        var hmin = Math.min.apply(null, winHeights), hmax = Math.max.apply(null, winHeights);
        if (hmax - hmin > 1) window.__errs.push('切页签时外壳高度在变: ' + hmin + '~' + hmax);
      }

      var lsOk = false;
      try { localStorage.setItem('__st', '1'); lsOk = localStorage.getItem('__st') === '1'; localStorage.removeItem('__st'); } catch(e) {}
      var ifr = document.querySelector('#jiadian .layout') || document.querySelector('#jiadian #mz-save');
      var tabs = btns.map(function(b){ return b.getAttribute('data-t'); }).join(',');
      var secs = [].slice.call(document.querySelectorAll('section')).map(function(s){ return s.id; }).join(',');
      var payload = ['ST',
        location.origin,
        ((document.querySelector('.ver') || {}).textContent || ''),
        tabs, secs,
        lsOk ? '1' : '0',
        typeof ((navigator.mediaDevices || {}).getDisplayMedia),
        ifr ? '1' : '0',
        (window.__errs || []).join(' ;; '),
        rows.join(' ;; '),
        String(document.querySelectorAll('.pc').length),
        String(document.querySelectorAll('.cg').length)
      ].join('|');
      chrome.webview.postMessage(payload);
    } catch (err) {
      try { chrome.webview.postMessage('ST|ERR||' + String(err)); } catch(_){}
    }
  }
  if (document.readyState === 'complete') setTimeout(run, 900);
  else addEventListener('load', function(){ setTimeout(run, 900); });
})();
";

        private WebView2 web;
        private Label splash;
        private NotifyIcon tray;
        private bool webBuilt;
        private bool exiting;
        private readonly bool selftest;
        private readonly string jsonPath;
        private readonly string shotPath;
        private readonly string shotTab;
        private readonly string shotScroll;
        private readonly int debugPort;
        private readonly TaskCompletionSource<string> result = new TaskCompletionSource<string>();
        private bool handled;

        public int ExitCode { get; set; }

        public MainForm(bool selftest, string jsonPath, string shotPath, int debugPort, string shotTab, string shotScroll)
        {
            this.selftest = selftest;
            this.jsonPath = jsonPath;
            this.shotPath = shotPath;
            this.shotTab = shotTab;
            this.shotScroll = shotScroll;
            this.debugPort = debugPort;

            Text = Boot.AppTitle;
            StartPosition = FormStartPosition.CenterScreen;
            AutoScaleMode = AutoScaleMode.Dpi;
            BackColor = Color.White;
            Icon = LoadAppIcon();
            DoubleBuffered = true;

            Rectangle wa = Screen.PrimaryScreen.WorkingArea;
            ClientSize = new Size(Math.Min(1400, (int)(wa.Width * 0.94)), Math.Min(900, (int)(wa.Height * 0.94)));
            MinimumSize = new Size(980, 620);

            Boot.Mark("form: ctor start");
            ShowSplash();
            if (!selftest) SetupTray();

            Load += OnLoadedForm;
            FormClosing += OnClosing;
            Shown += OnShownForm;
            Resize += OnResizeForm;
            Boot.Mark("form: ctor done");
        }

        private static Icon LoadAppIcon()
        {
            try
            {
                using (Stream s = Assembly.GetExecutingAssembly().GetManifestResourceStream("app.ico"))
                {
                    if (s != null) return new Icon(s);
                }
            }
            catch { }
            return null;
        }

        private async void OnLoadedForm(object sender, EventArgs e)
        {
            await AttachWebViewAsync();
        }

        private async Task AttachWebViewAsync()
        {
            try
            {
                web = new WebView2();
                web.Dock = DockStyle.Fill;
                Controls.Add(web);
                if (splash != null) splash.BringToFront();

                // 页面全在本地（内存 + https://mztool.local 拦截），不需要 SmartScreen 信誉查询；
                // 开着它首次导航会去查网络，实测会多等 ~2 秒。
                string extra = "--disable-features=msSmartScreenProtection,msWebOOUI,msPdfOOUI " +
                    (debugPort > 0 ? "--remote-debugging-port=" + debugPort + " " : "") +
                    (Environment.GetEnvironmentVariable("MZ_BROWSER_ARGS") ?? "");
                CoreWebView2EnvironmentOptions opts = new CoreWebView2EnvironmentOptions(extra);
                Boot.Mark("webview: env create begin");
                CoreWebView2Environment env = await CoreWebView2Environment.CreateAsync(null, Boot.DataDir, opts);
                Boot.Mark("webview: env created");
                await web.EnsureCoreWebView2Async(env);
                Boot.Mark("webview: controller ready");

                CoreWebView2 core = web.CoreWebView2;
                core.Settings.IsStatusBarEnabled = false;
                core.Settings.AreDefaultContextMenusEnabled = true;
                core.Settings.AreDevToolsEnabled = true;
                core.Settings.AreBrowserAcceleratorKeysEnabled = true;
                core.Settings.IsSwipeNavigationEnabled = false;
                core.Settings.IsPinchZoomEnabled = false;
                core.Settings.IsGeneralAutofillEnabled = false;
                core.Settings.IsPasswordAutosaveEnabled = false;

                // 页面直接从内存提供，不再从磁盘目录映射（省掉 www\index.html 的落地和「读到旧页面」的坑）
                string origin = "https://" + Boot.HostName;
                core.AddWebResourceRequestedFilter(origin + "/*", CoreWebView2WebResourceContext.All);
                core.WebResourceRequested += delegate (object handlerSender, CoreWebView2WebResourceRequestedEventArgs args)
                {
                    try
                    {
                        string path = args.Request.Uri;
                        if (path.StartsWith(origin, StringComparison.OrdinalIgnoreCase)) path = path.Substring(origin.Length);
                        int question = path.IndexOf('?');
                        if (question >= 0) path = path.Substring(0, question);

                        if (path.Length == 0 || path == "/" || path == "/index.html")
                        {
                            byte[] page = Boot.PageBytes();
                            if (page != null)
                            {
                                args.Response = env.CreateWebResourceResponse(
                                    new MemoryStream(page, false), 200, "OK", "Content-Type: text/html; charset=utf-8");
                                return;
                            }
                        }
                        args.Response = env.CreateWebResourceResponse(
                            new MemoryStream(new byte[0], false), 404, "Not Found", "Content-Type: text/plain");
                    }
                    catch { }
                };
                core.PermissionRequested += OnPermissionRequested;
                core.NewWindowRequested += OnNewWindow;
                core.WebMessageReceived += OnWebMessage;
                core.NavigationCompleted += OnNavigationCompleted;

                if (selftest) await core.AddScriptToExecuteOnDocumentCreatedAsync(SelftestJs);

                core.Navigate("https://" + Boot.HostName + "/index.html");
                Boot.Mark("webview: navigate called");
                webBuilt = true;
            }
            catch (Exception ex)
            {
                FailStartup(ex);
            }
        }

        private void FailStartup(Exception ex)
        {
            ExitCode = 2;
            Boot.CrashLog(ex);
            if (selftest && jsonPath != null)
            {
                WriteFile(jsonPath, "{\"ok\":false,\"error\":" + Quote(ex.GetType().Name + ": " + ex.Message) + "}\n");
                Close();
                return;
            }
            MessageBox.Show(this,
                "界面引擎（Microsoft Edge WebView2）启动失败。\n\n" + ex.Message +
                "\n\n可安装「Microsoft Edge WebView2 Runtime」后重试。",
                Boot.AppTitle, MessageBoxButtons.OK, MessageBoxIcon.Error);
            Close();
        }

        private void OnPermissionRequested(object sender, CoreWebView2PermissionRequestedEventArgs e)
        {
            try
            {
                if (e.PermissionKind == CoreWebView2PermissionKind.ClipboardRead)
                {
                    e.State = CoreWebView2PermissionState.Allow;
                    e.SavesInProfile = true;
                }
            }
            catch { }
        }

        private void OnNewWindow(object sender, CoreWebView2NewWindowRequestedEventArgs e)
        {
            e.Handled = true;
            try { Process.Start(e.Uri); } catch { }
        }

        private void OnWebMessage(object sender, CoreWebView2WebMessageReceivedEventArgs e)
        {
            string msg = null;
            try { msg = e.TryGetWebMessageAsString(); } catch { }
            if (msg == null) return;
            if (msg.StartsWith("ST|")) result.TrySetResult(msg);
            else if (msg.StartsWith("SD|")) HandleScheduledAction(msg);
            else if (msg.StartsWith("TB|save|")) SaveTaskBoard(msg.Substring(8));
            else if (msg.StartsWith("LG|save|")) SaveLedgerFile(msg.Substring(8));
        }

        // 页面「定时关机」发来的动作：SD|<pc|game|cancel|monitor>|<force 0/1>
        private void HandleScheduledAction(string msg)
        {
            string[] f = msg.Split('|');
            string action = f.Length > 1 ? f[1] : "";
            bool force = f.Length > 2 && f[2] == "1";
            Boot.Mark("schedule: " + action + " force=" + force);

            switch (action)
            {
                case "schedule":
                    {
                        // SD|schedule|<action>|<force>|<unix_ms>
                        string what = f.Length > 2 ? f[2] : "pc";
                        bool frc = f.Length > 3 && f[3] == "1";
                        long when;
                        long.TryParse(f.Length > 4 ? f[4] : "0", out when);
                        StartSchedule(when, what, frc);
                        long mins = Math.Max(0, (when - DateTimeOffset.UtcNow.ToUnixTimeMilliseconds()) / 60000);
                        string label = what == "pc" ? "关机" : "关闭游戏";
                        NotifyTray("已排定：约 " + mins + " 分钟后" + label +
                            (frc ? "（强制）" : "") + "；可在梦幻时钟页点「停止」取消");
                        NotifyPage("SDOK|已排定：约 " + mins + " 分钟后" + label);
                        break;
                    }
                case "abort":
                    AbortSchedule(true);
                    NotifyTray("定时已停止");
                    break;
                case "status":
                    if (scheduleDeadline > 0)
                        NotifyPage("SDREMAIN|" + (scheduleDeadline - DateTimeOffset.UtcNow.ToUnixTimeMilliseconds()) + "|" + scheduleAction);
                    else
                        NotifyPage("SDOK|未启动");
                    break;
                case "pc":
                    RunShutdown(true, force);
                    NotifyPage("SDOK|关机命令已发出（10 秒后关机，这期间点「停止」可取消）");
                    break;
                case "cancel":
                    RunShutdown(false, false);
                    NotifyPage("SDOK|已取消待执行的关机");
                    break;
                case "game":
                    {
                        int closed = CloseGameProcesses();
                        NotifyPage(closed > 0 ? ("SDOK|已关闭游戏（" + closed + " 个进程）") : "SDOK|没找到在跑的游戏进程");
                        break;
                    }
                case "monitor":
                    TurnOffMonitor();
                    NotifyPage("SDOK|显示器已关闭");
                    break;
                default:
                    NotifyPage("SDERR|未知动作");
                    break;
            }
        }

        private System.Windows.Forms.Timer scheduleTimer;
        private long scheduleDeadline;
        private string scheduleAction = "pc";
        private bool scheduleForce;

        // 计时放在宿主里：页面缩到托盘会被销毁，但这里的 Timer 照样走
        private void StartSchedule(long deadlineMs, string action, bool force)
        {
            scheduleDeadline = deadlineMs;
            scheduleAction = action;
            scheduleForce = force;
            if (scheduleTimer == null)
            {
                scheduleTimer = new System.Windows.Forms.Timer();
                scheduleTimer.Interval = 500;
                scheduleTimer.Tick += ScheduleTick;
            }
            scheduleTimer.Start();
            Boot.Mark("schedule: armed " + action + " force=" + force + " in " + (deadlineMs - DateTimeOffset.UtcNow.ToUnixTimeMilliseconds()) + "ms");
        }

        private void AbortSchedule(bool notify)
        {
            if (scheduleTimer != null) scheduleTimer.Stop();
            scheduleDeadline = 0;
            RunShutdown(false, false);          // 顺手取消已经排进系统的那 10 秒关机
            Boot.Mark("schedule: aborted");
            if (notify) NotifyPage("SDOK|已停止");
        }

        private void ScheduleTick(object sender, EventArgs e)
        {
            if (scheduleDeadline <= 0) return;
            if (DateTimeOffset.UtcNow.ToUnixTimeMilliseconds() < scheduleDeadline) return;

            string action = scheduleAction;
            bool force = scheduleForce;
            if (scheduleTimer != null) scheduleTimer.Stop();
            scheduleDeadline = 0;
            Boot.Mark("schedule: FIRE " + action);

            NotifyTray(action == "pc" ? "时间到：正在关机" : "时间到：正在关闭游戏");
            if (action == "pc")
            {
                RunShutdown(true, force);
                NotifyPage("SDOK|关机命令已发出（10 秒后关机）");
            }
            else
            {
                NotifyPage("SDOK|正在关闭游戏…");
                ThreadPool.QueueUserWorkItem(delegate
                {
                    int n = CloseGameProcesses();
                    PostUi(delegate { NotifyPage("SDOK|已关闭游戏（" + n + " 个进程）"); });
                });
            }
        }

        private void PostUi(Action action)
        {
            try { if (IsHandleCreated) BeginInvoke(action); } catch { }
        }

        // 任务板双写：除了页面里的 localStorage，再落一份 JSON 到 exe 目录，agent 可以直接读
        private void SaveTaskBoard(string json)
        {
            try
            {
                string dir = Boot.ExeDir();
                if (string.IsNullOrEmpty(dir)) dir = Boot.RootDir;
                string path = Path.Combine(dir, "任务板.json");
                File.WriteAllText(path, json, new UTF8Encoding(false));
                NotifyPage("TBOK|已保存到 " + path);
            }
            catch (Exception ex)
            {
                NotifyPage("TBERR|保存失败：" + ex.Message);
            }
        }

        // 收支记账导出：写到 exe 旁边的 JSON
        private void SaveLedgerFile(string json)
        {
            try
            {
                string dir = Boot.ExeDir();
                if (string.IsNullOrEmpty(dir)) dir = Boot.RootDir;
                string path = Path.Combine(dir, "收支记账.json");
                File.WriteAllText(path, json, new UTF8Encoding(false));
                NotifyPage("LGOK|已导出到 " + path);
            }
            catch (Exception ex)
            {
                NotifyPage("LGERR|导出失败：" + ex.Message);
            }
        }

        private void NotifyTray(string text)
        {
            try { if (tray != null) tray.ShowBalloonTip(2000, Boot.AppTitle, text, ToolTipIcon.Info); }
            catch { }
        }

        private void NotifyPage(string text)
        {
            try { if (web != null && web.CoreWebView2 != null) web.CoreWebView2.PostWebMessageAsString(text); }
            catch { }
        }

        // 关机只走命令行，不调用 ExitWindowsEx 之类的系统函数
        private static void RunShutdown(bool start, bool force)
        {
            try
            {
                ProcessStartInfo psi = new ProcessStartInfo("shutdown.exe",
                    start ? ("-s -t 10" + (force ? " -f" : "")) : "-a");
                psi.UseShellExecute = false;
                psi.CreateNoWindow = true;
                using (Process p = Process.Start(psi))
                {
                    if (p != null) p.WaitForExit(5000);
                }
            }
            catch (Exception ex) { Boot.CrashLog(ex); }
        }

        private static readonly string[] GameProcessNames = { "mhmain", "mhrender", "mhtab", "xyqsvc" };

        // 先请窗口正常关，2.5 秒后还在的强制结束
        private static int CloseGameProcesses()
        {
            int closed = 0;
            foreach (string name in GameProcessNames)
            {
                Process[] list;
                try { list = Process.GetProcessesByName(name); } catch { continue; }
                foreach (Process p in list)
                {
                    try { if (p.MainWindowHandle != IntPtr.Zero) p.CloseMainWindow(); } catch { }
                    p.Dispose();
                }
            }
            Thread.Sleep(2500);
            foreach (string name in GameProcessNames)
            {
                Process[] list;
                try { list = Process.GetProcessesByName(name); } catch { continue; }
                foreach (Process p in list)
                {
                    try { p.Kill(); closed++; } catch { }
                    p.Dispose();
                }
            }
            return closed;
        }

        [DllImport("user32.dll")]
        private static extern IntPtr SendMessage(IntPtr hWnd, int msg, IntPtr wParam, IntPtr lParam);

        private void TurnOffMonitor()
        {
            try { SendMessage(new IntPtr(0xFFFF), 0x0112, new IntPtr(0xF170), new IntPtr(2)); }
            catch { }
        }

        private async void OnNavigationCompleted(object sender, CoreWebView2NavigationCompletedEventArgs e)
        {
            Boot.Mark("webview: navigation completed");
            try
            {
                string timing = await web.CoreWebView2.ExecuteScriptAsync(
                    "(function(){var t=performance.timing;return (t.domContentLoadedEventEnd-t.navigationStart)+'/'+(t.loadEventEnd-t.navigationStart);})()");
                Boot.Mark("page: dcl/load " + timing);
            }
            catch { }
            Boot.Mark("READY");
            if (splash != null)
            {
                Controls.Remove(splash);
                splash.Dispose();
                splash = null;
            }

            if (selftest) { await RunSelftest(e); return; }
            if (!e.IsSuccess)
            {
                MessageBox.Show(this, "页面加载失败：" + e.WebErrorStatus,
                    Boot.AppTitle, MessageBoxButtons.OK, MessageBoxIcon.Error);
            }
        }

        private async Task RunSelftest(CoreWebView2NavigationCompletedEventArgs nav)
        {
            if (handled) return;
            handled = true;

            List<string> problems = new List<string>();
            if (!nav.IsSuccess) problems.Add("navigation:" + nav.WebErrorStatus);

            await Task.WhenAny(result.Task, Task.Delay(30000));
            string payload = result.Task.Status == TaskStatus.RanToCompletion ? result.Task.Result : null;
            if (payload == null) problems.Add("timeout: 页面 30 秒内没有回报自检结果");

            string origin = "", ver = "", tabs = "", secs = "", ls = "", gdm = "", ifr = "", errs = "", rows = "", cards = "", cg = "";
            if (payload != null)
            {
                string[] f = payload.Split('|');
                if (f.Length >= 12)
                {
                    origin = f[1]; ver = f[2]; tabs = f[3]; secs = f[4]; ls = f[5];
                    gdm = f[6]; ifr = f[7]; errs = f[8]; rows = f[9]; cards = f[10]; cg = f[11];
                }
                else problems.Add("payload-short:" + payload);
            }

            string[] expectTabs = { "daomai", "shouyi", "quiz", "renwu", "jiadian", "jzb", "baoshi", "paoshang", "ledger", "task", "about" };
            string[] gotTabs = tabs.Split(new char[] { ',' }, StringSplitOptions.RemoveEmptyEntries);
            if (gotTabs.Length != expectTabs.Length) problems.Add("页签数量 " + gotTabs.Length + " != 11");
            else
            {
                for (int i = 0; i < expectTabs.Length; i++)
                    if (gotTabs[i] != expectTabs[i]) problems.Add("页签顺序 #" + (i + 1) + " = " + gotTabs[i] + "（应为 " + expectTabs[i] + "）");
            }

            string[] gotSecs = secs.Split(new char[] { ',' }, StringSplitOptions.RemoveEmptyEntries);
            if (gotSecs.Length != 11) problems.Add("section 数量 " + gotSecs.Length + " != 11");
            if (origin != "https://" + Boot.HostName) problems.Add("origin=" + origin);
            if (!System.Text.RegularExpressions.Regex.IsMatch(ver, @"^V\d+\.\d+ · r\d+\s*$")) problems.Add("版本号异常: " + ver);
            if (ls != "1") problems.Add("localStorage 不可写");
            if (gdm != "function") problems.Add("getDisplayMedia=" + gdm);
            if (ifr != "1") problems.Add("模拟加点内容缺失");
            if (errs.Length > 0) problems.Add("JS 异常: " + errs);

            string[] rowList = rows.Split(new string[] { " ;; " }, StringSplitOptions.RemoveEmptyEntries);
            if (rowList.Length != 11) problems.Add("逐页签结果 " + rowList.Length + " 条 != 12");
            foreach (string row in rowList)
            {
                string[] p = row.Split(':');
                if (p.Length < 3) { problems.Add("行格式异常: " + row); continue; }
                if (p[1] != p[0]) problems.Add("点 " + p[0] + " 后显示的是 " + p[1]);
                int len;
                // iframe 型页签（模拟加点）正文在 iframe 里，section.innerText 本来就是 0，不能按字数判失败
                bool iframeOnly = p.Length >= 4 && p[3] == "1";
                if (!int.TryParse(p[2], out len)) problems.Add("页签 " + p[0] + " 字数无法解析: " + p[2]);
                else if (len < 80 && !iframeOnly) problems.Add("页签 " + p[0] + " 正文只有 " + p[2] + " 字");
            }

            int cardCount, cgCount;
            if (!int.TryParse(cards, out cardCount) || cardCount < 8) problems.Add(".pc 卡片数=" + cards);
            if (!int.TryParse(cg, out cgCount) || cgCount < 4) problems.Add(".cg 卡片数=" + cg);

            if (problems.Count == 0 && shotPath != null)
            {
                await Task.Delay(500);
                if (!string.IsNullOrEmpty(shotTab))
                {
                    // 截图前切到指定页签，便于人工核对某一页
                    try
                    {
                        await web.ExecuteScriptAsync(
                            "(function(){var b=document.querySelector('#tabs button[data-t=\"" + shotTab +
                            "\"]'); if(b) b.click();})()");
                        await Task.Delay(900);
                    }
                    catch { }
                }
                if (!string.IsNullOrEmpty(shotScroll))
                {
                    // 截图前把某个元素滚到视野中间（核对页面下半部分的卡片）
                    try
                    {
                        await web.ExecuteScriptAsync(
                            "(function(){var el=document.querySelector(\"" + shotScroll +
                            "\"); if(el) el.scrollIntoView({block:'center'});})()");
                        await Task.Delay(600);
                    }
                    catch { }
                }
                await CaptureShot(shotPath);
            }

            ExitCode = problems.Count == 0 ? 0 : 1;
            if (jsonPath != null) WriteFile(jsonPath, BuildReport(problems, origin, ver, tabs, secs));

            Close();
        }

        private string BuildReport(List<string> problems, string origin, string ver, string tabs, string secs)
        {
            StringBuilder sb = new StringBuilder();
            sb.Append("{\n");
            sb.Append("  \"ok\": ").Append(problems.Count == 0 ? "true" : "false").Append(",\n");
            sb.Append("  \"origin\": ").Append(Quote(origin)).Append(",\n");
            sb.Append("  \"version\": ").Append(Quote(ver)).Append(",\n");
            sb.Append("  \"tabs\": ").Append(Quote(tabs)).Append(",\n");
            sb.Append("  \"sections\": ").Append(Quote(secs)).Append(",\n");
            sb.Append("  \"userData\": ").Append(Quote(Boot.DataDir)).Append(",\n");
            sb.Append("  \"problems\": [");
            for (int i = 0; i < problems.Count; i++)
            {
                if (i > 0) sb.Append(", ");
                sb.Append(Quote(problems[i]));
            }
            sb.Append("]\n}\n");
            return sb.ToString();
        }

        private async Task CaptureShot(string path)
        {
            try
            {
                using (MemoryStream ms = new MemoryStream())
                {
                    await web.CoreWebView2.CapturePreviewAsync(CoreWebView2CapturePreviewImageFormat.Png, ms);
                    File.WriteAllBytes(path, ms.ToArray());
                }
            }
            catch { try { Boot.CrashLog(new Exception("capture failed")); } catch { } }
        }

        private static void WriteFile(string path, string text)
        {
            try { File.WriteAllText(path, text, new UTF8Encoding(false)); } catch { }
        }

        private static string Quote(string s)
        {
            if (s == null) return "null";
            StringBuilder sb = new StringBuilder("\"");
            foreach (char c in s)
            {
                switch (c)
                {
                    case '"': sb.Append("\\\""); break;
                    case '\\': sb.Append("\\\\"); break;
                    case '\n': sb.Append("\\n"); break;
                    case '\r': sb.Append("\\r"); break;
                    case '\t': sb.Append("\\t"); break;
                    default:
                        if (c < ' ') sb.Append("\\u").Append(((int)c).ToString("x4"));
                        else sb.Append(c);
                        break;
                }
            }
            return sb.Append('"').ToString();
        }

        protected override void OnShown(EventArgs e)
        {
            base.OnShown(e);
        }

        private void OnShownForm(object sender, EventArgs e)
        {
            Boot.Mark("form: shown");
            if (selftest) return;
            try { RestoreBoundsFile(); } catch { }
        }

        private void ShowSplash()
        {
            if (splash != null) return;
            splash = new Label();
            splash.Dock = DockStyle.Fill;
            splash.TextAlign = ContentAlignment.MiddleCenter;
            splash.Text = Boot.AppTitle + "\n\n正在启动…";
            splash.Font = new Font("Microsoft YaHei", 12F, FontStyle.Regular);
            splash.ForeColor = Color.FromArgb(120, 130, 150);
            splash.BackColor = Color.FromArgb(18, 20, 30);
            Controls.Add(splash);
            splash.BringToFront();
        }

        private void SetupTray()
        {
            tray = new NotifyIcon();
            tray.Icon = Icon ?? SystemIcons.Application;
            tray.Text = Boot.AppTitle;
            tray.Visible = true;
            ContextMenuStrip menu = new ContextMenuStrip();
            menu.Items.Add("显示窗口", null, delegate { RestoreFromTray(); });
            menu.Items.Add(new ToolStripSeparator());
            menu.Items.Add("退出", null, delegate { exiting = true; Close(); });
            tray.ContextMenuStrip = menu;
            tray.DoubleClick += delegate { RestoreFromTray(); };
        }

        private void OnResizeForm(object sender, EventArgs e)
        {
            Boot.Mark("form: resize " + WindowState);
            if (WindowState == FormWindowState.Minimized && tray != null) HideToTray();
        }

        // 缩到托盘时把 WebView2 整个拆掉，内存还给系统；从托盘恢复再重建（约 0.6 秒）
        private void HideToTray()
        {
            Boot.Mark("tray: hidden");
            Hide();
            TeardownWebView();
            try { tray.ShowBalloonTip(1200, Boot.AppTitle, "已缩到托盘，双击图标打开", ToolTipIcon.Info); } catch { }
        }

        private void RestoreFromTray()
        {
            if (exiting) return;
            Show();
            WindowState = FormWindowState.Normal;
            Activate();
            if (!webBuilt)
            {
                ShowSplash();
                Task ignored = AttachWebViewAsync();
            }
        }

        private void TeardownWebView()
        {
            if (web == null) return;
            try { Controls.Remove(web); web.Dispose(); } catch { }
            web = null;
            webBuilt = false;
            Boot.Mark("tray: webview disposed");
        }

        protected override void WndProc(ref Message m)
        {
            if (m.Msg == Boot.WmShowWindow)
            {
                RestoreFromTray();
                return;
            }
            base.WndProc(ref m);
        }

        private void OnClosing(object sender, FormClosingEventArgs e)
        {
            if (!selftest)
            {
                try { SaveBounds(); } catch { }
            }
            try { if (scheduleTimer != null) { scheduleTimer.Stop(); scheduleTimer.Dispose(); scheduleTimer = null; } } catch { }
            try { if (tray != null) { tray.Visible = false; tray.Dispose(); tray = null; } } catch { }
            try { if (web != null) web.Dispose(); } catch { }
        }

        private void SaveBounds()
        {
            string p = Path.Combine(Boot.RootDir, "window.txt");
            Rectangle b = WindowState == FormWindowState.Normal ? Bounds : RestoreBounds;
            File.WriteAllText(p, string.Format("{0},{1},{2},{3},{4}", b.X, b.Y, b.Width, b.Height,
                WindowState == FormWindowState.Maximized ? 1 : 0));
        }

        private void RestoreBoundsFile()
        {
            string p = Path.Combine(Boot.RootDir, "window.txt");
            if (!File.Exists(p)) return;
            string[] f = File.ReadAllText(p).Split(',');
            if (f.Length < 4) return;
            int x, y, w, h;
            if (!int.TryParse(f[0], out x) || !int.TryParse(f[1], out y)) return;
            if (!int.TryParse(f[2], out w) || !int.TryParse(f[3], out h)) return;
            if (w < 900 || h < 600) return;
            Rectangle want = new Rectangle(x, y, w, h);
            if (!Screen.PrimaryScreen.WorkingArea.IntersectsWith(want)) return;
            Bounds = want;
            if (f.Length > 4 && f[4].Trim() == "1") WindowState = FormWindowState.Maximized;
        }

        [DllImport("user32.dll")]
        private static extern bool SetForegroundWindow(IntPtr h);
    }
}
