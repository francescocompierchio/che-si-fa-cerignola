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


// Luxury Spa Lounge: registrazioni complete, CC BY 4.0, Kevin MacLeod.
(function(){
  const base=new URL(".",document.currentScript?.src||location.href);
  const tracks=[
  {
    "title": "Groove Grove",
    "id": "USUAN1200054",
    "duration": 206,
    "file": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Groove%20Grove.mp3"
  },
  {
    "title": "Clean Soul",
    "id": "USUAN1300033",
    "duration": 307,
    "file": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Clean%20Soul.mp3"
  },
  {
    "title": "Windswept",
    "id": "USUAN1100757",
    "duration": 208,
    "file": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Windswept.mp3"
  },
  {
    "title": "That Zen Moment",
    "id": "USUAN2400001",
    "duration": 602,
    "file": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/That%20Zen%20Moment.mp3"
  },
  {
    "title": "Dream Catcher",
    "id": "USUAN1800019",
    "duration": 377,
    "file": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Dream%20Catcher.mp3"
  }
];
  const key="csf_music_v1",lastKey="csf_music_last_v1";
  let enabled=true,last="",audio=null,button=null,bag=[],track=null,failed=0,credits=null,started=false,blocked=false,attempt=0,sourceRetry=false;
  try{enabled=localStorage.getItem(key)!=="off";last=localStorage.getItem(lastKey)||"";}catch(_){}
  const source=t=>"https://incompetech.com/music/royalty-free/index.html?isrc="+t.id;
  function save(){try{localStorage.setItem(key,enabled?"on":"off");}catch(_){}}
  function choose(){
    if(!bag.length){
      bag=tracks.slice();
      for(let i=bag.length-1;i>0;i--){const j=Math.floor(Math.random()*(i+1));[bag[i],bag[j]]=[bag[j],bag[i]];}
      if(bag[0].id===last&&bag.length>1)[bag[0],bag[1]]=[bag[1],bag[0]];
    }
    track=bag.shift();last=track.id;
    sourceRetry=false;blocked=false;
    audio.src=new URL("audio/"+track.id+".mp3",base).href;audio.loop=false;
    audio.volume=.20;
    render();
  }
  function render(){
    if(!button||!audio)return;
    const playing=enabled&&!audio.paused&&!audio.ended&&!document.hidden&&audio.readyState>=2;
    button.setAttribute("aria-pressed",String(playing));
    button.setAttribute("aria-label",playing?"Disattiva musica di sottofondo":"Attiva musica di sottofondo");
    button.title=playing?"Disattiva musica — "+track.title:!enabled?"Attiva musica lounge":failed>=tracks.length?"Musica non disponibile — tocca per riprovare":blocked?"Tocca per avviare la musica":"Attiva musica lounge";
    button.dataset.musicState=playing?"playing":!enabled?"off":failed>=tracks.length?"unavailable":blocked?"blocked":"ready";
    button.dataset.musicTrack=track?.title||"";
    button.classList.toggle("music-playing",playing);
    const mark=button.querySelector(".csf-music-mark");
    if(mark)mark.textContent=playing?"♫":"♪";
    if(credits)credits.textContent=track?"Musica: "+track.title+" — Kevin MacLeod":"Musica lounge — Kevin MacLeod";
  }
  function play(){
    if(!enabled||document.hidden||!audio||failed>=tracks.length)return;
    if(!track)choose();
    const current=++attempt;
    try{
      // Chiamata sincrona nel gestore del gesto: nessun await prima di play().
      Promise.resolve(audio.play()).then(()=>{
        if(current!==attempt)return;
        blocked=false;
        if(!enabled||document.hidden)audio.pause();
        render();
      }).catch(err=>{
        if(current!==attempt)return;
        blocked=err?.name==="NotAllowedError";
        render();
      });
    }catch(_){render();}
  }
  function pause(){attempt++;audio?.pause();render();}
  function toggle(){
    if(enabled&&!audio.paused&&!audio.ended){enabled=false;audio.autoplay=false;save();pause();}
    else{enabled=true;audio.autoplay=true;blocked=false;if(failed>=tracks.length){failed=0;bag=[];choose();}save();play();}
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
    audio=document.createElement("audio");audio.id="csf-lounge-audio";audio.preload=enabled?"auto":"none";audio.autoplay=enabled;audio.setAttribute("playsinline","");audio.hidden=true;document.body.append(audio);
    const style=document.createElement("style");
    style.textContent=".csf-music-toggle{display:inline-grid;place-items:center;min-width:44px;min-height:44px;flex:0 0 44px;border:1px solid var(--border,#dde3ec);border-radius:14px;background:var(--card,#fff);color:var(--accent,#1746a2);font-size:1.3rem;font-weight:800;cursor:pointer;line-height:1;vertical-align:middle}.csf-music-toggle.music-playing{background:var(--premium-selected,#e7efff);box-shadow:inset 0 1px 0 #ffffff50,0 2px 0 var(--depth-button-bottom,#d2ddeb),0 5px 9px var(--depth-ambient,#14213d18)}.csf-music-toggle:focus-visible{outline:3px solid var(--accent,#1746a2);outline-offset:3px}.csf-music-credits{font-size:.75rem;color:var(--muted,#53627a);text-align:center;margin:8px auto;max-width:740px}.csf-music-credits a{color:var(--accent,#1746a2)}.csf-music-credits ul{list-style:none;padding:0;line-height:1.65}";
    document.head.append(style);
    const details=document.createElement("details");details.className="csf-music-credits";
    credits=document.createElement("summary");details.append(credits);
    const p=document.createElement("p");p.append("Kevin MacLeod (Incompetech). Registrazioni complete; eventuale ricodifica MP3 per lo streaming. Licenza ");
    const license=document.createElement("a");license.href="https://creativecommons.org/licenses/by/4.0/";license.textContent="Creative Commons CC BY 4.0";license.target="_blank";license.rel="noopener noreferrer";p.append(license);details.append(p);
    const list=document.createElement("ul");
    for(const tr of tracks){const li=document.createElement("li"),a=document.createElement("a");a.href=source(tr);a.textContent=tr.title+" — Kevin MacLeod";a.target="_blank";a.rel="noopener noreferrer";li.append(a);list.append(li);}
    details.append(list);(document.querySelector("footer")||document.body).append(details);
    audio.addEventListener("playing",()=>{started=true;blocked=false;failed=0;try{localStorage.setItem(lastKey,track.id);}catch(_){}render();});
    for(const ev of ["pause","canplay","waiting"])audio.addEventListener(ev,render);
    audio.addEventListener("ended",()=>{if(enabled){choose();play();}else render();});
    audio.addEventListener("error",()=>{
      if(!enabled||!track)return;
      attempt++;
      if(!sourceRetry){
        sourceRetry=true;
        audio.src=track.file;play();return;
      }
      if(++failed<tracks.length&&!document.hidden){choose();play();}else render();
    });
    button.addEventListener("click",toggle);
    const gesture=ev=>{
      if(!ev.isTrusted||!enabled||ev.target?.closest?.("#csf-music-toggle"))return;
      if(audio.paused||blocked)play();
    };
    document.addEventListener("pointerup",gesture,{capture:true,passive:true});
    document.addEventListener("touchend",gesture,{capture:true,passive:true});
    document.addEventListener("pointerdown",ev=>{if(ev.pointerType==="mouse")gesture(ev);},{capture:true,passive:true});
    document.addEventListener("click",gesture,{capture:true,passive:true});
    document.addEventListener("keydown",gesture,{capture:true,passive:true});
    document.addEventListener("visibilitychange",()=>{if(document.hidden)pause();else if(enabled)play();});
    window.addEventListener("pagehide",pause);
    window.addEventListener("pageshow",()=>{if(enabled)play();});
    render();
    if(enabled){play();}
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