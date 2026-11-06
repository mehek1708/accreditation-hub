'use strict';
const requestedEvidence=new URLSearchParams(location.search).get('next');
if(requestedEvidence&&/^\/evidence\/[0-9a-f]{32}$/.test(requestedEvidence))sessionStorage.setItem('tracker-return',requestedEvidence);
function afterLogin(){const target=sessionStorage.getItem('tracker-return');sessionStorage.removeItem('tracker-return');return target&&/^\/evidence\/[0-9a-f]{32}$/.test(target)?target:'/';}

window.authReady=(async()=>{
 const response=await fetch('/api/auth/status');
 const info=await response.json();
 if(location.pathname==='/login'){
  if(info.user){location.replace(afterLogin());return info;}
  const message=document.querySelector('#login-message'),button=document.querySelector('#microsoft-login');
  if(!info.configured){message.textContent='University sign-in is awaiting IT setup. Access is locked until Microsoft Entra is connected.';button.hidden=true;}
  if(info.localDevelopment){
   document.querySelector('#sign-in-description').textContent='Open your saved workspace on this computer with your local development password.';
   message.textContent='Local development mode — continue building on this computer. University sign-in can be connected before publishing.';
   const form=document.querySelector('#local-login');form.hidden=false;
   form.onsubmit=async e=>{e.preventDefault();const b=form.querySelector('button');b.disabled=true;try{const r=await fetch('/api/auth/local',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({password:form.elements.password.value})});if(!r.ok){const data=await r.json();throw Error(data.error);}location.assign(afterLogin());}catch(error){message.textContent=error.message;}finally{b.disabled=false;}};
  }
  else if(new URLSearchParams(location.search).has('error'))message.textContent='Sign-in was not completed. Use an approved Northwest University account, or contact your administrator.';
  return info;
 }
 if(!info.user){location.replace('/login');throw Error('Sign-in required');}
 window.trackerUser=info.user;
 const bar=document.createElement('nav');bar.className='account-bar';bar.setAttribute('aria-label','Account');
 const label=document.createElement('span');label.textContent=(info.localDevelopment?'LOCAL DEVELOPMENT · ': '')+info.user.email+' · '+(info.user.role==='admin'?'Administrator':'Staff');bar.append(label);
 if(info.user.role==='admin')for(const [url,text] of [['/archives','Archives'],['/people','People & access']]){const a=document.createElement('a');a.href=url;a.textContent=text;bar.append(a);}
 const logout=document.createElement('button');logout.type='button';logout.textContent='Sign out';logout.onclick=async()=>{await trackerFetch('/api/logout',{method:'POST'});location.assign('/login');};bar.append(logout);
 if(document.body.classList.contains('home'))document.querySelector('.home-header').append(bar);
 document.documentElement.dataset.role=info.user.role;
 return info;
})();
window.trackerFetch=async(url,options={})=>{
 const {user}=await authReady;
 const headers=new Headers(options.headers||{});
 if(options.method&&options.method!=='GET')headers.set('X-CSRF-Token',user.csrf);
 const response=await fetch(url,{...options,headers});
 if(response.status===401){location.assign('/login');throw Error('Your session expired. Please sign in again.');}
 return response;
};
