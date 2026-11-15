(() => {
  'use strict';
  const tracks=window.JUKEBOX_TRACKS, $=id=>document.getElementById(id);
  const audio=$('audio'); audio.volume=.8;
  let selected=1, loaded=-1, story=false, noticeTimer, context, analyser, data;
  const bars=Array.from({length:42},(_,i)=>{
    const col=document.createElement('div'); col.className='eq-column';
    const blocks=Array.from({length:7},()=>{const b=document.createElement('i');b.className='eq-block';col.append(b);return b;});
    $('equalizer');document.querySelector('.equalizer').append(col);return blocks;
  });
  function notify(message){$('notice').textContent=message;$('notice').hidden=false;clearTimeout(noticeTimer);noticeTimer=setTimeout(()=>$('notice').hidden=true,4500);}
  function current(){return tracks[selected];}
  function ready(){return !!current().src;}
  function format(seconds){return Number.isFinite(seconds)?`${Math.floor(seconds/60)}:${String(Math.floor(seconds%60)).padStart(2,'0')}`:'0:00';}
  function initializeAudio(){
    const Constructor=window.AudioContext||window.webkitAudioContext;
    if(!context&&Constructor){try{context=new Constructor();analyser=context.createAnalyser();analyser.fftSize=256;const source=context.createMediaElementSource(audio);source.connect(analyser);analyser.connect(context.destination);data=new Uint8Array(analyser.frequencyBinCount);}catch(e){console.warn('Audio visualization unavailable',e);}}
    if(context?.state==='suspended')context.resume().catch(()=>{});
  }
  function status(){
    const playing=!audio.paused&&loaded===selected;
    document.body.classList.toggle('playing',playing);
    $('toggle').textContent=playing?'Ⅱ':'▶';$('toggle').setAttribute('aria-label',playing?'Pause':'Play');
    $('home-play').textContent=ready()?(playing?'Ⅱ   PAUSE THIS TRACK':'▶   PLAY THIS TRACK'):'AUDIO COMING SOON';
    $('player-status').textContent=ready()?(playing?(story?'Story playback · ':'Playing · ')+current().subtitle:'Ready to play'):'Audio not added yet · replace src in tracks.js';
    $('availability').textContent=ready()?'AUDIO AVAILABLE':'AWAITING TEAM AUDIO';
    $('seek').disabled=!ready()||!Number.isFinite(audio.duration);
  }
  function updateTime(){
    const duration=loaded===selected?audio.duration:0, position=loaded===selected?audio.currentTime:0;
    $('time').textContent=`${format(position)} / ${format(duration)}`;
    $('seek').value=duration?position/duration*100:0;
    updateNightFrame(position);
  }
  function updateNightFrame(position){
    if(current().id!=='b')return;
    // Match sonify_nightlights.py: 2012 starts at 0s, each year lasts 2s.
    // Hold 2023 during the audio's final release/echo tail.
    const year=2012+Math.min(11,Math.max(0,Math.floor(position/2)));
    const image=$('night-image');
    if(image.dataset.year!==String(year)){
      image.src=`assets/nightlights/${year}.jpg`;
      image.alt=`NASA rendered global night lights in ${year}`;
      image.dataset.year=String(year);
    }
    $('visual-caption').textContent=`NASA RENDERED IMAGE · ${year}`;
    $('visual-tag').textContent=`NIGHT LIGHTS / ${year} · 2012—2023`;
  }
  // These small previews are bundled with the UI; original TIFFs aren't needed.
  const nightFrames=Array.from({length:12},(_,i)=>{const image=new Image();image.src=`assets/nightlights/${2012+i}.jpg`;return image;});
  function render(){
    const track=current();$('carousel').replaceChildren();
    for(let offset=-2;offset<=2;offset++){
      const index=(selected+offset+tracks.length)%tracks.length,t=tracks[index];
      const card=document.createElement('button');card.className='track-card'+(offset===0?' active':'');
      card.style.setProperty('--card',t.color);card.style.setProperty('--x',`${offset*91}%`);card.style.setProperty('--scale',offset===0?1.13:Math.abs(offset)===1?.79:.51);card.style.setProperty('--z',3-Math.abs(offset));
      card.setAttribute('aria-label',`${t.title}: ${t.subtitle}${offset===0?', selected':''}`);
      const number=document.createElement('span');number.className='number';number.textContent=String(index+1).padStart(2,'0');
      const label=document.createElement('span');label.className='card-label';label.textContent=t.title.toUpperCase();card.append(number,label);
      card.onclick=()=>{if(index===selected)location.hash=`track/${t.id}`;else select(index);};$('carousel').append(card);
    }
    $('cover').replaceChildren();
    if(track.id==='b'){const image=new Image();image.src='assets/nightlights.jpg';image.alt='NASA global night-lights map';$('cover').append(image);}
    else{const icon=document.createElement('span');icon.className='cover-icon';icon.textContent=track.icon;$('cover').append(icon);$('cover').style.background=track.color;}
    $('selected-title').textContent=track.title;$('selected-type').textContent=track.subtitle.toUpperCase();$('selected-description').textContent=track.description;
    $('selected-count').textContent=`${String(selected+1).padStart(2,'0')} / 04`;
    $('track-title').textContent=`${track.title} / ${track.subtitle}`;$('track-number').textContent=`${String(selected+1).padStart(2,'0')} of 04`;
    $('track-nav').replaceChildren();tracks.forEach((t,i)=>{const button=document.createElement('button');button.className='nav-track'+(i===selected?' active':'');if(i===selected)button.setAttribute('aria-current','page');
      const num=document.createElement('span');num.className='nav-number';num.textContent=String(i+1).padStart(2,'0');
      const text=document.createElement('span'),strong=document.createElement('strong'),small=document.createElement('small');strong.textContent=t.title;small.textContent=t.subtitle;text.append(strong,small);button.append(num,text);button.onclick=()=>select(i,true);$('track-nav').append(button);
    });
    $('night-image').hidden=track.id!=='b';$('visual-tag').textContent=track.visual;$('visual-caption').textContent=track.id==='b'?'NASA RENDERED IMAGE · 2023':'ILLUSTRATIVE SIGNAL · AUDIO PENDING';
    $('hearing').textContent=track.hearing;$('mapping').textContent=track.mapping;$('description').textContent=track.visualDescription;
    $('source').hidden=!track.source;if(track.source)$('source').href=track.source;
    status();updateTime();
  }
  function select(index,navigate=false){
    const wasPlaying=!audio.paused;audio.pause();story=false;selected=(index+tracks.length)%tracks.length;
    if(loaded!==selected){audio.removeAttribute('src');audio.load();loaded=-1;}
    render();if(navigate||location.hash.startsWith('#track/'))location.hash=`track/${current().id}`;
    if(wasPlaying&&ready())play();
  }
  async function play(){
    if(!ready()){notify(`${current().title} is waiting for your teammate’s audio. Track B is ready to play.`);return;}
    initializeAudio();
    if(loaded!==selected){audio.src=current().src;loaded=selected;audio.load();}
    try{await audio.play();}catch(error){notify('Could not play this file. Check its path in tracks.js and serve the repo over localhost.');console.warn(error);}status();
  }
  function toggle(){story=false;if(!audio.paused&&loaded===selected)audio.pause();else play();status();}
  function route(){
    const match=location.hash.match(/^#track\/([a-d])$/),isTrack=!!match;
    if(match){const index=tracks.findIndex(t=>t.id===match[1]);if(index!==selected)select(index);}
    $('home-view').hidden=isTrack;$('track-view').hidden=!isTrack;render();
  }
  $('home-prev').onclick=()=>select(selected-1);$('home-next').onclick=()=>select(selected+1);
  $('previous').onclick=()=>select(selected-1,true);$('next').onclick=()=>select(selected+1,true);
  $('home-play').onclick=toggle;$('toggle').onclick=toggle;$('open-track').onclick=()=>location.hash=`track/${current().id}`;
  $('story-play').onclick=()=>{const first=tracks.findIndex(t=>t.src);if(first<0){notify('Add an audio file first.');return;}select(first);story=true;location.hash=`track/${current().id}`;notify('Playing available tracks in order. Pending tracks are skipped.');play();};
  $('volume').oninput=event=>audio.volume=Number(event.target.value);
  $('seek').oninput=event=>{if(Number.isFinite(audio.duration)){audio.currentTime=Number(event.target.value)/100*audio.duration;updateTime();}};
  audio.addEventListener('seeked',updateTime);
  audio.addEventListener('timeupdate',updateTime);audio.addEventListener('loadedmetadata',()=>{updateTime();status();});
  audio.addEventListener('play',status);audio.addEventListener('pause',status);
  audio.addEventListener('error',()=>{if(loaded>=0){$('player-status').textContent='Audio file unavailable · check tracks.js';notify('Audio file unavailable. Check the configured WAV path.');}});
  audio.addEventListener('ended',()=>{if(story){const next=tracks.findIndex((t,i)=>i>selected&&t.src);if(next>=0){select(next,true);story=true;play();}else{story=false;status();notify('Story complete. More tracks will join when your teammates add them.');}}else status();});
  window.addEventListener('hashchange',route);
  document.addEventListener('keydown',e=>{if(/INPUT|TEXTAREA|BUTTON|A/.test(e.target.tagName))return;if(e.code==='Space'){e.preventDefault();toggle();}if(e.code==='ArrowRight')select(selected+1);if(e.code==='ArrowLeft')select(selected-1);});
  const canvas=$('visual'),ctx=canvas.getContext('2d');let ticks=0;
  function animate(){
    requestAnimationFrame(animate);ticks++;
    const playing=!audio.paused&&loaded===selected;
    if(analyser&&playing)analyser.getByteFrequencyData(data);
    bars.forEach((blocks,i)=>{const height=playing&&data?Math.max(1,Math.round(data[Math.floor(i*data.length/bars.length)]/255*7)):[2,3,4,2,2,5,3,2,2,2,4,5,6,4,3,3,4,2,2,5,3][i%21];blocks.forEach((b,j)=>b.className='eq-block'+(j<height?(j>=5?' hot':' lit'):''));});
    if($('track-view').hidden||ticks%2)return;
    const w=canvas.clientWidth,h=canvas.clientHeight;if(!w||!h)return;if(canvas.width!==w||canvas.height!==h){canvas.width=w;canvas.height=h;}
    ctx.clearRect(0,0,w,h);
    if(current().id!=='b'){
      ctx.strokeStyle='#263637';ctx.lineWidth=.5;for(let i=1;i<12;i++){ctx.beginPath();ctx.moveTo(i*w/12,40);ctx.lineTo(i*w/12,h-40);ctx.stroke();}
      ctx.fillStyle='#778889';ctx.font='10px monospace';ctx.textAlign='center';ctx.fillText('AWAITING YOUR EARTH SIGNAL',w/2,h/2-30);
    }
    const baseline=h*.72;ctx.beginPath();ctx.strokeStyle=playing?'#78eafa':'#48727a';ctx.lineWidth=1.4;
    if(playing&&analyser){const waveform=new Uint8Array(analyser.fftSize);analyser.getByteTimeDomainData(waveform);for(let i=0;i<waveform.length;i++){const x=i/(waveform.length-1)*w,y=baseline+(waveform[i]-128)/128*h*.17;i?ctx.lineTo(x,y):ctx.moveTo(x,y);}}
    else{ctx.moveTo(0,baseline);ctx.lineTo(w,baseline);}ctx.stroke();
  }
  route();animate();
})();
