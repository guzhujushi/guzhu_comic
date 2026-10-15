package cn.guzhujushi.comic

import android.annotation.SuppressLint
import android.content.Intent
import android.graphics.Color
import android.graphics.Typeface
import android.os.Bundle
import android.util.Log
import android.view.Gravity
import android.view.View
import android.view.ViewGroup.LayoutParams.MATCH_PARENT
import android.view.ViewGroup.LayoutParams.WRAP_CONTENT
import android.webkit.WebResourceRequest
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.FrameLayout
import android.widget.TextView
import androidx.activity.OnBackPressedCallback
import androidx.appcompat.app.AppCompatActivity
import com.chaquo.python.Python
import com.chaquo.python.android.AndroidPlatform
import java.io.File
import java.util.concurrent.Executors

/**
 * 壳：Activity + WebView + 返回键。
 *
 * P2 之后的启动顺序：
 *
 *     assets/web/  ──解包──▶  filesDir/dist
 *                                 │
 *                        Chaquopy Python：android_boot.start() 起本地静态服务
 *                                 │
 *                                 ▼
 *                 WebView.loadUrl("http://127.0.0.1:47753")
 *
 * 为什么不 `file://` 直接开 index.html：`<script type="module">` 要过 CORS，而 `file://` 的
 * origin 是 opaque，会被直接拒掉；而且页面与图片各一份 origin，localStorage 也留不住。
 * 桌面那份同样理由，见 `backend/server.py` 开头。
 *
 * 起不来就退回 `assets/shell_status.html`（自检页），并把异常栈原样糊在屏幕上 —— 手机上没有
 * 控制台，出错时屏幕上那几行就是唯一的现场（日志另有一份在 filesDir/logs/app.log）。
 */
class MainActivity : AppCompatActivity() {

    private lateinit var webView: WebView
    private lateinit var statusView: TextView
    private val worker = Executors.newSingleThreadExecutor()

    @SuppressLint("SetJavaScriptEnabled")
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        if (BuildConfig.DEBUG) {
            WebView.setWebContentsDebuggingEnabled(true)
        }

        webView = WebView(this).apply {
            // 页面画出来之前先垫底色，免得启动那一下闪白（跟桌面的 background_color 一个意思）
            setBackgroundColor(Color.parseColor("#07080a"))
            settings.javaScriptEnabled = true
            settings.domStorageEnabled = true
            settings.allowFileAccess = false
            settings.allowContentAccess = false
            settings.setSupportZoom(false)
            settings.mediaPlaybackRequiresUserGesture = false
            webViewClient = LocalOnlyClient()
        }

        statusView = TextView(this).apply {
            setBackgroundColor(Color.parseColor("#E616171C"))
            setTextColor(Color.parseColor("#E7E9EE"))
            setTypeface(Typeface.MONOSPACE)
            textSize = 11f
            setPadding(28, 28, 28, 28)
            text = "正在启动 Python…"
        }

        setContentView(
            FrameLayout(this).apply {
                addView(webView, FrameLayout.LayoutParams(MATCH_PARENT, MATCH_PARENT))
                addView(
                    statusView,
                    FrameLayout.LayoutParams(MATCH_PARENT, WRAP_CONTENT, Gravity.BOTTOM),
                )
            },
        )

        onBackPressedDispatcher.addCallback(
            this,
            object : OnBackPressedCallback(true) {
                override fun handleOnBackPressed() {
                    if (webView.canGoBack()) {
                        webView.goBack()
                    } else {
                        isEnabled = false
                        onBackPressedDispatcher.onBackPressed()
                    }
                }
            },
        )

        // 先把自检页放上去：Python 起不来的话，屏幕上至少不是一片黑
        webView.loadUrl(SHELL_PAGE)

        try {
            Python.start(AndroidPlatform(applicationContext))
        } catch (t: Throwable) {
            fail(t)
            return
        }
        worker.execute { boot() }
    }

    private fun boot() {
        try {
            val dist = File(filesDir, "dist")
            say("解包前端资源 → ${dist.absolutePath}")
            // 整块重解：上一次装的那份可能被改过 / 删过；热更覆盖层在 filesDir/web，不在这儿
            dist.deleteRecursively()
            extractAssets("web", dist)

            say("起本地静态服务…")
            val url = Python.getInstance()
                .getModule("android_boot")
                .callAttr("start", filesDir.absolutePath, dist.absolutePath)
                .toString()
            say("服务已起：$url")

            runOnUiThread {
                statusView.visibility = View.GONE
                webView.loadUrl(url)
            }
            Log.i(TAG, "页面已切到 $url")
        } catch (t: Throwable) {
            fail(t)
        }
    }

    /**
     * 把 APK 里的 `assets/<path>` 递归解到 target。
     *
     * `assets.list()` 对文件返回空数组（个别机型会抛），两种情况都当"这个是文件"处理 ——
     * 我们这边没有空目录，所以不会误判。
     */
    private fun extractAssets(path: String, target: File) {
        val children = try {
            assets.list(path)
        } catch (t: Throwable) {
            Log.w(TAG, "list($path) 失败，当文件处理", t)
            null
        }
        if (children.isNullOrEmpty()) {
            target.parentFile?.mkdirs()
            assets.open(path).use { input -> target.outputStream().use { input.copyTo(it) } }
            return
        }
        target.mkdirs()
        for (child in children) {
            extractAssets("$path/$child", File(target, child))
        }
    }

    private fun say(msg: String) {
        Log.i(TAG, msg)
        runOnUiThread { statusView.text = msg }
    }

    private fun fail(t: Throwable) {
        Log.e(TAG, "启动失败", t)
        val text = Log.getStackTraceString(t)
        runOnUiThread {
            statusView.text = "启动失败（已退回自检页）：\n\n$text"
            statusView.visibility = View.VISIBLE
        }
    }

    /** `127.0.0.1` 的留在 WebView 里（那是我们自己起的前端与图片）；其余外链交给系统浏览器 */
    private inner class LocalOnlyClient : WebViewClient() {
        override fun shouldOverrideUrlLoading(view: WebView, request: WebResourceRequest): Boolean {
            val host = request.url.host ?: return false
            if (host == "127.0.0.1" || host == "localhost" || host == "::1") return false
            return try {
                startActivity(Intent(Intent.ACTION_VIEW, request.url))
                true
            } catch (t: Throwable) {
                Log.w(TAG, "外链打不开：${request.url}", t)
                true
            }
        }
    }

    override fun onDestroy() {
        worker.shutdownNow()
        super.onDestroy()
    }

    private companion object {
        const val TAG = "GuzhuShell"
        const val SHELL_PAGE = "file:///android_asset/shell_status.html"
    }
}