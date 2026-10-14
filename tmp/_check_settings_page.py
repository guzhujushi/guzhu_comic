# -*- coding: utf-8 -*-
"""设置页冒烟：表单由后端那张表生成、四块新东西（更新 / 磁盘 / 数据 / 桌面）都挂得上。

不测后端逻辑（那是 _check_backend_apis.py 的事），只测"页面铺得出来、按钮接到人"——
`settings.ts` 里全是 `querySelector(...)!`，选择器写错一个就是开页即崩，tsc 查不出来。
"""
import http.server, os, shutil, socket, subprocess, tempfile, threading, urllib.parse

REPO = r"D:\guzhu_comic"
CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"

STUB = """
var EXPORTS = [];
var SPEC = { sections: [
  { key: 'reader', label: '阅读', fields: [
    { key: 'restore_progress', label: '记住进度', kind: 'bool' },
    { key: 'mode', label: '模式', kind: 'enum', options: ['webtoon', 'single'] },
    { key: 'width', label: '宽度', kind: 'int', min: 0, max: 4000, restart: true }
  ] },
  { key: 'desktop', label: '桌面集成', fields: [
    { key: 'tray', label: '托盘', kind: 'bool', hint: '右下角一个图标' }
  ] }
] };
var CACHED = [
  { photo_id: '9001', album_id: '101', album_title: '离线测试', index: '1', title: '第 1 话',
    state: 'done', images: 20, total: 20, bytes: 1048576, offline: true, mtime: 2 },
  { photo_id: '7001', album_id: '', album_title: '', index: '', title: '',
    state: 'cached', images: 3, total: 0, bytes: 4096, offline: false, mtime: 1 }
];
var stub = {
  get_settings: function () { return Promise.resolve({
    reader: { restore_progress: true, mode: 'single', width: 900 },
    desktop: { tray: false }
  }); },
  get_settings_spec: function () { return Promise.resolve(SPEC); },
  get_cache_stats: function () { return Promise.resolve({ used_mb: 12, limit_mb: 2048, interval: 600, chapters: 3 }); },
  get_disk_usage: function () { return Promise.resolve({ cache_mb: 12, cache_limit_mb: 2048, download_mb: 30,
    data_mb: 1, free_mb: 51200, total_mb: 102400, download_dir: 'X:\\\\d', chapters: 30, offline_chapters: 28 }); },
  get_version: function () { return Promise.resolve({ app: '0.1.0', web: '', built_in: '', frozen: false,
    overlay: false, dist: 'X:\\\\dist', update: { enabled: true, url: 'https://x/web', auto: true } }); },
  get_desktop_state: function () { return Promise.resolve({ platform: 'win32', notify: true, tray: true,
    tray_live: true, autostart: false, hotkeys: true, hotkeys_live: false, hotkey_toggle: 'Ctrl+Alt+G' }); },
  check_update: function () { return Promise.resolve({ error: '还没发布', available: false }); },
  list_cached_chapters: function () { return Promise.resolve(CACHED); },
  export_data: function (kind) { EXPORTS.push(kind); return Promise.resolve({ ok: true, cancelled: false,
    kind: kind, path: 'X:\\\\a.json', count: 3, bytes: 99 }); },
  open_folder: function (kind) { return Promise.resolve({ opened: true, path: 'X:\\\\' + kind }); },
  get_log_tail: function () { return Promise.resolve({ path: 'X:\\\\app.log', lines: ['a', 'b'], truncated: false, error: '' }); },
  clear_cache: function () { return Promise.resolve({ meta_rows: 0, cache_files: 0 }); },
  cleanup_cache: function () { return Promise.resolve({ used_mb: 0, removed_chapters: 0, freed_mb: 0 }); },
  save_settings: function (s) { return Promise.resolve(s); },
  __exports: function () { return EXPORTS.join(','); }
};
window.pywebview = { api: new Proxy(stub, { get: function (t, k) {
  if (k === 'then') return undefined;
  if (k in t) return t[k];
  return function () { return Promise.resolve(null); };
} }) };
"""

PROBE = """
window.__err = '';
window.addEventListener('error', function (e) { window.__err += (e && e.message ? e.message : 'err') + ';'; });
setTimeout(function () {
  function note(text) {
    try { fetch('/report?d=' + encodeURIComponent(text)); } catch (e) {}
  }
  function click(sel) {
    var el = document.querySelector(sel);
    if (!el) throw new Error('找不到 ' + sel);
    el.click();
  }
  var steps = [
    function () { location.hash = '#/settings'; },
    function () {
      note('fieldsets=' + document.querySelectorAll('.settings-form fieldset').length);
      note('inputs=' + document.querySelectorAll('.settings-form [data-path]').length);
      note('select=' + document.querySelectorAll('.settings-form select[data-path]').length);
      note('restartTag=' + document.querySelectorAll('.settings-form .restart-tag').length);
      var v = document.querySelector('.version-line');
      note('versionLine=' + (v ? v.textContent.replace(/\\s+/g, ' ').trim() : 'missing'));
      var d = document.querySelector('.disk-line');
      note('diskLine=' + (d ? d.textContent.replace(/\\s+/g, ' ').trim() : 'missing'));
      var k = document.querySelector('.desktop-line');
      note('desktopLine=' + (k ? k.textContent.replace(/\\s+/g, ' ').trim() : 'missing'));
      note('hasDiskDetail=' + !!document.querySelector('.disk-detail'));
    },
    function () {
      var det = document.querySelector('.disk-detail');
      if (det) det.open = true;      // 摊开：明细这时候才去拉
    },
    function () {
      note('diskRows=' + document.querySelectorAll('.disk-row').length);
      note('diskTags=' + [].map.call(document.querySelectorAll('.disk-tag'), function (t) { return t.textContent; }).join('|'));
      note('clickable=' + document.querySelectorAll('.disk-row.clickable').length);
    },
    function () { click('[data-export="favorites"]'); },
    function () {
      note('exports=' + window.pywebview.api.__exports());
      var s = document.querySelector('.data-status');
      note('dataStatus=' + (s ? s.textContent.replace(/\\s+/g, ' ').trim() : 'missing'));
    },
    function () { click('.desktop-reload-btn'); },
    function () {
      note('err=' + window.__err);
      note('DONE=1');
    }
  ];
  var i = 0;
  (function tick() {
    if (i >= steps.length) return;
    var step = steps[i];
    i += 1;
    setTimeout(function () {
      try { step(); } catch (e) { note('ERR=' + (e && e.message ? e.message : e)); }
      tick();
    }, 900);
  })();
}, 2600);
"""


def free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


class Handler(http.server.SimpleHTTPRequestHandler):
    reports = []

    def do_GET(self):                       # noqa: N802
        if self.path.startswith("/report?"):
            query = urllib.parse.urlparse(self.path).query
            Handler.reports.append(urllib.parse.parse_qs(query).get("d", [""])[0])
            self.send_response(204)
            self.end_headers()
            return
        super().do_GET()

    def log_message(self, *args):
        pass


def main():
    Handler.reports = []
    tmp = os.path.join(tempfile.gettempdir(), "gz_settings_page")
    shutil.rmtree(tmp, ignore_errors=True)
    shutil.copytree(os.path.join(REPO, "frontend", "dist"), tmp)
    open(os.path.join(tmp, "stub.js"), "w", encoding="utf-8", newline="\n").write(STUB)
    open(os.path.join(tmp, "probe.js"), "w", encoding="utf-8", newline="\n").write(PROBE)
    idx = os.path.join(tmp, "index.html")
    base = open(idx, encoding="utf-8").read().replace(
        "</head>", '<script src="/stub.js"></script></head>', 1)
    open(idx, "w", encoding="utf-8", newline="").write(
        base.replace("</body>", '<script src="/probe.js"></script></body>', 1))

    port = free_port()
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", port), Handler)
    httpd.directory = tmp
    os.chdir(tmp)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()

    profile = os.path.join(tempfile.gettempdir(), "gz_settings_page_chrome")
    shutil.rmtree(profile, ignore_errors=True)
    try:
        subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars",
                        "--user-data-dir=" + profile, "--window-size=1200,900",
                        "--virtual-time-budget=25000",
                        "http://127.0.0.1:%d/#/popular" % port],
                       capture_output=True, timeout=300)
    finally:
        httpd.shutdown()
        shutil.rmtree(profile, ignore_errors=True)

    fields = {}
    for report in Handler.reports:
        if "=" in report:
            k, v = report.split("=", 1)
            fields[k] = v
    print("回报 %d 条:" % len(fields), "|".join("%s=%s" % kv for kv in fields.items()))
    shutil.rmtree(tmp, ignore_errors=True)

    if "DONE" not in fields:
        print("FAIL 探针没跑完（上面那条就是走到哪儿）")
        return 1
    expect = [
        ("表单按表生成：两段", fields.get("fieldsets") == "2"),
        ("四个控件都造出来了（三个输入框 + 一个下拉）", fields.get("inputs") == "4"),
        ("enum 造的是下拉框", fields.get("select") == "1"),
        ("标了重启生效的挂上了角标", fields.get("restartTag") == "1"),
        ("版本行写着安装包与前端", (fields.get("versionLine") or "").find("安装包 0.1.0") >= 0),
        ("磁盘行有离线下载与剩余空间", (fields.get("diskLine") or "").find("这块盘还剩") >= 0),
        ("桌面状态行按实际状态写", (fields.get("desktopLine") or "").find("托盘 已就绪") >= 0),
        ("快捷键没注册上据实说", (fields.get("desktopLine") or "").find("没注册上") >= 0),
        ("磁盘明细默认不拉", fields.get("hasDiskDetail") == "true"),
        ("摊开后铺了两话", fields.get("diskRows") == "2"),
        ("离线副本 / 缓存 两种标签都在", fields.get("diskTags") == "离线副本|缓存"),
        ("只有知道是哪本的才可点", fields.get("clickable") == "1"),
        ("导出按钮真的调了 export_data(favorites)", fields.get("exports") == "favorites"),
        ("导出结果写回数据状态那一行", (fields.get("dataStatus") or "").find("已导出 3 条") >= 0),
        ("全程没有脚本报错", fields.get("err") == ""),
    ]
    bad = 0
    for label, ok in expect:
        print("%s %s" % ("PASS" if ok else "FAIL", label))
        if not ok:
            bad += 1
    print("ALL PASS" if bad == 0 else "挂了 %d 条" % bad)
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
