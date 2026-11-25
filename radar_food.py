"""Radar Sagre & Food: cerca annunci, non inventa date ricorrenti."""
import re
from urllib.parse import urlencode,urlparse

TEMA=re.compile(r"\b(?:sagr[ae]|street[\s-]+food|degustazion[ei]|enogastronom\w*|cantine aperte|frantoi aperti|olio novello|vino novello|cena (?:a tema|evento|di beneficenza|degustazione)|pranzo (?:a tema|di natale|di capodanno)|cenon[ei]|show cooking|festa (?:del gusto|dei sapori|dell['’]olio|del vino|gastronomica)|festival (?:del gusto|gastronomico|del cibo)|menu degustazione|menù degustazione)\b",re.I)
SCARTO=re.compile(r"\b(?:convegno|seminario|corso professionale|annullat[oa]|rinviat[oa]|si è svolto|si è concluso)\b",re.I)
def pertinente(testo):
    return bool(TEMA.search(testo) and not SCARTO.search(testo))
def evento_documentato(ev):
    titolo=ev.get("titolo","")
    return bool(ev.get("dataInizio") and ev.get("dataFine") and ev.get("fonteUrl")
                and pertinente(titolo+" "+ev.get("descrizione",""))
                and not SCARTO.search(titolo)
                and (TEMA.search(titolo) or ev.get("categoria")=="Sagre & Food"))

DIRETTE=[
    ("Pro Loco Canosa – notizie locali","https://www.canosaviva.it/notizie/"),
    ("Comune Trinitapoli – eventi","https://www.comune.trinitapoli.bt.it/Vivere-il-comune/Eventi"),
    ("Sagra del Carciofo – organizzatore","https://www.sagradelcarciofotrinitapoli.it/"),
    ("Eventi Vicino – sagre Puglia","https://www.eventivicino.it/sagre/puglia"),
    ("Il Borghista – sagre Canosa","https://www.ilborghista.it/sagre/canosa-di-puglia"),
    ("LOVOJO – sagre Foggia","https://lovojo.it/sagre/puglia/foggia/"),
    ("Buzz Event Map – sagre BAT","https://buzzeventmap.com/eventi/barletta-andria-trani/sagre"),
    ("Cantine Paradiso – Cerignola","https://www.cantineparadiso.it/"),
    ("Antica Enotria – Cerignola","https://anticaenotria.it/"),
    ("Manfredonia Eventi","https://www.manfredoniaeventi.com/"),
]
GRUPPI=[
    ("Cerignola sagre e Pro Loco","Cerignola",True),
    ("Cerignola cene e ristoranti","Cerignola (ristorante OR trattoria OR pizzeria OR agriturismo OR masseria)",True),
    ("Cerignola cantine e frantoi","Cerignola (cantina OR frantoio OR olio OR vino OR masseria)",True),
    ("Cerignola social pubblici","Cerignola (site:instagram.com OR site:facebook.com)",True),
    ("Reali Siti e Canosa",'("Orta Nova" OR Stornara OR Stornarella OR Carapelle OR Ordona OR Canosa OR Trinitapoli OR "San Ferdinando di Puglia")',False),
    ("Costa e saline",'("Margherita di Savoia" OR Zapponeta OR Manfredonia OR Barletta OR Trani)',False),
    ("Foggia e Tavoliere",'(Foggia OR Lucera OR Troia OR Castelluccio OR Ascoli)',False),
    ("Monti Dauni",'(Candela OR Deliceto OR Bovino OR Rocchetta OR Ascoli)',False),
    ("Vulture",'(Lavello OR Melfi OR Venosa OR Rionero OR Rapolla OR Barile)',False),
    ("Alta Murgia BAT",'(Minervino OR Spinazzola OR Andria OR Canosa)',False),
]
def fonti():
    dirette=[{"nome":"Food - "+n,"url":u,"dominio":urlparse(u).hostname,"curata":False,"max_schede":5,"food":True,"prioritaria":"Cerignola" in n} for n,u in DIRETTE]
    tema='(sagra OR "street food" OR degustazione OR "cena a tema" OR "cantine aperte" OR "frantoi aperti" OR "olio novello" OR enogastronomia OR "show cooking")'
    rss=[{"nome":"Radar Food - "+n,"url":"https://news.google.com/rss/search?"+urlencode({"q":area+" "+tema+" when:45d","hl":"it","gl":"IT","ceid":"IT:it"}),"food":True,"prioritaria":locale,"solo_cerignola":locale,"max_schede_rss":4} for n,area,locale in GRUPPI]
    return dirette,rss
