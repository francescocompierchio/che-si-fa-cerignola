import io
import sys
import unittest
import warnings
from types import SimpleNamespace
from unittest.mock import Mock, patch

import aggiorna_eventi as crawler


class QualitaEventiTests(unittest.TestCase):
    def test_rassegna_apulia_suona_non_comporta_eventi_ogni_giorno(self):
        rassegna = {"fonteUrl":"https://buzzeventmap.com/event/15ed4d5f-1613-46bb-945a-51449ccf3788",
                    "citta":"Barletta", "dataInizio":"2026-11-08", "dataFine":"2026-11-29"}
        self.assertTrue(crawler.intervallo_editoriale_sostituito(rassegna))
        self.assertFalse(crawler.intervallo_editoriale_sostituito(dict(rassegna, dataInizio="2026-11-29")))

    def test_partenza_locale_non_attribuisce_un_concerto_al_comune(self):
        day = (crawler.oggi_dt() + crawler.timedelta(days=3)).date().isoformat()
        raw = {"dataInizio":day, "dataFine":day, "luogo":"Piazza Catuma",
               "citta":"Andria", "descrizione":"Appuntamento per un concerto di musica pop.",
               "fonteUrl":"https://buzzeventmap.com/event/trasferta-di-prova"}
        self.assertIsNone(crawler.normalizza_e_valida_evento(
            dict(raw, titolo="Bus Concerto Cremonini Bologna – Partenze dalla Puglia"), fonte_curata_eventi=True))
        self.assertIsNotNone(crawler.normalizza_e_valida_evento(
            dict(raw, titolo="Concerto di musica pop in piazza"), fonte_curata_eventi=True))

    def test_agenda_scartati_i_workshop_informativi_e_ammessi_quelli_ricreativi(self):
        day = (crawler.oggi_dt() + crawler.timedelta(days=3)).date().isoformat()
        raw = {"dataInizio":day, "dataFine":day, "luogo":"Biblioteca di Comunità",
               "citta":"Cerignola", "descrizione":"Laboratorio creativo con attività per famiglie.",
               "fonteUrl":"https://comune.cerignola.fg.it/vivere-il-comune/eventi/laboratorio/"}
        self.assertIsNone(crawler.normalizza_e_valida_evento(
            dict(raw, titolo="Workshop: Disinformazione e Fake news"), fonte_curata_eventi=True))
        self.assertIsNotNone(crawler.normalizza_e_valida_evento(
            dict(raw, titolo="Workshop di pittura per famiglie"), fonte_curata_eventi=True))

    def test_calendario_luma_rispetta_il_blocco_robots(self):
        fonte = next(f for f in crawler.FONTI_PORTALI if f["nome"] == "Xceed Luma Club Barletta")
        session = Mock()
        with patch.object(crawler.fonti_editori, "scheda_da_origini_note", return_value=None) as scarica:
            self.assertEqual(crawler.raccogli_da_portale_generico(session, fonte), [])
        scarica.assert_called_once_with(session, fonte["url"], {"xceed.me"})
        session.get.assert_not_called()

    def test_rettifiche_documentate_novembre_2026(self):
        from datetime import datetime
        ref = datetime(2026,11,26,12)
        raw = {"titolo":"Cenerentola 301","citta":"Manfredonia","luogo":"Teatro Comunale Lucio Dalla","dataInizio":"2026-11-22","dataFine":"2027-01-06","fonteUrl":"https://iltaccodibacco.it/puglia/eventi/335513.html"}
        ev = crawler.normalizza_e_valida_evento(raw, ref, True)
        self.assertIsNotNone(ev)
        self.assertEqual((ev["dataInizio"],ev["dataFine"]),("2026-12-06","2026-12-06"))
        self.assertEqual(ev["citta"],"Manfredonia")
        raw = {"titolo":"Menù di Capodanno – Posta Bassi","citta":"Manfredonia","luogo":"Agriturismo Posta Bassi","indirizzoMappa":"Via Manfredonia km 196+200","dataInizio":"2027-01-01","dataFine":"2027-01-01","fonteUrl":"https://www.postabassi.it/eventi-speciali/"}
        a = crawler.normalizza_e_valida_evento(raw, ref, True)
        b = crawler.normalizza_e_valida_evento(dict(raw,citta="Foggia",luogo="Posta Bassi",titolo="Pranzo di Capodanno – Posta Bassi"),ref,True)
        self.assertIsNotNone(a)
        self.assertEqual(a,b)
        self.assertEqual(a["citta"],"Foggia")
        self.assertEqual(a["costo"],"55 € a persona")
        self.assertEqual(crawler.classifica_categoria("Gheghè Christmas Bakery: laboratorio natalizio per bambini | Party con Gheghè"),"Famiglie & Bambini")

    def test_radar_organizzatori_non_alias_sede(self):
        from discovery_locale import fonti_organizzatori_movida
        from urllib.parse import parse_qs, urlparse
        rss=fonti_organizzatori_movida({"Cerignola": [], "Foggia":[{"nome":"Locale","organizzatori":["DBA Events","DBA Events"]}]})
        sources=[s for s in rss if " organizzatori " in s["nome"]]
        cer=next(s for s in sources if s["comune_radar"]=="Cerignola")
        fog=next(s for s in sources if s["comune_radar"]=="Foggia")
        q=parse_qs(urlparse(cer["url"]).query)["q"][0]
        self.assertIn('"Cerignola"',q)
        self.assertIn('"Neverland Cerignola"',q)
        self.assertTrue(any('"Andrea Ordine"' in parse_qs(urlparse(s["url"]).query)["q"][0] for s in sources if s["comune_radar"]=="Cerignola"))
        for nome in ("Cosimo Mancino","New Top Music"):
            self.assertTrue(any('"'+nome+'"' in parse_qs(urlparse(s["url"]).query)["q"][0] for s in sources if s["comune_radar"]=="Cerignola" and s["solo_cerignola"] and not s["alias_movida"]))
        self.assertTrue(cer["solo_cerignola"])
        self.assertEqual(cer["alias_movida"],[])
        qf=parse_qs(urlparse(fog["url"]).query)["q"][0]
        self.assertEqual(qf.count('"DBA Events"'),1)
        self.assertIn('"Foggia"',qf)
        self.assertEqual(fog["alias_movida"],[])

    def test_movida_live_locale_non_teatro(self):
        e={"categoria":"Musica & Concerti","titolo":"Rainbow Bridge live tribute","luogo":"Bohemien Pub","descrizione":"Concerto rock"}
        self.assertTrue(crawler.evento_movida_documentato(e))
        self.assertFalse(crawler.evento_movida_documentato({**e,"luogo":"Teatro Comunale"}))
        self.assertFalse(crawler.evento_movida_documentato({**e,"categoria":"Teatro & Spettacoli"}))

    def test_intervallo_editoriale_sostituito(self):
        e={"fonteUrl":"https://www.foggiareporter.it/a-cerignola-si-accende-il-natale-nelle-quattro-vie-dal-21-novembre-al-6-dicembre.html","citta":"Cerignola","dataInizio":"2026-11-21","dataFine":"2026-12-06"}
        self.assertTrue(crawler.intervallo_editoriale_sostituito(e))
        self.assertFalse(crawler.intervallo_editoriale_sostituito({**e,"dataInizio":"2026-11-29","dataFine":"2026-11-29"}))
        self.assertFalse(crawler.intervallo_editoriale_sostituito({**e,"fonteUrl":"https://example.org"}))

    def test_atlas_citta_data_tipo_attribuzione(self):
        dt=crawler.oggi_dt()+crawler.timedelta(days=3)
        raw={"kind":"PARTY","countryCode":"IT","city":"Barletta","webUrl":"https://lineupatlas.com/fr/soirees/habibi-barletta-abc","startsAt":dt.strftime("%Y-%m-%d")+"T21:00:00Z","cancelState":None,"title":"Habibi DJ set","venue":"Atrio22","venueAddress":"Via Leonardo da Vinci 15, Barletta","genres":["house"],"currency":"EUR","priceFromCents":1500,"timeTbd":False}
        ev,motivo=crawler.analizza_evento_atlas(raw,{})
        self.assertEqual(motivo,"ok")
        self.assertEqual(ev["categoria"],"Locali & Serate")
        self.assertIn("Lineup Atlas",ev["descrizione"])
        self.assertIn("15,00",ev["costo"])
        self.assertEqual(crawler.normalizza_e_valida_evento(ev,fonte_curata_eventi=True)["categoria"],"Locali & Serate")
        for change in ({"city":"Bari"},{"countryCode":"FR"},{"venue":"Secret Location"},{"venueAddress":"Via Roma, Trani"},{"kind":"CONCERT"},{"cancelState":"unknown"},{"startsAt":"2026-11-28"},{"title":"Claudio Baglioni","genres":[],"venue":"Auditorium"}):
            self.assertIsNone(crawler.analizza_evento_atlas(dict(raw,**change),{})[0],change)
        self.assertIsNone(crawler.analizza_evento_atlas(dict(raw,cancelState="CANCELLED"),{})[0])
        self.assertIsNone(crawler.analizza_evento_atlas(dict(raw,startsAt="2026-11-27T21:00:00Z",title="Shake IT with HAIVAI B"),{})[0])
    def test_atlas_registry(self):
        reg=crawler.registro_locali_movida()
        self.assertTrue(any(x["nome"]=="Atrio22" for x in reg["Barletta"]))

    def test_link_calendari_movida(self):
        self.assertTrue(crawler.calendario_ha_link_movida('<a href="/eventi/around-us/">Around Us</a>', "https://nightz.it/eventi/", "nightz.it", "nightz"))
        self.assertFalse(crawler.calendario_ha_link_movida('<a href="/eventi/">Eventi</a>', "https://nightz.it/eventi/", "nightz.it", "nightz"))
        self.assertFalse(crawler.calendario_ha_link_movida('<a href="https://example.org/eventi/around-us/">Around Us</a>', "https://nightz.it/eventi/", "nightz.it", "nightz"))
        with patch.object(crawler, "oggi_iso", return_value="2026-11-27"):
            self.assertTrue(crawler.calendario_ha_link_movida('<a href="/it/event/Golden-28-11-2026">Golden</a>', "https://www.ticketsms.it/location/Idol-Club", "ticketsms.it", "ticketsms"))
    def test_browser_non_aggira_blocchi(self):
        self.assertEqual(crawler.render_calendario_pubblico(None,"https://nightz.it/eventi/","<title>Just a moment...</title>","nightz.it","nightz"),("","blocco esplicito"))

    def test_xceed_jsonld_data_sede_e_categoria(self):
        import json
        dt = crawler.oggi_dt() + crawler.timedelta(days=3)
        url = "https://xceed.me/it/barletta/event/habibi/1234"
        ev = {"@type":"MusicEvent","name":"Habibi DJ set","url":url,"startDate":dt.strftime("%Y-%m-%d")+"T23:00:00+01:00","location":{"name":"Atrio22","address":{"streetAddress":"Via Leonardo da Vinci 15","addressLocality":"Barletta","addressCountry":"IT"}},"description":"Serata in discoteca"}
        def html(e):
            return "<h1>Habibi DJ set</h1><script type='application/ld+json'>"+json.dumps(e)+"</script>"
        trovati = crawler.analizza_xceed(html(ev),url,"Barletta")
        self.assertEqual(len(trovati),1)
        self.assertEqual(trovati[0]["categoria"],"Locali & Serate")
        self.assertEqual(crawler.normalizza_e_valida_evento(trovati[0],fonte_curata_eventi=True)["categoria"],"Locali & Serate")
        self.assertEqual(crawler.analizza_xceed(html(ev),url,"Trani"),[])
        self.assertEqual(crawler.analizza_xceed(html(dict(ev,eventStatus="https://schema.org/EventCancelled")),url,"Barletta"),[])
        self.assertEqual(crawler.analizza_xceed(html(dict(ev,url="https://xceed.me/it/barletta/event/altro/5678")),url,"Barletta"),[])
        self.assertEqual(crawler.analizza_xceed(html(dict(ev,location=dict(ev["location"],name="Secret Location"))),url,"Barletta"),[])
        mese = next(k for k,v in crawler.MESI_IT.items() if v == dt.month)
        self.assertEqual(crawler.analizza_xceed(html(dict(ev,description=f"{dt.day} {mese} {dt.year-1}")),url,"Barletta"),[])

    def test_nightz_scheda_documentata(self):
        dt = crawler.oggi_dt() + crawler.timedelta(days=3)
        mese = next(k for k,v in crawler.MESI_IT.items() if v == dt.month)
        html = f"<h1>Around Us</h1><p>Data e orario</p><p>{dt.day} {mese} {dt.year}</p><p>Dalle 23:00</p><p>Location</p><p>Bisceglie</p><p>Divine Club, Bisceglie, BT, Italia</p>"
        url = "https://nightz.it/eventi/around-us/"
        ev = crawler.analizza_nightz(html,url)
        self.assertEqual(len(ev),1)
        self.assertEqual(ev[0]["categoria"],"Locali & Serate")
        self.assertEqual(ev[0]["citta"],"Bisceglie")
        self.assertEqual(crawler.analizza_nightz(html.replace("Bisceglie","Bari"),url),[])
        self.assertEqual(crawler.analizza_nightz(html,"https://nightz.it/eventi/"),[])
        nuovo = "https://nightoutz.it/eventi/around-us/"
        self.assertEqual(len(crawler.analizza_nightz(html,nuovo)),1)
        self.assertTrue(crawler._fonte_appartiene_a_raccolta_automatica(nuovo))
        self.assertEqual(crawler.analizza_nightz(html,"https://nightoutz.it.evil.test/eventi/around-us/"),[])
        self.assertEqual(crawler.analizza_nightz(html.replace("Bisceglie","Bari"),nuovo),[])
        self.assertTrue(crawler.calendario_ha_link_movida('<a href="/eventi/around-us/">Around Us</a>', "https://nightoutz.it/eventi/", "nightoutz.it", "nightz"))
    def test_diagnostica_markup_pubblico(self):
        self.assertEqual(crawler.diagnostica_scheda_movida("<h1>Serata</h1><p>Location</p>","https://example.org")["h1"],"Serata")

    def test_ticketsms_concordanza_data_luogo(self):
        dt = crawler.oggi_dt() + crawler.timedelta(days=3)
        mese = next(k for k,v in crawler.MESI_IT.items() if v == dt.month)
        url = "https://www.ticketsms.it/it/event/Golden-Idol-Club-" + dt.strftime("%d-%m-%Y")
        html = f"<h1>Golden Opening Party</h1><p>{dt.day} {mese} {dt.year} / 22:00</p><h4>Idol Club / Bisceglie</h4>"
        self.assertEqual(len(crawler.analizza_ticketsms(html,url,"Bisceglie","Idol Club")),1)
        self.assertEqual(crawler.analizza_ticketsms(html,url,"Trani","Idol Club"),[])
        self.assertEqual(crawler.analizza_ticketsms(html.replace("22:00",""),url,"Bisceglie","Idol Club"),[])
    def test_ticketsms_verifica_renderizzato_e_salta_eventi_passati(self):
        today = crawler.datetime(2026, 11, 27, 12)
        fonte = next(f for f in crawler.FONTI_PORTALI if f.get("ticketsms"))
        url = "https://www.ticketsms.it/event/Golden-Opening-Party-At-Vyon-Club-Bisceglie-Idol-Club-28-11-2026"
        shell = "<html><head><title>TicketSms</title></head><body><div id='root'></div></body></html>"
        indice = (
            '<a href="/event/Altro-21-11-2026">Passato</a>'
            '<a href="/event/Golden-Opening-Party-At-Vyon-Club-Bisceglie-Idol-Club-28-11-2026">Golden</a>'
        )
        scheda = (
            "<h4>Sabato 28 novembre 2026 / 23:00</h4>"
            "<h1>Golden - Opening Party at Vyon Club</h1><h4>IDOL CLUB / BISCEGLIE</h4>"
        )
        with patch.object(crawler, "oggi_dt", return_value=today):
            self.assertFalse(crawler.calendario_ha_link_movida(
                '<a href="/event/Ara-10-10-2026">Ara</a>', fonte["url"], fonte["dominio"], "ticketsms"
            ))
            self.assertEqual(crawler.analizza_ticketsms(shell, url, "Bisceglie", "Idol Club"), [])
            self.assertEqual(crawler.analizza_ticketsms(
                scheda+"<h3>Evento annullato</h3>", url, "Bisceglie", "Idol Club"
            ), [])
            session = Mock()
            session.get.return_value = SimpleNamespace(status_code=200, text=shell, apparent_encoding="utf-8")
            with patch.object(crawler, "render_calendario_pubblico", side_effect=[(indice, "ok"), (scheda, "ok")]) as render:
                eventi = crawler.raccogli_da_portale_generico(session, fonte)
        self.assertEqual([arg.args[0] for arg in session.get.call_args_list], [fonte["url"], url])
        self.assertEqual([arg.args[-1] for arg in render.call_args_list], ["ticketsms", "ticketsms-scheda"])
        self.assertEqual(len(eventi), 1)
        self.assertEqual(eventi[0]["fonteUrl"], url)
        self.assertEqual(eventi[0]["luogo"], "Idol Club")
        self.assertIn("23:00", eventi[0]["dataTesto"])

    def test_ticketsms_usa_la_card_solo_se_data_sede_e_titolo_concordano(self):
        fonte = next(f for f in crawler.FONTI_PORTALI if f.get("ticketsms"))
        percorso = "/event/Golden-Opening-Party-At-Vyon-Club-Bisceglie-Idol-Club-28-11-2026"
        titolo = "Golden - Opening Party at Vyon Club"
        card = (
            f'<a href="{percorso}" title="{titolo} - BISCEGLIE - IDOL CLUB - 28/11/2026 - TicketSms">'
            '<img alt="Golden al Vyon Club"></a>'
            f'<a href="{percorso}"><div>sabato 28 novembre / 23:00</div><h5>{titolo}</h5><div>IDOL CLUB</div></a>'
        )
        session = Mock()
        shell = "<title>TicketSms</title><div id='root'></div>"
        session.get.return_value = SimpleNamespace(status_code=200, text=shell, apparent_encoding="utf-8")
        with patch.object(crawler, "oggi_dt", return_value=crawler.datetime(2026, 11, 27, 12)):
            casi = [
                (card, shell, "nessuna scheda dopo rendering", 1),
                (card.replace("28 novembre", "29 novembre"), shell, "nessuna scheda dopo rendering", 0),
                (card.replace("BISCEGLIE", "TRANI"), shell, "nessuna scheda dopo rendering", 0),
                (card, "<h2>Evento annullato</h2>", "nessuna scheda dopo rendering", 0),
                (card, "", "blocco esplicito", 0),
            ]
            for elenco, dettaglio, esito, attesi in casi:
                with self.subTest(esito=esito, dettaglio=dettaglio, elenco=elenco), patch.object(
                    crawler, "render_calendario_pubblico", side_effect=[(elenco, "ok"), (dettaglio, esito)]
                ):
                    eventi = crawler.raccogli_da_portale_generico(session, fonte)
                    self.assertEqual(len(eventi), attesi)
                    if eventi:
                        self.assertEqual(eventi[0]["titolo"], titolo)
                        self.assertIn("23:00", eventi[0]["dataTesto"])

    def test_sede_riservata_non_attribuita_a_comune(self):
        self.assertTrue(crawler.evento_sede_riservata({"titolo":"ECHOES Opening Winter Season with Stefano Andriezzi","dataInizio":"2026-11-28"}))
        self.assertFalse(crawler.evento_sede_riservata({"titolo":"Habibi","dataInizio":"2026-11-28"}))

    def test_xceed_scheda_data_e_sede(self):
        data = crawler.oggi_dt() + crawler.timedelta(days=3)
        mese = next(k for k,v in crawler.MESI_IT.items() if v == data.month)
        date = f"{data.day} {mese} {data.year}"
        url = "https://xceed.me/it/barletta/event/serata/1234"
        html = f"<h1>Classic Saturday DJ set</h1><p>{date} alle ore 22:00</p><h2>Info</h2><p>Una serata in discoteca con DJ set e musica.</p><h2>Location</h2><p>Atrio22, Barletta</p><h2>Indirizzo</h2><p>Via Leonardo da Vinci 15, Barletta</p>"
        ev = crawler.analizza_xceed(html,url,"Barletta")
        html_nodi = html.replace("Classic Saturday DJ set","<span>Classic Saturday</span><span>DJ set</span>").replace("alle ore 22:00","<span>alle ore</span><span>22:00</span>")
        self.assertEqual(len(crawler.analizza_xceed(html_nodi,url,"Barletta")),1)
        self.assertEqual(len(ev),1)
        self.assertEqual(ev[0]["dataInizio"],data.strftime("%Y-%m-%d"))
        self.assertEqual(ev[0]["categoria"],"Locali & Serate")
        self.assertEqual(crawler.analizza_xceed(html,url,"Trani"),[])
        self.assertEqual(crawler.analizza_xceed(html.replace("Una serata",f"{data.day} {mese} {data.year-1} Una serata"),url,"Barletta"),[])
        self.assertEqual(crawler.analizza_xceed(html,"https://xceed.me/it/barletta/events","Barletta"),[])


    def test_fonti_movida_costiera(self):
        nomi = {f["nome"] for f in crawler.FONTI_PORTALI if f.get("nightlife")}
        for citta in ("Trani", "Barletta", "Manfredonia"):
            self.assertIn("Tacco di Bacco Nightlife " + citta, nomi)
        self.assertIn("ManfredoniaEventi Nightlife", nomi)
        self.assertIn("LINEA Club Trani", nomi)

    def test_date_permalinks_movida(self):
        self.assertEqual(crawler.data_scheda_movida("https://linea.live/events/opening-2026-11-28"), "2026-11-28")
        self.assertEqual(crawler.data_scheda_movida("https://manfredoniaeventi.com/evento/dj-set-26-novembre-2026/"), "2026-11-26")
        self.assertEqual(crawler.data_scheda_movida("https://linea.live/events/city/trani"), "")

    def test_cena_spettacolo_e_promoter(self):
        for titolo in ("Acquolina in Cena Spettacolo", "Cena con spettacolo", "Cena con DJ set", "Dinner-show"):
            self.assertEqual(crawler.classifica_categoria(titolo),"Locali & Serate")
            self.assertTrue(crawler.indizi_movida(titolo))
        self.assertFalse(crawler.indizi_movida("Ristorante aperto tutti i giorni"))
        self.assertTrue(any(x["nome"]=="Acquolina Food Boutique" for x in crawler.registro_locali_movida()["Foggia"]))
    def test_movida_non_convegni(self):
        self.assertTrue(crawler.evento_movida_documentato({"categoria":"Musica & Concerti","titolo":"Live music al pub"}))
        self.assertFalse(crawler.evento_movida_documentato({"categoria":"Attività diurne","titolo":"Convegno"}))
        self.assertEqual(crawler.classifica_categoria("Opening winter season with Stefano Andriezzi"),"Locali & Serate")

    def test_date_separate_non_intervallo(self):
        ref = crawler.datetime(2026, 11, 25)
        self.assertEqual(crawler.date_discontinue("Mercatini 11, 13 e 20 dicembre 2026", ref), ["2026-12-11","2026-12-13","2026-12-20"])
        self.assertEqual(crawler.date_discontinue("dal 11 al 20 dicembre 2026", ref), [])
        self.assertEqual(crawler.date_discontinue("28 e 31 febbraio 2027", ref), [])

    def test_ricorrenza_mensile_non_inventa_date(self):
        testo = "Antiquariando, seconda domenica di ogni mese"
        self.assertFalse(crawler.ricorrenza_compatibile(testo, "2026-11-24"))
        self.assertTrue(crawler.ricorrenza_compatibile(testo, "2026-12-13"))
        self.assertTrue(crawler.ricorrenza_compatibile("ultima domenica del mese", "2026-12-27"))

    def test_orario_jsonld(self):
        self.assertEqual(crawler.orario_data_strutturata("2026-12-13T21:30:00+01:00"), " · Ore 21:30")
        self.assertEqual(crawler.orario_data_strutturata("2026-12-13"), "")
        self.assertEqual(crawler.orario_data_strutturata("2026-12-13T00:00:00"), "")

    def test_concordanza_fonti_non_confonde_date(self):
        e = {"titolo":"Concerto in piazza", "citta":"Cerignola", "luogo":"Piazza Libertà", "dataInizio":"2026-12-13", "dataFine":"2026-12-13", "fonteUrl":"https://example.org/evento"}
        b = dict(e, fonteUrl="https://example.net/serata")
        c = dict(b, dataInizio="2026-12-20", dataFine="2026-12-20")
        self.assertEqual(len(crawler.evidenze_fonti([e,b], [e])), 1)
        self.assertEqual(crawler.evidenze_fonti([e,c], [e]), [])
        self.assertEqual(crawler.evidenze_fonti([e,dict(e,fonteUrl="https://www.example.org/altro")], [e]), [])

    def test_stato_evento_annullato_non_ripescato(self):
        url = "https://example.org/evento/serata"
        data = (crawler.oggi_dt() + crawler.timedelta(days=3)).strftime("%Y-%m-%d")
        ev = {"@type": "Event", "name": "Serata DJ set", "startDate": data, "eventStatus": "https://schema.org/EventCancelled", "url": url}
        import json
        html = '<script type="application/ld+json">' + json.dumps(ev) + '</script><h1>Serata DJ set</h1><p>Luogo: Piazza Matteotti, Cerignola</p>'
        try:
            crawler.STATI_EVENTI_NEGATIVI.clear()
            self.assertEqual(crawler.analizza_pagina_evento(html, url, "Cerignola", True), [])
            self.assertTrue(crawler.evento_non_attivo({"fonteUrl": url, "dataInizio": data}))
            self.assertFalse(crawler.evento_non_attivo({"fonteUrl": url, "dataInizio": "2099-01-01"}))
            self.assertFalse(crawler.evento_non_attivo({"fonteUrl": "https://example.org/evento/altro", "dataInizio": data}))
        finally:
            crawler.STATI_EVENTI_NEGATIVI.clear()

    def test_stato_riprogrammato_solo_vecchia_data(self):
        import json
        url = "https://example.org/evento/serata"
        ev = {"@type": "Event", "name": "Serata", "startDate": "2030-03-01", "previousStartDate": "2030-02-01", "eventStatus": "https://schema.org/EventRescheduled", "url": url}
        try:
            crawler.STATI_EVENTI_NEGATIVI.clear()
            crawler.registra_stati_negativi('<script type="application/ld+json">' + json.dumps(ev) + '</script>', url)
            self.assertTrue(crawler.evento_non_attivo({"fonteUrl": url, "dataInizio": "2030-02-01"}))
            self.assertFalse(crawler.evento_non_attivo({"fonteUrl": url, "dataInizio": "2030-03-01"}))
        finally:
            crawler.STATI_EVENTI_NEGATIVI.clear()

    def test_spettacolo_in_sede_teatrale(self):
        self.assertEqual(
            crawler.classifica_categoria("Cenerentola 301", luogo="Teatro Comunale Lucio Dalla"),
            "Teatro & Spettacoli",
        )

    def test_concerto_in_teatro_resta_musica(self):
        self.assertEqual(
            crawler.classifica_categoria(
                "Recital pianistico – Alfonso Soldano",
                luogo="Teatro Umberto Giordano",
            ),
            "Musica & Concerti",
        )

    def test_cabaret_e_teatro(self):
        self.assertEqual(
            crawler.classifica_categoria("Breaking Brecht – Sing’n’Song Cabaret"),
            "Teatro & Spettacoli",
        )

    def test_portale_teatrale_non_sovrascrive_indizi_musicali(self):
        self.assertEqual(
            crawler.classifica_categoria(
                "Concerto di musica dal vivo",
                luogo="Roma Teatro Cinema",
                fonte_url="https://romateatrocinema.it/evento/test",
            ),
            "Musica & Concerti",
        )

    def test_calendari_puglia_culture_cerignola_configurati(self):
        fonti = {fonte["nome"]: fonte for fonte in crawler.FONTI_PORTALI}
        self.assertIn("Puglia Culture Stagione Teatrale Cerignola 2026/27", fonti)
        self.assertIn("Puglia Culture Teatro Ragazzi Cerignola 2026/27", fonti)
        self.assertTrue(fonti["Puglia Culture Stagione Teatrale Cerignola 2026/27"]["url"].endswith(
            "/rassegna/cerignola-stagione-teatrale-2026-27-un-teatro-per-tutti/"
        ))

    def test_elenco_puglia_culture_usa_card_evento_come_fallback(self):
        html = """
        <html><body><main>
          <div class="event-card">
            <a href="/evento/breaking-brecht-3/">BREAKING BRECHT</a>
            <p>domenica 06 dicembre 2026</p>
            <p>Teatro: Teatro Comunale S. Mercadante - Cerignola</p>
            <p>Prezzo: a partire da € 12</p>
          </div>
          <div class="event-card">
            <a href="/evento/mio-sempre-mio-andrea/">MIO, SEMPRE, MIO ANDREA</a>
            <p>venerdì 29 gennaio 2027</p>
            <p>Teatro: Teatro Comunale S. Mercadante - Cerignola</p>
          </div>
          <div class="event-card">
            <a href="/evento/spettacolo-altro-comune/">SPETTACOLO ALTRO COMUNE</a>
            <p>sabato 12 dicembre 2026</p>
            <p>Teatro: Teatro Comunale - Foggia</p>
          </div>
        </main></body></html>
        """
        soup = crawler.BeautifulSoup(html, "html.parser")
        eventi = crawler.estrai_eventi_puglia_da_elenco(
            soup,
            "https://www.pugliaculture.it/rassegna/cerignola-stagione-teatrale-2026-27-un-teatro-per-tutti/",
            "Cerignola",
        )
        self.assertEqual(len(eventi), 2)
        self.assertEqual(
            {evento["titolo"] for evento in eventi},
            {"BREAKING BRECHT", "MIO, SEMPRE, MIO ANDREA"},
        )
        self.assertTrue(all(evento["citta"] == "Cerignola" for evento in eventi))
        self.assertTrue(all(evento["luogo"] == "Teatro Comunale S. Mercadante" for evento in eventi))

    def test_puglia_culture_card_riconosce_sede_con_link_separati(self):
        html = """
        <html><body><main>
          <article class="event-card">
            <a href="/evento/breaking-brecht-3/">BREAKING BRECHT</a>
            <p>domenica 06 dicembre 2026</p>
            <p>Teatro:</p>
            <p><a href="/luogo/teatro-mercadante/">Teatro Comunale S. Mercadante</a> -
               <a href="/luogo/cerignola/">Cerignola</a></p>
          </article>
        </main></body></html>
        """
        soup = crawler.BeautifulSoup(html, "html.parser")
        eventi = crawler.estrai_eventi_puglia_da_elenco(
            soup,
            "https://www.pugliaculture.it/rassegna/cerignola-stagione-teatrale-2026-27-un-teatro-per-tutti/",
            "Cerignola",
        )
        self.assertEqual(len(eventi), 1)
        self.assertEqual(eventi[0]["titolo"], "BREAKING BRECHT")
        self.assertEqual(eventi[0]["luogo"], "Teatro Comunale S. Mercadante")
        self.assertEqual(eventi[0]["dataInizio"], "2026-12-06")

    def test_scheda_puglia_culture_con_metadati_fuori_main(self):
        html = """
        <html><body>
          <main><h1>MIO, SEMPRE, MIO ANDREA</h1></main>
          <section class="event-meta">
            <time datetime="2027-01-29T21:00:00+01:00">venerdì 29 gennaio 2027</time>
            <p>Prosa</p>
            <p>Teatro: Teatro Comunale S. Mercadante - Cerignola</p>
            <p>Prezzo: a partire da € 12</p>
            <p>Un progetto intenso che intreccia parole, musica e immagini.</p>
          </section>
        </body></html>
        """
        eventi = crawler.analizza_pagina_evento(
            html,
            "https://www.pugliaculture.it/evento/mio-sempre-mio-andrea/",
            citta_default="Cerignola",
            fonte_curata_eventi=True,
        )
        self.assertEqual(len(eventi), 1)
        self.assertEqual(eventi[0]["dataInizio"], "2027-01-29")
        self.assertEqual(eventi[0]["citta"], "Cerignola")
        self.assertEqual(eventi[0]["luogo"], "Teatro Comunale S. Mercadante")
        self.assertEqual(eventi[0]["categoria"], "Teatro & Spettacoli")

    def test_categoria_attivita_famiglie_e_natura(self):
        self.assertEqual(crawler.classifica_categoria("Laboratorio creativo per bambini e famiglie"), "Famiglie & Bambini")
        self.assertEqual(crawler.classifica_categoria("Escursione guidata lungo l'Ofanto"), "Natura & Escursioni")

    def test_feed_social_pubblici_configurati(self):
        self.assertGreaterEqual(len(crawler.FONTI_SOCIAL_RSS), 5)
        self.assertTrue(any("instagram.com" in f["url"] for f in crawler.FONTI_SOCIAL_RSS))
        self.assertTrue(any("facebook.com" in f["url"] for f in crawler.FONTI_SOCIAL_RSS))
        self.assertTrue(any("birdwatching" in f["url"] and "cicloturismo" in f["url"] for f in crawler.FONTI_SOCIAL_RSS))

    def test_catalogo_esperienze_weekend(self):
        import json
        from pathlib import Path
        catalogo = json.loads((Path(__file__).parent / "esperienze.json").read_text(encoding="utf-8"))
        self.assertGreaterEqual(len(catalogo), 20)
        self.assertTrue(all(x.get("tipoContenuto") == "esperienza" for x in catalogo))
        self.assertTrue(all(x.get("titolo") and x.get("citta") and x.get("indirizzoMappa") for x in catalogo))
        self.assertTrue(any("bosco" in x.get("titolo", "").lower() for x in catalogo))
        self.assertTrue(any("famiglie" in x.get("adattoA", "").lower() for x in catalogo))
        titoli = {x["titolo"] for x in catalogo}
        self.assertTrue(any("Faeto" in titolo for titolo in titoli))
        self.assertTrue(any("Foresta Umbra" in titolo for titolo in titoli))
        self.assertTrue(any("Oasi Lago Salso" in titolo for titolo in titoli))
        self.assertTrue(all(x.get("fonteUrl") for x in catalogo if any(k in x["titolo"] for k in ("Ripa Alta", "Faeto", "Foresta Umbra", "Oasi Lago Salso"))))

    def test_ocr_gestisce_immagini_palette_con_trasparenza(self):
        try:
            from PIL import Image
        except ImportError:
            self.skipTest("Pillow non installato in questo workflow")

        immagine = Image.new("P", (40, 40), 0)
        immagine.putpalette([0, 0, 0, 255, 255, 255] + [0, 0, 0] * 254)
        immagine.info["transparency"] = 0
        buffer = io.BytesIO()
        immagine.save(buffer, format="PNG")

        risposta = SimpleNamespace(
            status_code=200,
            headers={"Content-Type": "image/png"},
            content=buffer.getvalue(),
        )
        session = Mock()
        session.get.return_value = risposta

        with patch.dict(sys.modules, {"pytesseract": SimpleNamespace(image_to_string=lambda *args, **kwargs: "Locandina evento Cerignola sabato 12 dicembre")}):
            with warnings.catch_warnings(record=True) as avvisi:
                warnings.simplefilter("always")
                testo = crawler.estrai_testo_locandine(
                    session,
                    '<html><head><meta property="og:image" content="https://example.test/locandina.png"></head></html>',
                    base_url="https://example.test/",
                )

        self.assertIn("Cerignola", testo)
        self.assertFalse(any("Palette images with Transparency" in str(w.message) for w in avvisi))

    def test_ocr_rispetta_budget_timeout_e_non_blocca(self):
        try:
            from PIL import Image
        except ImportError:
            self.skipTest("Pillow non installato")
        buffer = io.BytesIO()
        Image.new("RGB", (50, 50)).save(buffer, format="PNG")
        session = Mock()
        session._csf_ocr_budget = {"rimanenti": 1}
        session.get.return_value = SimpleNamespace(status_code=200, headers={"Content-Type":"image/png"}, content=buffer.getvalue())
        ocr = Mock(side_effect=RuntimeError("timeout simulato"))
        html = '<main><img src="https://example.test/logo.png"><img src="https://example.test/poster.png"><img src="https://example.test/secondo.png"></main>'
        with patch.dict(sys.modules, {"pytesseract": SimpleNamespace(image_to_string=ocr)}):
            self.assertEqual(crawler.estrai_testo_locandine(session, html), "")
            self.assertEqual(crawler.estrai_testo_locandine(session, html), "")
        self.assertEqual(session.get.call_count, 1)
        self.assertEqual(session.get.call_args.args[0], "https://example.test/poster.png")
        self.assertEqual(ocr.call_args.kwargs["timeout"], crawler.OCR_TIMEOUT_SECONDI)

    def test_ocr_locandine_senza_immagini_non_blocca(self):
        self.assertEqual(crawler.estrai_testo_locandine(None), "")

    def test_indirizzo_concatenato_due_volte(self):
        indirizzo = (
            "Via Boccaccio 42/44, Barletta. Barletta, "
            "Via Boccaccio 42/44, Barletta"
        )
        self.assertEqual(
            crawler.normalizza_indirizzo_mappa(
                indirizzo, "Rainbow Bridge plays Hendrix", "Barletta"
            ),
            "Via Boccaccio 42/44, Barletta",
        )


if __name__ == "__main__":
    unittest.main()
