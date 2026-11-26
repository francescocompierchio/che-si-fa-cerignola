"use strict";
// Conteggi aggregati, senza identificativi statistici persistenti.
function csfEventStatsKey(ev){
  const slug=v=>String(v??"").normalize("NFD").replace(/[\u0300-\u036f]/g,"").toLowerCase().replace(/[^a-z0-9]+/g,"-").replace(/^-|-$/g,"");
  if(!ev||ev.tipoContenuto==="esperienza"||!/^\d{4}-\d{2}-\d{2}$/.test(String(ev.dataInizio||"")))return null;
  const city=slug(ev.citta).slice(0,45),title=slug(ev.titolo).slice(0,115);
  return city&&title?[city,ev.dataInizio,title].join("-"):null;
}
function csfEventStatsData(value){
  if(!value||typeof value.enabled!=="boolean")return null;
  const metric=k=>{if(value[k]==null)return 0;const n=value[k].count;return Number.isSafeInteger(n)&&n>=0&&n<=1000000000?n:null;};
  const open=metric("open"),share=metric("share");
  return open===null||share===null?null:{enabled:value.enabled,open,share};
}
function csfEventStatsClient({request,allowed,visible,now=Date.now,notify=()=>{}}){
  const cache=new Map(),pending=new Map(),cooldown=new Map();let denied=false;
  async function read(id,force=false){
    if(!id||denied)return null;
    const entry=cache.get(id);if(!force&&entry&&now()-entry.time<60000)return entry.data;
    if(pending.has(id))return pending.get(id);
    const promise=(async()=>{try{
      const res=await request(id+".json",{cache:"no-store"});
      if(res.status===401||res.status===403){denied=true;return null;}
      if(!res.ok)return null;
      const data=csfEventStatsData(await res.json());cache.set(id,{time:now(),data});notify(id,data);return data;
    }catch(_){return null;}finally{pending.delete(id);}})();
    pending.set(id,promise);return promise;
  }
  async function record(ev,action){
    const id=csfEventStatsKey(ev),metric=action==="csf_event_open"?"open":action==="csf_event_share"?"share":null;
    if(!id||!metric||!allowed()||!visible()||denied)return false;
    const key=id+"/"+metric,t=now(),previous=cooldown.get(key);
    if(previous!==undefined&&t-previous<60000)return false;
    cooldown.set(key,t);
    const stats=await read(id);if(!stats?.enabled||!allowed()||!visible())return false;
    try{
      const res=await request(key+".json",{method:"PUT",headers:{"Content-Type":"application/json"},keepalive:true,body:JSON.stringify({count:{".sv":{increment:1}},at:{".sv":"timestamp"}})});
      if(!res.ok)return false;await read(id,true);return true;
    }catch(_){return false;}
  }
  return {read,record};
}
if(typeof module==="object"&&module.exports){module.exports={csfEventStatsKey,csfEventStatsData,csfEventStatsClient};}else (function(){
 const id="G-M2QBFBHQXQ",key="csf_statistiche_consent_v1";
 let choice="";try{choice=localStorage.getItem(key)||"";}catch(_){}
 function excluded(){try{const q=new URLSearchParams(location.search);return localStorage.getItem("csf_escludi_visite")==="1"||!!localStorage.getItem("csf_admin_pin")||q.get("admin")==="1"||q.get("escludi")==="1";}catch(_){return true;}}
 function allowed(){return choice==="yes"&&!excluded();}
 function aggregateAllowed(){return choice!=="no"&&!excluded();}
 function startAggregate(){
   // Statistiche aggregate senza cookie; non ignorare un precedente rifiuto.
   if(!aggregateAllowed()||window.__csfCfStarted)return;
   if(location.hostname!=="francescocompierchio.github.io"||!location.pathname.startsWith("/che-si-fa-cerignola/"))return;
   const beacon=document.createElement("script");
   beacon.type="module";
   beacon.src="https://static.cloudflareinsights.com/beacon.min.js";
   beacon.setAttribute("data-cf-beacon",JSON.stringify({token:"aa1cf00a038d48b19e84d0e26eed967b"}));
   window.__csfCfStarted=true;
   document.body.appendChild(beacon);
 }
 function start(){
   if(!allowed()||window.__csfGaStarted)return;
   window.__csfGaStarted=true;window["ga-disable-"+id]=false;
   window.dataLayer=window.dataLayer||[];
   window.gtag=function(){window.dataLayer.push(arguments);};
   window.gtag("consent","default",{analytics_storage:"granted",ad_storage:"denied",ad_user_data:"denied",ad_personalization:"denied"});
   window.gtag("js",new Date());window.gtag("config",id,{allow_google_signals:false,allow_ad_personalization_signals:false});
   const script=document.createElement("script");script.async=true;script.src="https://www.googletagmanager.com/gtag/js?id="+id;document.head.appendChild(script);
 }
 const actions=new Set(["csf_event_open","csf_event_share","csf_event_map","csf_event_source","csf_event_save","csf_event_calendar"]);
 const appActions=new Set(["csf_app_share","csf_weekend_reminder","csf_report_open","csf_report_sent","csf_filter_used","csf_search_used","csf_install_guide","csf_install_prompt","csf_install_accepted","csf_pwa_installed","csf_standalone_open","csf_apk_download","csf_weekend_share","csf_install_link","csf_calendar_subscribe","csf_install_entry"]);
 const liveStats=location.hostname==="francescocompierchio.github.io"&&location.pathname.startsWith("/che-si-fa-cerignola/");
 const statsBase="https://chesifa-cerignola-default-rtdb.europe-west1.firebasedatabase.app/statisticheEventi/";
 function statsRender(node,data){
   if(!data){node.style.display="none";return;}
   node.textContent="👁 "+data.open.toLocaleString("it-IT")+" aperture · ↗ "+data.share.toLocaleString("it-IT")+" condivisioni avviate";
   node.style.display="block";
 }
 function statsNotify(id,data){document.querySelectorAll("[data-csf-event-stats]").forEach(node=>{if(node.dataset.csfEventStats===id)statsRender(node,data);});}
 const statsClient=csfEventStatsClient({request:(path,opts)=>fetch(statsBase+path,opts),allowed:aggregateAllowed,visible:()=>!document.hidden,notify:statsNotify});
 const statsNodes=new WeakMap();
 const statsObserver=liveStats&&typeof IntersectionObserver==="function"?new IntersectionObserver(entries=>{
   for(const entry of entries){if(entry.isIntersecting){statsObserver.unobserve(entry.target);const node=statsNodes.get(entry.target);statsNodes.delete(entry.target);if(node)void statsClient.read(node.dataset.csfEventStats).then(data=>statsRender(node,data));}}
 },{rootMargin:"160px"}):null;
 function attachStats(ev,parent,anchor=parent){
   if(!liveStats||!parent)return;
   const id=csfEventStatsKey(ev);if(!id)return;
   const node=document.createElement("small");node.dataset.csfEventStats=id;
   node.style.cssText="display:none;font-size:.73rem;line-height:1.35;opacity:.82;margin-top:4px;font-weight:500;overflow-wrap:anywhere";
   node.title="Interazioni rilevate da Che Si Fa Cerignola, non persone uniche né invii confermati. I limiti anti-abuso possono ridurre il totale.";
   parent.appendChild(node);
   if(statsObserver){statsNodes.set(anchor,node);statsObserver.observe(anchor);}
   else void statsClient.read(id).then(data=>statsRender(node,data));
 }
 window.CsfMetrics={
   attachStats,
   allowed, aggregateAllowed,
   action(name){if(allowed()&&window.__csfGaStarted&&typeof window.gtag==="function"&&appActions.has(name))window.gtag("event",name,{});},
   record(action,ev){if(liveStats)void statsClient.record(ev,action);if(!allowed()||!window.__csfGaStarted||typeof window.gtag!=="function"||!actions.has(action)||!ev?.titolo)return;window.gtag("event",action,{csf_event_id:[ev.titolo,ev.citta,ev.dataInizio].join("|").slice(0,100),csf_category:String(ev.categoria||"").slice(0,100)});}
 };
 function decide(v){
   try{localStorage.setItem(key,v);}catch(_){return;}
   choice=v;
   if(v==="no"){window["ga-disable-"+id]=true;try{document.cookie.split(";").map(c=>c.split("=")[0].trim()).filter(n=>/^_ga(?:_|$)/.test(n)).forEach(n=>{document.cookie=n+"=; Max-Age=0; Path=/; SameSite=Lax";document.cookie=n+"=; Max-Age=0; Path=/; Domain="+location.hostname+"; SameSite=Lax";});}catch(_){}}
   location.reload();
 }
 document.addEventListener("DOMContentLoaded",()=>{
   const eventPage=document.getElementById("csf-event-page");
   if(eventPage){const ev={titolo:eventPage.dataset.title,citta:eventPage.dataset.city,dataInizio:eventPage.dataset.date};const target=eventPage.querySelector("img")||eventPage.querySelector("h1");if(target){const holder=document.createElement("div");target.after(holder);attachStats(ev,holder,eventPage);}}
   const banner=document.getElementById("csf-consent");
   if(!banner)return;
   // Nessun banner automatico. Le statistiche dettagliate richiedono consenso esplicito.
   banner.hidden=true;
   const info=banner.querySelector("p");
   if(info)info.textContent="I contatori pubblici Firebase e Cloudflare Web Analytics misurano aperture e connessioni in forma aggregata, senza cookie statistici aggiuntivi. Puoi rifiutare tutte le statistiche oppure consentire anche quelle dettagliate di Google Analytics. Il rifiuto non limita le funzionalità.";
   document.getElementById("csf-consent-yes").textContent="Consenti anche statistiche dettagliate";
   document.getElementById("csf-consent-no").textContent="Rifiuta tutte le statistiche";
   document.getElementById("csf-consent-yes").addEventListener("click",()=>decide("yes"));
   document.getElementById("csf-consent-no").addEventListener("click",()=>decide("no"));
   document.getElementById("csf-consent-settings").addEventListener("click",()=>{banner.hidden=false;banner.scrollIntoView({block:"center"});});
   startAggregate();
   start();
   if(location.hostname==="francescocompierchio.github.io"&&/^\/che-si-fa-cerignola\/(?:index\.html|eventi\/.*)?$/.test(location.pathname)){
     const views=document.createElement("script");views.src="/che-si-fa-cerignola/public-views.js?v=31";views.async=true;document.body.appendChild(views);
   }
 });
})();