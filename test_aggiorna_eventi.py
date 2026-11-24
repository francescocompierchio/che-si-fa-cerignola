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
