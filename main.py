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
        transparent=glass.enabled(window_cfg),   # 页面自带透明度，底交给 DWM 的亚克力
    )

    webview.start(debug=dev_cfg["debug"], func=lambda: glass.apply(window, window_cfg))


if __name__ == "__main__":
    main()