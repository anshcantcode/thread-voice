import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import vm from 'node:vm';
import {Player, Voice} from '../src/thread_voice/web/audio.js';

const source = await readFile(new URL('../src/thread_voice/web/capture-worklet.js', import.meta.url), 'utf8');
for (const rate of [16000, 44100, 48000]) {
  const frames = []; let Processor;
  vm.runInNewContext(source, {AudioWorkletProcessor: class {constructor() {this.port = {postMessage: data => frames.push(data)};}}, sampleRate: rate, Int16Array, Math, registerProcessor: (_, type) => Processor = type});
  const capture = new Processor();
  for (let sent = 0; sent < rate; sent += 128) capture.process([[new Float32Array(Math.min(128, rate - sent)).fill(.25)]]);
  assert.equal(frames.length, 50, `${rate} Hz input must produce 50 continuous 20 ms frames`);
  assert.equal(frames[0].byteLength, 640);
  assert.ok(new Int16Array(frames[0]).every(value => value === 8192), 'Source-interval averaging preserves a constant signal');
}

let stopped = 0, disconnected = 0;
const context = {currentTime: 1, destination: {}, createBuffer: (_, count, rate) => ({getChannelData: () => new Float32Array(count), duration: count / rate}), createBufferSource: () => ({connect() {}, start() {}, stop() {stopped++;}, disconnect() {disconnected++;}})};
const player = new Player(context);
player.play('AAA='); player.play('AAA=');
assert.equal(player.nodes.size, 2);
player.clear();
assert.equal(stopped, 2, 'Interrupt stops every scheduled source, including queued audio');
assert.equal(disconnected, 2);
assert.equal(player.nodes.size, 0);
assert.equal(player.next, context.currentTime);
assert.throws(() => player.play('AA=='), /Invalid audio/);
player.next = 20;
assert.throws(() => player.play('AAA='), /queue exceeded/);
assert.equal(player.next, context.currentTime, 'Overflow clears the queue rather than retaining hidden audio');

let resolvePermission, trackStopped = false;
globalThis.AudioContext = class {constructor() {this.state = 'running'; this.currentTime = 0;} async resume() {} async close() {this.state = 'closed';}};
Object.defineProperty(globalThis, 'navigator', {configurable: true, value: {mediaDevices: {getUserMedia: () => new Promise(resolve => resolvePermission = resolve)}}});
const voice = new Voice(() => {}, () => {});
const permission = voice.start();
await new Promise(resolve => setImmediate(resolve));
await voice.stop();
resolvePermission({getTracks: () => [{stop() {trackStopped = true;}}]});
await permission;
assert.equal(trackStopped, true, 'Disconnect during permission request releases a late microphone stream');
assert.equal(voice.stream, null);
console.log('Audio checks passed: 16/44.1/48 kHz framing, playback cancellation, queue bounds, microphone permission race.');
