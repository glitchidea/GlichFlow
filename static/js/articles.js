// Makale Sistemi JavaScript

document.addEventListener('DOMContentLoaded', function() {
    // Genel başlatma
    initializeArticles();
    
    // Arama formu
    initializeSearchForm();
    
    // Yorum formu
    initializeCommentForm();
    
    // Markdown editor
    initializeMarkdownEditor();
    
    // Makale kartları
    initializeArticleCards();
});

// Genel başlatma
function initializeArticles() {
    console.log('Makale sistemi başlatıldı');
    
    // Smooth scroll
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function (e) {
            e.preventDefault();
            const target = document.querySelector(this.getAttribute('href'));
            if (target) {
                target.scrollIntoView({
                    behavior: 'smooth',
                    block: 'start'
                });
            }
        });
    });
    
    // Lazy loading için intersection observer
    if ('IntersectionObserver' in window) {
        const imageObserver = new IntersectionObserver((entries, observer) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    const img = entry.target;
                    img.src = img.dataset.src;
                    img.classList.remove('lazy');
                    imageObserver.unobserve(img);
                }
            });
        });
        
        document.querySelectorAll('img[data-src]').forEach(img => {
            imageObserver.observe(img);
        });
    }
    
    // Kod blokları için kopyala butonları
    initializeCodeCopyButtons();
}

// Arama formu
function initializeSearchForm() {
    const searchForm = document.querySelector('form[method="get"]');
    if (!searchForm) return;
    
    // Arama input'u için debounce
    const searchInput = searchForm.querySelector('input[name="query"]');
    if (searchInput) {
        let searchTimeout;
        searchInput.addEventListener('input', function() {
            clearTimeout(searchTimeout);
            searchTimeout = setTimeout(() => {
                // Otomatik arama (opsiyonel)
                // searchForm.submit();
            }, 500);
        });
    }
    
    // Form gönderimi
    searchForm.addEventListener('submit', function(e) {
        const query = searchForm.querySelector('input[name="query"]').value.trim();
        if (!query && !searchForm.querySelector('select[name="category"]').value && 
            !searchForm.querySelector('select[name="status"]').value && 
            !searchForm.querySelector('select[name="author"]').value) {
            e.preventDefault();
            showAlert('Lütfen en az bir arama kriteri girin.', 'warning');
        }
    });
}

// Yorum formu
function initializeCommentForm() {
    const commentForm = document.getElementById('commentForm');
    if (!commentForm) return;
    
    // Çift submit'i önlemek için flag
    let isSubmitting = false;
    
    commentForm.addEventListener('submit', function(e) {
        e.preventDefault();
        
        // Eğer zaten submit ediliyorsa, tekrar submit etme
        if (isSubmitting) {
            console.log('Form zaten submit ediliyor, çift submit engellendi');
            return;
        }
        
        isSubmitting = true;
        
        const formData = new FormData(this);
        const submitBtn = this.querySelector('button[type="submit"]');
        const originalText = submitBtn.innerHTML;
        
        // Loading state
        submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Gönderiliyor...';
        submitBtn.disabled = true;
        
        fetch(this.action, {
            method: 'POST',
            headers: {
                'X-CSRFToken': formData.get('csrfmiddlewaretoken'),
                'X-Requested-With': 'XMLHttpRequest'
            },
            body: formData
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                showAlert(data.message, 'success');
                this.reset();
                
                // Sayfayı yenile
                setTimeout(() => {
                    window.location.reload();
                }, 1500);
            } else {
                showAlert(data.error || 'Bir hata oluştu!', 'danger');
            }
        })
        .catch(error => {
            console.error('Error:', error);
            showAlert('Bir hata oluştu!', 'danger');
        })
        .finally(() => {
            submitBtn.innerHTML = originalText;
            submitBtn.disabled = false;
            isSubmitting = false; // Flag'i sıfırla
        });
    });
}

// Markdown editor
function initializeMarkdownEditor() {
    const markdownTextarea = document.querySelector('.markdown-editor');
    if (!markdownTextarea) return;
    
    // Auto-resize textarea
    markdownTextarea.addEventListener('input', function() {
        this.style.height = 'auto';
        this.style.height = this.scrollHeight + 'px';
    });
    
    // Tab tuşu desteği
    markdownTextarea.addEventListener('keydown', function(e) {
        if (e.key === 'Tab') {
            e.preventDefault();
            const start = this.selectionStart;
            const end = this.selectionEnd;
            
            // Tab ekle
            this.value = this.value.substring(0, start) + '  ' + this.value.substring(end);
            
            // Cursor pozisyonunu ayarla
            this.selectionStart = this.selectionEnd = start + 2;
        }
    });
    
    // Markdown kısayolları
    markdownTextarea.addEventListener('keydown', function(e) {
        // Ctrl+B: Kalın
        if (e.ctrlKey && e.key === 'b') {
            e.preventDefault();
            insertMarkdown('**', '**');
        }
        
        // Ctrl+I: İtalik
        if (e.ctrlKey && e.key === 'i') {
            e.preventDefault();
            insertMarkdown('*', '*');
        }
        
        // Ctrl+K: Link
        if (e.ctrlKey && e.key === 'k') {
            e.preventDefault();
            insertMarkdown('[', '](url)');
        }
    });
}

// Makale kartları
function initializeArticleCards() {
    const articleCards = document.querySelectorAll('.article-card');
    
    articleCards.forEach(card => {
        // Hover efektleri
        card.addEventListener('mouseenter', function() {
            this.style.transform = 'translateY(-5px)';
        });
        
        card.addEventListener('mouseleave', function() {
            this.style.transform = 'translateY(0)';
        });
        
        // Tıklama efekti
        card.addEventListener('click', function(e) {
            // Eğer buton veya link tıklanmadıysa
            if (!e.target.closest('a, button')) {
                const link = this.querySelector('a[href]');
                if (link) {
                    window.location.href = link.href;
                }
            }
        });
    });
}

// Markdown ekleme fonksiyonu
function insertMarkdown(before, after) {
    const textarea = document.querySelector('.markdown-editor');
    if (!textarea) return;
    
    const start = textarea.selectionStart;
    const end = textarea.selectionEnd;
    const selectedText = textarea.value.substring(start, end);
    
    // Markdown ekle
    const newText = before + selectedText + after;
    textarea.value = textarea.value.substring(0, start) + newText + textarea.value.substring(end);
    
    // Cursor pozisyonunu ayarla
    const newCursorPos = start + before.length + selectedText.length;
    textarea.setSelectionRange(newCursorPos, newCursorPos);
    textarea.focus();
    
    // Auto-resize
    textarea.style.height = 'auto';
    textarea.style.height = textarea.scrollHeight + 'px';
}

// Önizleme fonksiyonu
function previewMarkdown() {
    const textarea = document.querySelector('.markdown-editor');
    if (!textarea) return;
    
    const content = textarea.value;
    const previewContent = document.getElementById('previewContent');
    
    if (content.trim()) {
        // Basit markdown parser (gerçek uygulamada marked.js kullanılabilir)
        let html = content
            .replace(/^# (.*$)/gim, '<h1>$1</h1>')
            .replace(/^## (.*$)/gim, '<h2>$1</h2>')
            .replace(/^### (.*$)/gim, '<h3>$1</h3>')
            .replace(/\*\*(.*?)\*\*/gim, '<strong>$1</strong>')
            .replace(/\*(.*?)\*/gim, '<em>$1</em>')
            .replace(/`(.*?)`/gim, '<code>$1</code>')
            .replace(/```([\s\S]*?)```/gim, '<pre><code>$1</code></pre>')
            .replace(/\[([^\]]+)\]\(([^)]+)\)/gim, '<a href="$2">$1</a>')
            .replace(/!\[([^\]]*)\]\(([^)]+)\)/gim, '<img src="$2" alt="$1">')
            .replace(/\n/gim, '<br>');
        
        previewContent.innerHTML = html;
    } else {
        previewContent.innerHTML = '<p class="text-muted">Önizleme için içerik girin...</p>';
    }
    
    // Modal'ı göster
    const modal = new bootstrap.Modal(document.getElementById('previewModal'));
    modal.show();
}

// Alert fonksiyonu
function showAlert(message, type = 'info') {
    // Mevcut alert'leri kaldır
    const existingAlerts = document.querySelectorAll('.alert-dismissible');
    existingAlerts.forEach(alert => alert.remove());
    
    // Yeni alert oluştur
    const alertDiv = document.createElement('div');
    alertDiv.className = `alert alert-${type} alert-dismissible fade show position-fixed`;
    alertDiv.style.cssText = 'top: 20px; right: 20px; z-index: 9999; min-width: 300px;';
    alertDiv.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;
    
    document.body.appendChild(alertDiv);
    
    // 5 saniye sonra otomatik kaldır
    setTimeout(() => {
        if (alertDiv.parentNode) {
            alertDiv.remove();
        }
    }, 5000);
}

// Loading state fonksiyonu
function setLoading(element, isLoading) {
    if (isLoading) {
        element.disabled = true;
        element.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Yükleniyor...';
    } else {
        element.disabled = false;
        element.innerHTML = element.dataset.originalText || 'Kaydet';
    }
}

// Form validasyonu
function validateForm(form) {
    const requiredFields = form.querySelectorAll('[required]');
    let isValid = true;
    
    requiredFields.forEach(field => {
        if (!field.value.trim()) {
            field.classList.add('is-invalid');
            isValid = false;
        } else {
            field.classList.remove('is-invalid');
        }
    });
    
    return isValid;
}

// Etiket önerileri
function initializeTagSuggestions() {
    const tagInput = document.querySelector('input[name="tags"]');
    if (!tagInput) return;
    
    const commonTags = [
        'linux', 'ubuntu', 'debian', 'centos', 'arch',
        'docker', 'kubernetes', 'nginx', 'apache',
        'python', 'javascript', 'php', 'java',
        'mysql', 'postgresql', 'mongodb', 'redis',
        'git', 'github', 'gitlab', 'jenkins',
        'security', 'networking', 'devops', 'cloud'
    ];
    
    tagInput.addEventListener('input', function() {
        const value = this.value.toLowerCase();
        const suggestions = commonTags.filter(tag => 
            tag.includes(value) && !this.value.split(',').some(existing => 
                existing.trim().toLowerCase() === tag
            )
        );
        
        // Öneri listesi göster (basit implementasyon)
        if (suggestions.length > 0 && value.length > 1) {
            console.log('Öneriler:', suggestions.slice(0, 5));
        }
    });
}

// Makale istatistikleri
function updateArticleStats() {
    // Görüntülenme sayısını artır (AJAX ile)
    const articleId = document.querySelector('[data-article-id]');
    if (articleId) {
        fetch(`/articles/${articleId.dataset.articleId}/view/`, {
            method: 'POST',
            headers: {
                'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value,
                'X-Requested-With': 'XMLHttpRequest'
            }
        }).catch(error => console.log('View count update failed:', error));
    }
}

// Keyboard shortcuts
document.addEventListener('keydown', function(e) {
    // Ctrl+Enter: Form gönder
    if (e.ctrlKey && e.key === 'Enter') {
        const form = document.querySelector('form');
        if (form && !form.querySelector('button[type="submit"]:disabled')) {
            form.submit();
        }
    }
    
    // Escape: Modal kapat
    if (e.key === 'Escape') {
        const modal = document.querySelector('.modal.show');
        if (modal) {
            const modalInstance = bootstrap.Modal.getInstance(modal);
            if (modalInstance) {
                modalInstance.hide();
            }
        }
    }
});

// Print fonksiyonu
function printArticle() {
    const articleContent = document.querySelector('.article-content');
    if (articleContent) {
        const printWindow = window.open('', '_blank');
        printWindow.document.write(`
            <html>
                <head>
                    <title>${document.title}</title>
                    <style>
                        body { font-family: Arial, sans-serif; line-height: 1.6; margin: 40px; }
                        h1, h2, h3 { color: #333; }
                        code { background: #f4f4f4; padding: 2px 4px; }
                        pre { background: #f4f4f4; padding: 10px; overflow-x: auto; }
                        blockquote { border-left: 4px solid #ddd; padding-left: 20px; margin: 20px 0; }
                    </style>
                </head>
                <body>
                    ${articleContent.innerHTML}
                </body>
            </html>
        `);
        printWindow.document.close();
        printWindow.print();
    }
}

// Sosyal paylaşım
function shareArticle(platform) {
    const url = window.location.href;
    const title = document.title;
    
    let shareUrl = '';
    
    switch(platform) {
        case 'twitter':
            shareUrl = `https://twitter.com/intent/tweet?url=${encodeURIComponent(url)}&text=${encodeURIComponent(title)}`;
            break;
        case 'facebook':
            shareUrl = `https://www.facebook.com/sharer/sharer.php?u=${encodeURIComponent(url)}`;
            break;
        case 'linkedin':
            shareUrl = `https://www.linkedin.com/sharing/share-offsite/?url=${encodeURIComponent(url)}`;
            break;
        case 'copy':
            navigator.clipboard.writeText(url).then(() => {
                showAlert('Link kopyalandı!', 'success');
            });
            return;
    }
    
    if (shareUrl) {
        window.open(shareUrl, '_blank', 'width=600,height=400');
    }
}

// Kod blokları için kopyala butonları
function initializeCodeCopyButtons() {
    const codeBlocks = document.querySelectorAll('pre code');
    
    codeBlocks.forEach((codeBlock, index) => {
        // Sadece pre > code yapısındaki blokları al (inline code'ları değil)
        const preElement = codeBlock.parentElement;
        if (preElement.tagName === 'PRE') {
            // Kopyala butonu oluştur
            const copyBtn = document.createElement('button');
            copyBtn.className = 'copy-code-btn';
            copyBtn.innerHTML = '<i class="fas fa-copy"></i> Kopyala';
            copyBtn.setAttribute('data-code-index', index);
            
            // Butonu pre elementine ekle
            preElement.style.position = 'relative';
            preElement.appendChild(copyBtn);
            
            // Kopyalama event listener'ı ekle
            copyBtn.addEventListener('click', function() {
                copyCodeToClipboard(codeBlock.textContent, this);
            });
        }
    });
}

// Kodu panoya kopyala
function copyCodeToClipboard(code, button) {
    // Modern clipboard API kullan
    if (navigator.clipboard && window.isSecureContext) {
        navigator.clipboard.writeText(code).then(() => {
            showCopySuccess(button);
        }).catch(err => {
            console.error('Clipboard API hatası:', err);
            fallbackCopyTextToClipboard(code, button);
        });
    } else {
        // Fallback için eski yöntem
        fallbackCopyTextToClipboard(code, button);
    }
}

// Fallback kopyalama yöntemi
function fallbackCopyTextToClipboard(text, button) {
    const textArea = document.createElement('textarea');
    textArea.value = text;
    
    // Ekrandan gizle
    textArea.style.position = 'fixed';
    textArea.style.left = '-999999px';
    textArea.style.top = '-999999px';
    document.body.appendChild(textArea);
    
    // Seç ve kopyala
    textArea.focus();
    textArea.select();
    
    try {
        const successful = document.execCommand('copy');
        if (successful) {
            showCopySuccess(button);
        } else {
            showCopyError(button);
        }
    } catch (err) {
        console.error('Fallback kopyalama hatası:', err);
        showCopyError(button);
    }
    
    // Geçici textarea'yı kaldır
    document.body.removeChild(textArea);
}

// Kopyalama başarı mesajı
function showCopySuccess(button) {
    const originalText = button.innerHTML;
    button.innerHTML = '<i class="fas fa-check"></i> Kopyalandı!';
    button.classList.add('copied');
    
    // 2 saniye sonra orijinal haline döndür
    setTimeout(() => {
        button.innerHTML = originalText;
        button.classList.remove('copied');
    }, 2000);
    
    // Başarı mesajı göster
    showAlert('Kod panoya kopyalandı!', 'success');
}

// Kopyalama hata mesajı
function showCopyError(button) {
    const originalText = button.innerHTML;
    button.innerHTML = '<i class="fas fa-times"></i> Hata!';
    button.style.backgroundColor = '#f8d7da';
    button.style.color = '#721c24';
    button.style.borderColor = '#f5c6cb';
    
    // 2 saniye sonra orijinal haline döndür
    setTimeout(() => {
        button.innerHTML = originalText;
        button.style.backgroundColor = '';
        button.style.color = '';
        button.style.borderColor = '';
    }, 2000);
    
    // Hata mesajı göster
    showAlert('Kod kopyalanamadı!', 'danger');
}

// Export fonksiyonları
window.articlesJS = {
    insertMarkdown,
    previewMarkdown,
    showAlert,
    setLoading,
    validateForm,
    printArticle,
    shareArticle,
    initializeCodeCopyButtons,
    copyCodeToClipboard
};
