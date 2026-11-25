import unittest
from urllib.parse import parse_qs, urlparse

import aggiorna_eventi as a


class TestRegistroCerignola(unittest.TestCase):
    def test_registro_e_query(self):
        registro = a.registro_cerignola()
        self.assertGreaterEqual(len(registro), 50)
        fonti = a.fonti_registro_cerignola(registro)
        self.assertGreaterEqual(len(fonti), 4)
        query = " ".join(parse_qs(urlparse(f["url"]).query)["q"][0] for f in fonti)
        for r in registro:
            for alias in r["alias"]:
                self.assertIn(alias, query)
        for fonte in fonti:
            q = parse_qs(urlparse(fonte["url"]).query)["q"][0]
            self.assertIn("Cerignola", q)
            self.assertIn("when:30d", q)
            self.assertTrue(fonte["solo_cerignola"])
            self.assertLessEqual(fonte["max_schede_rss"], 4)
        self.assertIn("NONZAI", parse_qs(urlparse(fonti[0]["url"]).query)["q"][0])

    def test_calendario_solo_host_e_percorso_supportati(self):
        fonti = a.calendari_registro_cerignola()
        self.assertEqual(len(fonti), 1)
        self.assertIn("safara", fonti[0]["url"])
        self.assertTrue(fonti[0]["solo_cerignola"])
        self.assertEqual(a.calendari_registro_cerignola([
            {"nome": "falso", "calendario": "https://iltaccodibacco.it.example.org/cerignola/safara"},
            {"nome": "home", "calendario": "https://iltaccodibacco.it/cerignola/"},
        ]), [])

    def test_giorno_settimana(self):
        self.assertFalse(a.giorno_settimana_compatibile("Venerdì 7 febbraio inaugurazione del parco", "2027-02-07"))
        self.assertTrue(a.giorno_settimana_compatibile("Venerdì 7 febbraio inaugurazione del parco", "2025-02-07"))
        self.assertTrue(a.giorno_settimana_compatibile("Natale in Piazza", "2026-12-01"))

    def test_registro_vuoto(self):
        self.assertEqual(a.fonti_registro_cerignola([]), [])
        self.assertEqual(a.calendari_registro_cerignola([]), [])


if __name__ == "__main__":
    unittest.main()
