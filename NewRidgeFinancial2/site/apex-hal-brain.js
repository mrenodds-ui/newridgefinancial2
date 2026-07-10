/**
 * HAL Neural Core Visualization — mountable canvas brain
 * Build: hal-10260
 */
(function () {
  "use strict";

  const COLORS = {
    cyan: "0, 240, 255",
    amber: "255, 184, 0",
    magenta: "255, 0, 102",
  };

  let instance = null;

  function createBrain(root) {
    const canvas = root.querySelector("#hal-brain-canvas");
    if (!canvas) return null;
    const ctx = canvas.getContext("2d");
    const stateEl = root.querySelector("#hal-brain-state");
    const metricSynapses = root.querySelector("#hal-metric-synapses");
    const metricActivity = root.querySelector("#hal-metric-activity");
    const metricLatency = root.querySelector("#hal-metric-latency");

    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const CONFIG = {
      nodeCount: reduced ? 18 : Math.min(48, Math.max(28, Math.floor(window.innerWidth / 40))),
      connectionDistance: 110,
      idleSpeed: 0.22,
      thinkSpeed: 2.2,
    };

    let width = 0;
    let height = 0;
    let nodes = [];
    let connections = [];
    let animationId = null;
    let currentState = "idle";
    let replyTimer = null;
    let thinkStarted = 0;
    let destroyed = false;

    class Node {
      constructor() {
        this.reset();
      }
      reset() {
        this.x = Math.random() * Math.max(width, 1);
        this.y = Math.random() * Math.max(height, 1);
        this.vx = (Math.random() - 0.5) * CONFIG.idleSpeed;
        this.vy = (Math.random() - 0.5) * CONFIG.idleSpeed;
        this.radius = 1.6 + Math.random() * 2.2;
        this.activation = 0;
      }
      update(state) {
        const speed = state === "thinking" || state === "reply" ? CONFIG.thinkSpeed : CONFIG.idleSpeed;
        this.x += this.vx * (speed / CONFIG.idleSpeed);
        this.y += this.vy * (speed / CONFIG.idleSpeed);
        if (this.x < 0 || this.x > width) this.vx *= -1;
        if (this.y < 0 || this.y > height) this.vy *= -1;
        this.x = Math.max(0, Math.min(width, this.x));
        this.y = Math.max(0, Math.min(height, this.y));
        this.activation *= 0.94;
        if (state === "thinking" && Math.random() < 0.03) this.activate();
        if (state === "reply" && Math.random() < 0.08) this.activate();
      }
      activate() {
        this.activation = 1;
      }
      draw() {
        const alpha = 0.28 + this.activation * 0.72;
        const color = this.activation > 0.45 ? COLORS.magenta : COLORS.cyan;
        ctx.beginPath();
        ctx.arc(this.x, this.y, this.radius + this.activation * 2, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(${color}, ${alpha})`;
        ctx.fill();
        if (this.activation > 0.12) {
          ctx.beginPath();
          ctx.arc(this.x, this.y, this.radius * 3 + this.activation * 10, 0, Math.PI * 2);
          ctx.fillStyle = `rgba(${color}, ${this.activation * 0.18})`;
          ctx.fill();
        }
      }
    }

    function resize() {
      const rect = canvas.getBoundingClientRect();
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      width = Math.max(120, Math.floor(rect.width));
      height = Math.max(160, Math.floor(rect.height || 220));
      canvas.width = Math.floor(width * dpr);
      canvas.height = Math.floor(height * dpr);
      canvas.style.width = width + "px";
      canvas.style.height = height + "px";
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    }

    function updateConnections() {
      connections = [];
      for (let i = 0; i < nodes.length; i++) {
        for (let j = i + 1; j < nodes.length; j++) {
          const dx = nodes[i].x - nodes[j].x;
          const dy = nodes[i].y - nodes[j].y;
          const dist = Math.sqrt(dx * dx + dy * dy);
          if (dist < CONFIG.connectionDistance) connections.push({ a: i, b: j, dist });
        }
      }
      if (metricSynapses) metricSynapses.textContent = String(connections.length);
    }

    function drawConnection(conn, time) {
      const nodeA = nodes[conn.a];
      const nodeB = nodes[conn.b];
      const active = nodeA.activation > 0.3 || nodeB.activation > 0.3;
      const baseAlpha = 0.12 - (conn.dist / CONFIG.connectionDistance) * 0.08;
      ctx.beginPath();
      ctx.moveTo(nodeA.x, nodeA.y);
      ctx.lineTo(nodeB.x, nodeB.y);
      if (active && (currentState === "thinking" || currentState === "reply")) {
        ctx.strokeStyle = `rgba(${COLORS.amber}, ${baseAlpha + 0.35})`;
        ctx.lineWidth = 1.4;
        ctx.setLineDash([5, 5]);
        ctx.lineDashOffset = -time / 12;
      } else {
        ctx.strokeStyle = `rgba(${COLORS.cyan}, ${baseAlpha})`;
        ctx.lineWidth = 0.6;
        ctx.setLineDash([]);
      }
      ctx.stroke();
      ctx.setLineDash([]);
    }

    function frame() {
      if (destroyed) return;
      const time = Date.now();
      ctx.fillStyle = "rgba(5, 5, 8, 0.18)";
      ctx.fillRect(0, 0, width, height);

      if (currentState === "reply") {
        const cx = width / 2;
        const cy = height / 2;
        const pulse = ((time % 900) / 900) * Math.min(width, height) * 0.45;
        ctx.beginPath();
        ctx.arc(cx, cy, pulse, 0, Math.PI * 2);
        ctx.strokeStyle = `rgba(${COLORS.cyan}, ${0.35 - (time % 900) / 900 * 0.3})`;
        ctx.lineWidth = 2;
        ctx.stroke();
      }

      connections.forEach((c) => drawConnection(c, time));
      let activeCount = 0;
      nodes.forEach((node) => {
        node.update(currentState);
        node.draw();
        if (node.activation > 0.1) activeCount += 1;
      });

      if (metricActivity) {
        const pct = nodes.length ? Math.round((activeCount / nodes.length) * 100) : 0;
        metricActivity.textContent = pct + "%";
      }
      if (metricLatency) {
        if (currentState === "thinking" && thinkStarted) {
          metricLatency.textContent = Math.min(9999, Date.now() - thinkStarted) + "ms";
        } else if (currentState === "idle") {
          metricLatency.textContent = "—";
        }
      }

      if (time % 90 < 2) updateConnections();
      animationId = requestAnimationFrame(frame);
    }

    function drawStatic() {
      ctx.fillStyle = "rgb(5, 5, 8)";
      ctx.fillRect(0, 0, width, height);
      connections.forEach((c) => drawConnection(c, 0));
      nodes.forEach((n) => n.draw());
    }

    function setState(state) {
      const next = String(state || "idle").toLowerCase();
      currentState = next === "thinking" || next === "reply" || next === "idle" ? next : "idle";
      if (stateEl) {
        stateEl.textContent = currentState.toUpperCase();
        stateEl.className = "hal-brain-state " + currentState;
      }
      if (currentState === "thinking") {
        thinkStarted = Date.now();
        nodes.forEach((n) => {
          if (Math.random() < 0.25) n.activate();
        });
      }
      if (currentState === "reply") {
        const cx = width / 2;
        const cy = height / 2;
        nodes.forEach((n) => {
          n.vx += (cx - n.x) * 0.008;
          n.vy += (cy - n.y) * 0.008;
          n.activate();
        });
        if (replyTimer) clearTimeout(replyTimer);
        replyTimer = setTimeout(() => {
          nodes.forEach((n) => {
            n.vx = (Math.random() - 0.5) * CONFIG.idleSpeed;
            n.vy = (Math.random() - 0.5) * CONFIG.idleSpeed;
          });
          setState("idle");
        }, 1600);
      }
    }

    function onVisibility() {
      if (document.hidden) {
        if (animationId) cancelAnimationFrame(animationId);
        animationId = null;
      } else if (!reduced && !animationId && !destroyed) {
        animationId = requestAnimationFrame(frame);
      }
    }

    function destroy() {
      destroyed = true;
      if (animationId) cancelAnimationFrame(animationId);
      if (replyTimer) clearTimeout(replyTimer);
      window.removeEventListener("resize", onResize);
      document.removeEventListener("visibilitychange", onVisibility);
    }

    function onResize() {
      resize();
      updateConnections();
    }

    resize();
    nodes = [];
    for (let i = 0; i < CONFIG.nodeCount; i++) nodes.push(new Node());
    updateConnections();
    window.addEventListener("resize", onResize);
    document.addEventListener("visibilitychange", onVisibility);

    if (reduced) {
      drawStatic();
    } else {
      animationId = requestAnimationFrame(frame);
    }
    setState("idle");

    return { setState, destroy, getState: () => currentState };
  }

  function brainHtml() {
    return `
<div id="hal-brain-container" class="hal-brain-container apex-inst" aria-label="HAL neural core">
  <div class="hal-brain-header">
    <span class="hal-brain-label">NEURAL CORE</span>
    <span id="hal-brain-state" class="hal-brain-state">IDLE</span>
  </div>
  <canvas id="hal-brain-canvas" class="hal-brain-canvas"></canvas>
  <div class="hal-brain-metrics">
    <div class="hal-metric"><span class="hal-metric-label">SYNAPSES</span><span id="hal-metric-synapses" class="hal-metric-value">0</span></div>
    <div class="hal-metric"><span class="hal-metric-label">ACTIVITY</span><span id="hal-metric-activity" class="hal-metric-value">0%</span></div>
    <div class="hal-metric"><span class="hal-metric-label">LATENCY</span><span id="hal-metric-latency" class="hal-metric-value">—</span></div>
  </div>
</div>`;
  }

  function mount(host) {
    if (!host) return null;
    destroy();
    const wrap = document.createElement("div");
    wrap.innerHTML = brainHtml().trim();
    const el = wrap.firstElementChild;
    host.insertBefore(el, host.firstChild);
    instance = createBrain(el);
    window.HALBrain = instance;
    return instance;
  }

  function destroy() {
    if (instance && typeof instance.destroy === "function") instance.destroy();
    instance = null;
    const existing = document.getElementById("hal-brain-container");
    if (existing) existing.remove();
  }

  function setState(state) {
    if (instance && typeof instance.setState === "function") instance.setState(state);
  }

  window.ApexHalBrain = { mount, destroy, setState, get instance() { return instance; } };
})();
