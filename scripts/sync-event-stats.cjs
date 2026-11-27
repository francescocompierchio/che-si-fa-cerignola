"use strict";
const fs=require("node:fs");
const {csfEventStatsKey}=require("../metrics.js");
const {initializeApp,cert,deleteApp}=require("firebase-admin/app");
const {getDatabase}=require("firebase-admin/database");
const today=new Intl.DateTimeFormat("sv-SE",{timeZone:"Europe/Rome",year:"numeric",month:"2-digit",day:"2-digit"}).format(new Date());
const wanted=JSON.parse(fs.readFileSync("event-stats.rules.json","utf8")).rules.statisticheEventi;
const canon=x=>x&&typeof x==="object"?Array.isArray(x)?x.map(canon):Object.fromEntries(Object.keys(x).sort().map(k=>[k,canon(x[k])])):x;
const same=(a,b)=>JSON.stringify(canon(a))===JSON.stringify(canon(b));
(async()=>{
 const credential=JSON.parse(process.env.EVENT_STATS_FIREBASE_SERVICE_ACCOUNT||"null");
 if(!credential||credential.project_id!=="chesifa-cerignola")throw Error("Credenziale del progetto eventi non configurata o progetto errato");
 const app=initializeApp({credential:cert(credential),databaseURL:"https://chesifa-cerignola-default-rtdb.europe-west1.firebasedatabase.app"});
 try{
  const db=getDatabase(app),existing=await db.getRulesJSON();
  if(!existing?.rules||![undefined,false,"false"].includes(existing.rules[".write"]))throw Error("Regole superiori da verificare: nessuna modifica automatica");
  const actual=existing.rules.statisticheEventi;
  if(!same(actual,wanted)){
   const legacy=JSON.parse(JSON.stringify(wanted));
   delete legacy.$id.posterEnabled;
   legacy.$id.$metric['.write']="$id.matches(/^[a-z0-9-]{1,180}$/) && ($metric == 'open' || $metric == 'share') && root.child('statisticheEventi').child($id).child('enabled').val() == true && newData.exists() && newData.hasChildren(['count','at']) && newData.child('count').isNumber() && newData.child('count').val() <= 1000000000 && newData.child('count').val() == (data.exists() ? data.child('count').val() + 1 : 1) && newData.child('at').val() == now && (!data.exists() || data.child('at').val() <= now - 2000)";
   if((actual!==undefined&&!same(actual,legacy))||process.env.EVENT_STATS_ACTIVATE!=="true")throw Error("Regole statistiche non attive o differenti: nessuna modifica");
   await db.setRules(JSON.stringify({ ...existing,rules:{...existing.rules,statisticheEventi:wanted}}));
   const confirmed=await db.getRulesJSON();
   if(!same(confirmed?.rules?.statisticheEventi,wanted))throw Error("Regole non confermate");
  }
  const automatic=JSON.parse(fs.readFileSync("eventi.json","utf8"));
  const match=fs.readFileSync("index.html","utf8").match(/const eventiEditoriali = (\[[\s\S]*?\]);/);
  if(!Array.isArray(automatic)||!match)throw Error("Archivio non valido");
  const manual=(await db.ref("eventiManuali").get()).val()||{};
  const events=[...automatic,...JSON.parse(match[1]),...Object.values(manual)].filter(e=>e&&typeof e.dataInizio==="string"&&String(e.dataFine||e.dataInizio)>=today);
  const active=new Set(events.map(csfEventStatsKey).filter(Boolean));
  const posters=new Set(events.filter(e=>{try{return ["http:","https:"].includes(new URL(e.locandinaUrl).protocol)||(typeof e.locandinaUrl==="string"&&e.locandinaUrl.length<=240000&&/^data:image\/jpeg;base64,[A-Za-z0-9+/]+={0,2}$/.test(e.locandinaUrl));}catch(_){return false;}}).map(csfEventStatsKey).filter(Boolean));
  if(!active.size)throw Error("Archivio vuoto: nessuna disattivazione");
  const r=db.ref("statisticheEventi"),previous=(await r.get()).val()||{},updates={};
  for(const id of active){if(previous[id]?.enabled!==true)updates[id+"/enabled"]=true;if(posters.has(id)&&previous[id]?.posterEnabled!==true)updates[id+"/posterEnabled"]=true;else if(!posters.has(id)&&previous[id]?.posterEnabled===true)updates[id+"/posterEnabled"]=false;}
  for(const [id,value] of Object.entries(previous))if(value?.enabled===true&&!active.has(id))updates[id+"/enabled"]=false;
  if(Object.keys(updates).length)await r.update(updates);
  console.log("Eventi abilitati: "+active.size+"; modifiche registro: "+Object.keys(updates).length);
 }finally{await deleteApp(app);}
})().catch(e=>{console.error("Sincronizzazione non completata: "+String(e.message).slice(0,200));process.exitCode=1;});
