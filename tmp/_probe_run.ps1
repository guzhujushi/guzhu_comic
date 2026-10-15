$ErrorActionPreference = "Continue"
$adb = "$env:LOCALAPPDATA\Android\Sdk\platform-tools\adb.exe"
$out = "D:\guzhu_comic\tmp\_probe_run.log"
& $adb logcat -c
& $adb shell am force-stop cn.guzhujushi.comic
Start-Sleep -Seconds 2
& $adb shell am start -n cn.guzhujushi.comic/cn.guzhujushi.comic.MainActivity --ez guzhu.probe true
Start-Sleep -Seconds 150
& $adb logcat -d -v time -s python.stdout:* GuzhuShell:* AndroidRuntime:E *:F | Out-File -FilePath $out -Encoding utf8
Write-Output ("log bytes: " + (Get-Item $out).Length)
