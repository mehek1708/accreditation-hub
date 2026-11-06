(async()=>{
 await authReady;
 const $=s=>document.querySelector(s),people=location.pathname==='/people';
 const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
 let records=[],busy=false;
 $('#admin-title').textContent=people?'People & access':'Archives';
 $('#admin-description').textContent=people?'Only approved Northwest University Microsoft accounts can enter. Staff can update existing work. Administrators can also add, delete, restore, and manage people.':'Deleted tracker records stay here until an administrator restores or permanently deletes them. Google Drive files are never deleted by the tracker. Restore a parent cycle or standard before its children.';
 $('#person-form').hidden=!people;

 if(people){
  $('#owner-management').hidden=false;
  try{
   const response=await trackerFetch('/api/cycles');const data=await response.json();if(!response.ok)throw Error(data.error);
   $('#owner-form').elements.cycle.innerHTML=data.cycles.map(c=>`<option value="${esc(c.id)}">${esc(c.name)} (${esc(c.id)})</option>`).join('');
  }catch(e){$('#owner-message').textContent=e.message;}
  $('#owner-form').onsubmit=async e=>{
   e.preventDefault();const form=e.target,button=form.querySelector('button');button.disabled=true;
   try{
    const name=form.elements.owner.value.trim();if(!name)throw Error('Enter an owner name.');
    const url='/api/cycles/'+encodeURIComponent(form.elements.cycle.value)+'/project';
    const response=await trackerFetch(url);const data=await response.json();if(!response.ok)throw Error(data.error);
    const existing=[...(data.project.owners||[]),...data.project.standards.flatMap(s=>s.criteria.map(c=>c.owner)),...data.project.reviews.map(r=>r.owner)];
    if(existing.some(n=>n.trim().toLowerCase()===name.toLowerCase()))throw Error('This owner is already available in this cycle.');
    data.project.owners=[...(data.project.owners||[]),name];
    const saved=await trackerFetch(url,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});const result=await saved.json();if(!saved.ok)throw Error(result.error);
    form.elements.owner.value='';$('#owner-message').textContent='Owner added. Refresh the workspace to see the updated dropdown.';
   }catch(e){$('#owner-message').textContent=e.message;}finally{button.disabled=false;}
  };
 }
 async function refresh(){const response=await trackerFetch(people?'/api/users':'/api/archives');const data=await response.json();if(!response.ok)throw Error(data.error);records=data[people?'users':'archives'];
 $('#admin-list').innerHTML=records.map(r=>people?`<article class="admin-record"><h2>${esc(r.email)}</h2><p>${esc(r.role)} · ${esc(r.oid)}</p><div class="record-actions"><button data-edit="${esc(r.oid)}">Edit role / details</button><button class="danger" data-remove="${esc(r.oid)}" ${r.oid===trackerUser.oid?'disabled':''}>Delete access → Archives</button></div></article>`:`<article class="admin-record"><h2>${esc(r.label)}</h2><p>${esc(r.kind)}${r.cycle?' · '+esc(r.cycle):''} · Deleted ${esc(new Date(r.deleted*1000).toLocaleString())}</p><div class="record-actions"><button class="primary" data-restore="${esc(r.id)}">Restore</button><button class="danger" data-purge="${esc(r.id)}">Permanently delete</button></div></article>`).join('')||'<p>No records here.</p>';}
 async function save(url,data){if(busy)return;busy=true;$('#admin-error').textContent='';try{const response=await trackerFetch(url,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});const result=await response.json();if(!response.ok)throw Error(result.error);await refresh();return true;}catch(e){$('#admin-error').textContent=e.message;return false;}finally{busy=false;}}
 $('#person-form').onsubmit=async e=>{e.preventDefault();if(await save('/api/users/save',Object.fromEntries(new FormData(e.target))))e.target.reset();};
 $('#admin-list').onclick=async e=>{const b=e.target.closest('button');if(!b||busy)return;
 if(b.dataset.edit){const r=records.find(r=>r.oid===b.dataset.edit);for(const k of ['email','oid','role'])$('#person-form').elements[k].value=r[k];$('#person-form').elements.email.focus();}
 if(b.dataset.remove&&confirm('Remove this person’s access and end their active sessions? You can restore access from Archives.'))await save('/api/users/archive',{oid:b.dataset.remove});
 if(b.dataset.restore)await save('/api/archives/restore',{id:b.dataset.restore});
 if(b.dataset.purge){const confirmation=prompt('Permanently delete this archived tracker record? This cannot be undone here. Linked Google Drive files will remain untouched. Type DELETE to continue.');if(confirmation==='DELETE')await save('/api/archives/purge',{id:b.dataset.purge,confirmation});}
 };
 try{await refresh();}catch(e){$('#admin-error').textContent=e.message;}
})();
