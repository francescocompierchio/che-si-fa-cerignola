"use strict";
const assert=require("node:assert/strict");
const {randomUUID}=require("node:crypto");
const {initializeApp,cert,deleteApp}=require("firebase-admin/app");
const {getDatabase}=require("firebase-admin/database");
const base="https://chesifa-cerignola-default-rtdb.europe-west1.firebasedatabase.app";
const credential=JSON.parse(process.env.EVENT_STATS_FIREBASE_SERVICE_ACCOUNT||"null");
if(!credential||credential.project_id!=="chesifa-cerignola")throw Error("Credenziale progetto eventi mancante o errata");
const app=initializeApp({credential:cert(credential),databaseURL:base});
const db=getDatabase(app);
const id="csf-collaudo-"+randomUUID(),path="statisticheEventi/"+id,test=db.ref(path);
const url=p=>base+"/"+p+".json";
const body={count:{".sv":{increment:1}},at:{".sv":"timestamp"}};
async function request(p,method="GET",value){
 const r=await fetch(url(p),{method,cache:"no-store",signal:AbortSignal.timeout(15000),...(value===undefined?{}:{headers:{"Content-Type":"application/json"},body:JSON.stringify(value)})});
 return {status:r.status,ok:r.ok,data:await r.json()};
}
async function reject(p,method,value){const r=await request(p,method,value);assert.ok([401,403].includes(r.status),"Scrittura non autorizzata non rifiutata: "+r.status);}
(async()=>{
 try{
  const snapshot=(await db.ref("statisticheEventi").get()).val()||{};
  assert.ok(Object.entries(snapshot).some(([k,v])=>!k.startsWith("csf-collaudo-")&&v?.enabled===true),"Nessun evento reale registrato");
  // ID isolato, non associato a eventi visibili, rimosso sempre dopo il test.
  await test.set({enabled:true,posterEnabled:true});
  await reject(path+"/posterEnabled","PUT",false);
  assert.equal((await request(path)).data.enabled,true);
  await reject(path+"/enabled","PUT",false);
  await reject(path+"/open","PUT",{count:10000,at:{".sv":"timestamp"}});
  for(const metric of ["open","share","poster"]){
   const r=await request(path+"/"+metric,"PUT",body);
   assert.ok(r.ok,"Incremento reale non accettato: "+r.status);
   assert.equal((await request(path+"/"+metric)).data.count,1);
   await reject(path+"/"+metric,"DELETE");
   await reject(path+"/"+metric,"PUT",{count:99999,at:{".sv":"timestamp"}});
  }
  await reject("statisticheEventi/"+id+"-nonregistrato/open","PUT",body);
  await reject(path+"/extra","PUT",true);
  await test.child("enabled").set(false);
  await reject(path+"/open","PUT",body);
  console.log("OK produzione: apertura, condivisione e vista locandina persistono; scritture arbitrarie, eliminazioni e nodi non abilitati rifiutati.");
 }finally{
  try{await test.remove();console.log("Nodo temporaneo rimosso.");}finally{await deleteApp(app);}
 }
})().catch(e=>{console.error("Collaudo produzione non completato: "+String(e.message).slice(0,200));process.exitCode=1;});
