"use strict";
function linkCondivisioneTracciato(raw,source){
  try{
    const u=new URL(raw,"https://francescocompierchio.github.io/che-si-fa-cerignola/");
    if(u.origin!=="https://francescocompierchio.github.io"||!u.pathname.startsWith("/che-si-fa-cerignola/"))return raw;
    u.searchParams.set("utm_source",source);
    u.searchParams.set("utm_medium","social");
    u.searchParams.set("utm_campaign",u.pathname.endsWith("/eventi/weekend.html")?"condivisione_weekend":"condivisione_eventi");
    return u.href;
  }catch(_){return raw;}
}
document.addEventListener("DOMContentLoaded",()=>{
 document.querySelectorAll("[data-csf-install]").forEach(a=>a.addEventListener("click",()=>window.CsfMetrics?.action?.("csf_install_link")));
 const weekend=document.getElementById("csf-share-weekend");
 if(weekend){
   weekend.hidden=false;
   weekend.addEventListener("click",async()=>{
     const text=weekend.dataset.shareText;
     if(!text)return;
     window.CsfMetrics?.action?.("csf_weekend_share");
     const url=document.querySelector('link[rel="canonical"]')?.href||location.href;
     if(navigator.share){try{await navigator.share({title:"Weekend · Che Si Fa Cerignola",text,url:linkCondivisioneTracciato(url,"condivisione_app")});return;}catch(error){if(error.name==="AbortError")return;}}
     location.href="https://wa.me/?text="+encodeURIComponent(text+"\n"+linkCondivisioneTracciato(url,"whatsapp"));
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
   if(navigator.share){try{await navigator.share({title:ev.titolo,url:linkCondivisioneTracciato(url,"condivisione_app")});return;}catch(error){if(error.name==="AbortError")return;}}
   location.href="https://wa.me/?text="+encodeURIComponent(ev.titolo+" – "+ev.citta+"\n"+linkCondivisioneTracciato(url,"whatsapp"));
 });}
});