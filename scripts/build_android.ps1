# 安卓构建入口：把 Gradle 的 JDK 指到 Android Studio 自带的 JBR，再跑 gradlew。
#
# 为什么要这个脚本：本机系统 JDK 是 Oracle 26.0.1，Gradle 9.8.1 跑不动它；
# Android Studio 自带的 JBR 25.0.3 才行（见 tmp/现状与技术栈.md §2.2）。
#
# 用法：
#   powershell -ExecutionPolicy Bypass -File scripts\build_android.ps1
#   powershell -ExecutionPolicy Bypass -File scripts\build_android.ps1 help
#   powershell -ExecutionPolicy Bypass -File scripts\build_android.ps1 :app:assembleDebug --stacktrace
param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$Tasks
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$androidDir = Join-Path $repoRoot "android"

$jbr = "D:\Andriod Studio\jbr"
if (-not (Test-Path -LiteralPath (Join-Path $jbr "bin\java.exe"))) {
    throw "找不到 Android Studio 自带的 JBR：$jbr —— 请改成这台机器上 Android Studio 的实际路径。"
}
$env:JAVA_HOME = $jbr
$env:PATH = (Join-Path $jbr "bin") + ";" + $env:PATH

if (-not $Tasks -or $Tasks.Count -eq 0) { $Tasks = @(":app:assembleDebug") }

# 发布签名那三个变量（GUZHU_KS_PATH / GUZHU_KS_PASS / GUZHU_KS_ALIAS）在**用户变量**里配好了，
# 但**已经开着的终端**看不到它们（进程环境在启动那一刻就定了）—— 这里主动从用户变量补一次，
# 省得为了打个 release 包还得新开窗口。密钥本身不进仓库，见 android/README.md。
foreach ($n in @("GUZHU_KS_PATH", "GUZHU_KS_PASS", "GUZHU_KS_ALIAS")) {
    if (-not [Environment]::GetEnvironmentVariable($n, "Process")) {
        $v = [Environment]::GetEnvironmentVariable($n, "User")
        if ($v) { Set-Item -Path "Env:$n" -Value $v }
    }
}

Write-Host "[build_android] JAVA_HOME = $env:JAVA_HOME"
Write-Host "[build_android] tasks     = $($Tasks -join ' ')"
Write-Host "[build_android] workdir   = $androidDir"
Write-Host ""

Push-Location $androidDir
try {
    & (Join-Path $androidDir "gradlew.bat") @Tasks
    $code = $LASTEXITCODE
} finally {
    Pop-Location
}
exit $code
