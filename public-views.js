"use strict";
(function(root){
  function creaVisualizzazioni(db,permesso,escluso,visibile,mostra,avvisa){
  const ref=db.ref("statistiche/visualizzazioniTotali"),conn=db.ref(".info/connected");
  let connesso=false,contata=false,inCorso=false,ultimo=null;
  const render=()=>mostra(connesso?ultimo:null);
  async function aggiorna(){
    if(!connesso||inCorso)return;
    const admin=escluso();
    const delta=admin&&contata?-1:!admin&&permesso()&&visibile()&&!contata?1:0;
    if(!delta)return;
    inCorso=true;
    try{
      const r=await ref.transaction(n=>{
        if(n===null)return delta===1?1:undefined;
        if(!Number.isSafeInteger(n)||n<0||n+delta<0||!Number.isSafeInteger(n+delta))return;
        return n+delta;
      },undefined,false);
      if(!r.committed)throw Error("Scrittura non confermata");
      contata=delta===1;
    }catch(e){avvisa(e);}
    finally{inCorso=false;}
    // Se l'admin viene attivato durante una scrittura, storna la sola apertura corrente.
    if(delta===1&&contata&&escluso())void aggiorna();
  }
  ref.on("value",s=>{const n=s.val();ultimo=n===null?0:Number.isSafeInteger(n)&&n>=0?n:null;render();},e=>{ultimo=null;render();avvisa(e);});
  conn.on("value",s=>{connesso=s.val()===true;render();if(connesso)void aggiorna();},e=>{connesso=false;render();avvisa(e);});
  return {aggiorna};
}
  if(typeof module==="object"&&module.exports){module.exports=creaVisualizzazioni;return;}
  if(root.CsfPublicViews)return;
  const prefix="/che-si-fa-cerignola/";
  if(location.hostname!=="francescocompierchio.github.io"||!location.pathname.startsWith(prefix))return;
  const pill=document.getElementById("views-pill");
  const permesso=()=>!!root.CsfMetrics?.aggregateAllowed();
  const escluso=()=>{try{const q=new URLSearchParams(location.search);return localStorage.getItem("csf_escludi_visite")==="1"||!!localStorage.getItem("csf_admin_pin")||q.get("admin")==="1"||q.get("escludi")==="1";}catch(_){return true;}};
  const visibile=()=>!document.hidden;
  const mostra=n=>{if(!pill)return;if(n===null){pill.style.display="none";return;}document.getElementById("total-views-count").textContent=n.toLocaleString("it-IT");pill.style.display="inline-flex";};
  const avvisa=e=>console.warn("Visualizzazioni Firebase:",e?.message||e);
  let api=null,avvio=null;
  function carica(src){return new Promise((resolve,reject)=>{const s=document.createElement("script");s.src=src;s.onload=resolve;s.onerror=()=>reject(Error("SDK Firebase non disponibile"));document.head.appendChild(s);});}
  async function avvia(){
    if(api||(!pill&&(!permesso()||escluso()||!visibile())))return;
    if(avvio)return avvio;
    avvio=(async()=>{
      try{
        if(!root.firebase)await carica("https://www.gstatic.com/firebasejs/10.14.1/firebase-app-compat.js");
        if(!root.firebase.database)await carica("https://www.gstatic.com/firebasejs/10.14.1/firebase-database-compat.js");
        if(!root.firebase.apps.length)root.firebase.initializeApp({"apiKey":"AIzaSyB9XXi9bFa6qSFVcQHFc8KgULhK0fxrGfY","authDomain":"chesifa-cerignola.firebaseapp.com","databaseURL":"https://chesifa-cerignola-default-rtdb.europe-west1.firebasedatabase.app","projectId":"chesifa-cerignola","storageBucket":"chesifa-cerignola.firebasestorage.app","messagingSenderId":"953544345505","appId":"1:953544345505:web:4ec5aa4d1468975d1e2de0"});
        if(!pill&&(!permesso()||escluso()||!visibile()))return;
        api=creaVisualizzazioni(root.firebase.database(),permesso,escluso,visibile,mostra,avvisa);
      }catch(e){avvisa(e);}
      finally{avvio=null;}
    })();
    return avvio;
  }
  function aggiorna(){if(api)void api.aggiorna();else void avvia();}
  root.CsfPublicViews={aggiorna};
  document.addEventListener("visibilitychange",aggiorna);
  root.addEventListener("online",aggiorna);
  root.addEventListener("storage",aggiorna);
  root.setInterval(()=>{if(visibile())aggiorna();},60000);
  aggiorna();
})(typeof window==="undefined"?null:window);
