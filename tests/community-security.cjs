/* Eseguire solo con Firebase Emulator Suite, mai contro un DB reale.
   node --test tests/community-security.cjs (verifiche locali)
   CSFC_EMULATOR=1 FIREBASE_DATABASE_EMULATOR_HOST=127.0.0.1:9000 node --test tests/community-security.cjs */
const {test}=require("node:test");
const assert=require("node:assert/strict");
const fs=require("node:fs");
const path=require("node:path");
const vm=require("node:vm");
const read=f=>fs.readFileSync(path.join(__dirname,"..",f),"utf8");
const rules=read("community-database.rules.json");
test("config disattivata e modulo valido: nessun accesso DOM o Firebase a freddo",()=>{
  const context={window:{}};
  vm.runInNewContext(read("community-config.js"),context);
  const config=context.window.CSF_COMMUNITY_CONFIG;
  assert.equal(config.enabled,false);
  assert.equal(config.firebase.projectId,"che-si-fa-community");
  assert.equal(new URL(config.firebase.databaseURL).hostname,"che-si-fa-community-default-rtdb.europe-west1.firebasedatabase.app");
  vm.runInNewContext(read("community.js"),context);
  for(const firebase of [{projectId:"chesifa-cerignola",databaseURL:"https://example.com"},{projectId:"altro",databaseURL:"https://chesifa-cerignola-default-rtdb.europe-west1.firebasedatabase.app"}]){
    vm.runInNewContext(read("community.js"),{window:{CSF_COMMUNITY_CONFIG:{enabled:true,firebase}}});
  }
  assert.equal(JSON.parse(rules).rules[".read"],false);
  assert.equal(JSON.parse(rules).rules[".write"],false);
});
test("modulo collegato senza modificare la logica eventi",()=>{
  const h=read("index.html");
  assert.ok(h.includes('src="community-config.js?v=1"'));
  assert.ok(h.includes('src="community.js?v=1"'));
  assert.ok(h.indexOf('src="community-config.js?v=1"')<h.indexOf('src="community.js?v=1"'));
});
test("regole effettive su emulatore: autorizzazioni, coda e segnalazioni",{skip:process.env.CSFC_EMULATOR!=="1"},async()=>{
  assert.match(process.env.FIREBASE_DATABASE_EMULATOR_HOST||"",/^127\.0\.0\.1:\d+$/);
  const {initializeTestEnvironment,assertSucceeds,assertFails}=require("@firebase/rules-unit-testing");
  const {ref,set,get,query,orderByKey,limitToLast,serverTimestamp,update}=require("firebase/database");
  const [host,port]=process.env.FIREBASE_DATABASE_EMULATOR_HOST.split(":");
  const env=await initializeTestEnvironment({projectId:"demo-csf-community",database:{host,port:Number(port),rules}});
  try{
    const claims={email_verified:true,firebase:{sign_in_provider:"google.com"}};
    const user=env.authenticatedContext("reader",claims).database(), mod=env.authenticatedContext("moderator",claims).database(), guest=env.unauthenticatedContext().database();
    const id="-1234567890123456789";
    const msg={nick:"Utente",text:"Quali eventi ci sono sabato?",createdAt:serverTimestamp(),state:"pending"};
    await env.withSecurityRulesDisabled(async ctx=>{await set(ref(ctx.database()),{settings:{open:true},moderators:{moderator:true}});});
    await assertFails(set(ref(guest,"submissions/reader"),msg));
    await assertFails(set(ref(user,"submissions/other"),msg));
    await assertFails(set(ref(user,"moderators/reader"),true));
    await assertFails(set(ref(user,"published/"+id),{nick:"Utente",text:"spam",createdAt:serverTimestamp()}));
    await assertFails(set(ref(user,"submissions/reader"),{...msg,state:"approved"}));
    await assertSucceeds(set(ref(user,"submissions/reader"),msg));
    await assertFails(set(ref(user,"submissions/reader"),msg));
    await assertFails(get(ref(user,"submissions")));
    await assertFails(get(ref(user,"published")));
    await assertSucceeds(update(ref(mod),{["published/"+id]:{nick:"Utente",text:msg.text,createdAt:serverTimestamp()},["authors/"+id]:"reader","submissions/reader/state":"approved"}));
    await assertSucceeds(get(query(ref(user,"published"),orderByKey(),limitToLast(40))));
    await assertFails(get(query(ref(guest,"published"),orderByKey(),limitToLast(40))));
    await assertFails(get(ref(user,"authors/"+id)));
    await assertFails(set(ref(user,"submissions/reader"),msg));
    await assertSucceeds(set(ref(user,"reports/reader"),{messageId:id,createdAt:serverTimestamp(),state:"pending"}));
    await assertFails(set(ref(user,"reports/reader"),{messageId:id,createdAt:serverTimestamp(),state:"pending"}));
    await assertSucceeds(set(ref(mod,"bans/reader"),true));
    await assertFails(get(query(ref(user,"published"),orderByKey(),limitToLast(40))));
    await assertFails(set(ref(user,"submissions/reader"),msg));
  }finally{await env.cleanup();}
});
