"""
依赖探针 —— 在**真实的安卓运行时**里跑一遍「装得上 + 连得上」（T1 / T1-b / T2）。

用法（壳侧开一个开关就跑，不影响正常启动）：

    adb shell am start -n <包名>/cn.guzhujushi.comic.MainActivity --ez guzhu.probe true
    adb logcat -s GuzhuShell:* python.stdout:*

为什么要有它：`tmp/安卓端技术栈与现状.md` §5 的 T1~T2 是「能不能上安卓」的总闸，而它们**只能在
跑起来的安卓运行时里验** —— 桌面上拿同一组版本验过不算数（那边根本没有「安卓轮子」这回事）。
探针把这件事拆成逐步独立的若干步，**每步单独记成败与耗时** —— 因为卡在第 3 步（cffi 的 C ABI）
和第 5 步（图源被墙 / 域名不对）的退路完全不同，糊成一句「失败了」等于没验。

别在真机上直接跑它：第 4、5 步会真的发网络请求（各 30 秒超时）。
"""
import time

TAG = "[probe]"


def run() -> str:
    """跑一遍，返回给人看的报告（同时也逐行 print 到 logcat）。"""
    lines: list[str] = []
    t_all = time.time()

    def emit(text: str) -> None:
        print(f"{TAG} {text}", flush=True)
        lines.append(text)

    def step(name: str, fn) -> None:
        emit(f"RUN  {name}")
        t0 = time.time()
        try:
            output = fn()
            emit(f" OK  {name}  ({time.time() - t0:.1f}s)  {output}")
        except BaseException as exc:                      # noqa: BLE001 —— 探针就该连 KeyboardInterrupt 一起兜住
            emit(f"FAIL {name}  ({time.time() - t0:.1f}s)  {type(exc).__name__}: {exc}")

    def platform_info() -> str:
        import platform
        return f"machine={platform.machine()} python={platform.python_version()}"

    def cffi_info() -> str:
        import _cffi_backend
        import cffi
        return f"cffi={cffi.__version__} backend={_cffi_backend.__version__}"

    def curl_cffi_info() -> str:
        import curl_cffi
        return f"curl_cffi={curl_cffi.__version__}"

    def curl_https() -> str:
        """FFI 调用 + TLS 指纹这两条路一起走一遍（走 CDN 的站点，不依赖图源可达）"""
        import curl_cffi.requests as r
        resp = r.get("https://www.baidu.com/", impersonate="chrome", timeout=30)
        return f"GET baidu.com -> {resp.status_code}, {len(resp.content)} B"

    def jmcomic_client() -> str:
        from jmcomic import JmOption
        client = JmOption.default().new_jm_client()       # 这一步会把域名、setting 都拉一遍
        return f"client={type(client).__name__}"

    state: dict = {}

    def album_detail() -> str:
        from jmcomic import JmOption
        client = state.get("client") or JmOption.default().new_jm_client()
        state["client"] = client
        album = client.get_album_detail("422866")
        state["album"] = album
        return f"album={album.title!r} 章节数={len(album.episode_list)}"

    def photo_images() -> str:
        client = state["client"]
        album = state["album"]
        # `episode_list` 每项是 (photo_id, index, title) —— 顺序与 backend/api.py 里那条
        # `for pid, pindex, pname in album.episode_list` 一致
        photo_id = str(album.episode_list[0][0])
        photo = client.get_photo_detail(photo_id, fetch_album=False)
        state["photo"] = photo
        return f"chapter={photo_id} 图数={len(photo)} 首图={photo[0].download_url[:70]!r}"

    def fetch_image() -> str:
        import curl_cffi.requests as r
        url = state["photo"][0].download_url
        resp = r.get(url, impersonate="chrome", timeout=60)
        state["img_bytes"] = resp.content
        magic = resp.content[:4]
        return (f"{resp.status_code}, {len(resp.content)} B, 文件头={magic!r}"
                f"{'（RIFF/WEBP）' if magic[:4] == b'RIFF' else ''}")

    def decode_image() -> str:
        """
        用 Pillow 解码（**已知在安卓上不绿**：Chaquopy 的 Pillow 轮子不带 libwebp，
        而图源现在发的是 .webp）。

        这条**不影响本 app**：图片是 WebView 自己渲染的（Chromium 原生支持 webp），
        离线下载走的是 jmcomic 的下载器（原样落盘，不碰 PIL），`backend/` 里也一行 PIL 都没有
        （全项目只有 jmcomic 的 long_img 插件用 PIL，而它不是默认插件）。
        真要用 PIL 做长图合并 / 切图，得自己出一个带 libwebp 的轮子。
        """
        import io
        from PIL import Image
        image = Image.open(io.BytesIO(state["img_bytes"]))
        return f"{image.size} {image.format}"

    def pillow_formats() -> str:
        from PIL import Image, features
        return (f"webp={bool(features.check('webp'))} jpeg={bool(features.check('jpg'))} "
                f"png={bool(features.check('zlib'))} 共 {len(Image.registered_extensions())} 个扩展名")

    step("1 平台", platform_info)
    step("2 cffi（ABI 那一关）", cffi_info)
    step("3 curl_cffi", curl_cffi_info)
    step("4 HTTPS + 指纹", curl_https)
    step("5 jmcomic 建客户端", jmcomic_client)
    step("6 拉一部详情", album_detail)
    step("7 取一话的图片地址", photo_images)
    def descramble_real() -> str:
        """
        用**安卓系统自带的解码器**把一张真图解扰出来（P1 的验证点）。

        为什么单列一步：图源发的整页图是打过乱的（切成 num 条横带倒着重排），而 Chaquopy
        的 Pillow 没编 webp —— 所以安卓上这步**只能**走系统解码器。产物落在缓存目录里，
        可以拉回电脑上肉眼复核条带顺序对不对。
        """
        from backend import descramble, paths
        img = state["photo"][0]
        raw = state["img_bytes"]
        num = descramble.num_for(img)
        out = paths.CACHE_DIR / "_probe_descramble.webp"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(raw)
        descramble.fix_file(out, num)
        fixed = out.read_bytes()
        same = "（内容没变，说明这张不用解扰）" if fixed == raw else ""
        return f"num={num} 原图 {len(raw)} B → 解扰后 {len(fixed)} B{same}；产物 {out}"

    step("8 下一张图（真下到字节）", fetch_image)
    step("9 Pillow 解码 + 支持格式", decode_image)
    step("10 Pillow 格式清单", pillow_formats)
    step("11 系统解码器解扰（真图）", descramble_real)

    emit(f"DONE 共 {time.time() - t_all:.1f}s")
    return "\n".join(lines)