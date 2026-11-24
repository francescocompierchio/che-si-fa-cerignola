import os
import re
import json
import time
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from collections import Counter
from difflib import SequenceMatcher
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
from html import unescape
from zoneinfo import ZoneInfo

GIORNI_ANTICIPO_MAX = 180

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "it-IT,it;q=0.9"
}

DOMINI_AUTO = (
    "news.google.com", "iltaccodibacco.it", "viaggiareinpuglia.it",
    "pugliaevents.it", "eventiesagre.it", "eventbrite.it",
    "lanotiziaweb.it", "marchiodoc.it", "cerignolaviva.it",
    "canosaviva.it", "barlettaviva.it", "traniviva.it",
    "bisceglieviva.it", "andriaviva.it", "statoquotidiano.it",
    "immediato.net", "vulturenews.net", "foggia.today", "lagazzettadelmezzogiorno.it",
    "teatromercadantecerignola.it", "teatrogiordano.it",
    "palazzodelleartibeltrani.it", "politeamaitalia.com",
    "happyticket.com", "pugliaculture.it", "ciaotickets.com", "virgilio.it",
    "buzzeventmap.com", "paesionline.it", "2d2web.com",
    "aivents.it", "experience-app.com", "comune.cerignola.fg.it"
)

FONTI_VIVA = [
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
    {"nome": "Puglia Culture Cerignola", "url": "https://www.pugliaculture.it/rassegna/cerignola-stagione-teatrale-2026-27-un-teatro-per-tutti/", "dominio": "pugliaculture.it", "citta_default": "Cerignola", "curata": True, "prefisso_schede": "/evento/", "max_schede": 20},
    {"nome": "Comune Cerignola Homepage Eventi", "url": "https://comune.cerignola.fg.it/", "dominio": "comune.cerignola.fg.it", "citta_default": "Cerignola", "curata": True, "prefisso_schede": "/vivere-il-comune/eventi/", "max_schede": 20},
    {"nome": "Comune di Cerignola Eventi", "url": "https://comune.cerignola.fg.it/vivere-il-comune/eventi/", "dominio": "comune.cerignola.fg.it", "citta_default": "Cerignola", "curata": True, "prefisso_schede": "/vivere-il-comune/eventi/", "max_schede": 20},
    {"nome": "Teatro Mercadante Cerignola", "url": "https://www.teatromercadantecerignola.it/", "dominio": "teatromercadantecerignola.it", "citta_default": "Cerignola", "curata": True, "prefisso_schede": "/evento/", "max_schede": 20},
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
    r"mercatin[oi]\s+(?:di\s+natale|nataliz\w*|enogastronomic\w*|artigianal\w*)|"
    r"luminari[ae]|accensione\s+(?:delle\s+)?luminari[ae]|accensione\s+(?:dell['’]\s*)?albero|"
    r"villaggi[o]?\s+(?:di\s+natale|natalizi[o]?|di\s+babbo\s+natale)|"
    r"casa\s+di\s+babbo\s+natale|pist[ae]\s+di\s+(?:pattinaggio|ghiaccio)|presepe\s+vivente|"
    r"concert[oi]|concerts?|symphonic\s+concert|concerto\s+sinfonico|orchestra\s+sinfonica|musica\s+classica|recital\s+pianistic[o]?|musica\s+da\s+camera|opera\s+lirica|pianoforte|"
    r"spettacolo\s+teatrale|commedia\s+teatrale|teatro\s+ragazzi|prosa|musica\s+(?:dal\s+vivo|live)|live\s+music|tribute\s+band|cover\s+band|"
    r"dj\s*set|discotec[ah]|club\s+night|party|aperitiv[oi]\s+musical\w*|karaoke|"
    r"serat[ae]\s+(?:live|musical\w*|in\s+piazza|al\s+pub|nel\s+locale|danza|latina|disco|con)|"
    r"cabaret|festa\s+(?:in\s+piazza|di\s+piazza|patronale|di\s+paese|della\s+birra)|"
    r"sagr[ae]|street\s+food|degustazion[ei]|festa\s+gastronomic[ah]|percorso\s+enogastronomic[o]|caldarroste|prodotti\s+tipici|"
    r"laboratori[o]?\s+(?:per\s+bambini|creativ[oi])|animazione\s+per\s+bambini|"
    r"spettacol[oi]\s+(?:per\s+famiglie|di\s+intrattenimento)|festa\s+per\s+bambini|notte\s+bianca\s+dei\s+bambini|"
    r"fattori[ae]\s+didattic[ah]|parco\s+tematico|"
    r"trekking|escursion[ei]|passeggiat[ae]\s+(?:naturalistic[ah]|guidat[ah])|"
    r"uscit[ae]\s+organizzat[ah]|visita\s+guidata|visita\s+alle\s+saline|riserva\s+naturale|attivit[aà]\s+all['’]aperto|"
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


def registra_statistica_fonte(nome, **dati):
    """Conserva metriche per fonte per rendere verificabile ogni ciclo di raccolta."""
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
        "puglia",
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
    if citta and not re.search(rf"\b{re.escape(citta)}\b", indirizzo, re.I):
        indirizzo = f"{indirizzo}, {citta}".strip(" ,")
    return indirizzo


def classifica_categoria(testo):
    t = (testo or "").lower()
    # Le gare di corsa e gli eventi fitness rientrano nelle attività diurne.
    if any(k in t for k in ("corricerignola", "gara podistica", "maratona", "mezza maratona", "corsa podistica", "corsa su strada", "corsa campestre", "trail running", "urban trail", "spartan race", "hyrox")):
        return "Attività diurne"
    if any(k in t for k in ("luminari", "mercatini di natale", "mercatino di natale", "mercatini nataliz", "villaggio di natale", "villaggio nataliz", "villaggio di babbo natale", "casa di babbo natale", "pista di pattinaggio", "pista di ghiaccio", "presepe vivente", "laboratori per bambini", "laboratorio per bambini", "laboratori creativi", "animazione per bambini", "spettacolo per famiglie", "festa per bambini", "notte bianca dei bambini", "fattoria didattica", "fattorie didattiche", "parco tematico")):
        return "Famiglie & Bambini"
    if any(k in t for k in ("escursion", "trekking", "passeggiat", "camminat", "visita guidata", "visita alle saline", "riserva naturale", "saline", "monticchio", "murgia", "incoronata", "avventur")):
        return "Natura & Escursioni"
    if any(k in t for k in ("sagra", "sagre", "sfogliatella", "street food", "degustazion", "enogastronom", "festa gastronomica", "caldarroste", "prodotti tipici")):
        return "Sagre & Food"
    # Distingue la prosa e il teatro dalla musica, senza farsi ingannare
    # dalla sola presenza del nome del Teatro come luogo dell'evento.
    if any(k in t for k in (
        "spettacolo teatrale", "teatro ragazzi", "teatro inclusivo",
        "teatro & spettacoli", "commedia teatrale", "prosa", "cabaret",
    )):
        return "Teatro & Spettacoli"
    # Le serate in locali e i format sociali hanno priorità sui generici riferimenti musicali.
    if any(k in t for k in ("dj set", "dj-set", "club night", "discotec", "party", "serata al pub", "serata nel locale", "serata disco", "serata latina", "aperitivo musicale", "aperitivi musicali", "karaoke", "notte bianca")):
        return "Locali & Serate"
    # Riconosce anche esibizioni descritte senza la parola "concerto" nel titolo.
    if any(k in t for k in (
        "concerto", "concerti", "concert", "concerts", "symphonic concert", "in concerto",
        "concerto sinfonico", "orchestra sinfonica", "musica classica", "recital pianistico",
        "pianoforte", "musica da camera", "opera lirica",
        "vivaldi", "orchestra", "musica dal vivo", "musica live",
        "live music", "live", "tribute", "tributo", "tribute band", "cover band",
        "band", "jam", "quartet", "quatuor", "trio", "duo", "vocal harmony",
        "sassofono", "saxophone", "chitarra", "guitar", "cantautore", "cantante",
        "musicista", "soul", "r&b", "hendrix", "califano", "cabaret",
        "festa in piazza", "festa di piazza", "festa patronale", "festa di paese",
        "festa della birra"
    )):
        return "Musica & Concerti"
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
    if citta.lower() == "cerignola" and re.search(
        r"\bteatro\s+comunale\s+saverio\s+mercadante\b",
        testo_pag,
        re.I,
    ):
        return "Teatro Comunale Saverio Mercadante"

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

    luogo = normalizza_nome_luogo(luogo, citta)
    if not _luogo_utilizzabile(luogo) or luogo.lower() == citta.lower():
        luogo = estrai_luogo_documentato(f"{titolo}\n{descrizione}", citta)
    luogo = normalizza_nome_luogo(luogo, citta)
    if not _luogo_utilizzabile(luogo):
        return None

    # Ricalcola la categoria sul contenuto. Mantiene però la classe specifica
    # assegnata dalla scheda quando la fonte documenta esplicitamente il teatro.
    cat = classifica_categoria(f"{titolo} {descrizione}")
    if str(raw.get("categoria") or "").strip() == "Teatro & Spettacoli":
        cat = "Teatro & Spettacoli"

    if not d_txt:
        d_txt = formatta_data_italiano(d1, d2)

    costo = str(raw.get("costo") or "").strip() or "Non specificato nella fonte"
    desc_finale = rimuovi_riferimenti_pubblicazione(descrizione) if descrizione else ""
    if len(desc_finale) < 15:
        desc_finale = (
            f"{titolo} presso {luogo} ({citta}). "
            "Verifica orari e modalità di accesso nella fonte dell'organizzatore."
        )

    return {
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

    for ev_ld in eventi_ld[:20]:
        stato = str(ev_ld.get("eventStatus") or "").lower()
        if "eventcancelled" in stato or "eventpostponed" in stato:
            continue
        titolo = re.sub(r"\s+", " ", str(ev_ld.get("name") or "")).strip()
        d1 = str(ev_ld.get("startDate") or "").strip()[:10]
        d2 = str(ev_ld.get("endDate") or d1).strip()[:10]
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
            "dataTesto": formatta_data_italiano(d1, d2) if _data_iso_valida(d1) else "",
            "luogo": luogo_nome,
            "indirizzoMappa": indirizzo_completo,
            "costo": estrai_costo_jsonld(ev_ld, soup),
            "descrizione": desc,
            "fonteUrl": url_evento
        }, ref, fonte_curata_eventi=fonte_curata_eventi)
        if ev_ok:
            risultati.append(ev_ok)

    if risultati:
        return risultati

    h1 = soup.find("h1")
    titolo = re.sub(r"\s+", " ", h1.get_text(" ", strip=True)) if h1 else ""
    if not titolo:
        og_t = soup.find("meta", property="og:title")
        titolo = re.sub(r"\s+", " ", og_t.get("content", "")).strip() if og_t else ""
    if len(titolo) < 5:
        return []

    for tag in soup(["script", "style", "nav", "footer", "aside", "form", "noscript", "iframe", "time"]):
        tag.decompose()
    for meta_el in soup.select(".byline, .author, .meta, .post-meta, .entry-meta, .article-meta, [class*='publish'], [class*='update'], [class*='autore'], [class*='redazione']"):
        meta_el.decompose()

    cont = soup.find("main") or soup.find("article") or soup.body or soup
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
    if not d1:
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

    ev_ok = normalizza_e_valida_evento({
        "citta": citta,
        "categoria": classifica_categoria(testo_completo),
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
    }, ref, fonte_curata_eventi=fonte_curata_eventi)
    return [ev_ok] if ev_ok else []


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
        soup = BeautifulSoup(r.text, "html.parser")

        # Una pagina elenco non è di per sé un evento: si analizzano solo
        # collegamenti che sembrano schede evento individuali.
        links = []
        visti = {url.rstrip("/").lower()}
        for a in soup.find_all("a", href=True):
            full = urljoin(url, a["href"]).split("#")[0].strip()
            pr = urlparse(full)
            if pr.scheme not in ("http", "https") or not _host_appartiene(full, dominio):
                continue
            chiave = f"{pr.netloc.lower()}{pr.path.rstrip('/').lower()}"
            if chiave in visti:
                continue
            p_low = pr.path.lower()
            if any(x in p_low for x in ("/login", "/signup", "/privacy", "/cookie", "/contatti", "/chi-siamo", "/tag/", "/author/", "/autore/")):
                continue
            if p_low == urlparse(url).path.rstrip("/").lower():
                continue
            if _url_tacco_generica(full):
                continue
            t_link = re.sub(r"\s+", " ", a.get_text(" ", strip=True)).strip()
            if _contiene_anno_passato(f"{pr.path} {t_link}") or REGEX_SCARTO.search(t_link):
                continue

            # Alcune fonti ufficiali hanno percorsi stabili per le schede evento:
            # in quel caso il prefisso configurato è una prova sufficiente.
            prefisso_schede = str(fonte.get("prefisso_schede") or "").lower()
            if prefisso_schede:
                if not p_low.startswith(prefisso_schede):
                    continue
            else:
                # Accetta un titolo con tema evento oppure un URL tipico di scheda
                # evento con identificativo numerico; scarta menu e pagine generiche.
                path_evento_id = bool(re.search(r"/(?:eventi?|events?)/[^/]*\d+\.html?$", p_low))
                titolo_evento = bool(REGEX_TEMA_COERENTE.search(t_link))
                if not (path_evento_id or titolo_evento):
                    continue
            if len(p_low.strip("/")) >= 4:
                visti.add(chiave)
                links.append(full)

        scaricate = 0
        for link in links[:int(fonte.get("max_schede", 12))]:
            try:
                rp = session.get(link, timeout=(4, 7))
                if rp.status_code != 200:
                    continue
                scaricate += 1
                rp.encoding = rp.apparent_encoding or "utf-8"
                if "evento si è già concluso" in rp.text.lower() or "fa parte del nostro archivio" in rp.text.lower():
                    continue
                eventi.extend(analizza_pagina_evento(rp.text, link, citta_default=c_def, fonte_curata_eventi=curata))
            except Exception:
                continue

        registra_statistica_fonte(
            nome, stato="ok", linkCandidati=len(links),
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

    t1 = re.sub(r"[^a-z0-9\s]", "", str(a.get("titolo", "")).casefold())
    t2 = re.sub(r"[^a-z0-9\s]", "", str(b.get("titolo", "")).casefold())
    if SequenceMatcher(None, t1, t2).ratio() >= 0.68:
        return True

    # Le fonti ufficiali e gli aggregatori spesso usano sottotitoli diversi
    # per lo stesso spettacolo: confronta anche la parte distintiva iniziale.
    base_a = _titolo_base_duplicato(a.get("titolo"))
    base_b = _titolo_base_duplicato(b.get("titolo"))
    return len(base_a) >= 14 and len(base_a.split()) >= 2 and base_a == base_b


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


def esegui_aggiornamento():
    t_start = time.time()
    manuali_admin, precedenti_auto, scaduti_rimossi = carica_esistenti_protetti("eventi.json")
    print(
        f"Eventi JSON caricati: {len(manuali_admin)} record protetti/manuali, "
        f"{len(precedenti_auto)} automatici ancora validi, {scaduti_rimossi} scaduti eliminati. "
        "Gli eventi admin Firebase sono gestiti separatamente e non vengono modificati da questo workflow."
    )

    STATISTICHE_FONTI.clear()
    session = crea_session_raccolta()

    nuovi_raccolti = []
    for fonte in FONTI_VIVA:
        nuovi_raccolti.extend(raccogli_da_portale_viva(session, fonte))
    for fonte in FONTI_PORTALI:
        nuovi_raccolti.extend(raccogli_da_portale_generico(session, fonte))

    nuovi_unici = []
    for ev in nuovi_raccolti:
        if not any(sono_duplicati(x, ev) for x in nuovi_unici):
            nuovi_unici.append(ev)

    consolidati = list(manuali_admin)
    aggiunti_nuovi = 0
    for ev in nuovi_unici:
        if not any(sono_duplicati(x, ev) for x in consolidati):
            consolidati.append(ev)
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
    report = {
        "aggiornatoAl": oggi_dt().strftime("%Y-%m-%d %H:%M:%S %Z"),
        "fusoOrario": "Europe/Rome",
        "totaleContenuti": len(lista_finale),
        "nuoviAggiunti": aggiunti_nuovi,
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
        f"({aggiunti_nuovi} nuovi, {len(manuali_admin)} manuali, "
        f"{len(precedenti_auto)} automatici riconvalidati, {scaduti_rimossi} scaduti rimossi) "
        f"in {int(time.time() - t_start)}s"
    )




if __name__ == "__main__":
    esegui_aggiornamento()
