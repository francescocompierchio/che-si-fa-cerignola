# Regole segnalazioni — database eventi

Database: `chesifa-cerignola-default-rtdb` (non Community, non statistiche).

Il file `segnalazioni-validation.fragment.json` è un frammento di regola, NON un ruleset completo. Non pubblicarlo da solo. Salvare una copia delle regole effettive prima di intervenire. In `rules.segnalazioniDaApprovare.$id` (usare il nome della wildcard già presente), combinare la sua `.validate` esistente con la nuova mediante AND, senza toccare `.read`, `.write`, regole figlie e altri percorsi. Verificare che non esistano wildcard o validazioni conflittuali; provare regole complete nell'emulatore e con un invio pubblico e lettura/rimozione amministrativa prima della pubblicazione. Non rimuovere regole preesistenti. Non modificare permessi o piano.

La regola impone i dati minimi per tutte le segnalazioni; in modalità rapida richiede inoltre URL HTTPS o foto JPEG, data singola e ora HH:mm. Il modulo gestori mantiene i suoi campi obbligatori. Non può certificare che l'annuncio sia autentico, che i dati dichiarati siano veri, che il link sia accessibile o che la foto sia leggibile. Le date sono controllate sintatticamente lato database. La verifica redazionale resta necessaria.

Le regole effettive di produzione non sono disponibili in questo repository. Il test emulato usa permessi di test isolati, non adatti alla produzione.
