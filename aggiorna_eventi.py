import os
import re
import json
import io
import time
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from threading import Lock, BoundedSemaphore
from difflib import SequenceMatcher
from urllib.parse import parse_qs, urljoin, urlparse, urlencode
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
from html import escape, unescape
from zoneinfo import ZoneInfo
import stato_raccolta
import capodanno
import festivita
import ricorrenze

GIORNI_ANTICIPO_MAX = 180

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "it-IT,it;q=0.9"
}

DOMINI_AUTO = (
    "canosaweb.it", "minervinoviva.it", "volontariperminervino.it", "andiamoinpuglia.it",
    "news.google.com", "iltaccodibacco.it", "viaggiareinpuglia.it",
    "pugliaevents.it", "eventiesagre.it", "eventbrite.it",
    "lanotiziaweb.it", "marchiodoc.it", "cerignolaviva.it",
    "canosaviva.it", "barlettaviva.it", "traniviva.it",
    "bisceglieviva.it", "andriaviva.it", "statoquotidiano.it",
    "immediato.net", "vulturenews.net", "foggia.today", "lagazzettadelmezzogiorno.it",
    "teatromercadantecerignola.it", "romateatrocinema.it", "teatrogiordano.it",
    "palazzodelleartibeltrani.it", "politeamaitalia.com",
    "happyticket.com", "pugliaculture.it", "ciaotickets.com", "virgilio.it",
    "buzzeventmap.com", "paesionline.it", "2d2web.com", "piazzainfesta.it",
    "masseriapavoni.com", "agriturismomoschella.com", "instagram.com", "facebook.com",
    "aivents.it", "experience-app.com", "comune.cerignola.fg.it", "foggiareporter.it", "cosedicasa.live", "manfredoniaeventi.com", "linea.live", "xceed.me", "ticketsms.it", "nightz.it", "lineupatlas.com", "villabautier.com", "villademetra.it", "villatorrequarto.it", "ricevimentilavenere.it", "masseriabelvedereeventi.it", "agriturismomasseriacafora.it", "lucera.it", "identitagolose.it", "lucianopignataro.it", "gustoh24.it", "garganofm.com"
)

FONTI_VIVA = [
    {"nome": "MinervinoViva Eventi", "url": "https://www.minervinoviva.it/eventi/", "dominio": "minervinoviva.it", "citta_default": "Minervino Murge", "solo_eventi": True},
    {"nome": "MinervinoViva Notizie", "url": "https://www.minervinoviva.it/notizie/", "dominio": "minervinoviva.it", "citta_default": "Minervino Murge", "solo_eventi": False},
    {"nome": "CerignolaViva Eventi", "url": "https://www.cerignolaviva.it/eventi/", "dominio": "cerignolaviva.it", "citta_default": "Cerignola", "solo_eventi": True},
    {"nome": "CerignolaViva Notizie", "url": "https://www.cerignolaviva.it/notizie/", "dominio": "cerignolaviva.it", "citta_default": "Cerignola", "solo_eventi": False},
    {"nome": "CanosaViva Eventi", "url": "https://www.canosaviva.it/eventi/", "dominio": "canosaviva.it", "citta_default": "Canosa di Puglia", "solo_eventi": True},
    {"nome": "CanosaViva Notizie", "url": "https://www.canosaviva.it/notizie/", "dominio": "canosaviva.it", "citta_default": "Canosa di Puglia", "solo_eventi": False},
    {"nome": "BarlettaViva Eventi", "url": "https://www.barlettaviva.it/eventi/", "dominio": "barlettaviva.it", "citta_default": "Barletta", "solo_eventi": True},
    {"nome": "BarlettaViva Notizie", "url": "https://www.barlettaviva.it/notizie/", "dominio": "barlettaviva.it", "citta_default": "Barletta", "solo_eventi": False},
    {"nome": "TraniViva Eventi", "url": "https://www.traniviva.it/eventi/", "dominio": "traniviva.it", "citta_default": "Trani", "solo_eventi": True},
    {"nome": "TraniViva Notizie", "url": "https://www.traniviva.it/notizie/", "dominio": "traniviva.it", "citta_default": "Trani", "solo_eventi": False},
    {"nome": "BisceglieViva Eventi", "url": "https://www.bisceglieviva.it/eventi/", "dominio": "bisceglieviva.it", "citta_default": "Bisceglie", "solo_eventi": True},
    {"nome": "BisceglieViva Notizie", "url": "https://www.bisceglieviva.it/notizie/", "dominio": "bisceglieviva.it", "citta_default": "Bisceglie", "solo_eventi": False},
    {"nome": "AndriaViva Eventi", "url": "https://www.andriaviva.it/eventi/", "dominio": "andriaviva.it", "citta_default": "Andria", "solo_eventi": True},
    {"nome": "AndriaViva Notizie", "url": "https://www.andriaviva.it/notizie/", "dominio": "andriaviva.it", "citta_default": "Andria", "solo_eventi": False}
]

FONTI_PORTALI = [
    {"nome":"Comune Cerignola eventi culturali","url":"https://comune.cerignola.fg.it/tipi_evento/evento-culturale/","dominio":"comune.cerignola.fg.it","citta_default":"Cerignola","curata":True,"prefisso_schede":"/vivere-il-comune/eventi/","max_schede":16},
    {"nome":"Cose di Casa Antiquariando","url":"https://www.cosedicasa.live/mercatini/cerignola-antiquariando","dominio":"cosedicasa.live","citta_default":"Cerignola","curata":True,"scheda_diretta":True},
    {"nome":"Comune Cerignola Tempo Libero","url":"https://comune.cerignola.fg.it/argomento/tempo-libero/","dominio":"comune.cerignola.fg.it","citta_default":"Cerignola","curata": True,"max_schede":16,"prefisso_schede":"/vivere-il-comune/eventi/"},
    {"nome":"Comune Cerignola Manifestazioni Artistiche","url":"https://comune.cerignola.fg.it/tipi_evento/manifestazione-artistica/","dominio":"comune.cerignola.fg.it","citta_default":"Cerignola","curata": True,"max_schede":16,"prefisso_schede":"/vivere-il-comune/eventi/"},
    {"nome":"Comune Cerignola Associazioni","url":"https://comune.cerignola.fg.it/argomento/associazioni/","dominio":"comune.cerignola.fg.it","citta_default":"Cerignola","curata": True,"max_schede":16,"prefisso_schede":"/vivere-il-comune/eventi/"},
    {"nome":"CerignolaViva Cultura e appuntamenti","url":"https://www.cerignolaviva.it/notizie/?cat=cultura","dominio":"cerignolaviva.it","citta_default":"Cerignola","curata": False,"max_schede":20,"prefisso_schede":"/notizie/"},
    {"nome":"Marchiodoc Cerignola eventi","url":"https://www.marchiodoc.it/","dominio":"marchiodoc.it","citta_default":"","curata": False,"max_schede":12,"notizie_locali": True},
    {"nome":"Lucera.it eventi Cerignola","url":"https://www.lucera.it/eventi/","dominio":"lucera.it","citta_default":"","curata": False,"max_schede":10,"notizie_locali": True,"prefisso_schede":"/eventi/"},
    {"nome":"CanosaWeb eventi locali","url":"https://canosaweb.it/eventi/","dominio":"canosaweb.it","citta_default":"Canosa di Puglia","curata":False,"notizie_locali":True,"prefisso_schede":"/notizie/","max_schede":12},
    {"nome":"Comune Cerignola agenda ufficiale","url":"https://comune.cerignola.fg.it/vivere-il-comune/eventi/","dominio":"comune.cerignola.fg.it","citta_default":"Cerignola","curata":True,"prefisso_schede":"/vivere-il-comune/eventi/","max_schede":20},
    {"nome":"Volontari per Minervino - iniziative","url":"https://volontariperminervino.it/","dominio":"volontariperminervino.it","citta_default":"Minervino Murge","curata":False,"notizie_locali":True,"max_schede":8},
    {"nome":"Tacco di Bacco concerti Barletta","url":"https://iltaccodibacco.it/barletta/concerti/","dominio":"iltaccodibacco.it","citta_default":"","curata":True,"prefisso_schede":"/puglia/eventi/","nightlife":True,"max_schede":12},
    {"nome":"Tacco di Bacco concerti Bisceglie","url":"https://iltaccodibacco.it/bisceglie/concerti/","dominio":"iltaccodibacco.it","citta_default":"","curata":True,"prefisso_schede":"/puglia/eventi/","nightlife":True,"max_schede":12},
    {"nome": "Nightz eventi", "url": "https://nightz.it/eventi/", "browser_pubblico": True, "dominio": "nightz.it", "citta_default": "", "curata": True, "nightlife": True, "nightz": True, "max_schede": 20},
    {"nome": "Nightz Divine Club", "url": "https://nightz.it/locali/divine-club/", "dominio": "nightz.it", "citta_default": "", "curata": True, "nightlife": True, "nightz": True, "max_schede": 10},
    {"nome": "Nightz Aphelion Club", "url": "https://nightz.it/locali/aphelion-club/", "dominio": "nightz.it", "citta_default": "", "curata": True, "nightlife": True, "nightz": True, "max_schede": 10},
    {"nome": "Nightz Vyon Club", "url": "https://nightz.it/locali/vyon-club/", "dominio": "nightz.it", "citta_default": "", "curata": True, "nightlife": True, "nightz": True, "max_schede": 10},
    {"nome":"TicketSms Idol Club Bisceglie","browser_pubblico": True,"url":"https://www.ticketsms.it/it/location/Idol-Club","dominio":"ticketsms.it","citta_default":"Bisceglie","curata": True,"nightlife": True,"ticketsms": True,"luogo_atteso":"Idol Club","max_schede":12},
    {"nome":"Xceed promoter Aphelion","url":"https://xceed.me/it/organizer/aphelion-club-1","dominio":"xceed.me","citta_default":"Trani","curata": True,"nightlife": True,"xceed": True,"prefisso_schede":"/it/trani/event/","max_schede":12},
    {"nome":"ManfredoniaEventi categoria Nightlife","url":"https://www.manfredoniaeventi.com/categoria/nightlife/","dominio":"manfredoniaeventi.com","citta_default":"","curata": True,"nightlife": True,"prefisso_schede":"/evento/","data_nel_link": True,"max_schede":12},
    {"nome":"ManfredoniaEventi Minami","url":"https://manfredoniaeventi.com/luogo/minami-restaurant-lounge/","dominio":"manfredoniaeventi.com","citta_default":"","curata": True,"nightlife": True,"prefisso_schede":"/evento/","data_nel_link": True,"max_schede":12},
    {"nome":"ManfredoniaEventi Cafe des Artistes","url":"https://manfredoniaeventi.com/luogo/cafe-des-artistes/","dominio":"manfredoniaeventi.com","citta_default":"","curata": True,"nightlife": True,"prefisso_schede":"/evento/","data_nel_link": True,"max_schede":12},
    {"nome":"ManfredoniaEventi Al Molo 20","url":"https://manfredoniaeventi.com/organizzatore/al-molo-20/","dominio":"manfredoniaeventi.com","citta_default":"","curata": True,"nightlife": True,"prefisso_schede":"/evento/","data_nel_link": True,"max_schede":12},
    {"nome":"Xceed Barletta","url":"https://xceed.me/it/barletta/events","dominio":"xceed.me","citta_default":"Barletta","curata": True,"nightlife": True,"xceed": True,"prefisso_schede":"/it/barletta/event/","max_schede":15},
    {"nome":"Xceed Trani","url":"https://xceed.me/it/trani/events","dominio":"xceed.me","citta_default":"Trani","curata": True,"nightlife": True,"xceed": True,"prefisso_schede":"/it/trani/event/","max_schede":15},
    {"nome":"Xceed Atrio22","url":"https://xceed.me/it/barletta/venue/atrio22","dominio":"xceed.me","citta_default":"Barletta","curata": True,"nightlife": True,"xceed": True,"prefisso_schede":"/it/barletta/event/","max_schede":15},
    {"nome":"Xceed Aphelion Club","url":"https://xceed.me/it/trani/venue/aphelion-club-1","dominio":"xceed.me","citta_default":"Trani","curata": True,"nightlife": True,"xceed": True,"prefisso_schede":"/it/trani/event/","max_schede":15},
    {"nome":"Xceed Baia Nha","url":"https://xceed.me/it/trani/venue/baia-nha","dominio":"xceed.me","citta_default":"Trani","curata": True,"nightlife": True,"xceed": True,"prefisso_schede":"/it/trani/event/","max_schede":15},
    {"nome":"Tacco di Bacco Nightlife Cerignola","url":"https://iltaccodibacco.it/cerignola/nightlife/","dominio":"iltaccodibacco.it","citta_default":"","curata": True,"nightlife": True,"prefisso_schede":"/puglia/eventi/","max_schede":14},
    {"nome":"Tacco di Bacco Nightlife Trani","url":"https://iltaccodibacco.it/trani/nightlife/","dominio":"iltaccodibacco.it","citta_default":"","curata": True,"nightlife": True,"prefisso_schede":"/puglia/eventi/","max_schede":14},
    {"nome":"Tacco di Bacco Nightlife Barletta","url":"https://iltaccodibacco.it/barletta/nightlife/","dominio":"iltaccodibacco.it","citta_default":"","curata": True,"nightlife": True,"prefisso_schede":"/puglia/eventi/","max_schede":14},
    {"nome":"Tacco di Bacco Nightlife Manfredonia","url":"https://iltaccodibacco.it/manfredonia/nightlife/","dominio":"iltaccodibacco.it","citta_default":"","curata": True,"nightlife": True,"prefisso_schede":"/puglia/eventi/","max_schede":14},
    {"nome":"Tacco di Bacco Nightlife Bisceglie","url":"https://iltaccodibacco.it/bisceglie/nightlife/","dominio":"iltaccodibacco.it","citta_default":"","curata": True,"nightlife": True,"prefisso_schede":"/puglia/eventi/","max_schede":14},
    {"nome":"Tacco di Bacco Nightlife Andria","url":"https://iltaccodibacco.it/andria/nightlife/","dominio":"iltaccodibacco.it","citta_default":"","curata": True,"nightlife": True,"prefisso_schede":"/puglia/eventi/","max_schede":14},
    {"nome":"ManfredoniaEventi Nightlife","url":"https://www.manfredoniaeventi.com/","dominio":"manfredoniaeventi.com","citta_default":"","curata": True,"nightlife": True,"prefisso_schede":"/evento/","data_nel_link": True,"max_schede":20},
    {"nome":"LINEA Club Trani","url":"https://linea.live/events/city/trani","dominio":"linea.live","citta_default":"","curata": True,"nightlife": True,"solo_jsonld": True,"prefisso_schede":"/events/","data_nel_link": True,"max_schede":12},
    {"nome": "Lanotiziaweb Cerignola", "url": "https://www.lanotiziaweb.it/", "dominio": "lanotiziaweb.it", "citta_default": "", "curata": False, "notizie_locali": True, "max_schede": 8},
    {"nome": "Foggia Reporter Eventi Cerignola", "url": "https://www.foggiareporter.it/comune/comune-cerignola", "dominio": "foggiareporter.it", "citta_default": "", "curata": False, "notizie_locali": True, "max_schede": 8},
    {"nome": "Foggia Reporter Eventi", "url": "https://www.foggiareporter.it/category/eventi", "dominio": "foggiareporter.it", "citta_default": "", "curata": False, "notizie_locali": True, "max_schede": 8},
    {"nome": "Puglia Culture Cerignola", "url": "https://www.pugliaculture.it/circuito/Cerignola/", "dominio": "pugliaculture.it", "citta_default": "Cerignola", "curata": True, "prefisso_schede": "/evento/", "max_schede": 20},
    {"nome": "Puglia Culture Stagione Teatrale Cerignola 2026/27", "url": "https://www.pugliaculture.it/rassegna/cerignola-stagione-teatrale-2026-27-un-teatro-per-tutti/", "dominio": "pugliaculture.it", "citta_default": "Cerignola", "curata": True, "prefisso_schede": "/evento/", "max_schede": 30},
    {"nome": "Puglia Culture Teatro Ragazzi Cerignola 2026/27", "url": "https://www.pugliaculture.it/rassegna/cerignola-la-scena-dei-ragazzi-2026-27-spettacoli-per-le-scuole/", "dominio": "pugliaculture.it", "citta_default": "Cerignola", "curata": True, "prefisso_schede": "/evento/", "max_schede": 20},
    {"nome": "Comune Cerignola Homepage Eventi", "url": "https://comune.cerignola.fg.it/", "dominio": "comune.cerignola.fg.it", "citta_default": "Cerignola", "curata": True, "prefisso_schede": "/vivere-il-comune/eventi/", "max_schede": 20},
    {"nome": "Comune di Cerignola Eventi", "url": "https://comune.cerignola.fg.it/vivere-il-comune/eventi/", "dominio": "comune.cerignola.fg.it", "citta_default": "Cerignola", "curata": True, "prefisso_schede": "/vivere-il-comune/eventi/", "max_schede": 20},
    {"nome": "Teatro Mercadante Cerignola", "url": "https://www.teatromercadantecerignola.it/", "dominio": "teatromercadantecerignola.it", "citta_default": "Cerignola", "curata": True, "prefisso_schede": "/evento/", "max_schede": 20},
    {"nome": "Roma Teatro Cerignola", "url": "https://romateatrocinema.it/", "dominio": "romateatrocinema.it", "citta_default": "Cerignola", "curata": True, "parametro_scheda": "mec-events", "max_schede": 30},
    {"nome": "Tacco di Bacco Cerignola", "url": "https://iltaccodibacco.it/cerignola/", "dominio": "iltaccodibacco.it", "citta_default": "Cerignola", "curata": True},
    {"nome": "Tacco di Bacco Cerignola Concerti", "url": "https://iltaccodibacco.it/cerignola/concerti/", "dominio": "iltaccodibacco.it", "citta_default": "Cerignola", "curata": True},
    {"nome": "Tacco di Bacco Cerignola Sponsored", "url": "https://iltaccodibacco.it/cerignola/sponsored/", "dominio": "iltaccodibacco.it", "citta_default": "Cerignola", "curata": True},
    {"nome": "Tacco di Bacco Puglia Avventure", "url": "https://iltaccodibacco.it/puglia/avventure/", "dominio": "iltaccodibacco.it", "citta_default": "", "curata": True},
    {"nome": "Tacco di Bacco BAT", "url": "https://iltaccodibacco.it/barletta/", "dominio": "iltaccodibacco.it", "citta_default": "", "curata": True},
    {"nome": "Tacco di Bacco Foggia", "url": "https://iltaccodibacco.it/foggia/", "dominio": "iltaccodibacco.it", "citta_default": "", "curata": True},
    {"nome": "BuzzEventMap Cerignola", "url": "https://buzzeventmap.com/eventi/foggia/cerignola", "dominio": "buzzeventmap.com", "citta_default": "Cerignola", "curata": True},
    {"nome": "PaesiOnline Cerignola", "url": "https://www.paesionline.it/italia/eventi-cerignola", "dominio": "paesionline.it", "citta_default": "Cerignola", "curata": True},
    {"nome": "2D2Web Sagre Feste Cerignola", "url": "https://www.2d2web.com/sagre-feste/cerignola", "dominio": "2d2web.com", "citta_default": "Cerignola", "curata": True},
    {"nome": "Aivents Provincia Foggia", "url": "https://www.aivents.it/it/eventi-per-provincia/foggia", "dominio": "aivents.it", "citta_default": "", "curata": True},
    {"nome": "Virgilio Eventi Foggia", "url": "https://www.virgilio.it/italia/foggia/eventi/", "dominio": "virgilio.it", "citta_default": "", "curata": True},
    {"nome": "Experience App Foggia", "url": "https://experience-app.com/eventi/puglia/foggia/", "dominio": "experience-app.com", "citta_default": "", "curata": True},
    {"nome": "Piazza in Festa Cerignola", "url": "https://puglia.piazzainfesta.it/cerignola", "dominio": "piazzainfesta.it", "citta_default": "Cerignola", "curata": True, "prefisso_schede": "/cerignola/", "max_schede": 35},
    {"nome": "Masseria Pavoni Cerignola", "url": "https://www.masseriapavoni.com/", "dominio": "masseriapavoni.com", "citta_default": "Cerignola", "curata": True, "max_schede": 12},
    {"nome": "Agriturismo Moschella Cerignola", "url": "https://www.agriturismomoschella.com/", "dominio": "agriturismomoschella.com", "citta_default": "Cerignola", "curata": True, "max_schede": 12},

]

FONTI_SOCIAL_RSS = [
    {"nome":"Cerignola gastronomia e cene","url":"https://news.google.com/rss/search?q=Cerignola%20(%22cena%20evento%22%20OR%20%22cena%20di%20beneficenza%22%20OR%20%22serata%20gastronomica%22%20OR%20%22menu%20a%22%20OR%20degustazione%20OR%20%22show%20cooking%22%20OR%20%22cena%20a%20tema%22)%20when%3A30d&hl=it&gl=IT&ceid=IT%3Ait","citta_default":"Cerignola","solo_cerignola": True},
    {"nome":"Cerignola stampa locale eventi","url":"https://news.google.com/rss/search?q=Cerignola%20(site%3Alanotiziaweb.it%20OR%20site%3Amarchiodoc.it%20OR%20site%3Acerignolaviva.it%20OR%20site%3Afoggiareporter.it%20OR%20site%3Alucera.it)%20(serata%20OR%20festa%20OR%20musica%20OR%20mercatino%20OR%20concerto%20OR%20laboratorio%20OR%20cena)%20when%3A21d&hl=it&gl=IT&ceid=IT%3Ait","citta_default":"Cerignola","solo_cerignola": True},
    {"nome":"Cerignola pubblicazioni social locali","url":"https://news.google.com/rss/search?q=Cerignola%20(site%3Ainstagram.com%20OR%20site%3Afacebook.com)%20(%22NONZAI%22%20OR%20%22ADE%20rooftop%22%20OR%20%22Safar%C3%A0%22%20OR%20%22Blubar%22%20OR%20%22Villa%20Torre%20Quarto%22%20OR%20%22Sud%20Music%22)%20(evento%20OR%20serata%20OR%20dj%20OR%20live%20OR%20aperitivo)%20when%3A30d&hl=it&gl=IT&ceid=IT%3Ait","citta_default":"Cerignola","solo_cerignola": True},
    {"nome":"Andiamo in Puglia Daunia","url":"https://news.google.com/rss/search?q=site%3Aandiamoinpuglia.it%20(Cerignola%20OR%20Stornara%20OR%20Orta%20Nova%20OR%20Trinitapoli%20OR%20San%20Ferdinando%20OR%20Lavello)%20(sagra%20OR%20Natale%20OR%20concerto%20OR%20festa%20OR%20mercatino)%20when%3A21d&hl=it&gl=IT&ceid=IT%3Ait","citta_default":"","solo_scoperta":True},
    {"nome":"Andiamo in Puglia Nord Barese","url":"https://news.google.com/rss/search?q=site%3Aandiamoinpuglia.it%20(Canosa%20OR%20Barletta%20OR%20Trani%20OR%20Minervino%20OR%20Margherita%20di%20Savoia)%20(sagra%20OR%20concerto%20OR%20festa%20OR%20mercatino%20OR%20serata)%20when%3A21d&hl=it&gl=IT&ceid=IT%3Ait","citta_default":"","solo_scoperta":True},
    {"nome":"EventiVicino Reali Siti","url":"https://news.google.com/rss/search?q=site%3Aeventivicino.it%20(Cerignola%20OR%20Stornara%20OR%20Stornarella%20OR%20Orta%20Nova%20OR%20Trinitapoli%20OR%20Lavello%20OR%20Canosa)%20(serata%20OR%20festa%20OR%20sagra%20OR%20concerto)%20when%3A21d&hl=it&gl=IT&ceid=IT%3Ait","citta_default":"","solo_scoperta":True},
    {"nome":"Locali Cerignola e Reali Siti - nomi","url":"https://news.google.com/rss/search?q=(Cerignola%20OR%20Stornara%20OR%20Stornarella%20OR%20Orta%20Nova%20OR%20San%20Ferdinando%20OR%20Trinitapoli)%20(%22DJ%20set%22%20OR%20karaoke%20OR%20%22musica%20dal%20vivo%22%20OR%20discoteca%20OR%20%22cena%20spettacolo%22%20OR%20%22aperitivo%20musicale%22)%20when%3A14d&hl=it&gl=IT&ceid=IT%3Ait","citta_default":"","solo_scoperta":True},
    {"nome":"TicketSms discoteche BAT Capitanata","url":"https://news.google.com/rss/search?q=site%3Aticketsms.it%2Fevent%20(Bisceglie%20OR%20Trani%20OR%20Barletta%20OR%20Manfredonia%20OR%20Foggia%20OR%20Cerignola)%20(club%20OR%20party%20OR%20discoteca%20OR%20DJ)%20when%3A30d&hl=it&gl=IT&ceid=IT%3Ait","citta_default":"","nightlife": True,"solo_scoperta": True},
    {"nome":"DICE e promoter Puglia nord","url":"https://news.google.com/rss/search?q=site%3Adice.fm%20(Barletta%20OR%20Trani%20OR%20Foggia%20OR%20Manfredonia%20OR%20Bisceglie)%20(club%20OR%20DJ%20OR%20party)%20when%3A30d&hl=it&gl=IT&ceid=IT%3Ait","citta_default":"","nightlife": True,"solo_scoperta": True},
    {"nome":"Ticketoo e rivendita serate","url":"https://news.google.com/rss/search?q=site%3Aticketoo.it%20(Barletta%20OR%20Trani%20OR%20Manfredonia%20OR%20Foggia%20OR%20Bisceglie)%20(club%20OR%20DJ%20OR%20party)%20when%3A30d&hl=it&gl=IT&ceid=IT%3Ait","citta_default":"","nightlife": True,"solo_scoperta": True},
    {"nome":"Oazis musica live BAT","url":"https://news.google.com/rss/search?q=site%3Aoazis.app%20(Barletta%20OR%20Trani%20OR%20Bisceglie%20OR%20Manfredonia)%20(live%20OR%20DJ%20OR%20jam)%20when%3A30d&hl=it&gl=IT&ceid=IT%3Ait","citta_default":"","nightlife": True,"solo_scoperta": True},
    {"nome":"2night BAT weekend","url":"https://news.google.com/rss/search?q=site%3A2night.it%20(Barletta%20OR%20Trani%20OR%20Bisceglie%20OR%20Canosa)%20(%22dj%20set%22%20OR%20%22dinner%20show%22%20OR%20karaoke%20OR%20discoteca)%20when%3A14d&hl=it&gl=IT&ceid=IT%3Ait","citta_default":"","nightlife": True,"solo_scoperta": True},
    {"nome":"Resident Advisor costa","url":"https://news.google.com/rss/search?q=site%3Ara.co%2Fevents%20(Trani%20OR%20Barletta%20OR%20Manfredonia%20OR%20Foggia)%20(club%20OR%20DJ%20OR%20party)%20when%3A30d&hl=it&gl=IT&ceid=IT%3Ait","citta_default":"","nightlife": True,"solo_scoperta": True},
    {"nome":"KODO promoter Puglia nord","url":"https://news.google.com/rss/search?q=site%3Akodocollective.it%20(Barletta%20OR%20Trani%20OR%20Foggia)%20(DJ%20OR%20party%20OR%20club)%20when%3A30d&hl=it&gl=IT&ceid=IT%3Ait","citta_default":"","nightlife": True,"solo_scoperta": True},
    {"nome":"Club e promoter Capitanata","url":"https://news.google.com/rss/search?q=(Foggia%20OR%20Manfredonia%20OR%20Cerignola%20OR%20%22Margherita%20di%20Savoia%22%20OR%20Zapponeta)%20(discoteca%20OR%20%22dj%20set%22%20OR%20%22club%20night%22%20OR%20%22opening%20party%22%20OR%20%22dinner%20show%22)%20when%3A14d&hl=it&gl=IT&ceid=IT%3Ait","citta_default":"","nightlife": True,"solo_scoperta": True},
    {"nome":"Nightz Puglia nord","url":"https://news.google.com/rss/search?q=site%3Anightz.it%20(Barletta%20OR%20Trani%20OR%20Manfredonia%20OR%20Foggia%20OR%20Cerignola)%20(DJ%20OR%20club%20OR%20serata)%20when%3A30d&hl=it&gl=IT&ceid=IT%3Ait","citta_default":"","nightlife": True,"solo_scoperta": True},
    {"nome":"Movida Trani DJ e discoteche","url":"https://news.google.com/rss/search?q=Trani%20(%22dj%20set%22%20OR%20discoteca%20OR%20karaoke%20OR%20%22dinner%20show%22%20OR%20%22club%20night%22%20OR%20%22musica%20dal%20vivo%22%20OR%20%22serata%20latina%22%20OR%20%22opening%20party%22)%20when%3A21d&hl=it&gl=IT&ceid=IT%3Ait","citta_default":"","nightlife": True},
    {"nome":"Movida Barletta DJ e discoteche","url":"https://news.google.com/rss/search?q=Barletta%20(%22dj%20set%22%20OR%20discoteca%20OR%20karaoke%20OR%20%22dinner%20show%22%20OR%20%22club%20night%22%20OR%20%22musica%20dal%20vivo%22%20OR%20%22serata%20latina%22%20OR%20%22opening%20party%22)%20when%3A21d&hl=it&gl=IT&ceid=IT%3Ait","citta_default":"","nightlife": True},
    {"nome":"Movida Manfredonia DJ e discoteche","url":"https://news.google.com/rss/search?q=Manfredonia%20(%22dj%20set%22%20OR%20discoteca%20OR%20karaoke%20OR%20%22dinner%20show%22%20OR%20%22club%20night%22%20OR%20%22musica%20dal%20vivo%22%20OR%20%22serata%20latina%22%20OR%20%22opening%20party%22)%20when%3A21d&hl=it&gl=IT&ceid=IT%3Ait","citta_default":"","nightlife": True},
    {"nome":"Serate e musica Cerignola fonti pubbliche","url":"https://news.google.com/rss/search?q=Cerignola%20(%22dj%20set%22%20OR%20karaoke%20OR%20%22musica%20dal%20vivo%22%20OR%20aperitivo%20OR%20%22dinner%20show%22%20OR%20serata%20OR%20party)%20when%3A30d&hl=it&gl=IT&ceid=IT%3Ait","citta_default":"Cerignola"},
    {"nome":"Mercatini e feste Reali Siti","url":"https://news.google.com/rss/search?q=(Cerignola%20OR%20Stornara%20OR%20Stornarella%20OR%20%22Orta%20Nova%22%20OR%20Trinitapoli%20OR%20%22San%20Ferdinando%20di%20Puglia%22%20OR%20%22Canosa%20di%20Puglia%22%20OR%20Carapelle%20OR%20Ordona)%20(mercatini%20OR%20presepe%20OR%20sagra%20OR%20%22festa%20di%20paese%22%20OR%20%22villaggio%20di%20Natale%22)%20when%3A30d&hl=it&gl=IT&ceid=IT%3Ait","citta_default":"Cerignola"},
    {"nome": "Social pubblici Instagram Cerignola", "url": "https://news.google.com/rss/search?q=site%3Ainstagram.com%2Fp%2F+Cerignola+(evento+OR+serata+OR+concerto+OR+dj+OR+party+OR+locandina)&hl=it&gl=IT&ceid=IT%3Ait", "citta_default": "Cerignola"},
    {"nome": "Social pubblici Facebook Cerignola", "url": "https://news.google.com/rss/search?q=site%3Afacebook.com+Cerignola+(evento+OR+serata+OR+concerto+OR+dj+OR+party+OR+locandina)&hl=it&gl=IT&ceid=IT%3Ait", "citta_default": "Cerignola"},
    {"nome": "Famiglie e weekend Cerignola e dintorni", "url": "https://news.google.com/rss/search?q=(Cerignola+OR+Canosa+OR+Barletta+OR+Trinitapoli+OR+Margherita+di+Savoia+OR+Orta+Nova)+(weekend+OR+famiglie+OR+bambini+OR+laboratorio+OR+fattoria+didattica+OR+visita+guidata+OR+gita)&hl=it&gl=IT&ceid=IT%3Ait", "citta_default": "Cerignola"},
    {"nome": "Escursioni e cammini area BAT Foggia", "url": "https://news.google.com/rss/search?q=(Cerignola+OR+Canosa+OR+Barletta+OR+Andria+OR+Foggia+OR+Minervino+Murge)+(escursione+OR+trekking+OR+camminata+OR+cammino+OR+birdwatching+OR+cicloturismo+OR+e-bike+OR+passeggiata+guidata)&hl=it&gl=IT&ceid=IT%3Ait", "citta_default": "Cerignola"},
    {"nome": "Visite e attività rurali weekend", "url": "https://news.google.com/rss/search?q=(Cerignola+OR+Canosa+OR+Barletta+OR+Margherita+di+Savoia+OR+Foggia)+(masseria+OR+fattoria+OR+frantoio+OR+caseificio+OR+degustazione+OR+open+day+OR+family+day+OR+visita)&hl=it&gl=IT&ceid=IT%3Ait", "citta_default": "Cerignola"},
]

COMUNI_50KM = {
    "cerignola": "Cerignola",
    "stornara": "Stornara",
    "stornarella": "Stornarella",
    "orta nova": "Orta Nova",
    "san ferdinando di puglia": "San Ferdinando di Puglia",
    "san ferdinando": "San Ferdinando di Puglia",
    "trinitapoli": "Trinitapoli",
    "canosa di puglia": "Canosa di Puglia",
    "canosa": "Canosa di Puglia",
    "ordona": "Ordona",
    "carapelle": "Carapelle",
    "margherita di savoia": "Margherita di Savoia",
    "lavello": "Lavello",
    "ascoli satriano": "Ascoli Satriano",
    "zapponeta": "Zapponeta",
    "castelluccio dei sauri": "Castelluccio dei Sauri",
    "barletta": "Barletta",
    "candela": "Candela",
    "minervino murge": "Minervino Murge",
    "minervino": "Minervino Murge",
    "foggia": "Foggia",
    "melfi": "Melfi",
    "venosa": "Venosa",
    "deliceto": "Deliceto",
    "rapolla": "Rapolla",
    "andria": "Andria",
    "barile": "Barile",
    "palazzo san gervasio": "Palazzo San Gervasio",
    "rocchetta sant'antonio": "Rocchetta Sant'Antonio",
    "manfredonia": "Manfredonia",
    "rionero in vulture": "Rionero in Vulture",
    "rionero": "Rionero in Vulture",
    "trani": "Trani",
    "bovino": "Bovino",
    "spinazzola": "Spinazzola",
    "troia": "Troia",
    "lucera": "Lucera",
    "bisceglie": "Bisceglie",
    "monticchio": "Monticchio"
}

CINTURA_25 = {
    # Comuni entro 25 km in linea d'aria dal centro di Cerignola.
    "Stornara", "Stornarella", "Canosa di Puglia", "San Ferdinando di Puglia",
    "Orta Nova", "Trinitapoli", "Carapelle", "Zapponeta", "Ordona",
    "Margherita di Savoia", "Minervino Murge"
}

CATEGORIE_AMMESSE = [
    "Musica & Concerti",
    "Teatro & Spettacoli",
    "Locali & Serate",
    "Sagre & Food",
    "Famiglie & Bambini",
    "Natura & Escursioni",
    "Attività diurne"
]

MESI_IT = {
    "gennaio": 1, "gen": 1,
    "febbraio": 2, "feb": 2,
    "marzo": 3, "mar": 3,
    "aprile": 4, "apr": 4,
    "maggio": 5, "mag": 5,
    "giugno": 6, "giu": 6,
    "luglio": 7, "lug": 7,
    "agosto": 8, "ago": 8,
    "settembre": 9, "set": 9, "sett": 9,
    "ottobre": 10, "ott": 10,
    "novembre": 11, "nov": 11,
    "dicembre": 12, "dic": 12
}

NOMI_MESI_BREVI = {
    1: "Gen", 2: "Feb", 3: "Mar", 4: "Apr", 5: "Mag", 6: "Giu",
    7: "Lug", 8: "Ago", 9: "Set", 10: "Ott", 11: "Nov", 12: "Dic"
}

NOMI_GIORNI_BREVI = ["Lun", "Mar", "Mer", "Gio", "Ven", "Sab", "Dom"]

REGEX_TEMA_COERENTE = re.compile(
    r"\b(?:"
    r"mercatin[oi]\s+(?:di\s+natale|nataliz\w*|enogastronomic\w*|artigianal\w*|di\s+autoproduzione)|"
    r"natale\s+(?:nelle|tra\s+le|in\s+piazza)|tombolat[ae]|cena\s+spettacolo|dinner\s+show|show\s+cooking|music\s+selection|serat[ae]\s+k-pop|"
    r"luminari[ae]|accensione\s+(?:delle\s+)?luminari[ae]|accensione\s+(?:dell['’]\s*)?albero|"
    r"villaggi[o]?\s+(?:di\s+natale|natalizi[o]?|di\s+babbo\s+natale)|"
    r"casa\s+di\s+babbo\s+natale|pist[ae]\s+di\s+(?:pattinaggio|ghiaccio)|presepe\s+vivente|"
    r"concert[oi]|concerts?|symphonic\s+concert|concerto\s+sinfonico|orchestra\s+sinfonica|musica\s+classica|recital\s+pianistic[o]?|musica\s+da\s+camera|opera\s+lirica|pianoforte|"
    r"spettacolo\s+teatrale|commedia\s+teatrale|teatro\s+ragazzi|prosa|musica\s+(?:dal\s+vivo|live)|live\s+music|tribute\s+band|cover\s+band|"
    r"dj\s*set|discotec[ah]|club\s+night|party|aperitiv[oi]\s+musical\w*|karaoke|"
    r"serat[ae]\s+(?:live|musical\w*|in\s+piazza|al\s+pub|nel\s+locale|danza|latina|disco|con)|"
    r"cabaret|festa\s+(?:in\s+piazza|di\s+piazza|patronale|di\s+paese|della\s+birra)|"
    r"sagr[ae]|street\s+food|degustazion[ei]|festa\s+gastronomic[ah]|percorso\s+enogastronomic[o]|caldarroste|prodotti\s+tipici|"
    r"cena\s+(?:evento|di\s+beneficenza|a\s+tema)|serata\s+(?:gastronomica|di\s+cucina)|show\s+cooking|soft\s+clubbing|capodanno|cenon[ei]|veglion[ei]|san\s+silvestro|"
    r"laboratori[o]?\s+(?:per\s+bambini|creativ[oi])|animazione\s+per\s+bambini|"
    r"spettacol[oi]\s+(?:per\s+famiglie|di\s+intrattenimento)|festa\s+per\s+bambini|notte\s+bianca\s+dei\s+bambini|"
    r"fattori[ae]\s+didattic[ah]|parco\s+tematico|"
    r"trekking|escursion[ei]|passeggiat[ae]\s+(?:naturalistic[ah]|guidat[ah])|camminat[ae]\s+(?:guidat[ae]|naturalistic[ah])|cammin[oie]|birdwatching|cicloturismo|e-bike|gita\s+(?:fuori\s+porta|organizzat[ae])|family\s+day|open\s+day|"
    r"uscit[ae]\s+organizzat[ah]|visita\s+guidata|visita\s+alle\s+saline|visita\s+in\s+masseria|riserva\s+naturale|attivit[aà]\s+all['’]aperto|"
    r"fiera\s+(?:ricreativa|artigianale|d['’]aprile)|esperienz[ae]\s+artigianal\w*|festival|avventur\w*|"
    r"corricerignola|gara\s+podistica|maratona|mezza\s+maratona|corsa\s+(?:podistica|su\s+strada|campestre)|"
    r"trail\s+running|urban\s+trail|spartan\s+race|hyrox"
    r")\b",
    re.I
)

PAROLE_SCARTO = [
    "adblocker", "ci stai leggendo", "archivio", "evento si è già concluso",
    "grande successo per", "si è concluso", "si è conclusa", "si è svolta", "si è svolto",
    "si sono svolti", "si sono svolte", "si è tenuto", "si è tenuta", "bilancio positivo",
    "convegno", "convegni", "conferenza", "conferenze", "seminario", "seminari",
    "tavola rotonda", "dibattito", "aula magna", "dipartimento", "università",
    "presentazione libro", "presentazione del libro", "presentazione del volume",
    "mostra fotografica", "vernissage", "esposizione fotografica",
    "drammaturgia", "monologo", "notte poesia",
    "conservatorio",
    "santa messa", "messa solenne", "processione", "parrocchia", "parrocchie",
    "diocesi", "vescovo", "liturgia", "città mariana", "devozione", "incoronazione",
    "sport agonistico", "torneo", "tornei", "campionato", "campionati",
    "partita",
    "calcio", "volley", "basket", "audace cerignola", "ultras",
    "webinar", "evento online", "corso online", "google meet", "zoom", "b2b",
    "wedding", "fiera sposi", "comunicato stampa", "consiglio comunale", "giunta",
    "elezioni", "arresto", "incidente", "omicidio", "furto", "rapina", "sequestro",
    "carabinieri", "polizia", "guardia di finanza", "bando", "gara d'appalto", "delibera"
]

REGEX_SCARTO = re.compile(r"\b(?:" + "|".join(re.escape(w) for w in PAROLE_SCARTO) + r")\b", re.I)

ESCLUSIONI_PATH_VIVA = (
    "/cronaca/", "/politica/", "/sport/", "/necrologi/", "/meteo/",
    "/farmacie/", "/oroscopo/", "/redazione/", "/contatti/", "/pubblicita/",
    "/privacy/", "/cookie/", "/chi-siamo/", "/tag/", "/autore/",
    "/page/", "/pagina/", "/archivio/", "/cerca/", "/feed/", "/rss/",
    "/wp-admin/", "/wp-content/", "/login/", "/registrati/", "/oggi/", "/domani/", "/weekend/"
)


def oggi_dt():
    """Data/ora corrente nel fuso operativo italiano, indipendente dal runner UTC."""
    return datetime.now(ZoneInfo("Europe/Rome"))

STATISTICHE_FONTI = {}
STATI_EVENTI_NEGATIVI = set()
_LOCK_STATISTICHE = Lock()
MAX_WORKER_FONTI = 4
MAX_OCR_PER_FONTE = 6
OCR_TIMEOUT_SECONDI = 8
OCR_MAX_PIXEL = 20_000_000
_OCR_SLOT = BoundedSemaphore(2)


def registra_statistica_fonte(nome, **dati):
    """Conserva metriche per fonte per rendere verificabile ogni ciclo di raccolta."""
    with _LOCK_STATISTICHE:
        stato = STATISTICHE_FONTI.setdefault(nome, {})
        stato.update(dati)


def crea_session_raccolta():
    """Sessione HTTP con retry controllati per errori transitori e rate limit."""
    retry = Retry(
        total=3,
        connect=2,
        read=2,
        status=3,
        backoff_factor=0.7,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset({"GET"}),
        respect_retry_after_header=True,
        raise_on_status=False,
    )
    adapter = HTTPAdapter(
        max_retries=retry,
        pool_connections=10,
        pool_maxsize=10,
    )
    session = requests.Session()
    session.headers.update(HEADERS)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session



def _data_iso_valida(valore):
    valore = str(valore or "").strip()
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", valore):
        return False
    try:
        return datetime.strptime(valore, "%Y-%m-%d").strftime("%Y-%m-%d") == valore
    except ValueError:
        return False


def _host_appartiene(url, dominio):
    """Confronto hostname rigoroso: il dominio deve essere host o suo suffisso DNS."""
    host = (urlparse(str(url or "")).hostname or "").lower().rstrip(".")
    dominio = str(dominio or "").lower().strip(".")
    return bool(host and dominio and (host == dominio or host.endswith("." + dominio)))


def _url_pagina_elenco(url):
    """Riconosce alcuni endpoint di elenco che non sono schede di un singolo evento."""
    parsed = urlparse(str(url or ""))
    path = parsed.path.rstrip("/").lower()
    if _host_appartiene(url, "experience-app.com") and path.startswith("/eventi/"):
        return True
    if _host_appartiene(url, "buzzeventmap.com") and path.startswith("/eventi/"):
        return True
    return False


def _descrizione_placeholder(testo):
    valore = re.sub(r"\s+", " ", str(testo or "")).strip().lower()
    return any(frase in valore for frase in (
        "l'indirizzo potrebbe essere inesatto",
        "indirizzo potrebbe essere inesatto",
        "accertati prima di partire",
        "descrizione non disponibile",
        "informazioni non disponibili",
    ))


def oggi_iso():
    return oggi_dt().strftime("%Y-%m-%d")


def priorita_km(citta):
    if citta == "Cerignola":
        return 0
    if citta in CINTURA_25:
        return 1
    return 2


def _comune_nel_testo(testo):
    """Restituisce il primo comune citato nel testo; a parità, preferisce il nome più specifico."""
    testo = str(testo or "")
    corrispondenze = []
    for nome, canonico in COMUNI_50KM.items():
        for match in re.finditer(rf"\b{re.escape(nome)}\b", testo, re.I):
            corrispondenze.append((match.start(), -(match.end() - match.start()), canonico))
    if not corrispondenze:
        return ""
    return min(corrispondenze)[2]


PROVINCE_SIGLE_LOCALITA = (
    "Bari|BA|Brindisi|BR|Foggia|FG|Barletta-Andria-Trani|BAT|BT|"
    "Taranto|TA|Lecce|LE|Potenza|PZ|Matera|MT|Avellino|AV|Benevento|BN|"
    "Campobasso|CB|Napoli|NA|Roma|RM|Milano|MI|Torino|TO|Venezia|VE|Verona|VR|"
    "Padova|PD|Brescia|BS|Bergamo|BG|Bologna|BO|Genova|GE|Firenze|FI|Pisa|PI|"
    "Livorno|LI|Perugia|PG|Ancona|AN|Pescara|PE|L'Aquila|AQ|Salerno|SA|Caserta|CE|"
    "Cosenza|CS|Catanzaro|CZ|Reggio Calabria|RC|Messina|ME|Palermo|PA|Catania|CT|"
    "Cagliari|CA|Sassari|SS|Trieste|TS|Udine|UD|Trento|TN|Bolzano|BZ|Aosta|AO|"
    "Arezzo|AR|Siena|SI|Lucca|LU|Parma|PR|Modena|MO|Ravenna|RA|Ferrara|FE|Rimini|RN|"
    "Piacenza|PC|Como|CO|Varese|VA|Monza|MB|Pavia|PV|Cremona|CR|Mantova|MN|Lecco|LC|"
    "Sondrio|SO|Novara|NO|Alessandria|AL|Cuneo|CN|Asti|AT|Imperia|IM|Savona|SV|"
    "La Spezia|SP|Reggio Emilia|RE|Forlì-Cesena|FC|Macerata|MC|Pesaro e Urbino|PU|"
    "Teramo|TE|Chieti|CH|Frosinone|FR|Latina|LT|Viterbo|VT|Rieti|RI|Isernia|IS|"
    "Crotone|KR|Vibo Valentia|VV|Trapani|TP|Agrigento|AG|Enna|EN|Ragusa|RG|"
    "Siracusa|SR|Nuoro|NU|Oristano|OR|Olbia-Tempio|OT|Carbonia-Iglesias|CI|"
    "Ogliastra|OG|Medio Campidano|VS"
)


def _ripara_codifica(testo):
    """Ripara HTML entities e sequenze di codifica note nelle schede evento."""
    testo = unescape(str(testo or ""))
    sostituzioni = {
        "√Ý": "à",
        "‚Äô": "’",
        "â€™": "’",
        "Ã ": "à",
        "Ã¨": "è",
        "Ã©": "é",
        "Ã¬": "ì",
        "Ã²": "ò",
        "Ã¹": "ù",
    }
    for errato, corretto in sostituzioni.items():
        testo = testo.replace(errato, corretto)
    return re.sub(r"\s+", " ", testo).strip()


def normalizza_nome_luogo(luogo, citta=""):
    """Pulisce code editoriali e ripetizioni della città senza inventare una sede."""
    valore = re.sub(r"\s+", " ", str(luogo or "")).strip(" ,.;:-")
    valore = re.sub(
        r"\s+(?:prosegue|appuntamento|l'appuntamento|il\s+prossimo\s+appuntamento|evento\s+in\s+programma)\.?$",
        "",
        valore,
        flags=re.I,
    ).strip(" ,.;:-")
    if citta:
        # Corregge solo la duplicazione consecutiva finale: il nome della struttura
        # può legittimamente contenere la città una sola volta.
        # Accetta separatori diversi tra le due occorrenze (es. ", " e ". ").
        # Conserva il primo separatore e la prima occorrenza della città.
        pattern_duplicato = re.compile(
            rf"(?i)([,.;:]\s*|\s+-\s*|\s+)({re.escape(citta)})(?:[,.;:]\s*|\s+-\s*|\s+)({re.escape(citta)})$"
        )
        precedente = None
        while valore != precedente:
            precedente = valore
            valore = pattern_duplicato.sub(r"\1\2", valore).strip(" ,.;:-")
    return valore


def _luogo_utilizzabile(luogo):
    """Scarta frammenti di testo scambiati per una sede o un indirizzo."""
    valore = normalizza_nome_luogo(luogo)
    if not valore or len(valore) < 4 or len(valore) > 100:
        return False
    if valore.lower() in {
        "corso", "via", "piazza", "viale", "centro / piazze",
        "centro", "da definire", "da verificare", "n/d",
    } or re.search(r"\bcentro\s*/\s*piazze\b", valore, re.I):
        return False
    if re.search(
        r"\b(?:o ricevere maggiori informazioni|è possibile consultare|"
        r"per maggiori informazioni|per informazioni|clicca per|"
        r"persone parteciperanno|ingresso a pagamento|ingresso libero)\b",
        valore,
        re.I,
    ):
        return False
    if re.match(r"^(?:corso|via|piazza|viale)\s+(?:da|di|per|o|è|e)\b", valore, re.I):
        return False
    return True

def _localita_esplicita_fuori_area(testo):
    """Riconosce una località esplicita fuori dal bacino servito e impedisce il fallback al comune fonte."""
    testo = str(testo or "")[:900]
    pattern = re.compile(
        rf"\b([A-ZÀ-Ü][A-Za-zÀ-ÿ'’.-]*(?:\s+(?:di|del|della|de|san|santa|"
        rf"[A-ZÀ-Ü][A-Za-zÀ-ÿ'’.-]*)){{0,4}})\s*"
        rf"\((?i:{PROVINCE_SIGLE_LOCALITA})\)",
    )
    for match in pattern.finditer(testo):
        localita = match.group(1).strip()
        if not _comune_nel_testo(localita):
            return localita
    return ""


def _url_tacco_generica(url):
    """Individua pagine-categoria Tacco di Bacco, non schede di singoli eventi."""
    parsed = urlparse(str(url or ""))
    if not _host_appartiene(url, "iltaccodibacco.it"):
        return False
    ultimo = parsed.path.rstrip("/").split("/")[-1].lower()
    return ultimo in {
        "eventi", "concerti", "sponsored", "avventure", "notizie",
        "spettacoli", "tempo-libero", "cerignola", "barletta", "foggia",
        "puglia", "nightlife", "trani", "manfredonia", "bisceglie", "andria",
    }


def risolvi_comune_50km(testo_o_ev):
    if isinstance(testo_o_ev, dict):
        # L'indirizzo viene spesso costruito aggiungendo in coda la città predefinita
        # della fonte: quella sola occorrenza non è una prova della sede reale.
        indirizzo = str(testo_o_ev.get("indirizzoMappa") or "")
        citta_default = str(testo_o_ev.get("citta") or "").strip()
        if citta_default:
            indirizzo = re.sub(
                rf"(?:,\s*|\s+-\s*){re.escape(citta_default)}\s*$",
                "",
                indirizzo,
                flags=re.I,
            )
        for testo in (indirizzo, testo_o_ev.get("luogo"), testo_o_ev.get("titolo"), testo_o_ev.get("descrizione")):
            comune = _comune_nel_testo(testo)
            if comune:
                return comune

        # citta è soltanto un fallback se non esistono prove più specifiche.
        return _comune_nel_testo(citta_default)
    return _comune_nel_testo(testo_o_ev)


def normalizza_indirizzo_mappa(indirizzo, luogo, citta):
    """Rimuove un eventuale comune predefinito errato in coda all'indirizzo."""
    indirizzo = re.sub(r"\s+", " ", str(indirizzo or "")).strip(" ,")
    if not indirizzo:
        indirizzo = str(luogo or "").strip()
    # Sede verificata del Roma Teatro Cinema E… di Cerignola: alcune
    # schede aggregate riportano solo il nome abbreviato della struttura.
    if str(citta or "").casefold() == "cerignola" and re.search(
        r"roma\s+teatro\s+cinema", f"{luogo} {indirizzo}", re.I
    ):
        return "Roma Teatro Cinema E…, Corso Roma, 49, Cerignola"
    for nome in sorted(set(COMUNI_50KM.values()), key=len, reverse=True):
        if nome.lower() == str(citta or "").lower():
            continue
        indirizzo = re.sub(
            rf"(?:,\s*|\s+-\s*){re.escape(nome)}(?:\s*\([A-Z]{{2}}\))?\s*$",
            "",
            indirizzo,
            flags=re.I,
        ).strip(" ,")
    if citta:
        # Collassa anche il caso limite in cui l'intero campo contiene solo
        # il nome del comune ripetuto (es. "Foggia, Foggia").
        solo_comune_ripetuto = re.fullmatch(
            rf"\s*{re.escape(citta)}(?:\s*[,.;:]\s*{re.escape(citta)}|\s+-\s+{re.escape(citta)}|\s+{re.escape(citta)})+\s*",
            indirizzo,
            flags=re.I,
        )
        if solo_comune_ripetuto:
            indirizzo = citta
        else:
            # Elimina tutte le ripetizioni finali del comune anche con separatori misti
            # (es. ", " e ". "), mantenendo l'eventuale comune nel nome della sede.
            indirizzo = normalizza_nome_luogo(indirizzo, citta)
    if citta:
        # Rimuove una seconda occorrenza finale anche quando la prima è seguita
        # dalla sigla provinciale o dalla regione: "Foggia (FG), Foggia".
        duplicato_con_sigla = re.compile(
            rf"(?i)^(.*?\b{re.escape(citta)}\b(?:\s*\([A-Z]{{2}}\))?(?:,\s*(?:Puglia|Italia))?)(?:[,.;]\s*{re.escape(citta)}\b(?:\s*\([A-Z]{{2}}\))?)+$"
        )
        indirizzo = duplicato_con_sigla.sub(r"\1", indirizzo).strip(" ,.;")
    if citta:
        # Rimuove il comune ripetuto dopo la sigla provinciale:
        # "... Foggia (FG), Foggia, Puglia".
        indirizzo = re.sub(
            rf"(?i)(\b{re.escape(citta)}\b\s*\([A-Z]{{2}}\))(?:,\s*{re.escape(citta)}\b)+",
            r"\1",
            indirizzo,
        )
        # Alcuni aggregatori premettono il comune e poi lo ripetono in coda.
        if re.search(rf"(?i),\s*{re.escape(citta)}\b", indirizzo):
            indirizzo = re.sub(
                rf"(?i)^{re.escape(citta)}\s*,\s*",
                "",
                indirizzo,
            )
    # Alcuni aggregatori concatenano due volte l'intero indirizzo, separando
    # la prima copia dalla seconda con un punto (es. "... Barletta. Barletta, ...").
    # Normalizza quel separatore solo quando introduce nuovamente il comune.
    if indirizzo and citta:
        indirizzo = re.sub(
            rf"\.\s+(?={re.escape(citta)}\b)", ", ", indirizzo, flags=re.I
        )

    if indirizzo:
        parti_indirizzo = [parte.strip() for parte in indirizzo.split(",") if parte.strip()]

        def chiavi_segmento_indirizzo(parte):
            parte = re.sub(r"\s*\([A-Z]{2}\)$", "", parte)
            senza_comune = re.sub(
                rf"\s+{re.escape(str(citta))}$", "", parte, flags=re.I
            ) if citta else parte
            normalizza = lambda valore: re.sub(
                r"[^a-z0-9]+", " ", valore.casefold()
            ).strip()
            return {
                chiave for chiave in (normalizza(parte), normalizza(senza_comune))
                if chiave
            }

        # Elimina segmenti identici adiacenti.
        i = 0
        while i < len(parti_indirizzo) - 1:
            if chiavi_segmento_indirizzo(parti_indirizzo[i]).intersection(
                chiavi_segmento_indirizzo(parti_indirizzo[i + 1])
            ):
                parti_indirizzo.pop(i + 1)
            else:
                i += 1

        # Se l'intera sequenza iniziale ricompare identica in coda, conserva
        # una sola copia. Il vincolo inizio/fine evita di cancellare vie
        # omonime che compaiono legittimamente in indirizzi più articolati.
        chiavi = [chiavi_segmento_indirizzo(p) for p in parti_indirizzo]
        for lunghezza in range(len(parti_indirizzo) // 2, 1, -1):
            if chiavi[:lunghezza] == chiavi[-lunghezza:]:
                parti_indirizzo = parti_indirizzo[:-lunghezza]
                break

        indirizzo = ", ".join(parti_indirizzo)
        if citta:
            indirizzo = normalizza_nome_luogo(indirizzo, citta)

    if citta and not re.search(rf"\b{re.escape(citta)}\b", indirizzo, re.I):
        indirizzo = f"{indirizzo}, {citta}".strip(" ,")
    return indirizzo


def classifica_categoria(testo, luogo="", fonte_url=""):
    t = (testo or "").casefold()
    sede = (luogo or "").casefold()
    url = (fonte_url or "").casefold()

    if re.search(r"\b(?:capodanno|san silvestro)\b", t) and re.search(r"\b(?:cenon[ei]|veglion[ei]|party|dj set|cena)\b", t):
        return "Locali & Serate"
    if "capodanno" in t and "pranzo" in t:
        return "Sagre & Food"

    if festivita.TEMA.search(t) and re.search(r"\b(?:pranzo|cena|cenone|brunch)\b", t):
        return "Sagre & Food"
    if festivita.TEMA.search(t) and re.search(r"\b(?:dj set|party|serata)\b", t):
        return "Locali & Serate"
    if festivita.TEMA.search(t) and re.search(r"\b(?:presepe|befana|tombolata|villaggio|laboratorio)\b", t):
        return "Famiglie & Bambini"
    if re.search(r"\b(?:carnevale|san valentino|festa della donna|pasqua|pasquetta|ferragosto|halloween|madonna di ripalta|primo maggio)\b",t):
        if re.search(r"\b(?:dj set|party|serata)\b",t):
            return "Locali & Serate"
        if re.search(r"\b(?:pranzo|cena|brunch|picnic)\b",t):
            return "Sagre & Food"
        if re.search(r"\b(?:sfilata|luna park|attività per famiglie)\b",t):
            return "Famiglie & Bambini"
    # Le gare di corsa e gli eventi fitness rientrano nelle attività diurne.
    if any(k in t for k in ("corricerignola", "gara podistica", "maratona", "mezza maratona", "corsa podistica", "corsa su strada", "corsa campestre", "trail running", "urban trail", "spartan race", "hyrox")):
        return "Attività diurne"
    if any(k in t for k in ("luminari", "mercatini di natale", "mercatino di natale", "mercatini nataliz", "villaggio di natale", "villaggio nataliz", "villaggio di babbo natale", "babbo natale", "casa di babbo natale", "teatro ragazzi", "la scena dei ragazzi", "spettacoli per le scuole", "pista di pattinaggio", "pista di ghiaccio", "presepe vivente", "laboratori per bambini", "laboratorio per bambini", "laboratori creativi", "laboratorio creativo", "laboratori per famiglie", "attivita per famiglie", "attività per famiglie", "animazione per bambini", "spettacolo per famiglie", "festa per bambini", "notte bianca dei bambini", "fattoria didattica", "fattorie didattiche", "parco tematico")):
        return "Famiglie & Bambini"
    if any(k in t for k in ("escursion", "trekking", "passeggiat", "camminat", "visita guidata", "visita alle saline", "riserva naturale", "saline", "monticchio", "murgia", "incoronata", "avventur")):
        return "Natura & Escursioni"
    if any(k in t for k in ("sagra", "sagre", "sfogliatella", "street food", "degustazion", "enogastronom", "festa gastronomica", "caldarroste", "prodotti tipici", "cena evento", "cena di beneficenza", "cena a tema", "serata gastronomica", "serata di cucina", "show cooking")):
        return "Sagre & Food"

    # Gli indizi teatrali espliciti prevalgono sulle parole generiche.
    if any(k in t for k in (
        "spettacolo teatrale", "teatro inclusivo", "teatro & spettacoli",
        "commedia teatrale", "prosa", "cabaret", "monologo", "drammaturgia",
        "compagnia teatrale", "altri spettacoli teatrali",
    )):
        return "Teatro & Spettacoli"

    # Le serate in locali e i format sociali hanno priorità sui generici riferimenti musicali.
    if any(k in t for k in ("dinner show", "dinner party", "cena spettacolo", "music selection", "opening winter season", "opening summer season", "club opening", "vinyl set", "after show", "deejay", "dj set", "dj-set", "club night", "discotec", "party", "serata al pub", "serata nel locale", "serata disco", "serata latina", "aperitivo musicale", "aperitivi musicali", "karaoke", "notte bianca", "soft clubbing")):
        return "Locali & Serate"

    # Un concerto resta musica anche quando si svolge in un teatro.
    if any(k in t for k in (
        "concerto", "concerti", "concert", "concerts", "symphonic concert", "in concerto",
        "concerto sinfonico", "orchestra sinfonica", "musica classica", "recital pianistico",
        "pianoforte", "musica da camera", "opera lirica", "vivaldi", "orchestra",
        "musica dal vivo", "musica live", "live music", " live ", "tribute", "tributo",
        "tribute band", "cover band", "band", "jam", "quartet", "quatuor", "trio", "duo",
        "vocal harmony", "sassofono", "saxophone", "chitarra", "guitar", "cantautore",
        "cantante", "musicista", "soul", "r&b", "hendrix", "califano",
        "festa in piazza", "festa di piazza", "festa patronale", "festa di paese",
        "festa della birra",
    )):
        return "Musica & Concerti"

    # Se la scheda proviene da una stagione teatrale o indica una sede teatrale,
    # classifica come spettacolo solo in assenza di indizi musicali espliciti.
    fonte_teatrale = any(d in url for d in (
        "teatromercadantecerignola.it", "romateatrocinema.it"
    ))
    sede_teatrale = bool(re.search(r"\bteatro\b", sede))
    if fonte_teatrale or sede_teatrale or any(
        k in t for k in ("stagione teatrale", "altri spettacoli teatrali")
    ):
        return "Teatro & Spettacoli"

    return "Attività diurne"

def formatta_data_italiano(d_ini_iso, d_fin_iso):
    try:
        dt1 = datetime.strptime(d_ini_iso, "%Y-%m-%d")
        dt2 = datetime.strptime(d_fin_iso, "%Y-%m-%d")
        g1 = f"{NOMI_GIORNI_BREVI[dt1.weekday()]} {dt1.day:02d} {NOMI_MESI_BREVI[dt1.month]} {dt1.year}"
        if dt1.date() == dt2.date():
            return g1
        g2 = f"{dt2.day:02d} {NOMI_MESI_BREVI[dt2.month]} {dt2.year}"
        return f"Dal {dt1.day:02d} {NOMI_MESI_BREVI[dt1.month]} al {g2}"
    except Exception:
        return d_ini_iso


def _costruisci_data_sicura(giorno, mese, anno):
    try:
        return datetime(int(anno), int(mese), int(giorno))
    except ValueError:
        return None


def _inferisci_anno(giorno, mese, anno_str, ref_dt):
    if anno_str:
        return _costruisci_data_sicura(giorno, mese, int(anno_str))
    anno = ref_dt.year
    if mese < ref_dt.month - 2:
        anno += 1
    return _costruisci_data_sicura(giorno, mese, anno)


def rimuovi_riferimenti_pubblicazione(testo):
    t = re.sub(r"\s+", " ", (testo or "")).strip()
    mesi_pat = "|".join(MESI_IT.keys())
    t = re.sub(
        rf"^(?:[A-ZÀ-Ü\s']+,\s*)?\d{{1,2}}(?:\s+(?:{mesi_pat})|[/.-]\d{{1,2}})(?:\s+|[/.-])20\d{{2}}\s*[-–—:]\s*",
        " ",
        t,
        flags=re.I
    )
    t = re.sub(
        rf"\b(?:pubblicato|aggiornato|ultimo\s+aggiornamento|inserito|redazione|scritto)\s*(?:il|in\s+data|:)?\s*\d{{1,2}}(?:\s+(?:{mesi_pat})|[/.-]\d{{1,2}})(?:\s+|[/.-])20\d{{2}}(?:\s*(?:alle|ore|-)?\s*\d{{1,2}}[:.]\d{{2}})?",
        " ",
        t,
        flags=re.I
    )
    t = re.sub(
        rf"\b\d{{1,2}}(?:\s+(?:{mesi_pat})|[/.-]\d{{1,2}})(?:\s+|[/.-])20\d{{2}}\s*[-–|]\s*(?:redazione|di\s+[a-z]+)",
        " ",
        t,
        flags=re.I
    )
    return re.sub(r"\s+", " ", t).strip()


def estrai_date_italiano(testo, ref_dt=None):
    ref = ref_dt or oggi_dt()
    t = re.sub(r"\s+", " ", rimuovi_riferimenti_pubblicazione(testo)).strip().lower()
    mesi_pat = "|".join(MESI_IT.keys())
    prep_al = r"(?:al|all['’]|allo|alla|ai|agli|alle|-|–|—)"

    m = re.search(
        rf"\b(?:dal(?:l['’]|lo|la)?\s+)?(\d{{1,2}})\s+({mesi_pat})(?:\s+(20\d{{2}}))?\s*{prep_al}\s*(\d{{1,2}})\s+({mesi_pat})(?:\s+(20\d{{2}}))?\b",
        t
    )
    if m:
        g1, m1_s, a1_s, g2, m2_s, a2_s = m.groups()
        m1, m2 = MESI_IT[m1_s], MESI_IT[m2_s]
        dt2 = _inferisci_anno(int(g2), m2, a2_s, ref)
        if dt2:
            anno1 = int(a1_s) if a1_s else (dt2.year - 1 if m1 > m2 else dt2.year)
            dt1 = _costruisci_data_sicura(int(g1), m1, anno1)
            if dt1 and dt1 <= dt2:
                d1, d2 = dt1.strftime("%Y-%m-%d"), dt2.strftime("%Y-%m-%d")
                return d1, d2, formatta_data_italiano(d1, d2)

    m = re.search(
        rf"\b(?:dal(?:l['’]|lo|la)?\s+|l['’]\s*|nei\s+giorni\s+)?(\d{{1,2}})(?:\s*,\s*\d{{1,2}})+\s*(?:e|ed)\s*(\d{{1,2}})\s+({mesi_pat})(?:\s+(20\d{{2}}))?\b",
        t
    )
    if m:
        g1, g2, m_s, a_s = m.groups()
        mese = MESI_IT[m_s]
        dt1 = _inferisci_anno(int(g1), mese, a_s, ref)
        dt2 = _inferisci_anno(int(g2), mese, a_s, ref)
        if dt1 and dt2 and dt1 <= dt2:
            d1, d2 = dt1.strftime("%Y-%m-%d"), dt2.strftime("%Y-%m-%d")
            return d1, d2, formatta_data_italiano(d1, d2)

    m = re.search(
        rf"\b(?:dal(?:l['’]|lo|la)?\s+|l['’]\s*)?(\d{{1,2}})\s*(?:{prep_al}|e|ed)\s*(\d{{1,2}})\s+({mesi_pat})(?:\s+(20\d{{2}}))?\b",
        t
    )
    if m:
        g1, g2, m_s, a_s = m.groups()
        mese = MESI_IT[m_s]
        dt1 = _inferisci_anno(int(g1), mese, a_s, ref)
        dt2 = _inferisci_anno(int(g2), mese, a_s, ref)
        if dt1 and dt2 and dt1 <= dt2:
            d1, d2 = dt1.strftime("%Y-%m-%d"), dt2.strftime("%Y-%m-%d")
            return d1, d2, formatta_data_italiano(d1, d2)

    m = re.search(
        rf"\b(\d{{1,2}})\s+({mesi_pat})(?:\s+(20\d{{2}}))?\b",
        t
    )
    if m:
        g1, m_s, a_s = m.groups()
        dt1 = _inferisci_anno(int(g1), MESI_IT[m_s], a_s, ref)
        if dt1:
            d1 = dt1.strftime("%Y-%m-%d")
            return d1, d1, formatta_data_italiano(d1, d1)

    m = re.search(
        rf"\b(?:dal(?:l['’])?\s+)?(\d{{1,2}})[/.-](\d{{1,2}})(?:[/.-](20\d{{2}}))?\s*{prep_al}\s*(\d{{1,2}})[/.-](\d{{1,2}})(?:[/.-](20\d{{2}}))?\b",
        t
    )
    if m:
        g1, m1_s, a1_s, g2, m2_s, a2_s = m.groups()
        dt2 = _inferisci_anno(int(g2), int(m2_s), a2_s, ref)
        if dt2:
            anno1 = int(a1_s) if a1_s else (dt2.year - 1 if int(m1_s) > int(m2_s) else dt2.year)
            dt1 = _costruisci_data_sicura(int(g1), int(m1_s), anno1)
            if dt1 and dt1 <= dt2:
                d1, d2 = dt1.strftime("%Y-%m-%d"), dt2.strftime("%Y-%m-%d")
                return d1, d2, formatta_data_italiano(d1, d2)

    m = re.search(r"\b(\d{1,2})[/.-](\d{1,2})[/.-](20\d{2})\b", t)
    if m:
        g1, m1_s, a1_s = m.groups()
        dt1 = _costruisci_data_sicura(int(g1), int(m1_s), int(a1_s))
        if dt1:
            d1 = dt1.strftime("%Y-%m-%d")
            return d1, d1, formatta_data_italiano(d1, d1)

    return "", "", ""


def date_discontinue(testo, ref_dt=None):
    """Se una fonte elenca giorni separati, non inventare i giorni intermedi."""
    ref = ref_dt or oggi_dt()
    mesi = "|".join(MESI_IT)
    testo = rimuovi_riferimenti_pubblicazione(testo).casefold()
    m = re.search(rf"\b(\d{{1,2}}(?:\s*,\s*\d{{1,2}})*\s+(?:e|ed)\s+\d{{1,2}})\s+({mesi})(?:\s+(20\d{{2}}))?\b", testo)
    if not m:
        return []
    giorni = [int(x) for x in re.findall(r"\d{1,2}", m.group(1))]
    date = [_inferisci_anno(g, MESI_IT[m.group(2)], m.group(3), ref) for g in giorni]
    if not all(date) or len(set(giorni)) != len(giorni) or giorni != sorted(giorni):
        return []
    if len(giorni) < 2:
        return []
    return [d.strftime("%Y-%m-%d") for d in date]


def ricorrenza_compatibile(testo, data):
    """Una regola mensile esplicita può smentire una data, non confermarne di nuove."""
    m = re.search(r"\b(prim[oa]|second[oa]|terz[oa]|quart[oa]|ultim[oa])\s+(luned[iì]|marted[iì]|mercoled[iì]|gioved[iì]|venerd[iì]|sabato|domenica)\s+(?:di\s+ogni\s+mese|del\s+mese|di\s+tutti\s+i\s+mesi)\b", testo or "", re.I)
    if not m or not _data_iso_valida(data):
        return True
    d = datetime.strptime(data, "%Y-%m-%d")
    giorni = ["luned", "marted", "mercoled", "gioved", "venerd", "sabato", "domenica"]
    giorno = next(i for i,g in enumerate(giorni) if m.group(2).casefold().startswith(g))
    ordinale = m.group(1).casefold()[:-1]
    if d.weekday() != giorno:
        return False
    if ordinale == "ultim":
        return (d + timedelta(days=7)).month != d.month
    return (d.day - 1) // 7 + 1 == {"prim":1,"second":2,"terz":3,"quart":4}[ordinale]


def giorno_settimana_compatibile(titolo, data):
    """Se il titolo contiene giorno della settimana e data dell'evento,
    non accettare un anno inferito che contraddice il giorno dichiarato.
    """
    if not _data_iso_valida(data):
        return True
    dt = datetime.strptime(data, "%Y-%m-%d")
    giorni = ["luned", "marted", "mercoled", "gioved", "venerd", "sabato", "domenica"]
    pattern = r"\b(luned[iì]|marted[iì]|mercoled[iì]|gioved[iì]|venerd[iì]|sabato|domenica)\s+(\d{1,2})\s+(" + "|".join(MESI_IT) + r")\b"
    for m in re.finditer(pattern, titolo or "", re.I):
        if int(m.group(2)) == dt.day and MESI_IT[m.group(3).casefold()] == dt.month:
            atteso = next(i for i,g in enumerate(giorni) if m.group(1).casefold().startswith(g))
            if dt.weekday() != atteso:
                return False
    return True


def orario_data_strutturata(valore):
    m = re.match(r"^\d{4}-\d{2}-\d{2}T([01]\d|2[0-3]):([0-5]\d)", str(valore or ""))
    if not m or m.group(1,2) == ("00","00"):
        return ""
    return " · Ore " + m.group(1) + ":" + m.group(2)


def estrai_eventi_jsonld(obj, trovati):
    if isinstance(obj, list):
        for item in obj:
            estrai_eventi_jsonld(item, trovati)
    elif isinstance(obj, dict):
        t = obj.get("@type", "")
        tipi = t if isinstance(t, list) else [t]
        if any("Event" in str(x) for x in tipi) and obj.get("name"):
            trovati.append(obj)
        for v in obj.values():
            if isinstance(v, (dict, list)):
                estrai_eventi_jsonld(v, trovati)


def estrai_luogo_documentato(testo_o_soup, citta=""):
    if hasattr(testo_o_soup, "get_text"):
        testo_pag = testo_o_soup.get_text("\n", strip=True)
    else:
        testo_pag = str(testo_o_soup or "")

    # La pagina ufficiale del Mercadante espone la sede come riga autonoma,
    # non come etichetta "Luogo:"; riconoscila senza inventare altre sedi.
    if citta.lower() == "cerignola":
        if re.search(r"\bteatro\s+comunale\s+saverio\s+mercadante\b", testo_pag, re.I):
            return "Teatro Comunale Saverio Mercadante"
        if re.search(r"\bteatro\s+comunale\s+s\.?\s*mercadante\b", testo_pag, re.I):
            return "Teatro Comunale S. Mercadante"

    for raw_line in testo_pag.splitlines():
        line = re.sub(r"\s+", " ", raw_line).strip()
        if 4 <= len(line) <= 130:
            m_dove = re.match(r"^(?:dove|luogo|presso|location|sede|locale|indirizzo)\s*:\s*(.+)$", line, re.I)
            if m_dove:
                cand = m_dove.group(1).strip(" ,.;:-")
                if _luogo_utilizzabile(cand) and cand.lower() != citta.lower():
                    return cand[:80]
            # Alcuni portali ufficiali mostrano l'etichetta "Luogo" su una riga
            # e la sede sulla successiva, seguita dall'indirizzo postale.
            if line.lower() in {"luogo", "sede", "dove"}:
                righe_successive = testo_pag.splitlines()
                indice = righe_successive.index(raw_line)
                for successiva in righe_successive[indice + 1:indice + 4]:
                    cand = re.sub(r"\s*[-–|]\s*Comune di\s+.+$", "", successiva.strip(), flags=re.I)
                    if re.match(r"^(?:via|viale|piazza|piazzale|corso|largo)\b", cand, re.I):
                        break
                    if _luogo_utilizzabile(cand) and cand.lower() != citta.lower():
                        return cand[:80]
            m_etichetta = re.match(r"^(?:teatro|venue|location)\s*:\s*(.+)$", line, re.I)
            if m_etichetta:
                cand = re.sub(rf"\s*[-–|,]\s*{re.escape(citta)}(?:\s+\([A-Z]{{2}}\))?$", "", m_etichetta.group(1), flags=re.I).strip(" ,.;:-")
                if _luogo_utilizzabile(cand) and cand.lower() != citta.lower():
                    return cand[:80]

    if citta:
        for raw_line in testo_pag.splitlines():
            line = re.sub(r"\s+", " ", raw_line).strip()
            if 5 <= len(line) <= 95:
                m_loc_citta = re.match(rf"^([A-Za-zÀ-ü0-9'’.\-\s]{{4,60}})\s*[-–|]\s*{re.escape(citta)}\b", line, re.I)
                if m_loc_citta:
                    cand = m_loc_citta.group(1).strip(" ,.;:-")
                    if len(cand) >= 4 and not REGEX_SCARTO.search(cand):
                        return cand[:80]

    testo_flat = re.sub(r"\s+", " ", testo_pag)
    pat_strutture = (
        r"\b(?:in|presso|al|allo|alla|ai|agli|alle|all['’]|nel|nello|nella|sul|sulla|lungo)\s+"
        r"((?:Piazza|Piazzale|Largo|Corso|Via|Viale|Villa\s+Comunale|Parco|Giardini|Castello|Palazzo|"
        r"Saline|Riserva\s+Naturale|Bosco|Laghi\s+di|Lago\s+di|Lungomare|Arena|Anfiteatro|Chiostro|"
        r"Borgo\s+Antico|Centro\s+Storico|Masseria|Fattoria\s+Didattica|Pub|Club|Discoteca|Lounge|"
        r"Cantina|Politeama|Teatro|Vecchie\s+Segherie|Auditorium|Pala\w*|Cittadella)\s*[A-Za-zÀ-ü0-9'’.\-\s]{0,55})"
    )
    m = re.search(pat_strutture, testo_flat, re.I)
    if m:
        grezzo = m.group(1)
        pulito = re.split(
            r"(?:[,.;!?]|\s+(?:a|ad|in|nel|nella|il|lo|la|dal|dalle|con|per|dove|che|organizzato|in\s+programma)\b)",
            grezzo,
            flags=re.I
        )[0].strip(" ,.;:-")
        if _luogo_utilizzabile(pulito) and pulito.lower() != citta.lower():
            return pulito[:80]

    m_presso = re.search(r"\bpresso\s+(?:il\s+|la\s+|lo\s+|l['’])?([A-ZÀ-Ü][A-Za-zÀ-ü0-9'’.\-]*(?:\s+[A-ZÀ-Ü0-9][A-Za-zÀ-ü0-9'’.\-]*){0,4})", testo_flat)
    if m_presso:
        cand = m_presso.group(1).strip(" ,.;:-")
        if _luogo_utilizzabile(cand) and cand.lower() != citta.lower():
            return cand[:80]

    return ""


def estrai_indirizzo_documentato(testo_o_soup, citta=""):
    """Estrae una via/piazza esplicitamente pubblicata, senza geocodificare dati inventati."""
    if hasattr(testo_o_soup, "get_text"):
        righe = testo_o_soup.get_text("\n", strip=True).splitlines()
    else:
        righe = str(testo_o_soup or "").splitlines()

    for indice, raw_line in enumerate(righe):
        line = re.sub(r"\s+", " ", raw_line).strip()
        if not re.match(
            r"^(?:via|viale|piazza|piazzale|corso|largo|strada|contrada)\b",
            line,
            re.I,
        ):
            continue
        indirizzo = line.strip(" ,.;")
        if citta and citta.lower() not in indirizzo.lower():
            for successiva in righe[indice + 1:indice + 3]:
                prossima = re.sub(r"\s+", " ", successiva).strip(" ,.;")
                if citta.lower() in prossima.lower():
                    indirizzo = f"{indirizzo}, {prossima}"
                    break
        if citta and citta.lower() not in indirizzo.lower():
            indirizzo = f"{indirizzo}, {citta}"
        return indirizzo[:150]
    return ""


def estrai_costo_documentato(testo_o_soup):
    if hasattr(testo_o_soup, "get_text"):
        testo_pag = testo_o_soup.get_text("\n", strip=True)
    else:
        testo_pag = str(testo_o_soup or "")

    for raw_line in testo_pag.splitlines():
        line = re.sub(r"\s+", " ", raw_line).strip()
        if 5 <= len(line) <= 130:
            m_costo = re.match(r"^(?:ingresso|costo|prezzo|biglietti|quota)\s*:\s*(.+)$", line, re.I)
            if m_costo:
                return m_costo.group(1).strip()[:70]

    m_inline = re.search(
        r"\b(ingresso\s+(?:libero|gratuito)|gratuito|a\s+pagamento)\b|(?<!\w)€\s*\d+(?:[.,]\d{1,2})?|\b\d+(?:[.,]\d{1,2})?\s*€",
        testo_pag,
        re.I,
    )
    if m_inline:
        return (m_inline.group(1) or m_inline.group(0)).strip().capitalize()

    return "Non specificato nella fonte"


def _formatta_prezzo_jsonld(valore, valuta=""):
    try:
        prezzo = Decimal(str(valore).strip().replace(",", "."))
    except (InvalidOperation, ValueError, TypeError):
        return ""
    if prezzo == 0:
        return "Gratuito"
    if valuta and str(valuta).upper() != "EUR":
        return f"{str(valuta).upper()} {prezzo.normalize():f}"
    if str(valuta).upper() != "EUR":
        return ""
    testo = f"{prezzo:.2f}".replace(".", ",")
    if testo.endswith(",00"):
        testo = testo[:-3]
    return f"€ {testo}"


def estrai_costo_jsonld(evento, testo_pagina=None):
    """Legge price/lowPrice/highPrice dalle offerte JSON-LD e poi ripiega sul testo."""
    offerte = evento.get("offers") or []
    if isinstance(offerte, dict):
        offerte = [offerte]
    prezzi = []
    valuta = ""
    for offerta in offerte if isinstance(offerte, list) else []:
        if not isinstance(offerta, dict):
            continue
        specifica = offerta.get("priceSpecification")
        if isinstance(specifica, dict):
            offerta = {**specifica, **offerta}
        valuta = str(offerta.get("priceCurrency") or valuta or "").upper()
        low = offerta.get("lowPrice")
        high = offerta.get("highPrice")
        if low not in (None, ""):
            prezzo = _formatta_prezzo_jsonld(low, valuta)
            if prezzo:
                prezzi.append((Decimal(str(low).replace(",", ".")), prezzo))
        if high not in (None, ""):
            prezzo = _formatta_prezzo_jsonld(high, valuta)
            if prezzo:
                prezzi.append((Decimal(str(high).replace(",", ".")), prezzo))
        if low in (None, "") and high in (None, ""):
            valore = offerta.get("price")
            if valore not in (None, ""):
                prezzo = _formatta_prezzo_jsonld(valore, valuta)
                if prezzo:
                    prezzi.append((Decimal(str(valore).replace(",", ".")), prezzo))

    if prezzi:
        prezzi.sort(key=lambda x: x[0])
        minimo, massimo = prezzi[0], prezzi[-1]
        if minimo[0] == massimo[0]:
            return minimo[1]
        return f"Da {minimo[1]} a {massimo[1]}"

    if testo_pagina is not None:
        return estrai_costo_documentato(testo_pagina)
    return "Non specificato nella fonte"


def normalizza_e_valida_evento(raw, ref_dt=None, fonte_curata_eventi=False):
    ref = ref_dt or oggi_dt()
    oggi = ref.strftime("%Y-%m-%d")
    limite_max = (ref + timedelta(days=GIORNI_ANTICIPO_MAX)).strftime("%Y-%m-%d")

    titolo = _ripara_codifica(raw.get("titolo") or "")[:85]
    descrizione = _ripara_codifica(raw.get("descrizione") or "")[:220]
    luogo = _ripara_codifica(raw.get("luogo") or "")
    indirizzo_grezzo = _ripara_codifica(raw.get("indirizzoMappa") or "")
    url = str(raw.get("fonteUrl") or "").strip()

    parsed_url = urlparse(url)
    # Le pagine indice e le categorie del portale comunale possono essere
    # raggiunte come link interni: non sono schede di singoli eventi.
    if titolo.casefold().strip(" -|") in {
        "eventi", "tutti gli eventi", "calendario eventi",
        "eventi in programma", "eventi a cerignola",
    }:
        return None

    if (
        len(titolo) < 5
        or parsed_url.scheme not in ("http", "https")
        or not parsed_url.hostname
        or _url_tacco_generica(url)
        or _url_pagina_elenco(url)
    ):
        return None
    descrizione_non_verificata = _descrizione_placeholder(descrizione)
    # Experience App in alcune schede restituisce date e descrizioni generiche
    # non verificabili: non pubblicarle come se fossero eventi confermati.
    if descrizione_non_verificata and _host_appartiene(url, "experience-app.com"):
        return None
    if descrizione_non_verificata:
        descrizione = ""
    if re.search(r"(?:√[ÝÈ]|‚Ä|Ã[Â-ÿ]|�)", titolo + " " + descrizione):
        return None
    # Analizza i campi separatamente: concatenarli può far inglobare al parser
    # il comune valido precedente nel nome di una città estranea (es. "Cerignola Roma").
    for testo_geografico in (indirizzo_grezzo, luogo, descrizione[:650]):
        if _localita_esplicita_fuori_area(testo_geografico):
            return None

    testo_check = f"{titolo} {descrizione} {luogo}"
    if REGEX_SCARTO.search(testo_check):
        return None
    if not fonte_curata_eventi and not REGEX_TEMA_COERENTE.search(testo_check):
        return None

    raw_pulito = dict(raw)
    raw_pulito.update({
        "titolo": titolo,
        "descrizione": descrizione,
        "luogo": luogo,
        "indirizzoMappa": indirizzo_grezzo,
    })
    citta = risolvi_comune_50km(raw_pulito)
    if not citta:
        return None

    d1 = str(raw.get("dataInizio") or "").strip()[:10]
    d2 = str(raw.get("dataFine") or d1).strip()[:10]
    d_txt = str(raw.get("dataTesto") or "").strip()

    if not (_data_iso_valida(d1) and _data_iso_valida(d2)):
        d1, d2, d_txt = estrai_date_italiano(f"{titolo} {descrizione} {d_txt}", ref)

    if not (_data_iso_valida(d1) and _data_iso_valida(d2)):
        return None
    if d2 < oggi or d1 > d2 or d1 > limite_max:
        return None
    if d1 == d2 and not giorno_settimana_compatibile(titolo, d1):
        return None

    luogo = normalizza_nome_luogo(luogo, citta)
    if not _luogo_utilizzabile(luogo) or luogo.lower() == citta.lower():
        luogo = estrai_luogo_documentato(f"{titolo}\n{descrizione}", citta)
    luogo = normalizza_nome_luogo(luogo, citta)
    if not _luogo_utilizzabile(luogo):
        return None

    # Ricalcola la categoria sul contenuto. Mantiene però la classe specifica
    # assegnata dalla scheda quando la fonte documenta esplicitamente il teatro.
    cat = classifica_categoria(f"{titolo} {descrizione}", luogo=luogo, fonte_url=url)
    if str(raw.get("categoria") or "").strip() == "Teatro & Spettacoli":
        cat = "Teatro & Spettacoli"
    elif str(raw.get("categoria") or "").strip() == "Locali & Serate" and any(_host_appartiene(url,d) for d in ("xceed.me","ticketsms.it","nightz.it","lineupatlas.com")):
        cat = "Locali & Serate"

    if not d_txt:
        d_txt = formatta_data_italiano(d1, d2)

    costo = str(raw.get("costo") or "").strip() or "Non specificato nella fonte"
    desc_finale = rimuovi_riferimenti_pubblicazione(descrizione) if descrizione else ""
    if len(desc_finale) < 15:
        desc_finale = (
            f"{titolo} presso {luogo} ({citta}). "
            "Verifica orari e modalità di accesso nella fonte dell'organizzatore."
        )

    poster = str(raw.get("locandinaUrl") or "").strip()
    poster_ok = urlparse(poster).scheme in ("http", "https") and bool(urlparse(poster).hostname)
    return {
        **({"locandinaUrl": poster} if poster_ok else {}),
        "tipoContenuto": "evento",
        "citta": citta,
        "categoria": cat,
        "titolo": titolo,
        "dataTesto": d_txt,
        "dataInizio": d1,
        "dataFine": d2,
        "luogo": luogo,
        "indirizzoMappa": normalizza_indirizzo_mappa(indirizzo_grezzo, luogo, citta),
        "costo": costo,
        "descrizione": desc_finale[:220],
        "fonteUrl": url
    }


def chiave_stato_evento(url, data):
    """Confronto prudente: stessa scheda e stessa data, mai solo il nome."""
    pr = urlparse(str(url or ""))
    if pr.scheme not in ("http", "https") or not pr.hostname or not _data_iso_valida(data):
        return None
    return (pr.hostname.lower().removeprefix("www."), pr.path.rstrip("/") or "/", pr.query, data)


def registra_stati_negativi(html_text, page_url):
    """Legge esclusivamente stati espliciti Schema.org; non deduce cancellazioni da HTTP o testo generico."""
    soup = BeautifulSoup(html_text, "html.parser")
    eventi_ld = []
    for sc in soup.find_all("script", type="application/ld+json"):
        try:
            estrai_eventi_jsonld(json.loads(sc.string or ""), eventi_ld)
        except (ValueError, TypeError):
            continue
    negativi = set()
    for ev in eventi_ld:
        stato = str(ev.get("eventStatus") or "").lower().rstrip("/").rsplit("/", 1)[-1]
        if stato not in {"eventcancelled", "eventpostponed", "eventrescheduled"}:
            continue
        # Per gli eventi riprogrammati serve la vecchia data esplicita.
        data = str(ev.get("previousStartDate") if stato == "eventrescheduled" else ev.get("startDate") or "")[:10]
        url = urljoin(page_url, str(ev.get("url") or ""))
        if not _host_appartiene(url, urlparse(page_url).hostname):
            continue
        k = chiave_stato_evento(url, data)
        if k:
            negativi.add(k)
    with _LOCK_STATISTICHE:
        STATI_EVENTI_NEGATIVI.update(negativi)
    return negativi


def evento_non_attivo(ev):
    k = chiave_stato_evento(ev.get("fonteUrl"), ev.get("dataInizio"))
    with _LOCK_STATISTICHE:
        return k is not None and k in STATI_EVENTI_NEGATIVI


def ricontrolla_eventi_imminenti(eventi, massimo=10):
    """Rilegge un piccolo campione di schede automatiche imminenti.
    Un errore o un blocco HTTP non autorizza mai una cancellazione."""
    oggi = oggi_iso()
    limite = (oggi_dt() + timedelta(days=7)).strftime("%Y-%m-%d")
    scelti = []
    visti = set()
    for ev in sorted(eventi, key=lambda e: (priorita_km(e.get("citta", "")), e.get("dataInizio", ""))):
        url = ev.get("fonteUrl", "")
        if not (oggi <= ev.get("dataInizio", "") <= limite) or not _fonte_appartiene_a_raccolta_automatica(url):
            continue
        if url in visti or _host_appartiene(url, "news.google.com") or _host_appartiene(url, "instagram.com") or _host_appartiene(url, "facebook.com"):
            continue
        visti.add(url)
        scelti.append(url)
        if len(scelti) >= massimo:
            break
    letti = 0
    with requests.Session() as session:
        session.headers.update(HEADERS)
        for url in scelti:
            try:
                r = session.get(url, timeout=(3, 5), allow_redirects=False)
                if r.status_code == 200 and "html" in r.headers.get("Content-Type", "text/html").lower():
                    registra_stati_negativi(r.text, url)
                    letti += 1
            except requests.RequestException:
                pass
    return {"schedeSelezionate": len(scelti), "schedeLette": letti}


def analizza_pagina_evento(html_text, page_url, citta_default="", fonte_curata_eventi=False):
    ref = oggi_dt()
    soup = BeautifulSoup(html_text, "html.parser")
    risultati = []

    eventi_ld = []
    for sc in soup.find_all("script", type="application/ld+json"):
        try:
            estrai_eventi_jsonld(json.loads(sc.string or ""), eventi_ld)
        except Exception:
            continue

    negativi = registra_stati_negativi(html_text, page_url) if eventi_ld else set()
    testo_regola = (soup.find("main") or soup.find("article") or soup.body or soup).get_text(" ", strip=True)
    for ev_ld in eventi_ld[:20]:
        stato = str(ev_ld.get("eventStatus") or "").lower()
        if "eventcancelled" in stato or "eventpostponed" in stato:
            continue
        titolo = re.sub(r"\s+", " ", str(ev_ld.get("name") or "")).strip()
        d1 = str(ev_ld.get("startDate") or "").strip()[:10]
        d2 = str(ev_ld.get("endDate") or d1).strip()[:10]
        if not ricorrenza_compatibile(testo_regola, d1):
            continue
        loc = ev_ld.get("location") or {}
        if isinstance(loc, list):
            loc = loc[0] if loc else {}
        if isinstance(loc, dict):
            luogo_nome = str(loc.get("name") or "").strip()
            addr = loc.get("address", {})
        else:
            luogo_nome = str(loc or "").strip()
            addr = {}
        if isinstance(addr, dict):
            localita = str(addr.get("addressLocality") or "").strip()
            componenti_indirizzo = [
                luogo_nome,
                str(addr.get("streetAddress") or "").strip(),
                str(addr.get("postalCode") or "").strip(),
                localita,
                str(addr.get("addressRegion") or "").strip(),
            ]
        else:
            localita = ""
            componenti_indirizzo = [luogo_nome, str(addr or "").strip()]
        indirizzo_completo = ", ".join(x for x in componenti_indirizzo if x)
        desc = re.sub(r"\s+", " ", str(ev_ld.get("description") or "")).strip()
        url_evento = urljoin(page_url, str(ev_ld.get("url") or "").strip())
        host_pagina = urlparse(page_url).hostname or ""
        host_evento = urlparse(url_evento).hostname or ""
        if not (
            _host_appartiene(url_evento, host_pagina)
            or _host_appartiene(page_url, host_evento)
        ):
            url_evento = page_url

        ev_ok = normalizza_e_valida_evento({
            "citta": localita or citta_default,
            "titolo": titolo,
            "dataInizio": d1,
            "dataFine": d2,
            "dataTesto": (formatta_data_italiano(d1, d2) + orario_data_strutturata(ev_ld.get("startDate"))) if _data_iso_valida(d1) else "",
            "luogo": luogo_nome,
            "indirizzoMappa": indirizzo_completo,
            "costo": estrai_costo_jsonld(ev_ld, soup),
            "descrizione": desc,
            "fonteUrl": url_evento
        }, ref, fonte_curata_eventi=fonte_curata_eventi)
        if ev_ok and not evento_non_attivo(ev_ok):
            risultati.append(ev_ok)

    if risultati:
        return risultati
    if negativi:
        return []  # Non ricostruire dal testo una scheda esplicitamente non attiva.

    h1 = soup.find("h1")
    titolo = re.sub(r"\s+", " ", h1.get_text(" ", strip=True)) if h1 else ""
    if not titolo:
        og_t = soup.find("meta", property="og:title")
        titolo = re.sub(r"\s+", " ", og_t.get("content", "")).strip() if og_t else ""
    if len(titolo) < 5:
        return []

    # Le schede ufficiali possono pubblicare la data dell'evento dentro <time>.
    # Manteniamo il tag e il suo testo: rimuoverlo faceva perdere la data al parser.
    for tag in soup(["script", "style", "nav", "footer", "aside", "form", "noscript", "iframe"]):
        tag.decompose()
    for meta_el in soup.select(".byline, .author, .meta, .post-meta, .entry-meta, .article-meta, [class*='publish'], [class*='update'], [class*='autore'], [class*='redazione']"):
        meta_el.decompose()

    # Puglia Culture colloca parte dei metadati fuori dal contenitore main.
    cont = soup if _host_appartiene(page_url, "pugliaculture.it") else (soup.find("main") or soup.find("article") or soup.body or soup)
    paragrafi = []
    for p in cont.find_all(["p", "li", "h2", "h3"]):
        txt = re.sub(r"\s+", " ", p.get_text(" ", strip=True)).strip()
        if 15 <= len(txt) <= 500 and txt not in paragrafi:
            paragrafi.append(txt)
        if len(paragrafi) >= 14:
            break

    corpo = " ".join(paragrafi)[:1800]
    # Date e metadati dei portali istituzionali sono spesso in div/span,
    # non in paragrafi o intestazioni. Usa il testo visibile dell'area contenuto
    # per non perdere schede che il crawler ha scaricato correttamente.
    testo_visibile = re.sub(r"\s+", " ", cont.get_text(" ", strip=True)).strip()
    testo_completo = f"{titolo} | {testo_visibile[:6000]}"
    d1, d2, d_txt = estrai_date_italiano(testo_completo, ref)
    if _host_appartiene(page_url, "pugliaculture.it"):
        # Preferisce le date strutturate della scheda ed esclude le date di pubblicazione trascorse.
        date_strutturate = []
        limite = (ref + timedelta(days=GIORNI_ANTICIPO_MAX)).date()
        for el in soup.select('[itemprop="startDate"], time[datetime], [data-start-date]'):
            valore = (el.get("content") or el.get("datetime") or el.get("data-start-date") or "").strip()
            match_data = re.match(r"^(20\d{2}-\d{2}-\d{2})", valore)
            if not match_data:
                continue
            try:
                dt = datetime.strptime(match_data.group(1), "%Y-%m-%d").date()
            except ValueError:
                continue
            if ref.date() <= dt <= limite:
                date_strutturate.append(dt)
        if date_strutturate:
            d1 = min(date_strutturate).strftime("%Y-%m-%d")
            d2 = d1
            d_txt = formatta_data_italiano(d1, d2)
    if not d1 or not ricorrenza_compatibile(testo_completo, d1):
        return []

    citta = risolvi_comune_50km({"citta": citta_default, "titolo": titolo, "descrizione": corpo[:650]})
    if not citta:
        return []

    luogo = estrai_luogo_documentato(cont, citta)
    if not luogo:
        return []

    indirizzo_documentato = estrai_indirizzo_documentato(cont, citta)
    costo = estrai_costo_documentato(cont)
    descrizione = ""
    for p in paragrafi:
        if len(p) >= 40 and p.lower() != titolo.lower() and not REGEX_SCARTO.search(p):
            descrizione = rimuovi_riferimenti_pubblicazione(p)[:220]
            break

    raw = {
        "citta": citta,
        "categoria": classifica_categoria(testo_completo, luogo=luogo, fonte_url=page_url),
        "titolo": titolo,
        "dataTesto": d_txt,
        "dataInizio": d1,
        "dataFine": d2,
        "luogo": luogo,
        "indirizzoMappa": (
            "Teatro Comunale Saverio Mercadante, Piazza G. Matteotti, 1, Cerignola"
            if citta == "Cerignola" and luogo == "Teatro Comunale Saverio Mercadante"
            else f"{luogo}, {indirizzo_documentato}"
            if indirizzo_documentato
            else f"{luogo}, {citta}"
        ),
        "costo": costo,
        "descrizione": descrizione or f"{titolo} presso {luogo} ({citta}).",
        "fonteUrl": page_url
    }
    giorni = date_discontinue(testo_completo, ref)
    # Dividi soltanto quando il parser principale ha identificato lo stesso intervallo.
    if giorni and giorni[0] == d1 and giorni[-1] == d2:
        for giorno in giorni:
            if ricorrenza_compatibile(testo_completo, giorno):
                ev = normalizza_e_valida_evento(dict(raw, dataInizio=giorno, dataFine=giorno, dataTesto=formatta_data_italiano(giorno, giorno)), ref, fonte_curata_eventi=fonte_curata_eventi)
                if ev and not evento_non_attivo(ev):
                    risultati.append(ev)
        return risultati
    ev_ok = normalizza_e_valida_evento(raw, ref, fonte_curata_eventi=fonte_curata_eventi)
    return [ev_ok] if ev_ok and not evento_non_attivo(ev_ok) else []


def _contiene_anno_passato(testo):
    anni = [int(y) for y in re.findall(r"\b(20\d{2})\b", testo or "")]
    return bool(anni) and max(anni) < oggi_dt().year


def raccogli_da_portale_viva(session, fonte):
    eventi = []
    nome = fonte["nome"]
    url = fonte["url"]
    dominio = fonte["dominio"]
    c_def = fonte["citta_default"]
    solo_ev = fonte["solo_eventi"]

    try:
        r = session.get(url, timeout=(5, 9))
        if r.status_code != 200:
            registra_statistica_fonte(
                nome, stato=f"HTTP {r.status_code}", linkCandidati=0,
                pagineScaricate=0, eventiEstratti=0
            )
            print(f"{nome}: HTTP {r.status_code}")
            return []
        r.encoding = r.apparent_encoding or "utf-8"
        soup = BeautifulSoup(r.text, "html.parser")

        candidati = []
        visti = set()
        for a in soup.find_all("a", href=True):
            full = urljoin(url, a["href"]).split("#")[0].strip()
            pr = urlparse(full)
            if pr.scheme not in ("http", "https") or not _host_appartiene(full, dominio):
                continue
            p_low = pr.path.lower()
            if any(x in p_low for x in ESCLUSIONI_PATH_VIVA):
                continue
            if re.match(r"^/(?:eventi|notizie|spettacoli|tempo-libero)/?$", p_low):
                continue
            if not re.match(r"^/(?:eventi|notizie|spettacoli|tempo-libero)(?:/[a-z0-9_-]{3,})+/?(?:\.html)?$", p_low):
                continue

            chiave = f"{pr.netloc.lower()}{pr.path.rstrip('/').lower()}"
            if chiave in visti:
                continue
            t_link = re.sub(r"\s+", " ", a.get_text(" ", strip=True)).strip()
            if _contiene_anno_passato(f"{pr.path} {t_link}") or REGEX_SCARTO.search(t_link):
                continue
            if fonte.get("notizie_locali"):
                if not p_low.endswith(".html") or priorita_candidato_rss(t_link, "") < 0:
                    continue
            if solo_ev or "/eventi/" in p_low or REGEX_TEMA_COERENTE.search(t_link):
                visti.add(chiave)
                candidati.append(full)

        scaricate = 0
        for link in candidati[:12]:
            try:
                rp = session.get(link, timeout=(4, 7))
                if rp.status_code != 200:
                    continue
                scaricate += 1
                rp.encoding = rp.apparent_encoding or "utf-8"
                eventi.extend(analizza_pagina_evento(rp.text, link, citta_default=c_def, fonte_curata_eventi=solo_ev))
            except Exception:
                continue

        registra_statistica_fonte(
            nome, stato="ok", linkCandidati=len(candidati),
            pagineScaricate=scaricate, eventiEstratti=len(eventi)
        )
        print(f"{nome}: {len(eventi)} eventi estratti (da {scaricate} pagine)")
    except Exception as e:
        registra_statistica_fonte(
            nome, stato="errore", errore=str(e)[:120],
            linkCandidati=0, pagineScaricate=0, eventiEstratti=0
        )
        print(f"Errore {nome}: {str(e)[:75]}")

    return eventi




def estrai_testo_locandine(session, html_pagina="", item_feed=None, max_immagini=3, base_url=""):
    """Estrae testo da locandine pubbliche usando OCR locale, se Tesseract è installato."""
    immagini = []
    if item_feed is not None:
        for tag in item_feed.find_all(["enclosure", "media:content", "media:thumbnail"]):
            url_immagine = (tag.get("url") or tag.get("href") or "").strip()
            if url_immagine:
                url_immagine = urljoin(base_url, url_immagine)
                if url_immagine.startswith(("http://", "https://")):
                    immagini.append(url_immagine)
    if html_pagina:
        soup = BeautifulSoup(html_pagina, "html.parser")
        for meta in soup.select('meta[property="og:image"], meta[name="twitter:image"]'):
            url_immagine = (meta.get("content") or "").strip()
            if url_immagine:
                url_immagine = urljoin(base_url, url_immagine)
                if url_immagine.startswith(("http://", "https://")):
                    immagini.append(url_immagine)
        # Evita loghi, banner e immagini di navigazione estranee alla scheda.
        contenuto = soup.find("article") or soup.find("main")
        for img in (contenuto.find_all("img") if contenuto else soup.find_all("img")):
            segnali = " ".join(str(img.get(k, "")) for k in ("alt", "class", "id", "src", "data-src"))
            if re.search(r"\b(?:logo|avatar|banner|icon|favicon|sprite|advertisement|gravatar)\b", segnali, re.I):
                continue
            url_immagine = (img.get("data-src") or img.get("src") or "").strip()
            if url_immagine:
                url_immagine = urljoin(base_url, url_immagine)
                if url_immagine.startswith(("http://", "https://")):
                    immagini.append(url_immagine)
    immagini = list(dict.fromkeys(immagini))[:max_immagini]
    if not immagini:
        return ""
    try:
        from PIL import Image, ImageOps
        import pytesseract
    except ImportError:
        return ""
    testi = []
    for url_immagine in immagini:
        # Il budget è assegnato per fonte dal coordinatore. L'uso diretto resta compatibile.
        budget = getattr(session, "_csf_ocr_budget", None)
        if isinstance(budget, dict):
            if budget["rimanenti"] <= 0:
                break
            budget["rimanenti"] -= 1
        try:
            risposta = session.get(url_immagine, timeout=(4, 6))
            if risposta.status_code != 200 or not risposta.headers.get("Content-Type", "").lower().startswith("image/"):
                continue
            contenuto = risposta.content
            if not contenuto or len(contenuto) > 8 * 1024 * 1024:
                continue
            with Image.open(io.BytesIO(contenuto)) as originale:
                if originale.width * originale.height > OCR_MAX_PIXEL:
                    continue
                originale.thumbnail((1800, 1800))
                immagine = ImageOps.exif_transpose(originale.convert("RGBA")).convert("RGB")
            # Tesseract è CPU-bound: limita il numero di processi simultanei
            # e termina ogni singolo OCR che supera il tempo massimo.
            with _OCR_SLOT:
                testo = pytesseract.image_to_string(immagine, lang="ita+eng", config="--psm 6", timeout=OCR_TIMEOUT_SECONDI)
            testo = re.sub(r"\s+", " ", testo).strip()
            if len(testo) >= 20:
                testi.append(testo)
        except Exception:
            # Un'immagine corrotta, un formato non supportato o Tesseract assente
            # non devono interrompere la raccolta delle altre fonti.
            continue
    return " ".join(testi)[:5000]


def priorita_candidato_rss(titolo, descrizione):
    """Selezione dei link pubblici: non è una validazione di eventi."""
    testo = f"{titolo} {descrizione}"
    comune = _comune_nel_testo(testo)
    if not comune or REGEX_SCARTO.search(titolo):
        return -1
    if not re.search(r"\b(evento|serata|concerto|live|dj|party|aperitivo|capodanno|cenon|veglion|san silvestro|cena|gastronomic|clubbing|escursion|trekking|visita guidata|laboratorio|bambin|famigli|gita|passeggiat|camminat|cammino|birdwatching|cicloturismo|e-bike|masseria|fattoria|frantoio|caseificio|open day|family day|tour|mercatino|sagra|festa|locandina|natale|tombolata|show cooking|dinner show|music selection)\w*\b", testo, re.I):
        return -1
    punteggio = 10 if comune == "Cerignola" else 3
    if _comune_nel_testo(titolo):
        punteggio += 4
    if REGEX_TEMA_COERENTE.search(testo):
        punteggio += 3
    if re.search(r"\b(?:dj\s*set|party|karaoke|musica dal vivo|aperitivo|dinner show|show cooking|music selection|serata)\b", testo, re.I):
        punteggio += 6
    if re.search(r"\b\d{1,2}\s+(?:gennaio|febbraio|marzo|aprile|maggio|giugno|luglio|agosto|settembre|ottobre|novembre|dicembre)\b", testo, re.I):
        punteggio += 4
    return punteggio


def evento_capodanno_documentato(testo, url, fonte, poster=""):
    """Usa un singolo annuncio o una singola locandina, non il testo di tutto il sito."""
    testo = re.sub(r"\s+", " ", testo or "").strip()
    if re.search(r"\b(?:annullat[oa]|rinviat[oa]|si è svolto|si è concluso|evento passato|matrimonio)\b", testo, re.I):
        return []
    anno = fonte["anno_capodanno"]
    date = capodanno.date_documentate(testo, anno)
    # Due appuntamenti in un unico blocco: evitare di assegnare prezzi e orari
    # del cenone al pranzo. Servono due annunci separati.
    if len(date) != 1:
        return []
    sede = fonte.get("sede")
    if not sede:
        if _comune_nel_testo(testo) != "Cerignola":
            return []
        nomi = [r["nome"] for r in capodanno.registro()
                if any(re.search(r"(?<!\w)"+re.escape(a)+r"(?!\w)",testo,re.I) for a in r["alias"])]
        if len(nomi) != 1:
            return []
        sede = nomi[0]
    elif _comune_nel_testo(testo) not in ("",None,"Cerignola"):
        return []
    d = date[0]
    titolo = ("Cenone / veglione di Capodanno" if d.endswith("12-31") else "Pranzo di Capodanno")+" – "+sede
    orari = re.findall(r"\b(?:ore|h)\s*([01]?\d|2[0-3])[:.]([0-5]\d)\b",testo,re.I)
    prezzi = list(dict.fromkeys(re.findall(r"\b\d{1,3}(?:[.,]\d{2})?\s*€",testo)))
    costo = prezzi[0] if len(prezzi)==1 else "Consulta menu e prezzi nella fonte"
    desc = testo[:220] if len(testo)>=20 else "Verifica programma e prenotazioni nella fonte ufficiale."
    raw = {"titolo":titolo,"citta":"Cerignola","luogo":sede,"indirizzoMappa":sede+", Cerignola",
           "dataInizio":d,"dataFine":d,"dataTesto":formatta_data_italiano(d,d)+(f" · Ore {int(orari[0][0]):02d}:{orari[0][1]}" if len(orari)==1 else ""),
           "costo":costo,"descrizione":desc,"fonteUrl":url,"locandinaUrl":poster}
    ev = normalizza_e_valida_evento(raw,fonte_curata_eventi=True)
    return [ev] if ev else []


def evento_festivita_documentato(testo, url, fonte, poster=""):
    """Richiede un singolo annuncio, data esplicita e sede documentata."""
    testo=re.sub(r"\s+"," ",testo or "").strip()
    if re.search(r"\b(?:annullat[oa]|rinviat[oa]|si è svolto|si è concluso|evento passato|matrimonio)\b",testo,re.I):
        return []
    date=festivita.date_documentate(testo,fonte["anno_festivita"])
    if len(date)!=1:
        return []
    d=date[0]
    sede=fonte.get("sede")
    comune=_comune_nel_testo(testo)
    if sede and comune not in ("",None,"Cerignola"):
        return []
    if not sede:
        if comune!="Cerignola":
            return []
        nomi=[r["nome"] for r in capodanno.registro() if any(re.search(r"(?<!\w)"+re.escape(a)+r"(?!\w)",testo,re.I) for a in r["alias"])]
        if len(nomi)==1:
            sede=nomi[0]
        else:
            sede=estrai_luogo_documentato(testo,"Cerignola")
    if not _luogo_utilizzabile(sede):
        return []
    titolo=festivita.titolo_pasto(testo,d)
    if not titolo:
        for pat, label in ((r"\bpresepe\s+vivente\b","Presepe vivente"),(r"\bmercatin[oi]\b","Mercatini natalizi"),(r"\btombolat[ae]\b","Tombolata natalizia"),(r"\b(?:befana|epifania)\b","Festa dell'Epifania"),(r"\bvillaggio\b","Villaggio di Natale"),(r"\blaborator[io]+\b","Laboratorio natalizio"),(r"\bconcert[oi]\b","Concerto natalizio"),(r"\bluminarie\b","Accensione delle luminarie")):
            if re.search(pat,testo,re.I):
                titolo=label
                break
    if not titolo:
        return []
    titolo+=" – "+sede
    orari=list(dict.fromkeys(re.findall(r"\b(?:ore|h)\s*([01]?\d|2[0-3])[:.]([0-5]\d)\b",testo,re.I)))
    prezzi=list(dict.fromkeys(re.findall(r"\b\d{1,3}(?:[.,]\d{2})?\s*€",testo)))
    raw={"titolo":titolo,"citta":"Cerignola","luogo":sede,"indirizzoMappa":sede+", Cerignola","dataInizio":d,"dataFine":d,"dataTesto":formatta_data_italiano(d,d)+(f" · Ore {int(orari[0][0]):02d}:{orari[0][1]}" if len(orari)==1 else ""),"costo":prezzi[0] if len(prezzi)==1 else "Consulta la fonte","descrizione":testo[:220],"fonteUrl":url,"locandinaUrl":poster}
    ev=normalizza_e_valida_evento(raw,fonte_curata_eventi=True)
    return [ev] if ev else []


def evento_ricorrenza_documentato(testo,url,fonte,poster=""):
    testo=re.sub(r"\s+"," ",testo or "").strip()
    if re.search(r"\b(?:annullat[oa]|rinviat[oa]|si è svolto|si è concluso|evento passato)\b",testo,re.I):
        return []
    dates=ricorrenze.date_documentate(testo,fonte["ricorrenze_annuali"])
    if len(dates)!=1:
        return []
    d,nome=dates[0]
    sede=fonte.get("sede")
    comune=_comune_nel_testo(testo)
    if sede and comune not in ("",None,"Cerignola"):
        return []
    if not sede:
        if comune!="Cerignola":
            return []
        nomi=[r["nome"] for r in capodanno.registro() if any(re.search(r"(?<!\w)"+re.escape(a)+r"(?!\w)",testo,re.I) for a in r["alias"])]
        sede=nomi[0] if len(nomi)==1 else estrai_luogo_documentato(testo,"Cerignola")
    if not _luogo_utilizzabile(sede) or sede.casefold()=="cerignola":
        return []
    label=""
    for pat,n in ((r"\b(?:dj\s*set|party|serata)\b","Serata"),(r"\b(?:pranzo|brunch)\b","Pranzo"),(r"\b(?:cena|cenone)\b","Cena"),(r"\bconcert[oi]\b","Concerto"),(r"\bsfilat[ae]\b","Sfilata"),(r"\bfiera\b","Fiera"),(r"\bluna park\b","Luna park"),(r"\bfuochi pirotecnici\b","Fuochi pirotecnici"),(r"\b(?:laboratorio|animazione|festa per bambini)\b","Attività per famiglie"),(r"\b(?:escursione|pic\s*nic)\b","Attività all'aperto"),(r"\bspettacol[oi]\b","Spettacolo")):
        if re.search(pat,testo,re.I):
            label=n
            break
    if not label:
        return []
    titolo=f"{label} – {nome} – {sede}"
    orari=list(dict.fromkeys(re.findall(r"\b(?:ore|h)\s*([01]?\d|2[0-3])[:.]([0-5]\d)\b",testo,re.I)))
    prezzi=list(dict.fromkeys(re.findall(r"\b\d{1,3}(?:[.,]\d{2})?\s*€",testo)))
    raw={"titolo":titolo,"citta":"Cerignola","luogo":sede,"indirizzoMappa":sede+", Cerignola","dataInizio":d,"dataFine":d,"dataTesto":formatta_data_italiano(d,d)+(f" · Ore {int(orari[0][0]):02d}:{orari[0][1]}" if len(orari)==1 else ""),"costo":prezzi[0] if len(prezzi)==1 else "Consulta la fonte","descrizione":testo[:220],"fonteUrl":url,"locandinaUrl":poster}
    ev=normalizza_e_valida_evento(raw,fonte_curata_eventi=True)
    return [ev] if ev else []


def eventi_stagionali_documentati(testo,url,fonte,poster=""):
    eventi=[]
    if fonte.get("anno_capodanno"):
        eventi.extend(evento_capodanno_documentato(testo,url,fonte,poster))
    if fonte.get("anno_festivita"):
        eventi.extend(evento_festivita_documentato(testo,url,fonte,poster))
    if fonte.get("ricorrenze_annuali"):
        eventi.extend(evento_ricorrenza_documentato(testo,url,fonte,poster))
    return eventi


def analizza_capodanno_pubblico(session, html, url, fonte):
    soup = BeautifulSoup(html or "", "html.parser")
    for tag in soup(["script","style","nav","footer","header","aside"]):
        tag.decompose()
    eventi = []
    # Annunci singoli, evitando contenitori con più vecchie edizioni.
    blocks = soup.find_all(["article","section"],limit=50)
    for block in blocks:
        if block.find(["article","section"]):
            continue
        testo = block.get_text(" ",strip=True)
        if 30 <= len(testo) <= 3500:
            eventi.extend(eventi_stagionali_documentati(testo,url,fonte))
    if not blocks:
        cont = soup.find("main") or soup.body or soup
        testo = cont.get_text(" ",strip=True)
        if len(testo)<=3500:
            eventi.extend(eventi_stagionali_documentati(testo,url,fonte))
    # OCR per singola immagine, senza fondere locandine di date diverse.
    immagini = []
    for img in soup.find_all("img",limit=100):
        src = urljoin(url,str(img.get("data-src") or img.get("src") or ""))
        hint = " ".join(str(img.get(k,"")) for k in ("alt","title","src","data-src"))
        if urlparse(src).scheme in ("http","https") and (re.search(r"capodanno|cenone|veglione|silvestro|new.?year|31.?12|locandina|menu",hint,re.I) or (fonte.get("anno_festivita") and festivita.LINK.search(hint)) or ricorrenze.tema(hint.replace("-"," ").replace("_"," "),fonte.get("ricorrenze_annuali",[]))):
            immagini.append(src)
    for meta in soup.select('meta[property="og:image"]'):
        titolo_pagina=(soup.title.get_text(" ",strip=True) if soup.title else "")+" "+url
        if capodanno.TEMA.search(titolo_pagina) or (fonte.get("anno_festivita") and festivita.TEMA.search(titolo_pagina)) or ricorrenze.tema(titolo_pagina,fonte.get("ricorrenze_annuali",[])):
            immagini.append(urljoin(url,str(meta.get("content") or "")))
    for img in list(dict.fromkeys(immagini))[:3]:
        if urlparse(img).scheme not in ("http","https"):
            continue
        testo = estrai_testo_locandine(session,'<article><img src="'+escape(img,quote=True)+'"></article>',max_immagini=1,base_url=url)
        eventi.extend(eventi_stagionali_documentati(testo,url,fonte,img))
    # Preferire la scheda dotata di locandina, ma conservare solo un evento per sede e giorno.
    unici = {}
    for ev in eventi:
        k=(ev["luogo"].casefold(),ev["dataInizio"],ev["titolo"].casefold())
        if k not in unici or ev.get("locandinaUrl"):
            unici[k]=ev
    return list(unici.values())


def raccogli_capodanno_sito(session, fonte):
    nome,url = fonte["nome"],fonte["url"]
    eventi=[]
    scaricate=0
    try:
        r=session.get(url,timeout=(5,8))
        if r.status_code != 200:
            registra_statistica_fonte(nome,stato=f"HTTP {r.status_code}",eventiEstratti=0)
            return []
        if not _host_appartiene(r.url or url,fonte["dominio"]):
            registra_statistica_fonte(nome,stato="redirect esterno",eventiEstratti=0)
            return []
        r.encoding=r.apparent_encoding or "utf-8"
        scaricate=1
        eventi.extend(analizza_capodanno_pubblico(session,r.text,r.url or url,fonte))
        links=[]
        soup=BeautifulSoup(r.text,"html.parser")
        for a in soup.find_all("a",href=True):
            link=urljoin(r.url or url,a["href"]).split("#")[0]
            if not _host_appartiene(link,fonte["dominio"]) or urlparse(link).scheme not in ("http","https"):
                continue
            hint=link+" "+a.get_text(" ",strip=True)
            if re.search(r"capodanno|cenone|veglione|silvestro|new.?year",hint,re.I) or (fonte.get("anno_festivita") and festivita.LINK.search(hint)) or ricorrenze.tema(hint.replace("-"," ").replace("_"," "),fonte.get("ricorrenze_annuali",[])):
                if not _contiene_anno_passato(urlparse(link).path):
                    links.append(link)
        for link in list(dict.fromkeys(links))[:3]:
            if link.rstrip("/")==url.rstrip("/"):
                continue
            try:
                rp=session.get(link,timeout=(4,7))
                if rp.status_code==200 and _host_appartiene(rp.url or link,fonte["dominio"]):
                    scaricate+=1
                    rp.encoding=rp.apparent_encoding or "utf-8"
                    eventi.extend(analizza_capodanno_pubblico(session,rp.text,rp.url or link,fonte))
            except requests.RequestException:
                continue
        registra_statistica_fonte(nome,stato="ok",linkCandidati=len(links),pagineScaricate=scaricate,eventiEstratti=len(eventi))
    except Exception as exc:
        registra_statistica_fonte(nome,stato="errore",errore=str(exc)[:120],pagineScaricate=scaricate,eventiEstratti=len(eventi))
    return eventi


def raccogli_da_feed_social(session, fonte):
    """Legge contenuti pubblici indicizzati; non accede a profili privati o Stories effimere."""
    nome = fonte["nome"]
    eventi = []
    candidati = 0
    scaricate = 0
    try:
        risposta = session.get(fonte["url"], timeout=(6, 12))
        if risposta.status_code != 200:
            registra_statistica_fonte(nome, stato=f"HTTP {risposta.status_code}", linkCandidati=0, pagineScaricate=0, eventiEstratti=0)
            print(f"{nome}: HTTP {risposta.status_code}")
            return []
        # RSS è XML: il parser HTML tratta <link> come tag vuoto e perde gli URL.
        feed = BeautifulSoup(risposta.content, "xml")
        items = feed.find_all("item")
        candidati = len(items)
        tentativi_scheda = 0
        classificati = []
        for item in items[:100]:
            titolo_el = item.find("title")
            link_el = item.find("link")
            desc_el = item.find("description")
            titolo = re.sub(r"\s+", " ", titolo_el.get_text(" ", strip=True) if titolo_el else "").strip()
            link = (link_el.get_text(" ", strip=True) if link_el else "").strip()
            descrizione = BeautifulSoup(desc_el.get_text(" ", strip=True) if desc_el else "", "html.parser").get_text(" ", strip=True)
            punteggio = priorita_candidato_rss(titolo, descrizione)
            if fonte.get("solo_cerignola") and _comune_nel_testo(titolo + " " + descrizione) != "Cerignola":
                continue
            if fonte.get("ricorrenze_annuali") and ricorrenze.tema(titolo+" "+descrizione,fonte["ricorrenze_annuali"]) and ricorrenze.FORMATO.search(titolo+" "+descrizione) and not REGEX_SCARTO.search(titolo):
                punteggio=max(punteggio,10)
            if punteggio < 0 or not link or not titolo:
                continue
            if urlparse(link).scheme not in ("http", "https") or not urlparse(link).hostname:
                continue
            if fonte.get("anno_capodanno") and not capodanno.TEMA.search(titolo + " " + descrizione):
                continue
            if fonte.get("anno_festivita") and not festivita.TEMA.search(titolo + " " + descrizione):
                continue
            if fonte.get("ricorrenze_annuali") and not ricorrenze.tema(titolo+" "+descrizione,fonte["ricorrenze_annuali"]):
                continue
            if fonte.get("nightlife") and not indizi_movida(titolo + " " + descrizione):
                continue
            classificati.append((punteggio, item, titolo, link, descrizione))
        # Ordina tutti i candidati: il budget di rete resta invariato.
        classificati.sort(key=lambda x: -x[0])
        if fonte.get("solo_scoperta"):
            registra_statistica_fonte(nome, stato="ok", linkCandidati=candidati, pagineScaricate=0, eventiEstratti=0, candidatiDaVerificare=[{"titolo": x[2][:160], "url": x[3]} for x in classificati[:12]])
            return []
        visti_link = set()
        for _, item, titolo, link, descrizione in classificati:
            if tentativi_scheda >= min(6, int(fonte.get("max_schede_rss", 6))):
                break
            if link in visti_link:
                continue
            visti_link.add(link)
            tentativi_scheda += 1
            url_finale = link
            html_pagina = ""
            try:
                pagina = session.get(link, timeout=(5, 9), allow_redirects=True)
                if pagina.status_code == 200 and "html" in pagina.headers.get("Content-Type", "text/html").lower():
                    scaricate += 1
                    url_finale = pagina.url or link
                    pagina.encoding = pagina.apparent_encoding or "utf-8"
                    html_pagina = pagina.text
            except requests.RequestException:
                pass
            # La pagina intermedia di Google News non è la fonte originale.
            if _host_appartiene(url_finale, "news.google.com"):
                html_pagina = ""
            if fonte.get("anno_capodanno") or fonte.get("anno_festivita") or fonte.get("ricorrenze_annuali"):
                # Non pubblicare da snippet Google News senza fonte primaria leggibile.
                if html_pagina:
                    eventi.extend(analizza_capodanno_pubblico(session, html_pagina, url_finale, fonte))
                continue
            estratti = analizza_pagina_evento(html_pagina, url_finale, citta_default="", fonte_curata_eventi=False) if html_pagina else []
            if not estratti and not (html_pagina and registra_stati_negativi(html_pagina, url_finale)):
                testo_locandina = estrai_testo_locandine(session, html_pagina, item_feed=item, max_immagini=1, base_url=url_finale)
                testo_social = " ".join(x for x in (descrizione, testo_locandina) if x)
                # Il motore può mostrare testo e immagine del post anche se Meta impedisce l'apertura.
                # La sede non viene mai inventata: deve comparire nel testo o nella locandina.
                html_snippet = "<html><body><h1>" + escape(titolo) + "</h1><main><p>" + escape(testo_social) + "</p></main></body></html>"
                estratti = analizza_pagina_evento(html_snippet, url_finale, citta_default="", fonte_curata_eventi=False)
            if fonte.get("nightlife"):
                estratti = [e for e in estratti if evento_movida_documentato(e)]
            if fonte.get("solo_cerignola"):
                estratti = [e for e in estratti if e.get("citta") == "Cerignola"]
            eventi.extend(estratti)
        registra_statistica_fonte(nome, stato="ok", linkCandidati=candidati, pagineScaricate=scaricate, eventiEstratti=len(eventi))
        print(f"{nome}: {len(eventi)} eventi estratti da {candidati} risultati indicizzati; {tentativi_scheda} schede interrogate, {scaricate} lette")
    except Exception as exc:
        registra_statistica_fonte(nome, stato="errore", errore=str(exc)[:120], linkCandidati=candidati, pagineScaricate=scaricate, eventiEstratti=len(eventi))
        print(f"Errore {nome}: {str(exc)[:75]}")
    return eventi


def estrai_eventi_puglia_da_elenco(soup, base_url, citta_default="Cerignola"):
    """Estrae gli appuntamenti dalle card ufficiali Puglia Culture quando le singole schede non sono leggibili."""
    if not _host_appartiene(base_url, "pugliaculture.it"):
        return []

    eventi = []
    visti = set()
    for link in soup.find_all("a", href=True):
        url_evento = urljoin(base_url, link.get("href", "")).split("#")[0].strip()
        if not _host_appartiene(url_evento, "pugliaculture.it"):
            continue
        if not urlparse(url_evento).path.lower().startswith("/evento/"):
            continue

        titolo = re.sub(r"\\s+", " ", link.get_text(" ", strip=True)).strip()
        if len(titolo) < 5 or REGEX_SCARTO.search(titolo):
            continue

        chiave = (url_evento.rstrip("/").lower(), titolo.casefold())
        if chiave in visti:
            continue

        testo_card = ""
        data_inizio = data_fine = data_testo = ""
        luogo = ""
        for antenato in link.parents:
            if getattr(antenato, "name", None) in {"body", "html"}:
                break
            testo_candidato = re.sub(r"\\s+", " ", antenato.get_text(" ", strip=True)).strip()
            if not (40 <= len(testo_candidato) <= 1400):
                continue
            d1, d2, d_txt = estrai_date_italiano(testo_candidato)
            if not d1:
                continue
            comune_card = _comune_nel_testo(testo_candidato)
            # Non risalire a contenitori più grandi dopo aver trovato una card
            # datata di un altro comune: si rischierebbe di associare al link
            # eventi e sedi della card precedente.
            if comune_card != citta_default:
                break
            sede = estrai_luogo_documentato(antenato, citta_default)
            if not sede:
                break
            testo_card = testo_candidato
            data_inizio, data_fine, data_testo = d1, d2, d_txt
            luogo = sede
            break

        if not testo_card:
            continue

        indirizzo_documentato = estrai_indirizzo_documentato(testo_card, citta_default)
        indirizzo = (
            "Teatro Comunale Saverio Mercadante, Piazza G. Matteotti, 1, Cerignola"
            if citta_default == "Cerignola" and "mercadante" in luogo.casefold()
            else f"{luogo}, {indirizzo_documentato}"
            if indirizzo_documentato
            else f"{luogo}, {citta_default}"
        )
        evento = normalizza_e_valida_evento({
            "citta": citta_default,
            "categoria": classifica_categoria(testo_card, luogo=luogo, fonte_url=url_evento),
            "titolo": titolo,
            "dataTesto": data_testo,
            "dataInizio": data_inizio,
            "dataFine": data_fine,
            "luogo": luogo,
            "indirizzoMappa": indirizzo,
            "costo": estrai_costo_documentato(testo_card),
            "descrizione": f"{titolo} presso {luogo} ({citta_default}).",
            "fonteUrl": url_evento,
        }, fonte_curata_eventi=True)
        if evento:
            eventi.append(evento)
            visti.add(chiave)

    return eventi


def indizi_movida(testo):
    return bool(re.search(r"\b(?:nightlife|dj[\s-]*set|deejay|discotec\w*|club night|clubbing|opening(?:\s+winter|\s+summer)?\s+season|opening party|dinner (?:show|party)|cena spettacolo|karaoke|serat[ae] latin[ae]|reggaeton|techno|house music|vinyl (?:set|diwine)|aperitiv[oi] musical\w*|musica dal vivo|live music|cover band|tribute band|after show|music selection)\b", testo or "", re.I))


def data_scheda_movida(url):
    """Usa una data esplicita nel permalink come filtro, mai come unica prova."""
    path = urlparse(url).path.rstrip("/").lower()
    iso = re.search(r"(20\d{2}-\d{2}-\d{2})$", path)
    if iso and _data_iso_valida(iso.group(1)):
        return iso.group(1)
    m = re.search(r"-(\d{1,2})-(" + "|".join(MESI_IT) + r")-(20\d{2})$", path)
    if m:
        d = _costruisci_data_sicura(int(m.group(1)), MESI_IT[m.group(2)], int(m.group(3)))
        return d.strftime("%Y-%m-%d") if d else ""
    return ""


def evento_movida_documentato(ev):
    if ev.get("categoria") == "Locali & Serate":
        return True
    if ev.get("categoria") not in {"Musica & Concerti", "Attività diurne", "Sagre & Food"}:
        return False
    testo = " ".join(str(ev.get(k) or "") for k in ("titolo", "descrizione", "luogo"))
    if indizi_movida(testo):
        return True
    # Live tribute / band in an actual pub or club, not a concert in a theatre.
    sede = str(ev.get("luogo") or "")
    return bool(re.search(r"\b(?:pub|discopub|lounge|bistrot|bohemien|bohémien|club|bar)\b", sede, re.I)
                and re.search(r"\b(?:live|tribut[eo]|band|rock.blues|concerto)\b", testo, re.I))


def xceed_eventi_strutturati(soup, url, citta):
    """None = dati evento assenti; [] = dati presenti ma non validabili.
    Non accetta eventi correlati, sedi generiche o date incompatibili."""
    candidati = []
    for tag in soup.find_all("script", type="application/ld+json"):
        try:
            estrai_eventi_jsonld(json.loads(tag.string or tag.get_text()), candidati)
        except (TypeError, ValueError):
            continue
    if not candidati:
        return None
    def norm(s):
        return " ".join(re.findall(r"[a-z0-9à-ù]+", str(s or "").casefold()))
    h1 = soup.find("h1")
    titolo_pagina = h1.get_text(" ",strip=True) if h1 else ""
    if not titolo_pagina:
        return []
    id_evento = urlparse(url).path.rstrip("/").split("/")[-1]
    risultati = []
    for ev in candidati:
        titolo = str(ev.get("name") or "").strip()
        url_ld = urljoin(url, str(ev.get("url") or ""))
        if not _host_appartiene(url_ld, "xceed.me") or urlparse(url_ld).path.rstrip("/").split("/")[-1] != id_evento:
            continue
        if norm(titolo) != norm(titolo_pagina):
            continue
        stato = str(ev.get("eventStatus") or "").casefold()
        if any(x in stato for x in ("cancelled","postponed","movedonline")):
            continue
        inizio = str(ev.get("startDate") or "")
        if not _data_iso_valida(inizio[:10]):
            continue
        # I timestamp UTC espliciti vanno convertiti nel fuso dell'evento.
        try:
            dt = datetime.fromisoformat(inizio.replace("Z","+00:00"))
            if dt.tzinfo is not None:
                dt = dt.astimezone(ZoneInfo("Europe/Rome"))
        except ValueError:
            continue
        data = dt.strftime("%Y-%m-%d")
        if not oggi_iso() <= data <= (oggi_dt()+timedelta(days=90)).strftime("%Y-%m-%d"):
            continue
        mesi = "|".join(MESI_IT)
        pat = rf"\b(\d{{1,2}})\s+({mesi})\s*(20\d{{2}})?\b"
        # Una data nel titolo deve concordare con quella della scheda.
        if any(int(m.group(1)) != dt.day or MESI_IT[m.group(2).casefold()] != dt.month or (m.group(3) and int(m.group(3)) != dt.year) for m in re.finditer(pat,titolo,re.I)):
            continue
        loc = ev.get("location")
        if not isinstance(loc,dict):
            continue
        luogo = str(loc.get("name") or "").strip()
        addr = loc.get("address")
        if not isinstance(addr,dict) or not luogo or re.search(r"\b(?:secret|riservat|segreta|tba|tbc|to be announced)\w*\b", luogo, re.I):
            continue
        localita = str(addr.get("addressLocality") or "").strip()
        via = str(addr.get("streetAddress") or "").strip()
        if _comune_nel_testo(localita) != citta or not via:
            continue
        paese = addr.get("addressCountry")
        if isinstance(paese,dict):
            paese = paese.get("name")
        if paese and str(paese).casefold() not in {"it","ita","italia","italy"}:
            continue
        desc = BeautifulSoup(str(ev.get("description") or ""), "html.parser").get_text(" ",strip=True)
        # Se la promozione cita una sola data dello stesso mese incompatibile,
        # non pubblicare: è un possibile riuso di una vecchia locandina.
        date_desc = {(int(m.group(1)),MESI_IT[m.group(2).casefold()],int(m.group(3)) if m.group(3) else dt.year) for m in re.finditer(pat,desc,re.I)}
        if len(date_desc)==1 and any(x[1]==dt.month and x!=(dt.day,dt.month,dt.year) for x in date_desc):
            continue
        if not ricorrenza_compatibile(desc,data):
            continue
        orario = (" · Ore "+dt.strftime("%H:%M")) if "T" in inizio and dt.strftime("%H:%M")!="00:00" else ""
        record = normalizza_e_valida_evento({"titolo":titolo, "citta":citta, "luogo":luogo, "indirizzoMappa":f"{via}, {citta}", "dataInizio":data, "dataFine":data, "dataTesto":formatta_data_italiano(data,data)+orario, "descrizione":("Serata in club. "+desc)[:220], "costo":"Consulta la biglietteria", "fonteUrl":url}, fonte_curata_eventi=True)
        if record and not evento_non_attivo(record):
            record["categoria"] = "Locali & Serate"
            risultati.append(record)
    return risultati


def analizza_xceed(html_text, url, citta):
    """Scheda individuale Xceed: verifica data principale e città dell'indirizzo."""
    if not re.fullmatch(r"/it/[^/]+/event/[^/]+/\d+/?", urlparse(url).path):
        return []
    soup = BeautifulSoup(html_text, "html.parser")
    strutturati = xceed_eventi_strutturati(soup,url,citta)
    if strutturati is not None:
        return strutturati
    h1 = soup.find("h1")
    if not h1:
        return []
    titolo = h1.get_text(" ", strip=True)
    mesi = "|".join(MESI_IT)
    pat = rf"\b(\d{{1,2}})\s+({mesi})\s+(20\d{{2}})\b"
    # Non dipendere da una singola stringa per H1: i componenti web possono
    # dividere titolo, data, orario e intestazioni in più nodi.
    def sezione(etichette, max_nodi=30):
        for tag in soup.find_all(["h2","h3","h4","h5","h6","div","span","p","strong"]):
            if tag.get_text(" ", strip=True).casefold().strip(": ") not in etichette:
                continue
            pezzi = []
            for nodo in tag.next_elements:
                if nodo is tag or tag in getattr(nodo, "parents", []):
                    continue
                if getattr(nodo,"name",None) in {"h1","h2","h3","h4","h5","h6"} and pezzi:
                    break
                if isinstance(nodo, str) and nodo.strip():
                    if nodo.strip().casefold() in {"info","biglietti","artisti","location","indirizzo","address","venue","luogo"} and pezzi:
                        break
                    pezzi.append(nodo.strip())
                    if len(pezzi) >= max_nodi:
                        break
            if pezzi:
                return " ".join(pezzi)
        return ""
    pezzi = []
    for nodo in h1.next_elements:
        if h1 in getattr(nodo,"parents",[]):
            continue
        if getattr(nodo,"name",None) in {"h1","h2","h3","h4"} and pezzi:
            break
        if isinstance(nodo,str) and nodo.strip():
            if nodo.strip().casefold() in {"info","biglietti","location"}:
                break
            pezzi.append(nodo.strip())
            if len(pezzi) >= 15:
                break
    prima = " ".join(pezzi)
    m = re.search(pat, prima, re.I)
    if not m:
        return []
    dt = _costruisci_data_sicura(int(m.group(1)), MESI_IT[m.group(2).lower()], int(m.group(3)))
    if not dt:
        return []
    data = dt.strftime("%Y-%m-%d")
    for m2 in re.finditer(pat, titolo, re.I):
        if (int(m2.group(1)), MESI_IT[m2.group(2).lower()], int(m2.group(3))) != (dt.day, dt.month, dt.year):
            return []
    luogo = sezione({"location","luogo","venue"}, 5)
    indirizzo = sezione({"indirizzo","address"}, 5)
    if not luogo or not indirizzo or _comune_nel_testo(indirizzo) != citta:
        return []
    luogo = re.sub(rf",\s*{re.escape(citta)}\s*$","",luogo,flags=re.I)
    info = sezione({"info","informazioni","description"}, 8)
    for old in re.finditer(pat, info, re.I):
        if int(old.group(1)) == dt.day and MESI_IT[old.group(2).lower()] == dt.month and int(old.group(3)) != dt.year:
            return []
    ora = re.search(r"\b(?:alle ore|ore)\s*([01]\d|2[0-3]):([0-5]\d)", prima, re.I)
    d_txt = formatta_data_italiano(data,data) + (" · Ore "+ora.group(1)+":"+ora.group(2) if ora else "")
    ev = normalizza_e_valida_evento({"titolo":titolo, "citta":citta, "dataInizio":data, "dataFine":data, "dataTesto":d_txt, "luogo":luogo[:120], "indirizzoMappa":indirizzo[:200], "descrizione":("Serata in club. " + info)[:220], "fonteUrl":url, "costo":"Consulta la biglietteria"}, fonte_curata_eventi=True)
    if not ev or evento_non_attivo(ev):
        return []
    ev["categoria"] = "Locali & Serate"
    return [ev]



def analizza_ticketsms(html_text, url, citta, luogo):
    """Solo schede TicketSms di club noto: data del permalink e data visibile concordanti."""
    if not _host_appartiene(url, "ticketsms.it"):
        return []
    path = urlparse(url).path
    m = re.search(r"-(\d{2})-(\d{2})-(20\d{2})/?$", path)
    if not re.match(r"^/(?:it/)?event/[^/]+/?$", path, re.I) or not m:
        return []
    dt = _costruisci_data_sicura(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    if not dt or dt.strftime("%Y-%m-%d") < oggi_iso():
        return []
    soup = BeautifulSoup(html_text, "html.parser")
    if registra_stati_negativi(html_text, url):
        return []
    h1 = soup.find("h1")
    if not h1:
        return []
    titolo = h1.get_text(" ", strip=True)
    testo = soup.get_text(" ", strip=True)
    mesi = "|".join(MESI_IT)
    data_testo = re.search(rf"\b(\d{{1,2}})\s+({mesi})\s+(20\d{{2}})\s*/\s*([01]\d|2[0-3]):([0-5]\d)\b", testo, re.I)
    if not data_testo or (int(data_testo.group(1)), MESI_IT[data_testo.group(2).lower()], int(data_testo.group(3))) != (dt.day, dt.month, dt.year):
        return []
    if not re.search(rf"{re.escape(luogo)}\s*/\s*{re.escape(citta)}\b", testo, re.I):
        return []
    data = dt.strftime("%Y-%m-%d")
    ev = normalizza_e_valida_evento({"titolo":titolo, "citta":citta, "luogo":luogo, "indirizzoMappa":f"{luogo}, {citta}", "dataInizio":data, "dataFine":data, "dataTesto":formatta_data_italiano(data,data)+" · Ore "+data_testo.group(4)+":"+data_testo.group(5), "descrizione":"Serata in discoteca pubblicata in biglietteria. Verifica disponibilità e condizioni di ingresso.", "costo":"Consulta la biglietteria", "fonteUrl":url}, fonte_curata_eventi=True)
    if not ev:
        return []
    ev["categoria"] = "Locali & Serate"
    return [ev]


def analizza_nightz(html_text, url):
    """Scheda individuale Nightz, con data e località dichiarate esplicitamente."""
    if not _host_appartiene(url, "nightz.it") or not re.fullmatch(r"/eventi/[^/]+/?", urlparse(url).path):
        return []
    if registra_stati_negativi(html_text, url):
        return []
    soup = BeautifulSoup(html_text, "html.parser")
    h1 = soup.find("h1")
    if not h1:
        return []
    righe = list(soup.stripped_strings)
    def dopo(label, n=4):
        for i, riga in enumerate(righe):
            if riga.casefold().strip(": ") == label:
                return righe[i+1:i+1+n]
        return []
    data = " ".join(dopo("data e orario", 4))
    m = re.search(r"\b(\d{1,2})\s+("+"|".join(MESI_IT)+r")\s+(20\d{2})\b", data, re.I)
    if not m:
        return []
    dt = _costruisci_data_sicura(int(m.group(1)), MESI_IT[m.group(2).casefold()], int(m.group(3)))
    if not dt or dt.strftime("%Y-%m-%d") < oggi_iso():
        return []
    loc = dopo("location", 3)
    if len(loc) < 2:
        return []
    comune = COMUNI_50KM.get(loc[0].strip().casefold())
    indirizzo = loc[1].strip()
    if not comune or _comune_nel_testo(indirizzo) != comune:
        return []
    luogo = indirizzo.split(",")[0].strip()
    ora = re.search(r"\b(?:dalle|ore)\s*([01]\d|2[0-3]):([0-5]\d)", data, re.I)
    d = dt.strftime("%Y-%m-%d")
    ev = normalizza_e_valida_evento({"titolo":h1.get_text(" ",strip=True), "citta":comune, "luogo":luogo, "indirizzoMappa":indirizzo, "dataInizio":d, "dataFine":d, "dataTesto":formatta_data_italiano(d,d)+(" · Ore "+ora.group(1)+":"+ora.group(2) if ora else ""), "descrizione":"Serata pubblicata sul calendario Nightz. Verifica condizioni di ingresso e disponibilità con il locale.", "costo":"Consulta la fonte", "fonteUrl":url}, fonte_curata_eventi=True)
    if not ev:
        return []
    ev["categoria"] = "Locali & Serate"
    return [ev]


def diagnostica_scheda_movida(html_text, url):
    """Metadati pubblici minimali, utili per distinguere markup vuoto da parser errato."""
    soup = BeautifulSoup(html_text, "html.parser")
    h1 = soup.find("h1")
    strutturati = []
    for tag in soup.find_all("script", type="application/ld+json"):
        try:
            estrai_eventi_jsonld(json.loads(tag.string or tag.get_text()), strutturati)
        except (TypeError,ValueError):
            continue
    dettagli = []
    for ev in strutturati[:3]:
        loc = ev.get("location") if isinstance(ev.get("location"),dict) else {}
        addr = loc.get("address") if isinstance(loc.get("address"),dict) else {}
        dettagli.append({"tipo":ev.get("@type"), "nome":str(ev.get("name") or "")[:120], "startDate":str(ev.get("startDate") or "")[:40], "url":str(ev.get("url") or "")[:250], "sede":str(loc.get("name") or "")[:100], "comune":str(addr.get("addressLocality") or "")[:100], "via":str(addr.get("streetAddress") or "")[:120], "stato":str(ev.get("eventStatus") or "")[:100]})
    return {"url":url, "h1":h1.get_text(" ",strip=True)[:120] if h1 else "", "jsonld":len(soup.find_all("script", type="application/ld+json")), "eventiStrutturati":dettagli, "etichette":[x for x in ("Location","Indirizzo","Data e orario","Info") if x.casefold() in soup.get_text(" ",strip=True).casefold()], "lunghezzaHTML":len(html_text)}


def registro_locali_movida():
    try:
        with open(os.path.join(os.path.dirname(__file__), "fonti_movida.json"), encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d,dict) else {}
    except (OSError, ValueError):
        return {}


def registro_cerignola():
    """Anagrafica di organizzatori: non costituisce prova di un evento."""
    try:
        with open(os.path.join(os.path.dirname(__file__), "fonti_cerignola.json"), encoding="utf-8") as f:
            dati = json.load(f)
        return [r for r in dati if isinstance(r, dict)] if isinstance(dati, list) else []
    except (OSError, ValueError):
        return []


def fonti_registro_cerignola(registro=None):
    """Ricerche raggruppate senza troncare i nomi quando cresce il registro.
    Le pagine anagrafiche non vengono convertite in eventi.
    """
    registro = registro_cerignola() if registro is None else registro
    temi = {
        "movida": '(serata OR "dj set" OR party OR karaoke OR aperitivo OR "musica dal vivo" OR clubbing)',
        "associazioni": '(festa OR concerto OR festival OR spettacolo OR musica OR mercatini)',
        "famiglie": '(laboratorio OR bambini OR festa OR spettacolo OR mercatini OR Natale)',
        "gastronomia": '(degustazione OR "cena evento" OR "cena a tema" OR "dinner show" OR "show cooking" OR sagra OR "visita guidata")',
    }
    fonti = []
    for gruppo, tema in temi.items():
        alias = list(dict.fromkeys(
            a.strip().replace('"', '') for r in registro if r.get("gruppo") == gruppo
            for a in r.get("alias", []) if isinstance(a, str) and len(a.strip()) >= 3
        ))
        if not alias:
            continue
        for indice in range(0, len(alias), 12):
            nomi = " OR ".join('"' + a + '"' for a in alias[indice:indice+12])
            q = f"Cerignola ({nomi}) {tema} when:30d"
            url = "https://news.google.com/rss/search?" + urlencode(
                {"q": q, "hl": "it", "gl": "IT", "ceid": "IT:it"}
            )
            fonti.append({"nome": "Registro Cerignola - " + gruppo + (f" {indice//12+1}" if indice else ""),
                          "url": url, "citta_default": "", "solo_cerignola": True,
                          "max_schede_rss": 3})
    return fonti


def calendari_registro_cerignola(registro=None):
    registro = registro_cerignola() if registro is None else registro
    fonti = []
    for r in registro:
        url = r.get("calendario", "")
        # Solo calendari individuali con schema di link già supportato.
        if not isinstance(url, str) or not _host_appartiene(url, "iltaccodibacco.it"):
            continue
        if urlparse(url).scheme != "https" or not re.fullmatch(r"/cerignola/[^/]+/?", urlparse(url).path):
            continue
        fonti.append({"nome": "Calendario Cerignola - " + r["nome"], "url": url,
                      "dominio": "iltaccodibacco.it", "citta_default": "",
                      "curata": True, "prefisso_schede": "/puglia/eventi/",
                      "max_schede": 8, "solo_cerignola": True})
    return fonti


def atlas_data_locale(val):
    if not isinstance(val,str) or not re.match(r"^20\d{2}-\d{2}-\d{2}T",val):
        return None
    try:
        dt = datetime.fromisoformat(val.replace("Z","+00:00"))
        # Un timestamp senza fuso non permette di determinare con certezza la data italiana.
        return dt.astimezone(ZoneInfo("Europe/Rome")) if dt.tzinfo is not None else None
    except ValueError:
        return None


def analizza_evento_atlas(ev, registro=None):
    """Legge il record della API pubblica; fonte citata e link alla pagina della data.
    Non interpreta valori di stato ignoti e non inventa sede, giorno o tariffa."""
    if not isinstance(ev,dict) or ev.get("kind") != "PARTY" or ev.get("countryCode") != "IT":
        return None,"tipo/paese"
    if not isinstance(ev.get("city"),str):
        return None,"comune non testuale"
    citta = COMUNI_50KM.get(ev["city"].strip().casefold())
    if not citta:
        return None,"fuori area"
    url = ev.get("webUrl")
    if not isinstance(url,str) or not _host_appartiene(url,"lineupatlas.com") or urlparse(url).scheme!="https" or not re.search(r"/(?:soirees|parties|serate)/[^/]+/?$",urlparse(url).path):
        return None,"scheda non individuale"
    dt = atlas_data_locale(ev.get("startsAt"))
    if not dt:
        return None,"data/fuso non validi"
    d = dt.strftime("%Y-%m-%d")
    if not oggi_iso() <= d <= (oggi_dt()+timedelta(days=90)).strftime("%Y-%m-%d"):
        return None,"fuori finestra"
    stato = str(ev.get("cancelState") or "").strip().casefold()
    if stato in {"cancelled","canceled","postponed","eventcancelled","eventpostponed"} or ev.get("postponedTo"):
        # Elimina soltanto la stessa scheda Atlas e la stessa data, non una
        # corrispondenza approssimativa di un'altra fonte.
        key = chiave_stato_evento(url,d)
        if key:
            with _LOCK_STATISTICHE:
                STATI_EVENTI_NEGATIVI.add(key)
        return None,"annullamento/rinvio"
    if "cancelState" not in ev or stato not in {"","none","active","scheduled","normal","confirmed","not_cancelled","not_canceled"}:
        return None,"stato non riconosciuto"
    titolo = ev.get("title")
    luogo = ev.get("venue")
    indirizzo = ev.get("venueAddress")
    if not all(isinstance(x,str) and x.strip() for x in (titolo,luogo,indirizzo)):
        return None,"sede o titolo incompleto"
    if re.search(r"\b(?:secret|riservat\w*|segreta|tba|tbc|to be announced)\b",luogo+" "+indirizzo,re.I):
        return None,"sede riservata"
    if _comune_nel_testo(indirizzo) != citta:
        return None,"indirizzo senza comune concordante"
    # Due schede con descrizioni discordanti già riscontrate nelle fonti primarie.
    # Atlas aggrega le stesse biglietterie: non usarlo per aggirarne le anomalie.
    if (("haivai" in titolo.casefold() and d=="2026-11-27") or ("natale" in titolo.casefold() and "atrio22" in titolo.casefold() and d=="2026-12-25")):
        return None,"discordanza primaria nota"
    mesi = "|".join(MESI_IT)
    for m in re.finditer(rf"\b(\d{{1,2}})\s+({mesi})\s*(20\d{{2}})?\b",titolo,re.I):
        if int(m.group(1))!=dt.day or MESI_IT[m.group(2).casefold()]!=dt.month or (m.group(3) and int(m.group(3))!=dt.year):
            return None,"data titolo discordante"
    # PARTY non basta: la stessa API ha restituito anche un concerto di Baglioni.
    registro = registro if isinstance(registro,dict) else registro_locali_movida()
    noto = any(alias.casefold() in luogo.casefold() for club in registro.get(citta,[]) for alias in club.get("alias",[]))
    generi = ev.get("genres")
    generi = " ".join(x for x in generi if isinstance(x,str)) if isinstance(generi,list) else str(generi or "")
    elettronica = bool(re.search(r"\b(?:techno|house|electronic\w*|elettronic\w*|trance|hardstyle|drum\s*(?:and|&|n)\s*bass|reggaeton|disco|minimal|afro house|garage|dubstep)\b",generi,re.I))
    if not (noto or elettronica or indizi_movida(titolo)):
        return None,"non nightlife"
    # Il prezzo dell'API è indicativo; non convertire valute e non inventare un prezzo.
    prezzo = ev.get("priceFromCents")
    costo = "Consulta la fonte e la biglietteria"
    if isinstance(prezzo,int) and not isinstance(prezzo,bool) and prezzo>=0 and ev.get("currency")=="EUR":
        costo = ("Da "+format(prezzo/100,".2f").replace(".",",")+" € (indicativo)") if prezzo else "Prezzo indicato da 0 €; verifica la biglietteria"
    if ev.get("soldOut") is True:
        costo += " · Esaurito secondo la fonte"
    testo = "Fonte: Lineup Atlas. Serata in locale. Verifica prevendita e disponibilità nella scheda."
    if generi:
        testo += " Generi: "+generi[:100]+"."
    d_txt = formatta_data_italiano(d,d)
    if ev.get("timeTbd") is False:
        d_txt += " · Ore "+dt.strftime("%H:%M")
    record = normalizza_e_valida_evento({"titolo":titolo,"citta":citta,"luogo":luogo,"indirizzoMappa":indirizzo,"dataInizio":d,"dataFine":d,"dataTesto":d_txt,"descrizione":testo,"costo":costo,"fonteUrl":url,"categoria":"Locali & Serate"},fonte_curata_eventi=True)
    if not record:
        return None,"validazione generale"
    record["categoria"] = "Locali & Serate"
    return record,"ok"


def esplora_lineup_atlas(session, fonte):
    """API ufficiale, un'ora di cache per query, massimo 50 record per richiesta."""
    nome = fonte["nome"]
    path = os.path.join(".csf-state", "lineup-atlas-"+fonte.get("cache","bat")+".json")
    dati = {}
    try:
        with open(path, encoding="utf-8") as f:
            dati = json.load(f)
    except (OSError, ValueError):
        pass
    try:
        if not isinstance(dati,dict) or time.time()-dati.get("timestamp",0)>=3600:
            r = session.get(fonte["url"],timeout=(5,10))
            if r.status_code!=200:
                registra_statistica_fonte(nome,stato=f"HTTP {r.status_code}",eventiEstratti=0)
                return []
            payload=r.json()
            dati={"timestamp":time.time(),"payload":payload}
            os.makedirs(".csf-state",exist_ok=True)
            _scrivi_json_atomico(path,dati)
        payload=dati.get("payload")
        if not isinstance(payload,dict) or not isinstance(payload.get("items"),list):
            registra_statistica_fonte(nome,stato="errore",errore="schema API non riconosciuto",eventiEstratti=0)
            return []
        righe=payload["items"]
        registro=registro_locali_movida()
        eventi=[]
        scarti=Counter()
        dettagli=[]
        for ev in righe[:50]:
            record,motivo=analizza_evento_atlas(ev,registro)
            if record:
                eventi.append(record)
            else:
                scarti[motivo]+=1
                if isinstance(ev,dict):
                    dettagli.append({"titolo":str(ev.get("title") or "")[:120],"comune":str(ev.get("city") or "")[:70],"sede":str(ev.get("venue") or "")[:150],"indirizzo":str(ev.get("venueAddress") or "")[:200],"tipoSede":type(ev.get("venue")).__name__,"tipoIndirizzo":type(ev.get("venueAddress")).__name__,"data":str(ev.get("startsAt") or "")[:50],"url":str(ev.get("webUrl") or "")[:250],"stato":str(ev.get("cancelState"))[:40],"motivo":motivo})
        registra_statistica_fonte(nome,stato="ok",linkCandidati=len(righe),pagineScaricate=1,eventiEstratti=len(eventi),scartiMovida=dict(scarti),candidatiDaVerificare=dettagli[:20],paginaSuccessiva=bool(payload.get("nextCursor")))
        print(f"{nome}: {len(righe)} candidati API, {len(eventi)} eventi validati; scarti {dict(scarti)}")
        return eventi
    except Exception as exc:
        registra_statistica_fonte(nome,stato="errore",errore=str(exc)[:120],eventiEstratti=0)
        return []


def calendario_ha_link_movida(html_text, url, dominio, tipo):
    soup = BeautifulSoup(html_text,"html.parser")
    pattern = r"^/eventi/[^/]+/?$" if tipo == "nightz" else r"^/(?:it/)?event/[^/]+/?$"
    return any(_host_appartiene(urljoin(url,a["href"]),dominio) and re.fullmatch(pattern,urlparse(urljoin(url,a["href"])).path,re.I) for a in soup.find_all("a",href=True))


def render_calendario_pubblico(session, url, html_text, dominio, tipo):
    """Fallback browser normale per calendari con contenuti JS.
    Non usa login, proxy, stealth, CAPTCHA o accessi a endpoint privati.
    Rispetta robots.txt e non riprova pagine che mostrano un blocco esplicito."""
    from urllib.robotparser import RobotFileParser
    if not _host_appartiene(url,dominio):
        return "", "dominio non ammesso"
    title = BeautifulSoup(html_text,"html.parser").title
    if title and re.search(r"just a moment|access denied|attention required|captcha|verify you are human", title.get_text(" ",strip=True),re.I):
        return "", "blocco esplicito"
    pr = urlparse(url)
    try:
        robots = session.get(f"{pr.scheme}://{pr.netloc}/robots.txt",timeout=(3,5),allow_redirects=False)
        if robots.status_code == 200:
            rp = RobotFileParser()
            rp.parse(robots.text.splitlines())
            if not rp.can_fetch("*",url):
                return "", "robots.txt non consente la pagina"
        elif robots.status_code not in (404,410):
            return "", f"robots HTTP {robots.status_code}"
    except requests.RequestException:
        return "", "robots.txt non verificabile"
    try:
        from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
        with sync_playwright() as pw:
            browser = pw.chromium.launch(channel="chrome",headless=True)
            try:
                page = browser.new_page()
                page.route("**/*",lambda route: route.abort() if route.request.resource_type in {"image","media","font"} else route.continue_())
                response = page.goto(url,wait_until="domcontentloaded",timeout=12000)
                if not response or response.status != 200 or not _host_appartiene(page.url,dominio):
                    return "", "navigazione non riuscita"
                if re.search(r"just a moment|access denied|attention required|captcha|verify you are human",page.title(),re.I):
                    return "", "blocco esplicito"
                selettore = 'a[href*="/eventi/"]' if tipo=="nightz" else 'a[href*="/event/"]'
                try:
                    page.wait_for_selector(selettore,state="attached",timeout=7000)
                except PlaywrightTimeout:
                    pass
                rendered = page.content()
                return rendered, "ok" if calendario_ha_link_movida(rendered,url,dominio,tipo) else "nessuna scheda dopo rendering"
            finally:
                browser.close()
    except Exception as exc:
        return "", "browser non disponibile: "+type(exc).__name__


def raccogli_da_portale_generico(session, fonte):
    eventi = []
    nome = fonte["nome"]
    url = fonte["url"]
    dominio = fonte["dominio"]
    c_def = fonte.get("citta_default", "")
    curata = fonte.get("curata", True)

    try:
        r = session.get(url, timeout=(6, 10))
        if r.status_code != 200:
            registra_statistica_fonte(
                nome, stato=f"HTTP {r.status_code}", linkCandidati=0,
                pagineScaricate=0, eventiEstratti=0
            )
            print(f"{nome}: HTTP {r.status_code}")
            return []
        r.encoding = r.apparent_encoding or "utf-8"
        html_calendario = r.text
        tipo_browser = "nightz" if fonte.get("nightz") else "ticketsms" if fonte.get("ticketsms") else ""
        if tipo_browser and not calendario_ha_link_movida(html_calendario,url,dominio,tipo_browser):
            # Il budget browser è limitato ai due calendari principali;
            # le altre fonti rimangono leggere, senza aprire decine di browser.
            if fonte.get("browser_pubblico"):
                rendered, esito = render_calendario_pubblico(session,url,html_calendario,dominio,tipo_browser)
                registra_statistica_fonte(nome, renderingBrowser=esito)
                print(f"{nome}: rendering pubblico: {esito}")
                if rendered:
                    html_calendario = rendered
        soup = BeautifulSoup(html_calendario, "html.parser")

        if fonte.get("scheda_diretta"):
            eventi = analizza_pagina_evento(r.text, url, citta_default=c_def, fonte_curata_eventi=curata)
            registra_statistica_fonte(nome, stato="ok", linkCandidati=1, pagineScaricate=1, eventiEstratti=len(eventi))
            return eventi

        # Una pagina elenco non è di per sé un evento: si analizzano solo
        # collegamenti che sembrano schede evento individuali.
        links = []
        visti = {url.rstrip("/").lower()}
        for a in soup.find_all("a", href=True):
            full = urljoin(url, a["href"]).split("#")[0].strip()
            pr = urlparse(full)
            if pr.scheme not in ("http", "https") or not _host_appartiene(full, dominio):
                continue
            p_low = pr.path.lower()
            parametro_scheda = str(fonte.get("parametro_scheda") or "").strip()
            valore_scheda = parse_qs(pr.query).get(parametro_scheda, [""])[0] if parametro_scheda else ""
            chiave = f"{pr.netloc.lower()}{pr.path.rstrip('/').lower()}"
            if valore_scheda:
                chiave += f"?{parametro_scheda}={valore_scheda}&{pr.query}"
            if chiave in visti:
                continue
            if any(x in p_low for x in ("/login", "/signup", "/privacy", "/cookie", "/contatti", "/chi-siamo", "/tag/", "/author/", "/autore/")):
                continue
            if p_low == urlparse(url).path.rstrip("/").lower() and not valore_scheda:
                continue
            if _url_tacco_generica(full):
                continue
            t_link = re.sub(r"\s+", " ", a.get_text(" ", strip=True)).strip()
            if _contiene_anno_passato(f"{pr.path} {t_link}") or REGEX_SCARTO.search(t_link):
                continue
            if fonte.get("notizie_locali") and priorita_candidato_rss(t_link, pr.path.replace("-", " ")) < 0:
                continue

            # Alcune fonti ufficiali hanno percorsi stabili per le schede evento:
            # in quel caso il prefisso configurato è una prova sufficiente.
            prefisso_schede = str(fonte.get("prefisso_schede") or "").lower()
            if fonte.get("nightz"):
                if not re.fullmatch(r"/eventi/[^/]+/?", p_low):
                    continue
            elif fonte.get("ticketsms"):
                if not re.match(r"^/(?:it/)?event/[^/]+/?$", p_low) or not re.search(r"-\d{2}-\d{2}-20\d{2}/?$", p_low):
                    continue
            elif parametro_scheda:
                # Alcuni calendari ufficiali pubblicano le schede come query
                # sulla stessa homepage: ?mec-events=slug.
                if not valore_scheda:
                    continue
            elif prefisso_schede:
                if not p_low.startswith(prefisso_schede):
                    continue
            else:
                # Accetta un titolo con tema evento oppure un URL tipico di scheda
                # evento con identificativo numerico; scarta menu e pagine generiche.
                path_evento_id = bool(re.search(r"/(?:eventi?|events?)/[^/]*\d+\.html?$", p_low))
                titolo_evento = bool(REGEX_TEMA_COERENTE.search(t_link))
                if not (path_evento_id or titolo_evento):
                    continue
            if fonte.get("data_nel_link"):
                data_link = data_scheda_movida(full)
                if not data_link or data_link < oggi_iso() or data_link > (oggi_dt() + timedelta(days=60)).strftime("%Y-%m-%d"):
                    continue
                if not fonte.get("solo_jsonld") and not indizi_movida(t_link + " " + p_low.replace("-", " ")):
                    continue
            if len(p_low.strip("/")) >= 4 or valore_scheda:
                visti.add(chiave)
                links.append(full)

        scaricate = 0
        diagnostica = []
        for link in links[:int(fonte.get("max_schede", 12))]:
            try:
                rp = session.get(link, timeout=(4, 7))
                if rp.status_code != 200:
                    continue
                scaricate += 1
                rp.encoding = rp.apparent_encoding or "utf-8"
                if "evento si è già concluso" in rp.text.lower() or "fa parte del nostro archivio" in rp.text.lower():
                    continue
                if fonte.get("nightz"):
                    estratti = analizza_nightz(rp.text, link)
                elif fonte.get("ticketsms"):
                    estratti = analizza_ticketsms(rp.text, link, c_def, fonte["luogo_atteso"])
                elif fonte.get("xceed"):
                    if registra_stati_negativi(rp.text, link):
                        continue
                    estratti = analizza_xceed(rp.text, link, c_def)
                elif fonte.get("solo_jsonld"):
                    markup = BeautifulSoup(rp.text, "html.parser").find_all("script", type="application/ld+json")
                    estratti = analizza_pagina_evento("".join(str(x) for x in markup), link, citta_default="", fonte_curata_eventi=True)
                else:
                    estratti = analizza_pagina_evento(rp.text, link, citta_default=c_def, fonte_curata_eventi=curata)
                if not estratti and fonte.get("nightlife") and len(diagnostica) < 3:
                    diagnostica.append(diagnostica_scheda_movida(rp.text, link))
                if not estratti and not fonte.get("nightz") and not fonte.get("ticketsms") and not fonte.get("xceed") and not fonte.get("solo_jsonld") and not registra_stati_negativi(rp.text, link):
                    testo_locandina = estrai_testo_locandine(session, rp.text, base_url=link)
                    if testo_locandina:
                        h1 = BeautifulSoup(rp.text, "html.parser").find("h1")
                        titolo_immagine = h1.get_text(" ", strip=True) if h1 else ""
                        if len(titolo_immagine) < 5 or titolo_immagine.casefold() in {"evento", "eventi", "news", "notizie"}:
                            titolo_immagine = re.split(r"\b(?:quando|data|dove|luogo|orario|ore|prezzo|costo)\b", testo_locandina, maxsplit=1, flags=re.I)[0].strip()[:85]
                        html_ocr = "<html><body><h1>" + escape(titolo_immagine) + "</h1><main><p>" + escape(testo_locandina) + "</p></main></body></html>"
                        estratti = analizza_pagina_evento(html_ocr, link, citta_default=c_def, fonte_curata_eventi=curata)
                if fonte.get("data_nel_link"):
                    estratti = [e for e in estratti if e.get("dataInizio") == data_scheda_movida(link)]
                if fonte.get("nightlife"):
                    estratti = [e for e in estratti if evento_movida_documentato(e)]
                if fonte.get("solo_cerignola"):
                    estratti = [e for e in estratti if e.get("citta") == "Cerignola"]
                eventi.extend(estratti)
            except Exception:
                continue

        # Puglia Culture mostra date e sedi anche nelle card della pagina rassegna.
        # Se la singola scheda non espone markup leggibile, usa questi dati visibili
        # come fallback, mantenendo URL e validazione evento per evento.
        if _host_appartiene(url, "pugliaculture.it") and (
            "/rassegna/" in urlparse(url).path.lower()
            or "/circuito/" in urlparse(url).path.lower()
        ):
            eventi_elenco = estrai_eventi_puglia_da_elenco(soup, url, c_def)
            for evento_elenco in eventi_elenco:
                if not any(sono_duplicati(evento_elenco, esistente) for esistente in eventi):
                    eventi.append(evento_elenco)

        registra_statistica_fonte(
            nome, stato="ok", linkCandidati=len(links),
            pagineScaricate=scaricate, eventiEstratti=len(eventi), schedeNonEstratte=diagnostica
        )
        print(f"{nome}: {len(eventi)} eventi estratti (da {scaricate} pagine)")
    except Exception as e:
        registra_statistica_fonte(
            nome, stato="errore", errore=str(e)[:120],
            linkCandidati=0, pagineScaricate=0, eventiEstratti=0
        )
        print(f"Errore {nome}: {str(e)[:75]}")

    return eventi


def _titolo_base_duplicato(titolo):
    """Riduce il titolo alla sua parte identificativa, togliendo città e sottotitoli."""
    testo = _ripara_codifica(str(titolo or "")).casefold().strip()
    if "|" in testo:
        prefisso, resto = testo.split("|", 1)
        if prefisso.strip() in COMUNI_50KM:
            testo = resto.strip()
    testo = re.split(r"\s+[–—-]\s+", testo, maxsplit=1)[0]
    testo = re.split(r"\s*[:.!?]\s*", testo, maxsplit=1)[0]
    testo = re.sub(r"[^a-z0-9à-ù\s]", " ", testo)
    return re.sub(r"\s+", " ", testo).strip()


def sono_duplicati(a, b):
    if str(a.get("citta", "")).casefold() != str(b.get("citta", "")).casefold():
        return False

    # Una stessa manifestazione ricorrente in giorni diversi non è un duplicato.
    # Le date sono già normalizzate in formato ISO YYYY-MM-DD.
    inizio_a = str(a.get("dataInizio") or "")
    fine_a = str(a.get("dataFine") or inizio_a)
    inizio_b = str(b.get("dataInizio") or "")
    fine_b = str(b.get("dataFine") or inizio_b)
    date_valide = all(
        re.fullmatch(r"\d{4}-\d{2}-\d{2}", x)
        for x in (inizio_a, fine_a, inizio_b, fine_b)
    )
    if not date_valide:
        # Se manca una data valida, usa l'URL identico solo come fallback prudenziale.
        return bool(a.get("fonteUrl") and a.get("fonteUrl") == b.get("fonteUrl"))
    if fine_a < inizio_b or fine_b < inizio_a:
        return False

    if capodanno.TEMA.search(str(a.get("titolo") or "")) and capodanno.TEMA.search(str(b.get("titolo") or "")):
        # Due cenoni in sale diverse non sono duplicati, anche con titoli identici.
        sa = re.sub(r"[^\w]+", "", str(a.get("luogo") or "").casefold())
        sb = re.sub(r"[^\w]+", "", str(b.get("luogo") or "").casefold())
        if sa and sb and sa != sb:
            return False
    t1 = re.sub(r"[^a-z0-9\s]", "", str(a.get("titolo", "")).casefold())
    t2 = re.sub(r"[^a-z0-9\s]", "", str(b.get("titolo", "")).casefold())
    if SequenceMatcher(None, t1, t2).ratio() >= 0.68:
        return True

    # Titolo breve contenuto per intero e sede compatibile: unifica solo
    # repliche con le stesse date (es. teatro e aggregatore).
    if inizio_a == inizio_b and fine_a == fine_b:
        def parole_norm(valore):
            return re.findall(r"[a-z0-9à-ù]+", str(valore or "").casefold())
        ta, tb = (" ".join(parole_norm(e.get("titolo"))) for e in (a, b))
        la, lb = (set(parole_norm(e.get("luogo"))) for e in (a, b))
        generiche = {"teatro", "comunale", "piazza", "palazzo", "centro", "parco", "chiesa", "cinema", "ristorante", "cerignola", "foggia", "barletta", "andria", "trani", "manfredonia"}
        comune = {x for x in la & lb if len(x) >= 5 and x not in generiche}
        breve, lungo = sorted((ta, tb), key=len)
        if comune and len(breve) >= 9 and f" {breve} " in f" {lungo} ":
            return True

    # Le fonti ufficiali e gli aggregatori spesso usano sottotitoli diversi
    # per lo stesso spettacolo: confronta anche la parte distintiva iniziale.
    base_a = _titolo_base_duplicato(a.get("titolo"))
    base_b = _titolo_base_duplicato(b.get("titolo"))
    if len(base_a) >= 14 and len(base_a.split()) >= 2 and base_a == base_b:
        return True

    # Alcuni aggregatori mettono il nome degli artisti prima del titolo,
    # mentre la fonte ufficiale fa il contrario: confronta i token distintivi.
    parole_a = set(re.findall(r"\b[a-z0-9à-ù]{4,}\b", base_a))
    parole_b = set(re.findall(r"\b[a-z0-9à-ù]{4,}\b", base_b))
    comuni = parole_a & parole_b
    if not parole_a or not parole_b or len(comuni) < 2:
        return False
    copertura_breve = len(comuni) / min(len(parole_a), len(parole_b))
    copertura_lunga = len(comuni) / max(len(parole_a), len(parole_b))
    return copertura_breve >= 0.75 and copertura_lunga >= 0.30


def _fonte_appartiene_a_raccolta_automatica(url):
    """Confronta l'host reale, evitando falsi match su URL che contengono un dominio nel path."""
    return any(_host_appartiene(url, dominio) for dominio in DOMINI_AUTO)


def carica_esistenti_protetti(percorso_json="eventi.json"):
    """Protegge i manuali JSON e riconvalida solo gli eventi raccolti automaticamente.

    Gli eventi approvati dal pannello admin vivono nel nodo Firebase 'eventiManuali':
    questo processo non legge, modifica o cancella Firebase.
    """
    oggi = oggi_iso()
    manuali = []
    auto_validi = []
    scaduti_rimossi = 0

    if not os.path.exists(percorso_json):
        return manuali, auto_validi, scaduti_rimossi

    try:
        with open(percorso_json, "r", encoding="utf-8") as f:
            dati = json.load(f)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        # Fail closed: non rigenerare mai l'archivio da zero se quello esistente
        # è corrotto o illeggibile.
        raise RuntimeError(f"Archivio eventi esistente non leggibile: {percorso_json}") from exc

    if not isinstance(dati, list):
        raise RuntimeError(f"Formato archivio eventi non valido: {percorso_json} non contiene una lista")

    for item in dati:
        if not isinstance(item, dict):
            raise RuntimeError(f"Record non valido nell'archivio eventi: {percorso_json}")
        if item.get("tipoContenuto") != "evento":
            # Non cancellare eventuali record di altri tipi: non sono gestiti da questo crawler.
            manuali.append(item)
            continue

        titolo = str(item.get("titolo") or "").strip()
        if len(titolo) < 3:
            # Record incompleto: conserva per revisione invece di cancellarlo in silenzio.
            manuali.append(item)
            continue

        url = str(item.get("fonteUrl") or "").strip()
        is_manuale = bool(item.get("manuale")) or not _fonte_appartiene_a_raccolta_automatica(url)
        # I record manuali sono sempre protetti, anche se la data è passata:
        # la loro rimozione deve essere una scelta editoriale, non del crawler.
        if is_manuale:
            manuali.append(item)
            continue

        d_fin = str(item.get("dataFine") or item.get("dataInizio") or "").strip()[:10]
        ha_data = _data_iso_valida(d_fin)

        if ha_data and d_fin < oggi:
            scaduti_rimossi += 1
            continue

        if ha_data:
            evento_pulito = normalizza_e_valida_evento(
                item, ref_dt=oggi_dt(), fonte_curata_eventi=True
            )
            if evento_pulito:
                auto_validi.append(evento_pulito)
            else:
                print(f"Evento automatico scartato in riconvalida: {titolo[:70]}")
        else:
            print(f"Evento automatico senza data valida scartato in riconvalida: {titolo[:70]}")

    return manuali, auto_validi, scaduti_rimossi


def _scrivi_json_atomico(percorso, dati):
    """Scrive JSON completo su file temporaneo e sostituisce il target solo a scrittura riuscita."""
    temporaneo = f"{percorso}.tmp"
    try:
        with open(temporaneo, "w", encoding="utf-8") as f:
            json.dump(dati, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temporaneo, percorso)
    finally:
        if os.path.exists(temporaneo):
            os.remove(temporaneo)


def raccogli_fonti_parallele(compiti, max_worker=MAX_WORKER_FONTI):
    """Parallelismo limitato fra domini; ogni dominio mantiene richieste sequenziali.

    Ogni gruppo ha una Session HTTP indipendente. I risultati sono restituiti
    nell'ordine originale, non nell'ordine di completamento dei thread.
    """
    gruppi = {}
    for indice, (raccoglitore, fonte) in enumerate(compiti):
        dominio = (fonte.get("dominio") or urlparse(fonte["url"]).hostname or "").lower().removeprefix("www.")
        gruppi.setdefault(dominio, []).append((indice, raccoglitore, fonte))

    def raccogli_gruppo(gruppo):
        risultati = []
        with crea_session_raccolta() as session:
            for indice, raccoglitore, fonte in gruppo:
                nome = fonte["nome"]
                inizio = time.monotonic()
                session._csf_ocr_budget = {"rimanenti": MAX_OCR_PER_FONTE}
                try:
                    eventi = raccoglitore(session, fonte)
                except Exception as exc:
                    eventi = []
                    registra_statistica_fonte(nome, stato="errore", errore=str(exc)[:120], eventiEstratti=0)
                    print(f"{nome}: errore isolato: {str(exc)[:100]}", flush=True)
                registra_statistica_fonte(nome, durataSecondi=round(time.monotonic() - inizio, 2),
                                          tentativiOCR=MAX_OCR_PER_FONTE - session._csf_ocr_budget["rimanenti"])
                print(f"{nome}: completata in {time.monotonic() - inizio:.1f}s", flush=True)
                risultati.append((indice, eventi))
        return risultati

    if not gruppi:
        return []
    risultati = []
    with ThreadPoolExecutor(max_workers=max(1, min(MAX_WORKER_FONTI, max_worker))) as pool:
        for blocco in pool.map(raccogli_gruppo, gruppi.values()):
            risultati.extend(blocco)
    return [evento for _, eventi in sorted(risultati, key=lambda x: x[0]) for evento in eventi]


def evidenze_fonti(eventi, riferimento):
    """Concordanza osservata nel ciclo corrente, non certificazione di veridicità.
    Richiede stesso comune, titolo distintivo, data e sede, oltre a domini diversi.
    Non cambia la fonte primaria né la pubblicazione."""
    def norm(t):
        return " ".join(re.findall(r"[a-z0-9à-ù]+", str(t or "").casefold()))
    def host(e):
        return (urlparse(e.get("fonteUrl") or "").hostname or "").lower().removeprefix("www.")
    gruppi = {}
    for e in eventi:
        k = (norm(e.get("citta")), norm(e.get("titolo")), e.get("dataInizio"), e.get("dataFine"), norm(e.get("luogo")))
        if len(k[1]) >= 12 and k[4] and host(e):
            gruppi.setdefault(k, set()).add(host(e))
    ris = []
    for ev in riferimento:
        k = (norm(ev.get("citta")), norm(ev.get("titolo")), ev.get("dataInizio"), ev.get("dataFine"), norm(ev.get("luogo")))
        fonti = sorted(gruppi.get(k, set()))
        if len(fonti) >= 2:
            ris.append({"titolo":ev.get("titolo"),"citta":ev.get("citta"),"data":ev.get("dataInizio"),"dominiConcordanti":fonti})
    return ris


def evento_sede_riservata(ev):
    """Non pubblicare una localizzazione inventata per l'opening ECHOES.
    La fonte RA indica Secret Location (BT), mentre altre indicano comuni diversi."""
    t = str(ev.get("titolo") or "").casefold()
    return "stefano andriezzi" in t and "opening" in t and ev.get("dataInizio") == "2026-11-28"


def intervallo_editoriale_sostituito(ev):
    """Un programma su date discontinue già pubblicato come singoli appuntamenti.
    Escludi solo la scheda aggregata errata, non le date realmente confermate."""
    return (ev.get("fonteUrl") == "https://www.foggiareporter.it/a-cerignola-si-accende-il-natale-nelle-quattro-vie-dal-21-novembre-al-6-dicembre.html"
            and ev.get("citta") == "Cerignola"
            and ev.get("dataInizio") == "2026-11-21"
            and ev.get("dataFine") == "2026-12-06")


def prossimo_weekend_movida(ev):
    oggi = oggi_dt().date()
    venerdi = oggi + timedelta(days=(4-oggi.weekday())%7)
    if oggi.weekday() in (5,6):
        venerdi = oggi-timedelta(days=oggi.weekday()-4)
    return venerdi.strftime("%Y-%m-%d") <= ev.get("dataInizio","") <= (venerdi+timedelta(days=2)).strftime("%Y-%m-%d")


def esegui_aggiornamento():
    t_start = time.time()
    manuali_admin, precedenti_auto, scaduti_rimossi = carica_esistenti_protetti("eventi.json")
    print(
        f"Eventi JSON caricati: {len(manuali_admin)} record protetti/manuali, "
        f"{len(precedenti_auto)} automatici ancora validi, {scaduti_rimossi} scaduti eliminati. "
        "Gli eventi admin Firebase sono gestiti separatamente e non vengono modificati da questo workflow."
    )

    STATISTICHE_FONTI.clear()
    STATI_EVENTI_NEGATIVI.clear()
    oggi_stagionale=oggi_dt().date()
    dirette_capodanno, rss_capodanno = capodanno.fonti(oggi_stagionale)
    anno_festivita=festivita.stagione(oggi_stagionale)
    if anno_festivita is not None:
        if not dirette_capodanno:
            # Dal 2 al 6 gennaio restano attive le stesse strutture, senza Capodanno.
            dirette_capodanno,_=capodanno.fonti(oggi_stagionale.replace(day=1))
            for fonte in dirette_capodanno:
                fonte.pop("anno_capodanno",None)
        for fonte in dirette_capodanno:
            fonte["anno_festivita"]=anno_festivita
    rss_festivita=festivita.fonti(oggi_stagionale,capodanno.registro())
    dirette_annuali,rss_annuali=ricorrenze.fonti(oggi_stagionale,capodanno.registro())
    if dirette_capodanno and dirette_annuali:
        per_url={f["url"]:f["ricorrenze_annuali"] for f in dirette_annuali}
        for f in dirette_capodanno:
            if f["url"] in per_url:
                f["ricorrenze_annuali"]=per_url[f["url"]]
        dirette_annuali=[f for f in dirette_annuali if f["url"] not in {x["url"] for x in dirette_capodanno}]
    compiti = (
        [(raccogli_capodanno_sito, fonte) for fonte in dirette_capodanno + dirette_annuali]
        + [(raccogli_da_feed_social, fonte) for fonte in rss_capodanno + rss_festivita + rss_annuali]
        + [(raccogli_da_portale_viva, fonte) for fonte in FONTI_VIVA]
        + [(raccogli_da_portale_generico, fonte) for fonte in calendari_registro_cerignola() + FONTI_PORTALI]
        + [(raccogli_da_feed_social, fonte) for fonte in fonti_registro_cerignola() + FONTI_SOCIAL_RSS]
        + [(esplora_lineup_atlas, {"nome":"Lineup Atlas API Barletta","url":"https://lineupatlas.com/api/v1/events?city=barletta&country=IT&kind=PARTY&limit=30","dominio":"lineupatlas.com","cache":"bat"}), (esplora_lineup_atlas, {"nome":"Lineup Atlas API raggio costiero","url":"https://lineupatlas.com/api/v1/events?city=barletta&country=IT&kind=PARTY&rayon=50&limit=50","dominio":"lineupatlas.com","cache":"raggio-bat"})]
    )
    percorso_stato = os.path.join(".csf-state", "fonti.json")
    memoria = stato_raccolta.carica(percorso_stato)
    now = int(time.time())
    compiti, pause = stato_raccolta.pianifica(compiti, memoria, now, os.environ.get("CSF_FORZA_FONTI") == "1")
    for nome in pause:
        registra_statistica_fonte(nome, stato="pausa", eventiEstratti=0)
    for _, fonte in compiti:
        registra_statistica_fonte(fonte["nome"], prioritaria=bool(fonte.get("prioritaria") or fonte.get("citta_default")=="Cerignola" or fonte.get("solo_cerignola")))
    print(f"Raccolta parallela: {len(compiti)} fonti, {len(pause)} in pausa per blocchi ripetuti", flush=True)
    nuovi_raccolti = raccogli_fonti_parallele(compiti)
    memoria = stato_raccolta.aggiorna(memoria, STATISTICHE_FONTI, now)
    os.makedirs(".csf-state", exist_ok=True)
    _scrivi_json_atomico(percorso_stato, memoria)
    controllo_stato = ricontrolla_eventi_imminenti(precedenti_auto + nuovi_raccolti)
    prima = len(precedenti_auto) + len(nuovi_raccolti)
    precedenti_auto = [e for e in precedenti_auto if not evento_non_attivo(e) and not evento_sede_riservata(e) and not intervallo_editoriale_sostituito(e)]
    nuovi_raccolti = [e for e in nuovi_raccolti if not evento_non_attivo(e) and not evento_sede_riservata(e) and not intervallo_editoriale_sostituito(e)]
    esclusi_stato = prima - len(precedenti_auto) - len(nuovi_raccolti)

    nuovi_unici = []
    # Biglietteria diretta prima dell’aggregatore, anche quando la fonte primaria è già in archivio.
    nuovi_raccolti.sort(key=lambda e: (_host_appartiene(e.get("fonteUrl"), "lineupatlas.com"), not bool(e.get("locandinaUrl"))))
    for ev in nuovi_raccolti:
        if _host_appartiene(ev.get("fonteUrl"), "lineupatlas.com") and any(sono_duplicati(x,ev) and not _host_appartiene(x.get("fonteUrl"),"lineupatlas.com") for x in precedenti_auto):
            continue
        if not any(sono_duplicati(x, ev) for x in nuovi_unici):
            nuovi_unici.append(ev)

    consolidati = list(manuali_admin)
    aggiunti_nuovi = 0
    ritrovati = 0
    for ev in nuovi_unici:
        if not any(sono_duplicati(x, ev) for x in consolidati):
            consolidati.append(ev)
            if any(sono_duplicati(x, ev) for x in precedenti_auto):
                ritrovati += 1
            else:
                aggiunti_nuovi += 1

    for ev_old in precedenti_auto:
        if not any(sono_duplicati(x, ev_old) for x in consolidati):
            consolidati.append(ev_old)

    lista_finale = sorted(
        consolidati,
        key=lambda x: (
            x.get("dataInizio", "9999-12-31"),
            priorita_km(x.get("citta", "")),
            x.get("titolo", "").lower(),
        ),
    )

    # Verifica finale prima di toccare il file pubblicato.
    if not isinstance(lista_finale, list) or any(not isinstance(e, dict) for e in lista_finale):
        raise RuntimeError("Controllo integrità fallito: archivio eventi non valido")
    _scrivi_json_atomico("eventi.json", lista_finale)

    eventi_per_fonte = Counter(
        (urlparse(str(e.get("fonteUrl") or "")).hostname or "fonte non specificata").lower()
        for e in lista_finale
    )
    concordanze = evidenze_fonti(nuovi_raccolti, lista_finale)
    report = {
        "concordanzeFonti": concordanze,
        "eventiConcordanti": len(concordanze),
        "aggiornatoAl": oggi_dt().strftime("%Y-%m-%d %H:%M:%S %Z"),
        "fusoOrario": "Europe/Rome",
        "totaleContenuti": len(lista_finale),
        "controlloStato": controllo_stato,
        "saluteFonti": stato_raccolta.riepilogo(memoria, pause),
        "recordEsclusiPerStato": esclusi_stato,
        "eventiCerignolaProssimi7Giorni": sum(1 for e in lista_finale if e.get("citta") == "Cerignola" and oggi_iso() <= e.get("dataInizio", "") <= (oggi_dt() + timedelta(days=7)).strftime("%Y-%m-%d")),
        "movidaPerComune": dict(Counter(e.get("citta") for e in lista_finale if evento_movida_documentato(e))),
        "registroOrganizzatoriCerignola": len(registro_cerignola()),
        "registroCapodanno": len(capodanno.registro()),
        "ricorrenzeAttive": [x["nome"] for x in ricorrenze.attive(oggi_stagionale)],
        "festivitaCerignola": sum(1 for e in lista_finale if e.get("citta")=="Cerignola" and festivita.TEMA.search(e.get("titolo","")) and e.get("dataFine","")>=oggi_iso() and e.get("dataInizio","")<=(oggi_dt()+timedelta(days=45)).strftime("%Y-%m-%d")),
        "capodannoCerignola": sum(1 for e in lista_finale if e.get("citta")=="Cerignola" and capodanno.TEMA.search(e.get("titolo","")) and e.get("dataInizio","").endswith(("12-31","01-01"))),
        "registroLocaliMovida": {c:len(v) for c,v in registro_locali_movida().items()},
        "movidaProssimoWeekend": dict(Counter(e.get("citta") for e in lista_finale if evento_movida_documentato(e) and prossimo_weekend_movida(e))),
        "serateCerignola": sum(1 for e in lista_finale if e.get("citta") == "Cerignola" and e.get("categoria") == "Locali & Serate"),
        "nuoviAggiunti": aggiunti_nuovi,
        "automaticiRitrovati": ritrovati,
        "durataSecondi": round(time.time() - t_start, 2),
        "workerMassimi": MAX_WORKER_FONTI,
        "manualiConservati": len(manuali_admin),
        "automaticiRiconvalidati": len(precedenti_auto),
        "scadutiEliminati": scaduti_rimossi,
        "finestraAnticipoGiorni": GIORNI_ANTICIPO_MAX,
        "eventiPerCategoria": dict(Counter(e.get("categoria", "Non classificato") for e in lista_finale)),
        "eventiPerComune": dict(Counter(e.get("citta", "Non specificato") for e in lista_finale)),
        "eventiPerFonte": dict(eventi_per_fonte),
        "diagnosticaFonti": {
            nome: dict(dati) for nome, dati in STATISTICHE_FONTI.items()
        },
        "fontiConEventi": sum(
            1 for dati in STATISTICHE_FONTI.values()
            if dati.get("eventiEstratti", 0) > 0
        ),
        "fontiSenzaEventi": [
            nome for nome, dati in STATISTICHE_FONTI.items()
            if dati.get("eventiEstratti", 0) == 0
        ],
    }
    _scrivi_json_atomico("report_copertura.json", report)

    print(
        f"Fine: {len(lista_finale)} eventi totali salvati "
        f"({aggiunti_nuovi} realmente nuovi, {ritrovati} ritrovati, {len(manuali_admin)} manuali, "
        f"{len(precedenti_auto)} automatici riconvalidati, {scaduti_rimossi} scaduti rimossi) "
        f"in {int(time.time() - t_start)}s"
    )




if __name__ == "__main__":
    esegui_aggiornamento()
