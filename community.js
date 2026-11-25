/* Community separata: nessuna connessione finché non configurata. */
(() => {
  "use strict";
  const config=window.CSF_COMMUNITY_CONFIG;
  if(!config || config.enabled!==true || !config.firebase || !config.firebase.projectId ||
     !config.firebase.databaseURL || config.firebase.projectId==="chesifa-cerignola") return;
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
  const consent=$("input",null,{type:"checkbox",id:"csfc-consent"});
  const consentLabel=$("label","",{for:"csfc-consent"});
  consentLabel.append(consent,document.createTextNode(" Ho almeno 18 anni, accetto le regole e ho letto "));
  const privacy=$("a","l’informativa Community",{href:"community-privacy.html",target:"_blank",rel:"noopener noreferrer"});consentLabel.append(privacy);
  const login=$("button","Accedi con Google",{type:"button",class:"csfc-primary"});
  const logout=$("button","Esci",{type:"button",hidden:""});
  const nick=$("input",null,{required:"",maxlength:"24",minlength:"2",placeholder:"Nickname pubblico","aria-label":"Nickname pubblico",autocomplete:"off"});
  const msg=$("textarea",null,{required:"",maxlength:"300",rows:"3",placeholder:"Scrivi un messaggio sugli eventi…","aria-label":"Messaggio"});
  const send=$("button","Invia per moderazione",{type:"submit",class:"csfc-primary"});
  const form=$("form",null,{hidden:""});form.append(nick,msg,send);
  const mod=$("div",null,{id:"csfc-moderation",hidden:"","aria-label":"Coda moderazione"});
  panel.append(header,info,status,feed,consentLabel,login,logout,form,mod);
  root.append(toggle,panel);document.body.append(root);
  let app,auth,db,user,authUnsub,off=[],generation=0,opening=false,moderator=false,blocked=false;
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
  async function init(){
    if(app)return;
    await loadAuth();
    app=firebase.initializeApp(config.firebase,"csf-community");
    auth=app.auth();db=app.database();
    authUnsub=auth.onAuthStateChanged(u=>{user=u;if(!panel.hidden)refresh();},error);
  }
  async function refresh(){
    stop();const g=generation;moderator=false;blocked=false;
    const signed=!!user;
    login.hidden=signed;consentLabel.hidden=signed;logout.hidden=!signed;form.hidden=true;mod.hidden=true;
    if(!signed){status.textContent="Accedi per leggere e partecipare.";return;}
    db.goOnline();status.textContent="Connessione…";
    try{
      const [m,b,c]=await Promise.all([db.ref("moderators/"+user.uid).once("value"),db.ref("bans/"+user.uid).once("value"),db.ref("settings/open").once("value")]);
      if(g!==generation||panel.hidden)return;
      moderator=m.val()===true;blocked=b.val()===true;
      if(c.val()!==true){status.textContent="Community non ancora aperta.";return;}
      if(blocked){status.textContent="Account sospeso dalla community.";return;}
      status.textContent="Messaggi pubblicati dopo verifica.";form.hidden=false;
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
            a.append(button("Rimuovi messaggio",async()=>{const ch={};ch["published/"+v.messageId]=null;ch["authors/"+v.messageId]=null;ch["reports/"+uid+"/state"]="resolved";await db.ref().update(ch);}),button("Archivia",()=>db.ref("reports/"+uid+"/state").set("resolved")));mod.append(a);
          }
        };
        listen(db.ref("submissions").orderByChild("state").equalTo("pending").limitToFirst(40),s=>{submissions=Object.entries(s.val()||{});render();});
        listen(db.ref("reports").orderByChild("state").equalTo("pending").limitToFirst(40),s=>{reports=Object.entries(s.val()||{});render();});
      }
    }catch{if(g===generation)error();}
  }
  async function open(){if(opening)return;opening=true;panel.hidden=false;toggle.setAttribute("aria-expanded","true");status.textContent="Caricamento…";try{await init();if(!panel.hidden)await refresh();}catch{error();}finally{opening=false;}}
  function shut(){panel.hidden=true;toggle.setAttribute("aria-expanded","false");stop();toggle.focus();}
  toggle.onclick=()=>panel.hidden?open():shut();close.onclick=shut;
  panel.addEventListener("keydown",e=>{if(e.key==="Escape")shut();});
  login.onclick=async()=>{if(!consent.checked){status.textContent="Conferma età e informativa prima di accedere.";return;}try{await auth.signInWithPopup(new firebase.auth.GoogleAuthProvider());}catch{error();}};
  logout.onclick=async()=>{try{await auth.signOut();}catch{error();}};
  form.onsubmit=async e=>{
    e.preventDefault();if(!user||blocked)return;
    const n=nick.value.trim(),t=msg.value.trim();if(!checkText(n,t)){status.textContent="Usa 2–24 caratteri per il nickname e 1–300 per il messaggio, senza link o recapiti.";return;}
    send.disabled=true;
    try{await db.ref("submissions/"+user.uid).set({nick:n,text:t,createdAt:firebase.database.ServerValue.TIMESTAMP,state:"pending"});msg.value="";status.textContent="In attesa di moderazione.";}catch{send.disabled=false;status.textContent="Invio non riuscito. Attendi o verifica lo stato del tuo account.";}
  };
  document.addEventListener("visibilitychange",()=>{if(document.hidden)stop();else if(!panel.hidden&&app)refresh();});
})();
