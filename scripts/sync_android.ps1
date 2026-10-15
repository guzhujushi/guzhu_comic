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
    # 目标先清空：这两处都是生成物（不入库），而 Copy-Item 只覆盖同名文件 —— 不清的话
    # 上一版的前端 bundle 会一层层攒在里面（2026-10-15 实测：APK 里同时躺着 5 份 index-*.js）。
    # 后端那边同理：删掉 / 改名的模块会留个幽灵副本，最坏能被 import 到。
    if (Test-Path -LiteralPath $To) {
        $full = (Resolve-Path -LiteralPath $To).Path
        $allowed = Join-Path $root "android\app\src\main\"
        if (-not $full.StartsWith($allowed, [StringComparison]::OrdinalIgnoreCase)) {
            throw "拒绝清空（不在 $allowed 下）：$full"
        }
        Get-ChildItem -LiteralPath $full -Force | Remove-Item -Recurse -Force
    }
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
