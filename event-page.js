"use strict";

// Liquid Touch: onde concentriche locali al tocco, nessuna cattura o modifica degli eventi.
(function(){
  if(window.CsfLiquidTouch)return;
  window.CsfLiquidTouch=true;
  const motion=window.matchMedia("(prefers-reduced-motion: reduce)");
  const style=document.createElement("style");
  style.textContent=
    ".csf-liquid-wave{position:fixed;left:0;top:0;width:112px;height:112px;pointer-events:none!important;z-index:2147483647;border-radius:50%;margin:-56px 0 0 -56px;transform-origin:center;contain:layout style paint;background:radial-gradient(circle,transparent 25%,rgba(95,170,255,.12) 38%,rgba(245,252,255,.54) 43%,rgba(49,117,202,.26) 46%,transparent 50%,rgba(116,184,255,.12) 57%,rgba(255,255,255,.42) 61%,transparent 66%);animation:csf-liquid-wave .66s cubic-bezier(.15,.58,.3,1) both}"+
    ".csf-liquid-wave::before{content:'';position:absolute;inset:16px;border-radius:50%;border:1px solid rgba(255,255,255,.65);box-shadow:inset 0 0 7px rgba(34,106,193,.25),0 0 8px rgba(73,158,245,.22)}"+
    "@keyframes csf-liquid-wave{0%{transform:scale(.12);opacity:.95}40%{opacity:.75}100%{transform:scale(1.9);opacity:0}}"+
    "@keyframes csf-page-arrive{from{opacity:.45;translate:0 7px}to{opacity:1;translate:0 0}}"+
    "@keyframes csf-sheet-arrive{from{opacity:.5;scale:.985}to{opacity:1;scale:1}}"+
    "@media(prefers-reduced-motion:no-preference){.csf-page-arrive main,.csf-page-arrive .hero{animation:csf-page-arrive .32s ease-out both}#csf-share-dialog[open],.modal-backdrop.open .modal-box{animation:csf-sheet-arrive .22s ease-out both}}"+
    "@media(prefers-reduced-motion:reduce){.csf-liquid-wave{display:none!important}.csf-page-arrive main,.csf-page-arrive .hero{animation:none!important}}";
  document.head.append(style);
  const active=new Set();
  function remove(el){active.delete(el);el.remove();}
  function clear(){for(const el of active)remove(el);}
  function wave(x,y,target){
    if(motion.matches||document.hidden||!Number.isFinite(x)||!Number.isFinite(y)||!document.body)return;
    while(active.size>=5)remove(active.values().next().value);
    const el=document.createElement("span");
    el.className="csf-liquid-wave";el.setAttribute("aria-hidden","true");
    const dialog=target instanceof Element?target.closest("dialog[open]"):null;
    // Il dialog nativo è nel top layer: l'onda va creata al suo interno.
    el.style.left=x+"px";el.style.top=y+"px";
    (dialog||document.body).append(el);active.add(el);
    el.addEventListener("animationend",()=>remove(el),{once:true});
    setTimeout(()=>remove(el),850);
  }
  const pointers=new Map();
  document.addEventListener("pointerdown",ev=>{
    if(!ev.isPrimary||ev.button!==0||motion.matches)return;
    pointers.set(ev.pointerId,{x:ev.clientX,y:ev.clientY,target:ev.target});
  },{passive:true,capture:true});
  document.addEventListener("pointermove",ev=>{
    const p=pointers.get(ev.pointerId);
    if(p&&Math.hypot(ev.clientX-p.x,ev.clientY-p.y)>12)pointers.delete(ev.pointerId);
  },{passive:true,capture:true});
  document.addEventListener("pointercancel",ev=>pointers.delete(ev.pointerId),{passive:true,capture:true});
  document.addEventListener("pointerup",ev=>{
    const p=pointers.get(ev.pointerId);pointers.delete(ev.pointerId);
    if(p&&Math.hypot(ev.clientX-p.x,ev.clientY-p.y)<=12)wave(ev.clientX,ev.clientY,ev.target);
  },{passive:true,capture:true});
  function arrive(){
    if(motion.matches)return;
    document.documentElement.classList.remove("csf-page-arrive");
    // Riavvia solo l'animazione di ingresso, anche quando si torna da cache.
    requestAnimationFrame(()=>requestAnimationFrame(()=>document.documentElement.classList.add("csf-page-arrive")));
  }
  window.addEventListener("pageshow",arrive);
  if(document.readyState==="complete")arrive();
  window.addEventListener("pagehide",()=>{clear();pointers.clear();});
  motion.addEventListener?.("change",()=>{if(motion.matches){clear();pointers.clear();}});
})();


// Sottofondo originale CSF: lounge sintetizzato localmente, volume contenuto.
// Nessuna musica scaricata, servizio esterno, cookie o richiesta di rete.
(function(){
  const Audio=window.AudioContext||window.webkitAudioContext;
  const key="csf_music_v1";
  let enabled=true,ctx=null,source=null,master=null,buffer=null,button=null;
  try{enabled=localStorage.getItem(key)!=="off";}catch(_){}
  function loop(context){
    const rate=22050,beat=60/98,frames=Math.round(32*beat*rate);
    const out=context.createBuffer(1,frames,rate),data=out.getChannelData(0);
    const freq=m=>440*Math.pow(2,(m-69)/12),tau=2*Math.PI;
    function tone(at,duration,note,amp,kind){
      const offset=Math.round(at*rate),n=Math.round(duration*rate),f=freq(note);
      for(let i=0;i<n;i++){
        const x=i/rate;
        let env,val;
        if(kind==="pad"){
          env=Math.min(1,x/.22)*Math.min(1,(duration-x)/.30);
          val=.80*Math.sin(tau*f*x)+.14*Math.sin(tau*(f*2.002)*x)+.06*Math.sin(tau*f*.997*x);
        }else if(kind==="bass"){
          env=Math.min(1,x/.018)*Math.exp(-x*3.2)*Math.min(1,(duration-x)/.05);
          val=.85*Math.sin(tau*f*x)+.15*Math.sin(tau*f*2*x);
        }else{
          env=Math.min(1,x/.012)*Math.exp(-x*6)*Math.min(1,(duration-x)/.06);
          val=.70*Math.sin(tau*f*x)+.23*Math.sin(tau*f*2*x)+.07*Math.sin(tau*f*3*x);
        }
        data[(offset+i)%frames]+=amp*env*val;
      }
    }
    const chords=[[53,57,60,64],[50,53,57,60],[48,52,55,59],[48,55,62,64]];
    const bass=[38,34,41,36];
    for(let bar=0;bar<8;bar++){
      const n=bar%4,at=bar*4*beat;
      chords[n].forEach(note=>tone(at,4*beat+.14,note,.038,"pad"));
      for(const step of [0,1.5,2.5,3.5])tone(at+step*beat,.46*beat,bass[n]+(step===2.5?12:0),.15,"bass");
      [0.5,1.75,2.5,3.25].forEach((step,j)=>tone(at+step*beat,.88*beat,chords[n][(j+bar)%4]+12,.040,"pluck"));
    }
    let seed=12571;
    function noise(){seed=(Math.imul(seed,1664525)+1013904223)>>>0;return seed/4294967296*2-1;}
    for(let step=0;step<64;step++){
      const at=Math.round(step*.5*beat*rate);
      if(step%4===0||step%4===2){
        for(let i=0;i<rate*.24;i++){
          const x=i/rate,phase=tau*(50*x+38*(1-Math.exp(-30*x))/30);
          data[(at+i)%frames]+=.17*Math.min(1,x/.006)*Math.exp(-x*17)*Math.sin(phase);
        }
      }
      const off=step%2===1;
      if(off||step%8===4){
        for(let i=0;i<rate*.065;i++){
          const x=i/rate;
          data[(at+i)%frames]+=(off?.019:.013)*Math.exp(-x*64)*noise();
        }
      }
    }
    // Headroom per evitare clipping anche quando si sommano gli strumenti.
    for(let i=0;i<frames;i++)data[i]=Math.max(-.92,Math.min(.92,data[i]));
    return out;
  }
  function running(){return Boolean(enabled&&ctx?.state==="running"&&source&&!document.hidden);}
  function render(){
    if(!button)return;
    const playing=running();
    button.setAttribute("aria-pressed",String(playing));
    button.setAttribute("aria-label",playing?"Disattiva musica di sottofondo":"Attiva musica di sottofondo");
    button.title=playing?"Disattiva musica":"Attiva musica";
    button.dataset.musicState=playing?"playing":enabled?"ready":"off";
    button.classList.toggle("music-playing",playing);
    const mark=button.querySelector(".csf-music-mark");
    if(mark)mark.textContent=playing?"♫":"♪";
  }
  function ready(){
    if(!enabled||document.hidden||!ctx||ctx.state!=="running"){render();return;}
    if(!source){
      buffer=buffer||loop(ctx);
      master=ctx.createGain();master.gain.setValueAtTime(0,ctx.currentTime);
      master.connect(ctx.destination);
      source=ctx.createBufferSource();source.buffer=buffer;source.loop=true;source.connect(master);
      source.start();master.gain.linearRampToValueAtTime(.16,ctx.currentTime+.7);
    }
    render();
  }
  function play(allowCreate=true){
    if(!enabled||document.hidden||!Audio)return;
    try{
      if(!ctx){
        if(!allowCreate)return;
        ctx=new Audio();ctx.onstatechange=render;
      }
      if(ctx.state==="running"){ready();return;}
      // resume può restare in attesa dell'interazione: riprova al primo gesto.
      ctx.resume().then(ready).catch(()=>render());
    }catch(_){render();}
  }
  function pause(){
    if(ctx?.state==="running")ctx.suspend().catch(()=>{});
    render();
  }
  function save(){try{localStorage.setItem(key,enabled?"on":"off");}catch(_){}}
  function toggle(){
    if(running()){enabled=false;save();pause();}
    else{enabled=true;save();play();}
    render();
  }
  function init(){
    button=document.getElementById("csf-music-toggle");
    if(!button&&document.querySelector("header")){
      button=document.createElement("button");button.id="csf-music-toggle";button.type="button";button.className="csf-music-toggle";
      const mark=document.createElement("span");mark.className="csf-music-mark";mark.setAttribute("aria-hidden","true");mark.textContent="♪";button.append(mark);
      document.querySelector("header").append(button);
    }
    if(!button)return;
    if(!Audio){button.hidden=true;return;}
    const style=document.createElement("style");
    style.textContent=".csf-music-toggle{display:inline-grid;place-items:center;min-width:44px;min-height:44px;flex:0 0 44px;border:1px solid var(--border,#dde3ec);border-radius:14px;background:var(--card,#fff);color:var(--accent,#1746a2);font-size:1.3rem;font-weight:800;cursor:pointer;line-height:1;vertical-align:middle}.csf-music-toggle.music-playing{background:var(--premium-selected,#e7efff);box-shadow:inset 0 1px 0 #ffffff50,0 2px 0 var(--depth-button-bottom,#d2ddeb),0 5px 9px var(--depth-ambient,#14213d18)}.csf-music-toggle:focus-visible{outline:3px solid var(--accent,#1746a2);outline-offset:3px}";
    document.head.append(style);
    button.addEventListener("click",toggle);
    const gesture=ev=>{
      if(!ev.isTrusted||!enabled||ev.target?.closest?.("#csf-music-toggle"))return;
      if(!running())play();
    };
    document.addEventListener("pointerup",gesture,{capture:true,passive:true});
    document.addEventListener("click",gesture,{capture:true,passive:true});
    document.addEventListener("keydown",gesture,{capture:true,passive:true});
    document.addEventListener("visibilitychange",()=>{if(document.hidden)pause();else if(enabled&&ctx)play(false);});
    window.addEventListener("pagehide",pause);
    window.addEventListener("pageshow",()=>{if(enabled&&ctx)play(false);});
    render();
    // Prova l'avvio immediato; i browser che vietano autoplay attendono il gesto.
    if(enabled)play();
  }
  if(document.readyState==="loading")document.addEventListener("DOMContentLoaded",init,{once:true});else init();
})();

function csfLinkPaginaTracciato(raw,source){
  try{
    const u=new URL(raw,"https://francescocompierchio.github.io/che-si-fa-cerignola/");
    if(u.origin!=="https://francescocompierchio.github.io"||!u.pathname.startsWith("/che-si-fa-cerignola/"))return raw;
    u.searchParams.set("utm_source",source);
    u.searchParams.set("utm_medium","social");
    u.searchParams.set("utm_campaign",u.pathname.endsWith("/eventi/weekend.html")?"condivisione_weekend":"condivisione_eventi");
    return u.href;
  }catch(_){return raw;}
}

// Condivisione esplicita, senza SDK social né richieste di rete prima della scelta.
window.CsfShare = (() => {
  function apri(titolo, testo, url, tracciamento=csfLinkPaginaTracciato){
    const old=document.getElementById("csf-share-dialog");
    if(old)old.remove();
    const invocante=document.activeElement;
    const dialog=document.createElement("dialog");
    dialog.id="csf-share-dialog";
    dialog.setAttribute("aria-labelledby","csf-share-title");
    Object.assign(dialog.style,{width:"min(92vw,420px)",maxHeight:"85vh",overflow:"auto",boxSizing:"border-box",border:"1px solid var(--border,#dce4ef)",borderRadius:"22px",padding:"18px",background:"var(--card,#fff)",color:"var(--text,#12213c)",boxShadow:"0 20px 70px #0005"});
    const style=document.createElement("style");
    style.textContent="#csf-share-dialog::backdrop{background:rgba(10,20,40,.62)}#csf-share-dialog a,#csf-share-dialog button{box-sizing:border-box;display:flex;align-items:center;justify-content:center;min-height:45px;text-decoration:none;font:inherit;font-size:.9rem;font-weight:700;border:1px solid var(--border,#dce4ef);border-radius:12px;background:var(--premium-surface,#f4f7fc);color:var(--text,#12213c);padding:9px;cursor:pointer;text-align:center}#csf-share-dialog a:focus-visible,#csf-share-dialog button:focus-visible{outline:3px solid var(--accent,#1746a2);outline-offset:2px}";
    dialog.append(style);
    const heading=document.createElement("h2");
    heading.id="csf-share-title";heading.textContent="Condividi";heading.style.margin="0 0 5px";
    const sub=document.createElement("p");sub.textContent=titolo;Object.assign(sub.style,{margin:"0 0 14px",fontSize:".85rem",overflowWrap:"anywhere"});
    dialog.append(heading,sub);
    const grid=document.createElement("div");Object.assign(grid.style,{display:"grid",gridTemplateColumns:"repeat(2,minmax(0,1fr))",gap:"8px"});
    const status=document.createElement("p");status.setAttribute("role","status");status.setAttribute("aria-live","polite");status.style.fontSize=".8rem";status.style.margin="12px 0";
    const enc=encodeURIComponent;
    const tracked=source=>tracciamento(url,source);
    const button=(label,fn,full=false)=>{
      const b=document.createElement("button");b.type="button";b.textContent=label;if(full)b.style.gridColumn="1 / -1";b.addEventListener("click",fn);grid.append(b);return b;
    };
    const link=(label,href)=>{
      const a=document.createElement("a");a.textContent=label;a.href=href;a.rel="noopener noreferrer";if(!/Android|iPhone|iPad|iPod/i.test(navigator.userAgent||""))a.target="_blank";grid.append(a);
    };
    if(typeof navigator.share==="function"){
      button("Condividi con le app del telefono",async()=>{
        try{await navigator.share({title:titolo,text:testo,url:tracked("condivisione_app")});dialog.close();}
        catch(err){if(err?.name!=="AbortError")status.textContent="Menu di sistema non disponibile: scegli un social qui sotto.";}
      },true);
    }
    link("WhatsApp","https://wa.me/?text="+enc(testo+"\n"+tracked("whatsapp")));
    link("Telegram","https://t.me/share/url?url="+enc(tracked("telegram"))+"&text="+enc(testo));
    link("Facebook","https://www.facebook.com/sharer/sharer.php?u="+enc(tracked("facebook")));
    async function copia(source,instagram=false){
      const value=tracked(source);
      let copied=false;
      try{if(navigator.clipboard?.writeText){await navigator.clipboard.writeText(value);copied=true;}}catch(_){}
      if(!copied){
        const input=document.createElement("textarea");input.value=value;input.setAttribute("aria-label","Link da copiare");input.readOnly=true;input.style.width="100%";dialog.append(input);input.focus();input.select();
        try{copied=document.execCommand("copy");}catch(_){}
        if(copied)input.remove();
      }
      status.textContent=copied?(instagram?"Link copiato. Apri Instagram e incollalo in un messaggio o nello sticker Link di una storia.":"Link copiato."):"Seleziona e copia manualmente il link.";
    }
    button("Instagram · copia link",()=>copia("instagram",true));
    button("Copia link",()=>copia("link_copiato"));
    link("Apri Instagram","https://www.instagram.com/");
    dialog.append(grid,status);
    const close=document.createElement("button");close.type="button";close.textContent="Chiudi";close.style.width="100%";close.addEventListener("click",()=>{if(dialog.open&&typeof dialog.close==="function")dialog.close();else dialog.remove();});dialog.append(close);
    dialog.addEventListener("close",()=>{dialog.remove();if(invocante?.isConnected)invocante.focus();});
    document.body.append(dialog);
    try{if(typeof dialog.showModal!=="function")throw Error("dialog");dialog.showModal();}
    catch(_){dialog.setAttribute("open","");Object.assign(dialog.style,{position:"fixed",top:"15%",left:"50%",transform:"translateX(-50%)",zIndex:"1000"});}
  }
  return {apri};
})();

document.addEventListener("DOMContentLoaded",()=>{
 document.querySelectorAll("[data-csf-calendar]").forEach(a=>a.addEventListener("click",()=>window.CsfMetrics?.action?.("csf_calendar_subscribe")));
 document.querySelectorAll("[data-csf-install]").forEach(a=>a.addEventListener("click",()=>window.CsfMetrics?.action?.("csf_install_link")));
 const weekend=document.getElementById("csf-share-weekend");
 if(weekend){
   weekend.hidden=false;
   weekend.addEventListener("click",async()=>{
     const text=weekend.dataset.shareText;
     if(!text)return;
     window.CsfMetrics?.action?.("csf_weekend_share");
     const url=document.querySelector('link[rel="canonical"]')?.href||location.href;
     window.CsfShare.apri("Weekend · Che Si Fa Cerignola",text,url);
   });
 }
 const card=document.getElementById("csf-event-page");
 if(!card)return;
 const ev={titolo:card.dataset.title,citta:card.dataset.city,dataInizio:card.dataset.date,categoria:card.dataset.category};
 window.CsfMetrics?.record("csf_event_open",ev);
 card.querySelectorAll("[data-csf-action]").forEach(a=>a.addEventListener("click",()=>window.CsfMetrics?.record(a.dataset.csfAction,ev)));
 const share=document.getElementById("csf-share-event");
 if(share){share.hidden=false;share.addEventListener("click",async()=>{
   window.CsfMetrics?.record("csf_event_share",ev);
   const url=document.querySelector('link[rel="canonical"]')?.href||location.href;
   window.CsfShare.apri(ev.titolo,ev.titolo+" – "+ev.citta,url);
 });}
});