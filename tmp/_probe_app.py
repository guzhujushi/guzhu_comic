# -*- coding: utf-8 -*-
"""临时探针：用真实 pywebview 桥开一次首页，把推荐段 DOM 状态打印出来，然后关窗。"""
import sys, json, time, threading
sys.path.insert(0, r"D:\guzhu_comic")
import webview
from backend.api import API
from backend.config import load_config

cfg = load_config()
win_cfg = cfg["window"]
api = API()
RESULT = {}

JS_DOM = r"""
(function () {
  function q(s) { return document.querySelector(s) }
  function n(s) { return document.querySelectorAll(s).length }
  var rec = q('.rec-section');
  var panel = q('.board-panel');
  return JSON.stringify({
    readyState: document.readyState,
    apiType: typeof (window.pywebview && window.pywebview.api && window.pywebview.api.get_recommendations),
    rankType: typeof (window.pywebview && window.pywebview.api && window.pywebview.api.get_ranking),
    heroCards: n('.hero album-card'),
    hasRec: !!rec,
    recHidden: rec ? rec.hidden : null,
    recTitle: q('.rec-name') ? q('.rec-name').textContent : null,
    recCards: rec ? rec.querySelectorAll('album-card').length : 0,
    recRefreshDisabled: q('.rec-refresh') ? q('.rec-refresh').disabled : null,
    panelKids: panel ? Array.prototype.map.call(panel.children, function (c) {
      return (c.className || c.tagName) + (c.hidden ? '[hidden]' : '');
    }) : null,
    catCards: n('.cat-row album-card'),
    splashGone: !q('#splash')
  });
})()
"""

def probe(win, tag):
    try:
        RESULT[tag + "_dom"] = win.evaluate_js(JS_DOM)
    except Exception as e:
        RESULT[tag + "_dom"] = "ERR %r" % (e,)

def boot():
    try:
        win = webview.windows[0]
        # 等页面真的加载完
        for _ in range(60):
            time.sleep(0.5)
            try:
                if win.evaluate_js("document.readyState") == "complete":
                    break
            except Exception:
                pass
        # 等首页自己铺完（闪屏 2~3s + 各段请求）
        time.sleep(7)
        probe(win, "A")
        # 点一次「换一批」：看重复请求能不能把这段救回来
        try:
            win.evaluate_js("(function(){var b=document.querySelector('.rec-refresh'); if(b){b.click(); return 'clicked'} return 'no-btn'})()")
        except Exception as e:
            RESULT["click"] = "ERR %r" % (e,)
        time.sleep(4)
        probe(win, "B")
        try:
            RESULT["direct"] = win.evaluate_js(
                "window.pywebview.api.get_recommendations('home', null, [])"
                ".then(function(p){return JSON.stringify({cold:p.cold, n:(p.items||[]).length, first:(p.items||[])[0]||null})})"
                ".catch(function(e){return 'REJECT ' + e.message})")
        except Exception as e:
            RESULT["direct"] = "ERR %r" % (e,)
        try:
            RESULT["rank"] = win.evaluate_js(
                "window.pywebview.api.get_ranking('week','all',1,'views')"
                ".then(function(p){return 'ok ' + p.length + ' first=' + (p[0]||{}).id})"
                ".catch(function(e){return 'REJECT ' + e.message})")
        except Exception as e:
            RESULT["rank"] = "ERR %r" % (e,)
    finally:
        time.sleep(0.3)
        try:
            webview.windows[0].destroy()
        except Exception as e:
            RESULT["destroy"] = "ERR %r" % (e,)

webview.create_window(
    title="probe", url=cfg["dev"]["url"], js_api=api,
    width=win_cfg["width"], height=win_cfg["height"], hidden=False,
)
try:
    webview.start(boot, debug=False)
except Exception as e:
    RESULT["start"] = "ERR %r" % (e,)
print("PROBE_RESULT=" + json.dumps(RESULT, ensure_ascii=False))
