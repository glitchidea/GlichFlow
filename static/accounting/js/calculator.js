/* Modular hesaplayıcı stub: HTML'den bağımsız, veri modeline göre hesaplar */
(function() {
  'use strict';

  function qs(sel, root) { return (root || document).querySelector(sel); }
  function qsa(sel, root) { return Array.from((root || document).querySelectorAll(sel)); }

  function formatTL(value) {
    const num = Number(value || 0);
    return new Intl.NumberFormat('tr-TR', { style: 'currency', currency: 'TRY', maximumFractionDigits: 0 }).format(num);
  }

  function findSelectedPackage() {
    const pkg = qs('#packageSelect');
    if (!pkg || !pkg.value) return null;
    const opt = pkg.options[pkg.selectedIndex];
    return {
      id: pkg.value,
      base: Number(opt.getAttribute('data-price') || 0),
      extraMultiplier: Number(opt.getAttribute('data-multiplier') || 0),
    };
  }

  function updatePackageOptionsByGroup() {
    const groupId = qs('#groupSelect')?.value;
    const pkg = qs('#packageSelect');
    if (!pkg) return;
    let hasAny = false;
    for (const opt of pkg.querySelectorAll('option')) {
      if (!opt.value) continue;
      const show = !groupId || opt.getAttribute('data-group') === groupId;
      opt.hidden = !show;
      if (show) hasAny = true;
    }
    pkg.disabled = !hasAny;
    if (!hasAny) {
      pkg.value = '';
    }

    // Filter extras by group
    qsa('[data-extra-group]').forEach(function(card){
      const eg = String(card.getAttribute('data-extra-group'));
      card.style.display = (!groupId || eg === groupId) ? '' : 'none';
    });
  }

  function toggleExtraPages(pkg) {
    const section = qs('#extraPagesSection');
    if (!section) return;
    if (pkg && pkg.extraMultiplier > 0) {
      section.style.display = '';
    } else {
      section.style.display = 'none';
      const input = qs('#extraPagesInput');
      if (input) input.value = 0;
    }
  }

  function showPackageFeatures(pkg) {
    const container = qs('#packageFeatures');
    if (!container) return;
    // Hide all lists
    qsa('[data-features-for]').forEach(function(ul){ ul.classList.add('d-none'); });
    if (pkg && pkg.id) {
      container.style.display = '';
      const ul = qs('[data-features-for="' + pkg.id + '"]');
      if (ul) ul.classList.remove('d-none');
    } else {
      container.style.display = 'none';
    }
  }

  function calculateTotal() {
    const selected = findSelectedPackage();
    let total = selected ? selected.base : 0;

    // Extra pages
    if (selected && selected.extraMultiplier > 0) {
      const extra = Number(qs('#extraPagesInput')?.value || 0);
      const add = Math.round(selected.base * selected.extraMultiplier * extra);
      setBreakdownRow('rowExtraPages', 'sumExtraPages', add, add > 0);
      total += add;
    } else {
      setBreakdownRow('rowExtraPages', 'sumExtraPages', 0, false);
    }

    // Extras - handle both fixed prices and multipliers
    const root = qs('#calculator-root');
    const radiosByType = {};
    qsa('.extra-radio', root).forEach(function(input){
      const type = input.getAttribute('data-type');
      if (input.checked) {
        const multiplier = Number(input.getAttribute('data-multiplier') || 0);
        const price = Number(input.getAttribute('data-price') || 0);
        radiosByType[type] = { multiplier, price };
      }
    });
    
    for (const type in radiosByType) {
      const { multiplier, price } = radiosByType[type];
      let add = 0;
      if (price > 0) {
        add = price; // Fixed price
      } else if (multiplier > 0 && selected) {
        add = Math.round(selected.base * multiplier); // Percentage of base price
      }
      
      if (type === 'language') setBreakdownRow('rowLanguage', 'sumLanguage', add, add > 0);
      if (type === 'theme') setBreakdownRow('rowTheme', 'sumTheme', add, add > 0);
      if (type === 'hosting') setBreakdownRow('rowHosting', 'sumHosting', add, add > 0);
      if (type === 'domain') setBreakdownRow('rowDomain', 'sumDomain', add, add > 0);
      if (type === 'ssl') setBreakdownRow('rowSSL', 'sumSSL', add, add > 0);
      if (type === 'logo') setBreakdownRow('rowLogo', 'sumLogo', add, add > 0);
      total += add;
    }
    
    // Reset radio types that weren't selected
    if (!radiosByType['language']) setBreakdownRow('rowLanguage', 'sumLanguage', 0, false);
    if (!radiosByType['theme']) setBreakdownRow('rowTheme', 'sumTheme', 0, false);
    if (!radiosByType['hosting']) setBreakdownRow('rowHosting', 'sumHosting', 0, false);
    if (!radiosByType['domain']) setBreakdownRow('rowDomain', 'sumDomain', 0, false);
    if (!radiosByType['ssl']) setBreakdownRow('rowSSL', 'sumSSL', 0, false);
    if (!radiosByType['logo']) setBreakdownRow('rowLogo', 'sumLogo', 0, false);
    
    // Checkboxes
    qsa('.extra-checkbox', root).forEach(function(input){
      const type = input.getAttribute('data-type');
      const multiplier = Number(input.getAttribute('data-multiplier') || 0);
      const price = Number(input.getAttribute('data-price') || 0);
      let add = 0;
      
      if (input.checked) {
        if (price > 0) {
          add = price; // Fixed price
        } else if (multiplier > 0 && selected) {
          add = Math.round(selected.base * multiplier); // Percentage of base price
        }
      }
      
      if (type === 'hosting') setBreakdownRow('rowHosting', 'sumHosting', add, add > 0);
      if (type === 'domain') setBreakdownRow('rowDomain', 'sumDomain', add, add > 0);
      if (type === 'ssl') setBreakdownRow('rowSSL', 'sumSSL', add, add > 0);
      if (type === 'logo') setBreakdownRow('rowLogo', 'sumLogo', add, add > 0);
      total += add;
    });

    const baseOut = qs('#sumBasePrice');
    if (baseOut) baseOut.textContent = formatTL(selected ? selected.base : 0);
    const totalOut = qs('#totalPrice');
    if (totalOut) totalOut.textContent = formatTL(total);
  }

  function setBreakdownRow(rowId, sumId, amount, show){
    const row = qs('#' + rowId);
    const sum = qs('#' + sumId);
    if (row) row.classList.toggle('d-none', !show);
    if (sum) sum.textContent = formatTL(amount || 0);
  }

  document.addEventListener('DOMContentLoaded', function() {
    const root = qs('#calculator-root');
    if (!root) return;
    const group = qs('#groupSelect');
    const pkg = qs('#packageSelect');
    const extraPages = qs('#extraPagesInput');
    if (group) group.addEventListener('change', function(){ updatePackageOptionsByGroup(); calculateTotal(); updateSelectedPackageLabel(findSelectedPackage()); });
    if (pkg) pkg.addEventListener('change', function(){ const sel = findSelectedPackage(); toggleExtraPages(sel); showPackageFeatures(sel); updateSelectedPackageLabel(sel); calculateTotal(); });
    if (extraPages) extraPages.addEventListener('input', calculateTotal);
    qsa('.extra-radio', root).forEach(function(el){ el.addEventListener('change', calculateTotal); });
    qsa('.extra-checkbox', root).forEach(function(el){ el.addEventListener('change', calculateTotal); });
    updatePackageOptionsByGroup();
    const sel = findSelectedPackage();
    toggleExtraPages(sel);
    showPackageFeatures(sel);
    updateSelectedPackageLabel(sel);
    calculateTotal();

    const resetBtn = qs('#calcResetBtn');
    if (resetBtn) resetBtn.addEventListener('click', resetCalculator);
  });

  function updateSelectedPackageLabel(sel){
    const label = qs('#selectedPackageLabel');
    const pkg = qs('#packageSelect');
    if (!label || !pkg) return;
    if (sel && pkg.selectedIndex >= 0) {
      label.textContent = pkg.options[pkg.selectedIndex].textContent;
    } else {
      label.textContent = 'Henüz paket seçilmedi';
    }
  }

  function resetCalculator(){
    // Clear radios & checkboxes
    qsa('.extra-radio').forEach(function(i){ i.checked = false; });
    qsa('.extra-checkbox').forEach(function(i){ i.checked = false; });
    const extraInput = qs('#extraPagesInput');
    if (extraInput) extraInput.value = 0;
    const pkg = qs('#packageSelect');
    if (pkg) pkg.value = '';
    const group = qs('#groupSelect');
    if (group) group.value = '';
    updatePackageOptionsByGroup();
    showPackageFeatures(null);
    updateSelectedPackageLabel(null);
    setBreakdownRow('rowExtraPages', 'sumExtraPages', 0, false);
    setBreakdownRow('rowLanguage', 'sumLanguage', 0, false);
    setBreakdownRow('rowTheme', 'sumTheme', 0, false);
    setBreakdownRow('rowHosting', 'sumHosting', 0, false);
    setBreakdownRow('rowDomain', 'sumDomain', 0, false);
    setBreakdownRow('rowSSL', 'sumSSL', 0, false);
    setBreakdownRow('rowLogo', 'sumLogo', 0, false);
    const baseOut = qs('#sumBasePrice'); if (baseOut) baseOut.textContent = formatTL(0);
    const totalOut = qs('#totalPrice'); if (totalOut) totalOut.textContent = formatTL(0);
  }
})();


