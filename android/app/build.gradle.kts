
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

        // curl_cffi 只发 android_24_arm64_v8a 轮子，x86_64 连 pip 阶段都过不去
        ndk {
            abiFilters += listOf("arm64-v8a")
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
        // Python 3.13：Chaquopy 仓库的安卓原生轮子只到 cp313（pillow/pycryptodome/pyyaml/cffi 都没有 cp314）
        version = "3.13"
        buildPython(buildPythonPath)
        // Chaquopy 17 起 pip 只装 wheel。--no-deps 是必需的：curl-cffi 要求 cffi>=2.0.0，
        // 而安卓上根本没有 cffi 2.x 的轮子（Chaquopy 仓库最高 1.17.1，PyPI 的 cffi 无安卓轮子）
        // → 只能把依赖全部显式列出来、锁死版本（2026-10-15 用 pip --dry-run 逐个验过）
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
}

dependencies {
    implementation("androidx.core:core-ktx:1.19.1")
    implementation("androidx.appcompat:appcompat:1.8.0")
    implementation("androidx.webkit:webkit:1.17.1")
}
