import unittest

import aggiorna_eventi as crawler


class QualitaEventiTests(unittest.TestCase):
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
        self.assertEqual(len(crawler.FONTI_SOCIAL_RSS), 3)
        self.assertTrue(any("instagram.com" in f["url"] for f in crawler.FONTI_SOCIAL_RSS))
        self.assertTrue(any("facebook.com" in f["url"] for f in crawler.FONTI_SOCIAL_RSS))

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
