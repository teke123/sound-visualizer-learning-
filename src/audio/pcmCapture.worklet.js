class PcmCapture extends AudioWorkletProcessor {
  constructor() {
    super()
    this.enabled = false
    this.port.onmessage = (event) => { this.enabled = event.data.enabled }
  }

  process(inputs) {
    const input = inputs[0]?.[0]
    if (this.enabled && input) {
      const samples = new Float32Array(input)
      this.port.postMessage({ samples, startSample: currentFrame }, [samples.buffer])
    }
    return true
  }
}
registerProcessor('pcm-capture', PcmCapture)

