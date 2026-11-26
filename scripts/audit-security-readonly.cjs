"use strict";
const {initializeApp,cert,deleteApp}=require("firebase-admin/app");
const {getDatabase}=require("firebase-admin/database");
const fs=require("node:fs");
const summarize=v=>{if(v===undefined)return "inherit";if(v===false||v==="false")return "deny";if(v===true||v==="true")return "public";const s=String(v);return {requiresAuth:/auth\s*!=\s*null|auth\.uid|auth\.token/.test(s),uidOrRoleRestricted:/auth\.uid\s*={2,3}|={2,3}\s*auth\.uid|auth\.token\.(?:email|admin|role)|(?:admin|moderator)s?['"]?\).*auth\.uid|auth\.uid\).*\.val/.test(s),genericAuthOnly:/^\s*auth\s*!=\s*null\s*$/.test(s),validatesData:/newData|data\.|now/.test(s)}};
function inspect(rules,path){const levels=[rules];let node=rules;for(const part of path.split("/")){if(!part)continue;node=node?.[part]||Object.entries(node||{}).find(([k])=>k.startsWith("$"))?.[1];levels.push(node||{});}return {path,read:levels.map(n=>summarize(n[".read"])),write:levels.map(n=>summarize(n[".write"]))};}
(async()=>{for(const cfg of [{name:"eventi",secret:"EVENT_STATS_FIREBASE_SERVICE_ACCOUNT",project:"chesifa-cerignola",paths:["","eventiManuali","eventiManuali/example","localiCerignola","localiCerignola/example","segnalazioniDaApprovare","segnalazioniDaApprovare/example","statisticheEventi/example","statisticheEventi/example/open","statistiche/visiteTotali"]}]){
 const key=JSON.parse(process.env[cfg.secret]||"null");if(!key||key.project_id!==cfg.project)throw Error("Credenziale non valida");
 const app=initializeApp({credential:cert(key),databaseURL:"https://chesifa-cerignola-default-rtdb.europe-west1.firebasedatabase.app"},cfg.name);
 try{const rules=(await getDatabase(app).getRulesJSON()).rules;console.log("AUDIT "+JSON.stringify({name:cfg.name,paths:cfg.paths.map(p=>inspect(rules,p))}));}finally{await deleteApp(app);}
}})().catch(e=>{console.error("Audit non completato: "+String(e.message).slice(0,160));process.exitCode=1;});
