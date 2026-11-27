from collections import Counter
from datetime import date
import json
import unittest
from unittest.mock import MagicMock, Mock

from bs4 import BeautifulSoup
import apprendimento
import fonti_editori
import radar_territorio as radar


class RadarTerritorioTests(unittest.TestCase):
    def test_approvati_legge_solo_i_campi_pubblici_necessari(self):
        oggi = date(2026, 11, 26)
        session = MagicMock()
        response = session.get.return_value.__enter__.return_value
        response.status_code = 200
        response.iter_content.return_value = [json.dumps({"privato": {
            "titolo": "Serata disco", "citta": "Cerignola", "categoria": "Locali & Serate",
            "luogo": "Caffè Esempio", "dataInizio": "2026-11-27", "fonteUrl": "",
            "email": "esempio@example.org", "descrizione": "testo non necessario",
        }}).encode()]
        record, esito = radar.leggi_approvati(
            lambda e: radar.leggi_evento_editoriale(e, {"Cerignola"}, oggi), oggi, session=session
        )
        self.assertEqual(esito, "ok")
        self.assertEqual(len(record), 1)
        self.assertEqual(record[0]["dataFine"], "2026-11-27")
        self.assertNotIn("email", record[0])
        self.assertNotIn("descrizione", record[0])
        self.assertFalse(session.get.call_args.kwargs["allow_redirects"])

    def test_registro_produttivo_alimenta_ricerca_territoriale(self):
        memoria = {}
        oggi = date(2026, 11, 26)
        base = {"citta": "Cerignola", "luogo": "Caffè Esempio", "categoria": "Locali & Serate",
                "dataInizio": "2026-11-27", "titolo": "Dj set serale"}
        automatico = dict(base, titolo="DJ set del sabato", dataInizio="2026-11-28")
        approvato = dict(base, fonteUrl="https://esempio.it/eventi/dj")
        for now in range(3):
            stato = radar.aggiorna_registro(memoria, [automatico], [approvato], oggi, now)
        organizzatore = next(iter(stato["organizzatori"].values()))
        self.assertEqual(organizzatore["categorie"], {"Locali & Serate": 2})
        self.assertTrue(organizzatore["domini"]["esempio.it"]["presenteInEventoApprovato"])
        fasce = {"Cerignola": 0, "Canosa di Puglia": 1, "Foggia": 2}
        ricerche = radar.ricerche(memoria, [], oggi, fasce.get, set(fasce))
        self.assertEqual(Counter(f["fascia_copertura"] for f in ricerche), {0: 3, 1: 2, 2: 1})
        self.assertEqual(len({f["url"] for f in ricerche}), 6)
        self.assertEqual(sum(f["focus_serate"] and f["solo_cerignola"] for f in ricerche), 2)
        self.assertTrue(any(r["nome"] == "Ricerca locale Cerignola / Caffè Esempio" for r in ricerche))
        self.assertTrue(all(r["origini_note"] for r in ricerche))

    def test_stesse_categorie_in_tutte_le_fasce_con_memoria_dei_tentativi(self):
        fasce = {"Cerignola": 0, "Stornara": 1, "Canosa di Puglia": 1, "Trani": 2, "Foggia": 2}
        memoria = {"apprendimento": {}}
        oggi = date(2026, 11, 26)
        viste = set()
        comuni_visitati = set()
        for ciclo in range(21):
            memoria["apprendimento"]["cicli"] = ciclo
            fonti = radar.ricerche(memoria, [], oggi, fasce.get, set(fasce))
            prima = fonti[0]
            esiti = {f["nome"]: {"stato": "ok", "eventiEstratti": 0} for f in fonti}
            if ciclo == 0:
                esiti = {prima["nome"]: {"stato": "pausa"}}
            report = radar.registra_ricerche(memoria, fonti, esiti, ciclo + 1)
            if ciclo == 0:
                self.assertEqual(report[0]["esito"], "pausa")
                self.assertEqual(memoria["territorio"]["ultimeRicerche"], {})
                continue
            viste.update((f["fascia_copertura"], f["categoria_cercata"]) for f in fonti)
            comuni_visitati.update(f["comune_radar"] for f in fonti if f["focus_serate"])
        self.assertEqual(viste, {(fascia, categoria) for fascia in range(3) for categoria in apprendimento.AREE})
        self.assertEqual(comuni_visitati, set(fasce))

    def test_lacune_e_riscontri_usano_comune_e_intervallo(self):
        fasce = {"Cerignola": 0, "Stornara": 1, "Foggia": 2}
        oggi = date(2026, 11, 26)
        evento = {"titolo": "Concerto al teatro", "citta": "Foggia", "categoria": "Musica & Concerti",
                  "dataInizio": "2026-11-27", "dataFine": "2026-11-27"}
        replica = dict(evento, dataInizio="2026-11-28", dataFine="2026-11-28")
        confronta = lambda x, y: x["titolo"] == y["titolo"]
        report = radar.misura_fasce([evento, replica], [evento, evento], [evento, replica],
                                  oggi, set(fasce), fasce.get, confronta)
        self.assertTrue(all(set(d["categorie"]) == set(apprendimento.AREE) for d in report.values()))
        musica = report[radar.FASCE[2]]["categorie"]["Musica & Concerti"]
        self.assertEqual(musica, {"visibili": 2, "automatici": 1, "riferimenti": 2,
                                  "conRiscontroAutomatico": 1, "senzaRiscontroAutomatico": 1})
        memoria = {"apprendimento": {"cicli": 2}, "territorio": {"ultimaVerificaCopertura": {"fasce": report}}}
        piano = radar.ricerche(memoria, [evento, replica], oggi, fasce.get, set(fasce))
        self.assertEqual(piano[-1]["categoria_cercata"], "Musica & Concerti")

    def test_ricontrolli_imminenti_riservano_posti_e_recuperano_quelli_liberi(self):
        oggi, domani = "2026-11-26", "2026-11-27"
        schede = [(f, oggi, f"{f}/oggi/{i}") for f in (0, 2) for i in range(10)]
        schede.extend((f, domani, f"{f}/domani/{i}") for f in (0, 2) for i in range(10))
        schede.append((1, domani, "1/domani/0"))
        scelti = radar.scegli_schede_imminenti(schede, 10, 2)
        self.assertEqual(len(scelti), 10)
        self.assertLessEqual(5, sum(f == 0 for f, _ in scelti))
        self.assertLessEqual(2, sum(f == 2 for f, _ in scelti))
        self.assertEqual([url for f, url in scelti if "/domani/" in url], ["1/domani/0"])
        self.assertNotEqual(scelti, radar.scegli_schede_imminenti(schede, 10, 3))

    def test_feed_autoscoperti_richiedono_origine_configurata(self):
        soup = BeautifulSoup(
            '<link rel="alternate" type="application/rss+xml" href="/agenda/feed/">'
            '<link rel="alternate" type="application/atom+xml" href="https://altro.it/atom.xml">'
            '<link rel="alternate" type="application/rss+xml" href="/comments/feed/">'
            '<link rel="alternate" type="application/rss+xml" href="/feed?token=valore">',
            "html.parser",
        )
        feed = fonti_editori.dichiarati(soup, "https://editore.it/agenda")
        self.assertEqual(feed, ["https://editore.it/agenda/feed/"])
        memoria = {}
        self.assertEqual(fonti_editori.registrati(memoria, {
            "agenda": {"stato": "ok", "feedDichiarati": feed, "cittaDichiarataFeed": "Cerignola"}
        }, 90000), 1)
        self.assertEqual(fonti_editori.scegli(memoria, 90001, {"altro.it"}), [])
        self.assertTrue(fonti_editori.scegli(memoria, 90001, {"editore.it"})[0]["feed_autoscoperto"])
        commenti = "https://editore.it/comments/feed/"
        memoria["feedEditori"][commenti] = {"scopertoAl": 90000, "confermatoAl": 90000}
        fonti_editori.registrati(memoria, {}, 90001)
        self.assertNotIn(commenti, memoria["feedEditori"])

    def test_redirect_inatteso_e_robots_fermano_la_lettura(self):
        session = Mock()
        del session._csf_robots
        session.get.return_value.status_code = 302
        session.get.return_value.headers = {"Location": "https://altro.it/agenda"}
        self.assertIsNone(fonti_editori.scheda_da_origini_note(
            session, "https://news.google.com/links/prova", {"news.google.com", "editore.it"}
        ))
        self.assertEqual(session.get.call_count, 1)
        session.get.reset_mock()
        session.get.return_value.status_code = 200
        session.get.return_value.content = b""
        session.get.return_value.text = "User-agent: *\nDisallow: /agenda/"
        self.assertIsNone(fonti_editori.scheda_da_origini_note(
            session, "https://editore.it/agenda/prova", {"editore.it"}
        ))
        self.assertEqual(session.get.call_args.args[0], "https://editore.it/robots.txt")

    def test_tempo_pubblicazione_chiede_una_fonte_con_orario_e_fuso(self):
        from datetime import datetime, timezone
        from discovery_locale import misura_ritardo
        sito = "https://editore.it/agenda/dj"
        ora = datetime(2026, 11, 26, 23, tzinfo=timezone.utc)
        self.assertEqual(misura_ritardo(None, sito, ora, "2026-11-26"), {})
        self.assertEqual(list(misura_ritardo(None, sito, ora, "2026-11-26T22:30:00Z").values()), [30])

    def test_fonti_con_dati_contraddittori_e_contatti_espliciti(self):
        from discovery_locale import date_complete, orario_locandina, testo_prenotazione
        self.assertEqual(date_complete("2026-11-26 e 27 novembre 2026"), {"2026-11-26", "2026-11-27"})
        self.assertEqual(orario_locandina("Ingresso dalle 21:30"), "21:30")
        self.assertEqual(orario_locandina("Apertura ore 21:00, inizio 23:00"), "")
        self.assertEqual(testo_prenotazione("Prenotazioni: +39 320 000 0000"), "+39 320 000 0000")
        self.assertEqual(testo_prenotazione("Info generiche +39 320 000 0000"), "")
