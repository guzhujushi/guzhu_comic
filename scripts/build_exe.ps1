<#
.SYNOPSIS
  打 Windows 免安装包（PyInstaller onedir，含 frontend/dist 静态产物）。

.DESCRIPTION
  前置（P0 迁移已落码，见 tmp\打包分发设计.md §4 与 backend/paths.py、backend/server.py）：
    1) main.py 冻结态起本地静态服务挂 frontend/dist（源码态 + dev.use_dev_server 才走 vite）；
    2) 配置落用户目录（~/.jmreader/config.yaml，首启写默认值）；3) WebView2 的 user data 固定在
       ~/.jmreader/webview —— localStorage（主题 / 榜单偏好）才活得过重启。

  用法：
    powershell -ExecutionPolicy Bypass -File scripts\build_exe.ps1
    powershell -ExecutionPolicy Bypass -File scripts\build_exe.ps1 -SkipFrontend   # 前端没改，跳过 npm
    powershell -ExecutionPolicy Bypass -File scripts\build_exe.ps1 -Console       # 调试：留控制台看 traceback

  产物：build_out\<Name>\<Name>.exe（免安装，整个目录拷走就能用）+ build_out\<Name>-<Version>-win64.zip
  实测（2026-10-14）：onedir 38.9 MB / 构建约 25 秒 / Defender 全量扫描无威胁。
#>
param(
  [string]$Name = 'GuzhuComic',
  [string]$Version = '0.1.0',
  [switch]$SkipFrontend,
  [switch]$Console
)
$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$Python = Join-Path $Root '.venv\Scripts\python.exe'
$Frontend = Join-Path $Root 'frontend'
$Dist = Join-Path $Frontend 'dist'
$Work = Join-Path $Root 'build_work'
$Out = Join-Path $Root 'build_out'

if (-not (Test-Path $Python)) { throw "找不到虚拟环境解释器：$Python" }
& $Python -c "import PyInstaller" 2>$null
if ($LASTEXITCODE -ne 0) {
  throw "没装 PyInstaller。先在仓库根跑：.venv\Scripts\python.exe -m pip install -r requirements-build.txt"
}

# 1) 前端产物：Node / Vite / TS 只在**构建机**用得上，不进包
if (-not $SkipFrontend) {
  Write-Host '[1/4] 构建前端 …'
  Push-Location $Frontend
  try {
    & npm run build
    if ($LASTEXITCODE -ne 0) { throw '前端构建失败（npm run build = tsc && vite build）' }
  } finally { Pop-Location }
}
if (-not (Test-Path (Join-Path $Dist 'index.html'))) { throw "没有 frontend\dist\index.html" }
$DistKb = [math]::Round(((Get-ChildItem $Dist -Recurse -File | Measure-Object Length -Sum).Sum / 1KB), 1)
Write-Host "[1/4] 前端产物就绪：$DistKb KB"

New-Item -ItemType Directory -Force -Path $Work, $Out | Out-Null

# 2) 图标 + 版本信息（PyInstaller 只认 .ico 与 version-file；版本信息是"少挨杀软"的重要一项）
Write-Host '[2/4] 生成图标与版本信息 …'
$Ico = Join-Path $Work 'app.ico'
# 源图优先用 256 那张过：Pillow 写 ICO 只会缩、不会放（源图 180 时 256 那帧根本产不出来），
# 有 256 的源，资源管理器/任务栏的大图标才不是放大糊的。没有就退回 180 那张。
$PngBig = Join-Path $Root 'frontend\public\apple-touch-icon-256.png'
$Png = if (Test-Path $PngBig) { $PngBig } else { Join-Path $Root 'frontend\public\apple-touch-icon.png' }
$pyIcon = @"
from PIL import Image
im = Image.open(r'$Png').convert('RGBA')
wanted = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (180, 180), (256, 256)]
sizes = [s for s in wanted if s[0] <= min(im.size)]
im.save(r'$Ico', sizes=sizes)
print('icon ok', im.size, '->', len(sizes), 'sizes')
"@
& $Python -c $pyIcon
if ($LASTEXITCODE -ne 0) { throw '图标生成失败（Pillow 生成 .ico）' }

$VerFile = Join-Path $Work 'version_info.txt'
$Parts = $Version.Split('.')
while ($Parts.Count -lt 4) { $Parts += '0' }
$VerTuple = ($Parts[0..3] -join ', ')
$verText = @"
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=($VerTuple), prodvers=($VerTuple),
    mask=0x3f, flags=0x0, OS=0x40004, fileType=0x1, subtype=0x0, date=(0, 0)
  ),
  kids=[
    StringFileInfo([
      StringTable('080404B0', [
        StringStruct('CompanyName', 'Guzhu'),
        StringStruct('FileDescription', 'Guzhu Comic - desktop manga reader'),
        StringStruct('FileVersion', '$Version'),
        StringStruct('InternalName', '$Name'),
        StringStruct('LegalCopyright', 'MIT License'),
        StringStruct('OriginalFilename', '$Name.exe'),
        StringStruct('ProductName', 'Guzhu Comic'),
        StringStruct('ProductVersion', '$Version')
      ])
    ]),
    VarFileInfo([VarStruct('Translation', [2052, 1200])])
  ]
)
"@
# PyInstaller 用 tokenize.detect_encoding 读这个文件（默认 UTF-8），写 UTF-8 无 BOM 最稳
[System.IO.File]::WriteAllText($VerFile, $verText.Replace("`r`n", "`n"), (New-Object System.Text.UTF8Encoding($false)))

# 3) PyInstaller：onedir（**不要 --onefile**：自解压到 %TEMP% 是杀软误报的头号来源）
Write-Host '[3/4] PyInstaller 打包 …'
# 发布态不留控制台（黑框）；-Console 时换成 console 子系统，traceback 才看得见
$Subsystem = if ($Console) { '--console' } else { '--windowed' }
$pyArgs = @(
  '-m', 'PyInstaller', '--noconfirm', '--clean',
  $Subsystem,
  '--onedir', '--name', $Name, '--noupx',                       # 不开 UPX：压缩壳会被启发式引擎盯上
  '--icon', $Ico, '--version-file', $VerFile,                   # exe 图标 + 版本信息
  '--distpath', $Out, '--workpath', $Work, '--specpath', $Work,
  '--add-data', "$Dist;dist",                                    # 前端产物 -> <exe>/_internal/dist
  # tkinter / AVIF 编解码器我们都不用，砍掉 7 MB + 7.5 MB（实测不炸）
  '--exclude-module', 'tkinter', '--exclude-module', 'PIL.AvifImagePlugin',
  '--exclude-module', 'test', '--exclude-module', 'unittest', '--exclude-module', 'pydoc',
  # pythonnet / clr_loader（pywebview 的 Windows 后端要靠它）+ curl_cffi.libs 里的 libcurl 都不是自动收得全的
  '--collect-all', 'webview', '--collect-all', 'pythonnet', '--collect-all', 'clr_loader',
  '--hidden-import', 'clr', '--collect-all', 'jmcomic', '--collect-all', 'curl_cffi',
  'main.py'
)
# 子系统在 $pyArgs 里由 $Subsystem 决定（见上），这里不再拼第二遍参数
& $Python @pyArgs
if ($LASTEXITCODE -ne 0) { throw 'PyInstaller 失败' }

# 4) 体积报告 + zip（zip 分发比裸 exe 好：下载方不用面对"未知发布者 exe"）
Write-Host '[4/4] 打包体积与 zip …'
$AppDir = Join-Path $Out $Name
$TotalMb = [math]::Round(((Get-ChildItem $AppDir -Recurse -File | Measure-Object Length -Sum).Sum / 1MB), 1)
$ExeKb = [math]::Round(((Get-Item (Join-Path $AppDir "$Name.exe")).Length / 1KB), 0)
Write-Host "    onedir 合计 $TotalMb MB（exe $ExeKb KB）"
Get-ChildItem (Join-Path $AppDir '_internal') -Directory |
  ForEach-Object {
    $mb = [math]::Round(((Get-ChildItem $_.FullName -Recurse -File | Measure-Object Length -Sum).Sum / 1MB), 1)
    if ($mb -ge 1) { Write-Host ("      {0,-24} {1,7} MB" -f $_.Name, $mb) }
  }

$Zip = Join-Path $Out "$Name-$Version-win64.zip"
if (Test-Path $Zip) { Remove-Item -LiteralPath $Zip }
Add-Type -AssemblyName System.IO.Compression.FileSystem
[System.IO.Compression.ZipFile]::CreateFromDirectory(
  $AppDir, $Zip, [System.IO.Compression.CompressionLevel]::Optimal, $true)
$ZipMb = [math]::Round(((Get-Item $Zip).Length / 1MB), 1)
Write-Host "`n完成："
Write-Host "  免安装目录  $AppDir"
Write-Host "  分发包      $Zip   ($ZipMb MB)"
Write-Host "`n提醒：发布前请过一遍 tmp\打包分发设计.md §8 的误报清单（签名 / VirusTotal / Defender 申诉）。"