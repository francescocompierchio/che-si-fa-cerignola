# Telegram – segnalazioni autorizzate

Non si esegue scraping di Telegram, non si leggono cronologie e non si usano messaggi per addestramento o analisi AI. L'integrazione è un bot per l'invio intenzionale di annunci destinati alla pubblicazione su Che Si Fa Cerignola. I canali aderenti devono autorizzare il bot e possedere i diritti sui dati/locandine inviati. Non aggiungere canali generici senza accordo. Riferimenti: https://core.telegram.org/bots/api e https://telegram.org/tos/content-licensing.

## Attivazione
1. Il proprietario crea un bot con [@BotFather](https://t.me/BotFather) usando `/newbot` e salva il token in [GitHub Actions → Secrets](https://github.com/francescocompierchio/che-si-fa-cerignola/settings/secrets/actions) con il nome `TELEGRAM_EVENT_BOT_TOKEN`. Il token va inserito direttamente in GitHub.
2. Gli organizzatori aderenti aggiungono il bot a un canale pubblico dedicato alle segnalazioni volontarie, con i minimi permessi necessari per ricevere channel_post. Non concedere permessi di cancellazione o pubblicazione.
3. Il proprietario salva il secret `TELEGRAM_EVENT_CHANNELS`. Per il canale aderente, il metodo ufficiale [getChat](https://core.telegram.org/bots/api#getchat) accetta `@nome_canale` e restituisce l’ID numerico del canale. Il registro richiede quell’ID e lo username senza `@`. Usa `poster_hosts` solo per immagini che l’organizzatore ha autorizzato. Esempio con dati dimostrativi:
   ```json
   {"-1001234567890":{"username":"nome_canale","comune":"Cerignola","poster_hosts":[]}}
   ```
4. Pubblicare un annuncio nel formato seguente (esempio dimostrativo), solo se autorizzati:
```
/evento_csf {"titolo":"Dinner Show","dataInizio":"2026-12-05","luogo":"Nome locale","indirizzoMappa":"Via del locale, Cerignola","descrizione":"Cena spettacolo con DJ set.","orario":"21:00","consenso":"Autorizzo la pubblicazione su Che Si Fa Cerignola"}
```
Lo stesso annuncio può essere pubblicato come testo o scritto nella didascalia di una foto, con una riga per campo:
```
/evento_csf
Evento: Dinner Show
Data: 2026-12-05
Locale: Nome locale
Indirizzo: Via del locale, Cerignola
Orario: 21:00
Descrizione: Cena spettacolo con DJ set.
Autorizzo la pubblicazione su Che Si Fa Cerignola
```
Le righe facoltative sono `Al:`, `Ingresso:` e `Locandina:`. Il bot usa il testo della didascalia. Per pubblicare una locandina sulla scheda, indica il suo URL diretto nella riga `Locandina:`.

L’indirizzo deve terminare con una virgola e il comune autorizzato, ad esempio `Via Roma 1, Cerignola`. Facoltativi: dataFine, costo, locandinaUrl (URL HTTPS diretto su un dominio autorizzato dell'organizzatore, senza token o query). Nessun allegato Telegram scaricato. Fonte ufficiale: link al singolo annuncio pubblico. Per correggere, modificare il post mantenendo il formato. Per annullare, modificare il post in /annulla_csf oppure inviare /annulla_csf ID_DEL_POST dallo stesso canale. Non usare la semplice cancellazione del post come notifica (Bot API non consegna tale evento).
5. Il workflow esistente ogni 30 minuti riceve gli annunci, applica i filtri di area, data, pertinenza e duplicati, pubblica solo gli eventi validi, e registra i totali nel report. Lo stato di ricezione è salvato nello stesso commit di eventi.json per non perdere aggiornamenti in caso di push concorrente. Telegram conserva gli aggiornamenti non ricevuti al massimo 24 ore; il recupero storico non è previsto.

Nel [workflow di raccolta](https://github.com/francescocompierchio/che-si-fa-cerignola/actions/workflows/aggiorna-eventi.yml), `report_copertura.json` indica impostazioni mancanti o non valide, numero di canali configurati, aggiornamenti ricevuti e annunci accettati. `ok` con zero aggiornamenti indica che Telegram ha risposto. Per verificare la pubblicazione da un canale specifico serve un annuncio valido inviato da quel canale. Un `409` segnala un webhook attivo o un altro processo che interroga lo stesso bot.

Senza token e almeno un canale autorizzato, la funzione resta inattiva senza interferire con le altre fonti. I log non contengono token o messaggi originali. Il bot non invia messaggi, non gestisce utenti, non accede a Firebase e non modifica grafica o permessi. La condivisione Telegram dell'app è già disponibile nel menu Condividi.
