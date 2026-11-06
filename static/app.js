'use strict';
const $ = s => document.querySelector(s);
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const statuses = ['Not Started','In Progress','Ready for Review','Complete'];
const evidence = ['Needed','Partially Collected','Complete','Not needed'];
const activeCycle = location.pathname.split('/').filter(Boolean)[1] || '2021-2031';
const projectApi = '/api/cycles/'+encodeURIComponent(activeCycle)+'/project';
let years = [];
const evidenceHref=value=>value?new URL(value,location.origin).href:'';
let evidenceRequest=0;
let project, revision, view=(['evidence','submission','overview-attention','overview-progress'].includes(new URLSearchParams(location.search).get('view'))?new URLSearchParams(location.search).get('view'):'standards'), search='', statusFilter='', semester='Fall', reviewYear=2026, busy=false, conflicted=false, editorAction;
const uid = () => Array.from(crypto.getRandomValues(new Uint8Array(16)), b=>b.toString(16).padStart(2,'0')).join('');
const allCriteria = () => project.standards.flatMap(s=>s.criteria);
function toast(message){ $('#toast').textContent=message; $('#toast').hidden=false; setTimeout(()=>$('#toast').hidden=true,9000); }
function badge(value){return `<span class="badge ${value==='Complete'?'complete':value==='Ready for Review'?'ready':value==='In Progress'||value==='Partially Collected'?'progress':''}">${esc(value)}</span>`;}
function options(values,current,blank){return (blank?`<option value="">${blank}</option>`:'')+values.map(v=>`<option value="${esc(v)}" ${String(v)===String(current)?'selected':''}>${esc(v)}</option>`).join('');}
async function commit(next){
 if(busy) return false;
 if(conflicted){toast('Download your backup, then reload to get the latest shared version.');return false;}
 busy=true; $('#save-state').textContent='Saving…';
 try{
  const response=await trackerFetch(projectApi,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({revision,project:next})});
  const result=await response.json();
  if(!response.ok){if(response.status===409)conflicted=true;throw Error(result.error||'Unable to save');}
  project=next;revision=result.revision;$('#save-state').textContent='✓ All changes saved';render();return true;
 }catch(e){$('#save-state').textContent=conflicted?'Conflict · reload required':'Save failed · please retry';toast(e.message);return false;}
 finally{busy=false;}
}
function render(){
 clearProgressChart();
 if(window.ChartEditor)ChartEditor.dispose();
 document.querySelectorAll('[data-section]').forEach(row=>row.hidden=(project.hiddenSections||[]).includes(row.dataset.section));
 const task=(project.workspaceTasks||[]).find(t=>'task:'+t.id===view);
 if(view.startsWith('task:')&&!task)view='standards';
 if((project.hiddenSections||[]).includes(view))view=['standards','evidence','reviews','submission'].find(k=>!project.hiddenSections.includes(k))||'empty';
 renderTaskNavigation();
 $('#metrics').hidden=!!task||view==='empty'||view.startsWith('overview-');$('.notice').hidden=!!task||view==='empty'||view.startsWith('overview-');
 $('#project-name').textContent=task?task.name:view==='overview-attention'?'Criteria needing attention':view==='overview-progress'?'Progress tracker':view==='empty'?'Workspace':view==='standards'?'Standards & Criteria':view==='reviews'?'Semester Reviews':view==='evidence'?'Evidence':'Submission Overview';$('#project-description').textContent=project.description;
 document.title=$('#project-name').textContent+' · '+project.name;
 const range=`${project.startYear}–${project.endYear}`;
 $('#cycle-heading').textContent=range+' CYCLE';
 $('#cycle-sidebar').textContent='Accreditation cycle · '+range;
 $('#cycle-footer').textContent='One workspace. A clear path to '+project.endYear+'.';
 document.querySelectorAll('.nav').forEach(b=>b.classList.toggle('active',(b.dataset.view===view||('task:'+b.dataset.task)===view)));
 const c=allCriteria(), complete=c.filter(x=>x.status==='Complete').length;
 $('#metrics').innerHTML=[['Criteria complete',`${complete}<small> / ${c.length}</small>`,`${c.length?Math.round(100*complete/c.length):0}% of the framework complete`],['In progress',c.filter(x=>x.status==='In Progress').length,'Moving toward the next milestone'],['Ready for review',c.filter(x=>x.status==='Ready for Review').length,'Awaiting a final review'],['Evidence complete',c.filter(x=>x.evidence==='Complete').length,`${c.filter(x=>!x.link).length} criteria need a document link`]].map(([label,note,caption])=>`<div class="metric"><span>${label}</span><strong>${note}</strong><small>${caption}</small></div>`).join('');
 if(view.startsWith('overview-'))renderSubmissionDetail(view==='overview-attention'?'attention':'progress');else if(view==='standards')renderStandards();else if(view==='reviews')renderReviews();else if(view==='evidence')renderEvidence();else if(task)renderWorkspaceTask(task);else if(view==='empty')$('#content').innerHTML='<p>Add a workspace task with +, or restore a section from Archives.</p>';else renderSubmission();
}
function inlineSelect(c,key){
 const owners=[...new Set([...(project.owners||[]),...allCriteria().map(c=>c.owner),...project.reviews.map(r=>r.owner)].filter(Boolean))].sort((a,b)=>a.localeCompare(b));
 const values=key==='owner'?owners:key==='status'?statuses:evidence;
 return `<select class="inline-select ${key}" data-inline="${key}" data-id="${esc(c.id)}" aria-label="${esc(c.code)} ${key}">${options(values,c[key],key==='owner'?'Unassigned':null)}</select>`;
}
function renderStandards(){
 const cards=project.standards.map((s,i)=>{
  const criteria=s.criteria.filter(c=>(!statusFilter||c.status===statusFilter)&&(!search||[s.title,c.code,c.title,c.owner,c.notes].join(' ').toLowerCase().includes(search.toLowerCase())));
  if(!criteria.length&&(search||statusFilter))return '';
  const complete=s.criteria.filter(c=>c.status==='Complete').length;
  return `<article class="standard"><div class="standard-heading"><div class="standard-title"><span class="number">${String(i+1).padStart(2,'0')}</span><div><h3>${esc(s.title)}</h3><div class="subtitle">${s.criteria.length} criteria · ${complete} complete</div></div></div><button data-action="edit-standard" data-id="${esc(s.id)}">Edit standard ↗</button></div>${s.description?`<p class="standard-description">${esc(s.description)}</p>`:''}<div class="mini-progress"><progress aria-label="${esc(s.title)} completion" max="${s.criteria.length||1}" value="${complete}"></progress></div><div class="table-wrap"><table><thead><tr><th>CRITERION</th><th>OWNER</th><th>STATUS</th><th>EVIDENCE</th><th>LIVING DOCUMENT</th><th>EVIDENCE LINK</th></tr></thead><tbody>${criteria.map(c=>`<tr><td><button class="criterion-name" data-action="edit-criterion" data-id="${esc(c.id)}" data-standard="${esc(s.id)}">${esc(c.code)} &nbsp; ${c.title==='criteria name'?'<em>criteria name</em>':esc(c.title)}</button></td><td>${inlineSelect(c,'owner')}</td><td>${inlineSelect(c,'status')}</td><td>${inlineSelect(c,'evidence')}</td><td>${c.link?`<a class="document-link" href="${esc(c.link)}" target="_blank" rel="noopener">Open Drive ↗</a>`:'<span class="subtitle">Link needed</span>'}</td><td class="criterion-evidence-cell">${c.evidenceLink?`<a class="document-link" href="${esc(evidenceHref(c.evidenceLink))}" target="_blank" rel="noopener">Open evidence ↗</a>`:`<input type="url" data-evidence-link="${esc(c.id)}" value="" placeholder="Paste evidence link" aria-label="${esc(c.code)} evidence link">`}</td></tr>`).join('')}</tbody></table></div><div class="standard-bottom"><button data-action="add-criterion" data-id="${esc(s.id)}">＋ Add criterion</button><span>Click a criterion to edit</span></div></article>`;
 }).join('');
 $('#content').innerHTML=`<div class="toolbar"><div><h2>Standards &amp; Criteria</h2><div class="subtitle">A shared view of every requirement.</div></div><button class="primary" data-action="add-standard">＋ Add standard</button><div class="filters"><input type="search" id="search" placeholder="Search criteria or owners…" aria-label="Search criteria or owners" value="${esc(search)}"><select id="status-filter" aria-label="Filter by status">${options(statuses,statusFilter,'All statuses')}</select></div></div>${cards||(project.standards.length?'<div class="empty">No standards or criteria match this view.</div>':'<div class="empty">Your framework is ready to build! Add standards and criteria to begin.</div>')}`;
 $('#search').oninput=e=>{const pos=e.target.selectionStart;search=e.target.value;renderStandards();$('#search').focus();$('#search').setSelectionRange(pos,pos);};
 $('#status-filter').onchange=e=>{statusFilter=e.target.value;renderStandards();};
}
function renderReviews(){
 const reviews=project.reviews.filter(r=>r.year===reviewYear&&r.semester===semester);
 $('#content').innerHTML=`<div class="toolbar"><div><h2>Semester reviews</h2><div class="subtitle">Review each standard together, one criterion at a time.</div></div><button class="primary" data-action="generate-reviews">＋ Create semester tasks</button><div class="filters"><select id="semester" aria-label="Semester">${options(['Spring','Fall'],semester)}</select><select id="review-year" aria-label="Review year">${options(years,reviewYear)}</select></div></div>${reviews.map(r=>{
 const s=project.standards.find(s=>s.id===r.standardId),done=s.criteria.length>0&&s.criteria.every(c=>r.checked.includes(c.id));
 return `<article class="review"><div class="review-top"><div><h3>${esc(s.title)}</h3><div class="subtitle">${r.semester} ${r.year} · ${esc(r.owner)||'Unassigned'} · ${r.due?'Due '+esc(r.due):'No due date'}</div></div><div>${badge(done?'Complete':'In Progress')} <button data-action="edit-review" data-id="${esc(r.id)}">Edit task ↗</button></div></div><div class="checklist">${s.criteria.map(c=>`<label><input type="checkbox" data-review="${esc(r.id)}" data-criterion="${esc(c.id)}" ${r.checked.includes(c.id)?'checked':''}>${esc(c.code)} · ${esc(c.title)}</label>`).join('')||'<p>Add criteria to this standard to begin its review.</p>'}</div><p class="notes">${esc(r.notes)}</p><div class="subtitle">${r.checked.length} / ${s.criteria.length} reviewed · Checklist completion does not change criterion status.</div></article>`;
 }).join('')||'<div class="empty">No tasks for this semester yet. Create semester tasks to add a review for every standard.</div>'}`;
 $('#semester').onchange=e=>{semester=e.target.value;renderReviews();};$('#review-year').onchange=e=>{reviewYear=Number(e.target.value);renderReviews();};
}
function renderSubmission(){
 $('#content').innerHTML=`<div class="toolbar"><div><h2>Submission overview</h2><div class="subtitle">Keep track of your criteria and submission progress.</div></div></div>
 <div class="overview-panels overview-preview-panels">
 <button type="button" class="summary overview-preview" data-action="overview-attention"><span class="overview-card-title">Criteria needing attention</span><span class="overview-card-description">Review standards, criteria, and items that need your team’s attention.</span></button>
 <button type="button" class="summary overview-preview" data-action="overview-progress"><span class="overview-card-title">Progress tracker</span><span class="overview-card-description">View charts of criteria completion, progress by standard, and evidence collection.</span></button>
 </div>`;
}
let progressChart=null,progressObserver=null;
function clearProgressChart(){progressObserver?.disconnect();progressChart?.dispose();progressChart=null;}
function submissionComparison(){
 return `<label class="progress-chart-choice">Show <select id="progress-chart-measure"><option value="overall">Overall progress</option><option value="percent">Criteria completion (%)</option><option value="counts">Completed vs. total criteria</option></select></label><label class="progress-chart-choice">Chart type <select id="progress-chart-type"><option value="bar">Column chart</option><option value="horizontal">Horizontal bar chart</option><option value="line">Line chart</option></select></label><div id="progress-comparison" role="img" aria-label="Completed criteria and total criteria by standard"></div><details><summary>View counts and standard names</summary><div class="table-wrap"><table><thead><tr><th>Standard</th><th>Completed</th><th>Total</th></tr></thead><tbody>${project.standards.map((s,i)=>`<tr><td>${i+1}. ${esc(s.title)}</td><td>${s.criteria.filter(c=>c.status==='Complete').length}</td><td>${s.criteria.length}</td></tr>`).join('')}</tbody></table></div></details>`;
}
function progressOptions(type,measure='counts'){
 const horizontal=type==='horizontal',percent=measure==='percent'||measure==='overall',names=project.standards.map((s,i)=>'Standard '+(i+1));
 const dark=document.documentElement?.dataset.theme==='dark',text=dark?'#c4d2e4':'#31465e',colors=dark?['#789bc8','#57d6c2']:['#244f7c','#087f73'];
 const overall=measure==='overall',criteria=allCriteria();
 const ratio=(done,total)=>total?Math.round(done/total*1000)/10:0;
 const reviewDone=project.reviews.filter(r=>{const standard=project.standards.find(s=>s.id===r.standardId);return standard?.criteria.length&&standard.criteria.every(c=>r.checked.includes(c.id));}).length;
 const evidenceRequired=criteria.filter(c=>c.evidence!=='Not needed');
 const overallCounts=[[criteria.filter(c=>c.status==='Complete').length,criteria.length],[evidenceRequired.filter(c=>c.evidence==='Complete').length,evidenceRequired.length],[reviewDone,project.reviews.length]];
 const overallNames=['Criteria complete','Evidence collected','Semester reviews'];
 const category={type:'category',data:overall?overallNames:names,axisLabel:{interval:0,rotate:!horizontal&&names.length>7?35:0,color:text}};
 const value={type:'value',min:0,max:percent?100:undefined,minInterval:1,name:percent?'Complete (%)':'Criteria',axisLabel:{color:text,formatter:percent?'{value}%':'{value}'},splitLine:{lineStyle:{color:dark?'#304258':'#e1e7ee'}}};
 const completed=s=>s.criteria.filter(c=>c.status==='Complete').length;
 const series=overall?[{name:'Overall progress',data:overallCounts.map(([done,total])=>ratio(done,total)),itemStyle:{color:colors[1]}}]:percent?[{name:'Criteria complete',data:project.standards.map(s=>s.criteria.length?Math.round(completed(s)/s.criteria.length*1000)/10:0),itemStyle:{color:colors[1]}}]:[{name:'Total criteria',data:project.standards.map(s=>s.criteria.length)},{name:'Completed criteria',data:project.standards.map(completed)}];
 return {animation:false,color:colors,textStyle:{fontFamily:'Times New Roman'},tooltip:{trigger:'axis',renderMode:'richText',formatter:params=>{const i=params[0].dataIndex;if(overall){const [done,total]=overallCounts[i];return overallNames[i]+'\n'+(total?done+' of '+total+' complete ('+ratio(done,total)+'%)':'No applicable items');}const s=project.standards[i];return s.title+'\n'+completed(s)+' of '+s.criteria.length+' criteria complete'+(s.criteria.length?' ('+Math.round(completed(s)/s.criteria.length*100)+'%)':' — no criteria added');}},legend:{top:0,textStyle:{color:text}},grid:{top:65,bottom:50,left:20,right:45,containLabel:true},xAxis:horizontal?value:category,yAxis:horizontal?category:value,series:series.map(s=>({...s,type:type==='line'?'line':'bar',barMaxWidth:42,symbolSize:9,label:{show:true,position:horizontal?'right':'top',color:text,formatter:percent?'{c}%':'{c}'}}))};
}
function mountProgressChart(){
 if(typeof echarts==='undefined')return;
 const node=$('#progress-comparison');if(!node)return;
 clearProgressChart();progressChart=echarts.init(node,null,{renderer:'svg'});
 const select=$('#progress-chart-type');
 const measure=$('#progress-chart-measure');
 const draw=()=>progressChart.setOption(progressOptions(select.value,measure.value),true);
 measure.onchange=draw;
 select.onchange=draw;draw();
 progressObserver=new ResizeObserver(()=>progressChart?.resize());progressObserver.observe(node);
}

function renderSubmissionDetail(section){
 const c=allCriteria(),needsAttention=c=>c.status!=='Complete'||!['Complete','Not needed'].includes(c.evidence)||!c.owner.trim()||!c.link;
 const gaps=c.filter(needsAttention),notStarted=c.length&&c.every(x=>x.status==='Not Started');
 const colors=['#8b98ab','#4388ee','#dea63f','#25a99a'];
 function graph(items,labels,palette){
  const total=items.reduce((a,b)=>a+b,0);let offset=0;
  const rectangles=items.map((n,i)=>{const width=total?n/total*400:0;const rect=`<rect x="${offset}" y="0" width="${width}" height="24" fill="${palette[i]}"/>`;offset+=width;return rect;}).join('');
  return `<svg class="overview-bar" viewBox="0 0 400 24" role="img" aria-label="${esc(labels.map((label,i)=>label+': '+items[i]).join(', '))}"><rect width="400" height="24" fill="#dbe2ec"/>${rectangles}</svg><ul class="overview-legend">${labels.map((label,i)=>`<li><svg width="10" height="10" aria-hidden="true"><circle cx="5" cy="5" r="5" fill="${palette[i]}"/></svg> ${esc(label)} <strong>${items[i]}</strong></li>`).join('')}</ul>`;
 }
 const statusGraph=items=>graph(statuses.map(status=>items.filter(x=>x.status===status).length),statuses,colors);
 $('#content').innerHTML=`<div class="toolbar"><div><button type="button" data-action="overview-back">← Submission overview</button><h2 tabindex="-1" id="overview-detail-heading">${section==='attention'?'Criteria needing attention':'Progress tracker'}</h2><div class="subtitle">See what needs attention and track your team’s progress.</div></div><button class="primary" data-action="print">Print / Save PDF</button></div>
 <div class="overview-detail"><section class="summary overview-attention" ${section!=='attention'?'hidden':''} aria-labelledby="attention-heading"><h3 id="attention-heading">Criteria needing attention</h3>
 ${!c.length?'<p>No criteria added yet.</p>':notStarted?'<p class="overview-alert">● Work not started</p>':`<p>${gaps.length?`${gaps.length} of ${c.length} criteria need attention.`:'All criteria meet the tracking checks.'}</p>`}
 <p class="subtitle">Check status, evidence, owner, and document links below.</p>
 ${project.standards.map(s=>`<details class="overview-standard"><summary><span>${esc(s.title)}</span><small>${s.criteria.filter(needsAttention).length} need attention · ${s.criteria.filter(x=>x.status==='Complete').length}/${s.criteria.length} complete</small></summary>
 ${s.criteria.map(item=>`<div class="overview-criterion"><h4>${item.link?`<a class="overview-link" href="${esc(item.link)}" target="_blank" rel="noopener">${esc(item.code)} · ${esc(item.title)} ↗</a>`:`${esc(item.code)} · ${esc(item.title)}`}</h4><p>${esc(item.owner)||'Unassigned'} · ${esc(item.status)}</p><p>Evidence: ${esc(item.evidence)}</p>${!item.link?'<p class="subtitle">Living-document link needed</p>':''}${item.evidenceLink?`<a class="overview-link" href="${esc(evidenceHref(item.evidenceLink))}" target="_blank" rel="noopener">View evidence ↗</a>`:''}${item.notes?`<p class="notes">${esc(item.notes)}</p>`:''}</div>`).join('')||'<p>No criteria added.</p>'}</details>`).join('')}
 <p class="subtitle overview-footnote">Tracking checks do not verify evidence quality or accreditation compliance.</p></section>
 <section class="summary overview-progress" ${section!=='progress'?'hidden':''} aria-labelledby="progress-heading"><h3 id="progress-heading">Progress tracker</h3><p>Based on the current saved statuses.</p>
 ${c.length?`<div class="overview-chart"><h4>Overall criteria progress</h4><p><strong>${Math.round(c.filter(x=>x.status==='Complete').length/c.length*100)}% complete</strong> · ${c.filter(x=>x.status==='Complete').length} of ${c.length} criteria</p></div>
 <div class="overview-chart"><h4>Progress charts</h4>${submissionComparison()}</div>`:'<p>Add criteria to see progress charts.</p>'}
 </section></div>`;
 if(section==='progress')mountProgressChart();
}

function field(key,label,value='',type='text',values=null,wide=false){return `<label class="${wide?'wide':''}">${label}${values?`<select name="${key}">${options(values,value)}</select>`:type==='textarea'?`<textarea name="${key}" ${key==='notes'&&label==='Notes'?'placeholder="enter notes/requirements"':''}>${esc(value)}</textarea>`:`<input name="${key}" type="${type}" value="${esc(value)}" ${['name','title','code'].includes(key)?'required':''} ${type==='url'?(key==='evidenceLink'?'placeholder="Paste the link copied from Evidence"':'placeholder="https://docs.google.com/document/d/…"'):''}>`}</label>`;}
function openEditor(kind,id,standardId){
 const s=project.standards.find(s=>s.id===(standardId||id));
 const item=kind==='project'?project:kind==='standard'?s:kind==='criterion'?s.criteria.find(c=>c.id===id):project.reviews.find(r=>r.id===id);
 const x=item||{};let fields='';
 if(kind==='project')fields=field('name','Project name',x.name,'text',null,true)+field('description','Project description',x.description,'textarea',null,true)+field('coordinator','Cycle coordinator',x.coordinator)+field('submissionDate','Target submission date',x.submissionDate,'date');
 if(kind==='standard')fields=field('title','Standard name',x.title,'text',null,true)+field('description','Guidance for staff',x.description,'textarea',null,true);
 if(kind==='criterion')fields=field('code','Criterion number',x.code)+field('title','Criterion title',x.title,'text',null,true)+field('owner','Owner',x.owner)+field('status','Status',x.status||statuses[0],'text',statuses)+field('evidence','Evidence status',x.evidence||evidence[0],'text',evidence)+field('link','Google Drive living-document link',x.link,'url',null,true)+field('evidenceLink','Evidence link',evidenceHref(x.evidenceLink),'url',null,true)+field('notes','Notes',x.notes,'textarea',null,true);
 if(kind==='review')fields=field('owner','Review owner',x.owner)+field('due','Due date',x.due,'date')+field('notes','Meeting notes and follow-up actions',x.notes,'textarea',null,true);
 $('#delete-evidence').hidden=kind!=='criterion'||!x.link||trackerUser.role!=='admin';
 $('#fields').innerHTML=fields;if(kind==='criterion'&&trackerUser.role!=='admin'){$('#fields').querySelector('[name=link]').readOnly=true;if(x.evidenceLink)$('#fields').querySelector('[name=evidenceLink]').readOnly=true;}$('#modal-title').textContent=(item?'Edit ':'Add ')+kind;$('#form-error').textContent='';$('#delete-item').hidden=!item||kind==='project'||trackerUser.role!=='admin';$('#delete-item').textContent='Delete → Archives';
 editorAction={kind,id,standardId:standardId||id,item};$('#modal').showModal();
}
$('#editor').onsubmit=async e=>{
 e.preventDefault();if(busy)return;const {kind,id,standardId,item}=editorAction;const values=Object.fromEntries(new FormData(e.target));if(values.year)values.year=Number(values.year);
 const next=structuredClone(project);const s=next.standards.find(s=>s.id===standardId);
 if(kind==='project')Object.assign(next,values);
 if(kind==='standard'){if(item)Object.assign(s,values);else next.standards.push({id:uid(),criteria:[],...values});}
 if(kind==='criterion'){if(item)Object.assign(s.criteria.find(c=>c.id===id),values);else s.criteria.push({id:uid(),year:project.startYear,...values});}
 if(kind==='review')Object.assign(next.reviews.find(r=>r.id===id),values);
 const btn=e.target.querySelector('[type=submit]');btn.disabled=true;
 if(await commit(next))$('#modal').close();else $('#form-error').textContent='Changes were not saved. Check the error message and retry. Your form is still here.';
 btn.disabled=false;
};
$('#delete-evidence').onclick=async()=>{
 const {id,standardId}=editorAction;
 if(!confirm('Delete this living-document link? The Google Drive file will remain untouched.'))return;
 const next=structuredClone(project);next.standards.find(s=>s.id===standardId).criteria.find(c=>c.id===id).link='';
 if(await commit(next))$('#modal').close();
};
$('#delete-item').onclick=async()=>{
 const {kind,id,standardId}=editorAction;
 if(!confirm(kind==='standard'?'Delete this standard, all its criteria, and its semester reviews? They will be kept in Archives and can be restored. Linked cloud files stay untouched.':`Move this ${kind} to Archives? You can restore it later.`))return;
 const next=structuredClone(project);
 if(kind==='standard'){next.standards=next.standards.filter(s=>s.id!==id);next.reviews=next.reviews.filter(r=>r.standardId!==id);}
 if(kind==='criterion'){const s=next.standards.find(s=>s.id===standardId);s.criteria=s.criteria.filter(c=>c.id!==id);next.reviews.forEach(r=>r.checked=r.checked.filter(c=>c!==id));}
 if(kind==='review')next.reviews=next.reviews.filter(r=>r.id!==id);
 if(await commit(next))$('#modal').close();
};
$('#close-modal').onclick=$('#cancel-modal').onclick=()=>$('#modal').close();
$('#edit-project').onclick=()=>openEditor('project');
$('.sidebar-bottom').title='Data is saved on this server, shared by everyone using its address.';
for(const b of document.querySelectorAll('.nav'))b.onclick=()=>{view=b.dataset.view;render();};
$('#content').onclick=async e=>{
 const b=e.target.closest('[data-action]');if(!b)return;
 const {action,id,standard}=b.dataset;
 if(action==='overview-attention'||action==='overview-progress'){
  location.href=location.pathname+'?view='+action;return;
 }
 if(action==='overview-back'){
  location.href=location.pathname+'?view=submission';return;
 }
 if(action==='add-standard')openEditor('standard');
 if(action==='edit-standard')openEditor('standard',id);
 if(action==='add-criterion')openEditor('criterion',undefined,id);
 if(action==='edit-criterion')openEditor('criterion',id,standard);
 if(action==='edit-review')openEditor('review',id);
 if(action==='print'){
  const collapsed=Array.from(document.querySelectorAll('.overview-standard')).filter(el=>!el.open);
  collapsed.forEach(el=>el.open=true);
  const restore=()=>{collapsed.forEach(el=>el.open=false);window.removeEventListener('afterprint',restore);};
  window.addEventListener('afterprint',restore);window.print();
 }
 if(action==='generate-reviews'){
 const next=structuredClone(project);let count=0;
 next.standards.forEach(s=>{if(!next.reviews.some(r=>r.standardId===s.id&&r.year===reviewYear&&r.semester===semester)){next.reviews.push({id:uid(),standardId:s.id,year:reviewYear,semester,owner:'',due:'',notes:'',checked:[]});count++;}});
 if(!count)return toast('Every standard already has a task for this semester, or no standards exist yet.');
 if(await commit(next))toast(`Created ${count} semester review tasks.`);
 }
};
$('#content').onchange=async e=>{
 if(e.target.matches('[data-evidence-link]')){
  const input=e.target,criterion=allCriteria().find(c=>c.id===input.dataset.evidenceLink);
  if(busy||conflicted){input.value=evidenceHref(criterion.evidenceLink);toast('Finish saving or reload before editing.');return;}
  const next=structuredClone(project);next.standards.flatMap(s=>s.criteria).find(c=>c.id===criterion.id).evidenceLink=input.value.trim();
  input.disabled=true;if(!await commit(next)){input.value=evidenceHref(criterion.evidenceLink);input.disabled=false;}return;
 }

 if(e.target.matches('[data-inline]')){
  const select=e.target, key=select.dataset.inline, original=allCriteria().find(c=>c.id===select.dataset.id);
  if(busy||conflicted){select.value=original[key];if(conflicted)toast('Reload to get the latest shared version before editing.');return;}
  let value=select.value;
  const next=structuredClone(project);
  next.standards.flatMap(s=>s.criteria).find(c=>c.id===original.id)[key]=value;
  select.disabled=true;
  const saved=await commit(next);
  if(!saved){select.value=original[key];select.disabled=false;}
  else document.querySelectorAll('[data-inline]').forEach(s=>s.disabled=false);
  return;
 }
 if(!e.target.matches('[data-review]'))return;
 const checkbox=e.target;if(busy){checkbox.checked=!checkbox.checked;return;}
 const next=structuredClone(project),r=next.reviews.find(r=>r.id===checkbox.dataset.review),id=checkbox.dataset.criterion;
 r.checked=checkbox.checked?[...r.checked,id]:r.checked.filter(x=>x!==id);checkbox.disabled=true;
 if(!await commit(next)){checkbox.checked=!checkbox.checked;checkbox.disabled=false;}
};
function download(name,body,type){const url=URL.createObjectURL(new Blob([body],{type}));const a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}
$('#backup').onclick=()=>download('acbsp-'+activeCycle+'-backup.json',JSON.stringify({format:1,cycleId:activeCycle,exportedAt:new Date().toISOString(),project},null,2),'application/json');
$('#export-csv').onclick=()=>{
 const rows=[['Standard','Criterion','Title','Owner','Status','Evidence status','Reporting year','Living document','Evidence link','Notes'],...project.standards.flatMap(s=>s.criteria.map(c=>[s.title,c.code,c.title,c.owner,c.status,c.evidence,c.year,c.link,evidenceHref(c.evidenceLink),c.notes]))];
 const cell=v=>{let s=String(v);if(/^[=+@\-\t\r]/.test(s))s="'"+s;return '"'+s.replace(/"/g,'""')+'"';};
 download('acbsp-'+activeCycle+'-criteria.csv','\uFEFF'+rows.map(r=>r.map(cell).join(',')).join('\r\n'),'text/csv;charset=utf-8');
};
$('#restore').onclick=()=>$('#restore-file').click();
$('#restore-file').onchange=async e=>{
 const file=e.target.files[0];if(!file)return;
 try{if(file.size>5_000_000)throw Error('Backup must be under 5 MB');const data=JSON.parse(await file.text());if(data.format!==1||!data.project)throw Error('Select a tracker JSON backup');if(data.cycleId&&data.cycleId!==activeCycle)throw Error('Open the matching cycle before restoring this backup.');if(confirm('Replace the shared '+activeCycle+' cycle with this backup? Download its current backup first.'))await commit(data.project);}catch(err){toast(err.message);}e.target.value='';
};
async function load(){try{await authReady;const response=await trackerFetch(projectApi);if(!response.ok)throw Error('Could not load project');const data=await response.json();project=data.project;revision=data.revision;years=Array.from({length:project.endYear-project.startYear+1},(_,i)=>project.startYear+i);reviewYear=Math.max(project.startYear,Math.min(new Date().getFullYear(),project.endYear));$('#save-state').textContent='✓ Connected to shared storage';render();}catch(e){$('#save-state').textContent='Connection failed';$('#content').innerHTML='<div class="empty">Unable to load shared storage. Check the server and reload this page.</div>';toast(e.message);}}
load();

$('#delete-cycle').onclick=async()=>{
 if(busy||conflicted)return toast('Finish saving or reload before deleting this cycle.');
 if(!confirm('Delete this cycle and its standards, criteria, and reviews? Underlying evidence documents will remain saved.'))return;
 const button=$('#delete-cycle');button.disabled=true;
 try{
  const response=await trackerFetch('/api/archive-cycle',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id:activeCycle,revision})});
  const result=await response.json();if(!response.ok)throw Error(result.error);
  location.assign('/#cycles');
 }catch(error){toast(error.message);button.disabled=false;}
};

async function renderEvidence(){
 const request=++evidenceRequest;
 $('#content').innerHTML=`<div class="toolbar"><div><h2>Evidence library</h2><p>Upload a document, copy its link, and paste it into a criterion’s Evidence link field.</p></div><button type="button" class="primary" id="upload-evidence">＋ Upload evidence</button></div><input type="file" id="evidence-file" accept=".pdf,.docx,.xlsx,.pptx,.txt,.csv,.png,.jpg,.jpeg" hidden><p class="subtitle">PDF, Word, Excel, PowerPoint, TXT, CSV, PNG, or JPG · Up to 10 MB per file · Sign-in required to open links</p><p id="evidence-upload-status" role="status"></p><div id="evidence-list">Loading evidence…</div>`;
 $('#upload-evidence').onclick=()=>$('#evidence-file').click();
 $('#evidence-file').onchange=async event=>{
  const file=event.target.files[0];if(!file)return;
  if(file.size>10*1024*1024||!file.size){toast('Choose a nonempty document up to 10 MB.');event.target.value='';return;}
  const button=$('#upload-evidence'),status=$('#evidence-upload-status');button.disabled=true;status.textContent='Uploading '+file.name+'…';
  try{
   const response=await trackerFetch('/api/cycles/'+activeCycle+'/evidence',{method:'POST',headers:{'Content-Type':'application/octet-stream','X-File-Name':encodeURIComponent(file.name)},body:file});
   const result=await response.json();if(!response.ok)throw Error(result.error);
   toast('Evidence uploaded. Use Copy link to connect it to a criterion.');if(view==='evidence')renderEvidence();
  }catch(error){status.textContent=error.message;button.disabled=false;event.target.value='';toast(error.message);}
 };
 try{
  const response=await trackerFetch('/api/cycles/'+activeCycle+'/evidence');const result=await response.json();if(!response.ok)throw Error(result.error);
  if(view!=='evidence'||request!==evidenceRequest)return;
  $('#evidence-list').innerHTML=result.documents.map(d=>`<article class="evidence-card"><h3><a href="${esc(d.url)}">${esc(d.title)}</a></h3><p>${d.versions.length} version(s) · Latest: ${esc(d.versions[0].filename)} · ${(d.versions[0].size/1024).toFixed(1)} KB</p><label>Evidence link<input readonly value="${esc(evidenceHref(d.url))}" aria-label="Evidence link for ${esc(d.title)}"></label><div class="record-actions"><a href="${esc(d.url)}">Open document ↗</a><button type="button" data-copy-evidence="${esc(d.url)}">Copy link</button></div></article>`).join('')||'<div class="empty">Your evidence library is ready. Upload a document to begin.</div>';
  $('#evidence-list').onclick=async event=>{const button=event.target.closest('[data-copy-evidence]');if(!button)return;try{await navigator.clipboard.writeText(evidenceHref(button.dataset.copyEvidence));toast('Evidence link copied.');}catch(error){const input=button.closest('.evidence-card').querySelector('input');input.focus();input.select();toast('Select and copy the evidence link.');}};
 }catch(error){if(view==='evidence'&&request===evidenceRequest)$('#evidence-list').textContent=error.message;}
}

let editingTaskId=null,contextTaskId=null,contextTaskButton=null;
const taskCategories=['Text','Document','Media','Pictures','Charts','Other'];
function renderTaskNavigation(){
 $('#custom-workspaces').innerHTML=(project.workspaceTasks||[]).map(t=>`<div class="custom-workspace-row"><button class="nav ${view==='task:'+t.id?'active':''}" data-task="${esc(t.id)}" title="${esc(t.category)}">▧ &nbsp; ${esc(t.name)}</button></div>`).join('');
}
function openTaskEditor(id){
 if(!project||trackerUser.role!=='admin')return;
 const task=(project.workspaceTasks||[]).find(t=>t.id===id);editingTaskId=task?.id||null;
 const form=$('#task-form');form.reset();$('#task-error').textContent='';
 $('#task-modal-title').textContent=task?'Edit workspace task':'Add workspace task';
 form.elements.name.value=task?.name||'';
 form.elements.category.value=task&&taskCategories.includes(task.category)?task.category:task?'Other':'Text';
 form.elements.customCategory.value=task&&!taskCategories.includes(task.category)?task.category:'';
 syncTaskCategory();$('#task-modal').showModal();form.elements.name.focus();
}
function syncTaskCategory(){const custom=$('#task-form').elements.category.value==='Other';$('#custom-category-label').hidden=!custom;$('#task-form').elements.customCategory.required=custom;}
$('#workspace-add').onclick=()=>openTaskEditor();
$('#task-form').elements.category.onchange=syncTaskCategory;
$('#close-task').onclick=$('#cancel-task').onclick=()=>{if(!busy)$('#task-modal').close();};
$('#task-modal').addEventListener('cancel',e=>{if(busy)e.preventDefault();});
$('#task-form').onsubmit=async e=>{
 e.preventDefault();if(busy)return;
 const form=e.target,name=form.elements.name.value.trim(),category=form.elements.category.value==='Other'?form.elements.customCategory.value.trim():form.elements.category.value;
 if(!name||!category){$('#task-error').textContent='Enter a task name and category.';return;}
 const next=structuredClone(project);next.workspaceTasks=next.workspaceTasks||[];
 if(next.workspaceTasks.some(t=>t.id!==editingTaskId&&t.name.toLowerCase()===name.toLowerCase())){$('#task-error').textContent='A workspace task already uses this name.';return;}
 let id=editingTaskId;
 if(id)Object.assign(next.workspaceTasks.find(t=>t.id===id),{name,category});
 else{id=uid();next.workspaceTasks.push({id,name,category,content:'',link:''});}
 const button=form.querySelector('[type=submit]');button.disabled=true;
 if(await commit(next)){$('#task-modal').close();view='task:'+id;render();}else $('#task-error').textContent='Could not save the task. Check the message and try again.';
 button.disabled=false;
};
function closeTaskContext(){const menu=$('#task-context-menu');menu.hidden=true;}
function showTaskContext(id,button,x,y){
 if(trackerUser.role!=='admin')return;
 const builtIn=id.startsWith('section:');
 $('#edit-workspace-task').hidden=builtIn;
 $('#delete-workspace-task').textContent=builtIn?'Delete section':'Delete task';
 contextTaskId=id;contextTaskButton=button;const menu=$('#task-context-menu');menu.hidden=false;
 menu.style.left=Math.max(8,Math.min(x,window.innerWidth-menu.offsetWidth-8))+'px';
 menu.style.top=Math.max(8,Math.min(y,window.innerHeight-menu.offsetHeight-8))+'px';
 (builtIn?$('#delete-workspace-task'):$('#edit-workspace-task')).focus();
}
$('#custom-workspaces').onclick=e=>{
 const button=e.target.closest('[data-task]');if(button){view='task:'+button.dataset.task;render();}
};
$('#custom-workspaces').oncontextmenu=e=>{
 const button=e.target.closest('[data-task]');if(!button||trackerUser.role!=='admin')return;
 e.preventDefault();showTaskContext(button.dataset.task,button,e.clientX,e.clientY);
};
$('#custom-workspaces').onkeydown=e=>{
 if((e.shiftKey&&e.key==='F10')||e.key==='ContextMenu'){
 const button=e.target.closest('[data-task]');if(!button||trackerUser.role!=='admin')return;
 e.preventDefault();const rect=button.getBoundingClientRect();showTaskContext(button.dataset.task,button,rect.left,rect.bottom);
 }
};
document.addEventListener('click',e=>{if(!e.target.closest('#task-context-menu'))closeTaskContext();});
document.addEventListener('keydown',e=>{if(e.key==='Escape'&&!$('#task-context-menu').hidden){closeTaskContext();contextTaskButton?.focus();}});
$('#task-context-menu').onkeydown=e=>{if(['ArrowDown','ArrowUp'].includes(e.key)){e.preventDefault();const buttons=Array.from($('#task-context-menu').querySelectorAll('button')).filter(b=>!b.hidden);buttons[(buttons.indexOf(document.activeElement)+1)%buttons.length].focus();}};
$('#edit-workspace-task').onclick=()=>{closeTaskContext();openTaskEditor(contextTaskId);};
$('#delete-workspace-task').onclick=async()=>{
 closeTaskContext();if(busy)return;
 if(contextTaskId.startsWith('section:')){
 const key=contextTaskId.slice(8);
 if(!confirm('Remove this section from the workspace? Its records and files will stay saved. You can restore the section from Archives.'))return;
 const next=structuredClone(project);next.hiddenSections=[...new Set([...(next.hiddenSections||[]),key])];
 if(view===key)view=(['standards','evidence','reviews','submission'].find(k=>!next.hiddenSections.includes(k)))||'empty';
 if(await commit(next))toast('Section removed.');return;
 }
 const task=(project.workspaceTasks||[]).find(t=>t.id===contextTaskId);if(!task)return;
 if(!confirm('Delete “'+task.name+'”? Its contents can be restored from Archives. Linked documents will remain saved.'))return;
 const next=structuredClone(project);next.workspaceTasks=next.workspaceTasks.filter(t=>t.id!==task.id);
 if(await commit(next))toast('Workspace task deleted.');
};
function renderWorkspaceTask(task){
 if(task.category==='Charts'){
 ChartEditor.mount($('#content'),task,async config=>{const next=structuredClone(project);next.workspaceTasks.find(t=>t.id===task.id).chart=config;return await commit(next);});return;
 }
 $('#metrics').hidden=true;$('.notice').hidden=true;
 $('#content').innerHTML=`<div class="toolbar"><div><h2>${esc(task.name)}</h2><p>${esc(task.category)}</p></div>${trackerUser.role==='admin'?'<button type="button" id="edit-task-details">Edit name / category</button>':''}</div><article class="summary"><form id="task-content-form" class="task-content-form"><label>${task.category==='Text'?'Draft text':'Notes and requirements'}<textarea name="content" maxlength="30000" placeholder="Start writing here…">${esc(task.content)}</textarea></label><label>${task.category==='Media'?'Media link':'Document or resource link'}<input type="url" name="link" value="${esc(evidenceHref(task.link))}" placeholder="Paste a portal evidence link or an HTTPS link"></label>${task.link?`<a href="${esc(evidenceHref(task.link))}" target="_blank" rel="noopener">Open linked resource ↗</a>`:''}<div class="record-actions"><button type="submit" class="primary">Save changes</button><button type="button" id="task-evidence-library">Open evidence library</button></div><p id="task-content-error" role="status"></p></form></article>`;
 $('#edit-task-details')?.addEventListener('click',()=>openTaskEditor(task.id));
 $('#task-evidence-library').onclick=()=>{view='evidence';render();};
 $('#task-content-form').onsubmit=async e=>{
 e.preventDefault();if(busy)return;
 const next=structuredClone(project),t=next.workspaceTasks.find(t=>t.id===task.id);
 t.content=e.target.elements.content.value;t.link=e.target.elements.link.value.trim();
 const button=e.target.querySelector('[type=submit]');button.disabled=true;
 if(await commit(next))toast('Task saved.');else{$('#task-content-error').textContent='Not saved. Check the error message and try again.';button.disabled=false;}
 };
}

// Built-in sections use the same accessible menu as custom workspace tasks.
document.querySelectorAll('[data-section]').forEach(row=>{
 const button=row.querySelector('[data-view]');
 const open=(event)=>{if(trackerUser.role!=='admin')return;event.preventDefault();const r=button.getBoundingClientRect();showTaskContext('section:'+row.dataset.section,button,event.type==='contextmenu'?event.clientX:r.left,event.type==='contextmenu'?event.clientY:r.bottom);};
 row.addEventListener('contextmenu',open);
 row.addEventListener('keydown',event=>{if(event.key==='ContextMenu'||(event.shiftKey&&event.key==='F10'))open(event);});
});
