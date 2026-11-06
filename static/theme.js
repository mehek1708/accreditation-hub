(() => {
  const key = 'nu-accreditation-theme';
  const system = window.matchMedia('(prefers-color-scheme: dark)');
  let preference;
  try { preference = localStorage.getItem(key); } catch (_) {}
  function apply(theme) {
    document.documentElement.dataset.theme = theme;
    document.querySelectorAll('[data-theme-toggle]').forEach(button => {
      const dark = theme === 'dark';
      button.textContent = dark ? '☀' : '☾';
      button.title = dark ? 'Switch to light theme' : 'Switch to dark theme';
      button.setAttribute('aria-label', dark ? 'Switch to light theme' : 'Switch to dark theme');
      button.setAttribute('aria-pressed', String(dark));
    });
  }
  const current = () => preference === 'light' || preference === 'dark' ? preference : system.matches ? 'dark' : 'light';
  apply(current());
  document.addEventListener('DOMContentLoaded', () => {
    apply(current());
    document.querySelectorAll('[data-theme-toggle]').forEach(button => button.addEventListener('click', () => {
      preference = document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark';
      try { localStorage.setItem(key, preference); } catch (_) {}
      apply(preference);
    }));
  });
  system.addEventListener('change', () => apply(current()));
  window.addEventListener('storage', event => {
    if (event.key === key || event.key === null) { preference = event.newValue; apply(current()); }
  });
})();

// Open the portal at its real top instead of restoring a partially clipped banner.
if ('scrollRestoration' in history) history.scrollRestoration = 'manual';
window.addEventListener('pageshow', () => {
  if (!location.hash && document.body.matches('.home,.workspace-page')) {
    window.scrollTo({top:0,left:0,behavior:'instant'});
    const sidebar=document.querySelector('.workspace-page aside');
    if(sidebar)sidebar.scrollTop=0;
  }
});

// Motion is automatic; device accessibility preferences still take precedence.
(() => {
 const reduced=window.matchMedia('(prefers-reduced-motion: reduce)');
 const apply=()=>document.documentElement.dataset.motion=reduced.matches?'off':'on';
 apply();reduced.addEventListener('change',()=>{apply();update();});
 let queued=false;
 function update(){
  queued=false;
  const header=document.querySelector('.home-header');if(!header)return;
  header.classList.toggle('is-scrolled',window.scrollY>12);
  document.documentElement.style.setProperty('--home-header-height',header.offsetHeight+'px');
  document.querySelectorAll('.home-main>section').forEach(section=>{
   const r=section.getBoundingClientRect(),vh=window.innerHeight;
   const entering=Math.max(0,Math.min(1,(r.top-vh*.55)/(vh*.45)));
   const leaving=Math.max(0,Math.min(1,(header.offsetHeight-r.bottom+vh*.28)/(vh*.28)));
   const amount=Math.max(entering,leaving);
   section.style.opacity=reduced.matches?'1':String(1-amount*.25);
   section.style.transform=reduced.matches?'none':'translateY('+((entering-leaving)*24)+'px)';
  });
 }
 function schedule(){if(!queued){queued=true;requestAnimationFrame(update);}}
 document.addEventListener('DOMContentLoaded',()=>{
  const header=document.querySelector('.home-header');
  if(header){new ResizeObserver(schedule).observe(header);update();}
 });
 window.addEventListener('scroll',schedule,{passive:true});window.addEventListener('resize',schedule);window.addEventListener('pageshow',schedule);
})();
