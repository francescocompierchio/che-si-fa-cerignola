"use strict";
const fs=require("node:fs");
const assert=require("node:assert/strict");
const html=fs.readFileSync("index.html","utf8");
const start=html.indexOf("    function creaContatori(");
const end=html.indexOf("\n\n    try {\n      firebase.initializeApp",start);
assert.ok(start>=0&&end>start);
const crea=new Function(html.slice(start,end)+";return creaContatori;")();
async function verifica(crea,assert){
  const tick=async()=>{for(let i=0;i<16;i++)await Promise.resolve();};
  function scenario({ok=true,admin=false,fallisci=false,fallisciPresenza=false}={}){
    const m=new Map(), l={}, err=[], schermata={}, stato={ok,admin,fallisci,fallisciPresenza,n:10,transazioni:0,creazioni:0,registrazioni:0,rimozioni:0};
    const storage={getItem:k=>m.get(k),setItem:(k,v)=>m.set(k,v),removeItem:k=>m.delete(k)};
    const ref=(p)=>({on:(t,cb,fail)=>{l[p]={cb,fail};},transaction:async(fn)=>{stato.transazioni++;if(stato.fallisci)throw Error("denied");stato.n=fn(stato.n);return {committed:true};},push:()=>{stato.creazioni++;return {onDisconnect:()=>({remove:async()=>{if(stato.fallisciPresenza)throw Error("denied");}}),set:async()=>{stato.registrazioni++;},remove:async()=>{stato.rimozioni++;}};}});
    const api=crea({ref},()=>stato.ok,()=>stato.admin,storage,(k,v)=>schermata[k]=v,(k)=>err.push(k));
    const connetti=v=>l[".info/connected"].cb({val:()=>v});
    return {api,stato,m,err,schermata,l,connetti};
  }
  let t=scenario({fallisci:true});t.connetti(true);await tick();assert(!t.m.has("csf_visitato"),"flag dopo errore");assert(t.err.length===1,"errore visita");
  t.stato.fallisci=false;t.api.aggiorna();await tick();assert(t.stato.n===11&&t.m.has("csf_visitato"),"ritentativo confermato");t.api.aggiorna();await tick();assert(t.stato.transazioni===2&&t.stato.registrazioni===1,"nessun doppione");
  t.connetti(false);t.connetti(true);await tick();assert(t.stato.n===11&&t.stato.registrazioni===2,"riconnessione senza doppia visita");
  t.stato.admin=true;t.api.aggiorna();await tick();assert(t.stato.n===10&&t.stato.rimozioni===1&&!t.m.has("csf_visitato"),"esclusione admin");
  t=scenario({ok:false});t.connetti(true);await tick();assert(t.stato.transazioni===0&&t.stato.creazioni===0,"consenso negato");
  t=scenario({admin:true});t.connetti(true);await tick();assert(t.stato.transazioni===0&&t.stato.creazioni===0,"admin escluso");
  t=scenario({fallisciPresenza:true});t.connetti(true);await tick();assert(t.stato.registrazioni===0,"nessuna presenza senza onDisconnect");
  t.stato.fallisciPresenza=false;t.api.aggiorna();await tick();assert(t.stato.registrazioni===1,"recupero presenza");
  t.l["statistiche/visiteTotali"].cb({val:()=>11});assert(t.schermata.visite===11,"lettura visite");t.l["statistiche/visiteTotali"].fail(Error("denied"));assert(t.schermata.visite===null,"errore lettura");
  t.l["statistiche/utentiOnline"].cb({numChildren:()=>3});assert(t.schermata.online===3,"lettura online");t.connetti(false);assert(t.schermata.online===null&&t.schermata.visite===null,"offline");
}
verifica(crea,assert.ok).then(()=>console.log("OK: contatori Firebase simulati, consenso, admin, conferme e riconnessioni.")).catch(e=>{console.error(e);process.exitCode=1;});
