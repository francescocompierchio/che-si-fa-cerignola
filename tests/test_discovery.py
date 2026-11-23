import unittest
import json
import os
import tempfile
from datetime import datetime
from unittest.mock import patch

import aggiorna_eventi as motore


class RisoluzioneComuneTests(unittest.TestCase):
    def test_indirizzo_reale_prevale_sulla_citta_predefinita(self):
        evento = {
            "tipoContenuto": "evento",
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


class ControlliQualitaTests(unittest.TestCase):
    def evento_base(self, **extra):
        evento = {
            "tipoContenuto": "evento",
            "citta": "Cerignola",
            "categoria": "Attività diurne",
            "titolo": "Evento di prova a Cerignola",
            "dataTesto": "Mar 24 Nov 2026",
            "dataInizio": "2026-11-24",
            "dataFine": "2026-11-24",
            "luogo": "Teatro Mercadante",
            "indirizzoMappa": "Teatro Mercadante, Cerignola",
            "descrizione": "Appuntamento culturale presso il Teatro Mercadante di Cerignola.",
            "fonteUrl": "https://iltaccodibacco.it/puglia/eventi/337999.html",
        }
        evento.update(extra)
        return evento

    def test_localita_fuori_bacino_non_eredita_citta_default(self):
        evento = self.evento_base(
            descrizione="Sannicandro di Bari (Bari) Castello di Sannicandro, ore 17:30."
        )
        self.assertIsNone(
            motore.normalizza_e_valida_evento(
                evento, ref_dt=datetime(2026, 11, 23), fonte_curata_eventi=True
            )
        )

    def test_localita_nazionale_fuori_bacino_con_sigla_provincia(self):
        self.assertEqual(
            motore._localita_esplicita_fuori_area("Roma (RM) Teatro comunale"),
            "Roma",
        )
        evento = self.evento_base(
            descrizione="Roma (RM) Teatro comunale, appuntamento il 24 novembre."
        )
        self.assertIsNone(
            motore.normalizza_e_valida_evento(
                evento, ref_dt=datetime(2026, 11, 23), fonte_curata_eventi=True
            )
        )

    def test_monopoli_fuori_bacino_viene_esclusa(self):
        evento = self.evento_base(
            titolo="Natale ad Alberobello",
            descrizione="Dal 5 dicembre 2026 Monopoli (Bari), Viale Monacelle."
        )
        self.assertIsNone(
            motore.normalizza_e_valida_evento(
                evento, ref_dt=datetime(2026, 11, 23), fonte_curata_eventi=True
            )
        )

    def test_indirizzo_non_ripete_due_volte_il_comune(self):
        self.assertEqual(
            motore.normalizza_indirizzo_mappa("Foggia, Foggia", "Teatro Giordano", "Foggia"),
            "Foggia",
        )

    def test_indirizzo_mappa_rimuove_duplicazioni_con_separatori_misti(self):
        self.assertEqual(
            motore.normalizza_indirizzo_mappa(
                "Via Boccaccio 42/44, Barletta. Barletta, Barletta",
                "Via Boccaccio 42/44, Barletta",
                "Barletta",
            ),
            "Via Boccaccio 42/44, Barletta",
        )

    def test_corso_non_viene_accettato_come_sede(self):
        evento = self.evento_base(
            luogo="corso",
            indirizzoMappa="corso, Cerignola",
            descrizione="Corso da Sommelier Primo Livello. Per informazioni consultare il sito."
        )
        self.assertIsNone(
            motore.normalizza_e_valida_evento(
                evento, ref_dt=datetime(2026, 11, 23), fonte_curata_eventi=True
            )
        )

    def test_scheda_tacco_generica_non_viene_pubblicata(self):
        evento = self.evento_base(
            fonteUrl="https://iltaccodibacco.it/barletta/concerti/"
        )
        self.assertIsNone(
            motore.normalizza_e_valida_evento(
                evento, ref_dt=datetime(2026, 11, 23), fonte_curata_eventi=True
            )
        )

    def test_comune_da_descrizione_prevale_sulla_citta_appesa_all_indirizzo(self):
        evento = self.evento_base(
            citta="Foggia",
            titolo="Cenerentola 301",
            luogo="Teatro Comunale Lucio Dalla prosegue",
            indirizzoMappa="Teatro Comunale Lucio Dalla prosegue, Foggia",
            descrizione="Manfredonia (Foggia) Teatro Comunale Lucio Dalla Via della Crocie ore 18:00."
        )
        risultato = motore.normalizza_e_valida_evento(
            evento, ref_dt=datetime(2026, 11, 23), fonte_curata_eventi=True
        )
        self.assertIsNotNone(risultato)
        self.assertEqual(risultato["citta"], "Manfredonia")
        self.assertTrue(risultato["indirizzoMappa"].endswith("Manfredonia"))

    def test_centro_piazze_non_e_una_sede_verificabile(self):
        evento = self.evento_base(
            citta="Barletta",
            luogo="Centro / Piazze, Barletta",
            indirizzoMappa="Centro / Piazze, Barletta",
            descrizione="Appuntamento in centro / piazze, Barletta."
        )
        self.assertIsNone(
            motore.normalizza_e_valida_evento(
                evento, ref_dt=datetime(2026, 11, 23), fonte_curata_eventi=True
            )
        )

    def test_comune_reale_lucera_corregge_default_cerignola(self):
        evento = self.evento_base(
            titolo="Gianni Fiorellino",
            luogo="Cinema dell'Opera, Via Giordano Bruno 3, Lucera (FG)",
            indirizzoMappa="Cinema dell'Opera, Via Giordano Bruno 3, Lucera (FG), Cerignola",
            descrizione="Concerto di Gianni Fiorellino.",
        )
        risultato = motore.normalizza_e_valida_evento(
            evento, ref_dt=datetime(2026, 11, 23), fonte_curata_eventi=True
        )
        self.assertIsNotNone(risultato)
        self.assertEqual(risultato["citta"], "Lucera")
        self.assertNotIn(", Cerignola", risultato["indirizzoMappa"])

    def test_riconvalida_archivio_corregge_auto_e_conserva_manuali(self):
        automatico = self.evento_base(
            titolo="Gianni Fiorellino",
            luogo="Cinema dell'Opera, Via Giordano Bruno 3, Lucera (FG)",
            indirizzoMappa="Cinema dell'Opera, Via Giordano Bruno 3, Lucera (FG), Cerignola",
            descrizione="Concerto di Gianni Fiorellino.",
            fonteUrl="https://experience-app.com/evento/2393",
        )
        generico = self.evento_base(
            titolo="Evento senza scheda specifica",
            fonteUrl="https://iltaccodibacco.it/barletta/concerti/",
        )
        manuale = self.evento_base(
            titolo="Evento inviato da un locale",
            manuale=True,
            fonteUrl="https://example.com/evento-manuale",
        )
        with tempfile.TemporaryDirectory() as cartella:
            percorso = os.path.join(cartella, "eventi.json")
            with open(percorso, "w", encoding="utf-8") as f:
                json.dump([automatico, generico, manuale], f, ensure_ascii=False)
            manuali, automatici, scaduti = motore.carica_esistenti_protetti(percorso)

        self.assertEqual(scaduti, 0)
        self.assertEqual(len(manuali), 1)
        self.assertEqual(manuali[0]["titolo"], "Evento inviato da un locale")
        self.assertEqual(len(automatici), 1)
        self.assertEqual(automatici[0]["citta"], "Lucera")
        self.assertEqual(automatici[0]["titolo"], "Gianni Fiorellino")

    def test_ripara_codifica_titolo_e_apostrofo(self):
        self.assertEqual(
            motore._ripara_codifica("La Verit√Ý degli Avvocati: un‚Äôindagine"),
            "La Verità degli Avvocati: un’indagine",
        )

    def test_mercatino_di_natale_non_diventa_natura_per_la_parola_passeggiata(self):
        self.assertEqual(
            motore.classifica_categoria("Andria | mercatino di Natale e passeggiata"),
            "Famiglie & Bambini",
        )


class MigliorieClassificazioneLuoghiTests(unittest.TestCase):
    def test_esibizioni_musicali_senza_parola_concerto(self):
        casi = [
            "Christmas Vocal Harmony – SeiOttavi",
            "Echi dell’anima – Quatuor Naka",
            "Hendrix Birthday Eve JAM al Santo Graal",
            "Rainbow Bridge plays Hendrix",
            'FRANCO CALIFANO live tribute con la "CALIFFO BAND"',
            "Tra tradizione popolare e lirica: il sassofono racconta l’Europa",
        ]
        for titolo in casi:
            with self.subTest(titolo=titolo):
                self.assertEqual(motore.classifica_categoria(titolo), "Musica & Concerti")

    def test_serate_dj_e_party_restano_locali(self):
        for titolo in ("DJ set al pub", "Club night e party", "Aperitivo musicale"):
            with self.subTest(titolo=titolo):
                self.assertEqual(motore.classifica_categoria(titolo), "Locali & Serate")

    def test_film_festival_non_diventa_automaticamente_musica(self):
        self.assertEqual(
            motore.classifica_categoria("Foggia Film Festival con Jun Ichikawa"),
            "Attività diurne",
        )

    def test_pulisce_code_editoriali_e_citta_duplicata_nella_sede(self):
        self.assertEqual(
            motore.normalizza_nome_luogo("Teatro Comunale Lucio Dalla prosegue", "Manfredonia"),
            "Teatro Comunale Lucio Dalla",
        )
        self.assertEqual(
            motore.normalizza_nome_luogo("Biblioteca storica dell’Ordine degli Avvocati di Trani Trani", "Trani"),
            "Biblioteca storica dell’Ordine degli Avvocati di Trani",
        )
        self.assertEqual(
            motore.normalizza_nome_luogo("Vecchie Segherie Mastrototaro Appuntamento", "Bisceglie"),
            "Vecchie Segherie Mastrototaro",
        )
        self.assertEqual(
            motore.normalizza_nome_luogo("Via Boccaccio 42/44, Barletta. Barletta", "Barletta"),
            "Via Boccaccio 42/44, Barletta",
        )
        self.assertEqual(
            motore.normalizza_nome_luogo("Biblioteca storica dell’Ordine degli Avvocati di Trani Trani", "Trani"),
            "Biblioteca storica dell’Ordine degli Avvocati di Trani",
        )
        # Una singola occorrenza della città nel nome della sede va mantenuta.
        self.assertEqual(
            motore.normalizza_nome_luogo("Teatro Comunale di Barletta", "Barletta"),
            "Teatro Comunale di Barletta",
        )

    def test_dominio_automatico_verificato_sull_host(self):
        self.assertTrue(motore._fonte_appartiene_a_raccolta_automatica("https://www.experience-app.com/evento/123"))
        self.assertFalse(motore._fonte_appartiene_a_raccolta_automatica("https://example.com/experience-app.com/evento"))
        self.assertFalse(motore._fonte_appartiene_a_raccolta_automatica(""))

    def test_record_senza_fonte_o_con_flag_manuale_sono_protetti(self):
        manuale_senza_fonte = {
            "tipoContenuto": "evento",
            "titolo": "Evento manuale senza fonte",
            "citta": "Cerignola",
            "dataInizio": "2026-11-24",
            "dataFine": "2026-11-24",
        }
        manuale_flag = {
            "tipoContenuto": "evento",
            "titolo": "Evento manuale con flag",
            "manuale": True,
            "fonteUrl": "https://experience-app.com/evento/999",
            "dataInizio": "2026-11-24",
            "dataFine": "2026-11-24",
        }
        with tempfile.TemporaryDirectory() as cartella:
            percorso = os.path.join(cartella, "eventi.json")
            with open(percorso, "w", encoding="utf-8") as f:
                json.dump([manuale_senza_fonte, manuale_flag], f, ensure_ascii=False)
            manuali, automatici, scaduti = motore.carica_esistenti_protetti(percorso)
        self.assertEqual(scaduti, 0)
        self.assertEqual(len(manuali), 2)
        self.assertEqual(automatici, [])
