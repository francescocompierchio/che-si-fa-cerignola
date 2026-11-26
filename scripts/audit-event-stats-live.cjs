"use strict";
const assert=require("node:assert/strict");
const {randomUUID}=require("node:crypto");
const {chromium,webkit,devices}=require("playwright");
const {initializeApp,cert,deleteApp}=require("firebase-admin/app");
const {getDatabase}=require("firebase-admin/database");
const site="https://francescocompierchio.github.io/che-si-fa-cerignola/";
const dbUrl="https://chesifa-cerignola-default-rtdb.europe-west1.firebasedatabase.app";
const credential=JSON.parse(process.env.EVENT_STATS_FIREBASE_SERVICE_ACCOUNT||"null");
if(!credential||credential.project_id!=="chesifa-cerignola")throw Error("Credenziale progetto errata");
const app=initializeApp({credential:cert(credential),databaseURL:dbUrl}),db=getDatabase(app);
const stats=db.ref("statisticheEventi");
const ids=[];
const slug=v=>String(v).normalize("NFD").replace(/[\u0300-\u036f]/g,"").toLowerCase().replace(/[^a-z0-9]+/g,"-").replace(/^-|-$/g,"");
const wait=async(fn,label)=>{for(let i=0;i<35;i++){if(await fn())return;await new Promise(r=>setTimeout(r,500));}throw Error("Timeout: "+label);};
(async()=>{
 try{
  const snapshot=(await stats.get()).val()||{},active=Object.entries(snapshot).filter(([id,v])=>v?.enabled&&!id.includes("csf-collaudo"));
  const summary={events:active.length,posters:active.filter(([,v])=>v.posterEnabled).length,open:0,share:0,poster:0,withInteractions:0};
  for(const [,v] of active){for(const k of ["open","share","poster"])summary[k]+=v[k]?.count||0;if(["open","share","poster"].some(k=>v[k]?.count>0))summary.withInteractions++;}
  console.log("STATISTICHE REALI (sola lettura): "+JSON.stringify(summary));
  const hermes=active.find(([id])=>id.includes("dinner-show-hermes-club"));
  if(hermes)console.log("HERMES (sola lettura): "+JSON.stringify({open:hermes[1].open?.count||0,share:hermes[1].share?.count||0,poster:hermes[1].poster?.count||0}));
  for(const [name,engine,options] of [["Android",chromium,devices["Pixel 7"]],["iPhone WebKit",webkit,devices["iPhone 13"]]]){
   const browser=await engine.launch();
   const title="CSF collaudo "+randomUUID();
   const date=new Intl.DateTimeFormat("sv-SE",{timeZone:"Europe/Rome",year:"numeric",month:"2-digit",day:"2-digit"}).format(new Date());
   const id="cerignola-"+date+"-"+slug(title);
   ids.push(id);const ref=stats.child(id);
   await ref.set({enabled:true,posterEnabled:true});
   const context=await browser.newContext({...options,serviceWorkers:"block",timezoneId:"Europe/Rome"});
   try{
    await context.addInitScript(()=>{localStorage.setItem("csf_music_v1","off");localStorage.removeItem("csf_escludi_visite");localStorage.removeItem("csf_admin_pin");localStorage.removeItem("csf_statistiche_consent_v1");});
    const page=await context.newPage(),writes=[],responses=[];
    page.on("response",r=>{if(r.url().includes("/statisticheEventi/"+id+"/"))responses.push([r.request().method(),r.status()]);});
    await context.route("**/*",route=>{
     const url=route.request().url(),method=route.request().method();
     if(url.startsWith(dbUrl+"/statisticheEventi/"+id+".json")||url.startsWith(dbUrl+"/statisticheEventi/"+id+"/")){
      if(method==="PUT")writes.push(url.split("/").pop());
      return route.continue();
     }
     // Nessuna interazione di collaudo può raggiungere contatori reali o servizi analytics.
     if(url.startsWith(dbUrl+"/statisticheEventi/")&&method==="GET")return route.fulfill({contentType:"application/json",headers:{"access-control-allow-origin":"*"},body:"null"});
     if(url.startsWith(site)&&["GET","HEAD"].includes(method))return route.continue();
     return route.abort();
    });
    await page.goto(site+"?verifica="+randomUUID(),{waitUntil:"domcontentloaded"});
    await page.waitForFunction(()=>typeof renderEventi==="function"&&Array.isArray(tuttiEventiAttivi)&&tuttiEventiAttivi.length>0&&typeof CsfMetrics?.observePoster==="function");
    await page.evaluate(({title,date})=>{
      const ev={tipoContenuto:"evento",titolo:title,citta:"Cerignola",categoria:"Locali & Serate",dataInizio:date,dataFine:date,dataTesto:"Collaudo temporaneo",luogo:"Test isolato",descrizione:"Non pubblicato",inEvidenza:true,locandinaUrl:"https://francescocompierchio.github.io/che-si-fa-cerignola/locandine/hermes-dinner-show-2026-12-05.avif"};
      tuttiEventiAttivi=[ev];filtroAttivo="ALL";queryRicerca="";modalitaRapida="ALL";filtroSmart="ALL";dataSelezionata="";fineDataSelezionata="";renderEventi();
    },{title,date});
    const card=page.locator("#events-container details").filter({hasText:title});await card.waitFor();
    const label=card.locator("[data-csf-event-stats]");
    await label.scrollIntoViewIfNeeded();
    await label.waitFor({state:"visible"});
    assert.match(await label.textContent(),/0 viste locandina.*0 aperture.*0 condivisioni/);
    await card.locator("summary").click();
    await wait(async()=> (await ref.child("open/count").get()).val()===1,"apertura "+name);
    const poster=card.locator("img.event-poster");await poster.scrollIntoViewIfNeeded();
    await page.waitForFunction(t=>{const img=[...document.querySelectorAll("img.event-poster")].find(x=>x.alt.includes(t));return img?.complete&&img.naturalWidth>0;},title);
    await wait(async()=> (await ref.child("poster/count").get()).val()===1,"vista locandina "+name);
    await card.getByRole("button",{name:"Condividi evento",exact:true}).click();
    await wait(async()=> (await ref.child("share/count").get()).val()===1,"condivisione "+name);
    await wait(async()=>/1 viste locandina.*1 aperture.*1 condivisioni/.test(await label.textContent()),"aggiornamento numeri "+name);
    console.log("OK "+name+": scheda pubblicata + immagine caricata + tre scritture Firebase reali + UI aggiornata: "+JSON.stringify(writes));
   }finally{await context.close();await browser.close();await ref.remove();}
  }
 }finally{for(const id of ids)await stats.child(id).remove();await deleteApp(app);}
})().catch(e=>{console.error("COLLAUDO NON SUPERATO: "+String(e.message).slice(0,500));process.exitCode=1;});
