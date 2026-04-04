document.addEventListener('DOMContentLoaded', () => {

  // ── QR Code Grid ──────────────────────────────────────────
  const qrGrid = document.getElementById('qrGrid');
  if (qrGrid) {
    const pattern = [
      1,1,1,1,1,1,0,1,
      1,0,0,0,0,1,1,0,
      1,0,1,1,0,1,0,1,
      1,0,1,1,0,1,1,1,
      1,0,0,0,0,1,0,0,
      1,1,1,1,1,1,1,0,
      0,1,0,1,0,1,0,1,
      1,0,1,1,0,0,1,1,
    ];
    pattern.forEach(v => {
      const cell = document.createElement('div');
      cell.className = 'qr-cell' + (v ? '' : ' qr-cell--dark');
      qrGrid.appendChild(cell);
    });
  }

  // ── Payment method pills ──────────────────────────────────
  const pills = document.querySelectorAll('.method-pill');
  pills.forEach(pill => {
    pill.addEventListener('click', () => {
      pills.forEach(p => p.classList.remove('active'));
      pill.classList.add('active');
    });
  });

  document.querySelectorAll('a[href^="#"]').forEach(anchor => {
    anchor.addEventListener('click', e => {
      e.preventDefault();
      const target = document.querySelector(anchor.getAttribute('href'));
      if (target) {
        target.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }
    });
  });

});
