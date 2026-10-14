"""
应用版本号 —— 更新通道比版本就靠它。

* `APP_VERSION` 是**整包（exe）**的版本，跟 `scripts/build_exe.ps1 -Version` 一个口径；
  只有重新打包 exe 时才该动它。
* `BUNDLED_WEB` 是**包内那份前端产物**的构建号。exe 里那套 dist 是打包那一刻冻结的，
  之后前端一直在往前走，所以它只是个"出厂快照"的名字：客户端拿它跟更新通道里的构建号
  比一比，就知道自己这份前端是不是旧的。空串 = 不知道（就当自己旧，让对方说了算）。

改了这里记得同步 `scripts/build_exe.ps1` 的 -Version 与 `scripts/publish_frontend.ps1` 的 manifest。
"""
APP_VERSION = "0.1.1"

# 打包进 exe 的那份 dist 的构建号（打包脚本不写就是空串）
BUNDLED_WEB = ""
