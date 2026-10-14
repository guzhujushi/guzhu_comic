import webview

from backend import glass
from backend.api import API
from backend.config import load_config


def main() -> None:
    config = load_config()
    window_cfg = config["window"]
    dev_cfg = config["dev"]

    api = API()

    window = webview.create_window(
        title=window_cfg["title"],
        url=dev_cfg["url"],
        js_api=api,
        width=window_cfg["width"],
        height=window_cfg["height"],
        min_size=tuple(window_cfg["min_size"]),
        # 闪屏底色：WebView 把页面画出来之前先垫这个色。不传的话默认是白，开窗那一下会闪白 ——
        # 而"闪白"发生在我们的 HTML 之前，内联闪屏救不了它。注意毛玻璃开着（transparent）时
        # pywebview 走透明分支，这个参数会被忽略（见 winforms.py），那时只能靠首帧够快。
        background_color="#07080a",
        transparent=glass.enabled(window_cfg),   # 页面自带透明度，底交给 DWM 的亚克力
    )

    webview.start(debug=dev_cfg["debug"], func=lambda: glass.apply(window, window_cfg))


if __name__ == "__main__":
    main()