import json
import os
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch, Mock
import telegram_eventi as tg
import aggiorna_eventi as engine

class TelegramTests(unittest.TestCase):
    def setUp(self):
        self.today=date(2026,11,26)
        self.state={"version":1,"offset":0,"events":{}}
        self.channels={"-1001234567890":{"username":"csf_test_source","comune":"Cerignola","poster_hosts":["example.org"]}}
        self.item={"titolo":"Dinner Show – Hermes Club","dataInizio":"2026-12-05","luogo":"Hermes Club","indirizzoMappa":"Strada San Marco km 0.80, Cerignola","descrizione":"Cena spettacolo con musica dal vivo e DJ set.","orario":"21:00","consenso":tg.CONSENT,"locandinaUrl":"https://example.org/poster.webp"}
    def upd(self,uid=1,mid=12,text=None,cid=-1001234567890,edited=False):
        return {"update_id":uid,("edited_channel_post" if edited else "channel_post"):{"chat":{"id":cid,"type":"channel","username":"csf_test_source"},"message_id":mid,"text":text if text is not None else tg.PREFIX+json.dumps(self.item)}}
    def validate(self,raw):
        from datetime import datetime
        return engine.normalizza_e_valida_evento(raw,ref_dt=datetime(2026,11,26),fonte_curata_eventi=False)
    def test_ingresso_reale_parser(self):
        s,c=tg.process([self.upd()],self.state,self.channels,self.today,self.validate)
        self.assertEqual(c["accettati"],1)
        e=s["events"]["csf_test_source/12"]
        self.assertEqual(e["citta"],"Cerignola")
        self.assertEqual(e["categoria"],"Locali & Serate")
        self.assertEqual(e["fonteUrl"],"https://t.me/csf_test_source/12")
        self.assertTrue(e["telegramImportato"])
        self.assertEqual(s["offset"],2)
        self.assertNotIn("consenso",e)
        self.assertEqual(tg.process([self.upd()],s,self.channels,self.today,self.validate)[0],s)
        self.item["orario"]="22:00"
        edited,_=tg.process([self.upd(uid=2,edited=True)],s,self.channels,self.today,self.validate)
        self.assertIn("22:00",edited["events"]["csf_test_source/12"]["dataTesto"])
        canceled,c=tg.process([self.upd(uid=3,mid=13,text="/annulla_csf 12")],edited,self.channels,self.today,self.validate)
        self.assertEqual(c["annullati"],1)
        self.assertFalse(canceled["events"])
    def test_reject(self):
        for changed in [{"consenso":""},{"dataInizio":"2026-02-01"},{"dataInizio":"domani"},{"locandinaUrl":"https://api.telegram.org/botsecret/photo.jpg"},{"indirizzoMappa":"Via Roma, Milano"},{"titolo":"Cronaca: arrestato"}]:
            original=self.item.copy()
            self.item.update(changed)
            s,c=tg.process([self.upd()],self.state,self.channels,self.today,self.validate)
            self.assertFalse(s["events"],changed)
            self.item=original
        self.assertFalse(tg.process([self.upd(cid=-1009999999999)],self.state,self.channels,self.today,self.validate)[0]["events"])
        self.assertFalse(tg.process([self.upd(text="Notizia qualsiasi")],self.state,self.channels,self.today,self.validate)[0]["events"])
    def test_bot_non_configurato_o_errore(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/"state.json"
            session=Mock()
            with patch.dict(os.environ,{"TELEGRAM_EVENT_BOT_TOKEN":"","TELEGRAM_EVENT_CHANNELS":""}):
                _, report = tg.collect(self.today,self.validate,path,session)
                self.assertEqual(report["stato"],"non_configurato")
                self.assertEqual(report["impostazioniMancanti"],["TELEGRAM_EVENT_BOT_TOKEN","TELEGRAM_EVENT_CHANNELS"])
            session.post.assert_not_called()
            with patch.dict(os.environ,{"TELEGRAM_EVENT_BOT_TOKEN":"123:"+"a"*30,"TELEGRAM_EVENT_CHANNELS":json.dumps(self.channels)}):
                session.post.return_value.status_code=200
                session.post.return_value.json.return_value={"ok":True,"result":[self.upd()]}
                s,c=tg.collect(self.today,self.validate,path,session)
                self.assertEqual(c["accettati"],1)
                self.assertEqual(c["aggiornamentiRicevuti"],1)
                self.assertEqual(session.post.call_args.kwargs["json"]["allowed_updates"],["channel_post","edited_channel_post"])
                path.write_text(json.dumps(s),encoding="utf-8")
                session.post.return_value.status_code=403
                recovered, report = tg.collect(self.today,self.validate,path,session)
                self.assertEqual(recovered,s)
                self.assertEqual(report["motivo"],"accesso_negato")
                session.post.return_value.status_code=409
                self.assertEqual(tg.collect(self.today,self.validate,path,session)[1]["motivo"],"conflitto_webhook_o_altro_polling")
            with patch.dict(os.environ,{"TELEGRAM_EVENT_BOT_TOKEN":"123:"+"a"*30,"TELEGRAM_EVENT_CHANNELS":"json non pubblico"}):
                _, report = tg.collect(self.today,self.validate,path,session)
                self.assertEqual(report["impostazioniNonValide"],["TELEGRAM_EVENT_CHANNELS"])
                self.assertNotIn("json non pubblico", str(report))

    def test_didascalia_senza_json_e_solo_da_canale_aderente(self):
        text = "\n".join((
            "/evento_csf", "Evento: Dinner Show – Hermes Club", "Data: 2026-12-05",
            "Locale: Hermes Club", "Indirizzo: Strada San Marco km 0.80, Cerignola",
            "Orario: 21:00", "Descrizione: Cena spettacolo con DJ set.", tg.CONSENT,
        ))
        update = self.upd(text="")
        post = update["channel_post"]
        post["caption"] = text
        post["photo"] = [{"file_id": "riferimento-test"}]
        state, counts = tg.process([update], self.state, self.channels, self.today, self.validate)
        self.assertEqual(counts["accettati"], 1)
        self.assertNotIn("locandinaUrl", state["events"]["csf_test_source/12"])
        for bad in (text.replace(tg.CONSENT, ""), text.replace("Orario:", "Data:")):
            post["caption"] = bad
            self.assertFalse(tg.process([update], self.state, self.channels, self.today, self.validate)[0]["events"])
        post["caption"] = text
        post["forward_origin"] = {"type": "channel"}
        self.assertFalse(tg.process([update], self.state, self.channels, self.today, self.validate)[0]["events"])
