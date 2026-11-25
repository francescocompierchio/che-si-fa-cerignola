"""Radar movida: ricerca per locale e formato, con città e data verificate a valle."""
import re
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

def fonti(registro,anagrafiche):
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
    # Organizzatori pubblicamente documentati: indizi di ricerca, mai alias
    # di una sede. Fonti storiche, non annunci di eventi futuri:
    # https://www.cerignolaviva.it/notizie/cerignola-summer-mood-chiude-con-stasera-con-uccio-in-piazza-duomo-arrivano-i-mudu/
    # https://www.cerignolaviva.it/notizie/notte-fantastica-2024-a-cerignola-guest-star-paola-chiara/
    # https://www.lanotiziaweb.it/venerdi-12-luglio-a-cerignola-il-music-beach-soccer-con-maninni-e-aka-7even/
    # DJ e vocalist del Beer Fun Fest 2025, programma pubblico:
    # https://www.cerignolaviva.it/notizie/festa-della-birra-in-piazza-della-repubblica-a-cerignola-birra-food-giochi-e-musica/
    # https://www.andreaordinemusic.it/ (sito professionale, non calendario)
    organizzatori_locali={"Cerignola":["Neverland Cerignola","Ideando Eventi","Luigi Sgaramella Eventi","Sgaramella Eventi","Andrea Ordine","Antonio Depalma","Nicola Lomuscio","Christian Antonacci"]}
    for comune,locali_reg in registro.items():
        for r in locali_reg:
            for nome in r.get("organizzatori",[]):
                if isinstance(nome,str) and 5<=len(nome)<=100 and '"' not in nome:
                    organizzatori_locali.setdefault(comune,[]).append(nome)
    for comune,nomi in organizzatori_locali.items():
        unici=list(dict.fromkeys(nomi))
        for i in range(0,len(unici),4):
            gruppo=unici[i:i+4]
            q='"'+comune+'" ('+" OR ".join('"'+n+'"' for n in gruppo)+") "+temi
            rss.append(feed(comune+" organizzatori "+str(i//4+1),q,comune))
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
    return dirette,rss
