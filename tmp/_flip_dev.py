import io, sys
p = "D:\\guzhu_comic\\config.yaml"
raw = io.open(p, "rb").read()
on = b"use_dev_server: true"
off = b"use_dev_server: false"
mode = sys.argv[1]
if mode == "off":
    assert raw.count(on) == 1, raw.count(on)
    raw = raw.replace(on, off)
elif mode == "on":
    assert raw.count(off) == 1, raw.count(off)
    raw = raw.replace(off, on)
else:
    raise SystemExit("usage: _flip_dev.py on|off")
io.open(p, "wb").write(raw)
print("config.yaml ->", mode, len(raw), "B")