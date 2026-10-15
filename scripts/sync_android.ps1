<#
.SYNOPSIS
    把仓库里的 backend/ 与 frontend/dist 同步进 android/ 工作区（两处都是生成物，不入库）。

.DESCRIPTION
    同步目标：
      android/app/src/main/python/backend/   <- backend/         （Python 侧代码）
      android/app/src/main/assets/web/       <- frontend/dist    （WebView 加载的前端产物）
    改了后端、或重新构建了前端之后跑一次。Android Studio 构建前这两处必须已经存在。

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File scripts\sync_android.ps1
#>
[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot

$pairs = @(
    @{ From = Join-Path $root "backend";       To = Join-Path $root "android\app\src\main\python\backend" },
    @{ From = Join-Path $root "frontend\dist"; To = Join-Path $root "android\app\src\main\assets\web" }
)

function Copy-Tree {
    param([string]$From, [string]$To, [string[]]$Skip)
    if (-not (Test-Path -LiteralPath $From)) { throw "源目录不存在：$From" }
    New-Item -ItemType Directory -Force -Path $To | Out-Null
    foreach ($item in (Get-ChildItem -LiteralPath $From -Force)) {
        if ($Skip -contains $item.Name) { continue }
        Copy-Item -LiteralPath $item.FullName -Destination $To -Recurse -Force
    }
}

$report = foreach ($pair in $pairs) {
    Copy-Tree -From $pair.From -To $pair.To -Skip @("__pycache__", ".gitkeep")
    $files = @(Get-ChildItem -LiteralPath $pair.To -Recurse -File)
    [pscustomobject]@{
        Source = $pair.From.Replace($root + "\", "")
        Target = $pair.To.Replace($root + "\", "")
        Files  = $files.Count
        MB     = [math]::Round((($files | Measure-Object -Property Length -Sum).Sum) / 1MB, 2)
    }
}

$report | Format-Table -AutoSize | Out-String -Width 200 | Write-Host
Write-Host "同步完成。" -ForegroundColor Green
