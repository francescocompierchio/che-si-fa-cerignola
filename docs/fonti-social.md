# Segnalazioni e fonti social

## App pubblica

Nel menu **Pubblica un evento**, **Segnala un post o una Storia** apre la bozza per un annuncio pubblico. Gli utenti possono incollare il link originale di Instagram, Facebook o Telegram e compilare i campi dal testo o da una foto. Il modulo richiede la conferma prima dell'invio al pannello admin esistente. L’admin può aprire il link originale dalla segnalazione in attesa.

La PWA installata su Android può ricevere una condivisione dai dispositivi compatibili. La foto rimane in una bozza sul dispositivo e viene usata per l’estrazione locale del testo. La foto può essere allegata con il pulsante WhatsApp già presente, con il permesso di chi la pubblica. Su iPhone o con l’APK esistente si accede allo stesso modulo dalla pagina pubblica.

## Instagram e Facebook via Meta

GitHub Actions esegue un connettore opzionale per Instagram Business Discovery e per i post delle pagine Facebook autorizzate. Il connettore usa solo Meta Graph API. Le parole, data, sede e comune della didascalia passano dai filtri esistenti. Legge fino a due profili Instagram e due pagine Facebook per ciclo. Una stessa fonte torna disponibile dopo quattro ore. Gli errori di autorizzazione o quota attivano una pausa anche per le altre fonti dello stesso canale.

Per attivare il connettore servono un’app Meta con i permessi pertinenti di lettura, una versione Graph supportata e credenziali già concesse. La configurazione usa la scheda Settings → Secrets and variables → Actions in GitHub.

| Canale | Variables | Secrets |
| --- | --- | --- |
| Instagram | `META_GRAPH_VERSION`, `META_IG_ACCOUNT_ID`, `META_IG_PROFILES` con gli handle separati da spazi | `META_IG_ACCESS_TOKEN` |
| Facebook | `META_GRAPH_VERSION`, `META_FB_PAGE_IDS` con gli ID delle pagine autorizzate separati da spazi | `META_FB_ACCESS_TOKEN` |

Il rapporto `meta-rapporto.json` contiene stato, esiti HTTP aggregati e conteggio dei candidati. Gli account personali e le Stories dei profili terzi si gestiscono attraverso le segnalazioni volontarie con fonte pubblica.

## Telegram

I canali aderenti possono inviare il comando `/evento_csf` seguito da una descrizione a righe nella didascalia del post. I canali, il consenso alla pubblicazione e le regole sull’URL diretto della locandina seguono l’[integrazione Telegram](telegram.md). Il motore acquisisce il testo, la fonte e l’eventuale link alla locandina.
