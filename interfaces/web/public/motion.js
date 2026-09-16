/*
 * SAYELF shared motion capability.
 * GSAP is the renderer; this layer owns no story state and no visual design.
 * Callers only choose an element and a small intent such as reveal() or draw().
 */
const SAYELF_MOTION = (() => {
  const version = '1.0.0';
  const root = () => typeof window !== 'undefined' ? window : globalThis;
  const engine = () => {
    const candidate = root().gsap;
    return candidate && typeof candidate.to === 'function' && typeof candidate.timeline === 'function' ? candidate : null;
  };
  const reducedMotion = () => {
    try { return Boolean(root().matchMedia?.('(prefers-reduced-motion: reduce)').matches); }
    catch { return false; }
  };
  const nodes = target => {
    if (!target) return [];
    const doc = typeof document === 'undefined' ? null : document;
    const win = typeof window === 'undefined' ? null : window;
    if (typeof target === 'string') return doc ? [...doc.querySelectorAll(target)] : [];
    const ElementType = typeof Element === 'undefined' ? null : Element;
    if ((ElementType && target instanceof ElementType) || target === doc || target === win) return [target];
    return [...(target.length === undefined ? [target] : target)].filter(Boolean);
  };
  const idle = { kill() {}, revert() {}, pause() {}, play() {} };
  function applyImmediate(target, values = {}) {
    nodes(target).forEach(node => {
      if (!node?.style) return;
      if ('opacity' in values) node.style.opacity = values.opacity;
      if ('autoAlpha' in values) node.style.opacity = values.autoAlpha;
      const x = values.x ?? 0, y = values.y ?? 0, scale = values.scale;
      if ('x' in values || 'y' in values || 'scale' in values) {
        node.style.transform = `translate3d(${x}px,${y}px,0)${scale === undefined ? '' : ` scale(${scale})`}`;
      }
      if ('strokeDasharray' in values) node.style.strokeDasharray = values.strokeDasharray;
      if ('strokeDashoffset' in values) node.style.strokeDashoffset = values.strokeDashoffset;
      if ('fillOpacity' in values) node.style.fillOpacity = values.fillOpacity;
    });
  }
  function animate(target, vars = {}, options = {}) {
    const list = nodes(target);
    if (!list.length) return idle;
    const gs = engine();
    const duration = reducedMotion() ? 0 : Number(options.duration ?? vars.duration ?? .4);
    const end = { ...vars };
    delete end.duration; delete end.stagger; delete end.ease; delete end.delay;
    if (!gs || duration <= 0) { applyImmediate(list, end); return idle; }
    return gs.to(list, { ...vars, duration, ease: options.ease || vars.ease || 'power2.out' });
  }
  function reveal(target, options = {}) {
    const list = nodes(target);
    if (!list.length) return idle;
    const gs = engine();
    const duration = reducedMotion() ? 0 : Number(options.duration ?? .45);
    const y = Number(options.y ?? 10);
    if (!gs || duration <= 0) { applyImmediate(list, { autoAlpha: 1, x: 0, y: 0 }); return idle; }
    return gs.fromTo(list, { autoAlpha: 0, y }, { autoAlpha: 1, y: 0, duration, stagger: options.stagger ?? .04, ease: options.ease || 'power2.out' });
  }
  function draw(svg, options = {}) {
    const list = svg ? [...svg.querySelectorAll('.ink-layer path,.ink-layer circle,.ink-layer rect,.ink-layer ellipse')] : [];
    if (!list.length) return idle;
    svg.classList.add('draw-active');
    const cleanupClasses = () => svg.classList.remove('draw-active', 'motion-gsap');
    const finalState = { strokeDasharray: 'none', strokeDashoffset: 0, fillOpacity: 1 };
    if (reducedMotion()) { applyImmediate(list, finalState); return { kill: cleanupClasses, revert: cleanupClasses }; }
    const gs = engine();
    if (!gs) {
      void svg.offsetWidth;
      return { kill: cleanupClasses, revert: cleanupClasses };
    }
    svg.classList.add('motion-gsap');
    let timeline;
    const context = typeof gs.context === 'function'
      ? gs.context(() => {
          timeline = gs.timeline({ defaults: { ease: options.ease || 'power2.out' } });
          timeline.set(list, { strokeDasharray: options.strokeDasharray || 1050, strokeDashoffset: options.strokeDashoffset ?? 1050, fillOpacity: 0 });
          timeline.to(list, { strokeDashoffset: 0, fillOpacity: 1, duration: Number(options.duration ?? 3.1), stagger: options.stagger ?? .04, onComplete: options.onComplete });
        }, svg)
      : null;
    return {
      kill() { timeline?.kill(); context?.revert(); cleanupClasses(); },
      revert() { timeline?.kill(); context?.revert(); cleanupClasses(); },
      play() { timeline?.play(); }
    };
  }
  function stop(target) { const gs = engine(); if (gs) gs.killTweensOf(nodes(target)); }
  function context(scope, callback) {
    const gs = engine();
    return gs?.context ? gs.context(callback, scope) : { revert() {} };
  }
  return Object.freeze({ version, available: () => Boolean(engine()), renderer: () => engine() ? 'gsap' : 'css', reducedMotion, animate, reveal, draw, stop, context });
})();
globalThis.SAYELF_MOTION = SAYELF_MOTION;
