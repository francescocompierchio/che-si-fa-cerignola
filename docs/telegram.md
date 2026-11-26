# Telegram – segnalazioni autorizzate

Non si esegue scraping di Telegram, non si leggono cronologie e non si usano messaggi per addestramento o analisi AI. L'integrazione è un bot per l'invio intenzionale di annunci destinati alla pubblicazione su Che Si Fa Cerignola. I canali aderenti devono autorizzare il bot e possedere i diritti sui dati/locandine inviati. Non aggiungere canali generici senza accordo. Riferimenti: https://core.telegram.org/bots/api e https://telegram.org/tos/content-licensing.

## Attivazione
1. Il proprietario crea un bot con @BotFather (/newbot), conserva il token esclusivamente come GitHub Actions secret TELEGRAM_EVENT_BOT_TOKEN. Non condividerlo in chat e non inserirlo nel codice.
2. Gli organizzatori aderenti aggiungono il bot a un canale pubblico dedicato alle segnalazioni volontarie, con i minimi permessi necessari per ricevere channel_post. Non concedere permessi di cancellazione o pubblicazione.
3. Il proprietario configura il secret TELEGRAM_EVENT_CHANNELS come JSON: {"-1001234567890":{"username":"nome_canale","comune":"Cerignola","poster_hosts":["sito-ufficiale.example"]}}. Gli ID sono esempi, non canali reali. Il comune deve essere uno supportato dall'app; il nome deve corrispondere al canale. Nessuna autorizzazione automatica da messaggi.
4. Pubblicare un annuncio nel formato seguente (esempio dimostrativo), solo se autorizzati:
```
/evento_csf {"titolo":"Dinner Show","dataInizio":"2026-12-05","luogo":"Nome locale","indirizzoMappa":"Via del locale, Cerignola","descrizione":"Cena spettacolo con DJ set.","orario":"21:00","consenso":"Autorizzo la pubblicazione su Che Si Fa Cerignola"}
```
Facoltativi: dataFine, costo, locandinaUrl (URL HTTPS diretto su un dominio autorizzato dell'organizzatore, senza token o query). Nessun allegato Telegram scaricato. Fonte ufficiale: link al singolo annuncio pubblico. Per correggere, modificare il post mantenendo il formato. Per annullare, modificare il post in /annulla_csf oppure inviare /annulla_csf ID_DEL_POST dallo stesso canale. Non usare la semplice cancellazione del post come notifica (Bot API non consegna tale evento).
5. Il workflow esistente ogni 30 minuti riceve gli annunci, applica i filtri di area, data, pertinenza e duplicati, pubblica solo gli eventi validi, e registra i totali nel report. Lo stato di ricezione è salvato nello stesso commit di eventi.json per non perdere aggiornamenti in caso di push concorrente. Telegram conserva gli aggiornamenti non ricevuti al massimo 24 ore; il recupero storico non è previsto.

Senza token e almeno un canale autorizzato, la funzione resta inattiva senza interferire con le altre fonti. I log non contengono token o messaggi originali. Il bot non invia messaggi, non gestisce utenti, non accede a Firebase e non modifica grafica o permessi. La condivisione Telegram dell'app è già disponibile nel menu Condividi.
