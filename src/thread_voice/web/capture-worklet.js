/* Average each output sample's source interval. No browser-sized recording buffer. */
class Capture extends AudioWorkletProcessor {
  constructor() { super(); this.ratio = sampleRate / 16000; this.weight = 0; this.sum = 0; this.frame = new Int16Array(320); this.index = 0; }
  process(inputs) {
    const input = inputs[0]?.[0];
    if (!input) return true;
    for (const value of input) {
      let remaining = 1;
      while (remaining > 1e-9) {
        const amount = Math.min(remaining, this.ratio - this.weight);
        this.sum += value * amount; this.weight += amount; remaining -= amount;
        if (this.weight >= this.ratio - 1e-9) {
          this.frame[this.index++] = Math.round(Math.max(-1, Math.min(1, this.sum / this.ratio)) * 32767);
          this.sum = 0; this.weight = 0;
          if (this.index === this.frame.length) {
            this.port.postMessage(this.frame.buffer, [this.frame.buffer]);
            this.frame = new Int16Array(320); this.index = 0;
          }
        }
      }
    }
    return true;
  }
}
registerProcessor('thread-capture', Capture);
