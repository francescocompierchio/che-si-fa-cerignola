import unittest
from aggiorna_eventi import sono_duplicati

class TestDuplicatiSede(unittest.TestCase):
    def test_titolo_breve_stessa_sede(self):
        a = dict(citta="Cerignola", titolo="Cerignola | La Mandragola - Massimo Venturiello", luogo="Teatro Mercadante", dataInizio="2027-02-23", dataFine="2027-02-23")
        b = dict(a, titolo="LA MANDRAGOLA", luogo="Teatro Comunale S. Mercadante")
        self.assertTrue(sono_duplicati(a,b))
        self.assertFalse(sono_duplicati(a,dict(b,dataInizio="2027-02-24",dataFine="2027-02-24")))
