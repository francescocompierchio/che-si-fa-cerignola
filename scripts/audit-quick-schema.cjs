"use strict";
const assert=require("node:assert/strict");
const crypto=require("node:crypto");
const {initializeApp,cert,deleteApp}=require("firebase-admin/app");
const {getDatabase}=require("firebase-admin/database");
(async()=>{
 const url="https://chesifa-cerignola-default-rtdb.europe-west1.firebasedatabase.app";
 const key=JSON.parse(process.env.FIREBASE_KEY||"null");
 assert.equal(key.project_id,"chesifa-cerignola");
 const app=initializeApp({credential:cert(key),databaseURL:url});
 const id="audit-rapida-"+crypto.randomUUID();
 const db=getDatabase(app),ref=db.ref("segnalazioniDaApprovare/"+id);
 const endpoint=url+"/segnalazioniDaApprovare/"+id+".json";
 const item={tipoSegnalazione:"Segnalazione rapida",titolo:"",fonteUrl:"",descrizione:"AUDIT TECNICO TEMPORANEO — NON PUBBLICARE",notaRapida:"",inviatoIl:new Date().toISOString(),screenshot:"data:image/jpeg;base64,/9j/2Q=="};
 try{
  assert.equal((await ref.get()).exists(),false);
  const write=await fetch(endpoint,{method:"PUT",headers:{"Content-Type":"application/json"},body:JSON.stringify(item)});
  assert.equal(write.ok,true,"Creazione anonima di una segnalazione privata");
  const actual=(await ref.get()).val();
  assert.equal(actual.screenshot,item.screenshot);
  assert.equal(actual.tipoSegnalazione,item.tipoSegnalazione);
  assert.equal(actual.dataInizio,undefined);
  const read=await fetch(endpoint);assert.ok([401,403].includes(read.status),"Lettura anonima negata");
  const update=await fetch(endpoint,{method:"PATCH",headers:{"Content-Type":"application/json"},body:JSON.stringify({titolo:"alterazione non autorizzata"})});
  assert.ok([401,403].includes(update.status),"Modifica anonima negata");
  const del=await fetch(endpoint,{method:"DELETE"});assert.ok([401,403].includes(del.status),"Eliminazione anonima negata");
  console.log("OK Firebase reale: creazione senza account, foto conservata, lettura/modifica/cancellazione anonime negate, nessun evento pubblicato.");
 }finally{await ref.remove();assert.equal((await ref.get()).exists(),false);console.log("OK rimozione della segnalazione tecnica temporanea.");await deleteApp(app);}
})().catch(e=>{console.error("Audit non riuscito: "+e.message.slice(0,200));process.exitCode=1;});
