"""Radar movida: ricerca per locale e formato, con città e data verificate a valle."""
import re
import json
from pathlib import Path
from datetime import date
import capodanno
from urllib.parse import urlencode,urlparse

FORMATI=re.compile(r"\b(?:jam session|open mic|quiz game|music quiz|cervellone|tribut[oi]|tribute|live|dj[\s-]*set|deejay|karaoke|clubbing|discotec\w*|club night|party|apericena|aperitivo musicale|dinner show|cena spettacolo|serata latin[ae]|bachata|salsa|reggaeton|techno|house music|musica dal vivo|vinyl di wine|vinyl set|music selection|opening(?: winter| summer)? season|opening party|serata a tema|serata anni|piano bar)\b",re.I)
LIVE=re.compile(r"\b(?:concerto|concerti|jazz|rock|blues|band|jam session|live|musica dal vivo|tribut[oi]|tribute)\b",re.I)
SCARTO=re.compile(r"\b(?:convegno|seminario|presentazione del libro|annullat[oa]|rinviat[oa]|cronaca|arrestat[oa]|incidente)\b",re.I)
SEDI=re.compile(r"\b(?:pub|discopub|disco bar|club|lounge|bistrot|wine bar|bar|bohemien|bohémien|santo graal|cafe des artistes|café des artistes|da sergio e davide|cialuna)\b",re.I)
def pertinente(testo):
    return bool(FORMATI.search(testo or "") and not SCARTO.search(testo or ""))

def alias_corrispondente(testo,alias):
    return any(re.search(r"(?<!\w)"+re.escape(x)+r"(?!\w)",testo or "",re.I) for x in alias if isinstance(x,str) and len(x)>=5)

def live_in_locale(titolo,descrizione,sede,registro=()):
    testo=titolo+" "+descrizione
    return bool(not SCARTO.search(titolo) and LIVE.search(testo) and
                (SEDI.search(sede) or alias_corrispondente(sede,registro)) and
                not re.search(r"\b(?:teatro|auditorium|chiesa|cattedrale)\b",sede,re.I))

def registro_promoter():
    try:
        data=json.loads(Path(__file__).with_name("fonti_promoter.json").read_text(encoding="utf-8"))
        return [r for r in data if isinstance(r,dict)] if isinstance(data,list) else []
    except (OSError,ValueError):
        return []

def profilo_social(url):
    """Accetta soltanto profili pubblici esplicitamente registrati, non reel/post."""
    p=urlparse(str(url or ""))
    host=(p.hostname or "").removeprefix("www.")
    handle=p.path.strip("/")
    if p.scheme!="https" or host not in {"instagram.com","facebook.com"} or not re.fullmatch(r"[\w.-]{3,80}",handle,re.ASCII):
        return None
    if handle.casefold() in {"p","reel","reels","posts","stories","share","events","groups","login","explore","watch"}:
        return None
    return host,handle

def fonti(registro,anagrafiche,oggi=None,promoter=None):
    dirette=[];rss=[]
    def feed(nome,q,comune="",alias=()):
        return {"nome":"Radar Movida - "+nome,"url":"https://news.google.com/rss/search?"+urlencode({"q":q+" when:30d","hl":"it","gl":"IT","ceid":"IT:it"}),
                "radar_movida":True,"nightlife":True,"focus_serate":True,"prioritaria":comune=="Cerignola","solo_cerignola":comune=="Cerignola","comune_radar":comune,"alias_movida":list(alias),"max_schede_rss":4}
    temi='("dj set" OR karaoke OR "jam session" OR "quiz game" OR "cena spettacolo" OR "musica dal vivo" OR "serata a tema" OR party OR "aperitivo musicale" OR "soft clubbing" OR "live music")'
    # Calendari effettivi di singoli locali: niente pagine anagrafiche convertite in eventi.
    for comune,locali in registro.items():
        for r in locali:
            url=r.get("calendario","")
            host=urlparse(url).hostname or ""
            path=urlparse(url).path
            if (host.endswith("iltaccodibacco.it") and re.fullmatch(r"/[^/]+/[^/]+/?",path)) or (host.removeprefix("www.")=="manfredoniaeventi.com" and re.match(r"/(?:luogo|organizzatore)/",path)):
                dirette.append({"nome":"Radar calendario "+r["nome"],"url":url,"dominio":host,"curata":False,"nightlife":True,"focus_serate":True,"radar_movida":True,"comune_radar":comune,"alias_movida":r.get("alias",[]),"prefisso_schede":"/puglia/eventi/" if host.endswith("iltaccodibacco.it") else "/evento/","max_schede":8,"solo_cerignola":comune=="Cerignola"})
    for nome,tema in [
        ("DJ e discoteche",'("dj set" OR discoteca OR "club night" OR techno OR "soft clubbing")'),
        ("Karaoke quiz e giochi",'(karaoke OR "quiz game" OR cervellone OR "music quiz" OR "open mic")'),
        ("Pub e musica",'("jam session" OR "musica dal vivo" OR "cover band" OR tribute OR "live music")'),
        ("Cena e aperitivo",'("dinner show" OR "cena spettacolo" OR apericena OR "aperitivo musicale")'),
        ("Ballo e serate a tema",'(bachata OR salsa OR "serata latina" OR "serata anni" OR "serata a tema")'),
    ]:
        rss.append(feed("Cerignola "+nome,"Cerignola "+tema,"Cerignola"))
    # Ricerche per gruppi piccoli, anche senza comune nello snippet: il luogo
    # e la data devono comunque essere documentati nella pagina originale.
    locali=list(registro.get("Cerignola",[]))+[r for r in anagrafiche if r.get("gruppo")=="movida"]
    alias=list(dict.fromkeys(a for r in locali for a in r.get("alias",[]) if len(a)>=5 and '"' not in a))
    for i in range(0,len(alias),6):
        gruppo=alias[i:i+6]
        nomi="("+" OR ".join('"'+x+'"' for x in gruppo)+")"
        rss.append(feed("Cerignola profili "+str(i//6+1),nomi+" "+temi+" (Cerignola OR site:instagram.com OR site:facebook.com)","Cerignola",gruppo))
    # Query corte per intercettare annunci che non usano le formule tipiche.
    # Le fonti originali devono ancora documentare data, sede e città.
    for nome,tema in [
        ("Annunci brevi", '("serata" OR "evento" OR "party") (pub OR locale OR cocktail OR club)'),
        ("DJ grafie alternative", '(dj OR "dj-set" OR deejay OR "disc jockey")'),
        ("Musica e intrattenimento", '(karaoke OR "live" OR "cover band" OR "quiz" OR "musica live")'),
        ("Stampa locale", '(site:cerignolaviva.it OR site:lanotiziaweb.it OR site:marchiodoc.it) (dj OR karaoke OR "serata musicale" OR "cena spettacolo")'),
    ]:
        rss.append(feed("Cerignola "+nome,"Cerignola "+tema,"Cerignola"))
    # Il dominio ufficiale o l'handle sono segnali di discovery, non prove.
    # Non leggere profili privati, storie o pagine dietro autenticazione.
    visti=set()
    for r in locali:
        for campo in ("sito","social"):
            url=r.get(campo,"")
            host=(urlparse(url).hostname or "").removeprefix("www.")
            if not host or urlparse(url).scheme!="https" or url in visti:
                continue
            visti.add(url)
            if host in {"instagram.com","facebook.com"}:
                handle=urlparse(url).path.strip("/").split("/")[0]
                if not re.fullmatch(r"[a-zA-Z0-9_.-]{3,80}",handle):
                    continue
                q=f'site:{host} "{handle}" (dj OR live OR serata OR party OR karaoke)'
            else:
                q=f'site:{host} (evento OR serata OR musica OR dj OR karaoke)'
            rss.append(feed("Cerignola fonte "+r["nome"]+" "+campo,q,"Cerignola",r.get("alias",[])))
    for comune in ("Stornara","Stornarella","Orta Nova","Trinitapoli","San Ferdinando di Puglia","Canosa di Puglia","Lavello","Margherita di Savoia","Foggia","Barletta","Trani","Manfredonia","Bisceglie","Andria","Melfi","Venosa"):
        rss.append(feed(comune,'"'+comune+'" '+temi,comune))
    # Copertura indipendente da Apify: nomi e handle indicizzati, anche
    # Facebook e calendari social. Raggruppa al massimo quattro profili,
    # mantenendo il comune come vincolo sui risultati e non come prova.
    for comune,righe in registro.items():
        if comune=="Cerignola":
            righe=locali
        profili={}
        for r in righe:
            for campo in ("social","facebook","calendario"):
                profile=profilo_social(r.get(campo))
                if not profile:
                    continue
                host,handle=profile
                # Le vecchie ricerche individuali locali coprono già il campo social.
                if comune=="Cerignola" and profile==profilo_social(r.get("social")):
                    continue
                profili.setdefault(host,{}).setdefault(handle.casefold(),(handle,list(r.get("alias",[]))))
        for host,entries in sorted(profili.items()):
            gruppi=list(entries.values())
            for i in range(0,len(gruppi),4):
                blocco=gruppi[i:i+4]
                handles="("+" OR ".join('"'+h+'"' for h,_ in blocco)+")"
                alias=list(dict.fromkeys(x for h,aa in blocco for x in [h]+aa if isinstance(x,str) and len(x)>=5))
                rss.append(feed(f"{comune} profili pubblici {host} {i//4+1}",f"site:{host} {handles} {temi}",comune,alias))
        if comune!="Cerignola":
            alias=list(dict.fromkeys(x for r in righe for x in r.get("alias",[]) if isinstance(x,str) and len(x)>=5 and '"' not in x))
            for i in range(0,len(alias),6):
                blocco=alias[i:i+6]
                nomi="("+" OR ".join('"'+x+'"' for x in blocco)+")"
                rss.append(feed(f"{comune} locali nominativi {i//6+1}",f'{nomi} "{comune}" {temi}',comune,blocco))
    # Promoter regionali: non attribuire automaticamente il comune della sede
    # del promoter. La località deve provenire dalla singola scheda originale.
    for r in (registro_promoter() if promoter is None else promoter):
        profile=profilo_social(r.get("social"))
        nome=r.get("nome","")
        if profile and isinstance(nome,str) and nome:
            host,handle=profile
            alias=[x for x in (nome,handle) if len(x)>=5]
            rss.append(feed("Promoter pubblico "+nome,f'site:{host} "{handle}" {temi}',"",alias))
            # Una ricerca generica regionale satura il budget con risultati
            # lontani. Due ricerche mirate separano le zone e usano una finestra
            # più recente; non assumono mai la città a partire dalla query.
            if host=="instagram.com":
                for zona,comuni in (("Cerignola e Reali Siti",'(Cerignola OR "Orta Nova" OR Stornara OR Stornarella OR Canosa OR Trinitapoli OR "San Ferdinando di Puglia")'),("Foggia e costa",'(Foggia OR Manfredonia OR Barletta OR Trani OR Bisceglie OR Andria)')):
                    f=feed("Promoter mirato "+nome+" "+zona,f'site:{host} "{handle}" {comuni} (karaoke OR "piano bar" OR "dj set" OR "musica dal vivo" OR "serata" OR "cena spettacolo")',"",alias)
                    f["url"]=f["url"].replace("when%3A30d","when%3A7d")
                    f["promoter_mirato"]=True
                    rss.append(f)
    # Solo in stagione, con il validatore Capodanno dedicato: il filtro
    # nightlife generico scarterebbe i pranzi e i cenoni senza DJ.
    anno=capodanno.stagione(oggi or date.today())
    if anno is not None:
        for comune in ("Cerignola","Stornara","Stornarella","Orta Nova","Canosa di Puglia","San Ferdinando di Puglia","Trinitapoli","Lavello","Margherita di Savoia","Ascoli Satriano","Ordona","Carapelle"):
            f=feed(comune+" feste e cenoni",f'"{comune}" ("cenone" OR "veglione" OR "pranzo di Capodanno" OR "cenone di San Silvestro" OR "festa di fine anno") ({anno} OR {anno+1})',comune)
            f.update(anno_capodanno=anno,comune_capodanno=comune,nightlife=False,radar_movida=False)
            rss.append(f)
    return dirette,rss
