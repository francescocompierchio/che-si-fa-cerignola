"use strict";
const {initializeTestEnvironment,assertFails,assertSucceeds}=require("@firebase/rules-unit-testing");
const {ref,get,set,remove}=require("firebase/database");
const fragment=require("../docs/segnalazioni-validation.fragment.json");
(async()=>{
 const rules={rules:{".read":false,".write":false,segnalazioniDaApprovare:{".read":"auth != null && auth.uid == 'admin-test'","$id":{".write":"(!data.exists() && newData.exists()) || (auth != null && auth.uid == 'admin-test' && !newData.exists())",...fragment}}}};
 const env=await initializeTestEnvironment({projectId:"demo-csf-event-stats",database:{host:"127.0.0.1",port:9000,rules:JSON.stringify(rules)}});
 try{
  const db=env.unauthenticatedContext().database(),admin=env.authenticatedContext("admin-test").database(),r=(id,d=db)=>ref(d,"segnalazioniDaApprovare/"+id);
  const base={tipoSegnalazione:"Segnalazione rapida",titolo:"DJ Set",luogo:"Sala prova",citta:"Cerignola",dataInizio:"2027-01-02",dataFine:"2027-01-02",dataTesto:"Ore 22:30",inviatoIl:"2026-11-27T13:00:00Z",fonteUrl:"https://example.org/evento"};
  await assertSucceeds(set(r("valid"),base));
  await assertFails(get(r("valid")));
  for(const key of ["titolo","luogo","citta","dataInizio","dataFine","dataTesto","inviatoIl"]){const x={...base};delete x[key];await assertFails(set(r("missing-"+key),x));}
  await assertFails(set(r("blank"),{...base,titolo:"   "}));
  for(const [i,blank] of ["\t\n","\u00a0","\u2003"].entries()){
   for(const key of ["titolo","luogo","citta"])await assertFails(set(r("blank-"+i+"-"+key),{...base,[key]:blank.repeat(3)}));
  }
  await assertSucceeds(set(r("accented"),{...base,titolo:"È già festa",luogo:"Caffè",citta:"Cerignola"}));
  await assertFails(set(r("url-space"),{...base,fonteUrl:"https://example.org/a b"}));
  await assertFails(set(r("url-tab"),{...base,fonteUrl:"https://example.org/a\tb"}));
  await assertFails(set(r("bad-time"),{...base,dataTesto:"Ore 25:00"}));
  await assertFails(set(r("bad-date"),{...base,dataInizio:"2027-13-40"}));
  await assertFails(set(r("no-source"),{...base,fonteUrl:""}));
  await assertFails(set(r("no-type"),{...base,tipoSegnalazione:"altro"}));
  await assertSucceeds(set(r("photo"),{...base,fonteUrl:"",screenshot:"data:image/jpeg;base64,AAAA"}));
  await assertSucceeds(set(r("manager"),{...base,tipoSegnalazione:"Evento / Serata",fonteUrl:"",dataTesto:"2027-01-02 · 22:30",contatto:"Contatto prova",categoria:"Locali & Serate"}));
  await assertSucceeds(get(r("valid",admin)));
  await assertSucceeds(remove(r("valid",admin)));
  console.log("OK regole minime segnalazioni");
 }finally{await env.cleanup();}
})().catch(e=>{console.error(e);process.exitCode=1;});
