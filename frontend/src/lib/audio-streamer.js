/**
 * AudioStreamer — Google's reference implementation for Gemini Live API
 * audio playback, ported from:
 * https://github.com/google-gemini/multimodal-live-api-web-console
 *
 * Uses scheduled AudioBufferSourceNodes for gapless PCM playback.
 * NOT an AudioWorklet ring buffer — this is the proven pattern.
 */

export class AudioStreamer {
  constructor(audioContext) {
    this.context = audioContext;
    this.sampleRate = 24000;
    this.bufferSize = 7680; // 320ms at 24kHz
    this.audioQueue = [];
    this.isPlaying = false;
    this.isStreamComplete = false;
    this.checkInterval = null;
    this.scheduledTime = 0;
    this.initialBufferTime = 0.1; // 100ms initial delay
    this.gainNode = this.context.createGain();
    this.gainNode.connect(this.context.destination);
    this.onComplete = () => {};

    // Diagnostics
    this._chunksReceived = 0;
    this._buffersScheduled = 0;
  }

  /**
   * Convert PCM16 LE bytes to Float32 audio samples.
   */
  _processPCM16Chunk(chunk) {
    // chunk is an ArrayBuffer of Int16 PCM LE
    const dataView = new DataView(chunk);
    const numSamples = chunk.byteLength / 2;
    const float32Array = new Float32Array(numSamples);

    for (let i = 0; i < numSamples; i++) {
      const int16 = dataView.getInt16(i * 2, true); // true = little-endian
      float32Array[i] = int16 / 32768;
    }
    return float32Array;
  }

  /**
   * Add a PCM16 audio chunk to the playback queue.
   * @param {ArrayBuffer} chunk - Raw PCM16 LE audio data
   */
  addPCM16(chunk) {
    this._chunksReceived++;
    this.isStreamComplete = false;

    let processingBuffer = this._processPCM16Chunk(chunk);

    // Split into fixed-size buffers for consistent scheduling
    while (processingBuffer.length >= this.bufferSize) {
      const buffer = processingBuffer.slice(0, this.bufferSize);
      this.audioQueue.push(buffer);
      processingBuffer = processingBuffer.slice(this.bufferSize);
    }
    // Push remainder (smaller than bufferSize)
    if (processingBuffer.length > 0) {
      this.audioQueue.push(processingBuffer);
    }

    // Start playback if not already playing
    if (!this.isPlaying) {
      this.isPlaying = true;
      this.scheduledTime = this.context.currentTime + this.initialBufferTime;
      this.scheduleNextBuffer();
    }
  }

  /**
   * Create an AudioBuffer from Float32 data.
   */
  _createAudioBuffer(audioData) {
    const audioBuffer = this.context.createBuffer(
      1,
      audioData.length,
      this.sampleRate
    );
    audioBuffer.getChannelData(0).set(audioData);
    return audioBuffer;
  }

  /**
   * Schedule queued audio buffers for playback.
   * Schedules up to SCHEDULE_AHEAD_TIME (200ms) into the future.
   */
  scheduleNextBuffer() {
    const SCHEDULE_AHEAD_TIME = 0.2;

    while (
      this.audioQueue.length > 0 &&
      this.scheduledTime < this.context.currentTime + SCHEDULE_AHEAD_TIME
    ) {
      const audioData = this.audioQueue.shift();
      const audioBuffer = this._createAudioBuffer(audioData);
      const source = this.context.createBufferSource();
      source.buffer = audioBuffer;
      source.connect(this.gainNode);

      const startTime = Math.max(this.scheduledTime, this.context.currentTime);
      source.start(startTime);
      this.scheduledTime = startTime + audioBuffer.duration;
      this._buffersScheduled++;
    }

    if (this.audioQueue.length === 0) {
      if (this.isStreamComplete) {
        this.isPlaying = false;
        if (this.checkInterval) {
          clearInterval(this.checkInterval);
          this.checkInterval = null;
        }
      } else {
        // Poll for new data every 100ms when queue is empty
        if (!this.checkInterval) {
          this.checkInterval = window.setInterval(() => {
            if (this.audioQueue.length > 0) {
              this.scheduleNextBuffer();
            }
          }, 100);
        }
      }
    } else {
      // Schedule next check just before current audio ends
      const nextCheckTime =
        (this.scheduledTime - this.context.currentTime) * 1000;
      setTimeout(
        () => this.scheduleNextBuffer(),
        Math.max(0, nextCheckTime - 50)
      );
    }
  }

  /**
   * Stop all playback immediately (barge-in).
   * Ramps gain to 0 for click-free cutoff.
   */
  stop() {
    this.isPlaying = false;
    this.isStreamComplete = true;
    this.audioQueue = [];
    this.scheduledTime = this.context.currentTime;

    if (this.checkInterval) {
      clearInterval(this.checkInterval);
      this.checkInterval = null;
    }

    // Smooth fade-out to prevent click
    this.gainNode.gain.linearRampToValueAtTime(
      0,
      this.context.currentTime + 0.1
    );

    // Reconnect gain node after fade
    setTimeout(() => {
      this.gainNode.disconnect();
      this.gainNode = this.context.createGain();
      this.gainNode.connect(this.context.destination);
    }, 200);
  }

  /**
   * Resume after stop (for next response).
   */
  async resume() {
    if (this.context.state === "suspended") {
      await this.context.resume();
    }
    this.isStreamComplete = false;
    this.scheduledTime = this.context.currentTime + this.initialBufferTime;
    this.gainNode.gain.setValueAtTime(1, this.context.currentTime);
  }

  /**
   * Mark stream as complete.
   */
  complete() {
    this.isStreamComplete = true;
    this.onComplete();
  }

  /**
   * Get diagnostic info.
   */
  get diagnostics() {
    return {
      chunksReceived: this._chunksReceived,
      buffersScheduled: this._buffersScheduled,
      queueLength: this.audioQueue.length,
      isPlaying: this.isPlaying,
      contextState: this.context.state,
      contextSampleRate: this.context.sampleRate,
    };
  }
}
