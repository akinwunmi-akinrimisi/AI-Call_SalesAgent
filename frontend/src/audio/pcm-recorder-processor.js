/**
 * AudioWorklet processor for microphone capture at 16kHz.
 *
 * Captures mono Float32 audio frames from the microphone and posts
 * them to the main thread via port.postMessage. The main thread
 * converts to PCM16 and sends over WebSocket.
 */
class PCMRecorderProcessor extends AudioWorkletProcessor {
  process(inputs, outputs, parameters) {
    const input = inputs[0];
    if (input && input[0] && input[0].length > 0) {
      // Copy the Float32 data and send to main thread
      const samples = new Float32Array(input[0]);
      this.port.postMessage(samples);
    }
    return true;
  }
}

registerProcessor("pcm-recorder-processor", PCMRecorderProcessor);
