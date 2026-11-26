"""Rileva feed dichiarati dagli editori già ammessi dal motore."""
from hashlib import sha256
from urllib.parse import urljoin, urlsplit
import re
from urllib.robotparser import RobotFileParser

import requests

import radar_territorio

BOT = "CheSiFaCerignola"
HEADERS = {"User-Agent": BOT}


def indirizzo_feed(base, href):
    try:
        url = urljoin(base, href)
        parts = urlsplit(url)
    except ValueError:
        return ""
    if (not radar_territorio.host_pubblico(url)
        or radar_territorio.host_pubblico(base) != radar_territorio.host_pubblico(url)
        or parts.query or parts.fragment or ":" in parts.netloc or len(parts.path) > 150
        or not re.fullmatch(r"/[a-zA-Z0-9._/-]+", parts.path)
        or ".." in parts.path
        or not re.search(r"(?:\.(?:rss|xml|atom)$|/(?:feed|rss|atom)/?$)", parts.path, re.I)):
        return ""
    return url


def dichiarati(soup, pagina):
    feed = []
    for el in soup.select('link[rel~="alternate"][type="application/rss+xml"][href], link[rel~="alternate"][type="application/atom+xml"][href]'):
        url = indirizzo_feed(pagina, el["href"])
        if url and url not in feed:
            feed.append(url)
    return feed[:2]


def registrati(memoria, diagnostica, now):
    elenco = memoria.setdefault("feedEditori", {})
    for dati in diagnostica.values():
        if dati.get("stato") != "ok":
            continue
        for url in dati.get("feedDichiarati", []):
            if not indirizzo_feed(url, url):
                continue
            entry = elenco.setdefault(url, {"scopertoAl": now})
            entry.update({"confermatoAl": now, "citta": dati.get("cittaDichiarataFeed", "")})
    vivi = sorted(
        ((url, entry) for url, entry in elenco.items() if now - entry["confermatoAl"] <= 60 * 86400),
        key=lambda kv: (-kv[1]["confermatoAl"], kv[0]),
    )
    memoria["feedEditori"] = dict(vivi[:50])
    return sum(entry["scopertoAl"] == now for _, entry in vivi)


def scegli(memoria, now, domini, url_noti=()):
    fonti = memoria.get("fonti", {})
    noti = {(radar_territorio.host_pubblico(u), urlsplit(u).path.rstrip("/")) for u in url_noti}
    dovuti = []
    for url, entry in memoria.get("feedEditori", {}).items():
        host = radar_territorio.host_pubblico(url)
        if (host not in domini or not indirizzo_feed(url, url)
            or (host, urlsplit(url).path.rstrip("/")) in noti):
            continue
        nome = "Feed editore " + host + " " + sha256(url.encode()).hexdigest()[:8]
        dati = fonti.get(nome, {})
        ultimo = dati.get("ultimoTentativo", 0)
        ore = 2 if dati.get("produttivita", 0) or entry["citta"] == "Cerignola" else 6
        if dati.get("ultimoEsito", "").startswith("robots"):
            ore = 24
        if now - ultimo < ore * 3600 or dati.get("prossimoTentativo", 0) > now:
            continue
        task = {"nome": nome, "url": url, "dominio": host, "citta_default": entry["citta"],
                "feed_editore": True, "feed_autoscoperto": True, "max_schede_rss": 3}
        dovuti.append((entry["citta"] != "Cerignola", ultimo, nome, task))
    return [task for _, _, _, task in sorted(dovuti)[:2]]


def robots(session, url):
    parts = urlsplit(url)
    policy_url = f"{parts.scheme}://{parts.netloc}/robots.txt"
    cache = getattr(session, "_csf_robots", None)
    if cache is None:
        cache = session._csf_robots = {}
    if policy_url in cache:
        return cache[policy_url]
    cache[policy_url] = None
    try:
        r = session.get(policy_url, timeout=(3, 5), allow_redirects=False, headers=HEADERS)
    except requests.RequestException:
        return None
    policy = RobotFileParser()
    if r.status_code in (404, 410):
        policy.parse([])
    elif r.status_code == 200 and len(r.content) <= 128 * 1024:
        policy.parse(r.text.splitlines())
    else:
        return None
    if policy.crawl_delay(BOT) or policy.request_rate(BOT):
        return None
    cache[policy_url] = policy
    return policy


def scheda_da_origini_note(session, link, host_ammessi):
    """Segue solo reindirizzamenti pubblici verso origini già configurate."""
    for _ in range(4):
        host = radar_territorio.host_pubblico(link)
        if host not in host_ammessi or ":" in urlsplit(link).netloc:
            return None
        if host != "news.google.com":
            policy = robots(session, link)
            if policy is None or not policy.can_fetch(BOT, link):
                return None
        pagina = session.get(link, timeout=(4, 7), allow_redirects=False, headers=HEADERS)
        if pagina.status_code not in (301, 302, 303, 307, 308):
            return pagina
        destinazione = pagina.headers.get("Location", "")
        if not destinazione:
            return None
        link = urljoin(link, destinazione)
    return None
