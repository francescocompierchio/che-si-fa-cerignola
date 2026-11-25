import unittest
import tempfile
from pathlib import Path
import stato_raccolta as s

class StatoFontiTests(unittest.TestCase):
    def test_blocco_riprova_e_recupero(self):
        m={"fonti": {}}
        t=[(None, {"nome":"locale"})]
        m=s.aggiorna(m, {"locale":{"stato":"HTTP 429"}}, 1000)
        self.assertEqual(s.pianifica(t,m,1001)[0],t)
        m=s.aggiorna(m, {"locale":{"stato":"HTTP 429"}}, 2000)
        self.assertEqual(s.pianifica(t,m,2001)[1],["locale"])
        self.assertEqual(s.pianifica(t,m,2001,True)[0],t)
        self.assertEqual(s.pianifica(t,m,5600)[0],t)
        m=s.aggiorna(m, {"locale":{"stato":"ok","eventiEstratti":2}}, 5600)
        self.assertEqual(m["fonti"]["locale"]["blocchiConsecutivi"],0)
        self.assertEqual(s.pianifica(t,m,5601)[0],t)

    def test_vuoti_non_sospesi(self):
        m={"fonti":{}}
        for i in range(6):
            s.aggiorna(m,{"locale":{"stato":"ok","eventiEstratti":0}},i)
        self.assertEqual(s.riepilogo(m,[])["fontiDaRivedere"],["locale"])
        self.assertEqual(s.pianifica([(None,{"nome":"locale"})],m,7)[1],[])

    def test_adattiva(self):
        m={"fonti":{}}
        for i in range(12):
            s.aggiorna(m,{"secondaria":{"stato":"ok","eventiEstratti":0},"locale":{"stato":"ok","eventiEstratti":0,"prioritaria":True}},i)
        task=[(None,{"nome":"secondaria"}),(None,{"nome":"locale","prioritaria":True})]
        self.assertEqual(s.pianifica(task,m,12)[1],["secondaria"])
        self.assertEqual(s.pianifica(task,m,12)[0],[task[1]])
        self.assertEqual(len(s.pianifica(task,m,12,True)[0]),2)

    def test_cache_invalida(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"fonti.json"
            p.write_text("non-json")
            self.assertEqual(s.carica(p),{"fonti":{}})

    def test_priorita_temporale_non_supera_pause(self):
        import apprendimento as a
        now=1760000000
        m={"fonti":{"a":{"prossimoTentativo":now+10,"blocchiConsecutivi":2,"fasce":{a.fascia(now):{"prove":20,"novita":2}}}}}
        tasks=[(None,{"nome":"a","prioritaria":True}),(None,{"nome":"b","prioritaria":True})]
        self.assertEqual(s.pianifica(tasks,m,now)[1],["a"])
