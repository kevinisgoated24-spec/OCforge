import io
import json
import urllib.error

import pytest

from ocforge.fetch import github
from ocforge.fetch.http import RateLimited


class _Resp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.close()


@pytest.fixture(autouse=True)
def _reset():
    github._MEM.clear()
    github.set_cache_dir(None)
    yield
    github._MEM.clear()
    github.set_cache_dir(None)


def _fake_release(assets):
    return {"tag_name": "v1.2.3",
            "assets": [{"name": n, "browser_download_url": f"https://x/{n}", "size": 10}
                       for n in assets]}


def test_release_json_is_fetched_once_per_repo(monkeypatch, tmp_path):
    calls: list[str] = []

    def fake_open_url(url, **kw):
        calls.append(url)
        return _Resp(json.dumps(_fake_release(["Foo.kext.zip", "Bar.kext.zip"])).encode())

    monkeypatch.setattr(github, "open_url", fake_open_url)
    github.set_cache_dir(tmp_path)

    # three lookups against the same repo — different patterns
    github.latest_asset("owner/repo", r"Foo")
    github.latest_asset("owner/repo", r"Bar")
    github.latest_asset("owner/repo", r"Foo", tag="latest")
    assert len(calls) == 1

    # a fresh process (cleared _MEM) still hits disk, not the network
    github._MEM.clear()
    got = github.latest_asset("owner/repo", r"Bar")
    assert got.name == "Bar.kext.zip"
    assert len(calls) == 1


def test_rate_limit_error_is_friendly(monkeypatch):
    from ocforge.fetch import http as httpmod

    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("GH_TOKEN", raising=False)
    monkeypatch.setattr(httpmod, "_gh_cli_token", lambda: None)

    err = urllib.error.HTTPError(
        "https://api.github.com/x", 403, "Forbidden",
        {"X-RateLimit-Remaining": "0", "X-RateLimit-Reset": "1700000000"}, None,
    )
    rl = httpmod._rate_limit_error(err, "https://api.github.com/x")
    assert isinstance(rl, RateLimited)
    assert "GITHUB_TOKEN" in str(rl) and "rate limit" in str(rl).lower()

    # a plain 403 (not rate-limited) is left alone
    err2 = urllib.error.HTTPError("u", 403, "no", {"X-RateLimit-Remaining": "57"}, None)
    assert httpmod._rate_limit_error(err2, "u") is None
