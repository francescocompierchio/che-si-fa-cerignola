"use strict";
const assert=require("node:assert/strict");
const fs=require("node:fs");
const {chromium}=require("playwright");
const site="https://francescocompierchio.github.io/che-si-fa-cerignola/";
const db="https://chesifa-cerignola-default-rtdb.europe-west1.firebasedatabase.app/statisticheEventi/";
const id="foggia-2026-11-28-test";
const fixture='<!doctype html><meta charset="utf-8"><script src="metrics.js?v=34"></script><article><h2>Evento prova</h2><div id="stats"></div><button id="open">Dettagli</button><button id="share">Condividi</button></article><div style="height:1500px"></div><img id="poster" width="200" height="200" alt="Locandina" src="data:image/svg+xml,%3Csvg%20xmlns=%22http://www.w3.org/2000/svg%22%20width=%22200%22%20height=%22200%22%3E%3Crect%20width=%22200%22%20height=%22200%22%20fill=%22red%22/%3E%3C/svg%3E"><script>const ev={titolo:"Test",citta:"Foggia",dataInizio:"2026-11-28"};CsfMetrics.attachStats(ev,document.querySelector("#stats"),document.querySelector("article"));CsfMetrics.observePoster(ev,document.querySelector("#poster"));document.querySelector("#open").onclick=()=>CsfMetrics.record("csf_event_open",ev);document.querySelector("#share").onclick=()=>CsfMetrics.record("csf_event_share",ev);</script>';
(async()=>{
 const browser=await chromium.launch();
 try{
  for(const mode of ["normal","no","admin"]){
   let count=0,share=0,poster=0,writes=0;
   const page=await browser.newPage({viewport:{width:393,height:852},serviceWorkers:"block"});
   await page.addInitScript(mode=>{if(mode==="no")localStorage.setItem("csf_statistiche_consent_v1","no");if(mode==="admin")localStorage.setItem("csf_escludi_visite","1");},mode);
   await page.route("**/*",async route=>{
    const url=route.request().url();
    if(url===site)return route.fulfill({contentType:"text/html",body:fixture});
    if(url===site+"metrics.js?v=34")return route.fulfill({contentType:"application/javascript",body:fs.readFileSync("metrics.js","utf8")});
    if(url.startsWith(db)){
     if(route.request().method()==="PUT"){
      writes++;assert.deepEqual(route.request().postDataJSON(),{count:{".sv":{increment:1}},at:{".sv":"timestamp"}});
      if(url===db+id+"/open.json")count++;else if(url===db+id+"/share.json")share++;else if(url===db+id+"/poster.json")poster++;else throw Error("Percorso imprevisto");
      return route.fulfill({contentType:"application/json",headers:{"access-control-allow-origin":"*"},body:"{}"});
     }
     if(route.request().method()==="OPTIONS")return route.fulfill({status:204,headers:{"access-control-allow-origin":"*","access-control-allow-methods":"GET,PUT,OPTIONS","access-control-allow-headers":"content-type"}});
     return route.fulfill({contentType:"application/json",headers:{"access-control-allow-origin":"*"},body:JSON.stringify({enabled:true,posterEnabled:true,open:{count},share:{count:share},poster:{count:poster}})});
    }
    return route.abort();
   });
   await page.goto(site);
   const stats=page.locator("[data-csf-event-stats]");
   await stats.waitFor({state:"visible"});
   assert.match(await stats.textContent(),/0 aperture.*0 condivisioni/);
   await page.locator("#open").click();await page.locator("#share").click();
   if(mode==="normal"){
    await page.waitForFunction(()=>document.querySelector("[data-csf-event-stats]").textContent.includes("1 aperture")&&document.querySelector("[data-csf-event-stats]").textContent.includes("1 condivisioni"));
    await page.locator("#open").click();await page.locator("#share").click();
    assert.equal(writes,2);assert.equal(poster,0);
    await page.locator("#poster").scrollIntoViewIfNeeded();
    await page.waitForFunction(()=>document.querySelector("[data-csf-event-stats]").textContent.includes("1 viste locandina"));
    assert.equal(writes,3);
   }else{await page.locator("#poster").scrollIntoViewIfNeeded();await page.waitForTimeout(1300);assert.equal(writes,0);}
   await page.close();
  }
  console.log("OK UI mobile: numeri visibili, incrementi, deduplica, opt-out e amministratore; nessuna richiesta reale");
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
