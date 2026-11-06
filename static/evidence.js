(async()=>{
 await authReady;
 const $=s=>document.querySelector(s),id=location.pathname.split('/')[2];let doc,busy=false;
 const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
 async function load(){
  const response=await trackerFetch('/api/evidence/'+id);const result=await response.json();if(!response.ok)throw Error(result.error);
  doc=result;$('#document-title').textContent=doc.title;document.title=doc.title+' · Evidence';
  $('#back-evidence').href='/cycles/'+doc.cycle+'?view=evidence';$('#document-link').value=new URL(doc.url,location.origin).href;
  $('#document-actions').hidden=false;$('#replace-document').hidden=!doc.available;$('#archive-document').hidden=!doc.available;
  $('#document-status').textContent=doc.available?'Saved privately · '+doc.versions.length+' version(s)':'This tracker record is inactive. The underlying files remain available to administrators.';
  $('#download-current').href='/api/evidence/'+id+'/download/'+doc.versions[0].id;
  $('#document-versions').innerHTML=doc.versions.map((v,i)=>`<article class="admin-record"><h3>${esc(v.filename)} ${i===0?'· Latest':''}</h3><p>${esc(new Date(v.created*1000).toLocaleString())} · ${(v.size/1024).toFixed(1)} KB</p><a href="/api/evidence/${id}/download/${v.id}">Download this version</a></article>`).join('');
 }
 $('#copy-document').onclick=async()=>{try{await navigator.clipboard.writeText($('#document-link').value);$('#document-status').textContent='Evidence link copied.';}catch(e){$('#document-link').focus();$('#document-link').select();$('#document-status').textContent='Select and copy the evidence link below.';}};
 $('#replace-document').onclick=()=>$('#replacement-file').click();
 $('#replacement-file').onchange=async e=>{
  const file=e.target.files[0];if(!file||busy)return;
  if(file.size>10*1024*1024||!file.size){$('#document-status').textContent='Choose a nonempty file up to 10 MB.';e.target.value='';return;}
  busy=true;$('#replace-document').disabled=true;$('#archive-document').disabled=true;$('#document-status').textContent='Uploading updated version…';
  try{const response=await trackerFetch('/api/evidence/'+id+'/versions',{method:'POST',headers:{'Content-Type':'application/octet-stream','X-File-Name':encodeURIComponent(file.name),'X-Evidence-Revision':String(doc.revision)},body:file});const result=await response.json();if(!response.ok)throw Error(result.error);await load();}
  catch(error){$('#document-status').textContent=error.message;}
  finally{busy=false;e.target.value='';$('#replace-document').disabled=false;$('#archive-document').disabled=false;}
 };
 $('#archive-document').onclick=async()=>{
  if(busy||!confirm('Delete this evidence record? Its uploaded files will remain saved.'))return;
  busy=true;$('#archive-document').disabled=true;$('#replace-document').disabled=true;
  try{const response=await trackerFetch('/api/evidence/'+id+'/archive',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({revision:doc.revision})});const result=await response.json();if(!response.ok)throw Error(result.error);location.assign('/cycles/'+doc.cycle+'?view=evidence');}
  catch(error){$('#document-status').textContent=error.message;busy=false;$('#archive-document').disabled=false;$('#replace-document').disabled=false;}
 };
 try{await load();}catch(error){$('#document-title').textContent='Evidence unavailable';$('#document-status').textContent=error.message;}
})();
