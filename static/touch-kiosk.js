/* Hemma Touch 5.2.0
 * Native touch pan + mouse-emulated touch drag. Display routes only.
 * No framework, no timers while idle, no changes to admin interactions.
 */
(() => {
  'use strict';
  const root = document.documentElement;
  const body = document.body;
  if (!root.classList.contains('kiosk-touch-page') ||
      !body?.classList.contains('display-page') ||
      /^\/admin(?:\/|$)/.test(location.pathname) || window.HemmaTouchScroll) return;

  const VERSION = '5.2.0';
  const THRESHOLD = 8; // CSS pixels; small tap jitter must not become a drag.
  const FORM = 'input,textarea,select,option,[contenteditable]:not([contenteditable="false"]),[data-no-drag]';
  const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
  let active = null, frame = 0, momentum = null, blockedClickUntil = 0;
  let nativeContacts = 0;
  let busyUntil = 0, lastType = 'none', drags = 0, suppressedClicks = 0;
  let lastDragDistance = 0;
  const clock = () => performance.now();
  const element = target => target instanceof Element ? target : target?.parentElement;
  const editable = target => Boolean(element(target)?.closest(FORM));
  const docScroller = () => document.scrollingElement || root;
  const saverVisible = () => {
    const saver = document.getElementById('screensaver');
    return Boolean(saver && !saver.hidden);
  };

  function stopMomentum() {
    if (frame) cancelAnimationFrame(frame);
    frame = 0; momentum = null;
  }

  function releaseCapture(state) {
    if (!state?.captured) return;
    try { if (root.hasPointerCapture(state.id)) root.releasePointerCapture(state.id); }
    catch (_) { /* The browser may already have released it. */ }
  }

  function resetGesture() {
    const previous = active;
    active = null;
    releaseCapture(previous);
    body.classList.remove('kiosk-dragging');
  }

  // Find the actual scrolling elements, not only window.scrollY.
  // At an inner list's boundary, residual motion can continue on its parent.
  // A modal never scrolls the page underneath it.
  function scrollChain(target) {
    const chain = [], scrolling = docScroller();
    const boundary = target.closest('[role="dialog"],dialog[open]');
    for (let node = target; node && node !== body && node !== root; node = node.parentElement) {
      const style = getComputedStyle(node);
      if (/^(auto|scroll)$/.test(style.overflowY) && node.scrollHeight > node.clientHeight + 1) chain.push(node);
      if (node === boundary) return chain;
    }
    if (!body.classList.contains('modal-open') && scrolling.scrollHeight > root.clientHeight + 1) chain.push(scrolling);
    return chain;
  }

  function moveChain(chain, distance) {
    let remaining = distance, total = 0;
    for (const node of chain) {
      if (!node.isConnected) continue;
      const max = Math.max(0, node.scrollHeight - node.clientHeight);
      const before = node.scrollTop;
      node.scrollTop = Math.min(max, Math.max(0, before + remaining));
      const moved = node.scrollTop - before;
      total += moved; remaining -= moved;
      if (Math.abs(remaining) < 0.5) break;
    }
    return total;
  }

  function coast(chain, velocity) {
    stopMomentum();
    if (reducedMotion.matches || Math.abs(velocity) < 0.12 || !chain.length) return;
    const started = clock();
    momentum = {chain, velocity: Math.max(-2.5, Math.min(2.5, velocity)), last: started, started};
    const step = timestamp => {
      if (!momentum || active || saverVisible() || document.hidden) { stopMomentum(); return; }
      const m = momentum, dt = Math.min(34, Math.max(1, timestamp - m.last));
      m.last = timestamp;
      m.velocity *= Math.exp(-dt / 190);
      if (Math.abs(m.velocity) < 0.04 || timestamp - m.started > 850) { stopMomentum(); return; }
      const moved = moveChain(m.chain, m.velocity * dt);
      if (Math.abs(moved) < 0.5) { stopMomentum(); return; }
      busyUntil = timestamp + 180;
      frame = requestAnimationFrame(step);
    };
    frame = requestAnimationFrame(step);
  }

  window.addEventListener('pointerdown', event => {
    stopMomentum();
    // A fresh gesture must never inherit the previous drag's click blocker.
    blockedClickUntil = 0;
    if (active) resetGesture();
    lastType = event.pointerType || 'unknown';
    if (!event.isPrimary || event.button !== 0 || editable(event.target) || saverVisible()) return;
    const target = element(event.target);
    if (!target) return;
    const t = clock();
    active = {
      id: event.pointerId, type: event.pointerType || 'mouse', target,
      x: event.clientX, y: event.clientY, lastY: event.clientY, lastT: t,
      moved: false, dragging: false, captured: false, distance: 0,
      velocity: 0, chain: scrollChain(target)
    };
  }, {capture: true, passive: true});

  window.addEventListener('pointermove', event => {
    const s = active;
    if (!s || event.pointerId !== s.id) return;
    if (s.type === 'mouse' && !(event.buttons & 1)) { resetGesture(); return; }
    const dx = event.clientX - s.x, dy = event.clientY - s.y;
    s.distance = Math.max(s.distance, Math.hypot(dx, dy));
    if (s.distance >= THRESHOLD) s.moved = true;

    // Real touch/pen uses Chromium's own scrolling and momentum. Never
    // manually scroll while the browser is handling a native gesture.
    if (s.type === 'touch' || s.type === 'pen') return;

    // Also accepts an unrecognised pointer type, seen on some kiosk drivers.
    if (!s.dragging && Math.abs(dy) >= THRESHOLD) {
      s.dragging = true; drags += 1;
      body.classList.add('kiosk-dragging');
      try { root.setPointerCapture(s.id); s.captured = true; } catch (_) {}
    }
    if (!s.dragging) return;
    if (event.cancelable) event.preventDefault();
    const t = clock(), delta = s.lastY - event.clientY, dt = Math.max(8, t - s.lastT);
    const moved = moveChain(s.chain, delta);
    s.velocity = 0.35 * s.velocity + 0.65 * Math.max(-2.5, Math.min(2.5, moved / dt));
    s.lastY = event.clientY; s.lastT = t;
    lastDragDistance = s.distance;
    busyUntil = t + 180;
  }, {capture: true, passive: false});

  function finish(event, cancelled) {
    const s = active;
    if (!s || s.id !== event.pointerId) return;
    const t = clock();
    // Native touch normally fires pointercancel once panning begins.
    if (s.moved || cancelled) {
      blockedClickUntil = t + 650;
      if (!s.dragging) drags += 1;
      lastDragDistance = s.distance;
      busyUntil = t + 180;
    }
    resetGesture();
    if (!cancelled && s.dragging && t - s.lastT < 100) coast(s.chain, s.velocity);
  }
  window.addEventListener('pointerup', event => finish(event, false), {capture: true, passive: true});
  window.addEventListener('pointercancel', event => finish(event, true), {capture: true, passive: true});
  window.addEventListener('lostpointercapture', event => {
    if (active?.id === event.pointerId && active.captured) finish(event, true);
  }, {capture: true, passive: true});

  // Links/images otherwise start desktop HTML drag-and-drop on XWayland.
  document.addEventListener('dragstart', event => {
    if (!editable(event.target)) event.preventDefault();
  }, true);
  document.addEventListener('selectstart', event => {
    if (!editable(event.target)) event.preventDefault();
  }, true);
  document.addEventListener('contextmenu', event => {
    if (!editable(event.target)) event.preventDefault();
  }, true);
  window.addEventListener('click', event => {
    // Keyboard activation (detail=0) stays accessible. A new pointerdown
    // resets the blocker, so the very next deliberate tap still works.
    if (event.detail !== 0 && clock() < blockedClickUntil) {
      suppressedClicks += 1;
      event.preventDefault(); event.stopImmediatePropagation();
    }
  }, true);
  window.addEventListener('scroll', () => { busyUntil = clock() + 180; }, {capture: true, passive: true});
  // Pointer events are cancelled during native pan, but touchend still
  // tells us when the finger actually leaves the screen. Keep live DOM
  // replacements paused even when the finger is held still after a swipe.
  ['touchstart','touchend','touchcancel'].forEach(name => {
    window.addEventListener(name, event => {
      nativeContacts = event.touches.length;
      busyUntil = clock() + 180;
    }, {capture: true, passive: true});
  });
  window.addEventListener('wheel', stopMomentum, {passive: true});
  window.addEventListener('keydown', stopMomentum, {capture: true, passive: true});
  window.addEventListener('blur', () => { nativeContacts = 0; stopMomentum(); resetGesture(); });
  document.addEventListener('visibilitychange', () => {
    if (document.hidden) { nativeContacts = 0; stopMomentum(); resetGesture(); }
  });

  // Refresh code uses this to avoid replacing a card mid-drag.
  window.HemmaTouchScroll = Object.freeze({
    version: VERSION,
    isBusy: () => Boolean(active || nativeContacts || momentum || clock() < busyUntil),
    stop: () => { stopMomentum(); resetGesture(); },
    diagnostics: () => ({
      version: VERSION, pointerType: lastType, drags, suppressedClicks,
      lastDragDistance: Math.round(lastDragDistance),
      scrollY: Math.round(docScroller().scrollTop),
      maxScrollY: Math.max(0, docScroller().scrollHeight - root.clientHeight),
      dragging: Boolean(active?.dragging), nativeGesture: nativeContacts > 0 || active?.type === 'touch',
      scrollbarWidth: getComputedStyle(root).scrollbarWidth,
      scrollbarGutterPx: window.innerWidth - root.clientWidth,
      nativeTouchAction: getComputedStyle(body).touchAction,
      mouseDragEnabled: true
    })
  });
  root.dataset.touchVersion = VERSION;
})();
