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


class MigliorieCoperturaQualitaTests(unittest.TestCase):
    def evento_base(self, **extra):
        evento = {
            "tipoContenuto": "evento",
            "citta": "Cerignola",
            "categoria": "Attività diurne",
            "titolo": "Evento culturale di prova",
            "dataTesto": "Lun 01 Feb 2027",
            "dataInizio": "2027-02-01",
            "dataFine": "2027-02-01",
            "luogo": "Teatro Comunale Saverio Mercadante",
            "indirizzoMappa": "Teatro Comunale Saverio Mercadante, Cerignola",
            "descrizione": "Spettacolo in programma presso il teatro comunale.",
            "fonteUrl": "https://teatromercadantecerignola.it/evento/prova",
        }
        evento.update(extra)
        return evento

    def test_finestra_raccolta_include_eventi_con_oltre_45_giorni_di_anticipo(self):
        evento = self.evento_base()
        risultato = motore.normalizza_e_valida_evento(
            evento, ref_dt=datetime(2026, 11, 23), fonte_curata_eventi=True
        )
        self.assertIsNotNone(risultato)
        self.assertEqual(motore.GIORNI_ANTICIPO_MAX, 180)

    def test_finestra_raccolta_non_supera_180_giorni(self):
        evento = self.evento_base(
            dataTesto="Sab 29 Mag 2027",
            dataInizio="2027-05-29",
            dataFine="2027-05-29",
        )
        self.assertIsNone(
            motore.normalizza_e_valida_evento(
                evento, ref_dt=datetime(2026, 11, 23), fonte_curata_eventi=True
            )
        )

    def test_concerti_classici_non_vengono_scartati(self):
        for titolo in (
            "Concerto sinfonico dell'Orchestra",
            "Musica classica: Vivaldi",
            "Recital pianistico",
            "Musica da camera",
        ):
            with self.subTest(titolo=titolo):
                self.assertIsNone(motore.REGEX_SCARTO.search(titolo))
                self.assertEqual(motore.classifica_categoria(titolo), "Musica & Concerti")

    def test_indirizzo_mappa_rimuove_citta_ripetuta_dopo_sigla_provinciale(self):
        self.assertEqual(
            motore.normalizza_indirizzo_mappa(
                "Teatro Umberto Giordano, Piazza Cesare Battisti, Foggia (FG), Foggia",
                "Teatro Umberto Giordano",
                "Foggia",
            ),
            "Teatro Umberto Giordano, Piazza Cesare Battisti, Foggia (FG)",
        )

    def test_indirizzo_mappa_rimuove_citta_ripetuta_dopo_regione(self):
        self.assertEqual(
            motore.normalizza_indirizzo_mappa(
                "Teatro, Foggia, Puglia, Foggia", "Teatro", "Foggia"
            ),
            "Teatro, Foggia, Puglia",
        )

    def test_eventi_ricorrenti_in_date_diverse_non_sono_duplicati(self):
        a = self.evento_base(
            titolo="Le storie del Giovedì - Biblioteca di Comunità",
            dataInizio="2026-11-26",
            dataFine="2026-11-26",
            fonteUrl="https://comune.example/evento/giovedi-26",
        )
        b = dict(a)
        b.update({
            "dataInizio": "2026-12-03",
            "dataFine": "2026-12-03",
            "fonteUrl": "https://comune.example/evento/giovedi-03",
        })
        self.assertFalse(motore.sono_duplicati(a, b))

    def test_stesso_evento_stesso_giorno_da_fonti_diverse_e_duplicato(self):
        a = self.evento_base(
            titolo="Breaking Brecht",
            dataInizio="2026-12-06",
            dataFine="2026-12-06",
            fonteUrl="https://teatro.example/evento/brecht",
        )
        b = dict(a)
        b["fonteUrl"] = "https://puglia.example/rassegna/brecht"
        self.assertTrue(motore.sono_duplicati(a, b))

    def test_fonti_ufficiali_cerignola_sono_riconosciute_come_automatiche(self):
        self.assertTrue(
            motore._fonte_appartiene_a_raccolta_automatica(
                "https://comune.cerignola.fg.it/vivere-il-comune/eventi/workshop"
            )
        )
        self.assertTrue(
            motore._fonte_appartiene_a_raccolta_automatica(
                "https://www.teatromercadantecerignola.it/evento/breaking-brecht"
            )
        )

    def test_prefisso_schede_ufficiale_accetta_link_senza_keyword_nel_titolo(self):
        elenco_url = "https://teatromercadantecerignola.it/stagione-teatrale-2026-27/"
        html = """
        <html><body>
          <a href="/evento/soundtrack-mascagni/">SOUNDTRACK MASCAGNI</a>
          <a href="/contatti/">Contatti</a>
        </body></html>
        """

        class Risposta:
            status_code = 200
            apparent_encoding = "utf-8"

            def __init__(self, text):
                self.text = text

        class SessioneFinta:
            def get(self, url, timeout=None):
                return Risposta(html)

        fonte = {
            "nome": "Teatro ufficiale",
            "url": elenco_url,
            "dominio": "teatromercadantecerignola.it",
            "citta_default": "Cerignola",
            "curata": True,
            "prefisso_schede": "/evento/",
        }
        with patch.object(motore, "analizza_pagina_evento", return_value=[]) as analizza:
            motore.raccogli_da_portale_generico(SessioneFinta(), fonte)
        url_analizzate = [call.args[1] for call in analizza.call_args_list]
        self.assertEqual(
            url_analizzate,
            ["https://teatromercadantecerignola.it/evento/soundtrack-mascagni/"],
        )


class FontiUfficialiPrioritarieTests(unittest.TestCase):
    def test_fonti_ufficiali_locali_precedono_gli_aggregatori(self):
        nomi = [fonte["nome"] for fonte in motore.FONTI_PORTALI]
        self.assertLess(nomi.index("Puglia Culture Cerignola"), nomi.index("Tacco di Bacco Cerignola"))
        self.assertLess(nomi.index("Comune di Cerignola Eventi"), nomi.index("Experience App Foggia"))
        self.assertLess(nomi.index("Teatro Mercadante Cerignola"), nomi.index("Experience App Foggia"))

    def test_puglia_culture_e_riconosciuta_come_fonte_automatica(self):
        self.assertTrue(
            motore._fonte_appartiene_a_raccolta_automatica(
                "https://www.pugliaculture.it/evento/breaking-brecht/"
            )
        )


class LuoghiFontiUfficialiTests(unittest.TestCase):
    def test_estrazione_sede_da_etichetta_luogo_su_riga_separata(self):
        testo = (
            "Luogo\n"
            "Biblioteca di Comunità - Comune di Cerignola\n"
            "Via Cesare Battisti n. 13 - 71042 Cerignola FG\n"
        )
        self.assertEqual(
            motore.estrai_luogo_documentato(testo, "Cerignola"),
            "Biblioteca di Comunità",
        )

    def test_estrazione_sede_da_campo_teatro_etichettato(self):
        testo = (
            "Teatro: Teatro Comunale S. Mercadante - Cerignola\n"
            "sabato 6 dicembre 2026 ore 21:00\n"
        )
        self.assertEqual(
            motore.estrai_luogo_documentato(testo, "Cerignola"),
            "Teatro Comunale S. Mercadante",
        )


class RevisioneAffidabilitaCompletaTests(unittest.TestCase):
    def evento_base(self, **extra):
        evento = {
            "tipoContenuto": "evento",
            "citta": "Cerignola",
            "categoria": "Attività diurne",
            "titolo": "Spettacolo di prova al Teatro Mercadante",
            "dataTesto": "Dom 06 Dic 2026",
            "dataInizio": "2026-12-06",
            "dataFine": "2026-12-06",
            "luogo": "Teatro Mercadante",
            "indirizzoMappa": "Teatro Mercadante, Cerignola",
            "costo": "Non specificato nella fonte",
            "descrizione": "Spettacolo in programma presso il Teatro Mercadante di Cerignola.",
            "fonteUrl": "https://iltaccodibacco.it/puglia/eventi/338888.html",
        }
        evento.update(extra)
        return evento

    def test_data_iso_rifiuta_date_impossibili(self):
        for valore in ("2026-02-31", "2026-13-01", "2026-00-00", "2026-2-03", ""):
            with self.subTest(valore=valore):
                self.assertFalse(motore._data_iso_valida(valore))
        self.assertTrue(motore._data_iso_valida("2026-12-06"))

    def test_evento_con_data_impossibile_non_viene_pubblicato(self):
        evento = self.evento_base(
            dataTesto="Data non disponibile",
            dataInizio="2026-02-31",
            dataFine="2026-02-31",
        )
        self.assertIsNone(
            motore.normalizza_e_valida_evento(
                evento, ref_dt=datetime(2026, 11, 23), fonte_curata_eventi=True
            )
        )

    def test_orologio_del_motore_usa_fuso_italiano(self):
        self.assertEqual(motore.oggi_dt().tzinfo.key, "Europe/Rome")

    def test_cintura_25_km_coerente_con_le_localita_verificate(self):
        self.assertIn("Zapponeta", motore.CINTURA_25)
        self.assertIn("Minervino Murge", motore.CINTURA_25)
        self.assertNotIn("Lavello", motore.CINTURA_25)
        self.assertNotIn("Ascoli Satriano", motore.CINTURA_25)

    def test_hostname_rifiuta_dominio_falso_nel_nome_host(self):
        self.assertTrue(motore._host_appartiene(
            "https://www.iltaccodibacco.it/evento/123", "iltaccodibacco.it"
        ))
        self.assertFalse(motore._host_appartiene(
            "https://iltaccodibacco.it.evil.example/evento/123", "iltaccodibacco.it"
        ))

    def test_pagine_elenco_non_vengono_accettate_come_schede_evento(self):
        self.assertTrue(
            motore._url_pagina_elenco(
                "https://buzzeventmap.com/eventi/foggia/cerignola"
            )
        )
        self.assertTrue(
            motore._url_pagina_elenco(
                "https://experience-app.com/eventi/puglia/foggia/"
            )
        )
        self.assertFalse(
            motore._url_pagina_elenco(
                "https://buzzeventmap.com/event/eb3a9956-b25c-4b15-9f98-c56c79de3e93"
            )
        )

    def test_experience_app_con_descrizione_placeholder_viene_esclusa(self):
        evento = self.evento_base(
            titolo="Christmas Vocal Harmony – SeiOttavi",
            citta="Foggia",
            luogo="Teatro Umberto Giordano",
            indirizzoMappa="Teatro Umberto Giordano, Foggia",
            descrizione="L'indirizzo potrebbe essere inesatto, accertati prima di partire.",
            fonteUrl="https://experience-app.com/evento/2404",
        )
        self.assertIsNone(
            motore.normalizza_e_valida_evento(
                evento, ref_dt=datetime(2026, 11, 23), fonte_curata_eventi=True
            )
        )

    def test_placeholder_generico_non_viene_mostrato_nella_scheda(self):
        evento = self.evento_base(
            descrizione="L'indirizzo potrebbe essere inesatto, accertati prima di partire.",
        )
        risultato = motore.normalizza_e_valida_evento(
            evento, ref_dt=datetime(2026, 11, 23), fonte_curata_eventi=True
        )
        self.assertIsNotNone(risultato)
        self.assertNotIn("inesatto", risultato["descrizione"].lower())
        self.assertIn("verifica orari", risultato["descrizione"].lower())

    def test_testi_html_vengono_decodificati_prima_della_pubblicazione(self):
        self.assertEqual(
            motore._ripara_codifica('Iva Zanicchi &amp; Samuel Peron &quot;Viva la Mamma&quot;'),
            'Iva Zanicchi & Samuel Peron "Viva la Mamma"',
        )

    def test_concerto_sinfonico_in_inglese_e_classificato_musica(self):
        titolo = "ALAMAR SYMPHONIC CONCERT Ana Carla Maza & Orchestra"
        self.assertIsNotNone(motore.REGEX_TEMA_COERENTE.search(titolo))
        self.assertEqual(motore.classifica_categoria(titolo), "Musica & Concerti")

    def test_eventi_jsonld_usano_url_individuale_e_indirizzo_strutturato(self):
        html = """
        <html><head>
        <script type="application/ld+json">
        {
          "@context": "https://schema.org",
          "@type": "Event",
          "name": "Concerto sinfonico a Cerignola",
          "startDate": "2026-12-06T20:30:00+01:00",
          "endDate": "2026-12-06T22:30:00+01:00",
          "url": "https://iltaccodibacco.it/puglia/eventi/338777.html",
          "description": "Concerto sinfonico con orchestra al Teatro Mercadante di Cerignola.",
          "location": {
            "@type": "Place",
            "name": "Teatro Mercadante",
            "address": {
              "@type": "PostalAddress",
              "streetAddress": "Via dei Mille",
              "postalCode": "71042",
              "addressLocality": "Cerignola",
              "addressRegion": "Puglia"
            }
          }
        }
        </script>
        </head><body><h1>Calendario eventi</h1></body></html>
        """
        eventi = motore.analizza_pagina_evento(
            html,
            "https://iltaccodibacco.it/cerignola/",
            citta_default="Cerignola",
            fonte_curata_eventi=True,
        )
        self.assertEqual(len(eventi), 1)
        self.assertEqual(
            eventi[0]["fonteUrl"],
            "https://iltaccodibacco.it/puglia/eventi/338777.html",
        )
        self.assertIn("Via dei Mille", eventi[0]["indirizzoMappa"])
        self.assertEqual(eventi[0]["categoria"], "Musica & Concerti")

    def test_archivio_json_corrotto_blocca_la_rigenerazione(self):
        with tempfile.TemporaryDirectory() as cartella:
            percorso = os.path.join(cartella, "eventi.json")
            with open(percorso, "w", encoding="utf-8") as f:
                f.write('[{"titolo": "record valido"},')
            with self.assertRaises(RuntimeError):
                motore.carica_esistenti_protetti(percorso)

    def test_archivio_json_con_radice_non_lista_blocca_la_rigenerazione(self):
        with tempfile.TemporaryDirectory() as cartella:
            percorso = os.path.join(cartella, "eventi.json")
            with open(percorso, "w", encoding="utf-8") as f:
                json.dump({"eventi": []}, f)
            with self.assertRaises(RuntimeError):
                motore.carica_esistenti_protetti(percorso)

    def test_fonte_non_riconosciuta_non_viene_confusa_con_un_dominio_valido(self):
        self.assertFalse(
            motore._fonte_appartiene_a_raccolta_automatica(
                "https://iltaccodibacco.it.evil.example/eventi/338777.html"
            )
        )


    def test_url_evento_jsonld_accetta_www_e_host_base_dello_stesso_sito(self):
        html = """
        <html><head>
        <script type="application/ld+json">
        {
          "@context": "https://schema.org",
          "@type": "Event",
          "name": "Concerto sinfonico a Cerignola",
          "startDate": "2026-12-06",
          "url": "https://iltaccodibacco.it/puglia/eventi/338778.html",
          "description": "Concerto sinfonico con orchestra al Teatro Mercadante di Cerignola.",
          "location": {
            "name": "Teatro Mercadante",
            "address": {"addressLocality": "Cerignola"}
          }
        }
        </script>
        </head><body></body></html>
        """
        eventi = motore.analizza_pagina_evento(
            html,
            "https://www.iltaccodibacco.it/cerignola/",
            citta_default="Cerignola",
            fonte_curata_eventi=True,
        )
        self.assertEqual(
            eventi[0]["fonteUrl"],
            "https://iltaccodibacco.it/puglia/eventi/338778.html",
        )

    def test_record_di_tipo_non_gestito_viene_conservato_nell_archivio(self):
        altro_contenuto = {
            "tipoContenuto": "luogo",
            "titolo": "Luogo da visitare aggiunto manualmente",
            "citta": "Cerignola",
        }
        with tempfile.TemporaryDirectory() as cartella:
            percorso = os.path.join(cartella, "eventi.json")
            with open(percorso, "w", encoding="utf-8") as f:
                json.dump([altro_contenuto], f)
            manuali, automatici, scaduti = motore.carica_esistenti_protetti(percorso)
        self.assertEqual(manuali, [altro_contenuto])
        self.assertEqual(automatici, [])
        self.assertEqual(scaduti, 0)


class FontiUfficialiEIndirizziRegressionTests(unittest.TestCase):
    def test_fonte_teatro_usa_la_homepage_ufficiale_con_schede_evento(self):
        fonte = next(
            x for x in motore.FONTI_PORTALI
            if x["nome"] == "Teatro Mercadante Cerignola"
        )
        self.assertEqual(fonte["url"], "https://www.teatromercadantecerignola.it/")
        self.assertEqual(fonte["prefisso_schede"], "/evento/")

    def test_host_di_fonte_generica_non_accetta_dominio_simile_malevolo(self):
        self.assertFalse(motore._host_appartiene(
            "https://teatromercadantecerignola.it.evil.example/evento/falso",
            "teatromercadantecerignola.it",
        ))
        self.assertTrue(motore._host_appartiene(
            "https://www.teatromercadantecerignola.it/evento/vero",
            "teatromercadantecerignola.it",
        ))

    def test_estrazione_sede_ufficiale_mercadante_senza_etichetta_luogo(self):
        html = """
        <html><body><main>
          <h1>BREAKING BRECHT – Lo strano caso di Bertolt Brecht</h1>
          <p>domenica 06 Dicembre 2026</p>
          <p>ore 21:00</p>
          <p>Teatro Comunale Saverio Mercadante</p>
          <p>piazza G. Matteotti, 1</p>
          <p>Cerignola FG</p>
          <p>Spettacolo teatrale di prosa con Veronica Pivetti e Manuela Mandracchia.</p>
        </main></body></html>
        """
        eventi = motore.analizza_pagina_evento(
            html,
            "https://www.teatromercadantecerignola.it/evento/breaking-brecht/",
            citta_default="Cerignola",
            fonte_curata_eventi=True,
        )
        self.assertEqual(len(eventi), 1)
        self.assertEqual(eventi[0]["luogo"], "Teatro Comunale Saverio Mercadante")
        self.assertEqual(
            eventi[0]["indirizzoMappa"],
            "Teatro Comunale Saverio Mercadante, Piazza G. Matteotti, 1, Cerignola",
        )
        self.assertEqual(eventi[0]["dataInizio"], "2026-12-06")

    def test_indirizzo_aggregatore_rimuove_citta_ripetuta_e_prefisso(self):
        risultato = motore.normalizza_indirizzo_mappa(
            "Foggia, Teatro Umberto Giordano, Piazza Cesare Battisti, Foggia (FG), Foggia, Puglia",
            "Teatro Umberto Giordano",
            "Foggia",
        )
        self.assertEqual(
            risultato,
            "Teatro Umberto Giordano, Piazza Cesare Battisti, Foggia (FG), Puglia",
        )
