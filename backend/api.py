from jmcomic import JmOption
from jmcomic import JmcomicText

class API:
    def __init__(self):
        self.client = JmOption.default().new_jm_client()

    def search(self, keyword: str) -> list[dict[str, str]]:
        """
        搜索本子，只输入关键词，返回一个字典的列表和封面Url"
        """
        page = self.client.search_site(search_query=keyword, page=1)
        return [
            {"id": str(album_id), "title": title, "cover_url": JmcomicText.get_album_cover_url(album_id)}
            for album_id, title in page
        ]