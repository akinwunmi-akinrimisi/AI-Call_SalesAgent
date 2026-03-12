/**
 * AudioWorklet processor for PCM playback at 24kHz with ring buffer.
 *
 * Receives Int16 PCM audio from the main thread, converts to Float32,
 * stores in a ring buffer, and plays back through the audio output.
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

    this.port.onmessage = (event) => {
      // Barge-in: flush the playback buffer
      if (event.data && event.data.command === "clearBuffer") {
        this.readIndex = this.writeIndex;
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

  process(inputs, outputs) {
    const output = outputs[0];
    if (!output || !output[0]) return true;

    const channel = output[0];
    for (let i = 0; i < channel.length; i++) {
      if (this.readIndex !== this.writeIndex) {
        channel[i] = this.ringBuffer[this.readIndex];
        this.readIndex = (this.readIndex + 1) % this.bufferSize;
      } else {
        // No data available -- output silence
        channel[i] = 0;
      }
    }

    return true;
  }
}

registerProcessor("pcm-player-processor", PCMPlayerProcessor);
