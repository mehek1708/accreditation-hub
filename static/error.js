/* Shared recovery UI: leaves open forms and unsaved text in place. */
(() => {
 const art=`<svg class="error-art" viewBox="0 0 300 240" aria-hidden="true"><ellipse cx="150" cy="218" rx="80" ry="10" fill="#95b8d5" opacity=".18"/><path d="M111 193l-9 23 20-7 14 7 3-23M163 193l4 23 14-7 20 7-10-23" fill="#f2b84e" stroke="#9b6625" stroke-width="3" stroke-linejoin="round"/><path d="M99 110Q73 154 103 198Q150 224 197 198Q227 151 201 110Z" fill="#765442"/><path d="M119 125Q99 169 125 196Q150 209 176 196Q201 163 180 125" fill="#b38a65"/><path d="M128 158l9 9 12-10 12 10 12-9M131 180l8 7 11-8 11 8 8-7" fill="none" stroke="#8b654c" stroke-width="3" stroke-linecap="round"/><g class="eagle-head"><path d="M100 104Q83 51 121 35l-3-11 20 6 15-12 10 14Q212 29 208 84l-5 32-21-6-14 17-18-14-18 14-14-17-22 5Z" fill="#fffaf0" stroke="#d8dfe7" stroke-width="3"/><ellipse cx="126" cy="74" rx="7" ry="11" fill="#18334e"/><ellipse cx="176" cy="74" rx="7" ry="11" fill="#18334e"/><circle cx="128" cy="71" r="2.5" fill="white"/><circle cx="178" cy="71" r="2.5" fill="white"/><path d="M137 90Q150 77 164 90l-14 22Z" fill="#f2b84e" stroke="#bd842d" stroke-width="2"/><path d="M116 56q10-5 19 0M168 55q10-4 17 2" fill="none" stroke="#b5b9b7" stroke-width="3" stroke-linecap="round"/></g><g class="scratch-pose"><path d="M101 120q-35 26-6 64l17-18" fill="#604333"/><g class="eagle-scratch"><path d="M192 175q42-9 28-57l-17-30q-13-8-12 6l10 32-20 15" fill="#765442" stroke="#604333" stroke-width="3"/><path d="M198 102l9-5m-6 14 10-5" stroke="#b38a65" stroke-width="3"/></g><text x="238" y="59" fill="#4c8ca6" font-family="Georgia" font-size="34">?</text></g><g class="plug-pose"><path d="M103 123Q55 130 65 169l44-10M196 123q49 7 39 46l-44-10" fill="#604333"/><path d="M69 167q-34 30 15 39h32q15 0 15-22M231 167q34 30-15 39h-32q-15 0-15-22" fill="none" stroke="#4c8ca6" stroke-width="6" stroke-linecap="round"/><rect x="118" y="165" width="24" height="24" rx="7" fill="#4c8ca6"/><path d="M124 165v-10m12 10v-10" stroke="#c1cbd5" stroke-width="5"/><rect x="158" y="165" width="24" height="24" rx="7" fill="#4c8ca6"/><path d="M164 172v7m12-7v7" stroke="#17334d" stroke-width="3"/><path d="M143 143l-4-7m18 7 4-7" stroke="#e9ad42" stroke-width="3" stroke-linecap="round"/></g></svg>`;
 function fill(el,mode,standalone=false){
  const offline=mode==='offline',missing=mode==='missing';
  el.classList.toggle('is-offline',offline);
  el.innerHTML=`${art}<div class="error-code">${offline?'Connection paused':missing?'404 · Page not found':'A little hiccup'}</div><${standalone?'h1':'h2'} id="eagle-error-title">${offline?'Uh-oh, no internet!':missing?'Uh-oh, wrong perch!':'Uh-oh, something went wrong!'}</${standalone?'h1':'h2'}><p>${offline?'Our connection came unplugged. Check your Wi-Fi or internet connection and try again.':missing?'This page may have moved or is no longer available. Let’s get you back to familiar skies.':'The portal couldn’t connect or finish that request. Give it a moment, then try again.'}</p>${standalone?'':'<p>Your open page is still here. Keep any unsaved text before reloading.</p>'}<div class="error-actions"><button type="button" class="error-primary" data-retry>${standalone?'Try again':'Check connection'}</button>${standalone?'<a href="/">Back to home</a>':'<button type="button" data-dismiss>Back to my page</button>'}</div><p data-error-status role="status"></p>`;
  el.querySelector('[data-dismiss]')?.addEventListener('click',()=>el.close());
  el.querySelector('[data-retry]').onclick=async()=>{
   const button=el.querySelector('[data-retry]'),status=el.querySelector('[data-error-status]');button.disabled=true;
   try{const r=await nativeFetch('/api/auth/status',{cache:'no-store'});if(!r.ok)throw Error();if(standalone){location.href=mode==='missing'?'/':location.href;}else{status.textContent='Connected again. Return to your page and retry your action.';}}
   catch(_){status.textContent=navigator.onLine?'The portal is still unavailable. Please try again shortly.':'Still offline. Check your connection and try again.';}finally{button.disabled=false;}
  };
 }
 const nativeFetch=window.fetch.bind(window);let panel;
 window.showPortalError=(mode=navigator.onLine?'error':'offline')=>{
  if(!document.body){document.addEventListener('DOMContentLoaded',()=>window.showPortalError(mode),{once:true});return;}
  if(document.body.classList.contains('error-page'))return;
  if(!panel){panel=document.createElement('dialog');panel.className='eagle-error';panel.setAttribute('aria-labelledby','eagle-error-title');document.body.append(panel);}
  fill(panel,mode);if(!panel.open)panel.showModal();
 };
 window.fetch=async(...args)=>{
  try{const r=await nativeFetch(...args);if(r.status>=500)window.showPortalError();return r;}
  catch(error){if(error.name!=='AbortError')window.showPortalError();throw error;}
 };
 const start=()=>{const root=document.querySelector('[data-error-page]');if(root)fill(root,navigator.onLine?root.dataset.errorPage:'offline',true);else if(!navigator.onLine)window.showPortalError('offline');
  if('serviceWorker' in navigator)navigator.serviceWorker.register('/sw.js').catch(()=>{});
 };
 window.addEventListener('offline',()=>window.showPortalError('offline'));
 if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',start);else start();
})();
