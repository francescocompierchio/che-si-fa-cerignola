import threading
import unittest
from unittest.mock import patch, MagicMock
import aggiorna_eventi as motore


class RaccoltaParallelaTests(unittest.TestCase):
    def setUp(self):
        motore.STATISTICHE_FONTI.clear()

    def test_parallelismo_reale_ordine_e_isolamento_sessioni(self):
        barriera = threading.Barrier(2, timeout=5)
        attivi = set()
        lock = threading.Lock()
        sessioni = {}
        def fonte(nome, host):
            return {"nome": nome, "url": "https://" + host + "/eventi"}
        def raccogli(session, f):
            nome = f["nome"]
            host = f["url"].split("/")[2].removeprefix("www.")
            with lock:
                self.assertNotIn(host, attivi)
                attivi.add(host)
                sessioni[nome] = session
            if nome in ("a1", "b1"):
                barriera.wait()
            with lock:
                attivi.remove(host)
            return [nome]
        compiti = [
            (raccogli, fonte("a1", "example.org")),
            (raccogli, fonte("b1", "example.net")),
            (raccogli, fonte("a2", "www.example.org")),
        ]
        with patch.object(motore, "crea_session_raccolta", side_effect=lambda: MagicMock()):
            risultati = motore.raccogli_fonti_parallele(compiti, max_worker=2)
        self.assertEqual(risultati, ["a1", "b1", "a2"])
        self.assertIs(sessioni["a1"], sessioni["a2"])
        self.assertIsNot(sessioni["a1"], sessioni["b1"])
        self.assertIn("durataSecondi", motore.STATISTICHE_FONTI["a2"])

    def test_errore_fonte_non_interrompe_altre_fonti(self):
        def raccogli(session, fonte):
            if fonte["nome"] == "errore":
                raise RuntimeError("errore simulato")
            return [fonte["nome"]]
        compiti = [
            (raccogli, {"nome":"errore", "url":"https://example.org/a"}),
            (raccogli, {"nome":"successo", "url":"https://example.org/b"}),
        ]
        with patch.object(motore, "crea_session_raccolta", side_effect=lambda: MagicMock()):
            self.assertEqual(motore.raccogli_fonti_parallele(compiti), ["successo"])
        self.assertEqual(motore.STATISTICHE_FONTI["errore"]["stato"], "errore")

    def test_archivio_conservato_e_nuovi_distinti_da_ritrovati(self):
        vecchio = {"titolo":"Esistente", "dataInizio":"2030-01-01", "citta":"Cerignola", "categoria":"Altro"}
        nuovo = {**vecchio, "titolo":"Nuovo"}
        conservato = {**vecchio, "titolo":"Conservato"}
        scritture = {}
        with patch.object(motore, "carica_esistenti_protetti", return_value=([], [vecchio, conservato], 0)), patch.object(motore, "raccogli_fonti_parallele", return_value=[vecchio, nuovo]), patch.object(motore, "sono_duplicati", side_effect=lambda a,b:a["titolo"]==b["titolo"]), patch.object(motore, "_scrivi_json_atomico", side_effect=lambda p,d:scritture.update({p:d})):
            motore.esegui_aggiornamento()
        self.assertEqual(len(scritture["eventi.json"]), 3)
        self.assertEqual(scritture["report_copertura.json"]["nuoviAggiunti"], 1)
        self.assertEqual(scritture["report_copertura.json"]["automaticiRitrovati"], 1)
