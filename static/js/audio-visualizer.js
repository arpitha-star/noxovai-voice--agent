/**
 * NexovAI Voice AI - Canvas Waveform Visualizer
 * Renders dynamic voice wave activity in the phone screen.
 */

class AudioWaveformVisualizer {
  constructor(canvasId) {
    this.canvas = document.getElementById(canvasId);
    if (!this.canvas) return;
    this.ctx = this.canvas.getContext('2d');
    this.animationId = null;
    this.mode = 'idle'; // 'idle', 'speaking', 'listening'
    this.bars = 32;
    this.heights = new Array(this.bars).fill(4);
    this.targetHeights = new Array(this.bars).fill(4);

    this.resize();
    window.addEventListener('resize', () => this.resize());
  }

  resize() {
    if (!this.canvas) return;
    const rect = this.canvas.getBoundingClientRect();
    this.canvas.width = rect.width * window.devicePixelRatio || 360;
    this.canvas.height = rect.height * window.devicePixelRatio || 52;
  }

  setMode(mode) {
    this.mode = mode;
  }

  start() {
    if (this.animationId) return;
    const animate = () => {
      this.draw();
      this.animationId = requestAnimationFrame(animate);
    };
    animate();
  }

  stop() {
    if (this.animationId) {
      cancelAnimationFrame(this.animationId);
      this.animationId = null;
    }
    if (this.ctx && this.canvas) {
      this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
    }
  }

  draw() {
    if (!this.ctx || !this.canvas) return;
    const w = this.canvas.width;
    const h = this.canvas.height;

    this.ctx.clearRect(0, 0, w, h);

    const barWidth = (w / this.bars) - 3;
    const centerY = h / 2;

    for (let i = 0; i < this.bars; i++) {
      if (this.mode === 'speaking') {
        // High dynamic frequency simulation for agent speech
        const factor = Math.sin(Date.now() * 0.008 + i * 0.3) * 0.5 + 0.5;
        this.targetHeights[i] = 6 + factor * (h * 0.75);
      } else if (this.mode === 'listening') {
        // Subtle rhythmic wave for listening mode
        const factor = Math.sin(Date.now() * 0.004 + i * 0.2) * 0.5 + 0.5;
        this.targetHeights[i] = 4 + factor * (h * 0.45);
      } else {
        // Flat resting line
        this.targetHeights[i] = 3;
      }

      // Smooth interpolation
      this.heights[i] += (this.targetHeights[i] - this.heights[i]) * 0.2;

      const barH = Math.max(3, this.heights[i]);
      const x = i * (barWidth + 3);
      const y = centerY - barH / 2;

      // Color gradient based on state
      const gradient = this.ctx.createLinearGradient(0, y, 0, y + barH);
      if (this.mode === 'speaking') {
        gradient.addColorStop(0, '#38bdf8');
        gradient.addColorStop(1, '#0284c7');
      } else if (this.mode === 'listening') {
        gradient.addColorStop(0, '#34d399');
        gradient.addColorStop(1, '#059669');
      } else {
        gradient.addColorStop(0, '#475569');
        gradient.addColorStop(1, '#334155');
      }

      this.ctx.fillStyle = gradient;
      this.ctx.beginPath();
      this.ctx.roundRect(x, y, barWidth, barH, 2);
      this.ctx.fill();
    }
  }
}

window.AudioWaveformVisualizer = AudioWaveformVisualizer;
