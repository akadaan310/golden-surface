"""Domain-oriented navigation: what class of place an address is, from its domain.
Same table as app/src/domains.ts and luna-foundry/lib/lens.js (domainClass)."""
from urllib.parse import urlsplit

DOMAIN_CLASSES = {
    "gov": "government — public records and authoritative data",
    "mil": "military",
    "edu": "education and research",
    "org": "organizations and communities",
    "com": "commerce and companies",
    "net": "networks and services",
    "int": "international organizations",
    "io": "technology", "dev": "technology", "app": "technology", "ai": "technology",
}


def domain_class(host):
    if not host:
        return None
    labels = host.lower().rstrip(".").split(".")
    tld = labels[-1]
    second = labels[-2] if len(labels) > 1 else ""
    if len(tld) == 2 and second in DOMAIN_CLASSES:
        return {"tld": f"{second}.{tld}", "class": DOMAIN_CLASSES[second], "country": tld}
    if tld in DOMAIN_CLASSES:
        return {"tld": tld, "class": DOMAIN_CLASSES[tld]}
    if len(tld) == 2:
        return {"tld": tld, "class": "country", "country": tld}
    return {"tld": tld, "class": "general"}


def domain_of_url(url):
    try:
        parts = urlsplit(url or "")
    except ValueError:
        return None
    if parts.scheme not in ("http", "https"):
        return None
    return domain_class(parts.hostname)
