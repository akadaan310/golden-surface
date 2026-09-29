"""The relay's side of Luna: the public Foundry, the shell, and Loom.

  LUNA_FOUNDRY_URL  Lunar Foundry (default https://lunar-foundry.vercel.app). /map asks
                    it for a tab's Lunar natures. Only tabs NOT on a shared session are
                    sent, with secrets redacted from the URL. Set it empty to turn off.
  LUNA_SHELL_URL    the Luna shell (e.g. http://127.0.0.1:8471). The relay joins it as a
                    partner on start.
  LUNA_LOOM_URL     Loom (e.g. http://127.0.0.1:8472). Pages ر opens in the Surface are
                    opened in Loom too, so Loom's tabulars and the Surface agree.

All three are optional. A failure is logged loudly and never blocks the Surface.
"""
import asyncio
import time
from urllib.parse import quote

import aiohttp

from twin import redact_url

CACHE_SECONDS = 60
TIMEOUT = aiohttp.ClientTimeout(total=6)


class Luna:
    def __init__(self, env):
        self.foundry = env.get("LUNA_FOUNDRY_URL", "https://lunar-foundry.vercel.app").rstrip("/")
        self.shell = (env.get("LUNA_SHELL_URL") or "").rstrip("/")
        self.loom = (env.get("LUNA_LOOM_URL") or "").rstrip("/")
        self.cache = {}  # url -> (at, natures)

    async def natures(self, url):
        """Lunar natures for one public page, from the Foundry lens. Cached."""
        if not self.foundry or not url or not url.startswith(("http://", "https://")):
            return None
        url = redact_url(url)
        hit = self.cache.get(url)
        if hit and time.time() - hit[0] < CACHE_SECONDS:
            return hit[1]
        try:
            async with aiohttp.ClientSession(timeout=TIMEOUT) as s:
                async with s.get(f"{self.foundry}/lens?u={quote(url, safe='')}&format=json") as r:
                    data = await r.json(content_type=None)
            if data.get("ok"):
                lens = data["lens"]
                out = {"natures": lens.get("natures", []), "luna": lens.get("luna"), "domain": lens.get("domain")}
            else:
                out = {"error": data.get("error") or f"HTTP {r.status}"}
        except Exception as e:
            out = {"error": f"foundry: {type(e).__name__}"}
        self.cache[url] = (time.time(), out)
        if len(self.cache) > 500:
            for k in sorted(self.cache, key=lambda k: self.cache[k][0])[:100]:
                self.cache.pop(k, None)
        return out

    async def natures_for(self, tabs):
        """{tab id: natures} for every tab that may be sent: not signed in, a web URL."""
        send = [t for t in tabs if not t.get("signedIn") and (t.get("url") or "").startswith(("http://", "https://"))]
        results = await asyncio.gather(*(self.natures(t["url"]) for t in send))
        return {t["id"]: r for t, r in zip(send, results) if r is not None}

    async def join_shell(self, name, url):
        if not self.shell:
            return None
        try:
            async with aiohttp.ClientSession(timeout=TIMEOUT) as s:
                async with s.post(f"{self.shell}/partner", json={"name": name, "url": url}) as r:
                    return await r.json(content_type=None)
        except Exception as e:
            print(f"luna shell partner failed: {type(e).__name__}: {e}", flush=True)
            return None

    async def mirror_to_loom(self, url, title=None):
        if not self.loom or not url or not url.startswith(("http://", "https://")):
            return None
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15)) as s:
                async with s.post(f"{self.loom}/open", json={"url": url, "title": title or url[:60]}) as r:
                    return await r.json(content_type=None)
        except Exception as e:
            print(f"loom mirror failed: {type(e).__name__}: {e}", flush=True)
            return None
