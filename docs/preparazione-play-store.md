# Preparazione alla pubblicazione Android — Che Si Fa Cerignola

Stato: sito/PWA pubblicato. APK esistente nel repository. Nessun AAB firmato o scheda Google Play pubblicata.

## Google Play
- Account sviluppatore e verifica dell'identità del titolare: https://play.google.com/console/
- Richiedere al servizio che ha generato l'APK un AAB firmabile con target Android 16 / API 36 o superiore. Conservare lo stesso application ID e le chiavi di firma originali se già in uso. Non inserire chiavi o password nel repository.
- Verificare il report GitHub Actions "Verifica compatibilità APK Android" (formato, target SDK, identificativo, permessi, firma).
- Testare navigazione, ricerca, preferiti, link esterni, caricamento foto OCR, consenso statistico e calendario sul dispositivo reale.
- Informativa privacy: https://francescocompierchio.github.io/che-si-fa-cerignola/privacy.html
- Compilare Data safety in base al comportamento effettivo dell'app e degli SDK del wrapper Android; non dichiarare assenza di dati senza verificarla.
- Per account personali creati dopo il 13 novembre 2023: test chiuso con almeno 12 tester aderenti per 14 giorni consecutivi, poi richiesta di accesso alla produzione.
- Scheda: nome "Che Si Fa Cerignola"; descrizione breve "Eventi, serate e attività a Cerignola e dintorni."; app gratuita. Preparare screenshot reali della home, scheda evento, filtri e preferiti.
- Riferimenti: https://support.google.com/googleplay/android-developer/answer/11926878 e https://support.google.com/googleplay/android-developer/answer/14151465

## Google Analytics
Proprietà collegata al sito: G-M2QBFBHQXQ. In Amministrazione > Definizioni personalizzate creare due dimensioni con ambito Evento: "Evento locale" (parametro csf_event_id) e "Categoria evento" (parametro csf_category). In Esplorazioni usare tali dimensioni, Nome evento e Conteggio eventi. I dati sono parziali: soltanto utenti consenzienti, non prenotazioni o condivisioni confermate.
Verificare in Tempo reale con un dispositivo non escluso, dopo consenso.
Riferimento: https://support.google.com/analytics/answer/14240153
