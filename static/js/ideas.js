/**
 * Ideas App JavaScript - Fikir Not Defteri
 * Hızlı ekleme, filtreleme ve diğer interaktif özellikler
 */

document.addEventListener('DOMContentLoaded', function() {
    // Hızlı fikir ekleme formu
    const quickAddForm = document.getElementById('quickAddForm');
    if (quickAddForm) {
        quickAddForm.addEventListener('submit', handleQuickAdd);
    }

    // Filtre formu
    const filterForm = document.getElementById('filterForm');
    if (filterForm) {
        setupFilterForm();
    }

    // Fikir kartlarına hover efekti
    setupIdeaCards();

    // Otomatik kaydetme özelliği
    setupAutoSave();

    // Klavye kısayolları
    setupKeyboardShortcuts();
});

/**
 * Hızlı fikir ekleme işlemi
 */
function handleQuickAdd(event) {
    event.preventDefault();
    
    const form = event.target;
    const titleInput = document.getElementById('quickTitle');
    const descriptionInput = document.getElementById('quickDescription');
    const submitBtn = form.querySelector('button[type="submit"]');
    
    const title = titleInput.value.trim();
    const description = descriptionInput.value.trim();
    
    if (!title) {
        showAlert('Başlık gereklidir!', 'warning');
        titleInput.focus();
        return;
    }
    
    // Loading durumu
    setLoading(submitBtn, true);
    
    // CSRF token al - form içindeki token'ı kullan
    const csrfToken = form.querySelector('[name=csrfmiddlewaretoken]').value;
    
    // FormData oluştur
    const formData = new FormData();
    formData.append('title', title);
    formData.append('description', description);
    formData.append('csrfmiddlewaretoken', csrfToken);
    
    // AJAX isteği
    fetch('/ideas/quick-add/', {
        method: 'POST',
        headers: {
            'X-CSRFToken': csrfToken,
            'X-Requested-With': 'XMLHttpRequest'
        },
        body: formData
    })
    .then(response => {
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        return response.json();
    })
    .then(data => {
        console.log('Response data:', data);
        if (data.success) {
            showAlert(data.message, 'success');
            form.reset();
            
            // Başarılı ekleme sonrası yönlendirme
            if (data.redirect_url) {
                setTimeout(() => {
                    window.location.href = data.redirect_url;
                }, 1500);
            } else {
                // Sayfayı yenile
                setTimeout(() => {
                    window.location.reload();
                }, 1000);
            }
        } else {
            showAlert(data.error || 'Bir hata oluştu!', 'danger');
        }
    })
    .catch(error => {
        console.error('Error:', error);
        showAlert('Bir hata oluştu! Lütfen sayfayı yenileyin ve tekrar deneyin.', 'danger');
    })
    .finally(() => {
        setLoading(submitBtn, false);
    });
}

/**
 * Filtre formu ayarları
 */
function setupFilterForm() {
    const filterForm = document.getElementById('filterForm');
    const searchInput = filterForm.querySelector('input[name="search"]');
    const prioritySelect = filterForm.querySelector('select[name="priority"]');
    const statusSelect = filterForm.querySelector('select[name="status"]');
    
    // Arama input'una debounce ekle
    let searchTimeout;
    searchInput.addEventListener('input', function() {
        clearTimeout(searchTimeout);
        searchTimeout = setTimeout(() => {
            filterForm.submit();
        }, 500);
    });
    
    // Select değişikliklerinde otomatik submit
    prioritySelect.addEventListener('change', () => filterForm.submit());
    statusSelect.addEventListener('change', () => filterForm.submit());
}

/**
 * Fikir kartlarına hover efekti ve tıklama olayları
 */
function setupIdeaCards() {
    const ideaCards = document.querySelectorAll('.idea-card');
    
    ideaCards.forEach(card => {
        // Kart tıklama olayı
        card.addEventListener('click', function(e) {
            // Buton tıklamalarını hariç tut
            if (e.target.closest('button, a')) {
                return;
            }
            
            const link = card.querySelector('.idea-title a');
            if (link) {
                window.location.href = link.href;
            }
        });
        
        // Hover efekti için cursor pointer
        card.style.cursor = 'pointer';
    });
}

/**
 * Otomatik kaydetme özelliği (form sayfalarında)
 */
function setupAutoSave() {
    const form = document.querySelector('form[method="post"]');
    if (!form || !form.querySelector('textarea, input[type="text"]')) {
        return;
    }
    
    const inputs = form.querySelectorAll('textarea, input[type="text"]');
    let saveTimeout;
    
    inputs.forEach(input => {
        input.addEventListener('input', function() {
            clearTimeout(saveTimeout);
            saveTimeout = setTimeout(() => {
                saveDraft();
            }, 2000);
        });
    });
}

/**
 * Taslak kaydetme
 */
function saveDraft() {
    const form = document.querySelector('form[method="post"]');
    if (!form) return;
    
    const formData = new FormData(form);
    formData.append('save_draft', 'true');
    
    fetch(form.action, {
        method: 'POST',
        body: formData,
        headers: {
            'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showDraftSaved();
        }
    })
    .catch(error => {
        console.error('Draft save error:', error);
    });
}

/**
 * Klavye kısayolları
 */
function setupKeyboardShortcuts() {
    document.addEventListener('keydown', function(e) {
        // Ctrl/Cmd + N: Yeni fikir
        if ((e.ctrlKey || e.metaKey) && e.key === 'n') {
            e.preventDefault();
            const newIdeaLink = document.querySelector('a[href*="create"]');
            if (newIdeaLink) {
                window.location.href = newIdeaLink.href;
            }
        }
        
        // Ctrl/Cmd + F: Arama kutusuna odaklan
        if ((e.ctrlKey || e.metaKey) && e.key === 'f') {
            e.preventDefault();
            const searchInput = document.querySelector('input[name="search"]');
            if (searchInput) {
                searchInput.focus();
                searchInput.select();
            }
        }
        
        // Escape: Modal'ları kapat
        if (e.key === 'Escape') {
            const modals = document.querySelectorAll('.modal.show');
            modals.forEach(modal => {
                const bsModal = bootstrap.Modal.getInstance(modal);
                if (bsModal) {
                    bsModal.hide();
                }
            });
        }
    });
}

/**
 * Loading durumu ayarla
 */
function setLoading(element, isLoading) {
    if (isLoading) {
        element.disabled = true;
        element.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Kaydediliyor...';
        element.classList.add('loading');
    } else {
        element.disabled = false;
        element.innerHTML = '<i class="fas fa-plus"></i> Hızlı Ekle';
        element.classList.remove('loading');
    }
}

/**
 * Alert göster
 */
function showAlert(message, type = 'info') {
    // Mevcut alert'leri temizle
    const existingAlerts = document.querySelectorAll('.alert-temp');
    existingAlerts.forEach(alert => alert.remove());
    
    const alertDiv = document.createElement('div');
    alertDiv.className = `alert alert-${type} alert-dismissible fade show alert-temp`;
    alertDiv.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
    `;
    
    // Alert'i sayfanın üstüne ekle
    const container = document.querySelector('.main-content') || document.body;
    container.insertBefore(alertDiv, container.firstChild);
    
    // 5 saniye sonra otomatik kapat
    setTimeout(() => {
        if (alertDiv.parentNode) {
            alertDiv.remove();
        }
    }, 5000);
}

/**
 * Taslak kaydedildi bildirimi
 */
function showDraftSaved() {
    const indicator = document.getElementById('draft-indicator') || createDraftIndicator();
    indicator.style.display = 'block';
    indicator.textContent = 'Taslak kaydedildi';
    
    setTimeout(() => {
        indicator.style.display = 'none';
    }, 2000);
}

/**
 * Taslak göstergesi oluştur
 */
function createDraftIndicator() {
    const indicator = document.createElement('div');
    indicator.id = 'draft-indicator';
    indicator.className = 'position-fixed top-0 end-0 p-3';
    indicator.style.display = 'none';
    indicator.style.zIndex = '9999';
    indicator.innerHTML = `
        <div class="alert alert-info alert-dismissible fade show">
            <i class="fas fa-save"></i> <span></span>
        </div>
    `;
    
    document.body.appendChild(indicator);
    return indicator;
}

/**
 * Fikir kartı animasyonu
 */
function animateIdeaCard(card) {
    card.style.opacity = '0';
    card.style.transform = 'translateY(20px)';
    
    setTimeout(() => {
        card.style.transition = 'all 0.3s ease';
        card.style.opacity = '1';
        card.style.transform = 'translateY(0)';
    }, 100);
}

/**
 * Arama önerileri (gelecekte eklenebilir)
 */
function setupSearchSuggestions() {
    const searchInput = document.querySelector('input[name="search"]');
    if (!searchInput) return;
    
    // Bu özellik gelecekte eklenebilir
    // AJAX ile arama önerileri getirilebilir
}

/**
 * Drag & Drop özelliği (gelecekte eklenebilir)
 */
function setupDragAndDrop() {
    // Bu özellik gelecekte eklenebilir
    // Fikirleri sürükleyip bırakarak öncelik sırası değiştirilebilir
}

/**
 * Gerçek zamanlı arama
 */
function setupRealTimeSearch() {
    const searchInput = document.querySelector('input[name="search"]');
    if (!searchInput) return;
    
    let searchTimeout;
    searchInput.addEventListener('input', function() {
        clearTimeout(searchTimeout);
        searchTimeout = setTimeout(() => {
            performSearch(this.value);
        }, 300);
    });
}

/**
 * AJAX ile arama yap
 */
function performSearch(query) {
    if (query.length < 2) return;
    
    const url = new URL(window.location);
    url.searchParams.set('search', query);
    
    fetch(url.toString(), {
        headers: {
            'X-Requested-With': 'XMLHttpRequest'
        }
    })
    .then(response => response.text())
    .then(html => {
        // Sonuçları güncelle
        const parser = new DOMParser();
        const doc = parser.parseFromString(html, 'text/html');
        const newContent = doc.querySelector('.card-body');
        const currentContent = document.querySelector('.card-body');
        
        if (newContent && currentContent) {
            currentContent.innerHTML = newContent.innerHTML;
            setupIdeaCards(); // Yeni kartlara event listener ekle
        }
    })
    .catch(error => {
        console.error('Search error:', error);
    });
}

/**
 * Sayfa yüklendiğinde çalışacak ek işlemler
 */
window.addEventListener('load', function() {
    // Fikir kartlarını animasyonla göster
    const ideaCards = document.querySelectorAll('.idea-card');
    ideaCards.forEach((card, index) => {
        setTimeout(() => {
            animateIdeaCard(card);
        }, index * 100);
    });
    
    // Tooltip'leri aktif et
    const tooltips = document.querySelectorAll('[data-bs-toggle="tooltip"]');
    tooltips.forEach(tooltip => {
        new bootstrap.Tooltip(tooltip);
    });
});

/**
 * Hata yakalama
 */
window.addEventListener('error', function(e) {
    console.error('JavaScript Error:', e.error);
    // Hata durumunda kullanıcıya bilgi verilebilir
});

/**
 * Sayfa kapatılırken uyarı (taslak varsa)
 */
window.addEventListener('beforeunload', function(e) {
    const form = document.querySelector('form[method="post"]');
    if (form && form.querySelector('textarea, input[type="text"]')) {
        const hasContent = Array.from(form.querySelectorAll('textarea, input[type="text"]'))
            .some(input => input.value.trim().length > 0);
        
        if (hasContent) {
            e.preventDefault();
            e.returnValue = 'Kaydedilmemiş değişiklikleriniz var. Sayfadan ayrılmak istediğinizden emin misiniz?';
        }
    }
});

