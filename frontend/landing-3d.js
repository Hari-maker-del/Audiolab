(() => {
  "use strict";
  const canvas = document.getElementById("soundOrb");
  const scene = document.querySelector(".orb-scene");
  const heroArt = document.getElementById("heroArt");
  const menuButton = document.getElementById("navMenu");
  const navLinks = document.getElementById("navLinks");
  const reducedMotion = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const ctx = canvas && canvas.getContext("2d", { alpha: true });
  let width = 0, height = 0, dpr = 1, animationId = 0, pointerX = 0, pointerY = 0, currentX = 0, currentY = 0, lastTime = 0;
  const points = [];
  const stars = [];
  const TAU = Math.PI * 2;

  function randomSeeded(i) {
    const x = Math.sin(i * 127.1 + 311.7) * 43758.5453;
    return x - Math.floor(x);
  }

  // Fibonacci sphere points form the glowing 3D wire object without external libraries.
  for (let i = 0; i < 620; i++) {
    const y = 1 - (i / 619) * 2;
    const radius = Math.sqrt(Math.max(0, 1 - y * y));
    const theta = Math.PI * (3 - Math.sqrt(5)) * i;
    points.push({ x: Math.cos(theta) * radius, y, z: Math.sin(theta) * radius, size: 0.5 + randomSeeded(i) * 1.35, phase: randomSeeded(i + 44) * TAU });
  }
  for (let i = 0; i < 110; i++) {
    stars.push({ x: randomSeeded(i + 900) * 2 - 1, y: randomSeeded(i + 1200) * 2 - 1, z: randomSeeded(i + 1500), r: 0.35 + randomSeeded(i + 1700) * 1.15 });
  }

  function resize() {
    if (!canvas || !scene || !ctx) return;
    const rect = scene.getBoundingClientRect();
    width = Math.max(1, rect.width);
    height = Math.max(1, rect.height);
    dpr = Math.min(window.devicePixelRatio || 1, 1.8);
    canvas.width = Math.floor(width * dpr);
    canvas.height = Math.floor(height * dpr);
    canvas.style.width = width + "px";
    canvas.style.height = height + "px";
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    draw(0);
  }

  function rotate(p, ax, ay, az) {
    const cx = Math.cos(ax), sx = Math.sin(ax), cy = Math.cos(ay), sy = Math.sin(ay), cz = Math.cos(az), sz = Math.sin(az);
    let y = p.y * cx - p.z * sx;
    let z = p.y * sx + p.z * cx;
    let x = p.x * cy + z * sy;
    z = -p.x * sy + z * cy;
    const xx = x * cz - y * sz;
    const yy = x * sz + y * cz;
    return { x: xx, y: yy, z };
  }

  function project(p, scale, cx, cy) {
    const focal = 3.55;
    const perspective = focal / (focal + p.z);
    return { x: cx + p.x * scale * perspective, y: cy + p.y * scale * perspective, z: p.z, size: perspective };
  }

  function drawRing(rotation, radiusX, radiusY, rotationZ, cx, cy, scale, color, lineWidth, phase) {
    const ring = [];
    for (let i = 0; i <= 180; i++) {
      const a = i / 180 * TAU;
      const base = { x: Math.cos(a) * radiusX, y: Math.sin(a) * radiusY, z: 0 };
      const p = rotate(base, rotation.x, rotation.y, rotationZ);
      ring.push(project(p, scale, cx, cy));
    }
    for (let i = 1; i < ring.length; i++) {
      const a = ring[i - 1], b = ring[i];
      const depthAlpha = Math.max(0.07, Math.min(0.76, 0.3 + (a.z + b.z) * 0.2));
      ctx.beginPath();
      ctx.moveTo(a.x, a.y);
      ctx.lineTo(b.x, b.y);
      ctx.strokeStyle = color.replace("ALPHA", depthAlpha.toFixed(3));
      ctx.lineWidth = lineWidth * (a.z > 0 ? 1.2 : 0.7);
      ctx.stroke();
    }
    const a = rotate({ x: Math.cos(phase) * radiusX, y: Math.sin(phase) * radiusY, z: 0 }, rotation.x, rotation.y, rotationZ);
    const dot = project(a, scale, cx, cy);
    ctx.beginPath();
    ctx.arc(dot.x, dot.y, 2.1, 0, TAU);
    ctx.fillStyle = "#edbb65";
    ctx.shadowColor = "#db9c50";
    ctx.shadowBlur = 12;
    ctx.fill();
    ctx.shadowBlur = 0;
  }

  function draw(timestamp) {
    if (!ctx || !width || !height) return;
    const t = reducedMotion ? 0.7 : timestamp * 0.00022;
    currentX += (pointerX - currentX) * 0.035;
    currentY += (pointerY - currentY) * 0.035;
    ctx.clearRect(0, 0, width, height);

    const cx = width * 0.5 + currentX * width * 0.025;
    const cy = height * 0.49 + currentY * height * 0.025;
    const scale = Math.min(width, height) * 0.335;
    const ax = 0.25 + currentY * 0.2 + Math.sin(t * 0.8) * 0.09;
    const ay = t + currentX * 0.45;
    const az = Math.sin(t * 0.56) * 0.12;

    // Background stars and subtle depth specks.
    for (const s of stars) {
      const x = (s.x * width * 0.48) + width * 0.5;
      const y = (s.y * height * 0.48) + height * 0.5;
      const alpha = 0.14 + (0.5 + 0.5 * Math.sin(t * 4 + s.z * 12)) * 0.29;
      ctx.beginPath();
      ctx.arc(x, y, s.r, 0, TAU);
      ctx.fillStyle = "rgba(233,204,156," + alpha.toFixed(3) + ")";
      ctx.fill();
    }

    drawRing({ x: 1.05, y: 0.32 + Math.sin(t) * 0.08 }, 1.28, 0.55, t * 0.17, cx, cy, scale, "rgba(224,171,91,ALPHA)", 0.8, t * 1.4);
    drawRing({ x: -0.88, y: -0.36 }, 1.17, 0.76, -t * 0.24, cx, cy, scale, "rgba(225,126,65,ALPHA)", 0.65, t * 1.8 + 2);
    drawRing({ x: 0.1, y: 1.18 }, 1.36, 0.38, t * 0.3, cx, cy, scale, "rgba(225,200,147,ALPHA)", 0.5, -t * 1.3);

    const projected = [];
    for (const p of points) {
      const q = rotate(p, ax, ay, az);
      projected.push({ ...project(q, scale, cx, cy), base: p });
    }

    // Structured mesh lines: each sphere meridian is drawn in the rotated 3D space.
    const latitudeCount = 18;
    const longitudeCount = 28;
    ctx.lineWidth = 0.62;
    for (let lat = 1; lat < latitudeCount; lat++) {
      ctx.beginPath();
      let active = false;
      let segmentStart = null;
      for (let lon = 0; lon <= longitudeCount; lon++) {
        const phi = -Math.PI / 2 + Math.PI * lat / latitudeCount;
        const theta = TAU * lon / longitudeCount;
        const p = rotate({ x: Math.cos(phi) * Math.cos(theta), y: Math.sin(phi), z: Math.cos(phi) * Math.sin(theta) }, ax, ay, az);
        const v = project(p, scale, cx, cy);
        if (!active) { ctx.moveTo(v.x, v.y); active = true; }
        else ctx.lineTo(v.x, v.y);
        segmentStart = v;
      }
      ctx.strokeStyle = lat % 3 === 0 ? "rgba(232,179,101,0.24)" : "rgba(221,161,84,0.12)";
      ctx.stroke();
    }
    for (let lon = 0; lon < longitudeCount; lon++) {
      ctx.beginPath();
      for (let lat = 0; lat <= latitudeCount; lat++) {
        const phi = -Math.PI / 2 + Math.PI * lat / latitudeCount;
        const theta = TAU * lon / longitudeCount;
        const p = rotate({ x: Math.cos(phi) * Math.cos(theta), y: Math.sin(phi), z: Math.cos(phi) * Math.sin(theta) }, ax, ay, az);
        const v = project(p, scale, cx, cy);
        if (lat === 0) ctx.moveTo(v.x, v.y);
        else ctx.lineTo(v.x, v.y);
      }
      ctx.strokeStyle = lon % 3 === 0 ? "rgba(232,179,101,0.22)" : "rgba(221,161,84,0.11)";
      ctx.stroke();
    }

    // Glowing particle shell, with brighter points on the visible hemisphere.
    projected.sort((a, b) => a.z - b.z);
    for (const p of projected) {
      const alpha = Math.max(0.09, Math.min(0.95, 0.17 + (p.z + 1) * 0.36));
      const pulse = reducedMotion ? 1 : 0.83 + 0.17 * Math.sin(t * 2.7 + p.base.phase);
      const r = p.base.size * (0.65 + (p.z + 1) * 0.28) * pulse;
      ctx.beginPath();
      ctx.arc(p.x, p.y, r, 0, TAU);
      ctx.fillStyle = "rgba(246,196,113," + alpha.toFixed(3) + ")";
      if (p.z > 0.25) { ctx.shadowBlur = 7; ctx.shadowColor = "rgba(230,158,75,0.75)"; }
      ctx.fill();
      ctx.shadowBlur = 0;
    }

    // Small central light, like a signal source inside the shell.
    const core = ctx.createRadialGradient(cx - scale * 0.18, cy - scale * 0.2, 2, cx, cy, scale * 0.82);
    core.addColorStop(0, "rgba(246,200,126,0.12)");
    core.addColorStop(0.43, "rgba(213,131,58,0.06)");
    core.addColorStop(1, "rgba(0,0,0,0)");
    ctx.fillStyle = core;
    ctx.beginPath();
    ctx.arc(cx, cy, scale * 0.82, 0, TAU);
    ctx.fill();

    lastTime = timestamp;
  }

  function animate(timestamp) {
    draw(timestamp);
    if (!reducedMotion && !document.hidden) animationId = requestAnimationFrame(animate);
  }

  if (ctx && scene) {
    resize();
    const observer = new ResizeObserver(resize);
    observer.observe(scene);
    if (!reducedMotion) animationId = requestAnimationFrame(animate);

    scene.addEventListener("pointermove", event => {
      const r = scene.getBoundingClientRect();
      pointerX = ((event.clientX - r.left) / r.width - 0.5) * 2;
      pointerY = ((event.clientY - r.top) / r.height - 0.5) * 2;
    });
    scene.addEventListener("pointerleave", () => { pointerX = 0; pointerY = 0; });

    document.addEventListener("visibilitychange", () => {
      if (document.hidden && animationId) cancelAnimationFrame(animationId);
      else if (!document.hidden && !reducedMotion) animationId = requestAnimationFrame(animate);
    });
    window.addEventListener("beforeunload", () => { if (animationId) cancelAnimationFrame(animationId); });
  } else if (canvas) {
    canvas.hidden = true;
  }

  // Subtle 3D tilt on feature cards; disabled on touch and reduced-motion devices.
  if (!reducedMotion && window.matchMedia("(pointer:fine)").matches) {
    document.querySelectorAll(".tilt-card").forEach(card => {
      card.addEventListener("pointermove", event => {
        const rect = card.getBoundingClientRect();
        const nx = (event.clientX - rect.left) / rect.width - 0.5;
        const ny = (event.clientY - rect.top) / rect.height - 0.5;
        card.style.transform = "rotateX(" + (-ny * 4).toFixed(2) + "deg) rotateY(" + (nx * 5).toFixed(2) + "deg) translateY(-2px)";
      });
      card.addEventListener("pointerleave", () => { card.style.transform = ""; });
    });
  }

  if (menuButton && navLinks) {
    menuButton.addEventListener("click", () => {
      const open = navLinks.classList.toggle("is-open");
      menuButton.setAttribute("aria-expanded", String(open));
    });
    navLinks.querySelectorAll("a").forEach(link => link.addEventListener("click", () => {
      navLinks.classList.remove("is-open");
      menuButton.setAttribute("aria-expanded", "false");
    }));
  }

  const year = document.getElementById("year");
  if (year) year.textContent = String(new Date().getFullYear());
  window.addEventListener("pagehide", () => { if (animationId) cancelAnimationFrame(animationId); });
})();