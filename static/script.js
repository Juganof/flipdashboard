document.addEventListener('DOMContentLoaded', function () {
  const modalElement = document.getElementById('listingModal');
  const modal = new bootstrap.Modal(modalElement);

  document.querySelectorAll('.listing-card').forEach(card => {
    card.addEventListener('click', () => {
      document.getElementById('modalTitle').textContent = card.dataset.title || '';
      document.getElementById('modalPrice').textContent = card.dataset.price || 'N/A';
      document.getElementById('modalLocation').textContent = card.dataset.location || 'N/A';
      const img = document.getElementById('modalImage');
      if (card.dataset.image) {
        img.src = card.dataset.image;
        img.alt = card.dataset.title || '';
        img.classList.remove('d-none');
      } else {
        img.classList.add('d-none');
      }
      const link = document.getElementById('modalUrl');
      link.href = card.dataset.url;
      modal.show();
    });
  });
});
