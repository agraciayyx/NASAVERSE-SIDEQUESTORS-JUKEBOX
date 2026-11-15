(() => {
  'use strict';
  const tracks=window.JUKEBOX_TRACKS, $=id=>document.getElementById(id);
  const audio=$('audio'); audio.volume=.8;
  let selected=Math.max(0,tracks.findIndex(t=>t.src)), loaded=-1, story=false, noticeTimer, context, analyser, data;
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
    $('home-play').textContent=ready()?(playing?'♪   OPEN NOW PLAYING':'▶   PLAY THIS TRACK'):'VIEW THIS TRACK';
    $('player-status').textContent=introPlaying?`Story · the narrator introduces ${current().subtitle}`:ready()?(playing?(story?'Story playback · ':'Playing · ')+current().subtitle:'Ready to play'):'Audio not added yet · replace src in tracks.js';
    $('availability').textContent=ready()?'AUDIO AVAILABLE':'AWAITING TEAM AUDIO';
    $('seek').disabled=!ready()||!Number.isFinite(audio.duration);
  }
  function updateTime(){
    const duration=loaded===selected?audio.duration:0, position=loaded===selected?audio.currentTime:0;
    $('time').textContent=`${format(position)} / ${format(duration)}`;
    $('seek').value=duration?position/duration*100:0;
    updateNightFrame(position);updateTimeline(position);syncVideo(position);
  }
  // Video tracks: the NASA video plays in step with the audio clock, like the night-lights frames.
  // Pause holds the frame, seeking moves it, and the last frame holds through any audio tail.
  function syncVideo(position){
    const track=current(),video=$('track-video');
    if(!track.video||video.hidden||!Number.isFinite(video.duration))return;
    const target=Math.min(position,video.duration-0.05),playing=!audio.paused&&loaded===selected&&position<video.duration;
    if(playing){if(video.paused)video.play().catch(()=>{});if(Math.abs(video.currentTime-target)>0.3)video.currentTime=target;}
    else{if(!video.paused)video.pause();if(Math.abs(video.currentTime-target)>0.04)video.currentTime=target;}
  }
  function updateTimeline(position){
    const t=current().timeline;if(!t)return;
    const year=Math.min(t.end,Math.max(t.start,t.start+Math.floor(position/t.secondsPerYear+(t.offset||0))));
    $('visual-caption').textContent=$('track-video').hidden?'ILLUSTRATIVE SIGNAL · VIDEO FILE MISSING':`NASA VISUALIZATION · ${year}`;
    $('visual-tag').textContent=`${current().visual.split(' / ')[0]} / ${year} · ${t.label||`${t.start}—${t.end}`}`;
  }
  function updateNightFrame(position){
    if(!current().nightFrames)return;
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
  let dialAngle=0,dialIndex=selected;
  function placeDial(){
    const n=tracks.length,dial=$('dial');
    if(!dial.querySelector('.dial-mark'))tracks.forEach((t,i)=>{const a=(i*360/n-90)*Math.PI/180,m=document.createElement('button');m.className='dial-mark';m.textContent=String(i+1).padStart(2,'0');m.setAttribute('aria-label',`Select ${t.title}: ${t.subtitle}`);m.style.left=`${50+66*Math.cos(a)}%`;m.style.top=`${50+66*Math.sin(a)}%`;m.onclick=()=>select(i);dial.append(m);});
    let step=((selected-dialIndex)%n+n)%n;if(step>n/2)step-=n;dialAngle+=step*360/n;dialIndex=selected;   // turn the short way round
    $('knob').style.transform=`rotate(${dialAngle}deg)`;$('selected-count').style.transform=`rotate(${-dialAngle}deg)`;
    dial.querySelectorAll('.dial-mark').forEach((m,i)=>m.classList.toggle('on',i===selected));
  }
  function placeCards(){
    const n=tracks.length;
    tracks.forEach((t,index)=>{
      let card=$('carousel').querySelector(`[data-index="${index}"]`);
      if(!card){
        card=document.createElement('button');card.className='track-card';card.dataset.index=index;card.style.setProperty('--card',t.color);if(t.cover){card.classList.add('has-cover');card.style.setProperty('--cover',`url('${t.cover}')`);card.style.setProperty('--cover-pos',t.coverPosition||'center');}
        const number=document.createElement('span');number.className='number';number.textContent=String(index+1).padStart(2,'0');
        const label=document.createElement('span');label.className='card-label';label.textContent=t.title.toUpperCase();card.append(number,label);
        card.onclick=()=>{if(index===selected)location.hash=`track/${t.id}`;else select(index);};$('carousel').append(card);
      }
      let offset=((index-selected)%n+n)%n;if(offset>n/2)offset-=n;
      const previous=card.dataset.offset===undefined?offset:Number(card.dataset.offset);
      const wrapped=Math.abs(offset-previous)>2;   // jumped from one end to the other: fade in instead of flying across
      if(wrapped){card.style.transition='none';card.style.opacity='0';}
      card.classList.toggle('active',offset===0);card.hidden=Math.abs(offset)>2;card.dataset.offset=offset;
      card.style.setProperty('--x',`${Math.sign(offset)*[0,91,150][Math.min(2,Math.abs(offset))]}%`);card.style.setProperty('--scale',offset===0?1.13:Math.abs(offset)===1?.79:.51);card.style.setProperty('--z',3-Math.abs(offset));
      card.setAttribute('aria-label',`${t.title}: ${t.subtitle}${offset===0?', selected':''}`);
      if(wrapped){void card.offsetWidth;card.style.transition='';card.style.opacity='';}
    });
  }
  function render(){
    const track=current();placeCards();if(track.src)mediaURL(track.src).catch(()=>{});   // start loading the audio before Play is pressed
    $('cover').replaceChildren();
    if(track.cover){const image=new Image();image.src=track.cover;image.alt=`${track.subtitle}: NASA visualization`;image.style.objectPosition=track.coverPosition||'center';$('cover').append(image);$('cover').style.background='#000';}
    else{const icon=document.createElement('span');icon.className='cover-icon';icon.textContent=track.icon;$('cover').append(icon);$('cover').style.background=track.color;}
    $('selected-title').textContent=track.subtitle;$('selected-type').textContent=track.title.toUpperCase();$('selected-description').textContent=track.description;
    $('selected-count').textContent=String(selected+1).padStart(2,'0');placeDial();
    $('track-title').textContent=`${track.title} / ${track.subtitle}`;$('track-number').textContent=`${String(selected+1).padStart(2,'0')} of ${String(tracks.length).padStart(2,'0')}`;
    $('track-nav').replaceChildren();tracks.forEach((t,i)=>{const button=document.createElement('button');button.className='nav-track'+(i===selected?' active':'');if(i===selected)button.setAttribute('aria-current','page');
      const num=document.createElement('span');num.className='nav-number';num.textContent=String(i+1).padStart(2,'0');
      const text=document.createElement('span'),strong=document.createElement('strong'),small=document.createElement('small');strong.textContent=t.title;small.textContent=t.subtitle;text.append(strong,small);button.append(num,text);button.onclick=()=>select(i,true);$('track-nav').append(button);
    });
    const video=$('track-video');
    if(track.video){if(video.dataset.src!==track.video){video.dataset.src=track.video;video.hidden=false;const wanted=track.video;mediaURL(wanted).then(url=>{if(video.dataset.src===wanted)video.src=url;}).catch(()=>{if(video.dataset.src===wanted)video.dispatchEvent(new Event('error'));});}}
    else if(video.dataset.src){video.pause();video.removeAttribute('src');delete video.dataset.src;video.hidden=true;video.load();}
    $('night-image').hidden=!track.nightFrames;$('visual-tag').textContent=track.visual;$('visual-caption').textContent=track.nightFrames?'NASA RENDERED IMAGE · 2023':track.video&&!video.hidden?'NASA VISUALIZATION':track.src?'ILLUSTRATIVE SIGNAL':'ILLUSTRATIVE SIGNAL · AUDIO PENDING';
    $('hearing').textContent=track.hearing;$('mapping').textContent=track.mapping;$('description').textContent=track.visualDescription;
    $('source').hidden=!track.source;if(track.source)$('source').href=track.source;
    status();updateTime();updateNarrateButtons();
  }
  // Narrator: each track can have a spoken version of its two notes (assets/narration/).
  // The music dips while the narrator speaks and comes back when they finish.
  // Narration files get re-recorded often; a per-visit tag on their URLs stops the browser replaying an old copy.
  const loadedAt=Date.now(),fresh=path=>`${path}?v=${loadedAt}`;
  const narrator=$('narrator');let narrating=null;
  function musicVolume(){audio.volume=Number($('volume').value)*(narrating&&!narrator.paused?0.25:1);}
  function stopNarration(){narrator.pause();narrating=null;updateNarrateButtons();musicVolume();}
  function updateNarrateButtons(){document.querySelectorAll('.narrate').forEach(b=>{const on=narrating===b.dataset.part;b.classList.toggle('speaking',on);b.textContent=on?'■ STOP':'▶ LISTEN';b.hidden=!current().narration?.[b.dataset.part];});}
  document.querySelectorAll('.narrate').forEach(b=>b.onclick=()=>{
    if(narrating===b.dataset.part){stopNarration();return;}
    narrator.src=fresh(current().narration[b.dataset.part]);narrating=b.dataset.part;
    narrator.play().then(musicVolume).catch(()=>{notify('Could not play the narration file.');stopNarration();});updateNarrateButtons();
  });
  narrator.addEventListener('ended',stopNarration);
  // Captions: the bar under the video shows the sentence being spoken, word by word.
  // Timings come from assets/narration/captions.json, written by narration/make_narration.py.
  let captions={};fetch(fresh('assets/narration/captions.json')).then(r=>r.ok?r.json():{}).then(j=>captions=j).catch(()=>{});
  const storyVoice=$('story-voice');let shownCaption='';
  const clipKey=src=>decodeURIComponent(src.split('/').pop().split('?')[0]).replace(/\.mp3$/,'');
  // Story mode: the player controls go away and a read-only strip shows where the story is.
  function syncStoryMode(inStory){
    document.body.classList.toggle('story-mode',inStory);$('story-strip').hidden=!inStory;if(!inStory)return;
    const order=tracks.filter(t=>t.src),step=order.indexOf(current())+1;
    $('story-step').textContent=`${String(step).padStart(2,'0')} of ${String(order.length).padStart(2,'0')} · ${introPlaying?'Narrator':current().subtitle}`;
    const clock=introPlaying?storyVoice:audio,d=clock.duration,t=clock.currentTime;
    $('story-fill').style.width=Number.isFinite(d)&&d?`${t/d*100}%`:'0%';$('story-time').textContent=`${format(t)} / ${format(d)}`;
  }
  function updateCaption(){
    const inStory=story||introPlaying;$('caption-bar').hidden=!inStory;   // the caption bar belongs to Play Story only
    syncStoryMode(inStory);
    if(!inStory){shownCaption='';return;}
    const voice=!storyVoice.paused?storyVoice:!narrator.paused?narrator:null;let html,idle=!voice;
    if(voice){
      const lines=captions[clipKey(voice.src)]||[],t=voice.currentTime;
      const line=lines.filter(l=>l.start<=t+0.05).pop()||lines[0];
      if(line){const words=line.text.split(' '),said=Math.ceil(Math.min(1,Math.max(0,(t-line.start)/(line.end-line.start)))*words.length);
        html=`<span class="said">${words.slice(0,said).join(' ')}</span> ${words.slice(said).join(' ')}`;}
      else html='';
    }else html=current().description;
    if(html===shownCaption)return;shownCaption=html;
    $('caption').innerHTML=html;$('caption').classList.toggle('idle',idle);
    $('caption-tag').hidden=idle;$('caption-tag').textContent=voice===storyVoice?'STORY':'NARRATOR';$('caption-bar').classList.toggle('speaking',!idle);
  }
  // Play Story: before each track the narrator says one line of the storyline, then the music starts.
  let storyToken=0,introPlaying=false;
  function stopIntro(){introPlaying=false;storyVoice.pause();}
  async function storyStep(index){
    select(index,true);story=true;const token=++storyToken,intro=current().narration?.intro;
    if(loaded===selected){audio.currentTime=0;updateTime();}   // the story always starts a track from the top
    if(intro){
      introPlaying=true;storyVoice.src=fresh(intro);status();
      await new Promise(done=>{storyVoice.onended=done;storyVoice.onpause=done;storyVoice.play().catch(done);});
      introPlaying=false;
      if(token!==storyToken||!story||!storyVoice.ended)return;
    }
    play();
  }
  function select(index,navigate=false){
    stopNarration();stopIntro();storyToken++;
    const wasPlaying=!audio.paused;audio.pause();story=false;selected=(index+tracks.length)%tracks.length;
    if(loaded!==selected){audio.removeAttribute('src');audio.load();loaded=-1;}
    render();if(navigate||location.hash.startsWith('#track/'))location.hash=`track/${current().id}`;
    if(wasPlaying&&ready())play();
  }
  // Python's http.server can't serve parts of a file, so the browser can't seek in a WAV or video it streams from it.
  // Loading each file whole into memory first makes seeking work with the plain server.
  const mediaCache={};
  function mediaURL(path){
    if(!mediaCache[path])mediaCache[path]=fetch(path).then(r=>{if(!r.ok)throw new Error(`${r.status} ${path}`);return r.blob();}).then(blob=>URL.createObjectURL(blob));
    mediaCache[path].catch(()=>delete mediaCache[path]);
    return mediaCache[path];
  }
  async function play(){
    if(!ready()){notify(`${current().title} is waiting for your teammate’s audio. Pick a track that is ready to play.`);return;}
    initializeAudio();
    if(loaded!==selected){const want=selected,url=await mediaURL(current().src).catch(()=>current().src);if(want!==selected)return;audio.src=url;loaded=selected;audio.load();}
    try{await audio.play();}catch(error){notify('Could not play this file. Check its path in tracks.js and serve the repo over localhost.');console.warn(error);}status();
  }
  // Leaving the story: pausing, pressing play during a line, moving the playhead or opening a track yourself.
  function stopStory(){if(!story&&!introPlaying)return;story=false;stopIntro();storyToken++;$('notice').hidden=true;status();syncStoryMode(false);}
  function toggle(){if(introPlaying){stopStory();play();return;}story=false;if(!audio.paused&&loaded===selected)audio.pause();else play();status();}
  function route(){
    const match=location.hash.match(/^#track\/([a-z])$/),isTrack=!!match;
    if(match){const index=tracks.findIndex(t=>t.id===match[1]);if(index!==selected)select(index);}
    if(!isTrack&&(story||introPlaying)){stopStory();audio.pause();}
    $('home-view').hidden=isTrack;$('track-view').hidden=!isTrack;render();
  }
  $('home-prev').onclick=()=>select(selected-1);$('home-next').onclick=()=>select(selected+1);
  $('previous').onclick=()=>select(selected-1,true);$('next').onclick=()=>select(selected+1,true);
  $('home-play').onclick=()=>{stopStory();location.hash=`track/${current().id}`;if(ready()&&(audio.paused||loaded!==selected))play();};$('toggle').onclick=toggle;
  $('story-play').onclick=()=>{const first=tracks.findIndex(t=>t.src);if(first<0){notify('Add an audio file first.');return;}storyStep(first);notify('Playing the story: a short narration, then each track. Pending tracks are skipped.');};
  $('volume').oninput=musicVolume;
  $('seek').oninput=event=>{stopStory();if(Number.isFinite(audio.duration)){audio.currentTime=Number(event.target.value)/100*audio.duration;updateTime();}};
  audio.addEventListener('seeked',updateTime);
  audio.addEventListener('timeupdate',updateTime);audio.addEventListener('loadedmetadata',()=>{updateTime();status();});
  audio.addEventListener('play',status);audio.addEventListener('pause',status);
  audio.addEventListener('error',()=>{if(loaded>=0){$('player-status').textContent='Audio file unavailable · check tracks.js';notify('Audio file unavailable. Check the configured WAV path.');}});
  audio.addEventListener('ended',()=>{if(story){const next=tracks.findIndex((t,i)=>i>selected&&t.src);if(next>=0)storyStep(next);else{story=false;status();notify('Story complete. Thanks for listening.');}}else status();});
  window.addEventListener('hashchange',route);
  document.addEventListener('keydown',e=>{if(story||introPlaying)return;if(/INPUT|TEXTAREA|BUTTON|A/.test(e.target.tagName))return;if(e.code==='Space'){e.preventDefault();toggle();}if(e.code==='ArrowRight')select(selected+1);if(e.code==='ArrowLeft')select(selected-1);});
  const video=$('track-video');
  video.addEventListener('loadedmetadata',updateTime);
  video.addEventListener('error',()=>{if(!video.dataset.src)return;video.hidden=true;$('visual-caption').textContent='ILLUSTRATIVE SIGNAL · VIDEO FILE MISSING';console.warn('Video not found:',video.dataset.src);});
  audio.addEventListener('play',updateTime);audio.addEventListener('pause',updateTime);
  const canvas=$('visual'),ctx=canvas.getContext('2d');let ticks=0;
  function animate(){
    requestAnimationFrame(animate);ticks++;updateCaption();
    const playing=!audio.paused&&loaded===selected;
    if(analyser&&playing)analyser.getByteFrequencyData(data);
    bars.forEach((blocks,i)=>{const height=playing&&data?Math.max(1,Math.round(data[Math.floor(i*data.length/bars.length)]/255*7)):[2,3,4,2,2,5,3,2,2,2,4,5,6,4,3,3,4,2,2,5,3][i%21];blocks.forEach((b,j)=>b.className='eq-block'+(j<height?(j>=5?' hot':' lit'):''));});
    if($('track-view').hidden||ticks%2)return;
    const w=canvas.clientWidth,h=canvas.clientHeight;if(!w||!h)return;if(canvas.width!==w||canvas.height!==h){canvas.width=w;canvas.height=h;}
    ctx.clearRect(0,0,w,h);
    if(!current().nightFrames&&(!current().video||$('track-video').hidden)){
      ctx.strokeStyle='#263637';ctx.lineWidth=.5;for(let i=1;i<12;i++){ctx.beginPath();ctx.moveTo(i*w/12,40);ctx.lineTo(i*w/12,h-40);ctx.stroke();}
      ctx.fillStyle='#778889';ctx.font='10px monospace';ctx.textAlign='center';if(!current().src)ctx.fillText('AWAITING YOUR EARTH SIGNAL',w/2,h/2-30);
    }
    const baseline=h*.72;ctx.beginPath();ctx.strokeStyle=playing?'#78eafa':'#48727a';ctx.lineWidth=1.4;
    if(playing&&analyser){const waveform=new Uint8Array(analyser.fftSize);analyser.getByteTimeDomainData(waveform);for(let i=0;i<waveform.length;i++){const x=i/(waveform.length-1)*w,y=baseline+(waveform[i]-128)/128*h*.17;i?ctx.lineTo(x,y):ctx.moveTo(x,y);}}
    else{ctx.moveTo(0,baseline);ctx.lineTo(w,baseline);}ctx.stroke();
  }
  route();animate();
})();
