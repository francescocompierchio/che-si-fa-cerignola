# Segnalazioni e fonti social

## App pubblica

Nel menu **Pubblica un evento**, **Segnala un post o una Storia** apre la bozza per un annuncio pubblico. Gli utenti possono incollare il link originale di Instagram, Facebook o Telegram e compilare i campi dal testo o da una foto. Il modulo richiede la conferma prima dell'invio al pannello admin esistente. L’admin può aprire il link originale dalla segnalazione in attesa.

La PWA installata su Android può ricevere una condivisione dai dispositivi compatibili. La foto rimane in una bozza sul dispositivo e viene usata per l’estrazione locale del testo. La foto può essere allegata con il pulsante WhatsApp già presente, con il permesso di chi la pubblica. Su iPhone o con l’APK esistente si accede allo stesso modulo dalla pagina pubblica.

## Instagram e Facebook via Meta

GitHub Actions esegue un connettore opzionale per Instagram Business Discovery e per i post delle pagine Facebook autorizzate. Il connettore usa solo Meta Graph API. Le parole, data, sede e comune della didascalia passano dai filtri esistenti. Legge fino a due profili Instagram e due pagine Facebook per ciclo. Una stessa fonte torna disponibile dopo quattro ore. Gli errori di autorizzazione o quota attivano una pausa anche per le altre fonti dello stesso canale.

Dal [pannello Meta for Developers](https://developers.facebook.com/apps/), configura un’app con Facebook Login per le aziende e i permessi di lettura necessari per la risorsa. Per Instagram serve l’ID numerico del proprio account professionale autorizzato e collegato a una pagina Facebook. I profili da consultare devono soddisfare i requisiti di Business Discovery. Per Facebook usa una credenziale effettivamente autorizzata a consultare le pagine elencate. Consulta le [versioni Graph supportate](https://developers.facebook.com/docs/graph-api/changelog/versions/) per il valore di `META_GRAPH_VERSION`, ad esempio `v25.0`.

Inserisci gli ID e gli handle in **Variables** e i token in **Secrets**, nella pagina [Actions del repository](https://github.com/francescocompierchio/che-si-fa-cerignola/settings/secrets/actions). Puoi attivare un canale per volta.

| Canale | Variables | Secrets |
| --- | --- | --- |
| Instagram | `META_GRAPH_VERSION`, `META_IG_ACCOUNT_ID`, `META_IG_PROFILES` con gli handle separati da spazi o virgole | `META_IG_ACCESS_TOKEN` |
| Facebook | `META_GRAPH_VERSION`, `META_FB_PAGE_IDS` con gli ID delle pagine autorizzate separati da spazi o virgole | `META_FB_ACCESS_TOKEN` |

Nel [workflow **Aggiorna Eventi Cerignola**](https://github.com/francescocompierchio/che-si-fa-cerignola/actions/workflows/aggiorna-eventi.yml) apri l’ultima esecuzione e scarica l’artifact `copertura-eventi` per leggere `meta-rapporto.json`. I nomi delle impostazioni mancanti o non valide sono indicati separatamente per Instagram e Facebook, senza riportarne i valori. Un esito `200` indica una risposta valida, anche se il filtro non ha trovato appuntamenti. Gli esiti `401`, `403` e `429` distinguono token respinto, accesso negato e limite API. Il rapporto include anche il conteggio dei candidati. Per gli account personali e le Stories dei profili terzi è disponibile il modulo di segnalazione volontaria.

## Telegram

I canali aderenti possono inviare il comando `/evento_csf` seguito da una descrizione a righe nella didascalia del post. I canali, il consenso alla pubblicazione e le regole sull’URL diretto della locandina seguono l’[integrazione Telegram](telegram.md). Il motore acquisisce il testo, la fonte e l’eventuale link alla locandina.
