# Che Si Fa Community – pilot non attivo

## Decisioni di sicurezza
- Progetto Firebase Spark separato: NON usare il database eventi o sovrascriverne le regole. Nessuna attivazione del piano Blaze. Il piano Spark limita le connessioni Realtime Database a 100 e ha quote di storage/download. Superare una quota può interrompere il servizio; controllare l'uso.
- Nessun collegamento al progetto finché community-config.js contiene null. Il modulo non raccoglie dati né compare in home in tale stato.
- Una sola stanza per utenti autenticati con Google e email verificata. Età 18+ autodichiarata, non verificata. Non mostrare email, nome Google o UID nella stanza. Nickname scelto dall'utente; non è prova di identità.
- Solo testo, 300 caratteri, niente upload, link cliccabili, presenza online, messaggi privati o notifiche. Il filtro client per recapiti è indicativo, NON una barriera di sicurezza.
- Tutti gli invii sono privati finché un moderatore approva. Una richiesta pendente per account, minimo 30 secondi fra invii risolti; segnalazioni separate. Il moderatore può rifiutare, sospendere e rimuovere. Nessun ban automatico arbitrario. Un solo moderatore nel pilot, per evitare corse di approvazione.
- Le regole del database, non il browser, devono impedire all'utente di scrivere in published, moderators, bans, authors o settings. Regole candidate in community-database.rules.json. Nessun accesso diretto agli utenti dell'app esistente.
- Non è una moderazione automatica completa: serve un moderatore responsabile. Se nessuno può assumersi questo compito, mantenere chiuso il pilot.
- Nessuna copia di messaggi nella raccolta eventi; usare il normale flusso di segnalazione verificata.

## Prima di attivare
1. Creare un nuovo progetto Firebase Spark dedicato e RTDB in Europa, inizialmente bloccato. Attivare Authentication Google; autorizzare francescocompierchio.github.io. Verificare login anche su Android/TWA; il popup potrebbe richiedere apertura nel browser. Non pubblicare chiavi amministrative.
2. Applicare le regole candidate SOLO al database separato. Eseguire test su Emulator Suite / Rules Playground con account anonimo, Google normale, Google sospeso e moderatore: lettura non autorizzata, scrittura pubblica, escalation ruoli, contraffazione UID, bypass coda, limiti query, rate limit, rimozione e segnalazione. Non abilitare prima del successo.
3. Dal pannello Firebase (accesso amministratore), impostare moderators/<UID del moderatore> = true; settings/open = false. Non rendere il ruolo autoassegnabile. Impostare un solo moderatore nel pilot.
4. Completare community-privacy.html con informativa effettiva, contatti, procedura di cancellazione e contestazione, durata di conservazione, condizioni di utilizzo. Valutare gli obblighi GDPR e DSA per il servizio; non considerare la bozza una conformità verificata. Definire la rimozione periodica di messaggi pubblicati, coda risolta, segnalazioni e mapping authors. Il database non elimina automaticamente i dati.
5. Inserire nel file community-config.js la configurazione web pubblica del NUOVO progetto come window.CSF_COMMUNITY_CONFIG = { enabled: true, firebase: { ...config web... } }; non inserire credenziali server. Fare prova end-to-end in ambiente separato e verificare che il sito eventi resti invariato. Solo dopo aprire settings/open = true.
6. Monitorare costi/quote, abuso, tempi di moderazione. Per sospendere il servizio, impostare settings/open = false (le regole negano lettura pubblica e invio) e, se necessario, disattivare config. Non alterare il progetto eventi.

Riferimenti: https://firebase.google.com/docs/database/security/rules-conditions ; https://firebase.google.com/docs/auth/web/google-signin ; https://firebase.google.com/pricing ; https://firebase.google.com/docs/database/usage/limits .
