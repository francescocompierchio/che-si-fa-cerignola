/* Community separata: nessuna connessione finché non configurata. */
(() => {
  "use strict";
  const config=window.CSF_COMMUNITY_CONFIG;
  if(!config || config.enabled!==true || !config.firebase || !config.firebase.projectId ||
     !config.firebase.databaseURL || config.firebase.projectId==="chesifa-cerignola" || /chesifa-cerignola-default-rtdb/i.test(config.firebase.databaseURL)) return;
  const $=(tag,text,attrs={})=>{
    const n=document.createElement(tag);
    if(text!==null)n.textContent=text;
    for(const [k,v] of Object.entries(attrs))n.setAttribute(k,v);
    return n;
  };
  const root=$("aside",null,{id:"csfc","aria-label":"Community"});
  const toggle=$("button","Community",{id:"csfc-toggle",type:"button","aria-expanded":"false","aria-controls":"csfc-panel"});
  const panel=$("section",null,{id:"csfc-panel",hidden:"",role:"region","aria-labelledby":"csfc-title"});
  const title=$("h2","Che Si Fa Community",{id:"csfc-title"});
  const close=$("button","Chiudi",{type:"button","aria-label":"Chiudi community"});
  const header=$("header");header.append(title,close);
  const status=$("div","",{id:"csfc-status",role:"status"});
  const info=$("small","Spazio pubblico dedicato agli eventi. I messaggi sono pubblicati solo dopo moderazione. Non condividere dati personali.");
  const feed=$("div",null,{id:"csfc-feed",role:"log","aria-label":"Messaggi approvati"});
  const rulesNotice=$("small","Community riservata ai maggiorenni. ",{id:"csfc-rules-notice"});
  const privacy=$("a","Regole e informativa privacy",{href:"community-privacy.html",target:"_blank",rel:"noopener noreferrer"});rulesNotice.append(privacy);
  const login=$("button","Accedi con Google",{type:"button",class:"csfc-primary"});
  const googleSlot=$("div",null,{id:"csfc-google-signin",hidden:"","aria-label":"Accesso Google"});
  const alternate=$("button","Accesso Google alternativo",{type:"button",id:"csfc-login-alternate",hidden:""});
  const browserHint=$("small","Se Google mostra una pagina bianca, torna alla Community con Indietro. Se non sei collegato, prova l’accesso alternativo in una normale scheda Chrome (non nel browser interno di un’altra app).",{hidden:""});
  const logout=$("button","Esci",{type:"button",hidden:""});
  const nick=$("input",null,{required:"",maxlength:"24",minlength:"2",placeholder:"Nickname pubblico","aria-label":"Nickname pubblico",autocomplete:"off"});
  const msg=$("textarea",null,{required:"",maxlength:"300",rows:"3",placeholder:"Scrivi un messaggio sugli eventi…","aria-label":"Messaggio"});
  const send=$("button","Invia per moderazione",{type:"submit",class:"csfc-primary"});
  const form=$("form",null,{hidden:""});form.append(nick,msg,send);
  const mod=$("div",null,{id:"csfc-moderation",hidden:"","aria-label":"Coda moderazione"});
  panel.append(header,info,status,feed,rulesNotice,login,googleSlot,alternate,browserHint,logout,form,mod);
  root.append(toggle,panel);document.body.append(root);
  let app,auth,db,user,authUnsub,off=[],generation=0,opening=false,moderator=false,blocked=false;
  let gisLoad,gisReady=false,googleFlow=false,authBusy=false,alternateOffered=false,authInit,persistenceLimited=false;
  const stop=()=>{generation++;for(const f of off.splice(0))f();feed.replaceChildren();mod.replaceChildren();if(db)db.goOffline();};
  const error=()=>{status.textContent="Community temporaneamente non disponibile. Nessun messaggio è stato pubblicato automaticamente.";};
  const listen=(q,cb)=>{q.on("value",cb,error);off.push(()=>q.off("value",cb));};
  function button(label,fn){const n=$("button",label,{type:"button"});n.addEventListener("click",async()=>{n.disabled=true;try{await fn();}catch{error();}finally{n.disabled=false;}});return n;}
  function safeText(v){return typeof v==="string"?v:"";}
  function checkText(n,t){return n.length>=2&&n.length<=24&&t.length>0&&t.length<=300&&!/(https?:|www\.|[\w.+-]+@[\w.-]+\.[a-z]{2,}|\d[\d\s-]{7,}\d)/i.test(t+" "+n);}
  async function loadAuth(){
    if(window.firebase?.auth)return;
    await new Promise((resolve,reject)=>{const s=$("script",null,{src:"https://www.gstatic.com/firebasejs/10.14.1/firebase-auth-compat.js"});s.onload=resolve;s.onerror=reject;document.head.append(s);});
  }
  function loadGoogle(){
    if(window.google?.accounts?.id)return Promise.resolve(window.google.accounts.id);
    if(!gisLoad){
      gisLoad=new Promise((resolve,reject)=>{
        const s=$("script",null,{src:"https://accounts.google.com/gsi/client?hl=it",async:""});
        s.onload=()=>window.google?.accounts?.id?resolve(window.google.accounts.id):reject(Error("google-sdk"));
        s.onerror=()=>{s.remove();reject(Error("google-sdk"));};
        document.head.append(s);
      }).catch(e=>{gisLoad=null;throw e;});
    }
    return gisLoad;
  }
  async function receiveGoogle(response){
    if(panel.hidden||!auth||authBusy||user||!googleFlow)return;
    if(typeof response?.credential!=="string"||!response.credential){status.textContent="Accesso non riuscito. Riprova con il pulsante Google.";return;}
    authBusy=true;
    status.textContent="Verifica dell’account Google…";
    try{
      await auth.signInWithCredential(firebase.auth.GoogleAuthProvider.credential(response.credential));
      googleFlow=false;
    }catch(e){
      status.textContent="Accesso Google non riuscito ("+(e?.code||"verifica credenziale")+"). Riprova in Chrome.";
      browserHint.hidden=false;
    }finally{authBusy=false;}
  }
  async function alternateGoogle(){
    if(panel.hidden||!auth||authBusy||user)return;
    authBusy=true;googleFlow=false;googleSlot.hidden=true;alternate.disabled=true;
    status.textContent="Completa l’accesso Google nella nuova finestra. Poi torna alla Community.";
    try{
      // Alternativa esplicita: il flusso Firebase è utilizzabile in Chrome
      // quando il popup GIS non restituisce la credenziale.
      await auth.signInWithPopup(new firebase.auth.GoogleAuthProvider());
    }catch(e){
      status.textContent="Accesso alternativo non riuscito ("+(e?.code||"sessione")+"). Apri l’app in una normale scheda Chrome e riprova.";
      browserHint.hidden=false;
    }finally{
      authBusy=false;alternate.disabled=false;
      if(!user)login.hidden=false;
    }
  }
  async function prepareGoogle(){
    if(panel.hidden||user||authBusy||login.disabled)return;
    if(!auth){status.textContent="Connessione non disponibile. Chiudi e riapri la Community.";browserHint.hidden=false;return;}
    if(!/^[0-9]+-[a-z0-9]+\.apps\.googleusercontent\.com$/i.test(config.googleClientId||"")){status.textContent="Accesso Google non ancora configurato.";return;}
    login.disabled=true;alternateOffered=true;alternate.hidden=false;browserHint.hidden=false;
    status.textContent="Caricamento accesso Google…";
    try{
      const id=await loadGoogle();
      if(panel.hidden||user)return;
      if(!gisReady){
        id.initialize({client_id:config.googleClientId,callback:receiveGoogle,ux_mode:"popup",auto_select:false,use_fedcm_for_button:true});
        gisReady=true;
      }
      googleFlow=true;googleSlot.hidden=false;
      googleSlot.replaceChildren();
      id.renderButton(googleSlot,{type:"standard",theme:"outline",size:"large",text:"signin_with",shape:"rectangular",width:Math.min(300,Math.max(180,googleSlot.clientWidth||220)),locale:"it"});
      login.hidden=true;
      browserHint.hidden=false;
      status.textContent="Premi il pulsante ufficiale Google e scegli il tuo account.";
    }catch{
      googleFlow=false;googleSlot.hidden=true;login.hidden=false;browserHint.hidden=false;
      status.textContent="Impossibile caricare l’accesso Google. Riprova in Chrome.";
    }finally{login.disabled=false;}
  }
  async function init(){
    if(authInit)return authInit;
    authInit=(async()=>{
      await loadAuth();
      app=firebase.apps?.find(a=>a.name==="csf-community")||firebase.initializeApp(config.firebase,"csf-community");
      auth=app.auth();db=app.database();
      // Firebase gestisce e rinnova la sessione: nessun token copiato a mano.
      try{await auth.setPersistence(firebase.auth.Auth.Persistence.LOCAL);}
      catch{persistenceLimited=true;}
      // Attendi il ripristino della sessione prima di proporre un nuovo accesso.
      await new Promise((resolve,reject)=>{
        let first=true;
        authUnsub=auth.onAuthStateChanged(u=>{
          user=u;
          if(first){first=false;resolve();return;}
          if(!panel.hidden)refresh();
        },e=>{if(first){first=false;reject(e);}else error();});
      });
    })().catch(e=>{authInit=null;throw e;});
    return authInit;
  }
  async function refresh(){
    stop();const g=generation;moderator=false;blocked=false;
    const signed=!!user;
    login.hidden=signed||googleFlow;googleSlot.hidden=signed||!googleFlow;alternate.hidden=signed||!alternateOffered;rulesNotice.hidden=signed;logout.hidden=!signed;form.hidden=true;mod.hidden=true;
    if(!signed){
      if(!authBusy)status.textContent=googleFlow?"Premi il pulsante ufficiale Google. Se la pagina resta bianca, torna qui e prova l’accesso alternativo.":"Accedi per leggere e partecipare.";
      if(!googleFlow&&!alternateOffered&&!authBusy)prepareGoogle();
      return;
    }
    googleFlow=false;alternateOffered=false;googleSlot.hidden=true;alternate.hidden=true;browserHint.hidden=true;
    db.goOnline();status.textContent="Connessione…";
    try{
      const [m,b,c]=await Promise.all([db.ref("moderators/"+user.uid).once("value"),db.ref("bans/"+user.uid).once("value"),db.ref("settings/open").once("value")]);
      if(g!==generation||panel.hidden)return;
      moderator=m.val()===true;blocked=b.val()===true;
      if(c.val()!==true){status.textContent="Community non ancora aperta.";return;}
      if(blocked){status.textContent="Account sospeso dalla community.";return;}
      status.textContent=persistenceLimited?"Accesso riuscito. Il browser potrebbe non conservare la sessione.":"Messaggi pubblicati dopo verifica.";form.hidden=false;
      listen(db.ref("published").orderByKey().limitToLast(40),snap=>{
        feed.replaceChildren();
        if(!snap.exists()){feed.append($("small","Non ci sono ancora messaggi approvati."));return;}
        snap.forEach(child=>{
          const v=child.val(),a=$("article"),h=$("div",null,{class:"csfc-row"});
          h.append($("strong",safeText(v.nick)),button("Segnala",async()=>{
            if(!confirm("Segnalare questo messaggio alla moderazione?"))return;
            await db.ref("reports/"+user.uid).set({messageId:child.key,createdAt:firebase.database.ServerValue.TIMESTAMP,state:"pending"});
            status.textContent="Segnalazione inviata.";
          }));
          a.append(h,$("p",safeText(v.text)));feed.append(a);
        });
        feed.scrollTop=feed.scrollHeight;
      });
      listen(db.ref("submissions/"+user.uid),s=>{
        const v=s.val();send.disabled=v?.state==="pending";
        if(v?.state==="pending")status.textContent="Il tuo messaggio è in attesa di moderazione.";
      });
      if(moderator){
        mod.hidden=false;
        let submissions=[],reports=[];
        const render=()=>{
          mod.replaceChildren($("strong","Moderazione"));
          if(!submissions.length&&!reports.length)mod.append($("small","Nessuna richiesta in attesa."));
          for(const [uid,v] of submissions){
            const a=$("article");a.append($("strong",safeText(v.nick)),$("p",safeText(v.text)));
            a.append(button("Approva",async()=>{
              const id=db.ref("published").push().key;
              const live=await db.ref("submissions/"+uid).once("value");
              if(live.val()?.state!=="pending"||live.val()?.createdAt!==v.createdAt)throw Error("changed");
              const changes={};changes["published/"+id]={nick:v.nick,text:v.text,createdAt:firebase.database.ServerValue.TIMESTAMP};
              changes["authors/"+id]=uid;changes["submissions/"+uid+"/state"]="approved";
              await db.ref().update(changes);
            }),button("Rifiuta",()=>db.ref("submissions/"+uid+"/state").set("rejected")),button("Sospendi",async()=>{
              if(!confirm("Sospendere l’account?"))return;
              const changes={};changes["bans/"+uid]=true;changes["submissions/"+uid+"/state"]="rejected";await db.ref().update(changes);
            }));mod.append(a);
          }
          for(const [uid,v] of reports){
            const a=$("article");a.append($("p","Messaggio segnalato: "+safeText(v.messageId)));
            const details=$("p","Caricamento del contenuto segnalato…");a.append(details);
            db.ref("published/"+v.messageId).once("value").then(s=>{
              const m=s.val();details.textContent=m?safeText(m.nick)+": "+safeText(m.text):"Messaggio già rimosso.";
            }).catch(()=>{details.textContent="Contenuto non disponibile.";});
            a.append(button("Rimuovi messaggio",async()=>{if(!confirm("Rimuovere questo messaggio?"))return;const ch={};ch["published/"+v.messageId]=null;ch["authors/"+v.messageId]=null;ch["reports/"+uid+"/state"]="resolved";await db.ref().update(ch);}),button("Sospendi autore e rimuovi",async()=>{
              if(!confirm("Sospendere l'autore e rimuovere il messaggio?"))return;
              const author=(await db.ref("authors/"+v.messageId).once("value")).val();
              if(typeof author!=="string"||!author)throw Error("missing author");
              const ch={};ch["bans/"+author]=true;ch["published/"+v.messageId]=null;ch["authors/"+v.messageId]=null;ch["reports/"+uid+"/state"]="resolved";await db.ref().update(ch);
            }),button("Archivia",()=>db.ref("reports/"+uid+"/state").set("resolved")));mod.append(a);
          }
        };
        listen(db.ref("submissions").orderByChild("state").equalTo("pending").limitToFirst(40),s=>{submissions=Object.entries(s.val()||{});render();});
        listen(db.ref("reports").orderByChild("state").equalTo("pending").limitToFirst(40),s=>{reports=Object.entries(s.val()||{});render();});
      }
    }catch{if(g===generation)error();}
  }
  async function open(){if(opening)return;opening=true;panel.hidden=false;toggle.setAttribute("aria-expanded","true");status.textContent="Caricamento…";try{await init();if(!panel.hidden)await refresh();}catch{error();}finally{opening=false;}}
  function shut(){panel.hidden=true;googleFlow=false;alternateOffered=false;googleSlot.hidden=true;googleSlot.replaceChildren();alternate.hidden=true;browserHint.hidden=true;toggle.setAttribute("aria-expanded","false");stop();toggle.focus();}
  toggle.onclick=()=>panel.hidden?open():shut();close.onclick=shut;
  panel.addEventListener("keydown",e=>{if(e.key==="Escape")shut();});
  login.onclick=prepareGoogle;
  alternate.onclick=alternateGoogle;
  logout.onclick=async()=>{try{window.google?.accounts?.id?.disableAutoSelect();googleFlow=false;alternateOffered=false;await auth.signOut();}catch{error();}};
  form.onsubmit=async e=>{
    e.preventDefault();if(!user||blocked)return;
    const n=nick.value.trim(),t=msg.value.trim();if(!checkText(n,t)){status.textContent="Usa 2–24 caratteri per il nickname e 1–300 per il messaggio, senza link o recapiti.";return;}
    send.disabled=true;
    try{await db.ref("submissions/"+user.uid).set({nick:n,text:t,createdAt:firebase.database.ServerValue.TIMESTAMP,state:"pending"});msg.value="";status.textContent="In attesa di moderazione.";}catch{send.disabled=false;status.textContent="Invio non riuscito. Attendi o verifica lo stato del tuo account.";}
  };
  document.addEventListener("visibilitychange",()=>{if(document.hidden)stop();else if(!panel.hidden&&app){if(auth)user=auth.currentUser;refresh();}});
})();
