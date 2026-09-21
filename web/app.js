// Telegram Mini App Controller
(function() {
  const tg = window.Telegram?.WebApp;
  if (tg) {
    tg.ready();
    tg.expand();
    tg.enableClosingConfirmation?.();
  }

  const STORAGE_KEY = 'lidl_family_favorites_v2';

  let fullData = {
    double_deals: [],
    family_coupons: [],
    store_offers: [],
    monetary_coupons: [],
    super_savers: [],
    super_saver_doubles: []
  };

  let currentTab = 'double';
  let currentMember = 'all';
  let currentCategory = 'all';
  let currentSuperFilter = 'all';
  let searchQuery = '';
  let cachedUnifiedCategoryItems = null;

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
  const badgeSuper = document.getElementById('badge-super');
  const badgeStore = document.getElementById('badge-store');
  const badgeCategories = document.getElementById('badge-categories');
  const badgeFavs = document.getElementById('badge-favs');
  const badgeRadar = document.getElementById('badge-radar');
  const radarPanel = document.getElementById('radar-panel');
  const radarInput = document.getElementById('radar-input');
  const radarClearBtn = document.getElementById('radar-clear-btn');
  const radarAddBtn = document.getElementById('radar-add-btn');
  const radarDropdown = document.getElementById('radar-dropdown');
  const radarChipsList = document.getElementById('radar-chips-list');
  const radarTrackedCount = document.getElementById('radar-tracked-count');
  const radarClearAllBtn = document.getElementById('radar-clear-all-btn');
  const radarResetBtn = document.getElementById('radar-reset-btn');
  const radarQuickScroll = document.getElementById('radar-quick-scroll');

  const RADAR_STORAGE_KEY = 'lidl_radar_tracked_items_v1';
  let trackedItems = [];
  let activeRadarFilter = 'all';
  const superChipsContainer = document.getElementById('super-chips-container');
  const superCountAll = document.getElementById('super-count-all');
  const superCountCombos = document.getElementById('super-count-combos');
  const toastEl = document.getElementById('toast');
  const monetaryBanner = document.getElementById('monetary-banner');
  const monetaryTitle = document.getElementById('monetary-title');
  const monetarySub = document.getElementById('monetary-sub');
  const monetaryBadge = document.getElementById('monetary-badge');
  const monetaryDate = document.getElementById('monetary-date');
  const chipSharedCount = document.getElementById('chip-shared-count');
  const favsToolbar = document.getElementById('favs-toolbar');
  const favsProgress = document.getElementById('favs-progress');
  const clearCheckedBtn = document.getElementById('clear-checked-btn');
  const clearAllFavsBtn = document.getElementById('clear-all-favs-btn');
  const familyChipsContainer = document.getElementById('family-chips-container');
  const familyChipsScroll = document.getElementById('family-chips-scroll');
  const chipsArrowLeft = document.getElementById('chips-arrow-left');
  const chipsArrowRight = document.getElementById('chips-arrow-right');
  const categoryChipsContainer = document.getElementById('category-chips-container');
  const categoryChipsScroll = document.getElementById('category-chips-scroll');
  const catArrowLeft = document.getElementById('cat-arrow-left');
  const catArrowRight = document.getElementById('cat-arrow-right');

  // Update navigation arrows visibility for family chips
  function updateFamilyScrollArrows() {
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

  // Update navigation arrows visibility for category chips
  function updateCategoryScrollArrows() {
    if (!categoryChipsScroll) return;
    const maxScroll = categoryChipsScroll.scrollWidth - categoryChipsScroll.clientWidth;
    if (maxScroll <= 2) {
      catArrowLeft?.classList.add('hidden');
      catArrowRight?.classList.add('hidden');
      return;
    }
    if (categoryChipsScroll.scrollLeft > 6) {
      catArrowLeft?.classList.remove('hidden');
    } else {
      catArrowLeft?.classList.add('hidden');
    }
    if (categoryChipsScroll.scrollLeft < maxScroll - 6) {
      catArrowRight?.classList.remove('hidden');
    } else {
      catArrowRight?.classList.add('hidden');
    }
  }

  // Toggle secondary sub-row visibility (family chips vs category chips vs super chips)
  function updateSubRowsVisibility() {
    if (familyChipsContainer) {
      if (currentTab === 'coupons') {
        familyChipsContainer.classList.remove('hidden');
        setTimeout(updateFamilyScrollArrows, 60);
      } else {
        familyChipsContainer.classList.add('hidden');
      }
    }
    if (categoryChipsContainer) {
      if (currentTab === 'categories') {
        categoryChipsContainer.classList.remove('hidden');
        setTimeout(updateCategoryScrollArrows, 60);
      } else {
        categoryChipsContainer.classList.add('hidden');
      }
    }
    if (superChipsContainer) {
      if (currentTab === 'super') {
        superChipsContainer.classList.remove('hidden');
      } else {
        superChipsContainer.classList.add('hidden');
      }
    }
    if (radarPanel) {
      if (currentTab === 'radar') {
        radarPanel.classList.remove('hidden');
        renderRadarChips();
      } else {
        radarPanel.classList.add('hidden');
      }
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

  // Universal Product Key for cross-tab deduplication & favorites
  function normalizeTitle(t) {
    return (t || '').toLowerCase().replace(/[^a-z0-9]/g, '');
  }

  function getProductKey(item) {
    if (!item) return '';
    if (item.sku) return `sku_${item.sku}`;
    return `title_${normalizeTitle(item.title)}`;
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

  function isFavorite(item) {
    if (!item) return false;
    const key = typeof item === 'string' ? item : getProductKey(item);
    const sku = typeof item === 'object' ? item.sku : null;
    const title = typeof item === 'object' ? item.title : null;
    const favs = getFavorites();
    return favs.some(f => {
      if (f.key && f.key === key) return true;
      if (f.id && f.id === key) return true;
      if (sku && f.sku && f.sku === sku) return true;
      if (title && f.title && normalizeTitle(f.title) === normalizeTitle(title)) return true;
      return false;
    });
  }

  function toggleFavorite(item) {
    const favs = getFavorites();
    const key = getProductKey(item);
    const sku = item.sku;
    const title = item.title;

    const idx = favs.findIndex(f => {
      if (f.key && f.key === key) return true;
      if (f.id && f.id === key) return true;
      if (sku && f.sku && f.sku === sku) return true;
      if (title && f.title && normalizeTitle(f.title) === normalizeTitle(title)) return true;
      return false;
    });

    if (idx >= 0) {
      favs.splice(idx, 1);
      saveFavorites(favs);
      haptic('light');
      showToast('Удалено из списка');
    } else {
      favs.unshift({
        id: key,
        key: key,
        type: item.type || currentTab,
        title: item.title,
        sku: item.sku || '',
        discount: item.discount || item.super_discount || `${item.store_discount || ''} + ${item.coupon_discount || ''}`.trim(),
        final_unit_price: item.final_unit_price || item.unit_price || '-',
        final_pack_price: item.final_pack_price || item.final_price || item.pack_price || item.price || '-',
        packaging: item.packaging || '',
        formatted_date: item.formatted_date || '',
        owners: item.owners || [],
        image_url: item.image_url || '',
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
    const item = favs.find(f => f.id === id || f.key === id);
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
      const key = btn.dataset.key;
      const sku = btn.dataset.sku;
      const title = btn.dataset.title;
      const active = isFavorite({ sku: sku, title: title, key: key });
      if (active) {
        btn.classList.add('active');
        btn.textContent = '⭐';
        btn.title = 'Удалить из списка';
      } else {
        btn.classList.remove('active');
        btn.textContent = '☆';
        btn.title = 'В список покупок';
      }
    });
  }

  // Category Classifier
  function detectCategory(item) {
    const text = ((item.title || '') + ' ' + (item.packaging || '') + ' ' + (item.description || '')).toLowerCase();

    // Non-food
    if (/\b(w5|dettol|bellosan|whiskas|purina|tronic|parkside|esmara|crivit|livergy|lupilu|battery|batteries|towel|towels|paper|toilet|wipes|tissue|tissues|cleaner|detergent|bleach|shampoo|soap|gel|sponge|sponges|foil|wrap|bag|bags|pants|shorts|socks|shirt|jacket|shoes|pyjamas?|pajamas?|t-shirt|boxer|briefs|leggings|drill|screw|pliers|wrench|tool|tools|socket|meter|laser|pet food|cat food|dog food|dishwash|laundry)\b/i.test(text)) {
      return 'non_food';
    }

    // Beverages (evaluated before fruits/tea so fruit juices and lemon tea go to beverages)
    if (/\b(juice|drink|drinks|water|mineral|sparkling|tea|iced tea|coffee|espresso|cappuccino|latte|bellarom|nescafe|cola|soda|freeway|nectar|wine|beer|allini|perlenbacher|smoothie|syrup)\b/i.test(text)) {
      return 'beverages';
    }

    // Sweets & Snacks (evaluated before fruits for fruit chocolate/candies)
    if (/\b(chocolate|biscuit|biscuits|cookie|cookies|wafer|wafers|nutella|kinder|cadbury|sondey|cake|candy|candies|gummy|popcorn|chips|crisps|snack|snacks|bar|bars|almond|almonds|peanut|peanuts|hazelnut|hazelnuts|cashew|cashews|pistachio|pistachios|walnut|walnuts|\bnuts?\b|jam|marmalade|halva|donut|donuts|dessert|ice cream|pralines?|nougat|brezel|brezels|pretzel|pretzels)\b/i.test(text)) {
      return 'sweets_snacks';
    }

    // Dairy & Cheese
    if (/\b(cheese|gouda|edam|cheddar|emmental|mozzarella|parmesan|feta|halloumi|anari|milk|milbona|yogurt|yoghurt|mousse|protein|alambra|butter|cream|kefir|cottage|quark|curd|dairy|\beggs?\b)\b/i.test(text)) {
      return 'dairy_cheese';
    }

    // Bakery & Grocery (evaluated before dairy for brioche with milk/butter etc.)
    if (/\b(bread|baguette|baquette|baguettes?|baquettes?|toast|roll|bun|buns|croissant|croissants|brioche|pita|tortilla|tortillas|pasta|linguine|spaghetti|noodles|penne|macaroni|flour|oats|oatmeal|flakes|muesli|cereal|weetabix|rice|beans|lentils|chickpeas|sauce|ketchup|mayo|mayonnaise|mustard|tomato paste|olive oil|oil|sunflower oil|vinegar|spices|salt|sugar|yeast|baking|pizza|crispbread|crackers?)\b/i.test(text)) {
      return 'bakery_grocery';
    }

    // Meat & Fish
    if (/\b(chicken|turkey|beef|pork|bacon|ham|sausage|sausages|salami|cabanossi|ribs|burger|burgers|steak|mince|minced|agrikia|dulano|meat|poultry|fish|salmon|tuna|shrimp|prawns|seafood|fish fingers|fillet|pate|nuggets?)\b/i.test(text)) {
      return 'meat_fish';
    }

    // Vegetables & Fruits
    if (/\b(banana|bananas|apple|apples|avocado|avocados|pear|pears|grape|grapes|orange|oranges|lemon|lemons|lime|limes|kiwi|kiwis|peach|peaches|nectarine|nectarines|plum|plums|berry|berries|strawberry|strawberries|tomato|tomatoes|pepper|peppers|potato|potatoes|onion|onions|garlic|cucumber|cucumbers|salad|lettuce|cabbage|carrot|carrots|broccoli|cauliflower|zucchini|eggplant|aubergine|mushroom|mushrooms|fruit|fruits|vegetable|vegetables|grapefruit|grapefruits)\b/i.test(text)) {
      return 'veg_fruit';
    }

    return 'non_food';
  }

  // Unified Deduplicated Catalog for Categories Tab
  function getUnifiedCategoryItems() {
    if (cachedUnifiedCategoryItems) return cachedUnifiedCategoryItems;

    const seenKeys = new Set();
    const list = [];

    // 1. Double deals (highest priority: store discount + coupon combo)
    (fullData.double_deals || []).forEach(d => {
      const k = getProductKey(d);
      if (!seenKeys.has(k)) {
        seenKeys.add(k);
        list.push({ ...d, type: 'double' });
      }
    });

    // 2. Family coupons (excluding monetary cart coupons)
    (fullData.family_coupons || []).forEach(c => {
      if (c.is_monetary) return;
      const k = getProductKey(c);
      if (!seenKeys.has(k)) {
        seenKeys.add(k);
        list.push({ ...c, type: 'coupons' });
      }
    });

    // 3. Store offers (Daily Savers)
    (fullData.store_offers || []).forEach(s => {
      const k = getProductKey(s);
      if (!seenKeys.has(k)) {
        seenKeys.add(k);
        list.push({ ...s, type: 'store' });
      }
    });

    // 4. Super Savers
    (fullData.super_savers || []).forEach(ss => {
      const k = getProductKey(ss);
      if (!seenKeys.has(k)) {
        seenKeys.add(k);
        list.push({ ...ss, type: 'super' });
      }
    });

    cachedUnifiedCategoryItems = list;
    return list;
  }

  // ==========================================================================
  // Radar (Радар нужных акций) Controller
  // ==========================================================================

  function getBuiltinTrackedItems() {
    return [
      {
        id: "yogurt",
        name: "Йогурт",
        icon: "🥛",
        category: "dairy_cheese",
        keywords: ["yogurt", "yoghurt", "γιαουρτι", "γιαούρτι", "skyr", "йогурт"]
      },
      {
        id: "salmon",
        name: "Лосось / Форель",
        icon: "🐟",
        category: "meat_fish",
        keywords: ["salmon", "trout", "σολομος", "σολομός", "σολομού", "πέστροφα", "лосось", "семга", "форель"]
      },
      {
        id: "cheese",
        name: "Сыр / Фета / Халуми",
        icon: "🧀",
        category: "dairy_cheese",
        keywords: ["cheese", "feta", "halloumi", "gouda", "edam", "mozzarella", "cheddar", "τυρι", "τυρί", "φέτα", "χαλούμι", "сыр"]
      },
      {
        id: "butter",
        name: "Сливочное масло",
        icon: "🧈",
        category: "dairy_cheese",
        keywords: ["butter", "βουτυρο", "βούτυρο", "сливочное масло"]
      },
      {
        id: "avocado",
        name: "Авокадо",
        icon: "🥑",
        category: "veg_fruit",
        keywords: ["avocado", "αβοκαντο", "αβοκάντο", "авокадо"]
      },
      {
        id: "coffee",
        name: "Кофе",
        icon: "☕",
        category: "beverages",
        keywords: ["coffee", "espresso", "καφες", "καφές", "кофе"]
      },
      {
        id: "chicken",
        name: "Курица / Птица",
        icon: "🍗",
        category: "meat_fish",
        keywords: ["chicken", "κοτοπουλο", "κοτόπουλο", "курица", "цыпленок"]
      },
      {
        id: "olive_oil",
        name: "Оливковое масло",
        icon: "🫒",
        category: "bakery_grocery",
        keywords: ["olive oil", "ελαιολαδο", "ελαιόλαδο", "оливковое масло"]
      },
      {
        id: "nuts",
        name: "Орехи",
        icon: "🥜",
        category: "sweets_snacks",
        keywords: ["nuts", "almond", "walnut", "cashew", "ξηρων καρπων", "орехи"]
      },
      {
        id: "chocolate",
        name: "Шоколад",
        icon: "🍫",
        category: "sweets_snacks",
        keywords: ["chocolate", "σοκολατα", "σοκολάτα", "шоколад"]
      },
      {
        id: "parkside",
        name: "Parkside / Инструменты",
        icon: "🔧",
        category: "non_food",
        keywords: ["parkside", "инструмент", "парксайд"]
      }
    ];
  }

  function getThesaurus() {
    return fullData.thesaurus || {
      "йогурт": { name: "Йогурт", icon: "🥛", synonyms: ["yogurt", "yoghurt", "γιαουρτι", "skyr", "йогурт"] },
      "лосось": { name: "Лосось / Форель", icon: "🐟", synonyms: ["salmon", "trout", "σολομος", "πέστροφα", "лосось", "семга", "форель"] },
      "сыр": { name: "Сыр / Фета / Халуми", icon: "🧀", synonyms: ["cheese", "feta", "halloumi", "gouda", "edam", "mozzarella", "cheddar", "τυρι", "φέτα", "χαλούμι", "сыр"] },
      "сливочное масло": { name: "Сливочное масло", icon: "🧈", synonyms: ["butter", "βουτυρο", "сливочное масло"] },
      "авокадо": { name: "Авокадо", icon: "🥑", synonyms: ["avocado", "αβοκαντο", "авокадо"] },
      "кофе": { name: "Кофе", icon: "☕", synonyms: ["coffee", "espresso", "καφες", "кофе"] },
      "курица": { name: "Курица / Птица", icon: "🍗", synonyms: ["chicken", "κοτοπουλο", "курица", "цыпленок"] },
      "оливковое масло": { name: "Оливковое масло", icon: "🫒", synonyms: ["olive oil", "ελαιολαδο", "оливковое масло"] },
      "орехи": { name: "Орехи", icon: "🥜", synonyms: ["nuts", "almond", "walnut", "cashew", "ξηρων καρπων", "орехи"] },
      "шоколад": { name: "Шоколад", icon: "🍫", synonyms: ["chocolate", "σοκολατα", "шоколад"] },
      "мороженое": { name: "Мороженое", icon: "🍨", synonyms: ["ice cream", "παγωτο", "gelatelli", "bon gelati", "мороженое"] },
      "бананы": { name: "Бананы", icon: "🍌", synonyms: ["banana", "bananas", "μπανανες", "банан"] },
      "яблоки": { name: "Яблоки", icon: "🍎", synonyms: ["apple", "apples", "μηλα", "яблок"] },
      "помидоры": { name: "Помидоры", icon: "🍅", synonyms: ["tomato", "tomatoes", "ντοματες", "томат", "помидор"] },
      "огурцы": { name: "Огурцы", icon: "🥒", synonyms: ["cucumber", "cucumbers", "αγγουρια", "огур"] },
      "яйца": { name: "Яйца", icon: "🥚", synonyms: ["eggs", "αυγα", "яйц"] },
      "креветки": { name: "Креветки / Морепродукты", icon: "🍤", synonyms: ["shrimp", "shrimps", "prawn", "seafood", "γαριδες", "креветк"] },
      "говядина": { name: "Говядина / Бургеры", icon: "🥩", synonyms: ["beef", "burger", "μοσχαρι", "говядин"] },
      "свинина": { name: "Свинина / Бекон", icon: "🥩", synonyms: ["pork", "bacon", "χοιρινο", "свинин", "бекон"] },
      "колбаса": { name: "Колбаса / Сосиски", icon: "🌭", synonyms: ["sausage", "salami", "ham", "λουκανικα", "колбас", "сосиск"] },
      "макароны": { name: "Макароны / Паста", icon: "🍝", synonyms: ["pasta", "spaghetti", "combino", "макарон", "паста"] },
      "хлеб": { name: "Хлеб / Выпечка", icon: "🍞", synonyms: ["bread", "toast", "ψωμι", "хлеб"] },
      "чай": { name: "Чай", icon: "🫖", synonyms: ["tea", "lord nelson", "τσαϊ", "чай"] },
      "сок": { name: "Сок", icon: "🧃", synonyms: ["juice", "eviva", "solevita", "χυμος", "сок"] },
      "пиво": { name: "Пиво", icon: "🍺", synonyms: ["beer", "perlenbacher", "μπυρα", "пиво"] },
      "вино": { name: "Вино", icon: "🍷", synonyms: ["wine", "allini", "κρασι", "вино"] },
      "пицца": { name: "Пицца", icon: "🍕", synonyms: ["pizza", "πιτσα", "пицца"] },
      "parkside": { name: "Parkside / Инструменты", icon: "🔧", synonyms: ["parkside", "инструмент", "парксайд"] },
      "бытовая химия": { name: "W5 / Бытовая химия", icon: "🧺", synonyms: ["w5", "detergent", "laundry", "cleaner", "порошок", "стирк"] }
    };
  }

  function getTrackedItems() {
    try {
      const raw = localStorage.getItem(RADAR_STORAGE_KEY);
      if (raw !== null) {
        const parsed = JSON.parse(raw);
        if (Array.isArray(parsed)) return parsed;
      }
    } catch (e) {}

    if (fullData.tracked_items && Array.isArray(fullData.tracked_items) && fullData.tracked_items.length > 0) {
      return JSON.parse(JSON.stringify(fullData.tracked_items));
    }
    return getBuiltinTrackedItems();
  }

  function saveTrackedItems(items) {
    try {
      localStorage.setItem(RADAR_STORAGE_KEY, JSON.stringify(items));
    } catch (e) {}
    trackedItems = items;
    renderRadarChips();
    updateHeader();
  }

  function normalizeRadarText(text) {
    if (!text) return '';
    return text.toLowerCase()
      .replace(/[άέήίόύώϊΐϋΰ]/g, m => ({'ά':'α','έ':'ε','ή':'η','ί':'ι','ό':'ο','ύ':'υ','ώ':'ω','ϊ':'ι','ΐ':'ι','ϋ':'υ','ΰ':'υ'}[m] || m))
      .replace(/ё/g, 'е')
      .replace(/\s+/g, ' ')
      .trim();
  }

  function matchItemKeywords(item, keywords) {
    const text = normalizeRadarText(`${item.title || ''} ${item.packaging || ''} ${item.description || ''}`);
    for (const kw of keywords) {
      const nkw = normalizeRadarText(kw);
      if (!nkw) continue;
      if (nkw.length <= 4) {
        const reg = new RegExp(`(^|\\b|_)${nkw.replace(/[.*+?^${}()|[\\]\\]/g, '\\$&')}($|\\b|_)`, 'i');
        if (reg.test(text)) return kw;
      } else {
        if (text.includes(nkw)) return kw;
      }
    }
    return null;
  }

  function getRadarMatches() {
    const items = getTrackedItems();
    if (items.length === 0) return [];
    const matches = [];
    const seen = new Set();

    const sections = [
      { type: 'double', label: '🔥 Комбо', list: fullData.double_deals || [] },
      { type: 'super', label: '⚡ Super', list: fullData.super_savers || [] },
      { type: 'coupons', label: '🎟 Купон', list: fullData.family_coupons || [] },
      { type: 'store', label: '🛒 Daily', list: fullData.store_offers || [] }
    ];

    items.forEach(def => {
      sections.forEach(sec => {
        sec.list.forEach(deal => {
          const matchedKw = matchItemKeywords(deal, def.keywords || [def.name]);
          if (matchedKw) {
            const key = `${def.id}_${sec.type}_${deal.sku || deal.title}`;
            if (seen.has(key)) return;
            seen.add(key);
            matches.push({
              ...deal,
              type: sec.type,
              tracked_item_id: def.id,
              tracked_item_name: def.name,
              tracked_item_icon: def.icon || '🎯',
              matched_keyword: matchedKw
            });
          }
        });
      });
    });

    const prio = { double: 1, super: 2, coupons: 3, store: 4 };
    matches.sort((a, b) => (prio[a.type] || 9) - (prio[b.type] || 9));
    return matches;
  }

  function renderRadarChips() {
    if (!radarChipsList) return;
    const items = getTrackedItems();
    trackedItems = items;

    if (radarTrackedCount) {
      radarTrackedCount.textContent = items.length;
    }

    if (items.length === 0) {
      radarChipsList.innerHTML = `<span style="font-size:12px; color:var(--hint-color); padding:4px 0;">Список пуст. Введите товар в строке выше или выберите быструю подсказку 👆</span>`;
      return;
    }

    const allMatches = getRadarMatches();
    const matchCounts = {};
    allMatches.forEach(m => {
      matchCounts[m.tracked_item_id] = (matchCounts[m.tracked_item_id] || 0) + 1;
    });

    let html = `
      <button class="radar-chip ${activeRadarFilter === 'all' ? 'active' : ''}" data-id="all">
        <span>👥 Все</span>
        <span class="radar-chip-count">${allMatches.length}</span>
      </button>
    `;

    items.forEach(it => {
      const count = matchCounts[it.id] || 0;
      const isActive = activeRadarFilter === it.id;
      html += `
        <div class="radar-chip ${isActive ? 'active' : ''}" data-id="${it.id}">
          <span>${it.icon || '🎯'} ${it.name}</span>
          <span class="radar-chip-count">${count}</span>
          <button class="radar-chip-del" data-del-id="${it.id}" title="Удалить из радара">✕</button>
        </div>
      `;
    });

    radarChipsList.innerHTML = html;

    // Attach chip clicks
    radarChipsList.querySelectorAll('.radar-chip').forEach(chip => {
      chip.addEventListener('click', (e) => {
        if (e.target.classList.contains('radar-chip-del')) return;
        haptic('selection');
        activeRadarFilter = chip.dataset.id;
        renderRadarChips();
        renderCurrentList();
      });
    });

    // Attach delete clicks
    radarChipsList.querySelectorAll('.radar-chip-del').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        const id = btn.dataset.delId;
        deleteTrackedItem(id);
      });
    });
  }

  function addTrackedItem(query) {
    const q = (query || '').trim();
    if (!q) return;

    const nq = normalizeRadarText(q);
    const thes = getThesaurus();
    let itemDef = null;

    // Check thesaurus match
    for (const [key, info] of Object.entries(thes)) {
      if (normalizeRadarText(key) === nq || nq.includes(normalizeRadarText(key)) || normalizeRadarText(key).includes(nq)) {
        itemDef = {
          id: key.replace(/[^a-zA-Z0-9а-яА-ЯёЁ_]/g, '_'),
          name: info.name,
          icon: info.icon || '🎯',
          category: info.category || 'custom',
          keywords: info.synonyms || [key]
        };
        break;
      }
    }

    if (!itemDef) {
      itemDef = {
        id: nq.replace(/[^a-zA-Z0-9а-яА-ЯёЁ_]/g, '_') || 'custom',
        name: q.charAt(0).toUpperCase() + q.slice(1),
        icon: '🎯',
        category: 'custom',
        keywords: [nq]
      };
    }

    const items = trackedItems.length ? trackedItems : getTrackedItems();
    const exists = items.some(it => it.id === itemDef.id || it.name.toLowerCase() === itemDef.name.toLowerCase());
    if (exists) {
      activeRadarFilter = itemDef.id;
      renderRadarChips();
      renderCurrentList();
      showToast(`Товар ${itemDef.name} уже есть в радаре`);
      if (radarInput) radarInput.value = '';
      if (radarClearBtn) radarClearBtn.classList.add('hidden');
      if (radarDropdown) radarDropdown.classList.add('hidden');
      return;
    }

    items.push(itemDef);
    saveTrackedItems(items);
    activeRadarFilter = itemDef.id;
    renderRadarChips();
    renderCurrentList();
    haptic('success');
    showToast(`✅ Добавлено в радар: ${itemDef.name}`);

    if (radarInput) radarInput.value = '';
    if (radarClearBtn) radarClearBtn.classList.add('hidden');
    if (radarDropdown) radarDropdown.classList.add('hidden');
  }

  function deleteTrackedItem(id) {
    const cur = getTrackedItems();
    const items = cur.filter(it => it.id !== id);
    if (activeRadarFilter === id) {
      activeRadarFilter = 'all';
    }
    saveTrackedItems(items);
    renderRadarChips();
    renderCurrentList();
    haptic('light');
    showToast('🗑 Товар удален из радара');
  }

  function clearAllTrackedItems() {
    if (confirm('Очистить весь список отслеживания? Все товары будут удалены.')) {
      activeRadarFilter = 'all';
      saveTrackedItems([]);
      renderRadarChips();
      renderCurrentList();
      haptic('medium');
      showToast('Список отслеживания очищен');
    }
  }

  function resetTrackedItems() {
    if (confirm('Восстановить примеры популярных товаров семьи (йогурт, сыр, лосось и др.)?')) {
      const examples = (fullData.tracked_items && fullData.tracked_items.length > 0) 
        ? JSON.parse(JSON.stringify(fullData.tracked_items)) 
        : getBuiltinTrackedItems();
      activeRadarFilter = 'all';
      saveTrackedItems(examples);
      renderRadarChips();
      renderCurrentList();
      haptic('medium');
      showToast('Примеры товаров добавлены');
    }
  }

  function renderRadarCard(item) {
    let baseHtml = '';
    if (item.type === 'double') baseHtml = renderDoubleCard(item);
    else if (item.type === 'coupons') baseHtml = renderCouponCard(item);
    else if (item.type === 'super') baseHtml = renderSuperCard(item);
    else baseHtml = renderStoreCard(item);

    const radarBadge = `<span class="tag tag-radar-keyword">🎯 ${item.tracked_item_icon || '🎯'} ${item.tracked_item_name} (#${item.matched_keyword})</span>`;
    return baseHtml.replace('<div class="card-tags">', `<div class="card-tags">${radarBadge}`);
  }

  function setupRadarAutocomplete() {
    if (!radarInput || !radarDropdown) return;

    radarInput.addEventListener('input', (e) => {
      const q = e.target.value.trim();
      if (!q) {
        radarDropdown.classList.add('hidden');
        if (radarClearBtn) radarClearBtn.classList.add('hidden');
        return;
      }
      if (radarClearBtn) radarClearBtn.classList.remove('hidden');

      const nq = normalizeRadarText(q);
      const thes = getThesaurus();
      const suggestions = [];
      const seenNames = new Set();

      // 1. Search in Thesaurus
      for (const [key, info] of Object.entries(thes)) {
        const nkey = normalizeRadarText(key);
        const matchSynonym = (info.synonyms || []).some(s => normalizeRadarText(s).includes(nq));
        if (nkey.includes(nq) || matchSynonym) {
          if (!seenNames.has(info.name)) {
            seenNames.add(info.name);
            suggestions.push({
              id: key,
              name: info.name,
              icon: info.icon || '🎯',
              query: key,
              sub: (info.synonyms || []).slice(0, 3).join(', ')
            });
          }
        }
      }

      // 2. Search catalog product titles
      const allDeals = [
        ...(fullData.double_deals || []),
        ...(fullData.family_coupons || []),
        ...(fullData.super_savers || []),
        ...(fullData.store_offers || [])
      ];

      for (const d of allDeals) {
        const title = d.title || '';
        const nTitle = normalizeRadarText(title);
        if (nTitle.includes(nq) && !seenNames.has(title)) {
          seenNames.add(title);
          suggestions.push({
            id: 'catalog_' + (d.sku || title),
            name: title,
            icon: '🛒',
            query: title,
            sub: d.discount ? `Скидка ${d.discount}` : (d.final_pack_price || d.price || '')
          });
          if (suggestions.length >= 8) break;
        }
      }

      if (suggestions.length === 0) {
        suggestions.push({
          id: 'custom_' + nq,
          name: q,
          icon: '🎯',
          query: q,
          sub: 'Добавить собственный поисковый запрос'
        });
      }

      // Check current deal status for each suggestion
      const allMatches = getRadarMatches();
      let html = '';
      suggestions.slice(0, 7).forEach(s => {
        const count = allMatches.filter(m => {
          return matchItemKeywords(m, [s.query, s.name]);
        }).length;

        const badgeHtml = count > 0 
          ? `<span class="radar-item-badge radar-badge-active">🔥 ${count} ${count === 1 ? 'акция' : count < 5 ? 'акции' : 'акций'}</span>`
          : `<span class="radar-item-badge radar-badge-waiting">⏳ Ожидаем</span>`;

        html += `
          <div class="radar-dropdown-item" data-query="${s.query}">
            <div class="radar-item-left">
              <span class="radar-item-icon">${s.icon}</span>
              <div class="radar-item-texts">
                <span class="radar-item-title">${s.name}</span>
                <span class="radar-item-sub">${s.sub || ''}</span>
              </div>
            </div>
            ${badgeHtml}
          </div>
        `;
      });

      radarDropdown.innerHTML = html;
      radarDropdown.classList.remove('hidden');

      radarDropdown.querySelectorAll('.radar-dropdown-item').forEach(item => {
        item.addEventListener('click', () => {
          const query = item.dataset.query;
          addTrackedItem(query);
        });
      });
    });

    radarInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') {
        e.preventDefault();
        const q = radarInput.value.trim();
        if (q) {
          addTrackedItem(q);
        }
      } else if (e.key === 'Escape') {
        radarDropdown.classList.add('hidden');
      }
    });

    if (radarClearBtn) {
      radarClearBtn.addEventListener('click', () => {
        radarInput.value = '';
        radarClearBtn.classList.add('hidden');
        radarDropdown.classList.add('hidden');
      });
    }

    if (radarAddBtn) {
      radarAddBtn.addEventListener('click', () => {
        const q = radarInput.value.trim();
        if (q) {
          addTrackedItem(q);
        }
      });
    }

    if (radarClearAllBtn) {
      radarClearAllBtn.addEventListener('click', clearAllTrackedItems);
    }

    if (radarResetBtn) {
      radarResetBtn.addEventListener('click', resetTrackedItems);
    }

    document.addEventListener('click', (e) => {
      if (!radarInput.contains(e.target) && !radarDropdown.contains(e.target)) {
        radarDropdown.classList.add('hidden');
      }
    });

    document.querySelectorAll('.radar-quick-chip').forEach(btn => {
      btn.addEventListener('click', () => {
        const query = btn.dataset.query;
        addTrackedItem(query);
      });
    });
  }

  let lastCheckedTime = null;

  function formatBaseTime(isoStr, fallbackStr) {
    if (isoStr) {
      try {
        const d = new Date(isoStr);
        if (!isNaN(d.getTime())) {
          const now = new Date();
          const isToday = d.toDateString() === now.toDateString();
          const timeStr = d.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' });
          if (isToday) {
            return `Сегодня в ${timeStr}`;
          }
          const dateStr = d.toLocaleDateString('ru-RU', { day: '2-digit', month: '2-digit' });
          return `${dateStr} в ${timeStr}`;
        }
      } catch (e) {}
    }
    return fallbackStr || '';
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
      cachedUnifiedCategoryItems = null;

      if (isUserClick) {
        lastCheckedTime = new Date().toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' });
      }

      updateHeader();
      updateSubRowsVisibility();
      renderCurrentList();

      if (isUserClick) {
        const baseTime = formatBaseTime(fullData.generated_at, fullData.generated_at_str) || 'актуально';
        showToast(`✓ База проверена в ${lastCheckedTime} (каталог: ${baseTime})`);
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
    const baseTime = formatBaseTime(fullData.generated_at, fullData.generated_at_str);
    if (baseTime) {
      if (lastCheckedTime) {
        updateTimeEl.textContent = `Каталог: ${baseTime} • Проверено: ${lastCheckedTime}`;
      } else {
        updateTimeEl.textContent = `Каталог: ${baseTime}`;
      }
    }
    if (badgeDouble) badgeDouble.textContent = fullData.double_deals?.length || 0;
    if (badgeCoupons) badgeCoupons.textContent = fullData.family_coupons?.length || 0;
    if (badgeSuper) badgeSuper.textContent = fullData.super_savers?.length || 0;
    if (badgeStore) badgeStore.textContent = fullData.store_offers?.length || 0;
    if (superCountAll) superCountAll.textContent = fullData.super_savers?.length || 0;
    if (superCountCombos) superCountCombos.textContent = fullData.super_saver_doubles?.length || 0;

    // Radar matches count & badge
    const rMatches = getRadarMatches();
    if (badgeRadar) badgeRadar.textContent = rMatches.length;

    // Category count & badge
    const unified = getUnifiedCategoryItems();
    if (badgeCategories) badgeCategories.textContent = unified.length;

    // Category counts on chips
    const catCounts = {
      all: unified.length,
      veg_fruit: 0,
      sweets_snacks: 0,
      meat_fish: 0,
      dairy_cheese: 0,
      bakery_grocery: 0,
      beverages: 0,
      non_food: 0
    };
    unified.forEach(item => {
      const cat = detectCategory(item);
      if (catCounts[cat] !== undefined) {
        catCounts[cat]++;
      }
    });

    for (const [catKey, count] of Object.entries(catCounts)) {
      const el = document.getElementById(`cat-count-${catKey}`);
      if (el) el.textContent = count;
    }

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
      monetaryTitle.textContent = `Скидка ${first.discount} на весь чек`;
      if (monetaryDate) {
        if (first.validity_str) {
          monetaryDate.textContent = first.validity_str;
          monetaryDate.classList.remove('hidden');
        } else {
          monetaryDate.classList.add('hidden');
        }
      }
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

    if (currentTab === 'radar') {
      let matches = getRadarMatches();
      if (activeRadarFilter !== 'all') {
        matches = matches.filter(m => m.tracked_item_id === activeRadarFilter);
      }
      if (searchQuery) {
        const q = searchQuery.toLowerCase().trim();
        matches = matches.filter(item => {
          const title = (item.title || '').toLowerCase();
          const sku = (item.sku || '').toLowerCase();
          const disc = (item.discount || item.store_discount || item.coupon_discount || item.super_discount || '').toLowerCase();
          const kw = (item.matched_keyword || '').toLowerCase();
          const name = (item.tracked_item_name || '').toLowerCase();
          return title.includes(q) || sku.includes(q) || disc.includes(q) || kw.includes(q) || name.includes(q);
        });
      }
      return matches;
    }

    if (currentTab === 'categories') {
      let list = getUnifiedCategoryItems();
      if (currentCategory !== 'all') {
        list = list.filter(item => detectCategory(item) === currentCategory);
      }
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

    if (currentTab === 'super') {
      let list = currentSuperFilter === 'combos' 
        ? (fullData.super_saver_doubles || []) 
        : (fullData.super_savers || []);
      if (searchQuery) {
        const q = searchQuery.toLowerCase().trim();
        list = list.filter(item => {
          const title = (item.title || '').toLowerCase();
          const sku = (item.sku || '').toLowerCase();
          const disc = (item.discount || item.super_discount || item.coupon_discount || '').toLowerCase();
          const dateStr = (item.formatted_date || item.deal_date || '').toLowerCase();
          const camp = (item.campaign || '').toLowerCase();
          return title.includes(q) || sku.includes(q) || disc.includes(q) || dateStr.includes(q) || camp.includes(q);
        });
      }
      return list;
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
      } else if (currentTab === 'radar') {
        const tracked = getTrackedItems();
        if (tracked.length === 0) {
          emptyState.querySelector('.empty-icon').textContent = '🎯';
          emptyState.querySelector('h3').textContent = 'Радар пуст';
          emptyState.querySelector('p').innerHTML = 'Вы ещё не добавили товары для отслеживания.<br>Введите название продукта в строке поиска выше или выберите быструю подсказку (+ 🐟 Лосось, + 🧀 Сыр), чтобы получать уведомления о скидках.';
        } else if (activeRadarFilter !== 'all') {
          const item = tracked.find(t => t.id === activeRadarFilter);
          const name = item ? item.name : activeRadarFilter;
          emptyState.querySelector('.empty-icon').textContent = '⏳';
          emptyState.querySelector('h3').textContent = `Ожидаем скидку на: ${name}`;
          emptyState.querySelector('p').innerHTML = `Сейчас в магазине нет активных скидок на этот товар.<br>Бот <a href="https://t.me/lidlcouponsbot" target="_blank" style="color:var(--link-color); font-weight:600;">@lidlcouponsbot</a> сразу пришлет оповещение в Telegram, как только товар появится в каталоге!`;
        } else {
          emptyState.querySelector('.empty-icon').textContent = '⏳';
          emptyState.querySelector('h3').textContent = 'Нет активных скидок по отслеживаемым товарам';
          emptyState.querySelector('p').textContent = 'Сейчас ни на один из ваших товаров нет скидок. Бот пришлет оповещение при обновлении каталога.';
        }
      } else if (currentTab === 'double') {
        emptyState.querySelector('.empty-icon').textContent = searchQuery ? '🔍' : '🔥';
        if (searchQuery) {
          emptyState.querySelector('h3').textContent = 'Комбо не найдены';
          emptyState.querySelector('p').textContent = `По запросу «${searchQuery}» комбо-скидок не найдено. Попробуйте другой запрос.`;
        } else {
          emptyState.querySelector('h3').textContent = 'Сейчас нет активных комбо';
          emptyState.querySelector('p').textContent = 'Комбо появляются, когда скидка магазина суммируется с персональным купоном одного из членов семьи. Проверьте вкладки «Купоны семьи» и «Магазин».';
        }
      } else if (currentTab === 'coupons') {
        emptyState.querySelector('.empty-icon').textContent = searchQuery ? '🔍' : '🎟';
        if (searchQuery) {
          emptyState.querySelector('h3').textContent = 'Купоны не найдены';
          emptyState.querySelector('p').textContent = `По запросу «${searchQuery}» купоны не найдены.`;
        } else if (currentMember !== 'all') {
          emptyState.querySelector('h3').textContent = 'У выбранного члена семьи нет купонов';
          emptyState.querySelector('p').textContent = 'Выберите фильтр «Все» или переключитесь на другого члена семьи.';
        } else {
          emptyState.querySelector('h3').textContent = 'Купоны отсутствуют';
          emptyState.querySelector('p').textContent = 'Сейчас нет активных персональных купонов.';
        }
      } else if (currentTab === 'super') {
        emptyState.querySelector('.empty-icon').textContent = searchQuery ? '🔍' : '⚡';
        if (searchQuery) {
          emptyState.querySelector('h3').textContent = 'Товары не найдены';
          emptyState.querySelector('p').textContent = `По запросу «${searchQuery}» ничего не найдено.`;
        } else if (currentSuperFilter === 'intersect') {
          emptyState.querySelector('h3').textContent = 'Нет пересечений с купонами';
          emptyState.querySelector('p').textContent = 'Среди супер-скидок дня сейчас нет совпадений с купонами вашей семьи. Переключитесь на «Все супер-скидки».';
        } else {
          emptyState.querySelector('h3').textContent = 'Нет предложений на эту дату';
          emptyState.querySelector('p').textContent = 'На выбранный день нет активных супер-скидок.';
        }
      } else { // store
        emptyState.querySelector('.empty-icon').textContent = searchQuery ? '🔍' : '🛒';
        if (searchQuery) {
          emptyState.querySelector('h3').textContent = 'Товары не найдены';
          emptyState.querySelector('p').textContent = `По запросу «${searchQuery}» ничего не найдено.`;
        } else if (currentCategory !== 'all') {
          emptyState.querySelector('h3').textContent = 'В этой категории пока пусто';
          emptyState.querySelector('p').textContent = 'Попробуйте выбрать категорию «Все».';
        } else {
          emptyState.querySelector('h3').textContent = 'Нет активных предложений';
          emptyState.querySelector('p').textContent = 'Каталог магазина обновляется.';
        }
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
      } else if (currentTab === 'radar') {
        card.className = 'card';
        card.innerHTML = renderRadarCard(item);
      } else if (currentTab === 'double') {
        card.className = 'card';
        card.innerHTML = renderDoubleCard(item);
      } else if (currentTab === 'coupons') {
        card.className = 'card';
        card.innerHTML = renderCouponCard(item);
      } else if (currentTab === 'super') {
        card.className = 'card';
        card.innerHTML = renderSuperCard(item);
      } else if (currentTab === 'store') {
        card.className = 'card';
        card.innerHTML = renderStoreCard(item);
      } else if (currentTab === 'categories') {
        card.className = 'card';
        if (item.type === 'double') {
          card.innerHTML = renderDoubleCard(item);
        } else if (item.type === 'coupons') {
          card.innerHTML = renderCouponCard(item);
        } else if (item.type === 'super') {
          card.innerHTML = renderSuperCard(item);
        } else {
          card.innerHTML = renderStoreCard(item);
        }
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
        const type = btn.dataset.type;
        const key = btn.dataset.key;
        const sku = btn.dataset.sku;
        const title = btn.dataset.title;
        const id = btn.dataset.id;
        const item = findItemForFavorite(type, sku, title, key, id);
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

  function findItemForFavorite(type, sku, title, key, id) {
    if (type === 'favs') {
      return getFavorites().find(f => (key && f.key === key) || (id && f.id === id) || (sku && f.sku === sku));
    }

    const match = it => {
      if (sku && it.sku && it.sku === sku) return true;
      if (title && it.title && normalizeTitle(it.title) === normalizeTitle(title)) return true;
      if (key && getProductKey(it) === key) return true;
      if (id && getItemId(type, it) === id) return true;
      return false;
    };

    let list = [];
    if (type === 'double') list = fullData.double_deals || [];
    else if (type === 'coupons') list = fullData.family_coupons || [];
    else if (type === 'store') list = fullData.store_offers || [];

    let found = list.find(match);

    if (!found) {
      found = getUnifiedCategoryItems().find(match);
    }
    if (!found) {
      found = (fullData.double_deals || []).find(match)
           || (fullData.family_coupons || []).find(match)
           || (fullData.store_offers || []).find(match);
    }

    if (!found) return null;

    const itemType = found.type || type || 'store';
    return {
      id: key || getItemId(itemType, found),
      key: key || getProductKey(found),
      type: itemType,
      title: found.title,
      sku: found.sku,
      discount: found.discount || `${found.store_discount || ''} + ${found.coupon_discount || ''}`.trim(),
      final_unit_price: found.final_unit_price || found.unit_price || '-',
      final_pack_price: found.final_pack_price || found.pack_price || '-',
      packaging: found.packaging || '',
      owners: found.owners || [],
      image_url: found.image_url || '',
      formatted_date: found.formatted_date || '',
      validity_str: found.validity_str || '',
      is_expiring_today: found.is_expiring_today || false
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
    const isFav = isFavorite(item);
    const key = getProductKey(item);

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
              <button class="star-btn ${isFav ? 'active' : ''}" data-key="${key}" data-sku="${item.sku || ''}" data-title="${item.title || ''}" data-type="double" title="${isFav ? 'Удалить из списка' : 'В список покупок'}">${isFav ? '⭐' : '☆'}</button>
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
        ${item.validity_str ? `<span class="tag tag-coupon-date ${item.is_expiring_today ? 'tag-coupon-expiring' : ''}">${item.validity_str}</span>` : ''}
        ${item.packaging ? `<span class="tag" style="background:var(--bg-color); color:var(--hint-color);">${item.packaging}</span>` : ''}
        ${renderOwners(item.owners)}
      </div>
    `;
  }

  function renderCouponCard(item) {
    const isFav = isFavorite(item);
    const key = getProductKey(item);

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
              <button class="star-btn ${isFav ? 'active' : ''}" data-key="${key}" data-sku="${item.sku || ''}" data-title="${item.title || ''}" data-type="coupons" title="${isFav ? 'Удалить из списка' : 'В список покупок'}">${isFav ? '⭐' : '☆'}</button>
            </div>
            ${skuHtml}
          </div>
          ${item.unit_price ? `
            <div class="price-banner">
              <div class="unit-price-row">
                <span class="unit-price-highlight">${item.unit_price}</span>
              </div>
              <span class="pack-price-sub">при купоне</span>
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
        ${item.validity_str ? `<span class="tag tag-coupon-date ${item.is_expiring_today ? 'tag-coupon-expiring' : ''}">${item.validity_str}</span>` : ''}
        ${item.is_shared ? `<span class="tag tag-shared">⭐ Совпадение (${item.owners.length})</span>` : ''}
        ${renderOwners(item.owners)}
      </div>
    `;
  }

  function renderStoreCard(item) {
    const isFav = isFavorite(item);
    const key = getProductKey(item);

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
              <button class="star-btn ${isFav ? 'active' : ''}" data-key="${key}" data-sku="${item.sku || ''}" data-title="${item.title || ''}" data-type="store" title="${isFav ? 'Удалить из списка' : 'В список покупок'}">${isFav ? '⭐' : '☆'}</button>
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

  function renderSuperCard(item) {
    const isFav = isFavorite(item);
    const key = getProductKey(item);

    const imgHtml = item.image_url 
      ? `<img src="${item.image_url}" class="card-img" loading="lazy" alt="${item.title}">`
      : `<span class="card-img-fallback">⚡</span>`;

    const skuHtml = item.sku 
      ? `<span class="card-sku copy-sku" data-sku="${item.sku}">Код: ${item.sku} 📋</span>` 
      : '';

    const isCombo = Boolean(item.coupon_discount || (item.owners && item.owners.length));

    let priceHtml = '';
    if (isCombo) {
      priceHtml = `
        <div class="price-banner">
          <div class="unit-price-row">
            <span class="unit-price-highlight">${item.final_price}</span>
            ${item.super_price && item.super_price !== item.final_price ? `<span class="old-price-strike">${item.super_price}</span>` : ''}
          </div>
          <span class="pack-price-sub">с купоном семьи</span>
        </div>
      `;
    } else {
      const hasOldPrice = item.old_price && item.old_price !== item.price;
      priceHtml = `
        <div class="price-banner">
          <div class="unit-price-row">
            <span class="unit-price-highlight">${item.price}</span>
            ${hasOldPrice ? `<span class="old-price-strike">${item.old_price}</span>` : ''}
          </div>
          ${item.unit_price ? `<span class="pack-price-sub">${item.unit_price}</span>` : (item.packaging ? `<span class="pack-price-sub">${item.packaging}</span>` : '')}
        </div>
      `;
    }

    const dateBadge = item.formatted_date 
      ? `<span class="tag tag-super-date">${item.formatted_date}</span>`
      : '';

    return `
      <div class="card-top">
        <div class="card-img-wrap">${imgHtml}</div>
        <div class="card-body">
          <div>
            <div class="card-header-row">
              <div class="card-title">${item.title}</div>
              <button class="star-btn ${isFav ? 'active' : ''}" data-key="${key}" data-sku="${item.sku || ''}" data-title="${item.title || ''}" data-type="super" title="${isFav ? 'Удалить из списка' : 'В список покупок'}">${isFav ? '⭐' : '☆'}</button>
            </div>
            ${skuHtml}
          </div>
          ${priceHtml}
        </div>
      </div>
      <div class="card-tags">
        ${dateBadge}
        ${isCombo ? `<span class="tag tag-coupon">🎟 ${item.coupon_discount}</span>` : (item.discount ? `<span class="tag tag-store">${item.discount}</span>` : '')}
        ${isCombo ? renderOwners(item.owners) : ''}
        ${item.campaign ? `<span class="tag tag-super-campaign">${item.campaign}</span>` : ''}
        ${item.product_url ? `<a href="${item.product_url}" target="_blank" rel="noopener" class="tag" style="text-decoration:none; color:var(--link-color); background:var(--bg-color);">На сайт ↗</a>` : ''}
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
      : item.type === 'super'
      ? `<span class="tag tag-super">⚡ Super Savers</span>`
      : `<span class="tag tag-store">🛒 Daily Savers</span>`;

    const dateTag = item.formatted_date 
      ? `<span class="tag tag-super-date">${item.formatted_date}</span>` 
      : (item.validity_str ? `<span class="tag tag-coupon-date ${item.is_expiring_today ? 'tag-coupon-expiring' : ''}">${item.validity_str}</span>` : '');

    return `
      <div class="fav-card-row">
        <button class="fav-check-btn ${item.checked ? 'checked' : ''}" data-id="${item.id || item.key}" title="Отметить купленным">✓</button>
        <div style="flex:1; min-width:0;">
          <div class="card-top">
            <div class="card-img-wrap">${imgHtml}</div>
            <div class="card-body">
              <div>
                <div class="card-header-row">
                  <div class="card-title">${item.title}</div>
                  <button class="star-btn active" data-id="${item.id || item.key}" data-key="${item.key || item.id}" data-sku="${item.sku || ''}" data-title="${item.title || ''}" data-type="favs" title="Удалить из списка">✕</button>
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
            ${dateTag}
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
      updateSubRowsVisibility();
      renderCurrentList();
      window.scrollTo({ top: 0, behavior: 'smooth' });
    });
  });

  // Event Listeners: Family Member Chips
  document.querySelectorAll('#family-chips .chip').forEach(chip => {
    chip.addEventListener('click', () => {
      haptic('selection');
      document.querySelectorAll('#family-chips .chip').forEach(c => c.classList.remove('active'));
      chip.classList.add('active');
      currentMember = chip.dataset.member;
      renderCurrentList();
    });
  });

  // Event Listeners: Category Filter Chips
  document.querySelectorAll('#category-chips .chip-cat').forEach(chip => {
    chip.addEventListener('click', () => {
      haptic('selection');
      document.querySelectorAll('#category-chips .chip-cat').forEach(c => c.classList.remove('active'));
      chip.classList.add('active');
      currentCategory = chip.dataset.cat;
      renderCurrentList();
    });
  });

  // Event Listeners: Super Savers Filter Chips
  document.querySelectorAll('#super-chips .chip-super').forEach(chip => {
    chip.addEventListener('click', () => {
      haptic('selection');
      document.querySelectorAll('#super-chips .chip-super').forEach(c => c.classList.remove('active'));
      chip.classList.add('active');
      currentSuperFilter = chip.dataset.super;
      renderCurrentList();
    });
  });

  // Family Chips Horizontal Scroll: Wheel, Drag, and Arrows
  if (familyChipsScroll) {
    familyChipsScroll.addEventListener('scroll', updateFamilyScrollArrows, { passive: true });

    // Mouse wheel: scroll horizontally on desktop
    familyChipsScroll.addEventListener('wheel', (e) => {
      if (e.deltaY !== 0) {
        e.preventDefault();
        familyChipsScroll.scrollLeft += e.deltaY;
        updateFamilyScrollArrows();
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
      updateFamilyScrollArrows();
    });

    // Prevent chip selection if the user was dragging
    document.querySelectorAll('#family-chips .chip').forEach(chip => {
      chip.addEventListener('click', (e) => {
        if (hasMoved) {
          e.stopImmediatePropagation();
          hasMoved = false;
        }
      }, true);
    });
  }

  // Family Chips Arrow buttons
  if (chipsArrowLeft && familyChipsScroll) {
    chipsArrowLeft.addEventListener('click', () => {
      haptic('light');
      familyChipsScroll.scrollBy({ left: -140, behavior: 'smooth' });
      setTimeout(updateFamilyScrollArrows, 200);
    });
  }

  if (chipsArrowRight && familyChipsScroll) {
    chipsArrowRight.addEventListener('click', () => {
      haptic('light');
      familyChipsScroll.scrollBy({ left: 140, behavior: 'smooth' });
      setTimeout(updateFamilyScrollArrows, 200);
    });
  }

  // Category Chips Horizontal Scroll: Wheel, Drag, and Arrows
  if (categoryChipsScroll) {
    categoryChipsScroll.addEventListener('scroll', updateCategoryScrollArrows, { passive: true });

    // Mouse wheel: scroll horizontally on desktop
    categoryChipsScroll.addEventListener('wheel', (e) => {
      if (e.deltaY !== 0) {
        e.preventDefault();
        categoryChipsScroll.scrollLeft += e.deltaY;
        updateCategoryScrollArrows();
      }
    }, { passive: false });

    // Mouse drag-to-scroll on desktop
    let isDownCat = false;
    let startXCat = 0;
    let scrollStartCat = 0;
    let hasMovedCat = false;

    categoryChipsScroll.addEventListener('mousedown', (e) => {
      isDownCat = true;
      hasMovedCat = false;
      categoryChipsScroll.classList.add('grabbing');
      startXCat = e.pageX - categoryChipsScroll.offsetLeft;
      scrollStartCat = categoryChipsScroll.scrollLeft;
    });

    window.addEventListener('mouseup', () => {
      if (isDownCat) {
        isDownCat = false;
        categoryChipsScroll.classList.remove('grabbing');
      }
    });

    window.addEventListener('mousemove', (e) => {
      if (!isDownCat) return;
      const x = e.pageX - categoryChipsScroll.offsetLeft;
      const walk = (x - startXCat) * 1.5;
      if (Math.abs(walk) > 4) hasMovedCat = true;
      categoryChipsScroll.scrollLeft = scrollStartCat - walk;
      updateCategoryScrollArrows();
    });

    // Prevent chip selection if the user was dragging
    document.querySelectorAll('#category-chips .chip-cat').forEach(chip => {
      chip.addEventListener('click', (e) => {
        if (hasMovedCat) {
          e.stopImmediatePropagation();
          hasMovedCat = false;
        }
      }, true);
    });
  }

  // Category Arrow buttons
  if (catArrowLeft && categoryChipsScroll) {
    catArrowLeft.addEventListener('click', () => {
      haptic('light');
      categoryChipsScroll.scrollBy({ left: -140, behavior: 'smooth' });
      setTimeout(updateCategoryScrollArrows, 200);
    });
  }

  if (catArrowRight && categoryChipsScroll) {
    catArrowRight.addEventListener('click', () => {
      haptic('light');
      categoryChipsScroll.scrollBy({ left: 140, behavior: 'smooth' });
      setTimeout(updateCategoryScrollArrows, 200);
    });
  }

  window.addEventListener('resize', () => {
    updateFamilyScrollArrows();
    updateCategoryScrollArrows();
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
  setupRadarAutocomplete();
  loadData();
})();
