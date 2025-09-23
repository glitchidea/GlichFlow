// Base JavaScript for GlichFlow

document.addEventListener('DOMContentLoaded', function() {
    // Toggle sidebar
    const sidebarCollapse = document.getElementById('sidebarCollapse');
    if (sidebarCollapse) {
        sidebarCollapse.addEventListener('click', function() {
            document.getElementById('sidebar').classList.toggle('collapsed');
            document.getElementById('content').classList.toggle('expanded');
        });
    }
    
    // Initialize tooltips
    var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    var tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
});

// Okunmamış mesaj sayısını al
function updateUnreadCount() {
    // URL'yi dinamik olarak oluştur
    var url = window.location.origin + '/communications/get_unread_count/';
    $.ajax({
        url: url,
        type: 'GET',
        dataType: 'json',
        success: function(data) {
            // Mesaj sayacı güncelleme
            if (data.unread_message_count > 0) {
                $('#unreadMessageCount').text(data.unread_message_count).show();
            } else {
                $('#unreadMessageCount').hide();
            }
            
            // Bildirim sayacı güncelleme
            if (data.unread_notification_count > 0) {
                $('#unreadNotificationCount').text(data.unread_notification_count).show();
            } else {
                $('#unreadNotificationCount').hide();
            }
        }
    });
}

// Son bildirimleri al
function loadLatestNotifications() {
    // URL'yi dinamik olarak oluştur
    var url = window.location.origin + '/communications/notifications/';
    $.ajax({
        url: url,
        type: 'GET',
        dataType: 'html',
        success: function(data) {
            // HTML'den bildirimleri çıkar
            var parser = new DOMParser();
            var htmlDoc = parser.parseFromString(data, 'text/html');
            var notifications = htmlDoc.querySelectorAll('.list-group-item');
            
            var notificationItems = document.getElementById('notificationItems');
            notificationItems.innerHTML = '';
            
            if (notifications.length > 0) {
                // En son 5 bildirimi göster
                var count = Math.min(notifications.length, 5);
                for (var i = 0; i < count; i++) {
                    var notification = notifications[i];
                    var title = notification.querySelector('h6').textContent;
                    var content = notification.querySelector('p').textContent;
                    var href = notification.getAttribute('href');
                    var isRead = !notification.classList.contains('list-group-item-light');
                    
                    var li = document.createElement('li');
                    var a = document.createElement('a');
                    a.className = 'dropdown-item';
                    if (!isRead) {
                        a.className += ' bg-light';
                    }
                    a.href = href;
                    
                    var titleEl = document.createElement('div');
                    titleEl.className = 'fw-bold';
                    titleEl.textContent = title;
                    
                    var contentEl = document.createElement('div');
                    contentEl.className = 'small text-muted';
                    contentEl.textContent = content.length > 60 ? content.substring(0, 60) + '...' : content;
                    
                    a.appendChild(titleEl);
                    a.appendChild(contentEl);
                    li.appendChild(a);
                    notificationItems.appendChild(li);
                }
            } else {
                var li = document.createElement('li');
                var div = document.createElement('div');
                div.className = 'dropdown-item text-center text-muted p-2';
                div.textContent = 'Bildiriminiz yok';
                li.appendChild(div);
                notificationItems.appendChild(li);
            }
        },
        error: function() {
            var notificationItems = document.getElementById('notificationItems');
            notificationItems.innerHTML = '<li><div class="dropdown-item text-center text-danger p-2">Bildirimler yüklenemedi</div></li>';
        }
    });
}

// Bildirim butonuna tıklandığında son bildirimleri yükle
$(document).on('click', '#notificationsDropdown', function() {
    loadLatestNotifications();
});

// Sayfa yüklendiğinde çalıştır
$(document).ready(function() {
    updateUnreadCount();
    
    // Her 60 saniyede bir güncelle
    setInterval(updateUnreadCount, 60000);
});
