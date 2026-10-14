<#
.SYNOPSIS
  发布一版**前端**（热更新包）：打 zip + 算 sha256 + 写 manifest.json。

.DESCRIPTION
  客户端（backend/updater.py）只认两样东西：

    * manifest.json —— web（构建号）、version、file、sha256、size…
    * 那个 zip —— 解开来就是 frontend/dist 的内容（index.html + assets/…）

  发布流程（不需要 token，也不需要科学上网）：

    1) 跑这个脚本，产物落在 web_dist_out\
    2) 把 manifest.json 与那个 zip 传到 code.guzhujushi.cn 上仓库的 web\ 目录：
       加 -Push 就自动做（克隆缓存在 web_dist_out\_channel，走 ssh，不需要 token），
       或者自己拖拽上传 / git push
    3) 客户端「设置 → 更新 → 检查更新」就能看到新版；装完刷新页面即生效

  构建号（web）= <日期>-<git 短 sha>（工作区有未提交改动就带 -dirty）。
  客户端就是按"构建号跟我这份不一样"判断有没有新版的，所以**别手改它**。

  用法：
    powershell -ExecutionPolicy Bypass -File scripts\publish_frontend.ps1
    powershell -ExecutionPolicy Bypass -File scripts\publish_frontend.ps1 -SkipBuild
    powershell -ExecutionPolicy Bypass -File scripts\publish_frontend.ps1 -Version 0.1.1 -Notes "修了返回丢页码"
    powershell -ExecutionPolicy Bypass -File scripts\publish_frontend.ps1 -Push          # 顺手推到更新通道仓库
#>
param(
  [switch]$SkipBuild,
  [string]$Version = '',
  [string]$Notes = '',
  [string]$AppMin = '',
  [string]$OutDir = '',
  [switch]$Push,                                              # 打完包顺手推到更新通道仓库
  [string]$RepoUrl = 'git@code.guzhujushi.cn:guzhujushi/guzhu_comic.git',
  [string]$ChannelDir = ''                                    # 通道仓库的本地克隆（默认 web_dist_out\_channel）
)
$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$Frontend = Join-Path $Root 'frontend'
$Dist = Join-Path $Frontend 'dist'
$Target = if ($OutDir) { $OutDir } else { Join-Path $Root 'web_dist_out' }
$VersionPy = Join-Path $Root 'backend\version.py'

if (-not $SkipBuild) {
  Write-Host '[1/4] 构建前端 …'
  Push-Location $Frontend
  try {
    & npm run build
    if ($LASTEXITCODE -ne 0) { throw '前端构建失败（npm run build = tsc && vite build）' }
  } finally { Pop-Location }
} else {
  Write-Host '[1/4] 跳过构建（用现成的 frontend\dist）'
}
if (-not (Test-Path (Join-Path $Dist 'index.html'))) { throw "没有 $Dist\index.html" }

# 构建号：日期 + git 短 sha（+ dirty）。客户端拿它跟自己那份比。
$Sha = 'nogit'
try { $Sha = (& git rev-parse --short HEAD 2>$null) -join '' } catch { }
if (-not $Sha) { $Sha = 'nogit' }
$Dirty = ''
$Status = (& git status --porcelain 2>$null) -join ''
if ($Status) { $Dirty = '-dirty' }
$Build = (Get-Date -Format 'yyyyMMdd-HHmm') + "-$Sha$Dirty"

# 版本号：默认跟 backend\version.py 的 APP_VERSION 一样（前端版本只给人看，判断新旧靠构建号）
if (-not $Version) {
  $match = Select-String -Path $VersionPy -Pattern '^APP_VERSION\s*=\s*"([^"]+)"'
  if (-not $match) { throw "读不到 backend\version.py 里的 APP_VERSION" }
  $Version = $match.Matches[0].Groups[1].Value
}
# app_min：这一版前端至少要哪个安装包。默认就是当前源码的版本（开发时正好对得上）
if (-not $AppMin) { $AppMin = $Version }

Write-Host "[2/4] 打包 zip（构建号 $Build，版本 $Version）…"
New-Item -ItemType Directory -Force -Path $Target | Out-Null
$ZipName = "frontend-dist-$Build.zip"
$Zip = Join-Path $Target $ZipName
if (Test-Path $Zip) { Remove-Item -LiteralPath $Zip }
Add-Type -AssemblyName System.IO.Compression.FileSystem
# includeBaseDirectory = $false：zip 根下直接是 index.html 与 assets\（updater 就是这么找的）
[System.IO.Compression.ZipFile]::CreateFromDirectory(
  $Dist, $Zip, [System.IO.Compression.CompressionLevel]::Optimal, $false)

Write-Host '[3/4] 算 sha256 与体积 …'
$Hash = (Get-FileHash -LiteralPath $Zip -Algorithm SHA256).Hash.ToLower()
$Size = (Get-Item -LiteralPath $Zip).Length

$Manifest = [ordered]@{
  version      = $Version
  web          = $Build
  app_min      = $AppMin
  notes        = $Notes
  published_at = [int][double]::Parse((Get-Date -UFormat %s))
  file         = $ZipName
  size         = $Size
  sha256       = $Hash
}
$ManifestPath = Join-Path $Target 'manifest.json'
# UTF-8 无 BOM：updater 用 utf-8 直接读，带 BOM 的话 json.loads 会当场报错
$Json = ($Manifest | ConvertTo-Json -Depth 4)
[System.IO.File]::WriteAllText($ManifestPath, $Json, (New-Object System.Text.UTF8Encoding($false)))

# 客户端读的那个 https 地址（从 ssh 地址推出来，只为了把提示打对）
$RawBase = $RepoUrl
if ($RawBase -match '^(?:ssh://)?git@([^:/]+)(?::\d+)?[/:](.+?)(?:\.git)?$') {
  $RawBase = "https://$($Matches[1])/$($Matches[2])/raw/branch/main/web"
}

Write-Host "  manifest: web=$Build version=$Version size=$([math]::Round($Size/1KB,1)) KB"
Write-Host "  sha256  : $Hash"
Write-Host ''
Write-Host "  客户端读的是 $RawBase/manifest.json"

if (-not $Push) {
  Write-Host ''
  Write-Host '[4/4] 好了。把下面两个文件传到上面那个目录里（或者加 -Push 让脚本自己推）：'
  Write-Host "    $ManifestPath"
  Write-Host "    $Zip"
  exit 0
}

# ---- 推送：产物放进更新通道仓库的 web\ 目录 → commit → push（走 ssh，不需要 token） ----
$Channel = if ($ChannelDir) { $ChannelDir } else { Join-Path $Target '_channel' }
Write-Host ''
Write-Host "[5/5] 推到更新通道仓库 $RepoUrl"
if (-not (Test-Path (Join-Path $Channel '.git'))) {
  if (Test-Path $Channel) { throw "$Channel 在这儿但不是个 git 仓库 —— 先自己看一眼（脚本不做递归删除）" }
  & git clone $RepoUrl $Channel
  if ($LASTEXITCODE -ne 0) {
    throw "clone 失败：$RepoUrl（仓库建了吗？公开的吗？这台机器 ssh 到 code.guzhujushi.cn 通吗？）"
  }
} else {
  & git -C $Channel pull --ff-only
  if ($LASTEXITCODE -ne 0) { Write-Host '  ！pull 没成功（本地分叉或没网），按现状继续' }
}
# 空仓库 clone 出来没有分支，统一按 main 走（Gitea 那边默认分支就是 main）
$Branch = ((& git -C $Channel rev-parse --abbrev-ref HEAD) -join '').Trim()
if ($Branch -ne 'main') { & git -C $Channel checkout -B main | Out-Null }

$Web = Join-Path $Channel 'web'
New-Item -ItemType Directory -Force -Path $Web | Out-Null
Copy-Item -LiteralPath $ManifestPath -Destination (Join-Path $Web 'manifest.json') -Force
Copy-Item -LiteralPath $Zip -Destination (Join-Path $Web $ZipName) -Force
& git -C $Channel add -A
$Pending = ((& git -C $Channel status --porcelain) -join '').Trim()
if ($Pending) {
  & git -C $Channel commit -m "前端热更：$Build（$Version）"
  if ($LASTEXITCODE -ne 0) { throw 'commit 失败（更新通道仓库里的 git 身份没配？）' }
} else {
  Write-Host '  （产物与仓库里那份一样，没有要提交的）'
}
& git -C $Channel push origin main
if ($LASTEXITCODE -ne 0) { throw 'push 失败' }
Write-Host ''
Write-Host "  推完了。客户端下次开窗就会看到 $Build"
Write-Host '  想立刻验一遍发布端： .venv\Scripts\python.exe tmp\_check_publish_real.py'
