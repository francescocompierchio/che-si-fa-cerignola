# Motore eventi autonomo

## Stato al 26 novembre 2026

- Analisi iniziale completata sul commit `377e14f` e sul run [45902685298](https://github.com/francescocompierchio/che-si-fa-cerignola/actions/runs/45902685298).
- Baseline del run: 96 record in archivio, 109 eventi nell'unione statica visibile, 25 a Cerignola, 2 serate editoriali a Cerignola, 0 novità, 54 locandine in archivio, 171,51 secondi. Tra 420 voci diagnostiche, 218 risultavano OK e 194 in pausa. Apify ha riportato secret assente. La pagina pubblica mostrava 109 eventi e 25 con il filtro Cerignola.
- Collaudo iniziale: 107 test Python alla radice, 102 nella suite `tests`, controllo integrità SEO superato.
- Il workflow configura esecuzioni semiorarie. Monitorato il ritardo effettivo delle ultime esecuzioni pianificate. Il backend ha già radar tematici, verifica date, OCR, Telegram e feedback da risultati verificati.
- In corso: salvaguardia dell'archivio, memoria recuperabile, fonti e territorio, metriche, collaudo CI e pubblicazione.
- Da verificare in produzione: disponibilità del secret Apify, risultati reali delle nuove ricerche, orari di esecuzione e versione pubblica dopo il deploy.
