# 桌面「冻结态」真窗口验收 —— 打包态桌面走的就是这条路，无头检查抓不到它。
#
# 干了什么：把 config.yaml 的 dev.use_dev_server 临时关掉（等价于打包态：起本地静态服务 +
# 页面地址挂 ?t=），开一次真窗口，截 PrintWindow 图 + 打印本次新写的日志 + 报端口，
# 最后无论如何都把 config 与 adb 转发还原（try/finally）。
#
# 看什么：① 日志「加载地址」= http://127.0.0.1:47753/?t=…；② 截图里首页有真封面 / 真推荐 /
# 真「继续阅读」；③ 若页面上出现「pywebview 桥没就绪」，就是 ?t= 垫片没装上 —— 2026-10-15
# 那次的桌面回归正是这样暴露的（bridge.ts 曾被"原生桥在不在"这个条件带偏）。
#
# 跑法：powershell -ExecutionPolicy Bypass -File tmp\_check_desktop_frozen.ps1

$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Drawing
Add-Type -ReferencedAssemblies System.Drawing @"
using System;
using System.Text;
using System.Drawing;
using System.Drawing.Imaging;
using System.Runtime.InteropServices;
public class W4 {
  [DllImport("user32.dll")] public static extern bool SetProcessDPIAware();
  [DllImport("user32.dll")] public static extern bool EnumWindows(EnumProc cb, IntPtr l);
  [DllImport("user32.dll", CharSet=CharSet.Unicode)] static extern int GetWindowTextW(IntPtr h, StringBuilder s, int n);
  [DllImport("user32.dll")] static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
  [DllImport("user32.dll")] static extern bool IsWindowVisible(IntPtr h);
  [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT r);
  [DllImport("user32.dll")] public static extern bool PrintWindow(IntPtr h, IntPtr hdc, uint flags);
  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
  [DllImport("user32.dll")] public static extern bool SetWindowPos(IntPtr h, IntPtr a, int x, int y, int cx, int cy, uint f);
  public delegate bool EnumProc(IntPtr h, IntPtr l);
  public struct RECT { public int Left, Top, Right, Bottom; }
  public static IntPtr Find(uint pid, string title) {
    IntPtr hit = IntPtr.Zero;
    EnumWindows(delegate(IntPtr h, IntPtr l) {
      if (!IsWindowVisible(h)) return true;
      var sb = new StringBuilder(300); GetWindowTextW(h, sb, 300);
      if (sb.ToString().IndexOf(title, StringComparison.OrdinalIgnoreCase) < 0) return true;
      uint p; GetWindowThreadProcessId(h, out p);
      if (pid != 0 && p != pid) return true;
      hit = h; return false;
    }, IntPtr.Zero);
    return hit;
  }
  public static string Capture(IntPtr h, string path) {
    RECT r; GetWindowRect(h, out r);
    int w = r.Right - r.Left, ht = r.Bottom - r.Top;
    using (var bmp = new Bitmap(w, ht))
    using (var g = Graphics.FromImage(bmp)) {
      IntPtr hdc = g.GetHdc();
      bool ok = PrintWindow(h, hdc, 2);
      g.ReleaseHdc(hdc);
      bmp.Save(path, ImageFormat.Png);
      return "pw=" + ok + " size=" + w + "x" + ht;
    }
  }
}
"@
[W4]::SetProcessDPIAware() | Out-Null

$adb = "$env:LOCALAPPDATA\Android\Sdk\platform-tools\adb.exe"
& $adb forward --remove tcp:47753 2>$null | Out-Null
Write-Host ("adb 转发已撤：剩余 [" + ((& $adb forward --list) -join ",") + "]")

try {
& python D:\guzhu_comic\tmp\_flip_dev.py off
$log = "$env:USERPROFILE\.jmreader\logs\app.log"
$before = if (Test-Path $log) { (Get-Item $log).Length } else { 0 }

$py = Start-Process -FilePath "D:\guzhu_comic\.venv\Scripts\python.exe" -ArgumentList "main.py" -WorkingDirectory "D:\guzhu_comic" -WindowStyle Hidden -PassThru
Write-Host "已起 main.py pid=$($py.Id)"
Start-Sleep -Seconds 30

$h = [W4]::Find($py.Id, "Guzhu Comic")
if ($h -eq [IntPtr]::Zero) { $h = [W4]::Find(0, "Guzhu Comic") }
if ($h -ne [IntPtr]::Zero) {
  [W4]::SetWindowPos($h, [IntPtr](-1), 0, 0, 0, 0, 0x43) | Out-Null
  [W4]::SetForegroundWindow($h) | Out-Null
  Start-Sleep -Seconds 3
  $r = New-Object W4+RECT
  [W4]::GetWindowRect($h, [ref]$r) | Out-Null
  Write-Host "窗口句柄=$h 矩形 ($($r.Left),$($r.Top))-($($r.Right),$($r.Bottom))"
  Write-Host ("PrintWindow 截图: " + [W4]::Capture($h, "$env:TEMP\_frozen_win.png"))
  $bmp = New-Object System.Drawing.Bitmap(($r.Right - $r.Left), ($r.Bottom - $r.Top))
  $g = [System.Drawing.Graphics]::FromImage($bmp)
  $g.CopyFromScreen($r.Left, $r.Top, 0, 0, $bmp.Size)
  $bmp.Save("$env:TEMP\_frozen_crop.png", [System.Drawing.Imaging.ImageFormat]::Png)
  $g.Dispose(); $bmp.Dispose()
  Write-Host "屏幕裁剪截图: $env:TEMP\_frozen_crop.png"
} else {
  Write-Host "没找到 Guzhu Comic 窗口"
}

Write-Host "---- 本次新写的日志 ----"
if (Test-Path $log) {
  $fs = [System.IO.File]::Open($log, "Open", "Read", "ReadWrite")
  $fs.Seek($before, "Begin") | Out-Null
  $sr = New-Object System.IO.StreamReader($fs, [System.Text.Encoding]::UTF8)
  $txt = $sr.ReadToEnd(); $sr.Dispose(); $fs.Dispose()
  ($txt -split "`r?`n" | Where-Object { $_ -match "app:|desktop|bridge|serve|错误|ERROR|WARN" }) | ForEach-Object { Write-Host "  $_" }
}
Write-Host "---- 端口监听 ----"
Get-NetTCPConnection -State Listen -EA SilentlyContinue | Where-Object { $_.LocalPort -ge 47000 -and $_.LocalPort -le 48000 } | ForEach-Object {
  $p = Get-Process -Id $_.OwningProcess -EA SilentlyContinue
  Write-Host "  $($_.LocalAddress):$($_.LocalPort) <- pid $($_.OwningProcess) $($p.ProcessName)"
}

} finally {
  $kids = Get-CimInstance Win32_Process -Filter "ParentProcessId=$($py.Id)" -EA SilentlyContinue | Select-Object -ExpandProperty ProcessId
  if ($kids) { $kids | ForEach-Object { Stop-Process -Id $_ -Force -EA SilentlyContinue } }
  Stop-Process -Id $py.Id -Force -EA SilentlyContinue
  Start-Sleep -Seconds 2
  & python D:\guzhu_comic\tmp\_flip_dev.py on
  Select-String -LiteralPath D:\guzhu_comic\config.yaml -Pattern use_dev_server | ForEach-Object { Write-Host "config 还原: $($_.Line.Trim())" }
  & $adb forward tcp:47753 tcp:47753 | Out-Null
  Write-Host ("adb 转发已还原：[" + ((& $adb forward --list) -join ",") + "]")
}