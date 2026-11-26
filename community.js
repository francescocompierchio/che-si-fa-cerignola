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
  const info=$("small","Scrivi in italiano e con educazione. I messaggi vengono controllati prima di apparire in chat. Non condividere dati personali.");
  const feed=$("div",null,{id:"csfc-feed",role:"log","aria-label":"Messaggi approvati"});
  const rulesNotice=$("small","Community riservata ai maggiorenni. ",{id:"csfc-rules-notice"});
  const privacy=$("a","Regole e informativa privacy",{href:"community-privacy.html",target:"_blank",rel:"noopener noreferrer"});rulesNotice.append(privacy);
  const login=$("button","Accedi con Google",{type:"button",class:"csfc-primary"});
  const browserHint=$("small","L’accesso si apre nella stessa pagina e torna direttamente alla Community.",{hidden:""});
  const logout=$("button","Esci",{type:"button",hidden:""});
  const identity=$("small","",{id:"csfc-identity"});
  const msg=$("textarea",null,{required:"",maxlength:"300",rows:"3",placeholder:"Scrivi un messaggio sugli eventi…","aria-label":"Messaggio"});
  const send=$("button","Invia messaggio",{type:"submit",class:"csfc-primary"});
  const form=$("form",null,{hidden:""});form.append(identity,msg,send);
  const mod=$("div",null,{id:"csfc-moderation",hidden:"","aria-label":"Segnalazioni"});
  panel.append(header,info,status,feed,rulesNotice,login,browserHint,logout,form,mod);
  root.append(toggle,panel);document.body.append(root);
  let app,auth,db,user,authUnsub,off=[],generation=0,opening=false,moderator=false,blocked=false;
  let authInit,persistenceLimited=false;
  const stop=()=>{generation++;for(const f of off.splice(0))f();feed.replaceChildren();mod.replaceChildren();if(db)db.goOffline();};
  const error=()=>{status.textContent="Community temporaneamente non disponibile. Nessun messaggio è stato pubblicato automaticamente.";};
  const listen=(q,cb)=>{q.on("value",cb,error);off.push(()=>q.off("value",cb));};
  function button(label,fn){const n=$("button",label,{type:"button"});n.addEventListener("click",async()=>{n.disabled=true;try{await fn();}catch{error();}finally{n.disabled=false;}});return n;}
  function safeText(v){return typeof v==="string"?v:"";}
  function checkText(t){return t.length>0&&t.length<=300&&!/(https?:|www\.|[\w.+-]+@[\w.-]+\.[a-z]{2,}|\d[\d\s-]{7,}\d)/i.test(t);}
  function identityFromEmail(u){
    if(!u?.emailVerified||typeof u.email!=="string")return null;
    const at=u.email.lastIndexOf("@");if(at<1)return null;
    const nick=u.email.slice(0,at).slice(0,3),domain=u.email.slice(at+1);
    if(!/^[A-Za-z0-9._+%-]{1,3}$/.test(nick)||! /^[A-Za-z0-9.-]{1,100}$/.test(domain))return null;
    return {nick,domain,label:nick+"***@"+domain};
  }
  async function loadAuth(){
    if(window.firebase?.auth)return;
    await new Promise((resolve,reject)=>{const s=$("script",null,{src:"https://www.gstatic.com/firebasejs/10.14.1/firebase-auth-compat.js"});s.onload=resolve;s.onerror=reject;document.head.append(s);});
  }
  function beginGoogle(){
    if(panel.hidden||user||login.disabled)return;
    try{
      login.disabled=true;
      status.textContent="Apertura accesso Google…";
      location.assign(window.CsfCommunityOIDC.start(config.googleClientId,localStorage,window.crypto));
    }catch{
      login.disabled=false;browserHint.hidden=false;
      status.textContent="Il browser non consente di avviare l’accesso. Apri la Community in Chrome e riprova.";
    }
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
    login.hidden=signed;login.disabled=false;rulesNotice.hidden=false;logout.hidden=!signed;form.hidden=true;mod.hidden=true;browserHint.hidden=signed;
    if(!signed){status.textContent="Accedi con Google per leggere e partecipare.";return;}
    db.goOnline();status.textContent="Connessione…";
    try{
      const [m,b,c]=await Promise.all([db.ref("moderators/"+user.uid).once("value"),db.ref("bans/"+user.uid).once("value"),db.ref("settings/open").once("value")]);
      if(g!==generation||panel.hidden)return;
      moderator=m.val()===true;blocked=b.val()===true;
      if(c.val()!==true){status.textContent="Community non ancora aperta.";return;}
      if(blocked){status.textContent="Account sospeso dalla community.";return;}
      const verified=identityFromEmail(user);
      if(!verified){status.textContent="Non è disponibile un indirizzo Google verificato compatibile.";return;}
      identity.textContent="Scrivi come "+verified.label+" (email mascherata).";
      status.textContent=persistenceLimited?"Accesso riuscito. Il browser potrebbe non conservare la sessione.":"Controllo automatico prima della pubblicazione.";form.hidden=false;
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
        if(v?.state==="pending")status.textContent="Messaggio ricevuto. Il controllo può richiedere alcuni minuti o più se il servizio è occupato.";
        else if(v?.state==="approved")status.textContent="Messaggio approvato e pubblicato.";
        else if(v?.state==="rejected")status.textContent="Messaggio non pubblicato. Scrivi in italiano, con educazione e senza dati personali, e riprova. Puoi chiedere un riesame."
      });
      if(moderator){
        mod.hidden=false;
        let reports=[];
        const render=()=>{
          mod.replaceChildren($("strong","Segnalazioni (facoltative)"));
          if(!reports.length){mod.hidden=true;return;}
          mod.hidden=false;
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
        listen(db.ref("reports").orderByChild("state").equalTo("pending").limitToFirst(40),s=>{reports=Object.entries(s.val()||{});render();});
      }
    }catch{if(g===generation)error();}
  }
  async function open(){if(opening)return;opening=true;panel.hidden=false;toggle.setAttribute("aria-expanded","true");status.textContent="Caricamento…";try{await init();if(!panel.hidden)await refresh();}catch{error();}finally{opening=false;}}
  function shut(){panel.hidden=true;browserHint.hidden=true;toggle.setAttribute("aria-expanded","false");stop();toggle.focus();}
  toggle.onclick=()=>panel.hidden?open():shut();close.onclick=shut;
  panel.addEventListener("keydown",e=>{if(e.key==="Escape")shut();});
  login.onclick=beginGoogle;
  logout.onclick=async()=>{try{await auth.signOut();}catch{error();}};
  form.onsubmit=async e=>{
    e.preventDefault();if(!user||blocked)return;
    const verified=identityFromEmail(user),t=msg.value.trim();if(!verified||!checkText(t)){status.textContent="Usa 1–300 caratteri per il messaggio, senza link o recapiti.";return;}
    send.disabled=true;
    try{await db.ref("submissions/"+user.uid).set({nick:verified.nick,domain:verified.domain,text:t,createdAt:firebase.database.ServerValue.TIMESTAMP,state:"pending"});msg.value="";status.textContent="Messaggio ricevuto. In attesa del controllo.";}catch{send.disabled=false;status.textContent="Invio non riuscito. Riprova tra poco; il controllo potrebbe essere temporaneamente non disponibile.";}
  };
  // Il callback torna qui e riapre automaticamente il pannello.
  if(typeof location!=="undefined"&&new URLSearchParams(location.search).get("community")==="1"){
    const u=new URL(location.href);u.searchParams.delete("community");history.replaceState(null,"",u.pathname+u.search+u.hash);open();
  }
  window.addEventListener?.("pageshow",()=>{login.disabled=false;if(!panel.hidden&&auth){user=auth.currentUser;refresh();}});
  document.addEventListener("visibilitychange",()=>{if(document.hidden)stop();else if(!panel.hidden&&app){if(auth)user=auth.currentUser;refresh();}});
})();
