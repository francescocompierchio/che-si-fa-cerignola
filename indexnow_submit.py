#!/usr/bin/env python3
"""IndexNow: only public canonical URLs of this Pages project, after deployment."""
import json
import pathlib
import re
import sys
import urllib.request
import urllib.error
import xml.etree.ElementTree as ET
from urllib.parse import urlsplit

BASE = "https://francescocompierchio.github.io/che-si-fa-cerignola/"
HOST = urlsplit(BASE).hostname
KEY = "4efda12986bc4ea58704d2a938cf1f51"
KEY_URL = BASE + KEY + ".txt"
STATE = pathlib.Path(".indexnow-state/sent.json")
NS = "{http://www.sitemaps.org/schemas/sitemap/0.9}"
PRIORITY = ["", "eventi/", "eventi/cerignola.html", "eventi/weekend.html",
            "eventi/hub-serate.html", "eventi/hub-comune-barletta.html",
            "eventi/hub-comune-trani.html", "eventi/hub-comune-manfredonia.html"]


def permitted(url):
    if not isinstance(url, str) or not url.startswith(BASE):
        return False
    u = urlsplit(url)
    path = url[len(BASE):]
    return u.scheme == "https" and u.netloc == HOST and not u.query and not u.fragment and (
        path in {"", "collabora.html", "eventi/"} or bool(re.fullmatch(r"eventi/[a-z0-9-]+\.html", path))
    )


def parse_sitemap(data):
    root = ET.fromstring(data)
    if root.tag != NS + "urlset":
        raise ValueError("Sitemap non riconosciuta")
    out = {}
    for row in root.findall(NS + "url"):
        url = row.findtext(NS + "loc", "").strip()
        if not permitted(url):
            continue
        if url in out:
            raise ValueError("URL duplicato")
        out[url] = row.findtext(NS + "lastmod", "").strip()
    if BASE not in out or BASE + "eventi/" not in out:
        raise ValueError("Sitemap incompleta")
    return out


def plan(current, previous, limit=35):
    if previous is None:
        # Initial rollout: notify only the main recently updated landing pages.
        return [BASE + p for p in PRIORITY if BASE + p in current][:limit]
    changed = [u for u in current if u not in previous or current[u] != previous[u]]
    removed = [u for u in previous if u not in current and permitted(u)]
    return (changed + removed)[:limit]


def request(url, method="GET", payload=None):
    req = urllib.request.Request(url, data=payload, method=method,
        headers={"User-Agent": "CheSiFaCerignola-IndexNow/1.0",
                 "Accept": "*/*", "Content-Type": "application/json; charset=utf-8",
                 "Cache-Control": "no-cache"})
    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            return response.status, response.read(2_000_000)
    except urllib.error.HTTPError as exc:
        return exc.code, b""


def main():
    status, key = request(KEY_URL)
    if status != 200 or key.decode("utf-8").strip() != KEY:
        print("Chiave non ancora pubblicata; nessun invio. Si riprova al prossimo ciclo.")
        return
    status, data = request(BASE + "sitemap.xml")
    if status != 200:
        raise RuntimeError("Sitemap pubblica non disponibile")
    current = parse_sitemap(data)
    previous = None
    if STATE.exists():
        previous = json.loads(STATE.read_text(encoding="utf-8"))
        if not isinstance(previous, dict):
            raise ValueError("Stato IndexNow non valido")
    pending = plan(current, previous)
    urls = []
    for url in pending:
        status, _ = request(url, method="HEAD")
        if (url in current and status == 200) or (url not in current and status in (404, 410)):
            urls.append(url)
    if not urls:
        print("Nessuna modifica pubblicata da notificare.")
        return
    payload = json.dumps({"host": HOST, "key": KEY, "keyLocation": KEY_URL, "urlList": urls}).encode("utf-8")
    status, _ = request("https://api.indexnow.org/indexnow", "POST", payload)
    print(f"IndexNow HTTP {status}; {len(urls)} URL inviati")
    for url in urls:
        print(url)
    if status not in (200, 202):
        raise RuntimeError(f"IndexNow non ha accettato l'invio ({status}); stato conservato")
    # Mark only successfully submitted changes. First run baselines existing,
    # unchanged pages; any primary URL not yet available is retried next run.
    next_state = dict(current) if previous is None else dict(previous)
    for url in pending:
        if previous is None and url not in urls:
            next_state.pop(url, None)
    for url in urls:
        if url in current:
            next_state[url] = current[url]
        else:
            next_state.pop(url, None)
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(next_state, ensure_ascii=False, sort_keys=True), encoding="utf-8")


if __name__ == "__main__":
    main()
