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


// Sottofondo originale CSF: Terrazza Dorata, cocktail jazz lounge / bossa nova stereo.
// Nessuna musica scaricata, servizio esterno, cookie o richiesta di rete.
(function(){
  const Audio=window.AudioContext||window.webkitAudioContext;
  const key="csf_music_v1";
  let enabled=true,ctx=null,source=null,master=null,buffer=null,button=null;
  try{enabled=localStorage.getItem(key)!=="off";}catch(_){}
  function loop(context){
    // "Terrazza Dorata" — jazz lounge / bossa nova originale, 16 battute.
    // Rhodes, contrabbasso, chitarra nylon e batteria a spazzole.
    const rate=22050,beat=60/92,frames=Math.round(64*beat*rate);
    const out=context.createBuffer(2,frames,rate),L=out.getChannelData(0),R=out.getChannelData(1);
    const tau=2*Math.PI,cache=new Map();
    function mix(i,v,pan=0){
      i%=frames;L[i]+=v*(1-.38*pan);R[i]+=v*(1+.38*pan);
    }
    function tone(at,beats,note,amp,kind,pan=0){
      const duration=beats*beat,n=Math.round(duration*rate),key=[kind,n,note].join(":");
      let sample=cache.get(key);
      if(!sample){
        sample=new Float32Array(n);
        const f=440*Math.pow(2,(note-69)/12);
        for(let i=0;i<n;i++){
          const x=i/rate,p=tau*f*x,tail=Math.min(1,(duration-x)/.085);
          let env,val;
          if(kind==="rhodes"){
            env=Math.min(1,x/.008)*Math.exp(-x*1.9)*tail;
            val=.77*Math.sin(p+.22*Math.exp(-x*3)*Math.sin(p*2.002))+.16*Math.sin(p*2.001)*Math.exp(-x*4)+.07*Math.sin(p*4.002)*Math.exp(-x*13);
            val*=.94+.06*Math.sin(tau*4.6*x);
          }else if(kind==="bass"){
            env=Math.min(1,x/.012)*Math.exp(-x*2.7)*tail;
            val=.72*Math.sin(p)+.20*Math.sin(2*p)*Math.exp(-x*2)+.06*Math.sin(3*p)*Math.exp(-x*4)+.02*Math.sin(5*p)*Math.exp(-x*12);
          }else if(kind==="guitar"){
            env=Math.min(1,x/.005)*Math.exp(-x*4.1)*tail;
            val=.63*Math.sin(p)+.22*Math.sin(p*2)*Math.exp(-x*2)+.10*Math.sin(p*3)*Math.exp(-x*5)+.05*Math.sin(p*5)*Math.exp(-x*9);
          }else{
            env=Math.min(1,x/.03)*Math.exp(-x*1.8)*tail;
            val=.72*Math.sin(p+.13*Math.sin(tau*5.1*x))+.18*Math.sin(p*2)+.07*Math.sin(p*3)*Math.exp(-x*3);
          }
          sample[i]=env*val;
        }
        cache.set(key,sample);
      }
      const offset=Math.round(at*rate);
      for(let i=0;i<n;i++)mix(offset+i,amp*sample[i],pan);
    }
    // Voicing jazz a quattro voci e bassi separati: Dm9, G13, Cmaj9,
    // A7b9, Dm9, G13, Em7, A13, Fmaj9, Fm6, Em9, A7, Dm9, G13, Cmaj9, G13.
    const chords=[
      [53,57,60,64],[53,57,59,64],[52,55,59,62],[55,58,61,64],
      [53,57,60,64],[53,57,59,64],[55,59,62,66],[55,59,61,66],
      [57,60,64,67],[56,60,62,65],[55,59,62,66],[55,57,61,64],
      [53,57,60,64],[53,57,59,64],[52,55,59,62],[53,57,59,64]
    ];
    const roots=[38,43,36,45,38,43,40,45,41,41,40,45,38,43,36,43];
    const lead=[
      [[.5,69,.75],[1.5,72,.5],[2.25,76,.8]],
      [[0,74,.75],[1,71,.5],[2.5,69,.9]],
      [[.5,67,.65],[1.5,71,.65],[2.5,74,1.2]],
      [[0,73,.6],[1,70,.65],[2.5,69,1.1]],
      [[.5,65,.6],[1.5,69,.6],[2.5,72,1.15]],
      [[0,71,.7],[1.5,67,.7],[3,64,.8]],
      [[.5,66,.65],[1.5,67,.5],[2.5,71,1.1]],
      [[0,69,.8],[2,73,.65],[3,76,.75]],
      [[.5,76,.6],[1.5,79,.5],[2.5,77,1.0]],
      [[0,77,.8],[1.5,74,.6],[2.5,72,.9]],
      [[.5,71,.6],[1.5,74,.6],[2.5,78,1.1]],
      [[0,76,.7],[1.5,73,.6],[3,69,.75]],
      [[.5,65,.7],[1.5,69,.6],[2.5,72,1.0]],
      [[0,71,.8],[1.5,74,.6],[3,69,.75]],
      [[.5,67,.65],[1.5,64,.65],[2.5,62,1.2]],
      [[0,65,.7],[1.5,67,.6],[2.75,71,.65]]
    ];
    for(let bar=0;bar<16;bar++){
      const at=bar*4*beat,ch=chords[bar],root=roots[bar];
      const next=roots[(bar+1)%16];
      for(const [step,note,len] of [[0,root,.89],[1.5,root+7,.62],[2,root,.85],[3.5,next-1,.40]])
        tone(at+step*beat,len,note,.17,"bass");
      for(const step of [0,1.5,2.5])ch.forEach((note,j)=>tone(at+(step+j*.016)*beat,1.35,note,.037,"rhodes",-.35));
      for(const step of [.75,1.75,3.25])ch.slice(1).forEach((note,j)=>tone(at+(step+j*.014)*beat,.47,note+12,.016,"guitar",.65));
      for(const [step,note,len] of lead[bar]){
        tone(at+step*beat,len,note,.073,"rhodes",.18);
        tone(at+(step+.30)*beat,len,note,.012,"soft",.70);
      }
    }
    let seed=67429;
    function noise(){seed=(Math.imul(seed,1664525)+1013904223)>>>0;return seed/4294967296*2-1;}
    for(let step=0;step<128;step++){
      const at=Math.round(step*.5*beat*rate);
      if(step%4===0||step%8===6){
        for(let i=0;i<rate*.19;i++){const x=i/rate;mix(at+i,.095*Math.min(1,x/.005)*Math.exp(-x*21)*Math.sin(tau*(55*x+28*(1-Math.exp(-35*x))/35)));}
      }
      if(step%4===2){
        let low=0;
        for(let i=0;i<rate*.18;i++){const x=i/rate,z=noise();low=.78*low+.22*z;mix(at+i,.032*(z-low)*Math.exp(-x*19)*Math.min(1,x/.007),.25);}
      }
      let prev=0;
      for(let i=0;i<rate*.045;i++){const x=i/rate,z=noise();mix(at+i,(step%2?.012:.008)*(z-prev)*Math.exp(-x*85),-.40);prev=z;}
    }
    // Soft mastering; no harsh clipping. Seam is faded over 6 ms.
    for(let i=0;i<frames;i++){L[i]=Math.tanh(L[i]*1.25)*.86;R[i]=Math.tanh(R[i]*1.25)*.86;}
    for(let i=0;i<128;i++){const g=i/128;L[i]*=g;R[i]*=g;L[frames-1-i]*=g;R[frames-1-i]*=g;}
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