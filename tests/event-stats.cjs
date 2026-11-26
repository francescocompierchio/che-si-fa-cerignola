"use strict";
const assert=require("node:assert/strict");
const {csfEventStatsKey:key,csfEventStatsData:data,csfEventStatsClient:client}=require("../metrics.js");
const ev={titolo:"La Notte della Musica – Carlito's",citta:"Foggia",dataInizio:"2026-11-28"};
assert.equal(key(ev),"foggia-2026-11-28-la-notte-della-musica-carlito-s");
assert.equal(key({...ev,tipoContenuto:"esperienza"}),null);
assert.notEqual(key(ev),key({...ev,dataInizio:"2026-11-29"}));
assert.equal(data(null),null);
assert.equal(data({enabled:true,open:{count:-1}}),null);
assert.deepEqual(data({enabled:true}),{enabled:true,open:0,share:0});
assert.deepEqual(data({enabled:true,posterEnabled:true}),{enabled:true,open:0,share:0,poster:0,posterEnabled:true});
(async()=>{
 let t=1000,allow=true,visible=true,writes=0,disabled=false,stored={enabled:true,posterEnabled:true},notified;
 const c=client({allowed:()=>allow,visible:()=>visible,now:()=>t,notify:(_,d)=>{notified=d;},request:async(path,o)=>{
   if(o.method==="PUT"){
     writes++;assert.deepEqual(JSON.parse(o.body),{count:{".sv":{increment:1}},at:{".sv":"timestamp"}});
     const m=path.includes("/open")?"open":path.includes("/poster")?"poster":"share";stored[m]={count:(stored[m]?.count||0)+1,at:t};
     return {ok:true};
   }
   return {ok:true,json:async()=>disabled?null:stored};
 }});
 assert.equal(await c.record(ev,"csf_event_open"),true);
 assert.equal(await c.record(ev,"csf_event_open"),false);
 assert.equal(await c.record(ev,"csf_event_share"),true);
 assert.equal(await c.record(ev,"csf_poster_view"),true);
 assert.equal(await c.record(ev,"csf_poster_view"),false);
 assert.equal(writes,3);assert.equal(notified.open,1);assert.equal(notified.share,1);assert.equal(notified.poster,1);
 t+=60001;allow=false;assert.equal(await c.record(ev,"csf_event_open"),false);
 allow=true;visible=false;assert.equal(await c.record(ev,"csf_event_open"),false);
 visible=true;disabled=true;assert.equal(await c.record({...ev,dataInizio:"2026-12-01"},"csf_event_open"),false);
 assert.equal(writes,3);
 const denied=client({allowed:()=>true,visible:()=>true,request:async()=>({ok:false,status:403})});
 assert.equal(await denied.record(ev,"csf_event_open"),false);
 console.log("OK statistiche evento: identità, consenso, deduplica e nessun dato fittizio");
})().catch(e=>{console.error(e);process.exitCode=1;});
