import unittest
from datetime import datetime,timezone,timedelta
from guardiano import decisione

class GuardianoTest(unittest.TestCase):
    def setUp(self):
        self.now=datetime(2026,11,25,12,tzinfo=timezone.utc)
    def run_data(self,minutes,conclusion="success",status="completed"):
        t=(self.now-timedelta(minutes=minutes)).isoformat()
        return {"created_at":t,"updated_at":t,"conclusion":conclusion,"status":status}
    def test_recupero(self):
        self.assertEqual(decisione([self.run_data(100)],self.now),"recupera")
    def test_recente(self):
        self.assertEqual(decisione([self.run_data(89)],self.now),"raccolta_recente")
    def test_attivo(self):
        self.assertEqual(decisione([self.run_data(100),self.run_data(120,status="in_progress")],self.now),"raccolta_attiva")
    def test_errore_non_riprova(self):
        self.assertEqual(decisione([self.run_data(100,"failure")],self.now),"errore_da_diagnosticare")
    def test_storico_assente(self):
        self.assertEqual(decisione([],self.now),"storico_insufficiente")
    def test_stato_incerto(self):
        self.assertEqual(decisione([self.run_data(100,status="unknown")],self.now),"stato_incerto")

if __name__=="__main__":
    unittest.main()
