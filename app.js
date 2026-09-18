// Telegram Mini App Controller
(function() {
  const tg = window.Telegram?.WebApp;
  if (tg) {
    tg.ready();
    tg.expand();
    // Enable closing confirmation if needed
    tg.enableClosingConfirmation?.();
  }

  let fullData = {
    double_deals: [],
    family_coupons: [],
    store_offers: []
  };

  let currentTab = 'double';
  let currentMember = 'all';
  let searchQuery = '';

  // DOM Elements
  const searchInput = document.getElementById('search-input');
  const clearBtn = document.getElementById('clear-search');
  const cardsContainer = document.getElementById('cards-container');
  const emptyState = document.getElementById('empty-state');
  const loadingSpinner = document.getElementById('loading-spinner');
  const updateTimeEl = document.getElementById('update-time');
  const refreshBtn = document.getElementById('refresh-btn');
  const scrollTopBtn = document.getElementById('scroll-top-btn');
  const badgeDouble = document.getElementById('badge-double');
  const badgeCoupons = document.getElementById('badge-coupons');
  const badgeStore = document.getElementById('badge-store');
  const toastEl = document.getElementById('toast');

  // Trigger haptic feedback
  function haptic(type = 'light') {
    if (!tg?.HapticFeedback) return;
    if (type === 'selection') tg.HapticFeedback.selectionChanged();
    else if (type === 'success') tg.HapticFeedback.notificationOccurred('success');
    else tg.HapticFeedback.impactOccurred(type);
  }

  // Show toast notification
  function showToast(msg) {
    if (!toastEl) return;
    toastEl.textContent = msg;
    toastEl.classList.remove('hidden');
    setTimeout(() => {
      toastEl.classList.add('hidden');
    }, 2000);
  }

  // Load data.json
  async function loadData() {
    loadingSpinner.classList.remove('hidden');
    cardsContainer.innerHTML = '';
    emptyState.classList.add('hidden');

    try {
      // Cache buster for fresh data
      const res = await fetch(`data.json?v=${Date.now()}`);
      if (!res.ok) throw new Error('HTTP ' + res.status);
      fullData = await res.json();

      updateHeader();
      renderCurrentList();
    } catch (err) {
      console.error('Ошибка загрузки данных:', err);
      loadingSpinner.classList.add('hidden');
      emptyState.classList.remove('hidden');
      emptyState.querySelector('h3').textContent = 'Ошибка загрузки данных';
      emptyState.querySelector('p').textContent = 'Проверьте соединение с интернетом или повторите позже';
    }
  }

  function updateHeader() {
    loadingSpinner.classList.add('hidden');
    if (fullData.generated_at_str) {
      updateTimeEl.textContent = `Обновлено: ${fullData.generated_at_str}`;
    }
    if (badgeDouble) badgeDouble.textContent = fullData.double_deals?.length || 0;
    if (badgeCoupons) badgeCoupons.textContent = fullData.family_coupons?.length || 0;
    if (badgeStore) badgeStore.textContent = fullData.store_offers?.length || 0;
  }

  // Filtering Logic
  function getFilteredItems() {
    let list = [];
    if (currentTab === 'double') list = fullData.double_deals || [];
    else if (currentTab === 'coupons') list = fullData.family_coupons || [];
    else if (currentTab === 'store') list = fullData.store_offers || [];

    // Filter by member (only applicable to double deals & coupons)
    if (currentMember !== 'all') {
      if (currentTab === 'double' || currentTab === 'coupons') {
        list = list.filter(item => item.owners && item.owners.includes(currentMember));
      }
    }

    // Filter by search query
    if (searchQuery) {
      const q = searchQuery.toLowerCase().trim();
      list = list.filter(item => {
        const title = (item.title || '').toLowerCase();
        const sku = (item.sku || '').toLowerCase();
        const disc = (item.discount || item.store_discount || item.coupon_discount || '').toLowerCase();
        const pkg = (item.packaging || '').toLowerCase();
        return title.includes(q) || sku.includes(q) || disc.includes(q) || pkg.includes(q);
      });
    }

    return list;
  }

  // Render cards
  function renderCurrentList() {
    const items = getFilteredItems();
    cardsContainer.innerHTML = '';

    if (items.length === 0) {
      emptyState.classList.remove('hidden');
      return;
    }
    emptyState.classList.add('hidden');

    const fragment = document.createDocumentFragment();

    items.forEach(item => {
      const card = document.createElement('div');
      card.className = 'card';

      if (currentTab === 'double') {
        card.innerHTML = renderDoubleCard(item);
      } else if (currentTab === 'coupons') {
        card.innerHTML = renderCouponCard(item);
      } else {
        card.innerHTML = renderStoreCard(item);
      }

      fragment.appendChild(card);
    });

    cardsContainer.appendChild(fragment);

    // Attach copy sku listener
    document.querySelectorAll('.copy-sku').forEach(el => {
      el.addEventListener('click', (e) => {
        e.stopPropagation();
        const sku = el.dataset.sku;
        if (navigator.clipboard) {
          navigator.clipboard.writeText(sku).then(() => {
            haptic('success');
            showToast(`Артикул ${sku} скопирован`);
          });
        }
      });
    });
  }

  function renderOwners(owners) {
    if (!owners || !owners.length) return '';
    return `
      <div class="owner-pills">
        ${owners.map(name => `<span class="owner-pill owner-${name}">${name}</span>`).join('')}
      </div>
    `;
  }

  function renderDoubleCard(item) {
    const imgHtml = item.image_url 
      ? `<img src="${item.image_url}" class="card-img" loading="lazy" alt="${item.title}">`
      : `<span class="card-img-fallback">🔥</span>`;

    const skuHtml = item.sku 
      ? `<span class="card-sku copy-sku" data-sku="${item.sku}" title="Нажмите чтобы скопировать">Код: ${item.sku} 📋</span>` 
      : '';

    return `
      <div class="card-top">
        <div class="card-img-wrap">${imgHtml}</div>
        <div class="card-body">
          <div>
            <div class="card-title">${item.title}</div>
            ${skuHtml}
          </div>
          <div class="price-banner">
            <div>
              <span class="unit-price-highlight">${item.final_unit_price}</span>
              ${item.store_unit_price && item.store_unit_price !== '-' ? `<span style="font-size:11px; text-decoration:line-through; color:var(--hint-color); margin-left:4px;">${item.store_unit_price}</span>` : ''}
            </div>
            ${item.final_pack_price && item.final_pack_price !== '-' ? `<span class="pack-price-sub">${item.final_pack_price} / пачка</span>` : ''}
          </div>
        </div>
      </div>
      <div class="card-tags">
        ${item.store_discount ? `<span class="tag tag-store">🛒 ${item.store_discount}</span>` : ''}
        ${item.coupon_discount ? `<span class="tag tag-coupon">🎟 ${item.coupon_discount}</span>` : ''}
        ${item.packaging ? `<span class="tag" style="background:var(--bg-color); color:var(--hint-color);">${item.packaging}</span>` : ''}
        ${renderOwners(item.owners)}
      </div>
    `;
  }

  function renderCouponCard(item) {
    const imgHtml = item.image_url 
      ? `<img src="${item.image_url}" class="card-img" loading="lazy" alt="${item.title}">`
      : `<span class="card-img-fallback">🎟</span>`;

    const skuHtml = item.sku 
      ? `<span class="card-sku copy-sku" data-sku="${item.sku}">Код: ${item.sku} 📋</span>` 
      : '';

    return `
      <div class="card-top">
        <div class="card-img-wrap">${imgHtml}</div>
        <div class="card-body">
          <div>
            <div class="card-title">${item.title}</div>
            ${skuHtml}
          </div>
          ${item.unit_price ? `
            <div class="price-banner">
              <span class="unit-price-highlight">${item.unit_price}</span>
              <span class="pack-price-sub">при комбо-скидке</span>
            </div>
          ` : ''}
        </div>
      </div>
      <div class="card-tags">
        <span class="tag tag-coupon">🎟 ${item.discount}</span>
        ${item.is_shared ? `<span class="tag tag-shared">⭐ Совпадение (${item.owners.length})</span>` : ''}
        ${renderOwners(item.owners)}
      </div>
    `;
  }

  function renderStoreCard(item) {
    const imgHtml = item.image_url 
      ? `<img src="${item.image_url}" class="card-img" loading="lazy" alt="${item.title}">`
      : `<span class="card-img-fallback">🛒</span>`;

    const skuHtml = item.sku 
      ? `<span class="card-sku copy-sku" data-sku="${item.sku}">Код: ${item.sku} 📋</span>` 
      : '';

    return `
      <div class="card-top">
        <div class="card-img-wrap">${imgHtml}</div>
        <div class="card-body">
          <div>
            <div class="card-title">${item.title}</div>
            ${skuHtml}
          </div>
          <div class="price-banner">
            <span class="unit-price-highlight">${item.unit_price}</span>
            <span class="pack-price-sub">${item.pack_price}</span>
          </div>
        </div>
      </div>
      <div class="card-tags">
        ${item.discount ? `<span class="tag tag-store">${item.discount}</span>` : ''}
        ${item.packaging ? `<span class="tag" style="background:var(--bg-color); color:var(--hint-color);">${item.packaging}</span>` : ''}
      </div>
    `;
  }

  // Event Listeners: Navigation Tabs
  document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      haptic('selection');
      document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      currentTab = btn.dataset.tab;
      renderCurrentList();
      window.scrollTo({ top: 0, behavior: 'smooth' });
    });
  });

  // Event Listeners: Family Member Chips
  document.querySelectorAll('.chip').forEach(chip => {
    chip.addEventListener('click', () => {
      haptic('selection');
      document.querySelectorAll('.chip').forEach(c => c.classList.remove('active'));
      chip.classList.add('active');
      currentMember = chip.dataset.member;
      renderCurrentList();
    });
  });

  // Event Listeners: Search Input
  searchInput.addEventListener('input', (e) => {
    searchQuery = e.target.value;
    if (searchQuery) {
      clearBtn.classList.remove('hidden');
    } else {
      clearBtn.classList.add('hidden');
    }
    renderCurrentList();
  });

  clearBtn.addEventListener('click', () => {
    haptic('light');
    searchInput.value = '';
    searchQuery = '';
    clearBtn.classList.add('hidden');
    renderCurrentList();
  });

  refreshBtn.addEventListener('click', () => {
    haptic('medium');
    loadData();
    showToast('Каталог обновляется...');
  });

  // Scroll to Top
  window.addEventListener('scroll', () => {
    if (window.scrollY > 300) {
      scrollTopBtn.classList.remove('hidden');
    } else {
      scrollTopBtn.classList.add('hidden');
    }
  });

  scrollTopBtn.addEventListener('click', () => {
    haptic('light');
    window.scrollTo({ top: 0, behavior: 'smooth' });
  });

  // Init
  loadData();
})();
