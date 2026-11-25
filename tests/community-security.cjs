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
test("config Community separata e disattivazione sicura: nessun accesso DOM o Firebase quando spenta",()=>{
  const context={window:{}};
  vm.runInNewContext(read("community-config.js"),context);
  const config=context.window.CSF_COMMUNITY_CONFIG;
  assert.equal(config.enabled,true);
  assert.match(config.googleClientId,/^1064417630484-[a-z0-9]+\.apps\.googleusercontent\.com$/);
  assert.ok(!/signInWithRedirect\s*\(/.test(read("community.js")));
  assert.equal((read("community.js").match(/signInWithPopup\s*\(/g)||[]).length,1);
  assert.ok(read("community.js").includes("signInWithCredential"));
  assert.equal(config.firebase.projectId,"che-si-fa-community");
  assert.equal(new URL(config.firebase.databaseURL).hostname,"che-si-fa-community-default-rtdb.europe-west1.firebasedatabase.app");
  for (const disabled of [null,{...config,enabled:false}]) {
    vm.runInNewContext(read("community.js"),{window:{CSF_COMMUNITY_CONFIG:disabled}});
  }
  for(const firebase of [{projectId:"chesifa-cerignola",databaseURL:"https://example.com"},{projectId:"altro",databaseURL:"https://chesifa-cerignola-default-rtdb.europe-west1.firebasedatabase.app"}]){
    vm.runInNewContext(read("community.js"),{window:{CSF_COMMUNITY_CONFIG:{enabled:true,firebase}}});
  }
  assert.equal(JSON.parse(rules).rules[".read"],false);
  assert.equal(JSON.parse(rules).rules[".write"],false);
});
test("modulo collegato senza modificare la logica eventi",()=>{
  const h=read("index.html");
  assert.ok(h.includes('src="community-config.js?v=2"'));
  assert.ok(h.includes('src="community.js?v=4"'));
  assert.ok(h.indexOf('src="community-config.js?v=2"')<h.indexOf('src="community.js?v=4"'));
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

test("accesso Google: consenso, pulsante GIS, scambio credenziale Firebase senza popup Firebase",async()=>{
  const nodes=[];
  class El{
    constructor(tag){this.tag=tag;this.children=[];this.hidden=false;this.checked=false;this.clientWidth=260;this.events={};nodes.push(this);}
    setAttribute(k,v){this[k]=v;if(k==="hidden")this.hidden=true;}
    append(...x){this.children.push(...x);}
    replaceChildren(...x){this.children=x;}
    addEventListener(k,f){this.events[k]=f;}
    focus(){}
    remove(){}
  }
  let opts,rendered=0,exchanges=0,popupCalls=0,credentialInput=null,callback;
  const auth={onAuthStateChanged:f=>{callback=f;return ()=>{}},signInWithCredential:async c=>{exchanges++;credentialInput=c;},signInWithPopup:async()=>{popupCalls++;},signOut:async()=>{}};
  const db={goOffline(){},goOnline(){}};
  class GoogleAuthProvider { static credential(t){return {idToken:t};} }
  const firebase={initializeApp:()=>({auth:()=>auth,database:()=>db}),auth:{GoogleAuthProvider}};
  const google={accounts:{id:{initialize:o=>opts=o,renderButton:()=>rendered++,disableAutoSelect(){}}}};
  const window={firebase,google};const document={createElement:t=>new El(t),createTextNode:t=>t,body:new El("body"),head:new El("head"),addEventListener(){}};
  vm.runInNewContext(read("community-config.js"),{window});
  vm.runInNewContext(read("community.js"),{window,document,firebase,console});
  const el=id=>nodes.find(n=>n.id===id), login=nodes.find(n=>n.textContent==="Accedi con Google");
  await el("csfc-toggle").onclick();await new Promise(r=>setImmediate(r));
  assert.equal(typeof callback,"function");
  await login.onclick();assert.equal(rendered,0);
  await el("csfc-login-alternate").onclick();assert.equal(popupCalls,0);
  el("csfc-consent").checked=true;await login.onclick();
  assert.equal(rendered,1);assert.equal(opts.ux_mode,"popup");assert.equal(opts.auto_select,false);
  assert.equal(opts.client_id,window.CSF_COMMUNITY_CONFIG.googleClientId);
  assert.equal(el("csfc-login-alternate").hidden,false);
  await opts.callback({credential:"mock-token"});assert.equal(exchanges,1);assert.equal(credentialInput.idToken,"mock-token");
  el("csfc-consent").checked=false;await opts.callback({credential:"ignored"});assert.equal(exchanges,1);
  await el("csfc-login-alternate").onclick();assert.equal(popupCalls,0);
  el("csfc-consent").checked=true;await el("csfc-login-alternate").onclick();assert.equal(popupCalls,1);
});
