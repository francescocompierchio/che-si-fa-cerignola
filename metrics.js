"use strict";
(function(){
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
 window.CsfMetrics={
   allowed, aggregateAllowed,
   action(name){if(allowed()&&window.__csfGaStarted&&typeof window.gtag==="function"&&appActions.has(name))window.gtag("event",name,{});},
   record(action,ev){if(!allowed()||!window.__csfGaStarted||typeof window.gtag!=="function"||!actions.has(action)||!ev?.titolo)return;window.gtag("event",action,{csf_event_id:[ev.titolo,ev.citta,ev.dataInizio].join("|").slice(0,100),csf_category:String(ev.categoria||"").slice(0,100)});}
 };
 function decide(v){
   try{localStorage.setItem(key,v);}catch(_){return;}
   choice=v;
   if(v==="no"){window["ga-disable-"+id]=true;try{document.cookie.split(";").map(c=>c.split("=")[0].trim()).filter(n=>/^_ga(?:_|$)/.test(n)).forEach(n=>{document.cookie=n+"=; Max-Age=0; Path=/; SameSite=Lax";document.cookie=n+"=; Max-Age=0; Path=/; Domain="+location.hostname+"; SameSite=Lax";});}catch(_){}}
   location.reload();
 }
 document.addEventListener("DOMContentLoaded",()=>{
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
 });
})();