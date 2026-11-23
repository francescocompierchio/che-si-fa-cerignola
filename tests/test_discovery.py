import unittest
from unittest.mock import patch

import aggiorna_eventi as motore


class RisoluzioneComuneTests(unittest.TestCase):
    def test_indirizzo_reale_prevale_sulla_citta_predefinita(self):
        evento = {
            "citta": "Cerignola",
            "indirizzoMappa": "Cinema dell'Opera, Lucera",
            "luogo": "Cinema dell'Opera",
            "titolo": "Gianni Fiorellino in concerto a Cerignola",
            "descrizione": "Spettacolo musicale",
        }
        self.assertEqual(motore.risolvi_comune_50km(evento), "Lucera")

    def test_citta_resta_fallback_se_non_ci_sono_altre_prove(self):
        self.assertEqual(
            motore.risolvi_comune_50km({"citta": "Canosa di Puglia"}),
            "Canosa di Puglia",
        )

    def test_primo_comune_nell_indirizzo_prevale_sul_comune_predefinito_in_coda(self):
        evento = {
            "citta": "Cerignola",
            "indirizzoMappa": "Cinema dell'Opera, Via Giordano Bruno 3, Lucera (FG), Cerignola",
            "luogo": "Cinema dell'Opera, Lucera",
        }
        self.assertEqual(motore.risolvi_comune_50km(evento), "Lucera")

    def test_normalizzazione_non_lascia_il_comune_errato_nell_indirizzo(self):
        evento = {
            "citta": "Cerignola",
            "titolo": "Concerto di Gianni Fiorellino",
            "dataInizio": "2026-11-28",
            "dataFine": "2026-11-28",
            "luogo": "Cinema dell'Opera, Via Giordano Bruno 3, Lucera (FG)",
            "indirizzoMappa": "Cinema dell'Opera, Via Giordano Bruno 3, Lucera (FG), Cerignola",
            "fonteUrl": "https://experience-app.com/evento/2393",
        }
        risultato = motore.normalizza_e_valida_evento(
            evento, ref_dt=datetime(2026, 11, 23), fonte_curata_eventi=True
        )
        self.assertIsNotNone(risultato)
        self.assertEqual(risultato["citta"], "Lucera")
        self.assertTrue(risultato["indirizzoMappa"].endswith("Lucera (FG)"))
        self.assertNotIn(", Cerignola", risultato["indirizzoMappa"])

    def test_gare_podistiche_e_fitness_sono_eventi_diurni(self):
        testo = "CorriCerignola: gara podistica e corsa su strada"
        self.assertIsNotNone(motore.REGEX_TEMA_COERENTE.search(testo))
        self.assertIsNone(motore.REGEX_SCARTO.search(testo))
        self.assertEqual(motore.classifica_categoria(testo), "Attività diurne")

    def test_hyrox_e_trail_running_sono_riconosciuti(self):
        self.assertIsNotNone(motore.REGEX_TEMA_COERENTE.search("Hyrox e trail running"))


class RaccoltaPortaliTests(unittest.TestCase):
    def test_analizza_solo_link_evento_e_non_la_pagina_elenco(self):
        elenco_url = "https://portale.example/eventi/"
        html = """
        <html><body>
          <a href="/eventi/">Tutti gli eventi</a>
          <a href="/scheda/concerto-2026">Concerto live in piazza</a>
          <a href="/eventi/123.html">Scheda 123</a>
          <a href="/privacy/">Privacy</a>
        </body></html>
        """

        class Risposta:
            status_code = 200
            apparent_encoding = "utf-8"

            def __init__(self, text):
                self.text = text

        class SessioneFinta:
            def get(self, url, timeout=None):
                return Risposta(html if url == elenco_url else "<html><h1>Scheda</h1></html>")

        fonte = {
            "nome": "Portale test",
            "url": elenco_url,
            "dominio": "portale.example",
            "citta_default": "Cerignola",
            "curata": True,
        }

        with patch.object(motore, "analizza_pagina_evento", return_value=[]) as analizza:
            motore.raccogli_da_portale_generico(SessioneFinta(), fonte)

        url_analizzate = [call.args[1] for call in analizza.call_args_list]
        self.assertEqual(
            url_analizzate,
            [
                "https://portale.example/scheda/concerto-2026",
                "https://portale.example/eventi/123.html",
            ],
        )
        self.assertNotIn(elenco_url, url_analizzate)


if __name__ == "__main__":
    unittest.main()
