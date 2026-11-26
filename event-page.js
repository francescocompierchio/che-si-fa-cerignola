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


// Sottofondo originale CSF: Oro al tramonto, aperitivo lounge completo.
// Android conserva il sintetizzatore; iOS usa lo stesso brano prerenderizzato in MP3 locale.
(function(){
  const Audio=window.AudioContext||window.webkitAudioContext;
  const key="csf_music_v1";
  const nativeAudio=/iPad|iPhone|iPod/.test(navigator.userAgent)||(navigator.platform==="MacIntel"&&navigator.maxTouchPoints>1)||!Audio;
  const musicUrl=new URL("audio/oro-al-tramonto-v1.mp3",document.currentScript?.src||document.baseURI).href;
  let media=null,mediaPending=false,mediaPlaying=false,mediaError=false,mediaAttempt=0;
  let enabled=true,ctx=null,source=null,master=null,buffer=null,button=null,finished=false;
  try{enabled=localStorage.getItem(key)!=="off";}catch(_){}
  function composition(context){
    // "Oro al tramonto": 72 battute, 96 BPM, durata 3:00.
    // Forma completa: intro, tema, sviluppo, bridge, solo, ripresa e coda.
    const rate=22050,beat=60/96,bars=72,frames=Math.round(bars*4*beat*rate);
    const out=context.createBuffer(2,frames,rate),L=out.getChannelData(0),R=out.getChannelData(1);
    const tau=2*Math.PI,cache=new Map();
    function mix(i,v,pan=0){
      if(i<0||i>=frames)return;
      L[i]+=v*(1-.38*pan);R[i]+=v*(1+.38*pan);
    }
    function tone(at,beats,note,amp,kind,pan=0){
      const duration=beats*beat,n=Math.round(duration*rate),key=[kind,n,note].join(":");
      let sample=cache.get(key);
      if(!sample){
        sample=new Float32Array(n);
        const f=440*Math.pow(2,(note-69)/12);
        for(let i=0;i<n;i++){
          const x=i/rate,p=tau*f*x,tail=Math.min(1,(duration-x)/.10);
          let env,val;
          if(kind==="rhodes"){
            env=Math.min(1,x/.009)*Math.exp(-x*1.55)*tail;
            val=.72*Math.sin(p+.32*Math.exp(-x*3)*Math.sin(p*2.002))+.20*Math.sin(p*2.001)*Math.exp(-x*3.5)+.08*Math.sin(p*4.002)*Math.exp(-x*12);
            val*=.95+.05*Math.sin(tau*4.3*x);
          }else if(kind==="bass"){
            env=Math.min(1,x/.012)*Math.exp(-x*2.4)*tail;
            val=.72*Math.sin(p)+.20*Math.sin(2*p)*Math.exp(-x*2)+.06*Math.sin(3*p)*Math.exp(-x*4)+.02*Math.sin(5*p)*Math.exp(-x*12);
          }else if(kind==="guitar"){
            env=Math.min(1,x/.005)*Math.exp(-x*3.8)*tail;
            val=.58*Math.sin(p)+.24*Math.sin(p*2)*Math.exp(-x*2)+.12*Math.sin(p*3)*Math.exp(-x*5)+.06*Math.sin(p*5)*Math.exp(-x*9);
          }else if(kind==="pad"){
            env=Math.min(1,x/.32)*Math.min(1,(duration-x)/.5);
            val=.62*Math.sin(p)+.21*Math.sin(p*1.003)+.13*Math.sin(p*.997)+.04*Math.sin(p*2);
          }else{
            env=Math.min(1,x/.025)*Math.exp(-x*2.1)*tail;
            val=.74*Math.sin(p+.13*Math.sin(tau*4.8*x))+.20*Math.sin(p*2)*Math.exp(-x*2)+.06*Math.sin(p*3)*Math.exp(-x*3);
          }
          sample[i]=env*val;
        }
        cache.set(key,sample);
      }
      const offset=Math.round(at*rate),end=Math.min(n,frames-offset);
      for(let i=0;i<end;i++)mix(offset+i,amp*sample[i],pan);
    }
    // Cmaj9, Am9, Dm9, G13, Em9, A13, Fmaj9, Fm6, E7b9, Bm7b5, Bb13, Abmaj7.
    const harmony=[
      [36,[52,55,59,62,64]],[45,[55,59,60,64,67]],[38,[53,57,60,64,69]],
      [43,[53,57,59,64,69]],[40,[55,59,62,66,71]],[45,[55,59,61,66,69]],
      [41,[57,60,64,67,72]],[41,[56,60,62,65,68]],[40,[56,59,62,65,68]],
      [47,[53,57,62,65,69]],[46,[56,60,62,67,72]],[44,[55,60,63,67,72]]
    ];
    // Ogni blocco di otto battute ha armonia, arrangiamento e frase propri.
    const score=[
      {name:"Intro",ch:[0,4,6,3,0,1,2,3],p:.78,b:.48,g:0,m:.35,d:0,keys:"sparse"},
      {name:"Tema A",ch:[0,1,2,3,4,5,2,3],p:1,b:1,g:.55,m:1,d:.65,keys:"lounge"},
      {name:"Tema B",ch:[6,7,4,5,2,3,0,8],p:.88,b:1,g:.65,m:.9,d:.8,keys:"lounge"},
      {name:"Bridge",ch:[1,8,6,10,11,4,2,3],p:.85,b:.82,g:.25,m:.65,d:.35,keys:"sparse"},
      {name:"Solo chitarra",ch:[2,3,0,1,6,7,4,5],p:.67,b:1,g:1,m:.95,d:.85,keys:"sync"},
      {name:"Sviluppo",ch:[2,3,4,5,6,10,0,8],p:1,b:1,g:.5,m:1,d:1,keys:"sync"},
      {name:"Ripresa",ch:[1,2,3,0,6,7,4,5],p:1,b:.95,g:.55,m:.9,d:.75,keys:"lounge"},
      {name:"Tema finale",ch:[2,3,0,1,6,10,2,3],p:.9,b:.9,g:.7,m:.75,d:.6,keys:"lounge"},
      {name:"Coda",ch:[6,7,4,1,2,3,0,0],p:.7,b:.48,g:.2,m:.45,d:.15,keys:"sparse"}
    ];
    const patterns=[
      [[.5,1,.7],[1.5,2,.6],[2.75,3,.85]],
      [[0,3,.9],[1.75,2,.65],[3,1,.6]],
      [[.75,0,.55],[1.5,2,.7],[2.5,4,1.05]],
      [[0,4,.7],[1,3,.55],[2.25,1,1.25]],
      [[.25,2,.6],[1.25,4,.75],[2.5,3,.65],[3.25,1,.5]],
      [[.5,1,1.1],[2,3,.6],[3,2,.75]],
      [[0,2,.75],[1.25,1,.75],[2.75,0,.8]],
      [[.75,3,.7],[2,2,.7],[3,1,.65]]
    ];
    for(let bar=0;bar<bars;bar++){
      const section=Math.floor(bar/8),pos=bar%8,arr=score[section],at=bar*4*beat;
      const [root,ch]=harmony[arr.ch[pos]];
      const next=bar+1<bars?harmony[score[Math.floor((bar+1)/8)].ch[(bar+1)%8]][0]:36;
      const fade=section===8?Math.max(.35,1-pos*.09):1;
      const bassPattern=arr.keys==="sparse"?[[0,root,1.4],[2,root,.9]]:pos%2?
        [[0,root,.85],[1.5,root+7,.60],[2.5,root+12,.56],[3.5,next-1,.4]]:
        [[0,root,1.05],[1.5,root+7,.55],[2,root,.85],[3.5,next-1,.4]];
      for(const [step,note,len] of bassPattern)tone(at+step*beat,len,note,.13*arr.b*fade,"bass");
      const keys=arr.keys==="sparse"?[0,2.25]:arr.keys==="sync"?[.5,1.75,3]:pos%2?[0,1.5,3]:[0,1.75,2.75];
      for(const step of keys)ch.slice(0,4).forEach((note,j)=>tone(at+(step+j*.016)*beat,arr.keys==="sparse"?1.8:1.25,note,.036*arr.p*fade,"rhodes",-.35));
      if(section===0||section===3||section===8)ch.slice(1,4).forEach((note,j)=>tone(at,4.1,note,.014*fade,"pad",j%2?.7:-.7));
      if(arr.g)for(const step of (pos%2?[.75,2.25,3.25]:[.75,1.75,3.25]))ch.slice(1,4).forEach((note,j)=>tone(at+(step+j*.015)*beat,.50,note+12,.014*arr.g*fade,"guitar",.65));
      if(!(section===0&&pos<3)&&!(section===8&&pos>5)){
        const pattern=patterns[(pos+section*3+(pos>=4?1:0))%patterns.length];
        for(const [step,degree,len] of pattern){
          let note=ch[degree%ch.length];while(note<67)note+=12;
          if(section===4&&pos%3===1&&note<77)note+=12;
          const instrument=section===4||section===5&&pos%2?"guitar":"rhodes";
          tone(at+step*beat,len,note,.066*arr.m*fade,instrument,.20);
          if(section!==0&&section!==8)tone(at+(step+.34)*beat,len,note,.009*arr.m,"soft",.75);
        }
      }
    }
    let seed=67429;
    function noise(){seed=(Math.imul(seed,1664525)+1013904223)>>>0;return seed/4294967296*2-1;}
    for(let step=0;step<bars*8;step++){
      const section=Math.floor(step/64),pos=Math.floor(step/8)%8,at=Math.round(step*.5*beat*rate);
      const d=score[section].d*(section===8?Math.max(0,1-pos/5):1);
      if(!d)continue;
      if(step%4===0||step%8===6){
        for(let i=0;i<rate*.19;i++){const x=i/rate;mix(at+i,.095*d*Math.min(1,x/.005)*Math.exp(-x*21)*Math.sin(tau*(55*x+28*(1-Math.exp(-35*x))/35)));}
      }
      if(step%4===2){
        let low=0;
        for(let i=0;i<rate*.18;i++){const x=i/rate,z=noise();low=.78*low+.22*z;mix(at+i,.030*d*(z-low)*Math.exp(-x*19)*Math.min(1,x/.007),.25);}
      }
      let prev=0;
      for(let i=0;i<rate*.045;i++){const x=i/rate,z=noise();mix(at+i,(step%2?.012:.008)*d*(z-prev)*Math.exp(-x*85),-.40);prev=z;}
    }
    // Coda reale: ultimo accordo, decadimento e silenzio; nessuna cucitura in loop.
    const endAt=(bars-1)*4*beat;
    harmony[0][1].forEach((note,j)=>tone(endAt,3.6,note,.028,"rhodes",j%2?.25:-.25));
    const fadeFrames=Math.round(3.2*rate);
    for(let i=0;i<frames;i++){
      const g=Math.min(1,i/(rate*.45),(frames-1-i)/fadeFrames);
      L[i]=Math.tanh(L[i]*1.22)*.85*g;R[i]=Math.tanh(R[i]*1.22)*.85*g;
    }
    return out;
  }
  function running(){return Boolean(enabled&&!document.hidden&&(nativeAudio?mediaPlaying&&media&&!media.paused:ctx?.state==="running"&&source));}
  function sessionePlayback(){
    // Safari iOS: esplicita la categoria media, non ambient, prima del gesto play.
    // Il browser decide comunque volume, routing e interruzioni.
    if(!nativeAudio)return;
    try{if(navigator.audioSession)navigator.audioSession.type="playback";}catch(_){}
  }
  function ensureMedia(){
    if(media)return media;
    media=document.createElement("audio");
    media.id="csf-music-audio";
    media.preload="none";media.hidden=true;media.loop=false;media.autoplay=false;
    media.setAttribute("playsinline","");
    media.src=musicUrl;
    media.addEventListener("playing",()=>{
      if(!enabled||document.hidden){media.pause();return;}
      mediaPlaying=true;mediaError=false;render();
    });
    for(const ev of ["pause","waiting","stalled"])media.addEventListener(ev,()=>{mediaPlaying=false;render();});
    media.addEventListener("ended",()=>{mediaPlaying=false;finished=true;render();});
    media.addEventListener("error",()=>{mediaPlaying=false;mediaPending=false;mediaError=true;render();});
    document.body.append(media);
    return media;
  }
  function playNative(){
    const a=ensureMedia();
    if(mediaPlaying||mediaPending)return;
    sessionePlayback();
    if(a.error){mediaError=false;a.load();}
    if(a.ended)a.currentTime=0;
    const attempt=++mediaAttempt;
    mediaPending=true;mediaError=false;
    // Chiamata sincrona nel gesto reale: niente await/fetch prima di play().
    try{
      Promise.resolve(a.play()).then(()=>{
        if(attempt!==mediaAttempt)return;
        mediaPending=false;
        if(!enabled||document.hidden)a.pause();
        render();
      },()=>{
        if(attempt!==mediaAttempt)return;
        mediaPending=false;mediaPlaying=false;render();
      });
    }catch(_){mediaPending=false;mediaPlaying=false;render();}
    render();
  }
  function render(){
    if(!button)return;
    const playing=running();
    button.setAttribute("aria-pressed",String(playing));
    button.setAttribute("aria-label",playing?"Disattiva musica di sottofondo":"Attiva musica di sottofondo");
    button.title=playing?"Disattiva musica":mediaError?"Riprova musica":finished?"Riascolta Oro al tramonto":"Attiva musica";
    button.dataset.musicState=playing?"playing":!enabled?"off":finished?"finished":mediaPending?"loading":mediaError?"error":"ready";
    button.classList.toggle("music-playing",playing);
    const mark=button.querySelector(".csf-music-mark");
    if(mark)mark.textContent=playing?"♫":"♪";
  }
  function ready(){
    if(!enabled||finished||document.hidden||!ctx||ctx.state!=="running"){render();return;}
    if(!source){
      buffer=buffer||composition(ctx);
      master=ctx.createGain();master.gain.setValueAtTime(0,ctx.currentTime);
      master.connect(ctx.destination);
      source=ctx.createBufferSource();source.buffer=buffer;source.loop=false;source.connect(master);
      source.onended=()=>{source=null;master?.disconnect();master=null;finished=true;pause();};
      source.start();master.gain.linearRampToValueAtTime(.16,ctx.currentTime+.7);
    }
    render();
  }
  function play(allowCreate=true){
    if(!enabled||finished||document.hidden)return;
    if(nativeAudio){if(allowCreate||media)playNative();return;}
    if(!Audio)return;
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
    if(nativeAudio){++mediaAttempt;mediaPending=false;mediaPlaying=false;media?.pause();render();return;}
    if(ctx?.state==="running")ctx.suspend().catch(()=>{});
    render();
  }
  function save(){try{localStorage.setItem(key,enabled?"on":"off");}catch(_){}}
  function toggle(){
    if(running()||mediaPending||(nativeAudio&&media&&!media.paused&&!media.ended)){enabled=false;save();pause();}
    else{finished=false;enabled=true;save();play();}
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
    if(nativeAudio){ensureMedia();if(enabled)sessionePlayback();}
    const style=document.createElement("style");
    style.textContent=".csf-music-toggle{display:inline-grid;place-items:center;min-width:44px;min-height:44px;flex:0 0 44px;border:1px solid var(--border,#dde3ec);border-radius:14px;background:var(--card,#fff);color:var(--accent,#1746a2);font-size:1.3rem;font-weight:800;cursor:pointer;line-height:1;vertical-align:middle}.csf-music-toggle.music-playing{background:var(--premium-selected,#e7efff);box-shadow:inset 0 1px 0 #ffffff50,0 2px 0 var(--depth-button-bottom,#d2ddeb),0 5px 9px var(--depth-ambient,#14213d18)}.csf-music-toggle:focus-visible{outline:3px solid var(--accent,#1746a2);outline-offset:3px}";
    document.head.append(style);
    button.addEventListener("click",toggle);
    const gesture=ev=>{
      if(!ev.isTrusted||!enabled||finished||ev.target?.closest?.("#csf-music-toggle"))return;
      if(!running())play();
    };
    document.addEventListener("pointerup",gesture,{capture:true,passive:true});
    if(nativeAudio)document.addEventListener("touchend",gesture,{capture:true,passive:true});
    document.addEventListener("click",gesture,{capture:true,passive:true});
    document.addEventListener("keydown",gesture,{capture:true,passive:true});
    document.addEventListener("visibilitychange",()=>{if(document.hidden)pause();else if(enabled&&(ctx||media))play(false);});
    window.addEventListener("pagehide",pause);
    window.addEventListener("pageshow",()=>{if(enabled&&(ctx||media))play(false);});
    render();
    // Prova l'avvio immediato; i browser che vietano autoplay attendono il gesto.
    if(enabled&&!nativeAudio){if(document.readyState==="complete")setTimeout(()=>play(),0);else window.addEventListener("load",()=>setTimeout(()=>play(),0),{once:true});}
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
      const a=document.createElement("a");a.textContent=label;a.href=href;a.rel="noopener noreferrer";a.target="_blank";grid.append(a);
    };
    if(typeof navigator.share==="function"){
      button("Condividi con le app del telefono",async()=>{
        try{await navigator.share({title:titolo,text:testo,url:tracked("condivisione_app")});dialog.close();}
        catch(err){if(err?.name!=="AbortError")status.textContent="Menu di sistema non disponibile: scegli un social qui sotto.";}
      },true);
    }
    link("WhatsApp","https://wa.me/?text="+enc(testo+"\n"+tracked("whatsapp")));
    link("Telegram","https://t.me/share/url?url="+enc(tracked("telegram"))+"&text="+enc(testo));
    // I messaggi privati non sono post Facebook. Non fingere un invio
    // diretto quando il contenitore Android non espone la condivisione nativa.
    async function copia(source,messaggio=false){
      const value=messaggio?testo+"\n"+tracked(source):tracked(source);
      let copied=false;
      try{if(navigator.clipboard?.writeText){await navigator.clipboard.writeText(value);copied=true;}}catch(_){}
      if(!copied){
        const input=document.createElement("textarea");input.value=value;input.setAttribute("aria-label","Testo da copiare");input.readOnly=true;input.style.width="100%";dialog.append(input);input.focus();input.select();
        try{copied=document.execCommand("copy");}catch(_){}
        if(copied)input.remove();
      }
      const nome={instagram:"Instagram Direct",messenger:"Messenger",whatsapp:"WhatsApp"}[source];
      status.textContent=copied?(nome?"Copiato. Apri "+nome+" dal pulsante qui sotto o dal telefono, scegli una chat e incolla il messaggio.":"Link copiato."):"Seleziona e copia manualmente il testo prima di aprire la chat.";
    }
    button("WhatsApp · copia messaggio",()=>copia("whatsapp",true));
    button("Instagram Direct · copia messaggio",()=>copia("instagram",true));
    link("Apri Direct","https://www.instagram.com/direct/inbox/");
    button("Messenger · copia messaggio",()=>copia("messenger",true));
    link("Apri Messenger","https://www.messenger.com/");
    button("Copia link",()=>copia("link_copiato"));
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