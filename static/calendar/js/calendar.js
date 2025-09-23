/**
 * Takvim JavaScript Fonksiyonları
 */

let calendar;
let currentSettings = {};

/**
 * Takvimi başlatır
 */
function initializeCalendar(config) {
    console.log('Calendar initialization started with config:', config);
    console.log('FullCalendar available:', typeof FullCalendar !== 'undefined');
    console.log('FullCalendar plugins available:', {
        dayGrid: typeof FullCalendar.dayGridPlugin !== 'undefined',
        timeGrid: typeof FullCalendar.timeGridPlugin !== 'undefined',
        list: typeof FullCalendar.listPlugin !== 'undefined',
        interaction: typeof FullCalendar.interactionPlugin !== 'undefined'
    });
    currentSettings = config.settings;
    
    // FullCalendar'ı başlat
    const calendarEl = document.getElementById('calendar');
    
    if (!calendarEl) {
        console.error('Calendar element not found!');
        return;
    }
    
    console.log('Calendar element found:', calendarEl);
    
    calendar = new FullCalendar.Calendar(calendarEl, {
        initialView: config.viewType || 'dayGridMonth',
        initialDate: config.currentDate,
        locale: 'tr',
        firstDay: 1, // Pazartesi ile başla
        headerToolbar: {
            left: 'prev,next today',
            center: 'title',
            right: 'dayGridMonth,timeGridWeek,timeGridDay,listWeek'
        },
        buttonText: {
            today: 'Bugün',
            month: 'Ay',
            week: 'Hafta',
            day: 'Gün',
            list: 'Liste'
        },
        events: {
            url: config.eventsUrl,
            method: 'GET',
            extraParams: function() {
                return {
                    // FullCalendar otomatik olarak start ve end parametrelerini ekler
                };
            },
            failure: function() {
                showAlert('Etkinlikler yüklenirken bir hata oluştu.', 'danger');
            }
        },
        eventClick: function(info) {
            // Varsayılan davranışı engelle
            info.jsEvent.preventDefault();
            info.jsEvent.stopPropagation();
            
            // Etkinliğin URL'si varsa o sayfaya yönlendir
            if (info.event.url) {
                // Sadece yeni sekmede aç
                window.open(info.event.url, '_blank', 'noopener,noreferrer');
            } else {
                // URL yoksa modal göster
                showEventModal(info.event);
            }
        },
        eventDidMount: function(info) {
            // Etkinlik stillerini uygula
            applyEventStyles(info.event, info.el);
        },
        dateClick: function(info) {
            // Tarihe tıklama işlemi (gelecekte etkinlik ekleme için kullanılabilir)
            console.log('Tarihe tıklandı:', info.dateStr);
        },
        eventDrop: function(info) {
            // Etkinlik sürükleme işlemi (gelecekte tarih değiştirme için kullanılabilir)
            console.log('Etkinlik taşındı:', info.event.title, info.event.start);
        },
        eventResize: function(info) {
            // Etkinlik boyutlandırma işlemi (gelecekte süre değiştirme için kullanılabilir)
            console.log('Etkinlik boyutu değiştirildi:', info.event.title, info.event.start, info.event.end);
        },
        loading: function(bool) {
            if (bool) {
                showLoading();
            } else {
                hideLoading();
            }
        },
        height: 'auto',
        aspectRatio: 1.8,
        nowIndicator: true,
        dayMaxEvents: 3,
        moreLinkClick: 'popover',
        eventDisplay: 'block',
        dayCellContent: function(info) {
            return info.dayNumberText;
        }
    });
    
    calendar.render();
    console.log('Calendar rendered successfully');
    
    // Event listener'ları ekle
    setupEventListeners(config);
}

/**
 * Event listener'ları kurar
 */
function setupEventListeners(config) {
    // Görünüm butonları
    document.querySelectorAll('.view-btn').forEach(button => {
        button.addEventListener('click', function() {
            const view = this.dataset.view;
            if (view === 'agenda') {
                window.location.href = '/calendar/agenda/';
            } else {
                // View isimlerini FullCalendar 6.x formatına çevir
                let fullCalendarView = view;
                if (view === 'month') fullCalendarView = 'dayGridMonth';
                else if (view === 'week') fullCalendarView = 'timeGridWeek';
                else if (view === 'day') fullCalendarView = 'timeGridDay';
                
                calendar.changeView(fullCalendarView);
                updateActiveViewButton(view);
            }
        });
    });
    
    // Filtreler artık otomatik yetki kontrolü ile yapılıyor
    
    // Navigasyon butonları
    const prevBtn = document.getElementById('prev-btn');
    const nextBtn = document.getElementById('next-btn');
    const todayBtn = document.getElementById('today-btn');
    const todayBtnHeader = document.getElementById('today-btn-header');
    
    if (prevBtn) {
        prevBtn.addEventListener('click', function() {
            calendar.prev();
        });
    }
    
    if (nextBtn) {
        nextBtn.addEventListener('click', function() {
            calendar.next();
        });
    }
    
    if (todayBtn) {
        todayBtn.addEventListener('click', function() {
            calendar.today();
        });
    }
    
    if (todayBtnHeader) {
        todayBtnHeader.addEventListener('click', function() {
            calendar.today();
        });
    }
    
    // Senkronize et butonu
    const syncBtn = document.getElementById('sync-btn');
    if (syncBtn) {
        syncBtn.addEventListener('click', function() {
            syncCalendar();
        });
    }
}

/**
 * Aktif görünüm butonunu günceller
 */
function updateActiveViewButton(view) {
    document.querySelectorAll('.view-btn').forEach(button => {
        button.classList.remove('active');
        if (button.dataset.view === view) {
            button.classList.add('active');
        }
    });
}

// Filtreler artık otomatik yetki kontrolü ile yapılıyor

/**
 * Etkinlik stillerini uygular
 */
function applyEventStyles(event, element) {
    const eventType = event.extendedProps.event_type;
    const priority = event.extendedProps.priority;
    const isCompleted = event.extendedProps.is_completed;
    const isOverdue = event.extendedProps.is_overdue;
    
    // Öncelik sınıfını ekle
    element.classList.add(`priority-${priority}`);
    
    // Tamamlanmış etkinlikler
    if (isCompleted) {
        element.classList.add('completed');
    }
    
    // Süresi geçmiş etkinlikler
    if (isOverdue) {
        element.classList.add('overdue');
    }
    
    // Etkinlik türüne göre renk ayarla
    let color = event.color;
    switch (eventType) {
        case 'task':
            color = currentSettings.taskColor || '#28a745';
            break;
        case 'project':
            color = currentSettings.projectColor || '#007bff';
            break;
        case 'payment':
            color = currentSettings.paymentColor || '#ffc107';
            break;
        case 'deadline':
            color = currentSettings.deadlineColor || '#dc3545';
            break;
        case 'meeting':
            color = currentSettings.meetingColor || '#6f42c1';
            break;
    }
    
    element.style.backgroundColor = color;
    element.style.borderColor = color;
}

/**
 * Etkinlik modalını gösterir
 */
function showEventModal(event) {
    const modal = document.getElementById('eventModal');
    const modalTitle = document.getElementById('eventModalLabel');
    const eventDetails = document.getElementById('event-details');
    const viewEventBtn = document.getElementById('view-event-btn');
    
    // Modal başlığını güncelle
    modalTitle.textContent = event.title;
    
    // Etkinlik detaylarını oluştur
    const details = createEventDetails(event);
    eventDetails.innerHTML = details;
    
    // Detay butonunu ayarla
    if (event.url) {
        viewEventBtn.style.display = 'inline-block';
        viewEventBtn.onclick = function() {
            window.open(event.url, '_blank');
        };
    } else {
        viewEventBtn.style.display = 'none';
    }
    
    // Modalı göster
    const bsModal = new bootstrap.Modal(modal);
    bsModal.show();
}

/**
 * Etkinlik detaylarını oluşturur
 */
function createEventDetails(event) {
    const startDate = new Date(event.start);
    const endDate = event.end ? new Date(event.end) : null;
    const isCompleted = event.extendedProps.is_completed;
    const isOverdue = event.extendedProps.is_overdue;
    const priority = event.extendedProps.priority;
    const eventType = event.extendedProps.event_type;
    const description = event.extendedProps.description;
    
    let html = `
        <div class="event-detail-info">
            <div class="row">
                <div class="col-md-6">
                    <h6><i class="fas fa-calendar"></i> Tarih Bilgileri</h6>
                    <p><strong>Başlangıç:</strong> ${formatDateTime(startDate)}</p>
                    ${endDate ? `<p><strong>Bitiş:</strong> ${formatDateTime(endDate)}</p>` : ''}
                    ${event.allDay ? '<p><span class="badge bg-info">Tüm Gün</span></p>' : ''}
                </div>
                <div class="col-md-6">
                    <h6><i class="fas fa-info-circle"></i> Etkinlik Bilgileri</h6>
                    <p><strong>Tür:</strong> ${getEventTypeDisplay(eventType)}</p>
                    <p><strong>Öncelik:</strong> ${getPriorityDisplay(priority)}</p>
                    <p><strong>Durum:</strong> ${getStatusDisplay(isCompleted, isOverdue)}</p>
                </div>
            </div>
    `;
    
    if (description) {
        html += `
            <div class="mt-3">
                <h6><i class="fas fa-align-left"></i> Açıklama</h6>
                <p>${description}</p>
            </div>
        `;
    }
    
    html += '</div>';
    
    return html;
}

/**
 * Tarih formatlar
 */
function formatDateTime(date) {
    return date.toLocaleDateString('tr-TR', {
        year: 'numeric',
        month: 'long',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
    });
}

/**
 * Etkinlik türü görüntüleme metnini döndürür
 */
function getEventTypeDisplay(eventType) {
    const types = {
        'task': 'Görev',
        'project': 'Proje',
        'payment': 'Ödeme',
        'deadline': 'Son Tarih',
        'meeting': 'Toplantı',
        'milestone': 'Kilometre Taşı',
        'custom': 'Özel Etkinlik'
    };
    return types[eventType] || eventType;
}

/**
 * Öncelik görüntüleme metnini döndürür
 */
function getPriorityDisplay(priority) {
    const priorities = {
        'urgent': '<span class="badge bg-danger">Acil</span>',
        'high': '<span class="badge bg-warning">Yüksek</span>',
        'medium': '<span class="badge bg-info">Orta</span>',
        'low': '<span class="badge bg-secondary">Düşük</span>'
    };
    return priorities[priority] || priority;
}

/**
 * Durum görüntüleme metnini döndürür
 */
function getStatusDisplay(isCompleted, isOverdue) {
    if (isCompleted) {
        return '<span class="badge bg-success"><i class="fas fa-check"></i> Tamamlandı</span>';
    } else if (isOverdue) {
        return '<span class="badge bg-danger"><i class="fas fa-exclamation-triangle"></i> Süresi Geçmiş</span>';
    } else {
        return '<span class="badge bg-primary">Devam Ediyor</span>';
    }
}

/**
 * Takvimi senkronize eder
 */
function syncCalendar() {
    showLoading();
    
    fetch('/calendar/sync/', {
        method: 'POST',
        headers: {
            'X-CSRFToken': getCSRFToken(),
            'Content-Type': 'application/json',
        },
    })
    .then(response => response.json())
    .then(data => {
        hideLoading();
        if (data.success) {
            showAlert('Takvim başarıyla senkronize edildi.', 'success');
            calendar.refetchEvents();
        } else {
            showAlert('Senkronizasyon sırasında bir hata oluştu: ' + data.error, 'danger');
        }
    })
    .catch(error => {
        hideLoading();
        console.error('Error:', error);
        showAlert('Senkronizasyon sırasında bir hata oluştu.', 'danger');
    });
}

/**
 * Etkinlik tamamlama durumunu değiştirir
 */
function toggleEventCompletion(eventId, isCompleted) {
    fetch(`/calendar/api/events/${eventId}/toggle/`, {
        method: 'POST',
        headers: {
            'X-CSRFToken': getCSRFToken(),
            'Content-Type': 'application/json',
        },
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showAlert('Etkinlik durumu güncellendi.', 'success');
            calendar.refetchEvents();
        } else {
            showAlert('Durum güncellenirken bir hata oluştu: ' + data.error, 'danger');
        }
    })
    .catch(error => {
        console.error('Error:', error);
        showAlert('Durum güncellenirken bir hata oluştu.', 'danger');
    });
}

/**
 * CSRF token'ını alır
 */
function getCSRFToken() {
    const token = document.querySelector('[name=csrfmiddlewaretoken]');
    return token ? token.value : '';
}

/**
 * Yükleme göstergesini gösterir
 */
function showLoading() {
    const overlay = document.getElementById('loading-overlay');
    if (overlay) {
        overlay.style.display = 'flex';
    }
}

/**
 * Yükleme göstergesini gizler
 */
function hideLoading() {
    const overlay = document.getElementById('loading-overlay');
    if (overlay) {
        overlay.style.display = 'none';
    }
}

/**
 * Alert mesajı gösterir
 */
function showAlert(message, type = 'info') {
    // Bootstrap toast kullanarak alert göster
    const toastContainer = document.getElementById('toast-container') || createToastContainer();
    
    const toast = document.createElement('div');
    toast.className = `toast align-items-center text-white bg-${type} border-0`;
    toast.setAttribute('role', 'alert');
    toast.setAttribute('aria-live', 'assertive');
    toast.setAttribute('aria-atomic', 'true');
    
    toast.innerHTML = `
        <div class="d-flex">
            <div class="toast-body">
                ${message}
            </div>
            <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast" aria-label="Close"></button>
        </div>
    `;
    
    toastContainer.appendChild(toast);
    
    const bsToast = new bootstrap.Toast(toast);
    bsToast.show();
    
    // Toast'ı otomatik olarak kaldır
    toast.addEventListener('hidden.bs.toast', function() {
        toast.remove();
    });
}

/**
 * Toast container oluşturur
 */
function createToastContainer() {
    const container = document.createElement('div');
    container.id = 'toast-container';
    container.className = 'toast-container position-fixed top-0 end-0 p-3';
    container.style.zIndex = '9999';
    document.body.appendChild(container);
    return container;
}

/**
 * Sayfa yüklendiğinde çalışır
 */
document.addEventListener('DOMContentLoaded', function() {
    // Tooltip'leri başlat
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
    
    // Popover'ları başlat
    const popoverTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="popover"]'));
    popoverTriggerList.map(function (popoverTriggerEl) {
        return new bootstrap.Popover(popoverTriggerEl);
    });
});

/**
 * Klavye kısayolları
 */
document.addEventListener('keydown', function(e) {
    // Ctrl/Cmd + K ile bugüne git
    if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
        e.preventDefault();
        if (calendar) {
            calendar.today();
        }
    }
    
    // Ctrl/Cmd + R ile yenile
    if ((e.ctrlKey || e.metaKey) && e.key === 'r') {
        e.preventDefault();
        if (calendar) {
            calendar.refetchEvents();
        }
    }
    
    // Escape ile modal kapat
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

/**
 * Pencere boyutu değiştiğinde takvimi yeniden boyutlandır
 */
window.addEventListener('resize', function() {
    if (calendar) {
        calendar.updateSize();
    }
});

/**
 * Sayfa görünürlüğü değiştiğinde etkinlikleri yenile
 */
document.addEventListener('visibilitychange', function() {
    if (!document.hidden && calendar) {
        calendar.refetchEvents();
    }
});
