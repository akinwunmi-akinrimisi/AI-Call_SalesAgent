/**
 * AudioWorklet processor for PCM playback at 24kHz with ring buffer.
 *
 * Receives Int16 PCM audio from the main thread, converts to Float32,
 * stores in a ring buffer, and plays back through the audio output.
 *
 * Uses a pre-buffer threshold to accumulate enough audio before starting
 * playback, preventing stuttering from network jitter. Once playback
 * starts, it continues until the buffer is empty, then re-enters
 * buffering mode.
 *
 * Supports barge-in via the "clearBuffer" command, which flushes
 * the ring buffer by advancing readIndex to writeIndex.
 */
class PCMPlayerProcessor extends AudioWorkletProcessor {
  constructor() {
    super();

    // Ring buffer: ~3 minutes at 24kHz mono
    this.bufferSize = 24000 * 180; // 4,320,000 samples
    this.ringBuffer = new Float32Array(this.bufferSize);
    this.writeIndex = 0;
    this.readIndex = 0;

    // Pre-buffer: accumulate 200ms of audio (4800 samples at 24kHz)
    // before starting playback to absorb network jitter
    this.prebufferThreshold = 4800;
    this.isBuffering = true;

    this.port.onmessage = (event) => {
      // Barge-in: flush the playback buffer
      if (event.data && event.data.command === "clearBuffer") {
        this.readIndex = this.writeIndex;
        this.isBuffering = true;
        return;
      }

      // Otherwise treat event.data as ArrayBuffer of Int16 PCM
      const int16Data = new Int16Array(event.data);
      for (let i = 0; i < int16Data.length; i++) {
        this.ringBuffer[this.writeIndex] = int16Data[i] / 32768;
        this.writeIndex = (this.writeIndex + 1) % this.bufferSize;
      }
    };
  }

  /**
   * Number of samples available to read in the ring buffer.
   */
  availableSamples() {
    const avail = this.writeIndex - this.readIndex;
    return avail >= 0 ? avail : avail + this.bufferSize;
  }

  process(inputs, outputs) {
    const output = outputs[0];
    if (!output || !output[0]) return true;

    const channel = output[0];

    // If buffering, check if we've accumulated enough to start
    if (this.isBuffering) {
      if (this.availableSamples() >= this.prebufferThreshold) {
        this.isBuffering = false;
      } else {
        // Still buffering -- output silence
        for (let i = 0; i < channel.length; i++) {
          channel[i] = 0;
        }
        return true;
      }
    }

    for (let i = 0; i < channel.length; i++) {
      if (this.readIndex !== this.writeIndex) {
        channel[i] = this.ringBuffer[this.readIndex];
        this.readIndex = (this.readIndex + 1) % this.bufferSize;
      } else {
        // Buffer drained -- re-enter buffering mode and output silence
        channel[i] = 0;
        this.isBuffering = true;
      }
    }

    return true;
  }
}

registerProcessor("pcm-player-processor", PCMPlayerProcessor);
