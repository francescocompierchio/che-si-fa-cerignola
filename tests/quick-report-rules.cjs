"use strict";
const {initializeTestEnvironment,assertFails,assertSucceeds}=require("@firebase/rules-unit-testing");
const {ref,get,set,remove}=require("firebase/database");
const fragment=require("../docs/segnalazioni-validation.fragment.json");
(async()=>{
 const rules={rules:{".read":false,".write":false,segnalazioniDaApprovare:{".read":"auth != null && auth.uid == 'admin-test'","$id":{".write":"(!data.exists() && newData.exists()) || (auth != null && auth.uid == 'admin-test' && !newData.exists())",...fragment}}}};
 const env=await initializeTestEnvironment({projectId:"demo-csf-event-stats",database:{host:"127.0.0.1",port:9000,rules:JSON.stringify(rules)}});
 try{
  const db=env.unauthenticatedContext().database(),admin=env.authenticatedContext("admin-test").database(),r=(id,d=db)=>ref(d,"segnalazioniDaApprovare/"+id);
  const base={tipoSegnalazione:"Segnalazione rapida",titolo:"DJ Set",luogo:"Sala prova",citta:"Cerignola",dataInizio:"2027-01-02",dataFine:"2027-01-02",dataTesto:"Ore 22:30",descrizione:"Musica dal vivo",inviatoIl:"2026-11-27T13:00:00Z",fonteUrl:"https://example.org/evento",screenshot:"data:image/jpeg;base64,AAAA"};
  await assertSucceeds(set(r("valid"),base));
  await assertFails(get(r("valid")));
  await assertFails(set(r("valid"),{...base,titolo:"Modificato"}));
  await assertFails(remove(r("valid")));
  for(const key of ["tipoSegnalazione","titolo","luogo","citta","dataInizio","dataFine","dataTesto","descrizione","inviatoIl","screenshot"]){const x={...base};delete x[key];await assertFails(set(r("missing-"+key),x));}
  for(const [i,blank] of ["   ","\t\n","\u00a0","\u2003"].entries()){
   for(const key of ["titolo","luogo","citta","descrizione"])await assertFails(set(r("blank-"+i+"-"+key),{...base,[key]:blank.repeat(3)}));
  }
  await assertSucceeds(set(r("accented"),{...base,titolo:"È già festa",luogo:"Caffè",citta:"Cerignola"}));
  await assertSucceeds(set(r("multiline"),{...base,descrizione:"Musica\nDal vivo"}));
  await assertFails(set(r("url-space"),{...base,fonteUrl:"https://example.org/a b"}));
  await assertFails(set(r("url-tab"),{...base,fonteUrl:"https://example.org/a\tb"}));
  await assertFails(set(r("bad-time"),{...base,dataTesto:"Ore 25:00"}));
  await assertFails(set(r("bad-date"),{...base,dataInizio:"2027-13-40"}));
  await assertFails(set(r("bad-photo"),{...base,screenshot:"data:image/png;base64,AAAA"}));
  await assertFails(set(r("oversized-photo"),{...base,screenshot:"data:image/jpeg;base64,"+"A".repeat(240000)}));
  await assertFails(set(r("no-type"),{...base,tipoSegnalazione:"altro"}));
  await assertSucceeds(set(r("photo"),{...base,fonteUrl:""}));
  const {screenshot,...managerBase}=base;
  const manager={...managerBase,tipoSegnalazione:"Evento / Serata",fonteUrl:"",dataTesto:"2027-01-02 · 22:30",contatto:"Contatto prova",categoria:"Locali & Serate"};
  await assertSucceeds(set(r("manager"),manager));
  await assertFails(set(r("manager-no-contact"),{...manager,contatto:""}));
  await assertSucceeds(get(r("valid",admin)));
  await assertSucceeds(remove(r("valid",admin)));
  console.log("OK regole minime segnalazioni e conservazione dei permessi di test");
 }finally{await env.cleanup();}
})().catch(e=>{console.error(e);process.exitCode=1;});
