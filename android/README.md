# android/ — 安卓壳工作区

Gradle 工程，用 Android Studio **单独打开这一层**。设计文档在仓库的 `tmp/`：

- `tmp/安卓端技术栈调研.md` —— 选型与理由（§0 逐层选型、§3 已核实证据、§5 环境三层与设备要求）
- `tmp/安卓版可行性评估.md` —— 难点 D1~D10、要改的地方、待实测 T1~T8（T1 是总闸）
- `tmp/安卓真机连接与调试操作手册.md` —— PC / 手机要准备什么、怎么连线、怎么验机、怎么排障

## 目录

| 路径 | 是什么 | 入库 |
|---|---|---|
| `app/src/main/java/cn/guzhujushi/comic/MainActivity.kt` | 壳：Activity + WebView + 返回键 | 是 |
| `app/src/main/python/android_boot.py` | 安卓侧 Python 入口：接目录 → 装日志 → 起静态服务 → 回 base url | 是 |
| `app/src/ui/python/curl_cffi/` | **`ui` 变体专用的空壳**（见下「两条变体」） | 是 |
| `app/src/main/assets/shell_status.html` | 启动中 / 起不来时的自检页 | 是 |
| `app/src/main/python/backend/` | 仓库根 `backend/` 的同步副本 | **否**（.gitignore） |
| `app/src/main/assets/web/` | 仓库 `frontend/dist` 的同步副本 | **否**（.gitignore） |
| `gradle/wrapper/` | Gradle **9.8.1** wrapper（jar / `gradlew` / `gradlew.bat` 取自 gradle/gradle **v9.8.1**） | 是 |

`app/src/main/python/backend/` 与 `app/src/ui/python/curl_cffi/` 是两回事：前者是同步来的副本（不入库），
后者是**手写的桩**（入库）—— 见「两条变体」。

## 同步生成物

```powershell
powershell -ExecutionPolicy Bypass -File scripts\sync_android.ps1
```

改完后端、或重新构建前端（`npm run build`）之后各跑一次。

## 版本线（都是核对过的，别随手改）

- `minSdk 26` / `compileSdk 36` / `targetSdk 36` / 只出 `arm64-v8a`（curl_cffi 只有 arm64 轮子）
- Chaquopy 17.1.0（**CPython 3.13**；构建机解释器用**另装的 Python 3.13** —— Chaquopy 要求与 app 同 minor）
- AGP **9.4.0** + Gradle **9.8.1**；**不挂 Kotlin 插件**（AGP 9 起 Kotlin 内置，再挂 `org.jetbrains.kotlin.android` 会硬失败）
- **Python 不能用 3.14**：Chaquopy 的轮子仓库（`chaquo.com/pypi-13.1`）里 `cffi` / `pillow` / `pycryptodome` / `pyyaml` 的 arm64 轮子**只到 cp313**
- pip 段是 **`--no-deps` + 显式锁版本**：`curl_cffi` 0.15+ 全系声明 `cffi>=2.0.0`，而安卓上不存在 cffi 2.x 轮子 → 只能硬压 `cffi==1.17.1`（**C ABI 兼容性未验，这是 T1 剩下的风险**）
- `versionName` 必须与 `backend/version.py` 的 `APP_VERSION` 同步 —— 热更的 `app_min` 比的就是它
- **两条变体**（`flavorDimensions += "engine"`，两套包名能同时装在一台设备上）：
  - `full` —— `arm64-v8a` + 完整 pip 列表（含 `curl-cffi`），**回真机**、能连图源；
  - `ui` —— `x86_64` + **去掉 `curl-cffi`**，只跑模拟器：x86_64 上根本没有 `curl_cffi` 的安卓轮子，
    少了它 `jmcomic` 在 import 期就会 `ModuleNotFoundError`，所以 `src/ui/python/curl_cffi/` 里放了个
    **一调就抛错的桩**（`__version__ = "0.0.0+ui-stub"`），把 import 撑住、把「图源不可用」变成运行时明确报错。
    代价：**这个变体永远验不了 T1 / T1-b / T2（图源连通）**。
- 跑 Gradle 的 JDK：本机 Android Studio（`D:\Andriod Studio`）自带 **JBR 25.0.3**、系统 JDK 是 **26.0.1**；Java 25 要求 **Gradle ≥ 9.1**、AGP 9.4 又要求 **Gradle ≥ 9.6** → 版本线只能落在 AGP 9.4.0 / Gradle 9.8.1（见 `tmp/安卓端技术栈调研.md` §1.5）
- **开工前先把 Python 3.13 装上**，并在 `gradle.properties` 里把 `guzhu.buildPython` 指向它，否则 Chaquopy 的 pip 阶段会以 `from versions: none` 失败

## 当前进度（2026-10-15）

- **`full` 变体**：`:app:assembleFullDebug` → BUILD SUCCESSFUL，`app-full-debug.apk` = **35.71 MB**
  （`curl_cffi` / `cffi` / `pillow` / `pycryptodome` / `pyyaml` / `jmcomic` / `commonx` 全部打包在内）。
- **`ui` 变体**：`:app:assembleUiDebug` → BUILD SUCCESSFUL，`app-ui-debug.apk` = **29,004,046 B**；
  已装进 x86_64 模拟器（AVD `guzhu_x86`）跑通，**真前端在安卓 WebView 里渲染出来了**。
- 构建入口：**`scripts\build_android.ps1`**（仓库根，把 `JAVA_HOME` 指到 AS 自带的 JBR 25 再跑 `gradlew`）：

  ```powershell
  powershell -ExecutionPolicy Bypass -File scripts\build_android.ps1
  powershell -ExecutionPolicy Bypass -File scripts\build_android.ps1 :app:assembleDebug --stacktrace
  ```

- 修过的三处：① Kotlin 插件与 AGP 9 内置的冲突（已摘插件）；② 构建机 Python 3.14 → **3.13**（轮子只到 cp313）；③ `compileSdk` **36 → 37**（`androidx.core 1.19.1` 要求 ≥37；`targetSdk` 仍 36）。
- **已经能跑的那条（`ui` 变体 + 模拟器，0 元、不需要任何安卓设备）**：

  ```powershell
  powershell -ExecutionPolicy Bypass -File scripts\build_android.ps1 :app:assembleUiDebug
  $adb = "$env:LOCALAPPDATA\Android\Sdk\platform-tools\adb.exe"
  & $adb install -r android\app\build\outputs\apk\ui\debug\app-ui-debug.apk
  & $adb shell am start -n cn.guzhujushi.comic.ui/cn.guzhujushi.comic.MainActivity
  & $adb logcat -s GuzhuShell:* python.stdout:* python.stderr:*      # 启动链路
  & $adb forward tcp:47753 tcp:47753                                 # 想看设备里起的服务，从 PC 打 127.0.0.1:47753
  ```

  截图要 `cmd /c "...adb.exe exec-out screencap -p > 文件"` —— PowerShell 直接重定向会把二进制搞坏。
- **还没做的**：真机（`full` 变体，验 T1 / T1-b / T2）—— 手上两台（Mate 80 Pro = HarmonyOS 6、无 ADB 端点；另一台是 iPhone）都装不了。见 `tmp/安卓端技术栈调研.md` §5.3 / §5.7。

## 发布签名（release APK，2026-10-15 建）

密钥**不进仓库**：路径与口令都在**用户环境变量**里。

| 变量 | 值 |
|---|---|
| `GUZHU_KS_PATH` | `C:\Users\guzhu\.guzhu\keys\guzhu-release.jks` |
| `GUZHU_KS_PASS` | 32 位随机（想看：`echo $env:GUZHU_KS_PASS`） |
| `GUZHU_KS_ALIAS` | `guzhu` |

```powershell
# 出包（full = arm64-v8a 真机版）
powershell -ExecutionPolicy Bypass -File scripts\build_android.ps1 :app:assembleFullRelease
# 产物：android\app\build\outputs\apk\full\release\app-full-release.apk
# 核签名：apksigner verify --print-certs <apk>  →  CN=Guzhu Comic…，证书 SHA-256 05CD228B…
```

- **`scripts\build_android.ps1` 会主动从"用户变量"补一次这三个变量**（已经开着的终端看不到新加的变量），所以哪个窗口都能直接跑。
- 密钥是 4096 位 RSA / PKCS12 / 10000 天；证书 SHA-256 指纹 `05CD228B…`（`apksigner verify --print-certs` 核过）。
- 当初生成它的命令（万一要重做；**重做后签名就变了，同一台设备必须先卸载**）：

  ```powershell
  & "D:\Andriod Studio\jbr\bin\keytool.exe" -genkeypair -v -keystore <路径> -alias guzhu `
    -keyalg RSA -keysize 4096 -validity 10000 -storetype PKCS12 `
    -storepass <口令> -keypass <口令> `
    -dname "CN=Guzhu Comic, OU=Personal, O=Guzhu, L=Shanghai, ST=Shanghai, C=CN"
  ```
- **覆盖安装的两条规矩**：① release 与 debug 签名不同，换着装要先 `adb uninstall cn.guzhujushi.comic`；
  ② 以后每个版本都得用**同一个密钥库**签 —— 换了就得卸载重装（收藏 / 阅读记录会跟着没）。
- **备份**：密钥库文件 + 口令两样都要留一份（口令在用户变量里读得出来）。它是这个 app 唯一的"发布者身份"。
- 三个变量都没配时，`assemble*Release` 照样能跑，出的是**未签名**包（装不上），不会拿空字段报错。

## 还没做的（按设计文档的路线）

- ~~**P0**：`server.py` 加 `POST /api/<method>` + 随机 token，前端加桥垫片（桌面一起切）~~ —— **2026-10-15 已完成**（见 `tmp/STATUS.md` 的 0.5 / 0.7）
- ~~**P2**：Activity 起 Python → 起静态服务 → WebView 加载 `http://127.0.0.1:47753`~~ —— **2026-10-15 已完成并在模拟器上验收**
- **P3**：`dataSync` 前台服务 + SAF + `StatFs`（`shutil.disk_usage` 在安卓上读的是 root 分区）

`local.properties`（`sdk.dir`）由 Android Studio 首次打开时自己生成，不在仓库里。
