/**
 * Apex Chart Widget — canvas line/bar charts + crosshair (no external libs)
 * Build: hal-10340
 */
(function () {
  "use strict";

  class ApexChartWidget {
    constructor(canvas, data, type) {
      this.canvas = canvas;
      this.ctx = canvas.getContext("2d");
      this.data = data || {};
      this.type = type === "bar" ? "bar" : "line";
      this._dpr = window.devicePixelRatio || 1;
      this._hoverIdx = -1;
      this._onResize = () => {
        this.resize();
        this.draw();
      };
      this._onMove = (ev) => this.onPointer(ev);
      this._onLeave = () => {
        this._hoverIdx = -1;
        this.draw();
      };
      window.addEventListener("resize", this._onResize);
      canvas.addEventListener("mousemove", this._onMove);
      canvas.addEventListener("mouseleave", this._onLeave);
      this.resize();
      this.draw();
    }

    destroy() {
      window.removeEventListener("resize", this._onResize);
      this.canvas.removeEventListener("mousemove", this._onMove);
      this.canvas.removeEventListener("mouseleave", this._onLeave);
    }

    resize() {
      const parent = this.canvas.parentElement;
      if (!parent) return;
      const rect = parent.getBoundingClientRect();
      const cssW = Math.max(40, rect.width || 280);
      const cssH = Math.max(40, rect.height || 120);
      this._cssW = cssW;
      this._cssH = cssH;
      this._dpr = window.devicePixelRatio || 1;
      this.canvas.width = Math.floor(cssW * this._dpr);
      this.canvas.height = Math.floor(cssH * this._dpr);
      this.canvas.style.width = cssW + "px";
      this.canvas.style.height = cssH + "px";
      this.ctx.setTransform(this._dpr, 0, 0, this._dpr, 0, 0);
    }

    values() {
      if (Array.isArray(this.data.values)) return this.data.values.map(Number);
      if (Array.isArray(this.data)) return this.data.map(Number);
      return [];
    }

    labels() {
      return Array.isArray(this.data.labels) ? this.data.labels.map(String) : [];
    }

    onPointer(ev) {
      const rect = this.canvas.getBoundingClientRect();
      const x = ev.clientX - rect.left;
      const values = this.values().filter((v) => Number.isFinite(v));
      if (!values.length) return;
      const w = this._cssW || 280;
      let idx = 0;
      if (this.type === "bar") {
        const gap = 4;
        const barW = Math.max(4, (w - gap * (values.length + 1)) / values.length);
        idx = Math.max(0, Math.min(values.length - 1, Math.floor((x - gap) / (barW + gap))));
      } else {
        idx =
          values.length === 1
            ? 0
            : Math.max(0, Math.min(values.length - 1, Math.round((x / w) * (values.length - 1))));
      }
      if (idx !== this._hoverIdx) {
        this._hoverIdx = idx;
        this.draw();
      }
    }

    drawCrosshair(ctx, w, h, values) {
      if (this._hoverIdx < 0 || this._hoverIdx >= values.length) return;
      const i = this._hoverIdx;
      let x;
      if (this.type === "bar") {
        const gap = 4;
        const barW = Math.max(4, (w - gap * (values.length + 1)) / values.length);
        x = gap + i * (barW + gap) + barW / 2;
      } else {
        x = values.length === 1 ? w / 2 : (i / (values.length - 1)) * w;
      }
      ctx.strokeStyle = "rgba(0, 240, 255, 0.55)";
      ctx.lineWidth = 1;
      ctx.setLineDash([3, 3]);
      ctx.beginPath();
      ctx.moveTo(x, 0);
      ctx.lineTo(x, h);
      ctx.stroke();
      ctx.beginPath();
      const max = Math.max(...values, 1);
      const min = this.type === "line" ? Math.min(...values, 0) : 0;
      const range = max - min || 1;
      const pad = 6;
      const y =
        this.type === "bar"
          ? h - Math.max(2, (values[i] / max) * (h - 10))
          : h - ((values[i] - min) / range) * (h - pad * 2) - pad;
      ctx.moveTo(0, y);
      ctx.lineTo(w, y);
      ctx.stroke();
      ctx.setLineDash([]);
      const labs = this.labels();
      const tip = (labs[i] ? labs[i] + ": " : "") + String(values[i]);
      ctx.fillStyle = "rgba(0, 0, 0, 0.72)";
      ctx.fillRect(Math.min(x + 6, w - 90), 4, 86, 16);
      ctx.fillStyle = "#00f0ff";
      ctx.font = "10px JetBrains Mono, monospace";
      ctx.fillText(tip.slice(0, 18), Math.min(x + 10, w - 86), 15);
    }

    draw() {
      const ctx = this.ctx;
      const w = this._cssW || 280;
      const h = this._cssH || 120;
      const values = this.values().filter((v) => Number.isFinite(v));
      ctx.clearRect(0, 0, w, h);
      if (!values.length) return;

      if (this.type === "bar") {
        this.drawBars(ctx, w, h, values);
      } else {
        this.drawLine(ctx, w, h, values);
      }
      this.drawCrosshair(ctx, w, h, values);
    }

    drawLine(ctx, w, h, values) {
      const max = Math.max(...values, 1);
      const min = Math.min(...values, 0);
      const range = max - min || 1;
      const pad = 6;

      ctx.strokeStyle = "#00f0ff";
      ctx.lineWidth = 2;
      ctx.beginPath();
      values.forEach((v, i) => {
        const x = values.length === 1 ? w / 2 : (i / (values.length - 1)) * w;
        const y = h - ((v - min) / range) * (h - pad * 2) - pad;
        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      });
      ctx.stroke();

      ctx.lineTo(w, h);
      ctx.lineTo(0, h);
      ctx.closePath();
      const grad = ctx.createLinearGradient(0, 0, 0, h);
      grad.addColorStop(0, "rgba(0, 240, 255, 0.22)");
      grad.addColorStop(1, "rgba(0, 240, 255, 0)");
      ctx.fillStyle = grad;
      ctx.fill();
    }

    drawBars(ctx, w, h, values) {
      const max = Math.max(...values, 1);
      const gap = 4;
      const barW = Math.max(4, (w - gap * (values.length + 1)) / values.length);
      values.forEach((v, i) => {
        const bh = Math.max(2, (v / max) * (h - 10));
        const x = gap + i * (barW + gap);
        const y = h - bh;
        ctx.fillStyle = i % 2 === 0 ? "rgba(0, 240, 255, 0.55)" : "rgba(255, 184, 0, 0.55)";
        ctx.fillRect(x, y, barW, bh);
      });
    }
  }

  window.ApexChartWidget = ApexChartWidget;
})();
