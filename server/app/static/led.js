// LED control component. Auto-binds every .led-control element on the page.
// Talks to the cam via the nginx /led proxy (so HTTPS-safe).
(function () {
  'use strict';

  var KEEP_ON_WARNING =
    'Keep the LED on permanently?\n\n' +
    '• The cam will get hot — see gotcha #2 in the docs.\n' +
    '• It will likely scare birds away from the feeder.\n\n' +
    'Continue?';

  function init(root) {
    var btn    = root.querySelector('[data-led-btn]');
    var status = root.querySelector('[data-led-status]');
    var keep   = root.querySelector('[data-led-keep-on]');
    if (!btn || !status || !keep) return;

    var poll = null;

    function clearPoll() { if (poll) { clearInterval(poll); poll = null; } }
    function startPoll() { if (!poll) poll = setInterval(refresh, 1000); }

    function paint(d) {
      var on = d.state === 'on';
      btn.setAttribute('aria-checked', on ? 'true' : 'false');
      btn.disabled = false;

      if (on && d.permanent) {
        status.textContent = '⚠ always on — heat risk + scares birds';
        status.className = 'led-status warning';
        keep.hidden = true;
        clearPoll();
      } else if (on) {
        var s = Math.max(1, Math.ceil((d.remaining_ms || 0) / 1000));
        status.textContent = 'on · auto-off in ' + s + 's';
        status.className = 'led-status';
        keep.hidden = false;
        keep.disabled = false;
        startPoll();
      } else {
        status.textContent = 'off';
        status.className = 'led-status muted';
        keep.hidden = true;
        clearPoll();
      }
    }
    function unreachable() {
      status.textContent = 'cam unreachable';
      status.className = 'led-status warning';
      btn.disabled = true;
      keep.hidden = true;
      clearPoll();
    }
    function refresh() {
      fetch('/led', { cache: 'no-store' })
        .then(function (r) { return r.json(); })
        .then(paint).catch(unreachable);
    }

    btn.addEventListener('click', function () {
      var isOn = btn.getAttribute('aria-checked') === 'true';
      var target = isOn ? '/led/off' : '/led/on';
      btn.disabled = true;
      fetch(target, { cache: 'no-store' })
        .then(function (r) { return r.json(); })
        .then(paint).catch(unreachable);
    });

    keep.addEventListener('click', function () {
      if (!confirm(KEEP_ON_WARNING)) return;
      keep.disabled = true;
      fetch('/led/on/permanent', { cache: 'no-store' })
        .then(function (r) { return r.json(); })
        .then(paint).catch(unreachable);
    });

    refresh();
  }

  function boot() {
    document.querySelectorAll('.led-control').forEach(init);
  }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }
})();
