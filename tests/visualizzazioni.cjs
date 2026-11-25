"use strict";
const assert=require("node:assert/strict");
const crea=require("../public-views.js");
async function verificaVisualizzazioni(crea,assert){
  const tick=async()=>{for(let i=0;i<12;i++)await Promise.resolve();};
  function setup({admin=false,ok=true,visibile=true,fallisci=false,n=20}={}){
    const stato={admin,ok,visibile,fallisci,n,transazioni:0},callbacks={},errori=[],valori=[];
    const db={ref:p=>({on:(t,cb,err)=>callbacks[p]={cb,err},transaction:async fn=>{stato.transazioni++;if(stato.fallisci)throw Error("denied");const n=fn(stato.n);if(n===undefined)return {committed:false};stato.n=n;return {committed:true};}})};
    const api=crea(db,()=>stato.ok,()=>stato.admin,()=>stato.visibile,v=>valori.push(v),e=>errori.push(e));
    return {stato,api,errori,valori,callbacks,conn:v=>callbacks[".info/connected"].cb({val:()=>v})};
  }
  let t=setup();t.conn(true);await tick();assert(t.stato.n===21,"nuova apertura");await t.api.aggiorna();assert(t.stato.n===21,"no duplicati");
  t.conn(false);t.conn(true);await tick();assert(t.stato.n===21,"riconnessione");
  t.stato.admin=true;await t.api.aggiorna();assert(t.stato.n===20,"storno admin corrente");
  t=setup({admin:true});t.conn(true);await tick();assert(t.stato.transazioni===0,"admin escluso");
  t=setup({ok:false});t.conn(true);await tick();assert(t.stato.transazioni===0,"rifiuto rispettato");
  t=setup({visibile:false});t.conn(true);await tick();assert(t.stato.transazioni===0,"pagina nascosta");t.stato.visibile=true;await t.api.aggiorna();assert(t.stato.n===21,"apertura visibile");
  t=setup({fallisci:true});t.conn(true);await tick();assert(t.stato.n===20&&t.errori.length===1,"errore senza incremento");t.stato.fallisci=false;await t.api.aggiorna();assert(t.stato.n===21,"recupero");
  t=setup({n:null});t.conn(true);await tick();assert(t.stato.n===1,"inizializzazione");
  const r=t.callbacks["statistiche/visualizzazioniTotali"];r.cb({val:()=>1});assert(t.valori.at(-1)===1,"lettura");r.err(Error("denied"));assert(t.valori.at(-1)===null,"nessun numero fittizio");
}
verificaVisualizzazioni(crea,assert.ok).then(()=>console.log("OK: visualizzazioni, admin, rifiuto, retry, lettura e riconnessioni")).catch(e=>{console.error(e);process.exitCode=1;});
