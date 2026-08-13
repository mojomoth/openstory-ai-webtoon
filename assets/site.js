(() => {
  const bar = document.querySelector('.progress > span');
  if (bar) {
    const update = () => {
      const max = document.documentElement.scrollHeight - innerHeight;
      bar.style.width = `${max > 0 ? Math.min(100, scrollY / max * 100) : 0}%`;
    };
    addEventListener('scroll', update, { passive: true });
    addEventListener('resize', update);
    update();
  }

  document.querySelectorAll('.panel').forEach((panel, index) => {
    panel.setAttribute('aria-label', `${index + 1}번째 패널`);
  });
})();

