"""Acquisizione pubblica con preflight e tetto di spesa lato Apify."""
import json
import math
import os
import re
import time
from datetime import datetime, timezone
from html import escape
from pathlib import Path
from urllib.parse import urlsplit

import requests

STATE = Path(".csf-state/apify.json")
OUTPUT = Path("apify-eventi.json")
CAP = 0.035
INTERVAL = 8 * 3600
ACTORS = {"instagram.com": "instagram-post-scraper", "facebook.com": "facebook-posts-scraper"}


class Pausa(Exception):
    pass


def numero(value):
    if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
        raise Pausa("importo non verificabile")
    return value


def verifica_budget(plan, limits):
    if plan.get("tier", "").upper() != "FREE" or numero(plan["monthlyBasePriceUsd"]) != 0:
        raise Pausa("piano gratuito non confermato")
    credit = numero(plan["monthlyUsageCreditsUsd"])
    hard = numero(limits["limits"]["maxMonthlyUsageUsd"])
    used = numero(limits["current"]["monthlyUsageUsd"])
    if hard > credit or used + CAP + 0.25 > min(hard, credit, 5):
        raise Pausa("limite account o credito residuo insufficiente")


def verifica_prezzi(actor, now):
    active = [p for p in actor["pricingInfos"] if datetime.fromisoformat(
        p["startedAt"].replace("Z", "+00:00")) <= now]
    price = max(active, key=lambda p: p["startedAt"])
    if price["pricingModel"] != "PAY_PER_EVENT" or numero(price["minimalMaxTotalChargeUsd"]) > CAP:
        raise Pausa("modello tariffario non compatibile")
    events = price["pricingPerEvent"]["actorChargeEvents"]
    fees = {k: numero(v["eventTieredPricingUsd"]["FREE"]["tieredEventPriceUsd"])
            for k, v in events.items()}
    if not 0 < fees["post"] <= .005 or any(v > CAP for v in fees.values()):
        raise Pausa("tariffa oltre soglia")
    return fees


def profili():
    result = {}
    for city, rows in json.loads(Path("fonti_movida.json").read_text()).items():
        for row in rows:
            for field in ("social", "facebook"):
                url = row.get(field, "")
                parts = urlsplit(url)
                host = (parts.hostname or "").removeprefix("www.")
                if parts.scheme == "https" and host in ACTORS and re.fullmatch(r"/[\w.-]+/?", parts.path):
                    result[url] = (city, host)
    return result


def scegli(profiles, history, now):
    # Una fonte produttiva torna prima; le fonti vicine hanno la precedenza a parità di scadenza.
    due = []
    for url, (city, host) in profiles.items():
        rank = 0 if city == "Cerignola" else 1 if city in {"Orta Nova", "Canosa di Puglia"} else 2
        prev = history.get(url, {})
        hours = 48 if prev.get("validi") else 96
        if prev.get("stato") in {"bloccata", "indeterminata"}:
            hours = 168
        deadline = prev.get("at", 0) + (hours + rank * 24) * 3600
        if deadline <= now:
            due.append((deadline if prev else rank, rank, url, host))
    return min(due)[2:] if due else None


def api(session, path, body=None, **params):
    r = session.request("GET" if body is None else "POST", "https://api.apify.com/v2/" + path,
                        params=params, json=body, timeout=(5, 70), allow_redirects=False)
    if r.status_code not in (200, 201):
        raise Pausa(f"API HTTP {r.status_code} su {path.split('/')[0]}")
    return r.json()


def raccogli():
    import aggiorna_eventi as engine
    now = int(time.time())
    state = json.loads(STATE.read_text()) if STATE.exists() else {}
    if now - state.get("last", 0) < INTERVAL:
        return {"stato": "pausa programmata"}
    history = state.setdefault("profili", {})
    choice = scegli(profili(), history, now)
    if not choice or not os.getenv("APIFY_TOKEN"):
        return {"stato": "nessuna fonte dovuta o secret assente"}
    url, host = choice
    actor = "acts/apify~" + ACTORS[host]
    with requests.Session() as auth:
        auth.headers["Authorization"] = "Bearer " + os.environ["APIFY_TOKEN"]
        verifica_budget(api(auth, "users/me")["data"]["plan"], api(auth, "users/me/limits")["data"])
        fees = verifica_prezzi(api(auth, actor)["data"], datetime.now(timezone.utc))
        state["last"] = now
        STATE.parent.mkdir(exist_ok=True)
        engine._scrivi_json_atomico(str(STATE), state)
        body = {"resultsLimit": 4}
        if host == "instagram.com":
            body["username"] = [urlsplit(url).path.strip("/")]
        else:
            body["startUrls"] = [{"url": url}]
        run = api(auth, actor + "/runs", body, maxTotalChargeUsd=CAP, waitForFinish=50, timeout=100)["data"]
        for _ in range(12):
            if run["status"] not in {"READY", "RUNNING", "TIMING-OUT", "ABORTING"}:
                break
            time.sleep(5)
            run = api(auth, "actor-runs/" + run["id"])["data"]
        report = {"profilo": url, "run": run["id"], "stato": run["status"],
                  "costoUsd": run.get("usageTotalUsd"), "tariffeFree": fees}
        if run["status"] != "SUCCEEDED":
            return report
        rows = api(auth, "datasets/" + run["defaultDatasetId"] + "/items", limit=4, clean="true")
    events = []
    posts = posters = 0
    errors = [r for r in rows if r.get("error") or r.get("errorDescription")]
    with engine.crea_session_raccolta() as public:
        for row in rows:
            if row in errors:
                continue
            post = row.get("url") or row.get("postUrl") or ""
            parts = urlsplit(post)
            if parts.scheme != "https" or (parts.hostname or "").removeprefix("www.") != host:
                continue
            if not re.search(r"/(?:p|reels?|posts|videos|permalink)/[^/]+|/(?:story|permalink)\.php$", parts.path):
                continue
            posts += 1
            caption = (row.get("caption") or row.get("text") or "").strip()
            title = next((line.strip()[:150] for line in caption.splitlines() if len(line.strip()) >= 5), "")
            media = row.get("media") or []
            image = row.get("displayUrl") or next((m.get("thumbnail") for m in media if isinstance(m, dict) and m.get("thumbnail")), "")
            candidates = []
            if isinstance(image, str) and urlsplit(image).scheme == "https" and (urlsplit(image).hostname or "").endswith((".cdninstagram.com", ".fbcdn.net")):
                html = '<meta property="og:image" content="' + escape(image) + '">'
                for poster, ocr in engine.estrai_testo_locandine(public, html, max_immagini=1, singole=True):
                    posters += 1
                    candidates.extend(engine.eventi_da_locandina(ocr, poster, title, post))
            if title and engine.discovery_locale.TEMI.search(caption):
                candidates.extend(engine.eventi_da_locandina(caption, "", title, post))
            for ev in candidates:
                if not engine.evento_non_attivo(ev) and not any(engine.sono_duplicati(ev, old) for old in events):
                    events.append(ev)
    denied = any(re.search(r"blocked|access denied|private|login", str(r), re.I) for r in errors)
    status = "bloccata" if denied else "indeterminata" if errors or not posts else "letta"
    history[url] = {"at": now, "stato": status, "validi": len(events)}
    engine._scrivi_json_atomico(str(STATE), state)
    engine._scrivi_json_atomico(str(OUTPUT), events)
    return dict(report, esitoFonte=status, post=posts, immaginiOCR=posters, validi=len(events))


if __name__ == "__main__":
    OUTPUT.unlink(missing_ok=True)
    try:
        print(json.dumps(raccogli(), ensure_ascii=False))
    except Pausa as exc:
        print(f"Apify sospeso: {exc}")
    except Exception as exc:
        print("Apify indisponibile:", type(exc).__name__)
