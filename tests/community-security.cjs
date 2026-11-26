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
  assert.ok(!/signInWithPopup\s*\(/.test(read("community.js")));
  assert.ok(read("community-auth-callback.js").includes("signInWithCredential"));
  assert.ok(read("community-auth-callback.js").includes("history.replaceState"));
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
  assert.ok(h.includes('src="community.js?v=10"'));
  assert.ok(h.indexOf('src="community-config.js?v=2"')<h.indexOf('src="community.js?v=10"'));
});
test("regole effettive su emulatore: autorizzazioni, coda e segnalazioni",{skip:process.env.CSFC_EMULATOR!=="1"},async()=>{
  assert.match(process.env.FIREBASE_DATABASE_EMULATOR_HOST||"",/^127\.0\.0\.1:\d+$/);
  const {initializeTestEnvironment,assertSucceeds,assertFails}=require("@firebase/rules-unit-testing");
  const {ref,set,get,query,orderByKey,limitToLast,serverTimestamp,update}=require("firebase/database");
  const [host,port]=process.env.FIREBASE_DATABASE_EMULATOR_HOST.split(":");
  const env=await initializeTestEnvironment({projectId:"demo-csf-community",database:{host,port:Number(port),rules}});
  try{
    const claims={email:"mario@example.com",email_verified:true,firebase:{sign_in_provider:"google.com"}};
    const user=env.authenticatedContext("reader",claims).database(), mod=env.authenticatedContext("moderator",claims).database(), guest=env.unauthenticatedContext().database();
    const id="-1234567890123456789";
    const msg={nick:"mar",domain:"example.com",email:"mario@example.com",shareEmail:true,text:"Quali eventi ci sono sabato?",createdAt:serverTimestamp(),state:"pending"};
    await env.withSecurityRulesDisabled(async ctx=>{await set(ref(ctx.database()),{settings:{open:true},moderators:{moderator:true}});});
    await assertFails(set(ref(guest,"submissions/reader"),msg));
    await assertFails(set(ref(user,"submissions/other"),msg));
    await assertFails(set(ref(user,"moderators/reader"),true));
    await assertFails(set(ref(user,"published/"+id),{nick:"Utente",text:"spam",createdAt:serverTimestamp()}));
    await assertFails(set(ref(user,"submissions/reader"),{...msg,state:"approved"}));
    await assertFails(set(ref(user,"submissions/reader"),{...msg,nick:"abc"}));
    await assertFails(set(ref(user,"submissions/reader"),{...msg,nick:"ma"}));
    await assertFails(set(ref(user,"submissions/reader"),{...msg,domain:"evil.com"}));
    const {email,shareEmail,...legacy}=msg;
    await assertFails(set(ref(user,"submissions/reader"),legacy));
    await assertFails(set(ref(user,"submissions/reader"),{...legacy,email}));
    await assertFails(set(ref(user,"submissions/reader"),{...legacy,shareEmail:true}));
    await assertFails(set(ref(user,"submissions/reader"),{...msg,shareEmail:false}));
    await assertFails(set(ref(user,"submissions/reader"),{...msg,email:"maria@example.com",shareEmail:true}));
    await assertFails(set(ref(mod,"submissions/reader"),{...msg,email:"mario@example.com",shareEmail:true}));
    const second=env.authenticatedContext("second",claims).database();
    await assertSucceeds(set(ref(second,"submissions/second"),{...msg,email:"mario@example.com",shareEmail:true}));
    await assertSucceeds(set(ref(user,"submissions/reader"),msg));
    await assertFails(set(ref(user,"submissions/reader"),msg));
    await assertFails(get(ref(user,"submissions")));
    await assertFails(get(ref(user,"published")));
    const approved={["published/"+id]:{nick:"mario@example.com",text:msg.text,createdAt:serverTimestamp()},["authors/"+id]:"reader","submissions/reader/state":"approved"};
    await assertFails(update(ref(mod),approved));
    await env.withSecurityRulesDisabled(async ctx=>{await update(ref(ctx.database()),approved);});
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

test("OIDC: ritorno diretto, nonce, state monouso, scadenza, nessun access token",()=>{
  const {webcrypto}=require("node:crypto");
  const window={};vm.runInNewContext(read("community-auth-flow.js"),{window,URL,URLSearchParams,Uint8Array,atob});
  const api=window.CsfCommunityOIDC;
  const client="1064417630484-example.apps.googleusercontent.com",now=1700000000000;
  const store=new Map(),storage={setItem:(k,v)=>store.set(k,v),getItem:k=>store.get(k),removeItem:k=>store.delete(k)};
  const start=()=>new URL(api.start(client,storage,webcrypto,now));
  function fragment(u,override={},state=u.searchParams.get("state")){
    const data={aud:client,iss:"https://accounts.google.com",sub:"test",email_verified:true,nonce:u.searchParams.get("nonce"),iat:now/1000,exp:now/1000+3600,...override};
    const tok="header."+Buffer.from(JSON.stringify(data)).toString("base64url")+".signature";
    return "#"+new URLSearchParams({state,id_token:tok}).toString();
  }
  let u=start();
  assert.equal(u.origin,"https://accounts.google.com");
  assert.equal(u.searchParams.get("response_type"),"id_token");
  assert.equal(u.searchParams.get("redirect_uri"),api.CALLBACK);
  assert.equal(u.searchParams.get("state").length,64);
  assert.notEqual(u.searchParams.get("state"),u.searchParams.get("nonce"));
  assert.throws(()=>api.consume(fragment(u,{},"wrong"),client,storage,now),/session/);
  assert.ok(api.consume(fragment(u),client,storage,now).endsWith(".signature"));
  assert.throws(()=>api.consume(fragment(u),client,storage,now),/session/);
  for(const bad of [{nonce:"wrong"},{aud:"other"},{iss:"https://evil.example"},{email_verified:false},{exp:now/1000-1}]){
    u=start();assert.throws(()=>api.consume(fragment(u,bad),client,storage,now),/credential/);
  }
  u=start();assert.throws(()=>api.consume(fragment(u),client,storage,now+600001),/session/);
  u=start();assert.throws(()=>api.consume("#"+new URLSearchParams({state:u.searchParams.get("state"),error:"access_denied"}),client,storage,now),/cancelled/);
});
test("sessione Community LOCAL: riapertura senza nuovo login",async()=>{
  const nodes=[];
  class El{constructor(tag){this.tag=tag;this.hidden=false;this.children=[];nodes.push(this);}setAttribute(k,v){this[k]=v;if(k==="hidden")this.hidden=true;}append(...x){this.children.push(...x);}replaceChildren(...x){this.children=x;}addEventListener(){}focus(){}}
  let persistence,callback,navigations=0;
  const auth={currentUser:{uid:"test",emailVerified:true},setPersistence:async p=>{persistence=p;},onAuthStateChanged:f=>{callback=f;f(auth.currentUser);return()=>{}},signOut:async()=>{}};
  const db={goOffline(){},goOnline(){},ref:()=>({once:async()=>({val:()=>false})})};
  const firebase={initializeApp:()=>({auth:()=>auth,database:()=>db}),auth:{Auth:{Persistence:{LOCAL:"local"}}}};
  const window={firebase,CsfCommunityOIDC:{start:()=>"https://accounts.google.com/test"}},document={createElement:t=>new El(t),body:new El("body"),head:new El("head"),addEventListener(){}};
  const location={search:"",assign:()=>navigations++};
  vm.runInNewContext(read("community-config.js"),{window});
  vm.runInNewContext(read("community.js"),{window,document,firebase,location,URLSearchParams});
  const el=id=>nodes.find(n=>n.id===id),login=nodes.find(n=>n.textContent==="Accedi con Google");
  await el("csfc-toggle").onclick();
  assert.equal(persistence,"local");
  assert.equal(login.hidden,true);
  assert.equal(el("csfc-consent"),undefined);
  assert.equal(el("csfc-share-email"),undefined);
  assert.match(el("csfc-email-notice").textContent,/indirizzo Google completo/);
  await el("csfc-toggle").onclick();await el("csfc-toggle").onclick();
  assert.equal(login.hidden,true);assert.equal(navigations,0);
});
