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