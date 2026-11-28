"use strict";
const {initializeTestEnvironment,assertFails,assertSucceeds}=require("@firebase/rules-unit-testing");
const {ref,get,set,remove,increment,serverTimestamp}=require("firebase/database");
const fs=require("node:fs");
(async()=>{
 const env=await initializeTestEnvironment({projectId:"demo-csf-event-stats",database:{host:"127.0.0.1",port:9000,rules:fs.readFileSync("event-stats.rules.json","utf8")}});
 try{
  await env.withSecurityRulesDisabled(async c=>set(ref(c.database(),"statisticheEventi/foggia-2026-11-28-test/enabled"),true));
  const db=env.unauthenticatedContext().database(),r=p=>ref(db,"statisticheEventi/"+p);
  const event="foggia-2026-11-28-test",v=()=>({count:increment(1),at:serverTimestamp()});
  await assertSucceeds(get(r(event)));
  await assertFails(set(r(event+"/enabled"),false));
  await assertFails(set(r(event+"/fake"),v()));
  await assertFails(set(r("unknown/open"),v()));
  await assertFails(set(r(event+"/open"),{count:10000,at:serverTimestamp()}));
  await assertSucceeds(set(r(event+"/open"),v()));
  await assertFails(set(r(event+"/open"),v()));
  await assertFails(remove(r(event+"/open")));
  await assertSucceeds(set(r(event+"/share"),v()));
  await assertFails(set(r(event+"/poster"),v()));
  await assertFails(set(r(event+"/posterEnabled"),true));
  await env.withSecurityRulesDisabled(async c=>set(ref(c.database(),"statisticheEventi/"+event+"/posterEnabled"),true));
  await assertSucceeds(set(r(event+"/poster"),v()));
  await assertFails(set(r(event+"/poster"),v()));
  await assertFails(set(r(event),{enabled:true,open:{count:10000,at:serverTimestamp()}}));
  await assertFails(set(r(event+"/extra"),true));
  await env.withSecurityRulesDisabled(async c=>set(ref(c.database(),"statisticheEventi/"+event+"/enabled"),false));
  await assertFails(set(r(event+"/share"),v()));
  console.log("OK regole: sola lettura pubblica e incrementi validati su eventi abilitati");
 }finally{await env.cleanup();}
})().then(()=>{require("node:child_process").execFileSync(process.execPath,[require("node:path").join(__dirname,"quick-report-rules.cjs")],{stdio:"inherit",timeout:120000});}).catch(e=>{console.error(e);process.exitCode=1;});
