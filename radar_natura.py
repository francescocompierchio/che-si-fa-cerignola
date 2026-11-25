"""Radar naturalistico: fonti pubbliche e selezione tematica, senza date presunte."""
import re
from urllib.parse import urlencode,urlparse

TEMA=re.compile(r"\b(?:escursion\w*|trekking|birdwatching|cicloturismo|e-bike|passeggiat[ae]|camminat[ae]|sentier[oi]|river trekking|visita guidata)\b",re.I)
AMBIENTE=re.compile(r"\b(?:natura\w*|parco|bosco|boschi|foresta|oasi|lag[oi]|salin[ae]|ofanto|vulture|murgia|monticchio|siponto|riserva|fiume|campagna|fauna|birdwatching|trekking|escursion\w*|cicloturismo|e-bike|sentier[oi])\b",re.I)
SCARTO=re.compile(r"\b(?:gara podistica|trail running|maratona|convegno|seminario|annullat[oa]|rinviat[oa]|si è svolto)\b",re.I)
def pertinente(testo):
    return bool(TEMA.search(testo) and AMBIENTE.search(testo) and not SCARTO.search(testo))

def evento_documentato(ev):
    titolo=ev.get("titolo","")
    testo=titolo+" "+ev.get("descrizione","")
    # La locandina/scheda deve avere già superato la validazione generale.
    return bool(ev.get("dataInizio") and ev.get("dataFine") and ev.get("fonteUrl") and pertinente(testo)
                and not SCARTO.search(titolo) and (TEMA.search(titolo) or ev.get("categoria")=="Natura & Escursioni"))

DIRETTE=[
    ("VisitMonticchio esperienze","https://www.visitmonticchio.it/esperienze/calendario-esperienze-2/"),
    ("CAI Foggia","https://www.caifoggia.it/"),
    ("Parco Fiume Ofanto","https://www.parcoofanto.it/"),
    ("Daunia TuR","https://www.dauniatur.it/"),
    ("CSV Foggia","https://www.csvfoggia.it/"),
    ("Oasi Lago Salso","https://www.oasilagosalso.it/"),
    ("Visit Margherita trekking","https://coopcommargherita.wixsite.com/ilmiosito/visite-guidate"),
    ("Parco Alta Murgia","https://www.parcoaltamurgia.it/"),
    ("PugliArte archeotrekking","https://www.pugliarte.it/archeo-trekking/"),
]
GRUPPI=[
    ("Cerignola Ofanto",'(Cerignola OR "Lago Capacciotti" OR "Ripa Alta" OR "Valle dell’Ofanto")',True),
    ("Reali Siti e Canosa",'("Orta Nova" OR Stornara OR Stornarella OR Ordona OR Carapelle OR Canosa OR Trinitapoli)',False),
    ("Oasi e Saline",'("Margherita di Savoia" OR Zapponeta OR "Lago Salso" OR Siponto OR Manfredonia)',False),
    ("Bosco Incoronata Foggia",'(Foggia OR "Bosco Incoronata" OR Castelluccio)',False),
    ("Vulture e Monticchio",'(Monticchio OR Melfi OR Rionero OR Rapolla OR Barile OR Lavello OR Venosa)',False),
    ("Monti Dauni",'(Bovino OR Candela OR Deliceto OR Ascoli OR Troia OR Rocchetta)',False),
    ("Alta Murgia BAT",'(Minervino OR Spinazzola OR Andria OR Barletta OR Trani OR Canosa)',False),
    ("Social pubblici territorio",'(Cerignola OR Canosa OR Foggia OR Manfredonia OR Monticchio OR "Margherita di Savoia") (site:instagram.com OR site:facebook.com)',False),
]
def fonti():
    dirette=[{"nome":"Natura - "+n,"url":u,"dominio":urlparse(u).hostname,"curata":False,"max_schede":6,"natura":True,
              "prioritaria":n=="Parco Fiume Ofanto"} for n,u in DIRETTE]
    tema='(escursione OR trekking OR birdwatching OR cicloturismo OR "passeggiata naturalistica" OR "camminata guidata" OR "visita naturalistica")'
    rss=[{"nome":"Radar Natura - "+n,"url":"https://news.google.com/rss/search?"+urlencode({"q":area+" "+tema+" when:45d","hl":"it","gl":"IT","ceid":"IT:it"}),"natura":True,"prioritaria":locale,"max_schede_rss":4} for n,area,locale in GRUPPI]
    return dirette,rss
