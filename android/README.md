# android/ — 安卓壳工作区

Gradle 工程，用 Android Studio **单独打开这一层**。设计文档在仓库的 `tmp/`：

- `tmp/安卓端技术栈调研.md` —— 选型与理由（§0 逐层选型、§3 已核实证据、§5 环境三层与设备要求）
- `tmp/安卓版可行性评估.md` —— 难点 D1~D10、要改的地方、待实测 T1~T8（T1 是总闸）
- `tmp/安卓真机连接与调试操作手册.md` —— PC / 手机要准备什么、怎么连线、怎么验机、怎么排障

## 目录

| 路径 | 是什么 | 入库 |
|---|---|---|
| `app/src/main/java/cn/guzhujushi/comic/MainActivity.kt` | 壳：Activity + WebView + 返回键 | 是 |
| `app/src/main/assets/shell_status.html` | 壳自检页（P2 接线前先看这一页） | 是 |
| `app/src/main/python/backend/` | 仓库根 `backend/` 的同步副本 | **否**（.gitignore） |
| `app/src/main/assets/web/` | 仓库 `frontend/dist` 的同步副本 | **否**（.gitignore） |
| `gradle/wrapper/` | Gradle **9.8.1** wrapper（jar / `gradlew` / `gradlew.bat` 取自 gradle/gradle **v9.8.1**） | 是 |

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
- 跑 Gradle 的 JDK：本机 Android Studio（`D:\Andriod Studio`）自带 **JBR 25.0.3**、系统 JDK 是 **26.0.1**；Java 25 要求 **Gradle ≥ 9.1**、AGP 9.4 又要求 **Gradle ≥ 9.6** → 版本线只能落在 AGP 9.4.0 / Gradle 9.8.1（见 `tmp/安卓端技术栈调研.md` §1.5）
- **开工前先把 Python 3.13 装上**，并在 `gradle.properties` 里把 `guzhu.buildPython` 指向它，否则 Chaquopy 的 pip 阶段会以 `from versions: none` 失败

## 当前进度（2026-10-15）

- **`:app:assembleDebug` → BUILD SUCCESSFUL**，产出 `app/build/outputs/apk/debug/app-debug.apk` = **35.71 MB**（`curl_cffi` / `cffi` / `pillow` / `pycryptodome` / `pyyaml` / `jmcomic` / `commonx` 全部打包在内）。
- 构建入口：**`scripts\build_android.ps1`**（仓库根，把 `JAVA_HOME` 指到 AS 自带的 JBR 25 再跑 `gradlew`）：

  ```powershell
  powershell -ExecutionPolicy Bypass -File scripts\build_android.ps1
  powershell -ExecutionPolicy Bypass -File scripts\build_android.ps1 :app:assembleDebug --stacktrace
  ```

- 修过的三处：① Kotlin 插件与 AGP 9 内置的冲突（已摘插件）；② 构建机 Python 3.14 → **3.13**（轮子只到 cp313）；③ `compileSdk` **36 → 37**（`androidx.core 1.19.1` 要求 ≥37；`targetSdk` 仍 36）。
- **还没做的**：装到真机/模拟器上跑（**手上没有能装 APK 的设备** —— Mate 80 Pro 是 HarmonyOS 6、无 ADB 端点；另一台是 iPhone）。见 `tmp/安卓端技术栈调研.md` §5.3 / §5.7。

## 还没做的（按设计文档的路线）

- **P0**：`server.py` 加 `POST /api/<method>` + 随机 token，前端加桥垫片（桌面一起切）
- **P2**：Activity 起 Python → 起静态服务 → WebView 加载 `http://127.0.0.1:47753`（替换现在的自检页）
- **P3**：`dataSync` 前台服务 + SAF + `StatFs`（`shutil.disk_usage` 在安卓上读的是 root 分区）

`local.properties`（`sdk.dir`）由 Android Studio 首次打开时自己生成，不在仓库里。
