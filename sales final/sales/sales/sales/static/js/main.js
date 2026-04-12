// Main JS - filter panel and global utilities
document.addEventListener('DOMContentLoaded', function() {
  const STORAGE_KEY = 'sales_filter';
  const filterPanel = document.getElementById('filterPanel');
  const filterStats = document.getElementById('filterStats');
  const clearBtn = document.getElementById('clearFilterBtn');

  function getFilter() {
    const cat = document.querySelectorAll('.filter-cat:checked');
    const prod = document.querySelectorAll('.filter-prod:checked');
    return {
      category_ids: Array.from(cat).map(c => c.value),
      product_ids: Array.from(prod).map(p => p.value)
    };
  }

  function saveFilter() {
    const f = getFilter();
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify(f));
    updateSummary();
  }

  function restoreFilter() {
    try {
      const saved = JSON.parse(sessionStorage.getItem(STORAGE_KEY) || '{}');
      (saved.category_ids || []).forEach(id => {
        const cb = document.querySelector(`.filter-cat[value="${id}"]`);
        if (cb) cb.checked = true;
      });
      (saved.product_ids || []).forEach(id => {
        const cb = document.querySelector(`.filter-prod[value="${id}"]`);
        if (cb) cb.checked = true;
      });
      updateSummary();
    } catch (_) {}
  }

  function updateSummary() {
    if (!filterStats) return;
    const f = getFilter();
    if (f.category_ids.length === 0 && f.product_ids.length === 0) {
      filterStats.textContent = 'Select categories/products to see quantity & sales';
      return;
    }
    const params = new URLSearchParams();
    f.category_ids.forEach(id => params.append('category_ids', id));
    f.product_ids.forEach(id => params.append('product_ids', id));
    fetch('/api/sales/summary?' + params).then(r => r.json()).then(data => {
      filterStats.textContent = `Filtered: Qty ${data.quantity} | Gross ₹${data.total.toFixed(2)} | ${data.transactions} transactions`;
    }).catch(() => {
      filterStats.textContent = 'Error loading summary';
    });
  }

  function appendFilterToHref(href) {
    const f = getFilter();
    if (f.category_ids.length === 0 && f.product_ids.length === 0) return href;
    const u = new URL(href, window.location.origin);
    u.searchParams.delete('category_ids');
    u.searchParams.delete('product_ids');
    f.category_ids.forEach(id => u.searchParams.append('category_ids', id));
    f.product_ids.forEach(id => u.searchParams.append('product_ids', id));
    return u.pathname + u.search;
  }

  if (filterPanel) {
    filterPanel.querySelectorAll('.filter-cat, .filter-prod').forEach(cb => {
      cb.addEventListener('change', saveFilter);
    });
    if (clearBtn) {
      clearBtn.addEventListener('click', function() {
        filterPanel.querySelectorAll('.filter-cat, .filter-prod').forEach(cb => cb.checked = false);
        sessionStorage.removeItem(STORAGE_KEY);
        updateSummary();
      });
    }
    restoreFilter();

    // Custom report form: append filter params on submit
    const customReportForm = document.querySelector('form[action*="/reports/custom"]');
    if (customReportForm) {
      customReportForm.addEventListener('submit', function() {
        const f = getFilter();
        if (f.category_ids.length > 0 || f.product_ids.length > 0) {
          f.category_ids.forEach(id => {
            const inp = document.createElement('input');
            inp.type = 'hidden';
            inp.name = 'category_ids';
            inp.value = id;
            customReportForm.appendChild(inp);
          });
          f.product_ids.forEach(id => {
            const inp = document.createElement('input');
            inp.type = 'hidden';
            inp.name = 'product_ids';
            inp.value = id;
            customReportForm.appendChild(inp);
          });
        }
      });
    }

    // Links to products, categories, reports: append filter params when filter is active
    const filterAwareSelector = '.sidebar-nav a[href], a.report-card[href], a[href*="/products"], a[href*="/categories"], a[href*="/reports/"]';
    document.querySelectorAll(filterAwareSelector).forEach(link => {
      link.addEventListener('click', function(e) {
        const f = getFilter();
        if (f.category_ids.length > 0 || f.product_ids.length > 0) {
          const href = link.getAttribute('href');
          if (href && (href.startsWith('/') || href.includes('/products') || href.includes('/categories') || href.includes('/reports/'))) {
            const newHref = appendFilterToHref(href);
            if (newHref !== href) {
              e.preventDefault();
              window.location.href = newHref;
            }
          }
        }
      });
    });
  }
});
