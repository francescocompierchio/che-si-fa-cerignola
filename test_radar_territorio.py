from datetime import date
import json
import unittest
from unittest.mock import MagicMock, Mock

from bs4 import BeautifulSoup
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
        ricerche = radar.ricerche(memoria, [], oggi, lambda c: 0 if c == "Cerignola" else 1, set(radar.COMUNI_MOVIDA))
        self.assertEqual(len(ricerche), 3)
        self.assertTrue(any(r["nome"] == "Ricerca locale Cerignola / Caffè Esempio" for r in ricerche))
        self.assertTrue(all(r["origini_note"] for r in ricerche))

    def test_feed_autoscoperti_richiedono_origine_configurata(self):
        soup = BeautifulSoup(
            '<link rel="alternate" type="application/rss+xml" href="/agenda/feed/">'
            '<link rel="alternate" type="application/atom+xml" href="https://altro.it/atom.xml">'
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
