export class Player {
  constructor(context) {
    this.context = context; this.nodes = new Set(); this.next = 0;
    this.analyser = context.createAnalyser?.();
    if (this.analyser) { this.analyser.fftSize = 256; this.analyser.connect(context.destination); this.wave = new Float32Array(256); }
  }
  level() {
    if (!this.analyser || !this.nodes.size) return 0;
    this.analyser.getFloatTimeDomainData(this.wave);
    return Math.sqrt(this.wave.reduce((sum, value) => sum + value * value, 0) / this.wave.length);
  }
  play(encoded) {
    const bytes = Uint8Array.from(atob(encoded), c => c.charCodeAt(0));
    if (bytes.length % 2) throw Error('Invalid audio frame.');
    const view = new DataView(bytes.buffer);
    const buffer = this.context.createBuffer(1, bytes.length / 2, 24000);
    const channel = buffer.getChannelData(0);
    for (let i = 0; i < channel.length; i++) channel[i] = view.getInt16(i * 2, true) / 32768;
    const start = Math.max(this.next, this.context.currentTime + .02);
    if (start - this.context.currentTime > 12) { this.clear(); throw Error('Playback queue exceeded 12 seconds. Reply cleared; please interrupt or reconnect.'); }
    const node = this.context.createBufferSource(); node.buffer = buffer; node.connect(this.analyser || this.context.destination);
    this.nodes.add(node); node.onended = () => { this.nodes.delete(node); node.disconnect(); };
    node.start(start); this.next = start + buffer.duration;
  }
  clear() {
    for (const node of this.nodes) { node.onended = null; try { node.stop(); } catch {} node.disconnect(); }
    this.nodes.clear(); this.next = this.context.currentTime;
  }
}

export class Voice {
  constructor(onFrame, onSpeech, threshold = () => .035) { this.onFrame = onFrame; this.onSpeech = onSpeech; this.threshold = threshold; this.generation = 0; this.enabled = false; this.muted = false; this.inputLevel = 0; }
  level() { return Math.min(1, Math.max(this.muted ? 0 : this.inputLevel, this.player?.level() || 0) * 4); }
  setMuted(muted) { this.muted = muted; this.stream?.getAudioTracks().forEach(track => track.enabled = !muted); }
  async start() {
    const generation = ++this.generation;
    this.context = new AudioContext({latencyHint: 'interactive'});
    await this.context.resume();
    if (generation !== this.generation) return;
    this.player = new Player(this.context);
    const stream = await navigator.mediaDevices.getUserMedia({audio: {channelCount: 1, echoCancellation: true, noiseSuppression: true, autoGainControl: true}, video: false});
    if (generation !== this.generation) { stream.getTracks().forEach(track => track.stop()); return; }
    this.stream = stream;
    this.muted = false;
    await this.context.audioWorklet.addModule('/static/capture-worklet.js');
    if (generation !== this.generation) return;
    this.source = this.context.createMediaStreamSource(stream);
    this.processor = new AudioWorkletNode(this.context, 'thread-capture');
    const sink = this.context.createGain(); sink.gain.value = 0;
    this.source.connect(this.processor); this.processor.connect(sink); sink.connect(this.context.destination);
    this.hot = 0; this.quiet = 0; this.inSpeech = false;
    this.processor.port.onmessage = ({data}) => {
      if (!this.enabled) return;
      const samples = new Int16Array(data);
      const rms = Math.sqrt(samples.reduce((sum, x) => sum + (x / 32768) ** 2, 0) / samples.length);
      this.inputLevel = rms;
      if (rms > this.threshold()) {
        this.quiet = 0;
        if (++this.hot >= 3 && !this.inSpeech) { this.inSpeech = true; this.player.clear(); this.onSpeech(); }
      } else { this.hot = 0; if (++this.quiet > 15) this.inSpeech = false; }
      this.onFrame(data);
    };
  }
  async stop() {
    this.generation++; this.enabled = false; this.inputLevel = 0;
    this.stream?.getTracks().forEach(track => track.stop()); this.stream = null;
    if (this.processor) { this.processor.port.onmessage = null; this.processor.disconnect(); }
    this.source?.disconnect(); this.player?.clear();
    if (this.context && this.context.state !== 'closed') await this.context.close();
  }
}
