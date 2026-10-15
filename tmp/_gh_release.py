# -*- coding: utf-8 -*-
"""发布 GitHub release：推 main + 打 tag + 建 release + 上传 zip。

版本号从 `backend/version.py` 的 `APP_VERSION` 取（不再写死），对应：
  * tag   `v<版本>`
  * 说明  `tmp/release-notes-v<版本>.md`
  * 资产  `build_out/GuzhuComic-<版本>-win64.zip`（要先跑 scripts/build_exe.ps1 出包）

凭据（三选一，按顺序找）：
  * 环境变量 GH_TOKEN / GITHUB_TOKEN
  * 文件 tmp/_gh_token.txt（一行，PAT 本身）
  * 兜底：git 凭据管理器里那个 GitHub 凭据（`git credential fill`，push 用的就是它）

跑法：.venv\\Scripts\\python.exe tmp\\_gh_release.py
它自己会先验身份；任何一步失败都停下说清楚，不会半途留下乱七八糟的状态。
"""
import base64
import json
import os
import pathlib
import re
import subprocess
import sys
import urllib.error
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
REPO = "guzhujushi/guzhu_comic"

VERSION = re.search(r'^APP_VERSION\s*=\s*"([^"]+)"',
                    (ROOT / "backend" / "version.py").read_text(encoding="utf-8"),
                    re.M).group(1)
TAG = "v" + VERSION
TITLE = "GuzhuComic"
NOTES = ROOT / "tmp" / ("release-notes-v%s.md" % VERSION)
ZIP = ROOT / "build_out" / ("GuzhuComic-%s-win64.zip" % VERSION)

API = "https://api.github.com"
UPLOADS = "https://uploads.github.com"


def token():
    for name in ("GH_TOKEN", "GITHUB_TOKEN"):
        value = (os.environ.get(name) or "").strip()
        if value:
            return value, name
    path = ROOT / "tmp" / "_gh_token.txt"
    if path.exists():
        return path.read_text(encoding="utf-8").strip(), str(path)
    value = credential_manager_token()
    if value:
        return value, "git 凭据管理器（github.com）"
    raise SystemExit("没有凭据：设 GH_TOKEN 环境变量，或把 PAT 写进 tmp\\_gh_token.txt")


def credential_manager_token() -> str:
    """兜底：git 在 github.com 上缓存的那个凭据（`git push` 走的就是它）"""
    try:
        p = subprocess.run(["git", "credential", "fill"],
                           input="protocol=https\nhost=github.com\n\n",
                           capture_output=True, text=True, timeout=60, cwd=str(ROOT))
    except (OSError, subprocess.SubprocessError):
        return ""
    for line in (p.stdout or "").splitlines():
        if line.startswith("password="):
            return line.split("=", 1)[1].strip()
    return ""


def call(method, url, tok, *, data=None, raw=None, ctype="application/json"):
    body = raw if raw is not None else (json.dumps(data).encode("utf-8") if data is not None else None)
    req = urllib.request.Request(url, data=body, method=method, headers={
        "User-Agent": "codex-cli",
        "Accept": "application/vnd.github+json",
        "Authorization": "Bearer " + tok,
    })
    if body is not None:
        req.add_header("Content-Type", ctype)
    try:
        with urllib.request.urlopen(req, timeout=300) as r:
            text = r.read().decode("utf-8", "replace")
            return r.status, (json.loads(text) if text.strip() else None)
    except urllib.error.HTTPError as e:
        text = e.read().decode("utf-8", "replace")
        try:
            parsed = json.loads(text)
        except Exception:
            parsed = text
        return e.code, parsed


def git(*args, extra_env=None):
    env = dict(os.environ, GIT_TERMINAL_PROMPT="0")
    if extra_env:
        env.update(extra_env)
    p = subprocess.run(["git", *args], cwd=str(ROOT), capture_output=True, text=True, env=env, timeout=600)
    return p.returncode, (p.stdout or "").strip(), (p.stderr or "").strip()


def main():
    print("[0/6] 这一版：%s → tag %s" % (VERSION, TAG))
    for f in (NOTES, ZIP):
        if not f.exists():
            raise SystemExit("找不到 " + str(f) + "（说明要先写说明 / 先出包）")
    tok, where = token()
    print("[1/6] 凭据来源:", where)

    status, user = call("GET", API + "/user", tok)
    if status != 200:
        raise SystemExit("凭据不可用（%s）：%s" % (status, str(user)[:200]))
    print("[1/6] 身份:", user.get("login"), "| scopes:", user.get("scopes") or "（fine-grained）")

    rc, out, err = git("rev-parse", "HEAD")
    head = out if rc == 0 else ""
    rc, out, _ = git("rev-parse", "--short", "HEAD")
    print("[2/6] 本地 HEAD:", out, head[:7])

    # 用 GIT_CONFIG_* 从环境里塞认证头：不写进 .git/config，也不出现在进程命令行里
    auth = base64.b64encode(("x-access-token:" + tok).encode("utf-8")).decode("ascii")
    env = {"GIT_CONFIG_COUNT": "1",
           "GIT_CONFIG_KEY_0": "http.https://github.com/.extraheader",
           "GIT_CONFIG_VALUE_0": "AUTHORIZATION: Basic " + auth}

    rc, out, err = git("push", "origin", "main", extra_env=env)
    print("[3/6] push main:", "ok" if rc == 0 else "失败")
    if rc != 0:
        raise SystemExit(err[:400] or "push 失败")

    rc, out, _ = git("tag", "--list", TAG)
    if not out:
        rc, out, err = git("tag", "-a", TAG, "-m", "GuzhuComic " + VERSION)
        if rc != 0:
            raise SystemExit("打 tag 失败：" + err[:300])
        print("[4/6] 本地打 tag", TAG)
    else:
        print("[4/6] 本地已有 tag", TAG)
    rc, out, err = git("push", "origin", TAG, extra_env=env)
    if rc != 0 and "already exists" not in err:
        print("[4/6] push tag:", err[:200])
    else:
        print("[4/6] push tag: ok")

    notes = NOTES.read_text(encoding="utf-8")
    status, existing = call("GET", "%s/repos/%s/releases/tags/%s" % (API, REPO, TAG), tok)
    if status == 200:
        rid = existing["id"]
        st, res = call("PATCH", "%s/repos/%s/releases/%d" % (API, REPO, rid), tok,
                       data={"name": TITLE, "body": notes, "draft": False, "prerelease": False})
        print("[5/6] release 已存在，改成最新说明:", st)
    else:
        st, res = call("POST", "%s/repos/%s/releases" % (API, REPO), tok, data={
            "tag_name": TAG, "name": TITLE, "body": notes,
            "draft": False, "prerelease": False, "target_commitish": "main"})
        if st not in (200, 201):
            raise SystemExit("建 release 失败（%s）：%s" % (st, str(res)[:300]))
        rid = res["id"]
        print("[5/6] release 建好:", res["html_url"])

    assets = {a["name"]: a for a in (res.get("assets") or [])}
    if ZIP.name in assets:
        print("[6/6] 资产已存在，跳过:", ZIP.name)
    else:
        blob = ZIP.read_bytes()
        st, up = call("POST", "%s/repos/%s/releases/%d/assets?name=%s" % (UPLOADS, REPO, rid, ZIP.name),
                      tok, raw=blob, ctype="application/zip")
        if st not in (200, 201):
            raise SystemExit("上传资产失败（%s）：%s" % (st, str(up)[:300]))
        print("[6/6] 资产已上传：%s（%.2f MiB）" % (up["name"], up["size"] / 1048576))

    print("\n完成：https://github.com/%s/releases/tag/%s" % (REPO, TAG))


if __name__ == "__main__":
    raise SystemExit(main())