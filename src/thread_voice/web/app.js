import {Voice} from './audio.js';
import {createOrb} from './orb.js';

const $ = id => document.getElementById(id);
const element = (tag, text, className) => { const node = document.createElement(tag); if (text !== undefined) node.textContent = text; if (className) node.className = className; return node; };
let socket, config = {}, live = false, connecting = false, activeCall = null, noticeTimer;
const orb = createOrb($('thread-canvas'), {theme: 'dark', image: '/static/images/thread-sphere.png', scale: .94});
const voice = new Voice(data => {
  if (socket?.readyState === WebSocket.OPEN && socket.bufferedAmount < 64000) socket.send(data);
}, () => send({type: 'interrupt'}), () => Number($('vad-threshold').value));

function feedOrb() { requestAnimationFrame(feedOrb); if (!document.hidden) orb.setLevel(voice.level()); }
requestAnimationFrame(feedOrb);
function micLabel(label, icon = 'i-mic') {
  $('live').querySelector('span').textContent = label;
  $('live').setAttribute('aria-label', label);
  $('mic-icon').querySelector('use').setAttribute('href', '#' + icon);
}
function workspace(label = 'YOUR RESULTS') {
  $('empty-context').hidden = true; $('work-section').hidden = false; $('mode').textContent = label;
}

function notice(text) { $('notice').textContent = text; $('toast').hidden = false; clearTimeout(noticeTimer); noticeTimer = setTimeout(() => $('toast').hidden = true, 8000); }
function send(command) {
  if (socket?.readyState !== WebSocket.OPEN) { notice('The local runtime is disconnected. Reconnect to continue.'); return; }
  socket.send(JSON.stringify(command));
}
function activity(title, description, busy = false) {
  $('conversation-title').textContent = title; $('conversation-copy').textContent = description;
  $('activity').textContent = busy ? 'WORK IN PROGRESS' : live ? 'LIVE CONNECTION' : 'LOCAL WORKSPACE';
  $('signal').classList.toggle('active', busy);
  orb.setPhase(busy ? 'working' : live ? 'listening' : 'idle');
}
function controls(ready) {
  for (const id of ['demo', 'interrupt', 'send', 'new-note', 'notebook', 'export']) $(id).disabled = !ready;
  $('demo').disabled = !ready || live || connecting;
  $('live').disabled = !ready || connecting;
}
function resetVoice() {
  live = false; connecting = false; void voice.stop();
  $('disconnect').hidden = true; $('mode').textContent = 'LOCAL LAB';
  $('message').placeholder = 'Search your reference notes…';
  $('message').setAttribute('aria-label', 'Search local engineering notes');
  micLabel('Start talking'); $('live').classList.remove('muted'); $('control-dock').classList.remove('connected');
  document.body.dataset.connected = 'false'; document.body.dataset.voiceState = 'idle';
  $('live-health').textContent = 'Not connected'; $('call-note').textContent = 'Your microphone turns on when you start.';
  orb.setPhase('idle'); controls(socket?.readyState === WebSocket.OPEN);
}
function describe(event) {
  if (event.query) return event.query;
  if (event.message) return event.message;
  if (event.reason) return event.reason;
  if (event.type === 'draft.prepared') return `Draft ready: ${event.proposal.title}. Nothing saved yet.`;
  if (event.type === 'note.receipt') return `${event.duplicate ? 'Existing receipt' : 'Saved locally'}: ${event.receipt.title}`;
  if (event.type === 'transcript') return `${event.role}: ${event.text}`;
  if (event.type === 'voice.connected') return `Connected to ${event.model}`;
  return '';
}
function trace(event) {
  if (!event.seq) return;
  const row = element('tr');
  row.append(element('td', `${(event.at_ms / 1000).toFixed(2)}s`), element('td', event.type), element('td', describe(event)), element('td', String(event.revision)));
  $('events').prepend(row);
  while ($('events').children.length > 100) $('events').lastChild.remove();
  $('revision').textContent = `REV ${event.revision}`;
}
function draft(proposal) {
  workspace('A NOTE TO KEEP');
  const card = element('article', undefined, 'draft-card');
  card.append(element('span', 'DRAFT / NOT SAVED', 'tag'), element('h3', proposal.title), element('p', proposal.content));
  const save = element('button', 'Save note', 'primary-button'); save.addEventListener('click', () => {
    save.disabled = true; send({type: 'confirm', proposal_id: proposal.id, revision: proposal.revision});
  });
  card.append(save); $('draft').replaceChildren(card); $('draft').hidden = false;
}
function results(items) {
  workspace();
  const nodes = items.map(item => {
    const card = element('article', undefined, 'result-item');
    card.append(element('span', 'BUNDLED REFERENCE', 'tag'), element('h3', item.title), element('p', item.text));
    return card;
  });
  $('result-list').replaceChildren(...(nodes.length ? nodes : [element('p', 'No matching notes. Try “revisions” or “privacy”.', 'empty-copy')]));
}
function handle(event) {
  if (event.type === 'voice.audio') {
    if (live) { try { voice.player?.play(event.data); orb.setPhase('speaking'); } catch (error) { notice(error.message); } }
    return;
  }
  if (event.type === 'session.export') {
    const url = URL.createObjectURL(new Blob([JSON.stringify(event, null, 2)], {type: 'application/json'}));
    const link = element('a'); link.href = url; link.download = 'thread-voice-trace.json'; link.click(); setTimeout(() => URL.revokeObjectURL(url), 1000); return;
  }
  trace(event);
  switch (event.type) {
    case 'session.ready': controls(true); break;
    case 'demo.started': $('demo').disabled = true; $('mode').textContent = 'SCRIPTED INPUT'; break;
    case 'demo.finished': controls(true); $('mode').textContent = 'LOCAL LAB'; break;
    case 'search.started':
      workspace('FOLLOWING YOUR THOUGHT');
      activeCall = event.call_id; activity('Following your thought.', event.query, true);
      $('result-list').replaceChildren(element('p', 'A moment while I look through the reference notes…', 'empty-copy')); break;
    case 'search.completed':
      activeCall = null; activity('A fresh direction.', 'Current results are ready in your workspace.'); results(event.results); break;
    case 'search.cancelled': case 'search.failed':
      if (event.call_id === activeCall) { activeCall = null; activity('Work paused.', 'The search was cancelled. Start a fresh request whenever you like.'); }
      break;
    case 'playback.clear':
      voice.player?.clear(); activity('Take your time.', 'I’m listening. You can change your mind.'); orb.pulse('interrupt'); controls(true); break;
    case 'draft.prepared': draft(event.proposal); activity('Something to keep.', 'Take a look. Save it when it feels right.'); orb.setPhase('held'); break;
    case 'draft.expired': $('draft').hidden = true; $('draft').replaceChildren(); break;
    case 'note.receipt': {
      $('draft').hidden = true;
      if (!event.duplicate) {
        const receipt = element('div', undefined, 'receipt');
        receipt.append(element('strong', `✓ Saved locally · ${event.receipt.title}`), element('small', `Receipt ${event.receipt.id.slice(0, 12)} · ${event.receipt.created_at} UTC`));
        $('receipts').prepend(receipt);
      }
      activity('Right where you left it.', 'Your note is saved in your notebook.'); orb.pulse('done'); break;
    }
    case 'notebook.loaded': {
      workspace('YOUR NOTEBOOK');
      const cards = event.notes.map(note => {
        const card = element('article', undefined, 'result-item');
        card.append(element('span', `SAVED NOTE / ${note.created_at} UTC`, 'tag'), element('h3', note.title), element('p', note.content));
        return card;
      });
      $('result-list').replaceChildren(...(cards.length ? cards : [element('p', 'Your notebook is empty. Start with a note worth keeping.', 'empty-copy')]));
      break;
    }
    case 'voice.connected':
      live = true; connecting = false; voice.enabled = true;
      $('mode').textContent = 'LIVE VOICE'; $('message').placeholder = 'Say it aloud, or type a message…';
      $('message').setAttribute('aria-label', 'Message the live voice model');
      micLabel('Mute microphone'); $('control-dock').classList.add('connected'); document.body.dataset.connected = 'true'; document.body.dataset.voiceState = 'listening';
      $('live-health').textContent = 'Connected'; $('call-note').textContent = 'Live conversation · your microphone stays open';
      controls(true); activity('Go on.', 'You can jump in whenever you like.'); break;
    case 'voice.disconnected': resetVoice(); break;
    case 'voice.error': resetVoice(); notice(event.message); break;
    case 'voice.notice': case 'confirmation.rejected': case 'command.rejected': notice(event.message); break;
    case 'voice.turn_complete': orb.setPhase(live ? 'listening' : 'idle'); break;
    case 'note.failed': notice(event.message); $('draft').querySelector('button')?.removeAttribute('disabled'); break;
    case 'transcript': {
      const line = element('article', undefined, 'transcript-message ' + event.role);
      line.append(element('div', event.role === 'user' ? 'YOU' : 'THREAD', 'message-meta'), element('p', event.text, 'message-body')); $('captions').append(line);
      while ($('captions').children.length > 30) $('captions').firstChild.remove();
      $('caption-speaker').textContent = event.role === 'user' ? 'YOU' : 'THREAD'; $('caption-text').textContent = event.text;
      $('transcript-count').textContent = String($('captions').children.length);
      $('captions').scrollTop = $('captions').scrollHeight; break;
    }
  }
}
async function connect() {
  controls(false);
  try {
    const response = await fetch('/api/config'); if (!response.ok) throw Error('Configuration is unavailable.'); config = await response.json();
    $('version').textContent = 'v' + config.version; $('live-model').textContent = 'Gemini Live · ' + config.live_model; $('setup-info').hidden = config.live_configured;
    $('voice-info').textContent = config.live_configured ? 'Live mode sends your microphone and messages to Google Gemini. Provider charges may apply. Headphones recommended.' : 'Live voice is optional. Set a server-side Gemini key to enable it.';
    const current = socket = new WebSocket(`${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}/ws`);
    current.onopen = () => { if (socket !== current) return; $('connection').textContent = 'Ready when you are'; $('connection-dot').classList.add('ready'); $('reconnect').hidden = true; };
    current.onmessage = ({data}) => { if (socket === current) handle(JSON.parse(data)); };
    current.onclose = () => { if (socket !== current) return; resetVoice(); controls(false); $('draft').hidden = true; $('connection').textContent = 'Disconnected · new session on reconnect'; $('connection-dot').classList.remove('ready'); $('reconnect').hidden = false; activity('A moment of quiet.', 'Reconnect to start a fresh session. Saved notes remain on this computer.'); };
    current.onerror = () => notice('Could not connect to the local runtime. Check that the server is running.');
  } catch (error) { notice(error.message); $('connection').textContent = 'Runtime unavailable'; $('reconnect').hidden = false; }
}
$('reconnect').onclick = () => { socket?.close(); $('events').replaceChildren(); $('captions').replaceChildren(); void connect(); };
$('demo').onclick = () => send({type: 'demo'});
$('interrupt').onclick = () => { voice.player?.clear(); send({type: 'interrupt'}); };
$('export').onclick = () => send({type: 'export'});
$('notebook').onclick = () => send({type: 'notebook'});
$('composer').onsubmit = event => { event.preventDefault(); const text = $('message').value.trim(); if (!text) return; send(live ? {type: 'voice.text', text} : {type: 'search', query: text}); $('message').value = ''; };
$('new-note').onclick = () => $('note-dialog').showModal();
$('back-home').onclick = () => { $('empty-context').hidden = false; $('work-section').hidden = true; };
$('keyboard').onclick = () => { $('composer').hidden = !$('composer').hidden; $('keyboard').setAttribute('aria-expanded', String(!$('composer').hidden)); if (!$('composer').hidden) $('message').focus(); };
$('toast-close').onclick = () => $('toast').hidden = true;
$('transcript-inspect').onclick = () => { $('transcript-dialog').close(); $('inspector').showModal(); };
for (const button of document.querySelectorAll('[data-open]')) button.onclick = () => $(button.dataset.open).showModal();
for (const button of document.querySelectorAll('[data-close]')) button.onclick = () => $(button.dataset.close).close();
for (const button of document.querySelectorAll('[data-query]')) button.onclick = () => send({type: 'search', query: button.dataset.query});
$('close-note').onclick = () => $('note-dialog').close();
$('note-form').onsubmit = event => { event.preventDefault(); send({type: 'draft', title: $('note-title').value.trim(), content: $('note-content').value.trim()}); $('note-dialog').close(); };
$('live').onclick = async () => {
  if (connecting) return;
  if (live) {
    voice.setMuted(!voice.muted); $('live').classList.toggle('muted', voice.muted);
    micLabel(voice.muted ? 'Unmute microphone' : 'Mute microphone', voice.muted ? 'i-mute' : 'i-mic');
    $('call-note').textContent = voice.muted ? 'Microphone muted · you can still type' : 'Live conversation · your microphone stays open';
    orb.setPhase(voice.muted ? 'muted' : 'listening'); return;
  }
  if (!config.live_configured) { $('settings-dialog').showModal(); return; }
  connecting = true; controls(true); $('disconnect').hidden = false;
  orb.setPhase('connecting');
  try { await voice.start(); if (!connecting) return; send({type: 'voice.start'}); activity('One moment.', 'Opening your conversation.', true); }
  catch (error) { resetVoice(); notice(`Microphone could not start: ${error.message}`); }
};
$('disconnect').onclick = () => { resetVoice(); send({type: 'voice.stop'}); activity('A little quiet.', 'Voice is disconnected. Your local workspace is still here.'); };
window.addEventListener('pagehide', () => { orb.destroy(); void voice.stop(); socket?.close(); });
void connect();
