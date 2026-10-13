from jmcomic import JmOption
client = JmOption.default().new_jm_client()

# 第一板斧：有哪些方法？
[m for m in dir(client) if not m.startswith('_')]

# 第二板斧：这个方法签名和说明是什么？
help(client.week_ranking)
