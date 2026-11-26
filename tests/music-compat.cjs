"use strict";
const {chromium,webkit,devices}=require("playwright");
const assert=require("node:assert/strict");
(async()=>{
  for(const [name,engine,options] of [["iPhone WebKit",webkit,devices["iPhone 13"]],["Android Chromium",chromium,devices["Pixel 7"]]]){
    const browser=await engine.launch();
    try{
      const ctx=await browser.newContext({...options,serviceWorkers:"block"});
      const p=await ctx.newPage();
      await p.route("**/*",route=>route.request().url().startsWith("http://127.0.0.1:8765/")?route.continue():route.abort());
      await p.addInitScript(()=>{if(!sessionStorage.getItem("test_music_init")){localStorage.setItem("csf_music_v1","off");sessionStorage.setItem("test_music_init","1");}});
      // Fixture minima: carica esattamente lo script di produzione senza modificare i contatori.
      await p.addInitScript(()=>{const calls=[];Object.defineProperty(window,"__audioSessionCalls",{value:calls});const mock={get type(){return calls.at(-1)||"auto";},set type(v){calls.push(v);}};try{Object.defineProperty(navigator,"audioSession",{configurable:true,value:mock});}catch(_){}});
      await p.goto("http://127.0.0.1:8765/tests/music-fixture.html");
      const button=p.locator("#csf-music-toggle");
      await button.waitFor();
      assert.equal(await button.getAttribute("aria-pressed"),"false",name+" inizialmente spenta");
      await button.tap();
      await p.waitForFunction(()=>document.querySelector("#csf-music-toggle").dataset.musicState==="playing",null,{timeout:25000});
      if(name.startsWith("iPhone")){
        assert.ok(await p.evaluate(()=>window.__audioSessionCalls.includes("playback")),"iOS richiede categoria playback");
        const audio=p.locator("#csf-music-audio");
        await p.waitForFunction(()=>{const a=document.querySelector("#csf-music-audio");return a&&!a.paused&&a.currentTime>.2&&a.duration>179&&a.duration<182;},null,{timeout:20000});
        assert.ok((await audio.getAttribute("src")).endsWith("/audio/oro-al-tramonto-v1.mp3"));
        assert.ok(await audio.evaluate(a=>!a.muted&&a.volume>0));
      }else assert.equal(await p.locator("#csf-music-audio").count(),0,"Android mantiene il motore originale");
      await button.tap();
      await p.waitForFunction(()=>document.querySelector("#csf-music-toggle").dataset.musicState==="off");
      assert.equal(await p.evaluate(()=>localStorage.getItem("csf_music_v1")),"off");
      if(name.startsWith("iPhone")){
        await p.evaluate(()=>{window.__oldAudio=document.getElementById("csf-music-audio");});
        await button.tap();
        await p.waitForFunction(()=>document.querySelector("#csf-music-toggle").dataset.musicState==="playing",null,{timeout:25000});
        assert.ok(await p.evaluate(()=>window.__oldAudio!==document.getElementById("csf-music-audio")),"Lettore ricreato al riavvio esplicito");
        assert.ok(await p.evaluate(()=>window.__audioSessionCalls.join(",").includes("auto,playback")),"Categoria audio riapplicata");
        await button.tap();
        await p.waitForFunction(()=>document.querySelector("#csf-music-toggle").dataset.musicState==="off");
      }
      await p.reload();
      assert.equal(await button.getAttribute("aria-pressed"),"false");
      console.log("OK "+name+": avvio con gesto, riproduzione, stop, preferenza persistente");
    }finally{await browser.close();}
  }
})().catch(e=>{console.error(e);process.exitCode=1;});
