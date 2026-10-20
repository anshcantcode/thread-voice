import {Voice} from './audio.js';

const $ = id => document.getElementById(id);
const element = (tag, text, className) => { const node = document.createElement(tag); if (text !== undefined) node.textContent = text; if (className) node.className = className; return node; };
let socket, config = {}, live = false, connecting = false, activeCall = null, noticeTimer;
const voice = new Voice(data => {
  if (socket?.readyState === WebSocket.OPEN && socket.bufferedAmount < 64000) socket.send(data);
}, () => send({type: 'interrupt'}));

function notice(text) { $('notice').textContent = text; $('notice').hidden = false; clearTimeout(noticeTimer); noticeTimer = setTimeout(() => $('notice').hidden = true, 8000); }
function send(command) {
  if (socket?.readyState !== WebSocket.OPEN) { notice('The local runtime is disconnected. Reconnect to continue.'); return; }
  socket.send(JSON.stringify(command));
}
function activity(title, description, busy = false) {
  $('conversation-title').textContent = title; $('conversation-copy').textContent = description;
  $('activity').textContent = busy ? 'WORK IN PROGRESS' : live ? 'LIVE CONNECTION' : 'LOCAL WORKSPACE';
  $('signal').classList.toggle('active', busy);
}
function controls(ready) {
  for (const id of ['demo', 'interrupt', 'send', 'new-note', 'notebook', 'export']) $(id).disabled = !ready;
  $('demo').disabled = !ready || live || connecting;
  $('live').disabled = !ready || !config.live_configured || live || connecting;
}
function resetVoice() {
  live = false; connecting = false; void voice.stop();
  $('disconnect').hidden = true; $('mode').textContent = 'LOCAL LAB';
  $('message').placeholder = 'Search notes: cancellation, revisions, privacy…';
  $('message').setAttribute('aria-label', 'Search local engineering notes');
  $('live').textContent = 'Connect live voice'; controls(socket?.readyState === WebSocket.OPEN);
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
  const card = element('article', undefined, 'draft-card');
  card.append(element('span', 'DRAFT / NOT SAVED', 'tag'), element('h3', proposal.title), element('p', proposal.content));
  const save = element('button', 'Save note', 'primary'); save.addEventListener('click', () => {
    save.disabled = true; send({type: 'confirm', proposal_id: proposal.id, revision: proposal.revision});
  });
  card.append(save); $('draft').replaceChildren(card); $('draft').hidden = false;
}
function results(items) {
  const nodes = items.map(item => {
    const card = element('article', undefined, 'result-item');
    card.append(element('span', 'BUNDLED REFERENCE', 'tag'), element('h3', item.title), element('p', item.text));
    return card;
  });
  $('result-list').replaceChildren(...(nodes.length ? nodes : [element('p', 'No matching engineering notes. Try “revisions” or “privacy”.', 'fine')]));
}
function handle(event) {
  if (event.type === 'voice.audio') {
    if (live) { try { voice.player?.play(event.data); } catch (error) { notice(error.message); } }
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
      activeCall = event.call_id; activity('Following your thought.', event.query, true);
      $('result-list').replaceChildren(element('p', 'Searching bundled engineering notes…', 'fine')); break;
    case 'search.completed':
      activeCall = null; activity('A fresh direction.', 'Current results are ready in your workspace.'); results(event.results); break;
    case 'search.cancelled': case 'search.failed':
      if (event.call_id === activeCall) { activeCall = null; activity('Work paused.', 'The search was cancelled. Start a fresh request whenever you like.'); }
      break;
    case 'playback.clear':
      voice.player?.clear(); activity('You have the floor.', 'Your interruption retired pending work and any unsaved draft.'); controls(true); $('mode').textContent = live ? 'LIVE VOICE' : 'LOCAL LAB'; break;
    case 'draft.prepared': draft(event.proposal); activity('Ready for your review.', 'A draft is prepared. Save it only if it says what you intend.'); break;
    case 'draft.expired': $('draft').hidden = true; $('draft').replaceChildren(); break;
    case 'note.receipt': {
      $('draft').hidden = true;
      if (!event.duplicate) {
        const receipt = element('div', undefined, 'receipt');
        receipt.append(element('strong', `✓ Saved locally · ${event.receipt.title}`), element('small', `Receipt ${event.receipt.id.slice(0, 12)} · ${event.receipt.created_at} UTC`));
        $('receipts').prepend(receipt);
      }
      activity('Something worth keeping.', 'The note has a durable local receipt. Interrupting cannot erase a committed save.'); break;
    }
    case 'notebook.loaded': {
      const cards = event.notes.map(note => {
        const card = element('article', undefined, 'result-item');
        card.append(element('span', `SAVED NOTE / ${note.created_at} UTC`, 'tag'), element('h3', note.title), element('p', note.content));
        return card;
      });
      $('result-list').replaceChildren(...(cards.length ? cards : [element('p', 'Your notebook is empty. Prepare and confirm a draft to save your first note.', 'fine')]));
      break;
    }
    case 'voice.connected':
      live = true; connecting = false; voice.enabled = true;
      $('mode').textContent = 'LIVE VOICE'; $('message').placeholder = 'Say it aloud, or type a message…';
      $('message').setAttribute('aria-label', 'Message the live voice model');
      $('live').textContent = 'Voice connected'; controls(true); activity('Go on. I’m listening.', 'Speak naturally. You can interrupt a reply at any time.', true); break;
    case 'voice.disconnected': resetVoice(); break;
    case 'voice.error': resetVoice(); notice(event.message); break;
    case 'voice.notice': case 'confirmation.rejected': case 'command.rejected': notice(event.message); break;
    case 'note.failed': notice(event.message); $('draft').querySelector('button')?.removeAttribute('disabled'); break;
    case 'transcript': {
      const line = element('p'); line.append(element('b', event.role.toUpperCase()), document.createTextNode(event.text)); $('captions').append(line);
      while ($('captions').children.length > 30) $('captions').firstChild.remove();
      $('captions').scrollTop = $('captions').scrollHeight; break;
    }
  }
}
async function connect() {
  controls(false);
  try {
    const response = await fetch('/api/config'); if (!response.ok) throw Error('Configuration is unavailable.'); config = await response.json();
    $('voice-info').textContent = config.live_configured ? 'Live mode sends your microphone and messages to Google Gemini. Provider charges may apply. Headphones recommended.' : 'Live voice is optional. Set a server-side Gemini key to enable it.';
    const current = socket = new WebSocket(`${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}/ws`);
    current.onopen = () => { if (socket !== current) return; $('connection').textContent = 'Local runtime connected'; $('connection-dot').classList.add('ready'); $('reconnect').hidden = true; };
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
$('close-note').onclick = () => $('note-dialog').close();
$('note-form').onsubmit = event => { event.preventDefault(); send({type: 'draft', title: $('note-title').value.trim(), content: $('note-content').value.trim()}); $('note-dialog').close(); };
$('live').onclick = async () => {
  if (connecting || live) return;
  connecting = true; controls(true); $('disconnect').hidden = false;
  try { await voice.start(); if (!connecting) return; send({type: 'voice.start'}); activity('Opening the conversation.', 'Connecting to your configured live voice model.', true); }
  catch (error) { resetVoice(); notice(`Microphone could not start: ${error.message}`); }
};
$('disconnect').onclick = () => { resetVoice(); send({type: 'voice.stop'}); activity('A little quiet.', 'Voice is disconnected. Your local workspace is still here.'); };
window.addEventListener('pagehide', () => { void voice.stop(); socket?.close(); });
void connect();
