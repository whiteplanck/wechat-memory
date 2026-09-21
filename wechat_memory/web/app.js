"use strict";
const $ = id => document.getElementById(id);
let messages = [], selected = {conversation:null, day:null}, limit = 100, photoData = null, analysis = "", revision = 0, photoRevision = 0, importRevision = 0;
let activeArchive = null;
const token = document.querySelector('meta[name="session-token"]').content;
function status(text, error=false) { $("status").textContent=text; $("status").classList.toggle("error",error); }
async function api(route,data) {
  const response=await fetch(`/api/${route}`,{method:"POST",headers:{"Content-Type":"application/json","X-Session-Token":token},body:JSON.stringify(data)});
  const result=await response.json(); if(!response.ok) throw new Error(result.error || "操作失败"); return result;
}
function node(tag,text,cls) { const e=document.createElement(tag); if(text!==undefined)e.textContent=text;if(cls)e.className=cls;return e; }
function filtered() { const q=$("search").value.toLocaleLowerCase();return messages.filter(m=>(!selected.conversation||m.conversation===selected.conversation)&&(!selected.day||m.timestamp.startsWith(selected.day))&&(!q||`${m.text} ${m.sender}`.toLocaleLowerCase().includes(q))); }
function invalidate() {revision++;analysis="";$("analysis").textContent="筛选已更新，点击分析当前筛选生成结果。";$("save-analysis").disabled=true;}
function download(text,name,type="text/plain") { const url=URL.createObjectURL(new Blob([text],{type:`${type};charset=utf-8`})); const a=node("a");a.href=url;a.download=name;document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),1000); }
function renderTree() {
  $("tree").replaceChildren();const groups=new Map();for(const m of messages){if(!groups.has(m.conversation))groups.set(m.conversation,new Map());const days=groups.get(m.conversation);const day=m.timestamp.slice(0,10);days.set(day,(days.get(day)||0)+1);}
  if(!groups.size)$("tree").append(node("p","导入后，会话和日期会出现在这里。","muted"));
  for(const [name,days] of groups){const details=node("details");details.open=true;details.append(node("summary",name));const all=node("button","整个会话","tree-day");all.onclick=()=>select(name,null);details.append(all);for(const [day,n] of days){const b=node("button",`${day} · ${n}`,"tree-day");b.classList.toggle("selected",selected.conversation===name&&selected.day===day);b.onclick=()=>select(name,day);details.append(b);}$("tree").append(details);}
}
function select(conversation,day){selected={conversation,day};limit=100;invalidate();renderTree();render();}
function render() {
  $("backup").disabled=!activeArchive||$("backup").dataset.busy==="true";
  $("material").disabled=!filtered().length;
  const rows=filtered();$("count").textContent=rows.length;$("conversations").textContent=new Set(rows.map(m=>m.conversation)).size;$("people").textContent=new Set(rows.map(m=>m.sender)).size;$("photos").textContent=rows.filter(m=>m.type==="image").length;
  $("title").textContent=messages.length?"每段对话，都有迹可循。":"从一次对话，找回一段记忆。";$("scope").textContent=[selected.conversation||"全部记录",selected.day].filter(Boolean).join(" / ");$("messages").replaceChildren();
  if(!rows.length){const box=node("div",undefined,"empty");box.append(node("strong",messages.length?"没有匹配的消息":"你的第一份聊天档案"),node("p",messages.length?"尝试调整搜索或选择其他日期。":"导入标准 JSON，或从左侧虚构示例开始。"));$("messages").append(box);}
  for(const m of rows.slice(0,limit)){const article=node("article",undefined,"message"),head=node("header");head.append(node("strong",m.sender),node("span",m.timestamp.replace("T"," ")));article.append(head,node("p",m.text||`[${m.type}]`),node("small",`${m.conversation} · 消息 ${m.id}`));if(m.media.length)article.append(node("small","附件引用："+m.media.join("，")));$("messages").append(article);}
  $("more").hidden=rows.length<=limit;document.querySelectorAll("[data-export]").forEach(b=>b.disabled=!rows.length);$("analyze").disabled=!rows.length||$("analyze").dataset.busy==="true";renderCalendar();
}
function events(){return photoData?photoData.events:filtered().filter(m=>m.type==="image").map(m=>({date:m.timestamp.slice(0,10),title:`${m.sender} · ${m.text||"照片"}`}));}
function setMonth(){const first=events()[0];$("month").value=first?first.date.slice(0,7):new Date().toISOString().slice(0,7);}
function renderCalendar(){
  $("calendar-source").textContent=photoData?`日期依据：照片 EXIF 拍摄日期，共 ${photoData.events.length} 张。筛选聊天不会改变此照片目录。`:"日期依据：当前筛选中图片消息的发送日期。";
  if(!$("month").value)setMonth();const [year,month]=$("month").value.split("-").map(Number);if(!year||!month)return;const offset=(new Date(year,month-1,1).getDay()+6)%7,count=new Date(year,month,0).getDate(),grid=$("calendar");grid.replaceChildren();
  for(let i=0;i<offset;i++)grid.append(node("div",undefined,"day blank"));const byDate=new Map();for(const e of events()){if(!byDate.has(e.date))byDate.set(e.date,[]);byDate.get(e.date).push(e);}
  for(let day=1;day<=count;day++){const cell=node("div",undefined,"day");cell.append(node("span",day));const key=`${year}-${String(month).padStart(2,"0")}-${String(day).padStart(2,"0")}`;for(const e of byDate.get(key)||[])cell.append(node("p",e.title,"event"));grid.append(cell);}$("ics").disabled=!events().length;
}
function adoptArchive(result){
  activeArchive=result.archive||null;
  $("backup-result").textContent=activeArchive?`当前档案：${activeArchive.label}\n生成的备份会保存在档案目录下的 bundles 文件夹中。`:"请先导入或打开一个已保存档案。";
  $("import-notice").hidden=!(result.warnings?.length);
  $("import-warnings").textContent=(result.warnings||[]).join("\n");
  photoRevision++;messages=result.messages;selected={conversation:null,day:null};
  $("search").value="";photoData=null;$("skips").hidden=true;limit=100;
  invalidate();setMonth();renderTree();render();
  $("archives").value=result.archive?.id||"";
}
async function refreshArchives(){
  const current=$("archives").value, result=await api("archives",{});
  $("archives").replaceChildren(new Option("选择本地档案", ""));
  for(const item of result.archives){
    $("archives").append(new Option(`${item.label} · ${item.count} 条 · ${item.created_at.slice(0,10)}`, item.id));
  }
  $("archives").value=current;
  $("storage-path").textContent=`保存位置：${result.directory}`;
  if(result.errors.length)status(`${result.errors.length} 个档案无法读取，原文件已保留。请检查保存目录中的 JSON 文件。`,true);
  return result;
}
async function openArchive(id){
  const version=++importRevision;
  const result=await api("archive",{id});if(version!==importRevision)return;
  adoptArchive(result);status(`已打开本地档案：${result.archive.label}（${messages.length} 条）。文件：${result.archive.path}`);
}
async function importData(raw,label,save=true){
  const version=++importRevision;
  const result=await api("import",{raw,label,save,format:save?$("import-format").value:"standard",contact:$("import-contact").value,timezone:$("import-timezone").value});
  if(version!==importRevision)return;
  // Show the successfully imported data even if refreshing the archive list fails.
  adoptArchive(result);
  status(result.archive?`已从 ${result.source} 导入 ${messages.length} 条，保存到：${result.archive.path}`:`已载入 ${label}，示例不自动保存。`);
  try{await refreshArchives();if(version===importRevision)$("archives").value=result.archive?.id||"";}
  catch(e){status(result.archive?`档案已保存，但列表刷新失败：${e.message}`:e.message,true);}
}
$("import").onclick=()=>$("file").click();
$("file").onchange=async()=>{const file=$("file").files[0];if(!file)return;try{if(file.size>19*1024*1024)throw new Error("文件过大，请拆分为小于 19 MB 的文件");await importData(await file.text(),file.name);}catch(e){status(e.message,true);}finally{$("file").value="";}};
$("demo").onclick=()=>importData([{id:"demo-1",conversation:"周末旅行（虚构示例）",sender:"小林",timestamp:"2026-09-19T09:30:00+08:00",text:"周六去西湖散步，记得带相机。",type:"text"},{id:"demo-2",conversation:"周末旅行（虚构示例）",sender:"小周",timestamp:"2026-09-19T16:20:00+08:00",text:"今天拍的湖边照片。",type:"image",media:["photos/example.jpg"]},{id:"demo-3",conversation:"周末旅行（虚构示例）",sender:"小林",timestamp:"2026-09-20T10:00:00+08:00",text:"下周整理照片，做一本旅行日历。",type:"text"}],"虚构示例",false).catch(e=>status(e.message,true));
$("reset").onclick=()=>{$("search").value="";select(null,null);};$("clear").onclick=()=>{importRevision++;photoRevision++;activeArchive=null;messages=[];photoData=null;$("archives").value="";$("folder").value="";$("skips").hidden=true;$("skip-list").textContent="";$("search").value="";$("import-notice").hidden=true;$("backup-result").textContent="请先导入或打开一个已保存档案。";select(null,null);status("已关闭当前档案。本地文件仍保留，可从左侧重新打开。");};
$("archives").onchange=()=>{if($("archives").value)openArchive($("archives").value).catch(e=>status(e.message,true));};
$("reload-archives").onclick=()=>refreshArchives().catch(e=>status(e.message,true));
$("search").oninput=()=>{limit=100;invalidate();render();};$("more").onclick=()=>{limit+=100;render();};
document.querySelectorAll("[data-view]").forEach(b=>b.onclick=()=>{document.querySelectorAll("[data-view]").forEach(x=>{const active=x===b;x.setAttribute("aria-pressed",String(active));$(x.dataset.view+"-view").hidden=!active;});if(b.dataset.view==="calendar"){setMonth();renderCalendar();}});
document.querySelectorAll("[data-export]").forEach(b=>b.onclick=async()=>{try{const fmt=b.dataset.export;const r=await api("export",{messages:filtered(),format:fmt});download(r.content,`chat-${Date.now()}.${fmt==="json"?"json":"md"}`);status("已导出当前筛选的聊天记录。");}catch(e){status(e.message,true);}});
$("month").onchange=renderCalendar;$("chat-calendar").onclick=()=>{photoRevision++;photoData=null;$("skips").hidden=true;setMonth();renderCalendar();};
$("scan").onclick=async()=>{const b=$("scan"),version=++photoRevision;b.disabled=true;status("正在读取本地照片拍摄日期…");try{const result=await api("photos",{folder:$("folder").value});if(version!==photoRevision)return;photoData=result;$("skips").hidden=!result.skipped.length;$("skip-list").textContent=result.skipped.map(s=>`${s.file}：${s.reason}`).join("\n");setMonth();renderCalendar();status(`找到 ${result.events.length} 张带日期的照片，跳过 ${result.skipped.length} 张。`);}catch(e){if(version===photoRevision)status(e.message,true);}finally{b.disabled=false;}};
$("ics").onclick=async()=>{try{const content=photoData?photoData.ics:(await api("export",{messages:filtered(),format:"ics"})).content;download(content,`photos-${Date.now()}.ics`,"text/calendar");status("日历已下载，可手动导入日历应用。");}catch(e){status(e.message,true);}};
$("analyze").onclick=async()=>{const b=$("analyze"),version=revision;b.dataset.busy="true";b.disabled=true;$("save-analysis").disabled=true;status("本地模型正在分析，可能需要几分钟…");try{const result=await api("analyze",{messages:filtered(),model:$("model").value});if(version!==revision){status("聊天或筛选已改变，旧分析已丢弃，请重新分析。");return;}analysis=result.content;$("analysis").textContent=analysis;$("save-analysis").disabled=false;status("分析完成，请核对原始消息。 ");}catch(e){status(e.message,true);}finally{b.dataset.busy="false";render();}};
$("save-analysis").onclick=()=>download(analysis,`analysis-${Date.now()}.md`);
$("material").onclick=async()=>{
  try{const result=await api("material",{messages:filtered()});download(result.content,`analysis-material-${Date.now()}.txt`);
    status(`已导出分析材料：统计 ${result.coverage.total_messages} 条，样本 ${result.coverage.sampled_messages} 条。`);
  }catch(e){status(e.message,true);}
};
$("backup").onclick=async()=>{
  if(!activeArchive)return;const archive=activeArchive,b=$("backup");b.dataset.busy="true";b.disabled=true;
  status(`正在为「${archive.label}」生成本地备份并复制附件…`);
  try{const result=await api("bundle",{id:archive.id,media_root:$("media-root").value.trim()});
    const summary=`档案：${archive.label}\n备份目录：${result.path}\n离线浏览：打开目录内的 index.html\n${result.messages} 条消息，${result.conversations} 个会话\n已复制附件：${result.copied}；未复制：${result.skipped}\n未复制的附件详见 attachments-manifest.json。备份时请复制整个文件夹。`;
    if(activeArchive?.id===archive.id)$("backup-result").textContent=summary;
    status(`「${archive.label}」备份已保存：${result.path}（${result.skipped} 个附件未复制）`);
  }catch(e){status(`备份失败：${e.message}`,true);}finally{b.dataset.busy="false";render();}
};
setMonth();render();
const startupVersion=importRevision;
refreshArchives().then(result=>{
  if(startupVersion===importRevision&&result.archives.length&&!result.errors.length)return openArchive(result.archives[0].id);
}).catch(e=>status(`本地档案读取失败：${e.message}`,true));

// Optional browser-agent integration reuses the visible search, without
// transmitting records to a model or returning private message content.
if(document.modelContext?.registerTool){
  const lifecycle=new AbortController();
  try{
    Promise.resolve(document.modelContext.registerTool({
      name:"filter_chat_view",title:"筛选当前聊天视图",
      description:"Set the visible chat search and return only the matching message count. Does not invoke AI or export records.",
      inputSchema:{type:"object",properties:{query:{type:"string"}},required:["query"],additionalProperties:false},
      annotations:{readOnlyHint:false,untrustedContentHint:false},
      execute(input){
        if(!input||typeof input.query!=="string"||Object.keys(input).some(k=>k!=="query"))throw new Error("query must be a string");
        $("search").value=input.query;limit=100;invalidate();render();return {matchingMessages:filtered().length};
      }
    },{signal:lifecycle.signal})).catch(()=>{});
  }catch{ /* Browsers without the proposed API keep the full manual UI. */ }
  window.addEventListener("pagehide",()=>lifecycle.abort(),{once:true});
}
