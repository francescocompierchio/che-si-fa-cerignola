import io
import sys
import unittest
import warnings
from types import SimpleNamespace
from unittest.mock import Mock, patch

import aggiorna_eventi as crawler


class QualitaEventiTests(unittest.TestCase):
    def test_stato_evento_annullato_non_ripescato(self):
        url = "https://example.org/evento/serata"
        data = (crawler.oggi_dt() + crawler.timedelta(days=3)).strftime("%Y-%m-%d")
        ev = {"@type": "Event", "name": "Serata DJ set", "startDate": data, "eventStatus": "https://schema.org/EventCancelled", "url": url}
        import json
        html = '<script type="application/ld+json">' + json.dumps(ev) + '</script><h1>Serata DJ set</h1><p>Luogo: Piazza Matteotti, Cerignola</p>'
        try:
            crawler.STATI_EVENTI_NEGATIVI.clear()
            self.assertEqual(crawler.analizza_pagina_evento(html, url, "Cerignola", True), [])
            self.assertTrue(crawler.evento_non_attivo({"fonteUrl": url, "dataInizio": data}))
            self.assertFalse(crawler.evento_non_attivo({"fonteUrl": url, "dataInizio": "2099-01-01"}))
            self.assertFalse(crawler.evento_non_attivo({"fonteUrl": "https://example.org/evento/altro", "dataInizio": data}))
        finally:
            crawler.STATI_EVENTI_NEGATIVI.clear()

    def test_stato_riprogrammato_solo_vecchia_data(self):
        import json
        url = "https://example.org/evento/serata"
        ev = {"@type": "Event", "name": "Serata", "startDate": "2030-03-01", "previousStartDate": "2030-02-01", "eventStatus": "https://schema.org/EventRescheduled", "url": url}
        try:
            crawler.STATI_EVENTI_NEGATIVI.clear()
            crawler.registra_stati_negativi('<script type="application/ld+json">' + json.dumps(ev) + '</script>', url)
            self.assertTrue(crawler.evento_non_attivo({"fonteUrl": url, "dataInizio": "2030-02-01"}))
            self.assertFalse(crawler.evento_non_attivo({"fonteUrl": url, "dataInizio": "2030-03-01"}))
        finally:
            crawler.STATI_EVENTI_NEGATIVI.clear()

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

    def test_elenco_puglia_culture_usa_card_evento_come_fallback(self):
        html = """
        <html><body><main>
          <div class="event-card">
            <a href="/evento/breaking-brecht-3/">BREAKING BRECHT</a>
            <p>domenica 06 dicembre 2026</p>
            <p>Teatro: Teatro Comunale S. Mercadante - Cerignola</p>
            <p>Prezzo: a partire da € 12</p>
          </div>
          <div class="event-card">
            <a href="/evento/mio-sempre-mio-andrea/">MIO, SEMPRE, MIO ANDREA</a>
            <p>venerdì 29 gennaio 2027</p>
            <p>Teatro: Teatro Comunale S. Mercadante - Cerignola</p>
          </div>
          <div class="event-card">
            <a href="/evento/spettacolo-altro-comune/">SPETTACOLO ALTRO COMUNE</a>
            <p>sabato 12 dicembre 2026</p>
            <p>Teatro: Teatro Comunale - Foggia</p>
          </div>
        </main></body></html>
        """
        soup = crawler.BeautifulSoup(html, "html.parser")
        eventi = crawler.estrai_eventi_puglia_da_elenco(
            soup,
            "https://www.pugliaculture.it/rassegna/cerignola-stagione-teatrale-2026-27-un-teatro-per-tutti/",
            "Cerignola",
        )
        self.assertEqual(len(eventi), 2)
        self.assertEqual(
            {evento["titolo"] for evento in eventi},
            {"BREAKING BRECHT", "MIO, SEMPRE, MIO ANDREA"},
        )
        self.assertTrue(all(evento["citta"] == "Cerignola" for evento in eventi))
        self.assertTrue(all(evento["luogo"] == "Teatro Comunale S. Mercadante" for evento in eventi))

    def test_puglia_culture_card_riconosce_sede_con_link_separati(self):
        html = """
        <html><body><main>
          <article class="event-card">
            <a href="/evento/breaking-brecht-3/">BREAKING BRECHT</a>
            <p>domenica 06 dicembre 2026</p>
            <p>Teatro:</p>
            <p><a href="/luogo/teatro-mercadante/">Teatro Comunale S. Mercadante</a> -
               <a href="/luogo/cerignola/">Cerignola</a></p>
          </article>
        </main></body></html>
        """
        soup = crawler.BeautifulSoup(html, "html.parser")
        eventi = crawler.estrai_eventi_puglia_da_elenco(
            soup,
            "https://www.pugliaculture.it/rassegna/cerignola-stagione-teatrale-2026-27-un-teatro-per-tutti/",
            "Cerignola",
        )
        self.assertEqual(len(eventi), 1)
        self.assertEqual(eventi[0]["titolo"], "BREAKING BRECHT")
        self.assertEqual(eventi[0]["luogo"], "Teatro Comunale S. Mercadante")
        self.assertEqual(eventi[0]["dataInizio"], "2026-12-06")

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
        self.assertGreaterEqual(len(crawler.FONTI_SOCIAL_RSS), 5)
        self.assertTrue(any("instagram.com" in f["url"] for f in crawler.FONTI_SOCIAL_RSS))
        self.assertTrue(any("facebook.com" in f["url"] for f in crawler.FONTI_SOCIAL_RSS))
        self.assertTrue(any("birdwatching" in f["url"] and "cicloturismo" in f["url"] for f in crawler.FONTI_SOCIAL_RSS))

    def test_catalogo_esperienze_weekend(self):
        import json
        from pathlib import Path
        catalogo = json.loads((Path(__file__).parent / "esperienze.json").read_text(encoding="utf-8"))
        self.assertGreaterEqual(len(catalogo), 20)
        self.assertTrue(all(x.get("tipoContenuto") == "esperienza" for x in catalogo))
        self.assertTrue(all(x.get("titolo") and x.get("citta") and x.get("indirizzoMappa") for x in catalogo))
        self.assertTrue(any("bosco" in x.get("titolo", "").lower() for x in catalogo))
        self.assertTrue(any("famiglie" in x.get("adattoA", "").lower() for x in catalogo))
        titoli = {x["titolo"] for x in catalogo}
        self.assertTrue(any("Faeto" in titolo for titolo in titoli))
        self.assertTrue(any("Foresta Umbra" in titolo for titolo in titoli))
        self.assertTrue(any("Oasi Lago Salso" in titolo for titolo in titoli))
        self.assertTrue(all(x.get("fonteUrl") for x in catalogo if any(k in x["titolo"] for k in ("Ripa Alta", "Faeto", "Foresta Umbra", "Oasi Lago Salso"))))

    def test_ocr_gestisce_immagini_palette_con_trasparenza(self):
        try:
            from PIL import Image
        except ImportError:
            self.skipTest("Pillow non installato in questo workflow")

        immagine = Image.new("P", (40, 40), 0)
        immagine.putpalette([0, 0, 0, 255, 255, 255] + [0, 0, 0] * 254)
        immagine.info["transparency"] = 0
        buffer = io.BytesIO()
        immagine.save(buffer, format="PNG")

        risposta = SimpleNamespace(
            status_code=200,
            headers={"Content-Type": "image/png"},
            content=buffer.getvalue(),
        )
        session = Mock()
        session.get.return_value = risposta

        with patch.dict(sys.modules, {"pytesseract": SimpleNamespace(image_to_string=lambda *args, **kwargs: "Locandina evento Cerignola sabato 12 dicembre")}):
            with warnings.catch_warnings(record=True) as avvisi:
                warnings.simplefilter("always")
                testo = crawler.estrai_testo_locandine(
                    session,
                    '<html><head><meta property="og:image" content="https://example.test/locandina.png"></head></html>',
                    base_url="https://example.test/",
                )

        self.assertIn("Cerignola", testo)
        self.assertFalse(any("Palette images with Transparency" in str(w.message) for w in avvisi))

    def test_ocr_rispetta_budget_timeout_e_non_blocca(self):
        try:
            from PIL import Image
        except ImportError:
            self.skipTest("Pillow non installato")
        buffer = io.BytesIO()
        Image.new("RGB", (50, 50)).save(buffer, format="PNG")
        session = Mock()
        session._csf_ocr_budget = {"rimanenti": 1}
        session.get.return_value = SimpleNamespace(status_code=200, headers={"Content-Type":"image/png"}, content=buffer.getvalue())
        ocr = Mock(side_effect=RuntimeError("timeout simulato"))
        html = '<main><img src="https://example.test/logo.png"><img src="https://example.test/poster.png"><img src="https://example.test/secondo.png"></main>'
        with patch.dict(sys.modules, {"pytesseract": SimpleNamespace(image_to_string=ocr)}):
            self.assertEqual(crawler.estrai_testo_locandine(session, html), "")
            self.assertEqual(crawler.estrai_testo_locandine(session, html), "")
        self.assertEqual(session.get.call_count, 1)
        self.assertEqual(session.get.call_args.args[0], "https://example.test/poster.png")
        self.assertEqual(ocr.call_args.kwargs["timeout"], crawler.OCR_TIMEOUT_SECONDI)

    def test_ocr_locandine_senza_immagini_non_blocca(self):
        self.assertEqual(crawler.estrai_testo_locandine(None), "")

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
