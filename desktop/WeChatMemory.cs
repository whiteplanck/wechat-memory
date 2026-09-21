using System;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.Runtime.InteropServices;
using System.Text;
using System.Threading.Tasks;
using System.Windows.Forms;
using Microsoft.Web.WebView2.Core;
using Microsoft.Web.WebView2.WinForms;

static class Program
{
    [STAThread]
    static void Main(string[] args)
    {
        Application.EnableVisualStyles();
        Application.SetCompatibleTextRenderingDefault(false);
        string testDir = args.Length == 2 && args[0] == "--self-test" ? Path.GetFullPath(args[1]) : null;
        Application.Run(new MemoryWindow(testDir));
    }
}

sealed class MemoryWindow : Form
{
    readonly WebView2 view = new WebView2();
    readonly string root = AppDomain.CurrentDomain.BaseDirectory;
    readonly string testDir;
    readonly Label status = new Label();
    Process backend;
    ProcessJob job;
    string origin;
    bool finishing;
    readonly TaskCompletionSource<bool> loaded = new TaskCompletionSource<bool>();
    readonly TaskCompletionSource<bool> downloaded = new TaskCompletionSource<bool>();

    public MemoryWindow(string testDir)
    {
        this.testDir = testDir;
        Text = "微信记忆";
        Size = new Size(1320, 880);
        MinimumSize = new Size(860, 620);
        StartPosition = FormStartPosition.CenterScreen;
        BackColor = Color.FromArgb(8, 13, 22);
        var bar = new Panel { Dock = DockStyle.Top, Height = 44, BackColor = Color.FromArgb(16, 25, 39) };
        var init = new Button { Text = "初始化微信", Dock = DockStyle.Right, Width = 130, FlatStyle = FlatStyle.Flat, ForeColor = Color.White };
        init.Click += delegate { InitializeWeChat(); };
        status.Text = "  正在启动本地工作台…";
        status.ForeColor = Color.FromArgb(160, 220, 225);
        status.Dock = DockStyle.Fill;
        status.TextAlign = ContentAlignment.MiddleLeft;
        bar.Controls.Add(status);
        bar.Controls.Add(init);
        view.Dock = DockStyle.Fill;
        view.DefaultBackgroundColor = BackColor;
        Controls.Add(view);
        Controls.Add(bar);
        Shown += async delegate { await StartApp(); };
        FormClosing += delegate(object sender, FormClosingEventArgs e) {
            if (!finishing && testDir == null && backend != null && !backend.HasExited &&
                MessageBox.Show(this, "关闭将停止本应用及正在进行的任务。已保存的聊天和 Key 会保留。", "关闭微信记忆", MessageBoxButtons.OKCancel, MessageBoxIcon.Question) != DialogResult.OK)
                e.Cancel = true;
        };
        FormClosed += delegate { view.Dispose(); if (job != null) job.Dispose(); if (backend != null) backend.Dispose(); };
    }

    async Task StartApp()
    {
        try
        {
            CoreWebView2Environment.GetAvailableBrowserVersionString();
            if (testDir != null) Directory.CreateDirectory(testDir);
            var start = new ProcessStartInfo(Path.Combine(root, "runtime", "python", "python.exe"));
            start.Arguments = "-u -m wechat_memory.server --no-browser --port 0";
            if (testDir != null) start.Arguments += " --data-dir \"" + Path.Combine(testDir, "archives") + "\"";
            start.WorkingDirectory = root;
            start.UseShellExecute = false;
            start.CreateNoWindow = true;
            start.RedirectStandardOutput = true;
            start.RedirectStandardError = true;
            start.StandardOutputEncoding = Encoding.UTF8;
            job = new ProcessJob();
            backend = Process.Start(start);
            job.Add(backend);
            backend.BeginErrorReadLine(); // Drain without recording private request data.
            var read = backend.StandardOutput.ReadLineAsync();
            if (await Task.WhenAny(read, Task.Delay(30000)) != read) throw new Exception("startup timeout");
            string line = await read;
            int at = line == null ? -1 : line.IndexOf("http://127.0.0.1:", StringComparison.Ordinal);
            if (at < 0) throw new Exception("backend unavailable");
            origin = line.Substring(at).Trim().TrimEnd('/');
            Uri parsed;
            if (!Uri.TryCreate(origin, UriKind.Absolute, out parsed) || parsed.Host != "127.0.0.1" || parsed.Scheme != "http")
                throw new Exception("unexpected backend URL");
            string profile = testDir == null ? Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "WeChatMemory", "WebView2") : Path.Combine(testDir, "WebView2");
            var environment = await CoreWebView2Environment.CreateAsync(null, profile);
            await view.EnsureCoreWebView2Async(environment);
            var core = view.CoreWebView2;
            core.Settings.AreDevToolsEnabled = false;
            core.Settings.AreDefaultContextMenusEnabled = false;
            core.Settings.AreBrowserAcceleratorKeysEnabled = false;
            core.Settings.IsWebMessageEnabled = false;
            core.Settings.AreHostObjectsAllowed = false;
            core.Settings.IsPasswordAutosaveEnabled = false;
            core.Settings.IsGeneralAutofillEnabled = false;
            core.NavigationStarting += delegate(object sender, CoreWebView2NavigationStartingEventArgs e) {
                e.Cancel = !(e.Uri == origin || e.Uri.StartsWith(origin + "/", StringComparison.Ordinal) || e.Uri.StartsWith("blob:" + origin + "/", StringComparison.Ordinal));
            };
            core.NewWindowRequested += delegate(object sender, CoreWebView2NewWindowRequestedEventArgs e) { e.Handled = true; };
            core.PermissionRequested += delegate(object sender, CoreWebView2PermissionRequestedEventArgs e) { e.State = CoreWebView2PermissionState.Deny; };
            core.DownloadStarting += Download;
            core.NavigationCompleted += delegate(object sender, CoreWebView2NavigationCompletedEventArgs e) {
                if (e.IsSuccess) { status.Text = "  本地桌面应用  ·  云端分析需确认"; loaded.TrySetResult(true); }
                else loaded.TrySetException(new Exception("page failed"));
            };
            core.Navigate(origin + "/");
            if (testDir != null) await SmokeTest();
        }
        catch (Exception error)
        {
            Environment.ExitCode = 1;
            if (testDir != null) File.WriteAllText(Path.Combine(testDir, "desktop-failed.txt"), error.ToString());
            else MessageBox.Show(this, "桌面工作台启动失败。请确认已安装 Microsoft Edge WebView2 Runtime，并尝试重新安装应用。聊天与已保存的 Key 不会删除。", "微信记忆", MessageBoxButtons.OK, MessageBoxIcon.Error);
            finishing = true;
            Close();
        }
    }

    void Download(object sender, CoreWebView2DownloadStartingEventArgs e)
    {
        e.Handled = true;
        if (testDir != null)
        {
            e.ResultFilePath = Path.Combine(testDir, "desktop-export.txt");
            e.DownloadOperation.StateChanged += delegate {
                if (e.DownloadOperation.State == CoreWebView2DownloadState.Completed) downloaded.TrySetResult(true);
                if (e.DownloadOperation.State == CoreWebView2DownloadState.Interrupted) downloaded.TrySetException(new Exception("download failed"));
            };
            return;
        }
        var deferred = e.GetDeferral();
        BeginInvoke(new Action(delegate {
            try
            {
                using (var dialog = new SaveFileDialog { FileName = Path.GetFileName(e.ResultFilePath), Filter = "All files (*.*)|*.*", OverwritePrompt = true })
                {
                    if (dialog.ShowDialog(this) == DialogResult.OK) e.ResultFilePath = dialog.FileName;
                    else e.Cancel = true;
                }
            }
            finally { deferred.Complete(); }
        }));
    }

    async Task SmokeTest()
    {
        if (await Task.WhenAny(loaded.Task, Task.Delay(45000)) != loaded.Task) throw new Exception("page timeout");
        await loaded.Task;
        await view.CoreWebView2.ExecuteScriptAsync("document.getElementById('demo').click()");
        bool ok = false;
        for (int i = 0; i < 100; i++)
        {
            string result = await view.CoreWebView2.ExecuteScriptAsync("document.getElementById('count').textContent === '3' && document.querySelectorAll('.message').length === 3");
            if (result == "true") { ok = true; break; }
            await Task.Delay(100);
        }
        if (!ok) throw new Exception("demo render failed");
        await view.CoreWebView2.ExecuteScriptAsync("document.querySelector('[data-view=relationship]').click();document.getElementById('rel-build').click()");
        ok = false;
        for (int i = 0; i < 100; i++)
        {
            if (await view.CoreWebView2.ExecuteScriptAsync("!document.getElementById('rel-result').hidden && document.querySelectorAll('.rel-score').length===2 && document.getElementById('rel-saved').options.length>1") == "true") { ok = true; break; }
            await Task.Delay(100);
        }
        if (!ok) throw new Exception("relationship report failed");
        using (var stream = File.Create(Path.Combine(testDir, "relationship-ui.png")))
            await view.CoreWebView2.CapturePreviewAsync(CoreWebView2CapturePreviewImageFormat.Png, stream);
        await view.CoreWebView2.ExecuteScriptAsync("document.getElementById('rel-add').click()");
        if (await view.CoreWebView2.ExecuteScriptAsync("document.querySelectorAll('.rel-event-form').length>0") != "true") throw new Exception("event editor failed");
        await view.CoreWebView2.ExecuteScriptAsync("document.querySelector('[data-view=memories]').click()");
        if (await view.CoreWebView2.ExecuteScriptAsync("!document.getElementById('memories-view').hidden") != "true") throw new Exception("memories tab failed");
        await view.CoreWebView2.ExecuteScriptAsync("document.querySelector('[data-view=ai]').click(); document.getElementById('provider').value='deepseek'; document.getElementById('provider').dispatchEvent(new Event('change'))");
        if (await view.CoreWebView2.ExecuteScriptAsync("!document.getElementById('ai-view').hidden && !document.getElementById('deepseek-settings').hidden && !document.getElementById('cloud-consent').checked") != "true")
            throw new Exception("analysis UI failed");
        await view.CoreWebView2.ExecuteScriptAsync("download('desktop export test','desktop-export.txt')");
        if (await Task.WhenAny(downloaded.Task, Task.Delay(30000)) != downloaded.Task) throw new Exception("export timeout");
        await downloaded.Task;
        if (File.ReadAllText(Path.Combine(testDir, "desktop-export.txt")) != "desktop export test") throw new Exception("export contents");
        File.WriteAllText(Path.Combine(testDir, "desktop-passed.txt"), origin);
        finishing = true;
        Close();
    }

    void InitializeWeChat()
    {
        if (testDir != null) return;
        try
        {
            Process.Start(new ProcessStartInfo(Path.Combine(root, "runtime", "python", "python.exe"), "-m wechat_memory.installer_launcher init") { WorkingDirectory = root, UseShellExecute = false });
        }
        catch { MessageBox.Show(this, "无法打开初始化窗口，请从开始菜单运行 Initialize WeChat。", "微信记忆"); }
    }
}

// Closing the native app also terminates its own backend and extraction children.
sealed class ProcessJob : IDisposable
{
    [StructLayout(LayoutKind.Sequential)] struct Basic { public long ProcessTime, JobTime; public uint Flags; public UIntPtr Min, Max; public uint Active; public UIntPtr Affinity; public uint Priority, Scheduling; }
    [StructLayout(LayoutKind.Sequential)] struct Io { public ulong ReadOps, WriteOps, OtherOps, ReadBytes, WriteBytes, OtherBytes; }
    [StructLayout(LayoutKind.Sequential)] struct Extended { public Basic Limits; public Io Counters; public UIntPtr ProcessMemory, JobMemory, PeakProcessMemory, PeakJobMemory; }
    [DllImport("kernel32.dll", CharSet = CharSet.Unicode)] static extern IntPtr CreateJobObject(IntPtr attributes, string name);
    [DllImport("kernel32.dll")] static extern bool SetInformationJobObject(IntPtr job, int info, ref Extended data, uint size);
    [DllImport("kernel32.dll")] static extern bool AssignProcessToJobObject(IntPtr job, IntPtr process);
    [DllImport("kernel32.dll")] static extern bool CloseHandle(IntPtr handle);
    IntPtr handle;
    public ProcessJob()
    {
        handle = CreateJobObject(IntPtr.Zero, null);
        var data = new Extended(); data.Limits.Flags = 0x2000;
        if (handle == IntPtr.Zero || !SetInformationJobObject(handle, 9, ref data, (uint)Marshal.SizeOf(data))) { Dispose(); throw new Exception("job creation failed"); }
    }
    public void Add(Process process) { if (!AssignProcessToJobObject(handle, process.Handle)) { process.Kill(); throw new Exception("job assignment failed"); } }
    public void Dispose() { if (handle != IntPtr.Zero) { CloseHandle(handle); handle = IntPtr.Zero; } }
}
