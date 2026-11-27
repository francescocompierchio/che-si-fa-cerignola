import unittest
from aggiorna_eventi import integra_dettagli_serata, sono_duplicati

class TestDuplicatiSede(unittest.TestCase):
    def test_titolo_breve_stessa_sede(self):
        a = dict(citta="Cerignola", titolo="Cerignola | La Mandragola - Massimo Venturiello", luogo="Teatro Mercadante", dataInizio="2027-02-23", dataFine="2027-02-23")
        b = dict(a, titolo="LA MANDRAGOLA", luogo="Teatro Comunale S. Mercadante")
        self.assertTrue(sono_duplicati(a,b))
        self.assertFalse(sono_duplicati(a,dict(b,dataInizio="2027-02-24",dataFine="2027-02-24")))

    def test_around_us_alias_documentati_della_sede(self):
        nightoutz = dict(citta="Bisceglie", categoria="Locali & Serate", titolo="Around Us",
                        luogo="Divine Club", dataInizio="2026-11-28", dataFine="2026-11-28")
        editore = dict(nightoutz, luogo="Divinae Follie",
                       titolo="Bisceglie | Around Us con Salomé Le Chat, Skizzo e Innocent Soul")
        self.assertTrue(sono_duplicati(nightoutz, editore))
        self.assertFalse(sono_duplicati(nightoutz, dict(editore, luogo="Idol Club")))
        self.assertFalse(sono_duplicati(nightoutz, dict(editore, dataInizio="2026-11-29", dataFine="2026-11-29")))

    def test_around_us_conserva_orario_e_locandina(self):
        nightoutz = dict(citta="Bisceglie", categoria="Locali & Serate", titolo="Around Us",
                        luogo="Divine Club", dataInizio="2026-11-28", dataFine="2026-11-28",
                        dataTesto="Sab 28 Nov 2026 · Ore 23:00")
        editore = dict(nightoutz, luogo="Divinae Follie", dataTesto="Sab 28 Nov 2026",
                       locandinaUrl="https://editore.example/locandina.jpg")
        unito = integra_dettagli_serata(editore, nightoutz)
        self.assertEqual(unito["locandinaUrl"], editore["locandinaUrl"])
        self.assertIn("23:00", unito["dataTesto"])
        self.assertEqual(integra_dettagli_serata(nightoutz, editore)["locandinaUrl"], editore["locandinaUrl"])
        self.assertEqual(integra_dettagli_serata(editore, dict(nightoutz, luogo="Idol Club")), editore)
