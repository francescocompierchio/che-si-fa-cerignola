"""Legge un elenco esplicito di profili autorizzati tramite Meta Graph API."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlsplit
import json
import os
import re

import requests

STATE = Path(".csf-state/meta.json")
REPORT = Path("meta-rapporto.json")
OUTPUT = Path("meta-eventi.json")
GRAPH = "https://graph.facebook.com/"
MAX_PER_CYCLE = 2


def selezione(env):
    version = env.get("META_GRAPH_VERSION", "").strip()
    profiles = []
    report = {}
    id_pattern = r"[1-9][0-9]{4,24}"
    for kind, list_key, token_key, pattern in (
        ("instagram", "META_IG_PROFILES", "META_IG_ACCESS_TOKEN", r"[a-z0-9_][a-z0-9._]{0,29}"),
        ("facebook", "META_FB_PAGE_IDS", "META_FB_ACCESS_TOKEN", id_pattern),
    ):
        required = ["META_GRAPH_VERSION", list_key, token_key]
        if kind == "instagram":
            required.append("META_IG_ACCOUNT_ID")
        missing = [key for key in required if not env.get(key, "").strip()]
        targets = dict.fromkeys(t.removeprefix("@") if kind == "instagram" else t
                                for t in re.split(r"[\s,]+", env.get(list_key, "").strip().lower()) if t)
        valid = [target for target in targets if re.fullmatch(pattern, target)]
        invalid = []
        owner = env.get("META_IG_ACCOUNT_ID", "").strip() if kind == "instagram" else ""
        if version and not re.fullmatch(r"v[1-9][0-9]\.0", version):
            invalid.append("META_GRAPH_VERSION")
        if owner and not re.fullmatch(id_pattern, owner):
            invalid.append("META_IG_ACCOUNT_ID")
        if env.get(list_key, "").strip() and not valid:
            invalid.append(list_key)
        if not (missing or invalid):
            profiles.extend((kind, target, owner or target, env[token_key].strip()) for target in valid[:30])
        report[kind] = {"stato": "non_configurato" if missing else "configurazione_non_valida" if invalid else "configurato",
                        "impostazioniMancanti": missing, "impostazioniNonValide": invalid,
                        "fontiConfigurate": min(len(valid), 30), "vociScartate": len(targets) - len(valid)}
    return version, profiles, report


def stato_graph(status, payload):
    errore = payload.get("error") if isinstance(payload, dict) else None
    code = errore.get("code") if isinstance(errore, dict) else None
    if type(code) is not int:
        return 400 if errore and status == 200 else status
    if code == 190:
        return 401
    if code in (4, 17, 32, 341, 613):
        return 429
    if code in (3, 10, 368) or 200 <= code <= 299:
        return 403
    return 400 if status == 200 else status


def leggi(session, version, profile):
    kind, target, owner, token = profile
    params = {"limit": 4, "fields": "message,permalink_url,created_time"}
    path = f"{version}/{owner}/posts"
    if kind == "instagram":
        path = f"{version}/{owner}"
        params = {"fields": f"business_discovery.username({target}){{media.limit(4){{caption,permalink,timestamp}}}}"}
    with session.get(GRAPH + path, params=params, headers={"Authorization":"Bearer " + token},
                     timeout=(4, 9), allow_redirects=False, stream=True) as r:
        if r.status_code not in (200, 400):
            return [], r.status_code
        body = bytearray()
        for chunk in r.iter_content(8192):
            body.extend(chunk)
            if len(body) > 128 * 1024:
                return [], 413
        try:
            data = json.loads(body)
        except (ValueError, TypeError):
            return [], 400 if r.status_code == 400 else 502
        status = stato_graph(r.status_code, data)
    if status != 200:
        return [], status
    if not isinstance(data, dict):
        return [], 400
    if kind == "instagram":
        discovery = data.get("business_discovery")
        if not isinstance(discovery, dict):
            return [], 404
        data = discovery.get("media", {})
    rows = data.get("data", [])
    return rows[:4] if isinstance(rows, list) else [], 200


def eventi_da_post(engine, rows, kind, now):
    out = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        caption = row.get("caption") if kind == "instagram" else row.get("message")
        url = row.get("permalink") if kind == "instagram" else row.get("permalink_url")
        stamp = row.get("timestamp") if kind == "instagram" else row.get("created_time")
        if not isinstance(caption, str) or not isinstance(url, str) or not isinstance(stamp, str):
            continue
        try:
            parts = urlsplit(url)
            publication = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
            if parts.scheme != "https" or parts.username or parts.password or parts.port is not None:
                continue
            hosts = {"instagram.com"} if kind == "instagram" else {"facebook.com", "m.facebook.com"}
            if (parts.hostname or "").removeprefix("www.") not in hosts or not parts.path.strip("/"):
                continue
            if not now - timedelta(days=30) <= publication <= now + timedelta(minutes=5):
                continue
        except (ValueError, TypeError):
            continue
        if kind == "instagram":
            if not re.fullmatch(r"/(?:p|reel|tv)/[A-Za-z0-9_-]+/?", parts.path):
                continue
            url = parts._replace(query="", fragment="").geturl()
        else:
            url = parts._replace(fragment="").geturl()
        caption = caption[:6000]
        title = next((line.strip()[:100] for line in caption.splitlines() if len(line.strip()) >= 5), "")
        if title:
            out.extend(e for e in engine.eventi_da_locandina(caption, "", title, url)
                       if engine.discovery_locale.data_coerente_pubblicazione(e, publication.date()))
    return out


def raccogli(engine, env=os.environ, now=None, session=requests):
    version, profiles, report = selezione(env)
    if not profiles:
        status = "configurazione_non_valida" if any(r["impostazioniNonValide"] for r in report.values()) else "non_configurato"
        return [], {"stato":status, **report}
    if now is None:
        now = datetime.now(timezone.utc)
    data = json.loads(STATE.read_text(encoding="utf-8")) if STATE.is_file() else {}
    epoch = int(now.timestamp())
    results = []
    esiti = {}
    for kind in ("instagram", "facebook"):
        candidates = [p for p in profiles if p[0] == kind]
        if not candidates:
            continue
        report[kind]["stato"] = "pausa"
        if data.get(f"pausa/{kind}", 0) > epoch:
            continue
        for profile in sorted(candidates, key=lambda p: data.get(f"{p[0]}/{p[1]}", 0))[:MAX_PER_CYCLE]:
            key = f"{profile[0]}/{profile[1]}"
            if data.get(key, 0) > epoch - 4*3600:
                continue
            data[key] = epoch
            try:
                rows, status = leggi(session, version, profile)
                results.extend(eventi_da_post(engine, rows, kind, now))
            except (requests.RequestException, ValueError, TypeError, AttributeError):
                status = 0
            label = f"{kind}/{status}"
            esiti[label] = esiti.get(label, 0) + 1
            if status == 200 or report[kind]["stato"] != "ok":
                report[kind]["stato"] = "ok" if status == 200 else "errore"
            if status in (401, 403, 429):
                data[f"pausa/{kind}"] = epoch + 4*3600
                break
    STATE.parent.mkdir(exist_ok=True)
    engine._scrivi_json_atomico(str(STATE), {k:v for k,v in data.items() if v > epoch - 30*86400})
    status = "ok" if any(r["stato"] == "ok" for r in report.values()) else "errore" if esiti else "pausa"
    return results, {"stato":status, "esiti":esiti, "eventi":len(results), **report}


if __name__ == "__main__":
    import aggiorna_eventi as engine
    OUTPUT.unlink(missing_ok=True)
    try:
        eventi, rapporto = raccogli(engine)
        engine._scrivi_json_atomico(str(OUTPUT), eventi)
    except (OSError, ValueError, TypeError, AttributeError):
        rapporto = {"stato":"indisponibile"}
    engine._scrivi_json_atomico(str(REPORT), rapporto)
    print(json.dumps(rapporto))
