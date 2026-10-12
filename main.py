import webview

from backend.api import API
from backend.config import load_config


def main() -> None:
    config = load_config()
    window_cfg = config["window"]
    dev_cfg = config["dev"]

    api = API()

    webview.create_window(
        title=window_cfg["title"],
        url=dev_cfg["url"],
        js_api=api,
        width=window_cfg["width"],
        height=window_cfg["height"],
        min_size=tuple(window_cfg["min_size"]),
    )

    webview.start(debug=dev_cfg["debug"])


if __name__ == "__main__":
    main()