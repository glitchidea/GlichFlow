// Sellers Module JavaScript

document.addEventListener('DOMContentLoaded', function() {
    // Initialize tooltips
    var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    var tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });

    // Initialize popovers
    var popoverTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="popover"]'));
    var popoverList = popoverTriggerList.map(function (popoverTriggerEl) {
        return new bootstrap.Popover(popoverTriggerEl);
    });

    // File upload drag and drop
    initializeFileUpload();
    
    // Price calculator
    initializePriceCalculator();
    
    // Form validation
    initializeFormValidation();
    
    // Auto-save functionality
    initializeAutoSave();
    
    // Custom service toggle
    initializeCustomServiceToggle();
    
    // Prevent double modal opening
    preventDoubleModalOpening();
    
    // Initialize modal file upload
    initializeModalFileUpload();

    // Initialize non-modal file type linkage (accept + hint)
    initializeInlineFileTypeBinding();
});

// File Upload Functions
function initializeFileUpload() {
    const fileInputs = document.querySelectorAll('input[type="file"]');
    
    fileInputs.forEach(input => {
        // If paired with a sibling select[name="file_type"], bind accept and validate
        const container = input.closest('form') || document;
        const siblingSelect = container.querySelector('select[name="file_type"]');
        if (siblingSelect) {
            updateFileInputAccept(siblingSelect.value, input);
        }
        // Sadece file-upload-area class'ı olan container'lar için drag&drop ekle
        const dropContainer = input.closest('.file-upload-area');
        
        if (dropContainer) {
            // Drag and drop events
            dropContainer.addEventListener('dragover', handleDragOver);
            dropContainer.addEventListener('dragleave', handleDragLeave);
            dropContainer.addEventListener('drop', handleDrop);
            
            // Click to upload - sadece container'a tıklandığında, input'a değil
            dropContainer.addEventListener('click', (e) => {
                // Eğer tıklanan element input'un kendisi değilse
                if (e.target !== input) {
                    e.preventDefault();
                    input.click();
                }
            });
        }
        
        // File selection change - sadece modal dışındaki input'lar için
        if (!input.closest('.modal')) {
            input.addEventListener('change', function(e) {
                const fileTypeSelect = (this.closest('form') || document).querySelector('select[name="file_type"]');
                const selectedFileType = fileTypeSelect ? fileTypeSelect.value : null;
                handleFileSelect(e, selectedFileType);
            });
        }
    });
    
    // Modal form submit işlemi artık initializeModalFileUpload() fonksiyonunda yapılıyor
}

function handleDragOver(e) {
    e.preventDefault();
    e.currentTarget.classList.add('dragover');
}

function handleDragLeave(e) {
    e.preventDefault();
    e.currentTarget.classList.remove('dragover');
}

function handleDrop(e) {
    e.preventDefault();
    e.currentTarget.classList.remove('dragover');
    
    const files = e.dataTransfer.files;
    const input = e.currentTarget.querySelector('input[type="file"]');
    
    if (input && files.length > 0) {
        input.files = files;
        handleFileSelect({ target: input });
    }
}

function handleFileSelect(e, selectedFileType = null) {
    const file = e.target.files[0];
    const container = e.target.closest('.file-upload-area') || e.target.parentElement;
    
    if (file && container) {
        // Update file name display
        const fileNameDisplay = container.querySelector('.file-name-display');
        if (fileNameDisplay) {
            fileNameDisplay.textContent = file.name;
        }
        
        // Show file size
        const fileSizeDisplay = container.querySelector('.file-size-display');
        if (fileSizeDisplay) {
            fileSizeDisplay.textContent = formatFileSize(file.size);
        }
        
        // Validate file type - modal dışındaki input'lar için kategoriye göre validasyon
        if (!validateFileType(file, selectedFileType)) {
            const fileTypeName = getFileTypeName(selectedFileType);
            showAlert(`Bu dosya türü "${fileTypeName}" kategorisi için desteklenmiyor. Lütfen uygun bir dosya seçin.`, 'danger');
            e.target.value = '';
            return;
        }
        
        // Validate file size (100MB limit)
        if (file.size > 100 * 1024 * 1024) {
            showAlert('Dosya boyutu 100MB\'dan büyük olamaz.', 'danger');
            e.target.value = '';
            return;
        }
    }
}

// Modal file upload işlemi
function initializeModalFileUpload() {
    const fileUploadModal = document.getElementById('fileUploadModal');
    
    if (fileUploadModal) {
        // Modal açıldığında form'u temizle
        fileUploadModal.addEventListener('show.bs.modal', function() {
            const form = this.querySelector('form');
            if (form) {
                form.reset();
                // Form reset edildikten sonra file input'u da temizle
                const fileInput = form.querySelector('input[type="file"]');
                if (fileInput) {
                    fileInput.value = '';
                }
                
                // Clear validation error
                const validationAlert = this.querySelector('#file-validation-alert');
                if (validationAlert) {
                    validationAlert.classList.add('d-none');
                }
                
                // Dosya türü seçimini al ve hint'i güncelle
                const fileTypeSelect = form.querySelector('select[name="file_type"]');
                if (fileTypeSelect) {
                    updateFileInputAccept(fileTypeSelect.value, fileInput);
                    updateFileTypeHint(fileTypeSelect.value);
                }
            }
        });
        
        // Modal kapatıldığında form'u temizle
        fileUploadModal.addEventListener('hidden.bs.modal', function() {
            const form = this.querySelector('form');
            if (form) {
                form.reset();
                const fileInput = form.querySelector('input[type="file"]');
                if (fileInput) {
                    fileInput.value = '';
                }
                
                // Clear validation error
                const validationAlert = this.querySelector('#file-validation-alert');
                if (validationAlert) {
                    validationAlert.classList.add('d-none');
                }
                
                // Dosya türü seçimini al ve hint'i güncelle
                const fileTypeSelect = form.querySelector('select[name="file_type"]');
                if (fileTypeSelect) {
                    updateFileInputAccept(fileTypeSelect.value, fileInput);
                    updateFileTypeHint(fileTypeSelect.value);
                }
            }
        });
        
        // Form submit işlemini kontrol et
        const form = fileUploadModal.querySelector('form');
        if (form) {
            form.addEventListener('submit', function(e) {
                const fileInput = this.querySelector('input[type="file"]');
                if (fileInput && !fileInput.files.length) {
                    e.preventDefault();
                    showAlert('Lütfen bir dosya seçin.', 'warning');
                    return false;
                }
                
                // Form submit edilirken loading göster
                const submitBtn = this.querySelector('button[type="submit"]');
                if (submitBtn) {
                    submitBtn.disabled = true;
                    submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Yükleniyor...';
                }
            });
        }
        
        // Modal içindeki file input için özel event listener
        const modalFileInput = fileUploadModal.querySelector('input[type="file"]');
        if (modalFileInput) {
            modalFileInput.addEventListener('change', function(e) {
                const file = e.target.files[0];
                const validationAlert = fileUploadModal.querySelector('#file-validation-alert');
                const validationMessage = fileUploadModal.querySelector('#file-validation-message');
                
                // Hide any previous validation errors
                if (validationAlert) {
                    validationAlert.classList.add('d-none');
                }
                
                if (file) {
                    // Dosya türü seçimini al
                    const fileTypeSelect = fileUploadModal.querySelector('select[name="file_type"]');
                    const selectedFileType = fileTypeSelect ? fileTypeSelect.value : null;
                    
                    // Dosya seçildiğinde validasyon yap
                    if (!validateFileType(file, selectedFileType)) {
                        const fileTypeName = getFileTypeName(selectedFileType);
                        const errorMessage = `Bu dosya türü "${fileTypeName}" kategorisi için desteklenmiyor. Lütfen uygun bir dosya seçin.`;
                        
                        // Show error in modal alert
                        if (validationAlert && validationMessage) {
                            validationMessage.textContent = errorMessage;
                            validationAlert.classList.remove('d-none');
                        }
                        
                        e.target.value = '';
                        return;
                    }
                    
                    if (file.size > 100 * 1024 * 1024) {
                        const errorMessage = 'Dosya boyutu 100MB\'dan büyük olamaz.';
                        
                        // Show error in modal alert
                        if (validationAlert && validationMessage) {
                            validationMessage.textContent = errorMessage;
                            validationAlert.classList.remove('d-none');
                        }
                        
                        e.target.value = '';
                        return;
                    }
                    
                    // File is valid - show success message
                    showAlert('Dosya seçildi: ' + file.name, 'success');
                }
            });
        }
        
        // Dosya türü değiştiğinde file input'un accept attribute'unu güncelle
        const fileTypeSelect = fileUploadModal.querySelector('select[name="file_type"]');
        if (fileTypeSelect && modalFileInput) {
            fileTypeSelect.addEventListener('change', function() {
                updateFileInputAccept(this.value, modalFileInput);
                updateFileTypeHint(this.value);
                
                // Clear any validation errors when file type changes
                const validationAlert = fileUploadModal.querySelector('#file-validation-alert');
                if (validationAlert) {
                    validationAlert.classList.add('d-none');
                }
                
                // Clear file input when type changes
                modalFileInput.value = '';
            });
            
            // İlk yüklemede de güncelle
            updateFileInputAccept(fileTypeSelect.value, modalFileInput);
            updateFileTypeHint(fileTypeSelect.value);
        }
    }
}

// Bind inline (non-modal) file type select to accept + hint block if present
function initializeInlineFileTypeBinding() {
    const inlineSelects = document.querySelectorAll('form select[name="file_type"]');
    inlineSelects.forEach(select => {
        const form = select.closest('form');
        if (!form) return;
        const fileInput = form.querySelector('input[type="file"]');
        if (!fileInput) return;
        // Initial apply
        updateFileInputAccept(select.value, fileInput);
        // Hook change
        select.addEventListener('change', function() {
            updateFileInputAccept(this.value, fileInput);
            updateFileTypeHint(this.value);
        });
    });
}

function validateFileType(file, fileType = null) {
    // Dosya türü seçimine göre izin verilen uzantıları belirle
    let allowedTypes = [];
    
    if (fileType) {
        switch (fileType) {
            case 'source_code':
                allowedTypes = [
                    // Arşiv dosyaları (her zaman desteklenir)
                    '.zip', '.rar', '.7z', '.tar', '.gz',
                    // Kaynak kod dosyaları
                    '.py', '.js', '.html', '.css', '.php', '.java', '.cpp', '.c', '.h', '.hpp',
                    '.cs', '.rb', '.go', '.rs', '.swift', '.kt', '.scala', '.ts', '.tsx', '.jsx',
                    '.vue', '.svelte', '.dart', '.r', '.m', '.pl', '.sh', '.bash', '.ps1',
                    // Konfigürasyon dosyaları
                    '.yml', '.yaml', '.json', '.xml', '.toml', '.ini', '.cfg', '.conf',
                    '.env', '.gitignore', '.dockerfile', '.dockerignore', '.gitattributes',
                    // Veritabanı dosyaları
                    '.sql', '.sqlite', '.db', '.sqlite3',
                    // Diğer
                    '.md', '.txt', '.log', '.license', '.readme'
                ];
                break;
                
            case 'design':
                allowedTypes = [
                    // Arşiv dosyaları
                    '.zip', '.rar', '.7z', '.tar', '.gz',
                    // Tasarım dosyaları
                    '.psd', '.ai', '.sketch', '.fig', '.xd', '.indd', '.eps', '.pdf',
                    // Görsel dosyaları
                    '.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.svg', '.ico',
                    // Video dosyaları
                    '.mp4', '.webm', '.ogg', '.mov', '.avi', '.mkv',
                    // Diğer
                    '.md', '.txt'
                ];
                break;
                
            case 'documentation':
                allowedTypes = [
                    // Arşiv dosyaları
                    '.zip', '.rar', '.7z', '.tar', '.gz',
                    // Dokümantasyon dosyaları
                    '.md', '.markdown', '.txt', '.rtf', '.doc', '.docx', '.pdf',
                    '.ppt', '.pptx', '.odt', '.ods', '.odp',
                    // Görsel dosyaları (diagramlar için)
                    '.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.svg',
                    // Diğer
                    '.json', '.xml', '.yaml', '.yml'
                ];
                break;
                
            case 'database':
                allowedTypes = [
                    // Arşiv dosyaları
                    '.zip', '.rar', '.7z', '.tar', '.gz',
                    // Veritabanı dosyaları
                    '.sql', '.sqlite', '.sqlite3', '.db', '.mdb', '.accdb',
                    '.dump', '.backup', '.bak',
                    // Konfigürasyon dosyaları
                    '.yml', '.yaml', '.json', '.xml', '.ini', '.cfg', '.conf',
                    // Diğer
                    '.md', '.txt', '.log'
                ];
                break;
                
            case 'assets':
                allowedTypes = [
                    // Arşiv dosyaları
                    '.zip', '.rar', '.7z', '.tar', '.gz',
                    // Görsel dosyaları
                    '.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.svg', '.ico', '.tiff', '.tif',
                    // Video dosyaları
                    '.mp4', '.webm', '.ogg', '.mov', '.avi', '.mkv', '.flv', '.wmv', '.m4v',
                    // Ses dosyaları
                    '.mp3', '.wav', '.opus', '.m4a', '.aac', '.flac', '.ogg', '.wma',
                    // Diğer medya
                    '.gif', '.webp'
                ];
                break;
                
            case 'other':
            default:
                // Tüm dosya türlerini destekle
                allowedTypes = [
                    '.zip', '.rar', '.7z', '.tar', '.gz',
                    '.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.svg',
                    '.mp4', '.webm', '.ogg', '.mov',
                    '.mp3', '.wav', '.opus', '.m4a', '.aac', '.flac',
                    '.txt', '.log', '.csv', '.json', '.md', '.markdown',
                    '.docx', '.pptx', '.pdf', '.py', '.js', '.html', '.css',
                    '.sql', '.sqlite', '.db', '.yml', '.yaml', '.env', '.gitignore'
                ];
                break;
        }
    } else {
        // Eğer dosya türü belirtilmemişse, tüm türleri destekle
        allowedTypes = [
            '.zip', '.rar', '.7z', '.tar', '.gz',
            '.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.svg',
            '.mp4', '.webm', '.ogg', '.mov',
            '.mp3', '.wav', '.opus', '.m4a', '.aac', '.flac',
            '.txt', '.log', '.csv', '.json', '.md', '.markdown',
            '.docx', '.pptx', '.pdf', '.py', '.js', '.html', '.css',
            '.sql', '.sqlite', '.db', '.yml', '.yaml', '.env', '.gitignore'
        ];
    }
    
    const fileName = file.name.toLowerCase();
    return allowedTypes.some(type => fileName.endsWith(type));
}

function formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';
    
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

function getFileTypeName(fileType) {
    const fileTypeNames = {
        'source_code': 'Kaynak Kod',
        'design': 'Tasarım Dosyaları',
        'documentation': 'Dokümantasyon',
        'database': 'Veritabanı',
        'assets': 'Varlıklar',
        'other': 'Diğer'
    };
    return fileTypeNames[fileType] || 'Bilinmeyen';
}

function updateFileInputAccept(fileType, fileInput) {
    let acceptTypes = '';
    
    switch (fileType) {
        case 'source_code':
            acceptTypes = '.zip,.rar,.7z,.tar,.gz,.py,.js,.html,.css,.php,.java,.cpp,.c,.h,.hpp,.cs,.rb,.go,.rs,.swift,.kt,.scala,.ts,.tsx,.jsx,.vue,.svelte,.dart,.r,.m,.pl,.sh,.bash,.ps1,.yml,.yaml,.json,.xml,.toml,.ini,.cfg,.conf,.env,.gitignore,.dockerfile,.dockerignore,.gitattributes,.sql,.sqlite,.db,.sqlite3,.md,.txt,.log,.license,.readme';
            break;
            
        case 'design':
            acceptTypes = '.zip,.rar,.7z,.tar,.gz,.psd,.ai,.sketch,.fig,.xd,.indd,.eps,.pdf,.jpg,.jpeg,.png,.gif,.webp,.bmp,.svg,.ico,.mp4,.webm,.ogg,.mov,.avi,.mkv,.md,.txt';
            break;
            
        case 'documentation':
            acceptTypes = '.zip,.rar,.7z,.tar,.gz,.md,.markdown,.txt,.rtf,.doc,.docx,.pdf,.ppt,.pptx,.odt,.ods,.odp,.jpg,.jpeg,.png,.gif,.webp,.bmp,.svg,.json,.xml,.yaml,.yml';
            break;
            
        case 'database':
            acceptTypes = '.zip,.rar,.7z,.tar,.gz,.sql,.sqlite,.sqlite3,.db,.mdb,.accdb,.dump,.backup,.bak,.yml,.yaml,.json,.xml,.ini,.cfg,.conf,.md,.txt,.log';
            break;
            
        case 'assets':
            acceptTypes = '.zip,.rar,.7z,.tar,.gz,.jpg,.jpeg,.png,.gif,.webp,.bmp,.svg,.ico,.tiff,.tif,.mp4,.webm,.ogg,.mov,.avi,.mkv,.flv,.wmv,.m4v,.mp3,.wav,.opus,.m4a,.aac,.flac,.ogg,.wma';
            break;
            
        case 'other':
        default:
            acceptTypes = '.zip,.rar,.7z,.tar,.gz,.jpg,.jpeg,.png,.gif,.webp,.bmp,.svg,.mp4,.webm,.ogg,.mov,.mp3,.wav,.opus,.m4a,.aac,.flac,.txt,.log,.csv,.json,.md,.markdown,.docx,.pptx,.pdf,.py,.js,.html,.css,.sql,.sqlite,.db,.yml,.yaml,.env,.gitignore';
            break;
    }
    
    fileInput.setAttribute('accept', acceptTypes);
}

function updateFileTypeHint(fileType) {
    const hintContent = document.getElementById('hint-content');
    if (!hintContent) return;
    
    let hintText = '📁 Arşiv: ZIP, RAR, 7Z, TAR, GZ (her kategori için)<br>';
    
    switch (fileType) {
        case 'source_code':
            hintText += '💻 Kaynak Kod: PY, JS, HTML, CSS, PHP, JAVA, CPP, C, H, CS, RB, GO, RS, SWIFT, KT, SCALA, TS, TSX, JSX, VUE, SVELTE, DART, R, M, PL, SH, BASH, PS1<br>';
            hintText += '⚙️ Konfigürasyon: YML, YAML, JSON, XML, TOML, INI, CFG, CONF, ENV, GITIGNORE, DOCKERFILE<br>';
            hintText += '🗄️ Veritabanı: SQL, SQLITE, DB, SQLITE3<br>';
            hintText += '📄 Diğer: MD, TXT, LOG, LICENSE, README';
            break;
            
        case 'design':
            hintText += '🎨 Tasarım: PSD, AI, SKETCH, FIG, XD, INDD, EPS, PDF<br>';
            hintText += '🖼️ Görsel: JPG, PNG, GIF, WEBP, BMP, SVG, ICO<br>';
            hintText += '🎥 Video: MP4, WEBM, OGG, MOV, AVI, MKV<br>';
            hintText += '📄 Diğer: MD, TXT';
            break;
            
        case 'documentation':
            hintText += '📚 Dokümantasyon: MD, MARKDOWN, TXT, RTF, DOC, DOCX, PDF, PPT, PPTX, ODT, ODS, ODP<br>';
            hintText += '🖼️ Görsel: JPG, PNG, GIF, WEBP, BMP, SVG (diagramlar için)<br>';
            hintText += '📄 Diğer: JSON, XML, YAML, YML';
            break;
            
        case 'database':
            hintText += '🗄️ Veritabanı: SQL, SQLITE, SQLITE3, DB, MDB, ACCDB, DUMP, BACKUP, BAK<br>';
            hintText += '⚙️ Konfigürasyon: YML, YAML, JSON, XML, INI, CFG, CONF<br>';
            hintText += '📄 Diğer: MD, TXT, LOG';
            break;
            
        case 'assets':
            hintText += '🖼️ Görsel: JPG, PNG, GIF, WEBP, BMP, SVG, ICO, TIFF, TIF<br>';
            hintText += '🎥 Video: MP4, WEBM, OGG, MOV, AVI, MKV, FLV, WMV, M4V<br>';
            hintText += '🎵 Ses: MP3, WAV, OPUS, M4A, AAC, FLAC, OGG, WMA';
            break;
            
        case 'other':
        default:
            hintText += '📄 Tüm dosya türleri desteklenir';
            break;
    }
    
    hintContent.innerHTML = hintText;
}

// Price Calculator Functions
function initializePriceCalculator() {
    const basePackageSelect = document.getElementById('base-package');
    const additionalCostsInput = document.getElementById('additional-costs');
    
    if (basePackageSelect) {
        basePackageSelect.addEventListener('change', calculatePrice);
    }
    
    if (additionalCostsInput) {
        additionalCostsInput.addEventListener('input', calculatePrice);
    }
    
    // Extra services checkboxes
    const extraServiceCheckboxes = document.querySelectorAll('input[name="extra_services"]');
    extraServiceCheckboxes.forEach(checkbox => {
        checkbox.addEventListener('change', calculatePrice);
    });
}

function calculatePrice() {
    const basePackageSelect = document.getElementById('base-package');
    const additionalCostsInput = document.getElementById('additional-costs');
    const totalPriceDisplay = document.getElementById('total-price');
    
    let totalPrice = 0;
    
    // Base package price
    if (basePackageSelect && basePackageSelect.value) {
        const selectedOption = basePackageSelect.options[basePackageSelect.selectedIndex];
        const basePrice = parseFloat(selectedOption.dataset.price) || 0;
        totalPrice += basePrice;
    }
    
    // Additional costs
    if (additionalCostsInput) {
        const additionalCosts = parseFloat(additionalCostsInput.value) || 0;
        totalPrice += additionalCosts;
    }
    
    // Extra services
    const extraServiceCheckboxes = document.querySelectorAll('input[name="extra_services"]:checked');
    extraServiceCheckboxes.forEach(checkbox => {
        const servicePrice = parseFloat(checkbox.dataset.price) || 0;
        totalPrice += servicePrice;
    });
    
    // Update total price display
    if (totalPriceDisplay) {
        totalPriceDisplay.textContent = totalPrice.toFixed(2) + ' ₺';
    }
    
    return totalPrice;
}

// Form Validation Functions
function initializeFormValidation() {
    const forms = document.querySelectorAll('form[data-validate]');
    
    forms.forEach(form => {
        form.addEventListener('submit', function(e) {
            if (!validateForm(form)) {
                e.preventDefault();
                e.stopPropagation();
            }
            form.classList.add('was-validated');
        });
    });
}

function validateForm(form) {
    let isValid = true;
    const requiredFields = form.querySelectorAll('[required]');
    
    requiredFields.forEach(field => {
        if (!field.value.trim()) {
            isValid = false;
            showFieldError(field, 'Bu alan zorunludur.');
        } else {
            clearFieldError(field);
        }
    });
    
    // Email validation
    const emailFields = form.querySelectorAll('input[type="email"]');
    emailFields.forEach(field => {
        if (field.value && !isValidEmail(field.value)) {
            isValid = false;
            showFieldError(field, 'Geçerli bir e-posta adresi girin.');
        }
    });
    
    return isValid;
}

function showFieldError(field, message) {
    clearFieldError(field);
    
    field.classList.add('is-invalid');
    
    const errorDiv = document.createElement('div');
    errorDiv.className = 'invalid-feedback';
    errorDiv.textContent = message;
    
    field.parentNode.appendChild(errorDiv);
}

function clearFieldError(field) {
    field.classList.remove('is-invalid');
    
    const errorDiv = field.parentNode.querySelector('.invalid-feedback');
    if (errorDiv) {
        errorDiv.remove();
    }
}

function isValidEmail(email) {
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return emailRegex.test(email);
}

// Auto-save Functions
function initializeAutoSave() {
    const autoSaveForms = document.querySelectorAll('form[data-autosave]');
    
    autoSaveForms.forEach(form => {
        const inputs = form.querySelectorAll('input, textarea, select');
        
        inputs.forEach(input => {
            input.addEventListener('change', debounce(() => {
                autoSaveForm(form);
            }, 2000));
        });
    });
}

function autoSaveForm(form) {
    const formData = new FormData(form);
    const url = form.action || window.location.href;
    
    fetch(url, {
        method: 'POST',
        body: formData,
        headers: {
            'X-CSRFToken': getCSRFToken(),
            'X-Requested-With': 'XMLHttpRequest'
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showAutoSaveIndicator();
        }
    })
    .catch(error => {
        console.error('Auto-save error:', error);
    });
}

function getCSRFToken() {
    const token = document.querySelector('[name=csrfmiddlewaretoken]');
    return token ? token.value : '';
}

function showAutoSaveIndicator() {
    const indicator = document.getElementById('autosave-indicator');
    if (indicator) {
        indicator.style.display = 'block';
        setTimeout(() => {
            indicator.style.display = 'none';
        }, 3000);
    }
}

// Utility Functions
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

function showAlert(message, type = 'info') {
    const alertContainer = document.getElementById('alert-container') || createAlertContainer();
    
    const alertDiv = document.createElement('div');
    alertDiv.className = `alert alert-${type} alert-dismissible fade show`;
    alertDiv.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;
    
    alertContainer.appendChild(alertDiv);
    
    // Auto-remove after 5 seconds
    setTimeout(() => {
        if (alertDiv.parentNode) {
            alertDiv.remove();
        }
    }, 5000);
}

function createAlertContainer() {
    const container = document.createElement('div');
    container.id = 'alert-container';
    container.className = 'position-fixed top-0 end-0 p-3';
    container.style.zIndex = '9999';
    document.body.appendChild(container);
    return container;
}

// AJAX Functions
function makeAjaxRequest(url, data, method = 'POST') {
    return fetch(url, {
        method: method,
        body: JSON.stringify(data),
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCSRFToken(),
            'X-Requested-With': 'XMLHttpRequest'
        }
    })
    .then(response => response.json());
}

// Package price fetch
function fetchPackagePrice(packageId) {
    return makeAjaxRequest('/sellers/api/package-price/', { package_id: packageId });
}

// Extra service price fetch
function fetchExtraServicePrice(serviceId, basePrice, quantity) {
    return makeAjaxRequest('/sellers/api/extra-service-price/', {
        service_id: serviceId,
        base_price: basePrice,
        quantity: quantity
    });
}

// Modal Functions
function openModal(modalId) {
    const modal = new bootstrap.Modal(document.getElementById(modalId));
    modal.show();
}

function closeModal(modalId) {
    const modal = bootstrap.Modal.getInstance(document.getElementById(modalId));
    if (modal) {
        modal.hide();
    }
}

// Table Functions
function sortTable(table, column, direction = 'asc') {
    const tbody = table.querySelector('tbody');
    const rows = Array.from(tbody.querySelectorAll('tr'));
    
    rows.sort((a, b) => {
        const aVal = a.cells[column].textContent.trim();
        const bVal = b.cells[column].textContent.trim();
        
        if (direction === 'asc') {
            return aVal.localeCompare(bVal);
        } else {
            return bVal.localeCompare(aVal);
        }
    });
    
    rows.forEach(row => tbody.appendChild(row));
}

// Export Functions
function exportToCSV(tableId, filename) {
    const table = document.getElementById(tableId);
    const rows = table.querySelectorAll('tr');
    let csv = [];
    
    rows.forEach(row => {
        const cells = row.querySelectorAll('td, th');
        const rowData = Array.from(cells).map(cell => {
            return '"' + cell.textContent.replace(/"/g, '""') + '"';
        });
        csv.push(rowData.join(','));
    });
    
    const csvContent = csv.join('\n');
    const blob = new Blob([csvContent], { type: 'text/csv' });
    const url = window.URL.createObjectURL(blob);
    
    const a = document.createElement('a');
    a.href = url;
    a.download = filename || 'export.csv';
    a.click();
    
    window.URL.revokeObjectURL(url);
}

// Search Functions
function initializeSearch() {
    const searchInputs = document.querySelectorAll('input[data-search]');
    
    searchInputs.forEach(input => {
        input.addEventListener('input', debounce(() => {
            performSearch(input);
        }, 300));
    });
}

function performSearch(input) {
    const searchTerm = input.value.toLowerCase();
    const targetSelector = input.dataset.search;
    const targets = document.querySelectorAll(targetSelector);
    
    targets.forEach(target => {
        const text = target.textContent.toLowerCase();
        if (text.includes(searchTerm)) {
            target.style.display = '';
        } else {
            target.style.display = 'none';
        }
    });
}

// Initialize search on page load
document.addEventListener('DOMContentLoaded', function() {
    initializeSearch();
    initializeProjectAutoFill();
});

// Project Auto-Fill Functions
function initializeProjectAutoFill() {
    const linkedProjectSelect = document.getElementById('id_linked_project');
    
    if (linkedProjectSelect) {
        linkedProjectSelect.addEventListener('change', function() {
            const projectId = this.value;
            
            if (projectId) {
                fetchProjectData(projectId);
            } else {
                // Clear auto-filled data if no project selected
                clearAutoFilledData();
            }
        });
    }
}

function fetchProjectData(projectId) {
    const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]').value;
    
    fetch('/sellers/api/project-data/', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': csrfToken
        },
        body: JSON.stringify({
            project_id: projectId
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            autoFillProjectData(data.data);
            showNotification('Proje verileri otomatik olarak dolduruldu!', 'success');
        } else {
            showNotification('Proje verileri alınamadı: ' + data.error, 'error');
        }
    })
    .catch(error => {
        console.error('Error:', error);
        showNotification('Proje verileri alınırken hata oluştu!', 'error');
    });
}

function autoFillProjectData(projectData) {
    // Proje adını doldur
    const projectNameField = document.getElementById('id_project_name');
    if (projectNameField && projectData.name && !projectNameField.value) {
        projectNameField.value = projectData.name;
    }
    
    // Proje açıklamasını doldur
    const projectDescField = document.getElementById('id_project_description');
    if (projectDescField && projectData.description && !projectDescField.value) {
        projectDescField.value = projectData.description;
    }
    
    // Başlangıç tarihini doldur
    const startDateField = document.getElementById('id_start_date');
    if (startDateField && projectData.start_date && !startDateField.value) {
        startDateField.value = projectData.start_date;
    }
    
    // Bitiş tarihini doldur
    const endDateField = document.getElementById('id_end_date');
    if (endDateField && projectData.end_date && !endDateField.value) {
        endDateField.value = projectData.end_date;
    }
    
    // Bütçe bilgisini doldur (isteğe bağlı)
    const budgetField = document.getElementById('id_base_price');
    if (budgetField && projectData.budget && !budgetField.value) {
        budgetField.value = projectData.budget;
    }
    
    // Proje türünü tahmin et (açıklamadan)
    const projectTypeField = document.getElementById('id_project_type');
    if (projectTypeField && projectData.description && !projectTypeField.value) {
        const description = projectData.description.toLowerCase();
        if (description.includes('web') || description.includes('site')) {
            projectTypeField.value = 'Web Site';
        } else if (description.includes('saas') || description.includes('yazılım')) {
            projectTypeField.value = 'SaaS';
        } else if (description.includes('mobil') || description.includes('app')) {
            projectTypeField.value = 'Mobil Uygulama';
        } else if (description.includes('e-ticaret') || description.includes('ecommerce')) {
            projectTypeField.value = 'E-ticaret';
        }
    }
    
    // Bilgi kutusu göster
    showProjectInfo(projectData);
}

function clearAutoFilledData() {
    // Otomatik doldurulan verileri temizle (isteğe bağlı)
    // Bu fonksiyon kullanıcı isterse proje seçimini kaldırdığında verileri temizleyebilir
}

function showProjectInfo(projectData) {
    // Proje bilgilerini gösteren bir bilgi kutusu oluştur
    const infoContainer = document.getElementById('project-info-container');
    
    if (infoContainer) {
        infoContainer.innerHTML = `
            <div class="alert alert-info">
                <h6><i class="fas fa-info-circle"></i> Bağlı Proje Bilgileri</h6>
                <div class="row">
                    <div class="col-md-6">
                        <strong>Proje Yöneticisi:</strong> ${projectData.manager || 'Belirtilmemiş'}<br>
                        <strong>Durum:</strong> ${getStatusText(projectData.status)}<br>
                        <strong>Öncelik:</strong> ${getPriorityText(projectData.priority)}
                    </div>
                    <div class="col-md-6">
                        <strong>Bütçe:</strong> ${projectData.budget ? projectData.budget + ' TL' : 'Belirtilmemiş'}<br>
                        <strong>Maliyet:</strong> ${projectData.cost ? projectData.cost + ' TL' : 'Belirtilmemiş'}
                    </div>
                </div>
                <small class="text-muted">
                    <i class="fas fa-lightbulb"></i> 
                    Proje verileri otomatik olarak dolduruldu. İsterseniz düzenleyebilirsiniz.
                </small>
            </div>
        `;
    }
}

function getStatusText(status) {
    const statusMap = {
        'not_started': 'Başlamadı',
        'in_progress': 'Devam Ediyor',
        'on_hold': 'Beklemede',
        'completed': 'Tamamlandı',
        'cancelled': 'İptal Edildi'
    };
    return statusMap[status] || status;
}

function getPriorityText(priority) {
    const priorityMap = {
        'low': 'Düşük',
        'medium': 'Orta',
        'high': 'Yüksek',
        'urgent': 'Acil'
    };
    return priorityMap[priority] || priority;
}

function showNotification(message, type = 'info') {
    // Bootstrap toast veya alert kullanarak bildirim göster
    const toastContainer = document.getElementById('toast-container') || createToastContainer();
    
    const toast = document.createElement('div');
    toast.className = `toast align-items-center text-white bg-${type === 'error' ? 'danger' : type} border-0`;
    toast.setAttribute('role', 'alert');
    toast.innerHTML = `
        <div class="d-flex">
            <div class="toast-body">
                ${message}
            </div>
            <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
        </div>
    `;
    
    toastContainer.appendChild(toast);
    
    const bsToast = new bootstrap.Toast(toast);
    bsToast.show();
    
    // Toast'ı otomatik olarak kaldır
    toast.addEventListener('hidden.bs.toast', () => {
        toast.remove();
    });
}

function createToastContainer() {
    const container = document.createElement('div');
    container.id = 'toast-container';
    container.className = 'toast-container position-fixed top-0 end-0 p-3';
    container.style.zIndex = '9999';
    document.body.appendChild(container);
    return container;
}

// Custom Service Toggle Functions
function initializeCustomServiceToggle() {
    const useCustomServiceCheckbox = document.getElementById('use_custom_service');
    const extraServiceColumn = document.getElementById('extra_service_column');
    const customServiceColumn = document.getElementById('custom_service_column');
    const extraServiceSelect = document.getElementById('id_extra_service');
    const customServiceInput = document.getElementById('id_custom_service_name');
    
    if (useCustomServiceCheckbox && extraServiceColumn && customServiceColumn) {
        // İlk durumu ayarla
        toggleCustomServiceFields();
        
        // Checkbox değişikliklerini dinle
        useCustomServiceCheckbox.addEventListener('change', toggleCustomServiceFields);
    }
    
    function toggleCustomServiceFields() {
        if (useCustomServiceCheckbox.checked) {
            // Özel hizmet modu
            extraServiceColumn.style.display = 'none';
            customServiceColumn.style.display = 'block';
            if (extraServiceSelect) extraServiceSelect.required = false;
            if (customServiceInput) customServiceInput.required = true;
        } else {
            // Mevcut hizmet modu
            extraServiceColumn.style.display = 'block';
            customServiceColumn.style.display = 'none';
            if (extraServiceSelect) extraServiceSelect.required = true;
            if (customServiceInput) customServiceInput.required = false;
        }
    }
}

// Prevent Double Modal Opening
function preventDoubleModalOpening() {
    // Modal açma butonlarını kontrol et
    const modalTriggers = document.querySelectorAll('[data-bs-toggle="modal"]');
    
    modalTriggers.forEach(trigger => {
        // Önceki event listener'ları temizle
        trigger.removeEventListener('click', handleModalTriggerClick);
        trigger.addEventListener('click', handleModalTriggerClick);
    });
}

function handleModalTriggerClick(e) {
    const targetModalId = this.getAttribute('data-bs-target');
    const targetModal = document.querySelector(targetModalId);
    
    if (targetModal) {
        // Eğer modal zaten açıksa, yeni açma işlemini engelle
        if (targetModal.classList.contains('show')) {
            e.preventDefault();
            e.stopPropagation();
            return false;
        }
        
        // Modal açılmadan önce diğer açık modal'ları kapat
        const openModals = document.querySelectorAll('.modal.show');
        openModals.forEach(modal => {
            if (modal !== targetModal) {
                const bsModal = bootstrap.Modal.getInstance(modal);
                if (bsModal) {
                    bsModal.hide();
                }
            }
        });
    }
}
