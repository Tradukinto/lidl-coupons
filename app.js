// Telegram Mini App Controller
(function() {
  const tg = window.Telegram?.WebApp;
  if (tg) {
    tg.ready();
    tg.expand();
    // Enable closing confirmation if needed
    tg.enableClosingConfirmation?.();
  }

  const STORAGE_KEY = 'lidl_family_favorites_v2';

  let fullData = {
    double_deals: [],
    family_coupons: [],
    store_offers: [],
    monetary_coupons: []
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
  const badgeFavs = document.getElementById('badge-favs');
  const toastEl = document.getElementById('toast');
  const monetaryBanner = document.getElementById('monetary-banner');
  const monetaryTitle = document.getElementById('monetary-title');
  const monetarySub = document.getElementById('monetary-sub');
  const monetaryBadge = document.getElementById('monetary-badge');
  const chipSharedCount = document.getElementById('chip-shared-count');
  const favsToolbar = document.getElementById('favs-toolbar');
  const favsProgress = document.getElementById('favs-progress');
  const clearCheckedBtn = document.getElementById('clear-checked-btn');
  const clearAllFavsBtn = document.getElementById('clear-all-favs-btn');
  const familyChipsContainer = document.getElementById('family-chips-container');
  const familyChipsScroll = document.getElementById('family-chips-scroll');
  const chipsArrowLeft = document.getElementById('chips-arrow-left');
  const chipsArrowRight = document.getElementById('chips-arrow-right');

  // Update navigation arrows visibility based on scroll position
  function updateScrollArrows() {
    if (!familyChipsScroll) return;
    const maxScroll = familyChipsScroll.scrollWidth - familyChipsScroll.clientWidth;
    if (maxScroll <= 2) {
      chipsArrowLeft?.classList.add('hidden');
      chipsArrowRight?.classList.add('hidden');
      return;
    }
    if (familyChipsScroll.scrollLeft > 6) {
      chipsArrowLeft?.classList.remove('hidden');
    } else {
      chipsArrowLeft?.classList.add('hidden');
    }
    if (familyChipsScroll.scrollLeft < maxScroll - 6) {
      chipsArrowRight?.classList.remove('hidden');
    } else {
      chipsArrowRight?.classList.add('hidden');
    }
  }

  // Toggle family chips visibility (shown only when 'coupons' tab is active)
  function updateFamilyChipsVisibility() {
    if (!familyChipsContainer) return;
    if (currentTab === 'coupons') {
      familyChipsContainer.classList.remove('hidden');
      setTimeout(updateScrollArrows, 60);
    } else {
      familyChipsContainer.classList.add('hidden');
    }
  }

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

  // Favorites in LocalStorage
  function getFavorites() {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      return raw ? JSON.parse(raw) : [];
    } catch (e) {
      return [];
    }
  }

  function saveFavorites(favs) {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(favs));
    } catch (e) {
      console.error('Ошибка сохранения избранного:', e);
    }
    updateFavsBadge();
  }

  function isFavorite(id) {
    const favs = getFavorites();
    return favs.some(f => f.id === id);
  }

  function toggleFavorite(item) {
    const favs = getFavorites();
    const idx = favs.findIndex(f => f.id === item.id);
    if (idx >= 0) {
      favs.splice(idx, 1);
      saveFavorites(favs);
      haptic('light');
      showToast('Удалено из списка');
    } else {
      favs.unshift({
        ...item,
        checked: false,
        added_at: Date.now()
      });
      saveFavorites(favs);
      haptic('success');
      showToast('⭐ Добавлено в список покупок');
    }
    updateFavsBadge();
    if (currentTab === 'favs') {
      renderCurrentList();
    } else {
      updateStarButtonsState();
    }
  }

  function toggleCheckFavorite(id) {
    const favs = getFavorites();
    const item = favs.find(f => f.id === id);
    if (item) {
      item.checked = !item.checked;
      saveFavorites(favs);
      haptic('selection');
      renderCurrentList();
    }
  }

  function updateFavsBadge() {
    const favs = getFavorites();
    if (badgeFavs) {
      badgeFavs.textContent = favs.length;
    }
  }

  function updateStarButtonsState() {
    document.querySelectorAll('.star-btn').forEach(btn => {
      const id = btn.dataset.id;
      if (isFavorite(id)) {
        btn.classList.add('active');
        btn.textContent = '⭐';
      } else {
        btn.classList.remove('active');
        btn.textContent = '☆';
      }
    });
  }

  // Load data.json
  async function loadData(isUserClick = false) {
    if (refreshBtn) refreshBtn.classList.add('rotating');
    if (!isUserClick) {
      loadingSpinner.classList.remove('hidden');
      cardsContainer.innerHTML = '';
      emptyState.classList.add('hidden');
    }

    try {
      // Cache buster for fresh data
      const res = await fetch(`data.json?t=${Date.now()}`, { cache: 'no-store' });
      if (!res.ok) throw new Error('HTTP ' + res.status);
      fullData = await res.json();

      updateHeader();
      updateFamilyChipsVisibility();
      renderCurrentList();

      if (isUserClick) {
        showToast(`✓ Синхронизировано (${fullData.generated_at_str || 'сейчас'})`);
      }
    } catch (err) {
      console.error('Ошибка загрузки данных:', err);
      loadingSpinner.classList.add('hidden');
      emptyState.classList.remove('hidden');
      emptyState.querySelector('h3').textContent = 'Ошибка загрузки данных';
      emptyState.querySelector('p').textContent = 'Проверьте соединение с интернетом или повторите позже';
      showToast('Ошибка связи с сервером');
    } finally {
      if (refreshBtn) {
        setTimeout(() => refreshBtn.classList.remove('rotating'), 600);
      }
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
    updateFavsBadge();

    // Shared Count badge on chips
    const sharedCoupons = (fullData.family_coupons || []).filter(c => c.is_shared || (c.owners && c.owners.length >= 2));
    if (chipSharedCount) {
      chipSharedCount.textContent = sharedCoupons.length;
    }

    // Monetary Coupons Banner
    const monetaryList = fullData.monetary_coupons || [];
    if (monetaryList.length > 0 && monetaryBanner) {
      monetaryBanner.classList.remove('hidden');
      const first = monetaryList[0];
      const allOwners = Array.from(new Set(monetaryList.map(m => m.owner))).join(', ');
      monetaryTitle.textContent = `Скидка на чек: ${first.discount} (аккаунт ${allOwners})`;
      monetarySub.textContent = `Скидка снимется со всего чека при сканировании карты на кассе`;
      monetaryBadge.textContent = allOwners;
    } else if (monetaryBanner) {
      monetaryBanner.classList.add('hidden');
    }
  }

  // Generate unique item ID
  function getItemId(type, item) {
    const sku = item.sku || '';
    const title = item.title || '';
    const disc = item.discount || item.store_discount || item.coupon_discount || '';
    return `${type}_${sku}_${title}_${disc}`.replace(/\s+/g, '_');
  }

  // Filtering Logic
  function getFilteredItems() {
    if (currentTab === 'favs') {
      let favs = getFavorites();
      if (searchQuery) {
        const q = searchQuery.toLowerCase().trim();
        favs = favs.filter(item => {
          const title = (item.title || '').toLowerCase();
          const sku = (item.sku || '').toLowerCase();
          const disc = (item.discount || '').toLowerCase();
          return title.includes(q) || sku.includes(q) || disc.includes(q);
        });
      }
      return favs;
    }

    let list = [];
    if (currentTab === 'double') list = fullData.double_deals || [];
    else if (currentTab === 'coupons') list = fullData.family_coupons || [];
    else if (currentTab === 'store') list = fullData.store_offers || [];

    // Filter by member or shared: applies ONLY when 'coupons' tab is active
    if (currentTab === 'coupons') {
      if (currentMember === 'shared') {
        list = list.filter(item => (item.owners && item.owners.length >= 2) || item.is_shared);
      } else if (currentMember !== 'all') {
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

    // Handle Favorites Toolbar
    if (currentTab === 'favs') {
      if (favsToolbar) favsToolbar.classList.remove('hidden');
      const allFavs = getFavorites();
      const checkedCount = allFavs.filter(f => f.checked).length;
      if (favsProgress) {
        favsProgress.textContent = `Куплено: ${checkedCount} из ${allFavs.length}`;
      }
    } else {
      if (favsToolbar) favsToolbar.classList.add('hidden');
    }

    if (items.length === 0) {
      emptyState.classList.remove('hidden');
      if (currentTab === 'favs') {
        emptyState.querySelector('.empty-icon').textContent = '⭐';
        emptyState.querySelector('h3').textContent = 'Список покупок пуст';
        emptyState.querySelector('p').textContent = 'Нажимайте на звёздочку ☆ на карточках товаров, чтобы составить список перед походом в Lidl';
      } else {
        emptyState.querySelector('.empty-icon').textContent = '🔍';
        emptyState.querySelector('h3').textContent = 'Ничего не найдено';
        emptyState.querySelector('p').textContent = 'Попробуйте изменить запрос или выбрать фильтр «Все»';
      }
      return;
    }
    emptyState.classList.add('hidden');

    const fragment = document.createDocumentFragment();

    items.forEach(item => {
      const card = document.createElement('div');

      if (currentTab === 'favs') {
        card.className = `card ${item.checked ? 'checked-item' : ''}`;
        card.innerHTML = renderFavCard(item);
      } else if (currentTab === 'double') {
        card.className = 'card';
        card.innerHTML = renderDoubleCard(item);
      } else if (currentTab === 'coupons') {
        card.className = 'card';
        card.innerHTML = renderCouponCard(item);
      } else {
        card.className = 'card';
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

    // Attach listeners: Star buttons
    document.querySelectorAll('.star-btn').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        const id = btn.dataset.id;
        const type = btn.dataset.type;
        const item = findItemById(type, id);
        if (item) {
          toggleFavorite(item);
        }
      });
    });

    // Attach listeners: Checkbox in Favs tab
    document.querySelectorAll('.fav-check-btn').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        const id = btn.dataset.id;
        toggleCheckFavorite(id);
      });
    });
  }

  function findItemById(type, id) {
    if (type === 'favs') {
      return getFavorites().find(f => f.id === id);
    }
    let list = [];
    if (type === 'double') list = fullData.double_deals || [];
    else if (type === 'coupons') list = fullData.family_coupons || [];
    else if (type === 'store') list = fullData.store_offers || [];

    const found = list.find(it => getItemId(type, it) === id);
    if (!found) return null;

    return {
      id: id,
      type: type,
      title: found.title,
      sku: found.sku,
      discount: found.discount || `${found.store_discount || ''} + ${found.coupon_discount || ''}`.trim(),
      final_unit_price: found.final_unit_price || found.unit_price || '-',
      final_pack_price: found.final_pack_price || found.pack_price || '-',
      packaging: found.packaging || '',
      owners: found.owners || [],
      image_url: found.image_url || ''
    };
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
    const id = getItemId('double', item);
    const isFav = isFavorite(id);

    const imgHtml = item.image_url 
      ? `<img src="${item.image_url}" class="card-img" loading="lazy" alt="${item.title}">`
      : `<span class="card-img-fallback">🔥</span>`;

    const skuHtml = item.sku 
      ? `<span class="card-sku copy-sku" data-sku="${item.sku}" title="Нажмите чтобы скопировать">Код: ${item.sku} 📋</span>` 
      : '';

    const hasUnitPrice = item.final_unit_price && item.final_unit_price !== '-';
    const primaryPrice = hasUnitPrice ? item.final_unit_price : item.final_pack_price;

    return `
      <div class="card-top">
        <div class="card-img-wrap">${imgHtml}</div>
        <div class="card-body">
          <div>
            <div class="card-header-row">
              <div class="card-title">${item.title}</div>
              <button class="star-btn ${isFav ? 'active' : ''}" data-id="${id}" data-type="double" title="В список">${isFav ? '⭐' : '☆'}</button>
            </div>
            ${skuHtml}
          </div>
          <div class="price-banner">
            <div class="unit-price-row">
              <span class="unit-price-highlight">${primaryPrice}</span>
              ${item.store_unit_price && item.store_unit_price !== '-' ? `<span style="font-size:11px; text-decoration:line-through; color:var(--hint-color);">${item.store_unit_price}</span>` : ''}
            </div>
            ${hasUnitPrice && item.final_pack_price && item.final_pack_price !== '-' ? `<span class="pack-price-sub">${item.final_pack_price} / пачка</span>` : ''}
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
    const id = getItemId('coupons', item);
    const isFav = isFavorite(id);

    const imgHtml = item.image_url 
      ? `<img src="${item.image_url}" class="card-img" loading="lazy" alt="${item.title}">`
      : `<span class="card-img-fallback">🎟</span>`;

    const skuHtml = item.sku 
      ? `<span class="card-sku copy-sku" data-sku="${item.sku}">Код: ${item.sku} 📋</span>` 
      : '';

    const isMonetary = item.is_monetary || (item.discount && item.discount.includes('€') && !item.discount.includes('%'));

    return `
      <div class="card-top">
        <div class="card-img-wrap">${imgHtml}</div>
        <div class="card-body">
          <div>
            <div class="card-header-row">
              <div class="card-title">${item.title}</div>
              <button class="star-btn ${isFav ? 'active' : ''}" data-id="${id}" data-type="coupons" title="В список">${isFav ? '⭐' : '☆'}</button>
            </div>
            ${skuHtml}
          </div>
          ${item.unit_price ? `
            <div class="price-banner">
              <div class="unit-price-row">
                <span class="unit-price-highlight">${item.unit_price}</span>
              </div>
              <span class="pack-price-sub">при комбо-скидке</span>
            </div>
          ` : isMonetary ? `
            <div class="price-banner" style="background:linear-gradient(135deg, #fef3c7, #e0e7ff);">
              <div class="unit-price-row">
                <span class="unit-price-highlight" style="color:#b45309;">-${item.discount} со всего чека</span>
              </div>
              <span class="pack-price-sub">при сканировании на кассе</span>
            </div>
          ` : ''}
        </div>
      </div>
      <div class="card-tags">
        <span class="tag tag-coupon">${isMonetary ? '💶 На чек: ' : '🎟 '}${item.discount}</span>
        ${item.is_shared ? `<span class="tag tag-shared">⭐ Совпадение (${item.owners.length})</span>` : ''}
        ${renderOwners(item.owners)}
      </div>
    `;
  }

  function renderStoreCard(item) {
    const id = getItemId('store', item);
    const isFav = isFavorite(id);

    const imgHtml = item.image_url 
      ? `<img src="${item.image_url}" class="card-img" loading="lazy" alt="${item.title}">`
      : `<span class="card-img-fallback">🛒</span>`;

    const skuHtml = item.sku 
      ? `<span class="card-sku copy-sku" data-sku="${item.sku}">Код: ${item.sku} 📋</span>` 
      : '';

    const hasUnitPrice = item.unit_price && item.unit_price !== '-';
    const primaryPrice = hasUnitPrice ? item.unit_price : item.pack_price;

    return `
      <div class="card-top">
        <div class="card-img-wrap">${imgHtml}</div>
        <div class="card-body">
          <div>
            <div class="card-header-row">
              <div class="card-title">${item.title}</div>
              <button class="star-btn ${isFav ? 'active' : ''}" data-id="${id}" data-type="store" title="В список">${isFav ? '⭐' : '☆'}</button>
            </div>
            ${skuHtml}
          </div>
          <div class="price-banner">
            <div class="unit-price-row">
              <span class="unit-price-highlight">${primaryPrice}</span>
            </div>
            ${hasUnitPrice && item.pack_price && item.pack_price !== '-' ? `<span class="pack-price-sub">${item.pack_price} / пачка</span>` : ''}
          </div>
        </div>
      </div>
      <div class="card-tags">
        ${item.discount ? `<span class="tag tag-store">${item.discount}</span>` : ''}
        ${item.packaging ? `<span class="tag" style="background:var(--bg-color); color:var(--hint-color);">${item.packaging}</span>` : ''}
      </div>
    `;
  }

  function renderFavCard(item) {
    const imgHtml = item.image_url 
      ? `<img src="${item.image_url}" class="card-img" loading="lazy" alt="${item.title}">`
      : `<span class="card-img-fallback">⭐</span>`;

    const skuHtml = item.sku 
      ? `<span class="card-sku copy-sku" data-sku="${item.sku}">Код: ${item.sku} 📋</span>` 
      : '';

    const sourceTag = item.type === 'double' 
      ? `<span class="tag tag-store">🔥 Комбо</span>`
      : item.type === 'coupons'
      ? `<span class="tag tag-coupon">🎟 Купон</span>`
      : `<span class="tag tag-store">🛒 Daily Savers</span>`;

    return `
      <div class="fav-card-row">
        <button class="fav-check-btn ${item.checked ? 'checked' : ''}" data-id="${item.id}" title="Отметить купленным">✓</button>
        <div style="flex:1; min-width:0;">
          <div class="card-top">
            <div class="card-img-wrap">${imgHtml}</div>
            <div class="card-body">
              <div>
                <div class="card-header-row">
                  <div class="card-title">${item.title}</div>
                  <button class="star-btn active" data-id="${item.id}" data-type="favs" title="Удалить из списка">✕</button>
                </div>
                ${skuHtml}
              </div>
              <div class="price-banner">
                <div class="unit-price-row">
                  <span class="unit-price-highlight">${item.final_unit_price !== '-' ? item.final_unit_price : item.final_pack_price}</span>
                </div>
                ${item.final_unit_price !== '-' && item.final_pack_price && item.final_pack_price !== '-' ? `<span class="pack-price-sub">${item.final_pack_price} / пачка</span>` : ''}
              </div>
            </div>
          </div>
          <div class="card-tags" style="margin-top:8px;">
            ${sourceTag}
            ${item.discount ? `<span class="tag tag-coupon">${item.discount}</span>` : ''}
            ${renderOwners(item.owners)}
          </div>
        </div>
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
      updateFamilyChipsVisibility();
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

  // Family Chips Horizontal Scroll: Wheel, Drag, and Arrows
  if (familyChipsScroll) {
    familyChipsScroll.addEventListener('scroll', updateScrollArrows, { passive: true });

    // Mouse wheel: scroll horizontally on desktop
    familyChipsScroll.addEventListener('wheel', (e) => {
      if (e.deltaY !== 0) {
        e.preventDefault();
        familyChipsScroll.scrollLeft += e.deltaY;
        updateScrollArrows();
      }
    }, { passive: false });

    // Mouse drag-to-scroll on desktop
    let isDown = false;
    let startX = 0;
    let scrollStart = 0;
    let hasMoved = false;

    familyChipsScroll.addEventListener('mousedown', (e) => {
      isDown = true;
      hasMoved = false;
      familyChipsScroll.classList.add('grabbing');
      startX = e.pageX - familyChipsScroll.offsetLeft;
      scrollStart = familyChipsScroll.scrollLeft;
    });

    window.addEventListener('mouseup', () => {
      if (isDown) {
        isDown = false;
        familyChipsScroll.classList.remove('grabbing');
      }
    });

    window.addEventListener('mousemove', (e) => {
      if (!isDown) return;
      const x = e.pageX - familyChipsScroll.offsetLeft;
      const walk = (x - startX) * 1.5;
      if (Math.abs(walk) > 4) hasMoved = true;
      familyChipsScroll.scrollLeft = scrollStart - walk;
      updateScrollArrows();
    });

    // Prevent chip selection if the user was dragging
    document.querySelectorAll('.chip').forEach(chip => {
      chip.addEventListener('click', (e) => {
        if (hasMoved) {
          e.stopImmediatePropagation();
          hasMoved = false;
        }
      }, true);
    });
  }

  // Arrow buttons
  if (chipsArrowLeft && familyChipsScroll) {
    chipsArrowLeft.addEventListener('click', () => {
      haptic('light');
      familyChipsScroll.scrollBy({ left: -140, behavior: 'smooth' });
      setTimeout(updateScrollArrows, 200);
    });
  }

  if (chipsArrowRight && familyChipsScroll) {
    chipsArrowRight.addEventListener('click', () => {
      haptic('light');
      familyChipsScroll.scrollBy({ left: 140, behavior: 'smooth' });
      setTimeout(updateScrollArrows, 200);
    });
  }

  window.addEventListener('resize', updateScrollArrows);

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

  // Event Listener: Refresh Button
  refreshBtn.addEventListener('click', () => {
    haptic('medium');
    loadData(true);
  });

  // Event Listeners: Favorites Toolbar Actions
  if (clearCheckedBtn) {
    clearCheckedBtn.addEventListener('click', () => {
      const favs = getFavorites().filter(f => !f.checked);
      saveFavorites(favs);
      haptic('light');
      showToast('Купленные товары удалены');
      renderCurrentList();
    });
  }

  if (clearAllFavsBtn) {
    clearAllFavsBtn.addEventListener('click', () => {
      if (confirm('Очистить весь список покупок?')) {
        saveFavorites([]);
        haptic('medium');
        showToast('Список покупок очищен');
        renderCurrentList();
      }
    });
  }

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
