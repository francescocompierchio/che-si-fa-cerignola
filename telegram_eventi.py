"""Ingresso Telegram opt-in: solo annunci destinati espressamente a Che Si Fa.

Nessuno scraping, nessun accesso alla cronologia, nessuna elaborazione AI dei
messaggi. L'allowlist è amministrata dal proprietario, non dagli utenti.
"""
import json
import os
import re
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import urlparse
import requests

STATE = Path("telegram-eventi.json")
PREFIX = "/evento_csf "
CANCEL = re.compile(r"^/annulla_csf(?: ([1-9][0-9]{0,12}))?$")
HANDLE = re.compile(r"^[A-Za-z][A-Za-z0-9_]{4,31}$")
TOKEN = re.compile(r"^[0-9]+:[A-Za-z0-9_-]{20,}$")
FIELDS = {"titolo", "dataInizio", "dataFine", "luogo", "indirizzoMappa", "descrizione", "costo", "orario", "locandinaUrl", "consenso"}
CONSENT = "Autorizzo la pubblicazione su Che Si Fa Cerignola"

def load_state(path=STATE):
    if not path.exists():
        return {"version":1,"offset":0,"events":{}}
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or value.get("version") != 1 or type(value.get("offset")) is not int or value["offset"] < 0 or not isinstance(value.get("events"), dict):
        raise ValueError("Stato Telegram non valido")
    if any(not isinstance(v,dict) or not v.get("telegramImportato") for v in value["events"].values()):
        raise ValueError("Archivio Telegram non valido")
    return value

def config(value):
    data = json.loads(value or "{}")
    if not isinstance(data, dict) or len(data)>100:
        raise ValueError("Registro Telegram non valido")
    for cid, v in data.items():
        if not re.fullmatch(r"-100[0-9]{5,15}", cid) or not isinstance(v,dict) or not HANDLE.fullmatch(str(v.get("username",""))) or not isinstance(v.get("comune"),str) or not v["comune"].strip():
            raise ValueError("Canale Telegram non valido")
        hosts=v.get("poster_hosts",[])
        if not isinstance(hosts,list) or any(not isinstance(h,str) or not re.fullmatch(r"[a-z0-9]+(?:[.-][a-z0-9]+)+",h) for h in hosts):
            raise ValueError("Domini locandine non validi")
    return data

def plain(value, limit, required=False):
    if not isinstance(value,str):
        raise ValueError("Campo non testuale")
    value = " ".join(value.split())
    if len(value)>limit or (required and not value) or any(ord(c)<32 for c in value) or "<" in value or ">" in value:
        raise ValueError("Campo non valido")
    return value

def poster_url(value, allowed):
    if not value:
        return ""
    p=urlparse(value)
    if p.scheme!="https" or p.hostname not in allowed or p.username or p.password or p.port not in (None,443) or p.query or p.fragment:
        raise ValueError("Locandina non autorizzata")
    if not re.search(r"\.(?:jpg|jpeg|png|webp|avif)$",p.path,re.I):
        raise ValueError("Formato locandina non valido")
    return value

def process(updates, state, channels, today, validate):
    """Riceve esclusivamente aggiornamenti Bot API; non memorizza messaggi grezzi."""
    result={"version":1,"offset":state["offset"],"events":{k:v for k,v in state["events"].items() if v.get("dataFine","")>=today.isoformat()}}
    count={"accettati":0,"annullati":0,"ignorati":0}
    for update in sorted(updates,key=lambda u:u.get("update_id",0)):
        uid=update.get("update_id")
        if type(uid) is not int or uid<result["offset"]:
            continue
        result["offset"]=uid+1
        post=update.get("channel_post") or update.get("edited_channel_post") or {}
        chat=post.get("chat") or {}
        channel=channels.get(str(chat.get("id")))
        mid=post.get("message_id")
        if not channel or chat.get("type")!="channel" or str(chat.get("username","")).casefold()!=channel["username"].casefold() or type(mid) is not int or mid<=0:
            count["ignorati"]+=1
            continue
        text=post.get("text") or post.get("caption") or ""
        if not isinstance(text,str) or len(text)>4000 or post.get("forward_origin"):
            count["ignorati"]+=1
            continue
        cancel=CANCEL.fullmatch(text.strip())
        if cancel:
            key=channel["username"].lower()+"/"+str(cancel.group(1) or mid)
            if result["events"].pop(key,None) is not None:
                count["annullati"]+=1
            continue
        if not text.startswith(PREFIX):
            count["ignorati"]+=1
            continue
        try:
            item=json.loads(text[len(PREFIX):])
            if not isinstance(item,dict) or set(item)-FIELDS or item.get("consenso")!=CONSENT:
                raise ValueError("Consenso o schema assente")
            start=plain(item.get("dataInizio",""),10,True)
            end=plain(item.get("dataFine",start),10,True)
            d1,d2=date.fromisoformat(start),date.fromisoformat(end)
            if start!=d1.isoformat() or end!=d2.isoformat() or d1>d2 or d2<today or d1>today+timedelta(days=180) or (d2-d1).days>30:
                raise ValueError("Date non valide")
            title=plain(item.get("titolo",""),85,True)
            place=plain(item.get("luogo",""),100,True)
            desc=plain(item.get("descrizione",""),220,True)
            if re.search(r"\b(?:cronaca|arrestat\w*|arresto|omicidi\w*|furto|rapina|incidente stradale|elezioni|comizio|consiglio comunale|convegno|seminario)\b", title+" "+desc, re.I):
                raise ValueError("Annuncio non pertinente")
            address=plain(item.get("indirizzoMappa",""),140,True)
            # La città deve essere esplicita, non inferita dal registro del canale.
            if "," not in address or address.rsplit(",",1)[-1].strip().casefold()!=channel["comune"].strip().casefold():
                raise ValueError("Indirizzo senza comune autorizzato")
            hour=plain(item.get("orario",""),5)
            if hour and not re.fullmatch(r"(?:[01][0-9]|2[0-3]):[0-5][0-9]",hour):
                raise ValueError("Orario non valido")
            cost=plain(item.get("costo",""),100)
            poster=poster_url(plain(item.get("locandinaUrl",""),300),channel.get("poster_hosts",[]))
            # Solo i dati deliberatamente inviati per la pubblicazione; mai nomi utente dei visitatori.
            source="https://t.me/"+channel["username"]+"/"+str(mid)
            raw={"titolo":title,"dataInizio":start,"dataFine":end,"luogo":place,"indirizzoMappa":address,"descrizione":desc,"citta":channel["comune"],"costo":cost,"fonteUrl":source}
            if poster:
                raw["locandinaUrl"]=poster
            ev=validate(raw)
            if not ev or ev.get("citta")!=channel["comune"]:
                raise ValueError("Evento fuori area o non pertinente")
            if hour:
                ev["dataTesto"]+=" · Ore "+hour
            ev["telegramImportato"]=True
            result["events"][channel["username"].lower()+"/"+str(mid)]=ev
            count["accettati"]+=1
        except (ValueError,TypeError,KeyError):
            count["ignorati"]+=1
    return result,count

def collect(today, validate, path=STATE, session=requests):
    state=load_state(path)
    token=os.environ.get("TELEGRAM_EVENT_BOT_TOKEN","").strip()
    setting=os.environ.get("TELEGRAM_EVENT_CHANNELS","")
    empty={"version":1,"offset":state["offset"],"events":{k:v for k,v in state["events"].items() if v.get("dataFine","")>=today.isoformat()}}
    if not token or not setting:
        return empty,{"stato":"non_configurato","accettati":0,"annullati":0,"ignorati":0}
    try:
        channels=config(setting)
        if not channels or not TOKEN.fullmatch(token):
            return empty,{"stato":"non_configurato","accettati":0,"annullati":0,"ignorati":0}
        # Offset confermato solo dopo il commit atomico di archivio e stato su main.
        # Se il push fallisce, la prossima esecuzione ripete il lotto senza perdere eventi.
        res=session.post("https://api.telegram.org/bot"+token+"/getUpdates",json={"offset":state["offset"],"limit":100,"timeout":0,"allowed_updates":["channel_post","edited_channel_post"]},timeout=(4,12),allow_redirects=False)
        if res.status_code!=200:
            raise ValueError("Bot API non disponibile")
        payload=res.json()
        if not payload.get("ok") or not isinstance(payload.get("result"),list):
            raise ValueError("Risposta Bot API non valida")
        new,counts=process(payload["result"],state,channels,today,validate)
        return new,{"stato":"ok",**counts}
    except (requests.RequestException,ValueError,TypeError,KeyError):
        # Non includere mai URL, token, corpo della risposta o messaggi nel log.
        return empty,{"stato":"errore","accettati":0,"annullati":0,"ignorati":0}
