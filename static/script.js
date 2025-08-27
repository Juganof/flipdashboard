document.addEventListener('DOMContentLoaded', function () {
  const modalElement = document.getElementById('listingModal');
  const modal = new bootstrap.Modal(modalElement);

  document.querySelectorAll('.listing-card').forEach(card => {
    card.addEventListener('click', () => {
      const listingId = card.dataset.id;
      const listing = listings.find(l => l.id === listingId);

      if (listing) {
        document.getElementById('modalTitle').textContent = listing.title || '';
        document.getElementById('modalPrice').textContent = listing.price || 'N/A';
        document.getElementById('modalLocation').textContent = listing.location || 'N/A';
        document.getElementById('modalDate').textContent = listing.start_date || 'N/A';
        document.getElementById('modalSeller').textContent = listing.seller ? listing.seller.sellerName : 'N/A';
        document.getElementById('modalSellerRating').textContent = listing.seller ? (listing.seller.sellerReviewAverage || listing.seller.sellerReviewScore) : 'N/A';
        
        const shippingOptions = listing.shipping_options || [];
        const shippingText = shippingOptions.map(option => option.name).join(', ');
        document.getElementById('modalShipping').textContent = shippingText || 'N/A';
        
        document.getElementById('modalDescription').textContent = listing.description || 'No description available';
        
        const img = document.getElementById('modalImage');
        if (listing.image_url) {
          img.src = listing.image_url;
          img.alt = listing.title || '';
          img.classList.remove('d-none');
        } else {
          img.classList.add('d-none');
        }
        
        const link = document.getElementById('modalUrl');
        link.href = listing.url;
        
        modal.show();
      }
    });
  });
});