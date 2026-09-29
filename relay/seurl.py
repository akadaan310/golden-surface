"""seurl://golden — the Golden Surface as addresses.

  seurl://golden/map                          the surface map
  seurl://golden/tab/{id}                     one tab
  seurl://golden/tab/{id}/scroll?from=&len=   a window of the tab's text
  seurl://golden/tab/{id}/open?url=           open a URL in the tab (an act: POST /cmd)

Same grammar as app/src/seurl.ts. Reading an address never changes the surface."""
from urllib.parse import parse_qs, urlsplit

PREFIX = "seurl://golden"


def address(tab_id=None, verb=None, **params):
    s = PREFIX + ("/map" if tab_id is None else f"/tab/{tab_id}")
    if verb:
        s += f"/{verb}"
    if params:
        from urllib.parse import urlencode
        s += "?" + urlencode(params)
    return s


def parse(u):
    """-> {"verb": map|tab|scroll|open, "tab": id|None, "params": {k: v}} or raises ValueError."""
    parts = urlsplit(u or "")
    if parts.scheme != "seurl" or parts.netloc != "golden":
        raise ValueError("not a seurl://golden address")
    segs = [s for s in parts.path.split("/") if s]
    params = {k: v[0] for k, v in parse_qs(parts.query).items()}
    if segs in ([], ["map"]):
        return {"verb": "map", "tab": None, "params": params}
    if len(segs) >= 2 and segs[0] == "tab":
        verb = segs[2] if len(segs) > 2 else "tab"
        if verb not in ("tab", "scroll", "open") or len(segs) > 3:
            raise ValueError(f"unknown verb {verb}")
        if verb == "open" and not params.get("url"):
            raise ValueError("open needs url=")
        return {"verb": verb, "tab": segs[1], "params": params}
    raise ValueError("unknown seurl://golden path")
