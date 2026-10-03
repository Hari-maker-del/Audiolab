(function(){
  function boot(){
    var studio=document.getElementById('page-studio');
    if(!studio || studio.innerHTML.trim()) return;
    studio.innerHTML='<div class="hero"><div><div class="eyebrow">Audiolab / Studio</div><h1>Create speech that sounds like you.</h1><p>Your voice. Your language. Your sound. A local-first Indian-language AI audio workspace.</p></div><div class="actions"><button class="btn primary" onclick="document.querySelector('[data-page=generate]').click()">Create Voice</button><button class="btn secondary" onclick="document.querySelector('[data-page=voices]').click()">Upload Reference</button></div></div><div class="card"><span class="status"><span class="dot"></span> IndicF5 · Local inference</span><h3 style="margin-top:15px">Audiolab is ready</h3><p class="muted">The web interface is live. The local AI backend must be running on your computer for voice analysis and generation.</p><div class="actions" style="margin-top:18px"><button class="btn secondary" onclick="location.reload()">Refresh</button></div></div>';
  }
  if(document.readyState==='loading') document.addEventListener('DOMContentLoaded',function(){setTimeout(boot,300)}); else setTimeout(boot,300);
})();
