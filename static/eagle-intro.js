(async () => {
  const intro = document.querySelector('.eagle-intro');
  if (!intro) return;
  try {
    const info=await authReady;
    if(!info.user){intro.remove();return;}
    const hash=await crypto.subtle.digest('SHA-256',new TextEncoder().encode(info.user.csrf));
    const key=Array.from(new Uint8Array(hash),b=>b.toString(16).padStart(2,'0')).join('');
    if(localStorage.getItem('nu-eagle-login')===key){intro.remove();return;}
    localStorage.setItem('nu-eagle-login',key);
  } catch (_) {intro.remove();return;}

  const reduced = matchMedia('(prefers-reduced-motion: reduce)');
  const canvas = intro.querySelector('canvas'), ctx = canvas.getContext('2d');
  const blur = intro.querySelector('.intro-blur');
  let raf, timer;
  function finish() {
    if (!intro.isConnected) return;
    const focused = intro.contains(document.activeElement);
    clearTimeout(timer); cancelAnimationFrame(raf);
    intro.remove();
    document.removeEventListener('keydown', key);
    document.removeEventListener('focusin', focus);
    document.removeEventListener('visibilitychange', visibility);
    window.removeEventListener('resize', finish);
    window.removeEventListener('pagehide', finish);
    if (focused) document.querySelector('.university-logo')?.focus({preventScroll:true});
  }
  const key = e => { if (e.key === 'Escape') finish(); };
  const focus = e => { if (!intro.contains(e.target)) finish(); };
  const visibility = () => { if (document.hidden) finish(); };
  if (reduced.matches || !ctx) { finish(); return; }
  intro.querySelector('button').addEventListener('click', finish);
  document.addEventListener('keydown', key);
  document.addEventListener('focusin', focus);
  document.addEventListener('visibilitychange', visibility);
  window.addEventListener('resize', finish);
  window.addEventListener('pagehide', finish);
  reduced.addEventListener('change', e => { if (e.matches) finish(); });
  const load = src => new Promise((resolve,reject) => { const image=new Image();image.onload=()=>resolve(image);image.onerror=reject;image.src=src; });
  const clamp = x => Math.max(0,Math.min(1,x));
  const ease = x => x*x*(3-2*x);
  const mix = (a,b,t) => a+(b-a)*t;
  timer=setTimeout(finish,7000);
  load('/eagle-original-flight.png').then(sprite => {
    if (!intro.isConnected) return;
    clearTimeout(timer);
    const w=innerWidth,h=innerHeight,dpr=Math.min(devicePixelRatio||1,2);
    canvas.width=Math.round(w*dpr);canvas.height=Math.round(h*dpr);
    ctx.scale(dpr,dpr);ctx.imageSmoothingEnabled=true;ctx.imageSmoothingQuality='high';
    const cell=sprite.naturalWidth/3;
    const size=Math.min(430,w*.85);
    const start=performance.now();
    function pose(x,y,s,alpha,bank,elapsed,fold){
      ctx.save();ctx.globalAlpha=alpha;ctx.translate(x,y);ctx.rotate(bank);ctx.scale(-s/600,s/600);
      // Animate one intact feather silhouette continuously: no grid-cell switches,
      // overlapping wing poses, additive halos, or chopped-off feather edges.
      const shoulder=cell*.63;
      const flap=(1-Math.cos(elapsed/850*Math.PI*2))*.5;
      const stretch=mix(1,.48,flap*(1-fold));
      const mapY=v=>v<shoulder?shoulder+(v-shoulder)*stretch:v;
      for(let row=0;row<Math.ceil(shoulder);row+=2){
        const bottom=Math.min(row+2,shoulder);
        const topY=mapY(row),bottomY=mapY(bottom);
        ctx.drawImage(sprite,0,row,cell,bottom-row,-210,(topY/cell-.75)*420,420,(bottomY-topY)/cell*420+.25);
      }
      ctx.drawImage(sprite,0,shoulder,cell,cell-shoulder,-210,(shoulder/cell-.75)*420,420,(cell-shoulder)/cell*420);
      ctx.restore();
    }
    function draw(now){
      if(!intro.isConnected)return;
      const elapsed=now-start;
      ctx.clearRect(0,0,w,h);
      const progress=clamp(elapsed/4200);
      const x=mix(-size*.4,w+size*.4,progress);
      const revealed=clamp(x/w)*w;
      // Only the area ahead of the eagle is frosted; the page behind it is clear.
      blur.style.left = `${revealed}px`;
      pose(x,h*.48+Math.sin(progress*Math.PI*2)*10,size,ease(clamp(elapsed/180)),0,elapsed,0);
      if(progress>=1){finish();return;}
      raf=requestAnimationFrame(draw);
    }
    raf=requestAnimationFrame(draw);timer=setTimeout(finish,5200);
  }).catch(finish);
})();
