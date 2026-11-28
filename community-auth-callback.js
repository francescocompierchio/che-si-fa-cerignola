/* La pagina non contiene analytics, script di terzi non necessari o il feed eventi. */
(async()=>{
  "use strict";
  const fragment=location.hash;
  // Togli il token dalla barra degli indirizzi prima di caricare gli SDK remoti.
  history.replaceState(null,"",location.pathname);
  const status=document.getElementById("status");
  const back=document.getElementById("back");
  const flow=window.CsfCommunityOIDC,config=window.CSF_COMMUNITY_CONFIG;
  function load(src){
    return new Promise((resolve,reject)=>{
      const script=document.createElement("script");
      script.src=src;script.onload=resolve;script.onerror=()=>reject(Error("network"));
      document.head.append(script);
    });
  }
  try{
    if(!flow||!config||config.enabled!==true||config.firebase.projectId!=="che-si-fa-community"||config.firebase.databaseURL!=="https://che-si-fa-community-default-rtdb.europe-west1.firebasedatabase.app")throw Error("config");
    const token=flow.consume(fragment,config.googleClientId,localStorage);
    status.textContent="Verifica sicura dell’account Google…";
    await load("https://www.gstatic.com/firebasejs/10.14.1/firebase-app-compat.js");
    await load("https://www.gstatic.com/firebasejs/10.14.1/firebase-auth-compat.js");
    const auth=firebase.initializeApp(config.firebase,"csf-community").auth();
    await auth.setPersistence(firebase.auth.Auth.Persistence.LOCAL);
    const result=await auth.signInWithCredential(firebase.auth.GoogleAuthProvider.credential(token));
    if(!result?.user?.emailVerified)throw Error("credential");
    status.textContent="Accesso riuscito. Ritorno alla Community…";
    location.replace(flow.HOME);
  }catch(e){
    const messages={session:"La richiesta di accesso è scaduta oppure il browser ha cambiato sessione. Torna alla Community e riprova nello stesso browser.",cancelled:"Accesso annullato. Puoi riprovare dalla Community.",credential:"Google non ha restituito una credenziale valida. Torna alla Community e riprova.",network:"Connessione non disponibile. Riprova."};
    status.textContent=messages[e?.message]||"Accesso non completato. Torna alla Community e riprova.";
    back.hidden=false;
  }
})();
