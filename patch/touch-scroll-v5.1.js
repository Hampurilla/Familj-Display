/*
  Familj Display v5.1 - Touch Scroll Safety Layer

  Native browser touch scrolling remains the primary mechanism.
  This script only:
    - prevents accidental text/image drag on display pages,
    - detects real vertical drags,
    - suppresses accidental clicks after a drag,
    - offers a conservative manual-scroll fallback if the browser
      does not move the page during a touch drag.

  It deliberately ignores inputs, selects, textareas and contenteditable.
*/
(() => {
    "use strict";

    if (window.__familjTouchScrollV51Loaded) return;
    window.__familjTouchScrollV51Loaded = true;

    const root = document.documentElement;
    const body = document.body;
    if (!body) return;

    root.classList.add("familj-touch-scroll-v51");

    const isEditable = (el) => !!el?.closest?.(
        'input, textarea, select, option, [contenteditable="true"]'
    );

    const isInteractive = (el) => !!el?.closest?.(
        'button, a, [role="button"], summary, label'
    );

    let pointerId = null;
    let startX = 0;
    let startY = 0;
    let lastY = 0;
    let startScrollY = 0;
    let dragDetected = false;
    let nativeMoved = false;
    let lastMoveAt = 0;

    const DRAG_THRESHOLD = 9;
    const FALLBACK_THRESHOLD = 18;

    const maxScrollY = () =>
        Math.max(0, document.documentElement.scrollHeight - window.innerHeight);

    const clamp = (v, lo, hi) => Math.min(hi, Math.max(lo, v));

    const reset = () => {
        pointerId = null;
        dragDetected = false;
        nativeMoved = false;
    };

    window.addEventListener("pointerdown", (event) => {
        if (event.pointerType !== "touch" && event.pointerType !== "pen") return;
        if (isEditable(event.target)) return;

        pointerId = event.pointerId;
        startX = event.clientX;
        startY = event.clientY;
        lastY = event.clientY;
        startScrollY = window.scrollY;
        dragDetected = false;
        nativeMoved = false;
        lastMoveAt = performance.now();
    }, { passive: true });

    window.addEventListener("scroll", () => {
        if (pointerId !== null && Math.abs(window.scrollY - startScrollY) > 1) {
            nativeMoved = true;
        }
    }, { passive: true });

    window.addEventListener("pointermove", (event) => {
        if (event.pointerId !== pointerId) return;
        if (isEditable(event.target)) return;

        const dx = event.clientX - startX;
        const dy = event.clientY - startY;

        if (!dragDetected && Math.abs(dy) > DRAG_THRESHOLD && Math.abs(dy) > Math.abs(dx)) {
            dragDetected = true;
            body.classList.add("touch-dragging");
        }

        /*
          Conservative fallback:
          Chromium should natively scroll because touch-action: pan-y.
          If it still has not changed scrollY after a clearly vertical drag,
          manually move the page. This prevents "must grab scrollbar" behavior.
        */
        if (
            dragDetected &&
            !nativeMoved &&
            Math.abs(dy) > FALLBACK_THRESHOLD &&
            maxScrollY() > 0
        ) {
            const delta = lastY - event.clientY;
            if (Math.abs(delta) > 0.5) {
                const next = clamp(window.scrollY + delta, 0, maxScrollY());
                window.scrollTo({ top: next, behavior: "auto" });
            }
        }

        lastY = event.clientY;
        lastMoveAt = performance.now();
    }, { passive: true });

    const finish = (event) => {
        if (pointerId === null) return;
        if (event && event.pointerId !== pointerId) return;

        setTimeout(() => {
            body.classList.remove("touch-dragging");
        }, 50);

        pointerId = null;
    };

    window.addEventListener("pointerup", finish, { passive: true });
    window.addEventListener("pointercancel", finish, { passive: true });

    /*
      If a user drags on top of a card/button, do not treat the release
      as an activation. A normal tap still works.
    */
    document.addEventListener("click", (event) => {
        if (!dragDetected) return;
        if (!isInteractive(event.target)) return;

        event.preventDefault();
        event.stopImmediatePropagation();
        dragDetected = false;
    }, true);

    document.addEventListener("dragstart", (event) => {
        if (isEditable(event.target)) return;
        event.preventDefault();
    });

    /* Diagnostics, useful over SSH/DevTools. */
    window.familjTouchScrollDiagnostics = () => ({
        version: "5.1",
        scrollY: window.scrollY,
        scrollHeight: document.documentElement.scrollHeight,
        innerHeight: window.innerHeight,
        maxScrollY: maxScrollY(),
        touchActionBody: getComputedStyle(body).touchAction,
        overflowYBody: getComputedStyle(body).overflowY,
        scrollbarHidden: true
    });
})();
