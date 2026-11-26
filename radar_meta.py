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
    version = env.get("META_GRAPH_VERSION", "")
    if not re.fullmatch(r"v[1-9][0-9]\.0", version):
        return "", []
    profiles = []
    igid = env.get("META_IG_ACCOUNT_ID", "")
    ig_token = env.get("META_IG_ACCESS_TOKEN", "")
    if ig_token and re.fullmatch(r"[1-9]\d{4,24}", igid):
        handles = dict.fromkeys(env.get("META_IG_PROFILES", "").lower().split())
        for handle in list(handles)[:30]:
            if re.fullmatch(r"[a-z0-9_][a-z0-9._]{0,29}", handle):
                profiles.append(("instagram", handle, igid, ig_token))
    fb_token = env.get("META_FB_ACCESS_TOKEN", "")
    if fb_token:
        pages = dict.fromkeys(env.get("META_FB_PAGE_IDS", "").split())
        for page in list(pages)[:30]:
            if re.fullmatch(r"[1-9]\d{4,24}", page):
                profiles.append(("facebook", page, page, fb_token))
    return version, profiles


def leggi(session, version, profile):
    kind, target, owner, token = profile
    params = {"limit": 4, "fields": "message,permalink_url,created_time"}
    path = f"{version}/{owner}/posts"
    if kind == "instagram":
        path = f"{version}/{owner}"
        params = {"fields": f"business_discovery.username({target}){{media.limit(4){{caption,permalink,timestamp}}}}"}
    with session.get(GRAPH + path, params=params, headers={"Authorization":"Bearer " + token},
                     timeout=(4, 9), allow_redirects=False, stream=True) as r:
        if r.status_code != 200:
            return [], r.status_code
        body = bytearray()
        for chunk in r.iter_content(8192):
            body.extend(chunk)
            if len(body) > 128 * 1024:
                return [], 413
        data = json.loads(body)
    if not isinstance(data, dict) or data.get("error"):
        return [], 400
    if kind == "instagram":
        data = data.get("business_discovery", {}).get("media", {})
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
    version, profiles = selezione(env)
    if not profiles:
        return [], {"stato":"non_configurato"}
    if now is None:
        now = datetime.now(timezone.utc)
    data = json.loads(STATE.read_text(encoding="utf-8")) if STATE.is_file() else {}
    epoch = int(now.timestamp())
    results = []
    esiti = {}
    for kind in ("instagram", "facebook"):
        candidates = [p for p in profiles if p[0] == kind]
        if not candidates or data.get(f"pausa/{kind}", 0) > epoch:
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
            if status in (401, 403, 429):
                data[f"pausa/{kind}"] = epoch + 4*3600
                break
    STATE.parent.mkdir(exist_ok=True)
    engine._scrivi_json_atomico(str(STATE), {k:v for k,v in data.items() if v > epoch - 30*86400})
    return results, {"stato":"ok" if esiti else "pausa", "esiti":esiti, "eventi":len(results)}


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
