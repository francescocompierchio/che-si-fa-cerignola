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
ATTORE_CALENDARI = "acts/topapi~website-content-crawler"
AGENDA_CERIGNOLA = "https://comune.cerignola.fg.it/vivere-il-comune/eventi/"
PERCORSO_EVENTO_COMUNALE = re.compile(r"/vivere-il-comune/eventi/[a-z0-9][a-z0-9-]*/?")
TETTO_CALENDARI = 0.01
INTERVALLO_CALENDARI = 24 * 3600
MASSIMO_PAGINE_CALENDARI = 5


class Pausa(Exception):
    pass


def numero(value):
    if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
        raise Pausa("importo non verificabile")
    return value


def verifica_budget(plan, limits, tetto=CAP):
    piano = plan.get("tier") or plan.get("id")
    if str(piano).strip().upper() != "FREE" or numero(plan["monthlyBasePriceUsd"]) != 0:
        raise Pausa("piano gratuito non confermato")
    credit = numero(plan["monthlyUsageCreditsUsd"])
    hard = numero(limits["limits"]["maxMonthlyUsageUsd"])
    used = numero(limits["current"]["monthlyUsageUsd"])
    if hard > credit or used + tetto + 0.25 > min(hard, credit, 5):
        raise Pausa("limite account o credito residuo insufficiente")


def verifica_prezzi(actor, now, primary="post", tetto=CAP):
    if actor.get("actorPermissionLevel") != "LIMITED_PERMISSIONS":
        raise Pausa("permessi Actor non compatibili")
    active = [p for p in actor["pricingInfos"] if datetime.fromisoformat(
        p["startedAt"].replace("Z", "+00:00")) <= now]
    if not active:
        raise Pausa("tariffa attiva non verificabile")
    price = max(active, key=lambda p: p["startedAt"])
    minimo = price.get("minimalMaxTotalChargeUsd")
    if (price["pricingModel"] != "PAY_PER_EVENT" or price.get("isPPEPlatformUsagePaidByUser")
        or (minimo is not None and numero(minimo) > tetto)):
        raise Pausa("modello tariffario non compatibile")
    events = price["pricingPerEvent"]["actorChargeEvents"]
    fees = {k: numero(v["eventTieredPricingUsd"]["FREE"]["tieredEventPriceUsd"]
                      if "eventTieredPricingUsd" in v else v["eventPriceUsd"])
            for k, v in events.items()}
    if not 0 < fees.get(primary, 0) <= .005 or any(v > tetto for v in fees.values()):
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


def diagnosi_calendario(session, run):
    """Riporta solo indicatori fissi dai log privati di Apify."""
    diagnostica = {"ultimoStatoActor": run["status"]}
    if run["status"] != "FAILED":
        return diagnostica
    run_id = run.get("id", "")
    if not re.fullmatch(r"[a-zA-Z0-9]{8,32}", run_id):
        return diagnostica
    with session.get("https://api.apify.com/v2/logs/" + run_id, timeout=(4, 10),
                     allow_redirects=False, stream=True) as response:
        if response.status_code != 200:
            return dict(diagnostica, logActorHttp=response.status_code)
        raw = bytearray()
        for chunk in response.iter_content(4096):
            raw.extend(chunk)
            if len(raw) >= 96 * 1024:
                break
    testo = str(run.get("statusMessage") or "") + "\n" + raw.decode("utf-8", errors="replace")
    segnali = {
        "accesso_negato": r"(?:HTTP|status(?: code)?)[^\n\d]{0,8}(?:401|403|429)\b|captcha|access denied|forbidden|blocked by robots",
        "input_non_valido": r"invalid input|input validation|schema validation|must NOT have additional properties|input schema|ArgumentError",
        "avvio_o_dipendenza": r"ModuleNotFoundError|ERR_MODULE_NOT_FOUND|Cannot find module|ImportError|No module named|SyntaxError|FileNotFoundError|Cannot find package|ENOENT|exec format error",
        "configurazione_crawler": r"unknown propert|does not allow|unexpected (?:key|property)|Expected value|TypeError|ReferenceError",
        "timeout_o_memoria": r"timed out|TimeoutError|out of memory|OOMKilled|memory limit",
        "pagina_richiesta": r"\bCheerioCrawler\b|\bHttpCrawler\b|(?:fetch|loaded|received)\s+(?:page\s+)?https?://comune\.cerignola\.fg\.it",
    }
    diagnostica["segnaliActor"] = [nome for nome, regex in segnali.items() if re.search(regex, testo, re.I)]
    # Nomi standard di eccezioni, senza testo degli errori o porzioni di URL.
    diagnostica["classiErroreActor"] = sorted(set(re.findall(
        r"\b(?:TypeError|ReferenceError|SyntaxError|RangeError|ModuleNotFoundError|ImportError|FileNotFoundError|ArgumentError|TimeoutError|ERR_MODULE_NOT_FOUND|ERR_INVALID_ARG_TYPE|ERR_REQUIRE_ESM|ERR_PACKAGE_PATH_NOT_EXPORTED|ENOENT|EACCES)\b", testo)))[:10]
    return diagnostica


def diagnosi_ultimo_calendario(token, ultima):
    with requests.Session() as auth:
        auth.headers["Authorization"] = "Bearer " + token
        risultato = api(auth, ATTORE_CALENDARI + "/runs", limit=8, desc="true")["data"]["items"]
        for run in risultato:
            avvio = run.get("startedAt") or ""
            if avvio and abs(datetime.fromisoformat(avvio.replace("Z", "+00:00")).timestamp() - ultima) < 180:
                return diagnosi_calendario(auth, run)
    return {"ultimoStatoActor": "non_rintracciato"}


def leggi_righe_calendario(rows, engine):
    """Accetta solo risposte HTML leggibili e schede del calendario concordanti con l'URL richiesto."""
    eventi = []
    metriche = {"pagineLette": 0, "indiciLetti": 0, "schedeLette": 0}
    origine = urlsplit(AGENDA_CERIGNOLA)
    for row in rows[:MASSIMO_PAGINE_CALENDARI]:
        if not isinstance(row, dict):
            continue
        url, html, crawl = row.get("url"), row.get("rawHtml"), row.get("crawl")
        if not isinstance(url, str) or not isinstance(html, str) or not 50 <= len(html) <= 2_000_000 or not isinstance(crawl, dict):
            continue
        if crawl.get("httpStatusCode") != 200 or crawl.get("loadedUrl") != url:
            continue
        p = urlsplit(url)
        if (p.scheme, p.netloc) != (origine.scheme, origine.netloc) or p.query or p.fragment:
            continue
        indice = p.path.rstrip("/") == origine.path.rstrip("/")
        if not indice and not PERCORSO_EVENTO_COMUNALE.fullmatch(p.path):
            continue
        metriche["pagineLette"] += 1
        if indice:
            metriche["indiciLetti"] += 1
            continue
        metriche["schedeLette"] += 1
        for evento in engine.analizza_pagina_evento(html, url, citta_default="Cerignola", fonte_curata_eventi=True):
            if evento.get("citta") != "Cerignola" or engine.evento_non_attivo(evento) or any(engine.sono_duplicati(evento, e) for e in eventi):
                continue
            evento.pop("locandinaUrl", None)
            descrizione = evento.get("descrizione", "")[:190].rstrip()
            evento["descrizione"] = f"{descrizione} · Fonte: Comune di Cerignola" if descrizione else "Fonte: Comune di Cerignola"
            eventi.append(evento)
    return eventi, metriche


def raccogli_calendario():
    import aggiorna_eventi as engine

    token = os.getenv("APIFY_TOKEN", "").strip()
    if not token:
        return {"stato": "secret APIFY_TOKEN assente nel workflow"}
    now = int(time.time())
    state = json.loads(STATE.read_text()) if STATE.exists() else {}
    ultima = state.get("ultimoCalendario", 0)
    if now - ultima < INTERVALLO_CALENDARI:
        report = {"stato": "pausa programmata", "prossimoUnix": ultima + INTERVALLO_CALENDARI}
        if "diagnosiCalendario" not in state:
            try:
                state["diagnosiCalendario"] = diagnosi_ultimo_calendario(token, ultima)
                engine._scrivi_json_atomico(str(STATE), state)
            except (requests.RequestException, Pausa, TypeError, ValueError, KeyError):
                return dict(report, ultimoStatoActor="diagnosi_indisponibile")
        return dict(report, **state["diagnosiCalendario"])

    with requests.Session() as pubblico:
        policy = engine.fonti_editori.robots(pubblico, AGENDA_CERIGNOLA)
    if not policy or not all(policy.can_fetch(agent, AGENDA_CERIGNOLA) for agent in ("*", engine.fonti_editori.BOT)):
        raise Pausa("robots.txt del calendario non consente la lettura o non è verificabile")

    with requests.Session() as auth:
        auth.headers["Authorization"] = "Bearer " + token
        account = api(auth, "users/me")["data"]
        verifica_budget(account["plan"], api(auth, "users/me/limits")["data"], TETTO_CALENDARI)
        fees = verifica_prezzi(api(auth, ATTORE_CALENDARI)["data"], datetime.now(timezone.utc), "page-crawled", TETTO_CALENDARI)
        if MASSIMO_PAGINE_CALENDARI * fees["page-crawled"] > TETTO_CALENDARI:
            raise Pausa("tariffa del calendario oltre il tetto per esecuzione")
        body = {
            "startUrls": [{"url": AGENDA_CERIGNOLA}], "crawlMode": "startUrlPath",
            "maxCrawlDepth": 1, "maxCrawlPages": MASSIMO_PAGINE_CALENDARI, "maxConcurrency": 1,
            "linkSelector": f'main a[href^="{AGENDA_CERIGNOLA}"]:not([href="{AGENDA_CERIGNOLA}"])',
            "respectRobotsTxtFile": True, "renderJavaScript": "never", "maxRequestRetries": 0,
            "requestTimeoutSecs": 10, "outputFormats": ["raw"],
            "proxyConfiguration": {"useApifyProxy": False},
        }
        state["ultimoCalendario"] = now
        state.pop("diagnosiCalendario", None)
        STATE.parent.mkdir(exist_ok=True)
        engine._scrivi_json_atomico(str(STATE), state)
        run = api(auth, ATTORE_CALENDARI + "/runs", body, maxTotalChargeUsd=TETTO_CALENDARI,
                  waitForFinish=50, timeout=75)["data"]
        for _ in range(4):
            if run["status"] not in {"READY", "RUNNING", "TIMING-OUT", "ABORTING"}:
                break
            time.sleep(5)
            run = api(auth, "actor-runs/" + run["id"])["data"]
        report = {"fonte": AGENDA_CERIGNOLA, "stato": run["status"], "pianoGratuitoVerificato": True,
                  "tettoUsd": TETTO_CALENDARI, "costoUsd": run.get("usageTotalUsd"),
                  "eventiAddebitati": {"page-crawled": run.get("chargedEventCounts", {}).get("page-crawled", 0)}}
        try:
            diagnosi = diagnosi_calendario(auth, run)
            state["diagnosiCalendario"] = diagnosi
            engine._scrivi_json_atomico(str(STATE), state)
            report.update(diagnosi)
        except requests.RequestException:
            pass
        if run["status"] != "SUCCEEDED":
            return report
        rows = api(auth, "datasets/" + run["defaultDatasetId"] + "/items", limit=MASSIMO_PAGINE_CALENDARI,
                   fields="url,crawl,rawHtml", clean="true")
    if not isinstance(rows, list):
        raise Pausa("risultato calendario non verificabile")
    eventi, metriche = leggi_righe_calendario(rows, engine)
    engine._scrivi_json_atomico(str(OUTPUT), eventi)
    return dict(report, **metriche, righeRicevute=len(rows), validi=len(eventi))


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
        report = raccogli_calendario()
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
