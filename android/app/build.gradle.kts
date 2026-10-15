plugins {
    id("com.android.application")
    id("com.chaquo.python")
}

// 仓库根（android/ 的上一层）：backend/ 与 frontend/dist 都从这儿同步过来
val repoRoot = rootProject.projectDir.parentFile
// Chaquopy 要求构建机 Python 与 app 同 minor（3.13）；没配时退回仓库 .venv（3.14，会直接报错提醒）
val buildPythonPath = providers.gradleProperty("guzhu.buildPython").orNull
    ?: File(repoRoot, ".venv/Scripts/python.exe").absolutePath

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

    // ── 两条变体线（来龙去脉见 tmp/安卓端技术栈调研.md §5.3.1）────────────────────────
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

    buildTypes {
        release {
            isMinifyEnabled = false
            proguardFiles(getDefaultProguardFile("proguard-android-optimize.txt"), "proguard-rules.pro")
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
