(() => {
  const $=s=>document.querySelector(s);
  const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  let cycles=[],saving=false;
  async function refresh(){
    try{
      await authReady;
      const response=await trackerFetch('/api/cycles');
      if(!response.ok)throw Error('Unable to load cycles. Check the connection and reload.');
      cycles=(await response.json()).cycles;
      $('#cycle-count').textContent=`${cycles.length} available cycle${cycles.length===1?'':'s'}`;
      const year=new Date().getFullYear();
      $('#cycle-list').innerHTML=cycles.map(c=>`<div class="cycle-entry"><a class="cycle-card" href="/cycles/${esc(c.id)}" aria-label="Open ${esc(c.name)}"><div class="cycle-top"><span class="cycle-type">ACBSP ACCREDITATION</span><span class="cycle-active">${year<c.startYear?'Upcoming cycle':year>c.endYear?'Past cycle':'Current cycle'}</span></div><h3>${c.startYear}–${c.endYear}</h3><div class="cycle-details"><h4>${esc(c.name)}</h4><p>${esc(c.description)||'A shared workspace for this accreditation cycle.'}</p>${c.coordinator?`<p class="cycle-meta">Coordinator: ${esc(c.coordinator)}</p>`:''}${c.submissionDate?`<p class="cycle-meta">Target submission: ${esc(c.submissionDate)}</p>`:''}</div><div class="cycle-features"><span>Standards &amp; Criteria</span><span>Evidence links</span><span>Semester reviews</span></div><div class="cycle-open">Open workspace <span aria-hidden="true">↗</span></div></a></div>`).join('');
      $('#cycle-template').innerHTML='<option value="starter">Standard starter framework (7 standards, 30 criteria)</option><option value="blank">Build your own framework (start empty)</option>'+cycles.map(c=>`<option value="${esc(c.id)}">Copy framework: ${esc(c.name)} (${c.startYear}–${c.endYear})</option>`).join('');
    }catch(error){$('#cycle-count').textContent='Connection unavailable';$('#cycle-list').textContent=error.message;}
  }
  const form=$('#cycle-form');
  $('#add-cycle').onclick=()=>{
    form.reset();$('#cycle-error').textContent='';
    const start=cycles.length?Math.max(...cycles.map(c=>c.endYear))+1:new Date().getFullYear();
    form.elements.startYear.value=Math.min(start,2199);
    form.elements.endYear.value=Math.min(start+9,2200);
    $('#cycle-modal').showModal();
  };
  $('#close-cycle').onclick=$('#cancel-cycle').onclick=()=>{if(!saving)$('#cycle-modal').close();};
  $('#cycle-modal').addEventListener('cancel',e=>{if(saving)e.preventDefault();});
  form.onsubmit=async event=>{
    event.preventDefault();if(saving)return;
    const data=Object.fromEntries(new FormData(form));data.startYear=Number(data.startYear);data.endYear=Number(data.endYear);
    $('#cycle-error').textContent='';
    if(data.endYear<=data.startYear||data.endYear-data.startYear>30){$('#cycle-error').textContent='End year must be after start year, with no more than 30 years between them.';return;}
    if(data.submissionDate&&(Number(data.submissionDate.slice(0,4))<data.startYear||Number(data.submissionDate.slice(0,4))>data.endYear)){ $('#cycle-error').textContent='Choose a submission date within the cycle years.';return; }
    saving=true;for(const button of form.querySelectorAll('button'))button.disabled=true;
    $('#create-cycle').textContent='Creating…';
    try{
      const response=await trackerFetch('/api/cycles',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});
      const result=await response.json();if(!response.ok)throw Error(result.error||'Could not create cycle.');
      $('#cycle-modal').close();
      await refresh();
      location.assign(result.url);
    }catch(error){$('#cycle-error').textContent=error.message;}
    finally{saving=false;for(const button of form.querySelectorAll('button'))button.disabled=false;$('#create-cycle').textContent='Create cycle';}
  };
  refresh();
})();
