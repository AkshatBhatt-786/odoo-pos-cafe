document.addEventListener('DOMContentLoaded', () => {

  // ── Custom Cursor ──────────────────────────────────────────
  const cursorDot  = document.getElementById('cursor');
  const cursorRing = document.getElementById('cursorRing');

  if (cursorDot && cursorRing) {
    let mx = 0, my = 0, rx = 0, ry = 0;
    let cursorVisible = false;

    document.addEventListener('mousemove', e => {
      mx = e.clientX;
      my = e.clientY;
      if (!cursorVisible) {
        cursorDot.style.opacity  = '1';
        cursorRing.style.opacity = '0.5';
        cursorVisible = true;
      }
    });

    document.addEventListener('mouseleave', () => {
      cursorDot.style.opacity  = '0';
      cursorRing.style.opacity = '0';
      cursorVisible = false;
    });

    function animateCursor() {
      cursorDot.style.left = mx + 'px';
      cursorDot.style.top  = my + 'px';
      rx += (mx - rx) * 0.12;
      ry += (my - ry) * 0.12;
      cursorRing.style.left = rx + 'px';
      cursorRing.style.top  = ry + 'px';
      requestAnimationFrame(animateCursor);
    }
    animateCursor();

    const hoverEls = document.querySelectorAll('a, button, .feature-card, .method-pill, .kds-ticket, .mini-table-card');
    hoverEls.forEach(el => {
      el.addEventListener('mouseenter', () => {
        cursorDot.style.transform  = 'translate(-50%,-50%) scale(2.5)';
        cursorRing.style.transform = 'translate(-50%,-50%) scale(1.4)';
        cursorRing.style.opacity   = '0.2';
      });
      el.addEventListener('mouseleave', () => {
        cursorDot.style.transform  = 'translate(-50%,-50%) scale(1)';
        cursorRing.style.transform = 'translate(-50%,-50%) scale(1)';
        cursorRing.style.opacity   = '0.5';
      });
    });
  }

  // ── Scroll Reveal ─────────────────────────────────────────
  const reveals = document.querySelectorAll('.reveal');
  if (reveals.length > 0) {
    const observer = new IntersectionObserver((entries) => {
      entries.forEach((entry, i) => {
        if (entry.isIntersecting) {
          setTimeout(() => {
            entry.target.classList.add('visible');
          }, i * 80);
          observer.unobserve(entry.target);
        }
      });
    }, { threshold: 0.1 });

    reveals.forEach(el => observer.observe(el));
  }

  // ── Auto-dismiss alerts ───────────────────────────────────
  const alerts = document.querySelectorAll('.alert[data-auto-dismiss]');
  alerts.forEach(alert => {
    const delay = parseInt(alert.dataset.autoDismiss) || 3000;
    setTimeout(() => {
      alert.style.transition = 'opacity 0.4s ease';
      alert.style.opacity = '0';
      setTimeout(() => alert.remove(), 400);
    }, delay);
  });

  // ── Active nav link ───────────────────────────────────────
  const currentPath = window.location.pathname;
  document.querySelectorAll('.nav__link').forEach(link => {
    if (link.getAttribute('href') === currentPath) {
      link.classList.add('active');
    }
  });

});
