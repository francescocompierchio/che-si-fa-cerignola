import unittest
from datetime import datetime,timezone,timedelta
from guardiano import decisione, allarmi_raccolta, SOGLIA_COMMUNITY, verifica_community, COMMUNITY
from unittest.mock import patch

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
    def test_timeout_programmato(self):
        self.assertEqual(decisione([{**self.run_data(100,"timed_out"),"event":"schedule"}],self.now),"recupera")
        self.assertEqual(decisione([{**self.run_data(100,"timed_out"),"event":"workflow_dispatch"}],self.now),"errore_da_diagnosticare")
    def test_errore_recente(self):
        self.assertEqual(decisione([self.run_data(1,"failure")],self.now),"errore_da_diagnosticare")
    def test_allarmi(self):
        self.assertTrue(allarmi_raccolta([self.run_data(5,"failure"),self.run_data(20,"failure")],self.now))
        self.assertTrue(allarmi_raccolta([self.run_data(190)],self.now))
        self.assertFalse(allarmi_raccolta([self.run_data(5),self.run_data(20,"failure")],self.now))
        self.assertFalse(allarmi_raccolta([self.run_data(5,"failure"),self.run_data(20)],self.now))
    def test_soglia_community(self):
        self.assertEqual(decisione([self.run_data(26)],self.now,SOGLIA_COMMUNITY),"recupera")
        self.assertEqual(decisione([self.run_data(24)],self.now,SOGLIA_COMMUNITY),"raccolta_recente")
        self.assertEqual(decisione([self.run_data(26,"failure")],self.now,SOGLIA_COMMUNITY),"errore_da_diagnosticare")
    def test_community_disabilitata(self):
        note=[];allarmi=[]
        with patch("guardiano.api",return_value={"state":"disabled_manually"}) as api:
            verifica_community(self.now,note,allarmi)
        api.assert_called_once_with(COMMUNITY)
        self.assertTrue(allarmi)
    def test_community_fallita_non_rilanciata(self):
        note=[];allarmi=[]
        runs=[{**self.run_data(35,"failure"),"event":"schedule"}]
        with patch("guardiano.api",side_effect=[{"state":"active"},{"workflow_runs":runs}]) as api:
            verifica_community(self.now,note,allarmi)
        self.assertEqual(api.call_count,2)
        self.assertTrue(allarmi)
    def test_storico_assente(self):
        self.assertEqual(decisione([],self.now),"storico_insufficiente")
    def test_stato_incerto(self):
        self.assertEqual(decisione([self.run_data(100,status="unknown")],self.now),"stato_incerto")

if __name__=="__main__":
    unittest.main()
