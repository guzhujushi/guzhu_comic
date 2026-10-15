plugins {
    id("com.android.application")
    id("com.chaquo.python")
}

// 仓库根（android/ 的上一层）：backend/ 与 frontend/dist 都从这儿同步过来
val repoRoot = rootProject.projectDir.parentFile
// Chaquopy 要求构建机 Python 与 app 同 minor（3.13）；没配时退回仓库 .venv（3.14，会直接报错提醒）
val buildPythonPath = providers.gradleProperty("guzhu.buildPython").orNull
    ?: File(repoRoot, ".venv/Scripts/python.exe").absolutePath

// ── 发布签名（release APK）──────────────────────────────────────────────────────
// 密钥**不进仓库**：路径与口令都从用户环境变量读（2026-10-15 建好并写进用户变量；
// 怎么生成 / 怎么备份见 android/README.md）：
//   GUZHU_KS_PATH   密钥库文件的绝对路径
//   GUZHU_KS_PASS   口令（PKCS12 下 key 口令必须与它一致）
//   GUZHU_KS_ALIAS  别名，缺省 guzhu
// 没配齐 = 不建这个签名配置：`:app:assemble*Release` 照样能跑，出的是**未签名**包（装不上）。
val ksPath = System.getenv("GUZHU_KS_PATH")
val ksPass = System.getenv("GUZHU_KS_PASS")
val ksAlias = System.getenv("GUZHU_KS_ALIAS") ?: "guzhu"
val hasReleaseKey = !ksPath.isNullOrBlank() && !ksPass.isNullOrBlank() && File(ksPath).isFile

android {
    namespace = "cn.guzhujushi.comic"
    compileSdk = 37

    defaultConfig {
        applicationId = "cn.guzhujushi.comic"
        minSdk = 26
        targetSdk = 36
        // 必须与 backend/version.py 的 APP_VERSION 同步：热更的 app_min 比的就是它
        versionCode = 1
        versionName = "0.1.1"
    }

    // ── 两条变体线（来龙去脉见 tmp/安卓端技术栈与现状.md §1）────────────────────────
    //   full —— arm64-v8a 真机。带 curl_cffi（图源的 TLS 指纹就在它里面）。
    //   ui   —— x86_64 模拟器。**故意不带 curl_cffi**：它在 PyPI 上只有 android_24_arm64_v8a
    //           轮子，没有任何 x86_64 安卓轮子，x86_64 构建在 pip 阶段就过不去。
    //           代价是这条路验不了图源连通（T1/T1-b/T2）；
    //           换来的是：不用买任何安卓设备，就能把壳 / 路由 / 触屏布局 / 长图渲染 /
    //           内存那一层（P2 / P3 与 T3~T7 的大半）在模拟器上跑起来。
    flavorDimensions += "engine"
    productFlavors {
        create("full") {
            dimension = "engine"
            ndk { abiFilters += listOf("arm64-v8a") }
        }
        create("ui") {
            dimension = "engine"
            // 加后缀：两条变体能同时装在一台设备上，互不覆盖
            applicationIdSuffix = ".ui"
            versionNameSuffix = "-ui"
            ndk { abiFilters += listOf("x86_64") }
        }
    }

    buildFeatures {
        buildConfig = true
    }

    signingConfigs {
        if (hasReleaseKey) {
            create("release") {
                storeFile = File(ksPath!!)
                storePassword = ksPass
                keyAlias = ksAlias
                keyPassword = ksPass
            }
        }
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            proguardFiles(getDefaultProguardFile("proguard-android-optimize.txt"), "proguard-rules.pro")
            // 没配密钥就不挂签名配置（AGP 会出未签名包，而不是拿空字段报错）
            if (hasReleaseKey) signingConfig = signingConfigs.getByName("release")
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
}


chaquopy {
    defaultConfig {
        // Python 3.13：Chaquopy 仓库的安卓原生轮子只到 cp313（pillow / pycryptodome / pyyaml / cffi）
        version = "3.13"
        buildPython(buildPythonPath)

        // 两条变体都要的「原生依赖包」。chaquopy-xxx 是 Chaquopy 把「某个轮子依赖的 C 库」
        // 单独发的 pip 包，装进来它的 .so 才会被放进 APK 的 lib/<abi>/：
        //   chaquopy-libffi   -> libffi.so            cffi 的 _cffi_backend.so 要它
        //   chaquopy-libjpeg  -> libjpeg_chaquopy.so  PIL/_imaging.so 要它
        //   chaquopy-freetype -> libfreetype.so       PIL/_imagingft.so 要它
        // ⚠️ 平时这几个是 pip 顺着 `Requires-Dist: chaquopy-libffi` 自己装的，而下面为了绕开
        //    `cffi>=2.0.0` 用了 `--no-deps` —— 自动依赖一并没了，所以必须在这儿显式点名。
        //    （2026-10-15 实测教训：不点名的后果是构建照常成功、装到设备上 import 才 dlopen 失败）
        pip {
            install("chaquopy-libffi==3.3")
            install("chaquopy-libjpeg==1.5.3")
            install("chaquopy-freetype==2.9.1")
            install("pycparser")            // cffi 的纯 Python 依赖，同样被 --no-deps 甩掉了
        }
    }

    // pip 列表**按变体分别写**（默认配置里不放，免得 ui 变体被默认值带进 curl_cffi）。
    // 两边都用 `--no-deps` + 显式锁版本：curl_cffi 0.15+ 声明 `cffi>=2.0.0`，
    // 而安卓上不存在 cffi 2.x 的轮子，只能硬压 cffi==1.17.1。
    productFlavors {
        getByName("full") {
            pip {
                options("--no-deps")
                install("cffi==1.17.1")
                install("certifi")
                install("curl-cffi==0.16.3")
                install("pillow==11.0.0")
                install("pycryptodome==3.21.0")
                install("pyyaml==6.0.3")
                install("jmcomic==2.7.9")
                install("commonx==0.6.40")
            }
        }
        getByName("ui") {
            // 除 curl-cffi 之外与 full 完全一致。缺的那个由 src/ui/python/curl_cffi/ 里的桩顶上，
            // 否则 jmcomic 在 import 期就 ModuleNotFoundError。
            pip {
                options("--no-deps")
                install("cffi==1.17.1")
                install("certifi")
                install("pillow==11.0.0")
                install("pycryptodome==3.21.0")
                install("pyyaml==6.0.3")
                install("jmcomic==2.7.9")
                install("commonx==0.6.40")
            }
        }
    }
}

dependencies {
    implementation("androidx.core:core-ktx:1.19.1")
    implementation("androidx.appcompat:appcompat:1.8.0")
    implementation("androidx.webkit:webkit:1.17.1")
}
