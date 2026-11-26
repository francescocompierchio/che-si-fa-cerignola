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


def verifica_prezzi(actor, now, primary="post"):
    if actor.get("actorPermissionLevel") != "LIMITED_PERMISSIONS":
        raise Pausa("permessi Actor non compatibili")
    active = [p for p in actor["pricingInfos"] if datetime.fromisoformat(
        p["startedAt"].replace("Z", "+00:00")) <= now]
    price = max(active, key=lambda p: p["startedAt"])
    if price["pricingModel"] != "PAY_PER_EVENT" or numero(price.get("minimalMaxTotalChargeUsd", 0)) > CAP:
        raise Pausa("modello tariffario non compatibile")
    events = price["pricingPerEvent"]["actorChargeEvents"]
    fees = {k: numero(v["eventTieredPricingUsd"]["FREE"]["tieredEventPriceUsd"]
                      if "eventTieredPricingUsd" in v else v["eventPriceUsd"])
            for k, v in events.items()}
    if not 0 < fees[primary] <= .005 or any(v > CAP for v in fees.values()):
        raise Pausa("tariffa oltre soglia")
    return fees


def profili():
    result = {}
    venues = json.loads(Path("fonti_movida.json").read_text())
    venues["Promoter territoriali"] = json.loads(Path("fonti_promoter.json").read_text())
    for city, rows in venues.items():
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
    if not due:
        return None
    # Cinque slot locali, due nella prima cintura e uno nella seconda.
    # Se il gruppo non ha fonti dovute lo slot passa al gruppo più vicino.
    rank_slot = (0, 0, 1, 0, 0, 1, 0, 2)[sum(p.get("visite", 1) for p in history.values()) % 8]
    tier = [item for item in due if item[1] == rank_slot]
    if not tier:
        nearest = min(item[1] for item in due)
        tier = [item for item in due if item[1] == nearest]
    return min(tier)[2:]


def api(session, path, body=None, **params):
    r = session.request("GET" if body is None else "POST", "https://api.apify.com/v2/" + path,
                        params=params, json=body, timeout=(5, 70), allow_redirects=False)
    if r.status_code not in (200, 201):
        raise Pausa(f"API HTTP {r.status_code} su {path.split('/')[0]}")
    return r.json()


def pagine_google(rows, engine):
    events = []
    stats = {"pagineLette": 0, "pagineBloccate": 0, "erroriLettura": 0}
    urls = dict.fromkeys(hit.get("url") for row in rows for hit in row.get("organicResults", []))
    allowed = set(engine.DOMINI_AUTO) - {"facebook.com", "instagram.com", "news.google.com"}
    for url in [u for u in urls if isinstance(u, str) and urlsplit(u).scheme == "https"
                and (urlsplit(u).hostname or "").removeprefix("www.") in allowed
                and not engine._url_pagina_elenco(u)][:4]:
        try:
            with requests.get(url, timeout=(3, 6), allow_redirects=False, stream=True) as response:
                if response.status_code in (401, 403, 429):
                    stats["pagineBloccate"] += 1
                    continue
                if response.status_code != 200 or "text/html" not in response.headers.get("Content-Type", ""):
                    stats["erroriLettura"] += 1
                    continue
                body = bytearray()
                for chunk in response.iter_content(65536):
                    body.extend(chunk)
                    if len(body) > 2_000_000:
                        break
                if len(body) <= 2_000_000:
                    stats["pagineLette"] += 1
                    events.extend(engine.analizza_pagina_evento(body.decode("utf-8", errors="replace"), url))
        except (requests.RequestException, ValueError):
            stats["erroriLettura"] += 1
    return events, stats


def raccogli():
    import aggiorna_eventi as engine
    now = int(time.time())
    state = json.loads(STATE.read_text()) if STATE.exists() else {}
    if now - state.get("last", 0) < INTERVAL:
        return {"stato": "pausa programmata", "prossimoUnix": state["last"] + INTERVAL}
    if not os.getenv("APIFY_TOKEN"):
        return {"stato": "secret APIFY_TOKEN assente nel workflow"}
    meta_consentita = os.getenv("APIFY_META_AUTORIZZATO") == "1"
    google_consentito = os.getenv("APIFY_GOOGLE_AUTORIZZATO") == "1"
    if not (meta_consentita or google_consentito):
        return {"stato": "sospeso", "motivo": "autorizzazione della piattaforma non configurata"}
    history = state.setdefault("profili", {})
    choice = scegli(profili(), history, now) if meta_consentita else None
    google = google_consentito and now - state.get("lastGoogle", 0) >= 7 * 86400
    if google:
        actor, url, host = "acts/automatic~google-search-results-scraper", "Google Cerignola", ""
    elif choice:
        url, host = choice
        actor = "acts/apify~" + ACTORS[host]
    else:
        return {"stato": "nessuna fonte dovuta"}
    with requests.Session() as auth:
        auth.headers["Authorization"] = "Bearer " + os.environ["APIFY_TOKEN"]
        verifica_budget(api(auth, "users/me")["data"]["plan"], api(auth, "users/me/limits")["data"])
        fees = verifica_prezzi(api(auth, actor)["data"], datetime.now(timezone.utc),
                               "apify-default-dataset-item" if google else "post")
        state["last"] = now
        if google:
            state["lastGoogle"] = now
        STATE.parent.mkdir(exist_ok=True)
        engine._scrivi_json_atomico(str(STATE), state)
        body = {"resultsLimit": 4}
        if google:
            body = {"queries": ['Cerignola ("dj set" OR karaoke OR "cena spettacolo" OR concerto OR sagra)'],
                    "maxPagesPerQuery": 1, "countryCode": "it", "languageCode": "it"}
        elif host == "instagram.com":
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
            if not google:
                history[url] = {"visite": history.get(url, {}).get("visite", 0) + 1, "at": now, "stato": "indeterminata", "validi": 0}
                engine._scrivi_json_atomico(str(STATE), state)
            return report
        rows = api(auth, "datasets/" + run["defaultDatasetId"] + "/items", limit=4, clean="true")
    if google:
        events, stats = pagine_google(rows, engine)
        engine._scrivi_json_atomico(str(OUTPUT), events)
        return dict(report, **stats, validi=len(events))
    events = []
    posts = posters = contraddizioni = 0
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
            date_caption = engine.discovery_locale.date_complete(caption)
            date_ocr = {ev["dataInizio"] for ev in candidates}
            if date_caption and date_ocr and date_caption != date_ocr:
                contraddizioni += 1
                continue
            if title and engine.discovery_locale.TEMI.search(caption):
                candidates.extend(engine.eventi_da_locandina(caption, "", title, post))
            for ev in candidates:
                if not engine.evento_non_attivo(ev) and not any(engine.sono_duplicati(ev, old) for old in events):
                    events.append(ev)
    denied = any(re.search(r"blocked|access denied|private|login", str(r), re.I) for r in errors)
    status = "bloccata" if denied else "indeterminata" if errors or not posts else "letta"
    history[url] = {"visite": history.get(url, {}).get("visite", 0) + 1, "at": now, "stato": status, "validi": len(events)}
    engine._scrivi_json_atomico(str(STATE), state)
    engine._scrivi_json_atomico(str(OUTPUT), events)
    return dict(report, esitoFonte=status, post=posts, immaginiOCR=posters, discordanzeData=contraddizioni, validi=len(events))


if __name__ == "__main__":
    OUTPUT.unlink(missing_ok=True)
    try:
        report = raccogli()
    except Pausa as exc:
        report = {"stato": "sospeso", "motivo": str(exc)}
    except KeyError as exc:
        # Le chiavi attese sono nomi di campi, mai valori dell'account.
        key = str(exc.args[0])
        safe = key if key in {"data", "tier", "monthlyUsageCreditsUsd", "monthlyBasePriceUsd",
                              "plan", "limits", "current", "monthlyUsageUsd", "maxMonthlyUsageUsd",
                              "pricingInfos", "FREE", "tieredEventPriceUsd", "defaultDatasetId"} else "altro"
        report = {"stato": "sospeso", "campoMancante": safe}
    except Exception as exc:
        report = {"stato": "indisponibile", "errore": type(exc).__name__}
    Path("apify-rapporto.json").write_text(json.dumps(report, ensure_ascii=False))
    print(json.dumps(report, ensure_ascii=False))
