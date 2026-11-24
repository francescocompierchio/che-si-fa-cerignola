"use strict";
(function(){
 const id="G-M2QBFBHQXQ",key="csf_statistiche_consent_v1";
 let choice="";try{choice=localStorage.getItem(key)||"";}catch(_){}
 function excluded(){try{const q=new URLSearchParams(location.search);return localStorage.getItem("csf_escludi_visite")==="1"||!!localStorage.getItem("csf_admin_pin")||q.get("admin")==="1"||q.get("escludi")==="1";}catch(_){return true;}}
 function allowed(){return choice==="yes"&&!excluded();}
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
 window.CsfMetrics={
   allowed,
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
   banner.hidden=choice==="yes"||choice==="no"||excluded();
   document.getElementById("csf-consent-yes").addEventListener("click",()=>decide("yes"));
   document.getElementById("csf-consent-no").addEventListener("click",()=>decide("no"));
   document.getElementById("csf-consent-settings").addEventListener("click",()=>{banner.hidden=false;banner.scrollIntoView({block:"center"});});
   start();
 });
})();