// Gelir Raporu JavaScript Fonksiyonları

document.addEventListener('DOMContentLoaded', function() {
    // Sayfa yüklendiğinde animasyonları başlat
    initializeAnimations();
    
    // Filtreleme formunu başlat
    initializeFilterForm();
    
    // Grafikleri başlat
    initializeCharts();
    
    // Export fonksiyonlarını başlat
    initializeExportFunctions();
    
    // Responsive davranışları başlat
    initializeResponsive();
});

// Animasyonları başlat
function initializeAnimations() {
    const cards = document.querySelectorAll('.card');
    cards.forEach((card, index) => {
        card.style.opacity = '0';
        card.style.transform = 'translateY(30px)';
        
        setTimeout(() => {
            card.style.transition = 'all 0.6s ease';
            card.style.opacity = '1';
            card.style.transform = 'translateY(0)';
        }, index * 100);
    });
}

// Filtreleme formunu başlat
function initializeFilterForm() {
    const filterType = document.getElementById('filter_type');
    const form = document.getElementById('filterForm');
    
    if (filterType) {
        filterType.addEventListener('change', toggleFilterOptions);
    }
    
    if (form) {
        form.addEventListener('submit', function(e) {
            showLoadingSpinner();
        });
    }
    
    // Tarih validasyonu
    const startDate = document.getElementById('start_date');
    const endDate = document.getElementById('end_date');
    
    if (startDate && endDate) {
        startDate.addEventListener('change', validateDateRange);
        endDate.addEventListener('change', validateDateRange);
    }
}

// Filtreleme seçeneklerini toggle et
function toggleFilterOptions() {
    const filterType = document.getElementById('filter_type').value;
    const monthlyFilter = document.getElementById('monthly_filter');
    const yearFilter = document.getElementById('year_filter');
    const dateRangeFilter = document.getElementById('date_range_filter');
    const endDateFilter = document.getElementById('end_date_filter');
    
    // Tüm filtreleri gizle
    [monthlyFilter, yearFilter, dateRangeFilter, endDateFilter].forEach(filter => {
        if (filter) {
            filter.style.display = 'none';
            filter.style.opacity = '0';
        }
    });
    
    // Seçilen filtreye göre göster
    setTimeout(() => {
        if (filterType === 'monthly') {
            if (monthlyFilter) {
                monthlyFilter.style.display = 'block';
                monthlyFilter.style.opacity = '1';
            }
            if (yearFilter) {
                yearFilter.style.display = 'block';
                yearFilter.style.opacity = '1';
            }
        } else if (filterType === 'date_range') {
            if (dateRangeFilter) {
                dateRangeFilter.style.display = 'block';
                dateRangeFilter.style.opacity = '1';
            }
            if (endDateFilter) {
                endDateFilter.style.display = 'block';
                endDateFilter.style.opacity = '1';
            }
        }
    }, 200);
}

// Tarih aralığı validasyonu
function validateDateRange() {
    const startDate = document.getElementById('start_date');
    const endDate = document.getElementById('end_date');
    
    if (startDate && endDate && startDate.value && endDate.value) {
        const start = new Date(startDate.value);
        const end = new Date(endDate.value);
        
        if (start > end) {
            showNotification('Başlangıç tarihi bitiş tarihinden sonra olamaz!', 'error');
            endDate.value = '';
        }
    }
}

// Grafikleri başlat
function initializeCharts() {
    // Chart.js konfigürasyonu
    Chart.defaults.font.family = "'Inter', sans-serif";
    Chart.defaults.color = '#6c757d';
    
    // Responsive grafikler
    window.addEventListener('resize', debounce(() => {
        Chart.helpers.each(Chart.instances, (chart) => {
            chart.resize();
        });
    }, 250));
}

// Export fonksiyonlarını başlat
function initializeExportFunctions() {
    // PDF export butonu
    const pdfBtn = document.querySelector('[onclick="exportToPDF()"]');
    if (pdfBtn) {
        pdfBtn.addEventListener('click', exportToPDF);
    }
    
    // Excel export butonu
    const excelBtn = document.querySelector('[onclick="exportToExcel()"]');
    if (excelBtn) {
        excelBtn.addEventListener('click', exportToExcel);
    }
}

// PDF export
function exportToPDF() {
    showLoadingSpinner();
    
    setTimeout(() => {
        const { jsPDF } = window.jspdf;
        const doc = new jsPDF();
        
        // Başlık
        doc.setFontSize(20);
        doc.text('Gelir Raporu', 20, 20);
        
        // Tarih
        doc.setFontSize(10);
        doc.text(`Rapor Tarihi: ${new Date().toLocaleDateString('tr-TR')}`, 20, 30);
        
        // İstatistikler
        doc.setFontSize(12);
        doc.text('İstatistikler:', 20, 50);
        
        const totalRevenue = document.querySelector('.stats-card .card-value')?.textContent || '0 ₺';
        const totalProjects = document.querySelectorAll('.stats-card .card-value')[1]?.textContent || '0';
        const completedProjects = document.querySelectorAll('.stats-card .card-value')[2]?.textContent || '0';
        
        doc.text(`Toplam Gelir: ${totalRevenue}`, 20, 65);
        doc.text(`Toplam Proje: ${totalProjects}`, 20, 75);
        doc.text(`Tamamlanan Proje: ${completedProjects}`, 20, 85);
        
        // Tablo başlığı
        doc.text('Son Satışlar:', 20, 105);
        
        // Tablo verileri
        const table = document.querySelector('.revenue-table .table tbody');
        if (table) {
            const rows = table.querySelectorAll('tr');
            let yPosition = 120;
            
            rows.forEach((row, index) => {
                if (yPosition > 280) {
                    doc.addPage();
                    yPosition = 20;
                }
                
                const cells = row.querySelectorAll('td');
                if (cells.length >= 4) {
                    const projectName = cells[0].textContent.trim();
                    const customer = cells[1].textContent.trim();
                    const status = cells[2].textContent.trim();
                    const price = cells[3].textContent.trim();
                    const date = cells[4].textContent.trim();
                    
                    doc.setFontSize(8);
                    doc.text(`${index + 1}. ${projectName}`, 20, yPosition);
                    doc.text(`Müşteri: ${customer}`, 20, yPosition + 5);
                    doc.text(`Durum: ${status}`, 20, yPosition + 10);
                    doc.text(`Fiyat: ${price}`, 20, yPosition + 15);
                    doc.text(`Tarih: ${date}`, 20, yPosition + 20);
                    
                    yPosition += 30;
                }
            });
        }
        
        doc.save('gelir-raporu.pdf');
        hideLoadingSpinner();
        showNotification('PDF raporu başarıyla indirildi!', 'success');
    }, 1000);
}

// Excel export
function exportToExcel() {
    showLoadingSpinner();
    
    setTimeout(() => {
        const data = [
            ['Proje Adı', 'Müşteri', 'Durum', 'Fiyat', 'Tarih']
        ];
        
        const table = document.querySelector('.revenue-table .table tbody');
        if (table) {
            const rows = table.querySelectorAll('tr');
            rows.forEach(row => {
                const cells = row.querySelectorAll('td');
                if (cells.length >= 5) {
                    data.push([
                        cells[0].textContent.trim(),
                        cells[1].textContent.trim(),
                        cells[2].textContent.trim(),
                        cells[3].textContent.trim(),
                        cells[4].textContent.trim()
                    ]);
                }
            });
        }
        
        const ws = XLSX.utils.aoa_to_sheet(data);
        const wb = XLSX.utils.book_new();
        XLSX.utils.book_append_sheet(wb, ws, 'Gelir Raporu');
        
        XLSX.writeFile(wb, 'gelir-raporu.xlsx');
        hideLoadingSpinner();
        showNotification('Excel raporu başarıyla indirildi!', 'success');
    }, 1000);
}

// Responsive davranışları başlat
function initializeResponsive() {
    // Grafik boyutlarını ayarla
    adjustChartSizes();
    
    // Window resize event
    window.addEventListener('resize', debounce(() => {
        adjustChartSizes();
    }, 250));
}

// Grafik boyutlarını ayarla
function adjustChartSizes() {
    const charts = document.querySelectorAll('canvas');
    charts.forEach(chart => {
        const container = chart.closest('.chart-area, .chart-pie');
        if (container) {
            const containerWidth = container.offsetWidth;
            if (containerWidth < 300) {
                chart.style.maxHeight = '200px';
            } else {
                chart.style.maxHeight = '300px';
            }
        }
    });
}

// Loading spinner göster
function showLoadingSpinner() {
    const spinner = document.createElement('div');
    spinner.id = 'loading-spinner';
    spinner.className = 'loading-spinner';
    spinner.style.cssText = `
        position: fixed;
        top: 50%;
        left: 50%;
        transform: translate(-50%, -50%);
        z-index: 9999;
        background: rgba(255, 255, 255, 0.9);
        padding: 20px;
        border-radius: 10px;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.1);
    `;
    
    const spinnerInner = document.createElement('div');
    spinnerInner.className = 'loading-spinner';
    spinnerInner.style.cssText = `
        width: 40px;
        height: 40px;
        border: 4px solid #f3f3f3;
        border-top: 4px solid #667eea;
        border-radius: 50%;
        animation: spin 1s linear infinite;
    `;
    
    spinner.appendChild(spinnerInner);
    document.body.appendChild(spinner);
}

// Loading spinner gizle
function hideLoadingSpinner() {
    const spinner = document.getElementById('loading-spinner');
    if (spinner) {
        spinner.remove();
    }
}

// Bildirim göster
function showNotification(message, type = 'info') {
    const notification = document.createElement('div');
    notification.className = `alert alert-${type} alert-dismissible fade show`;
    notification.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        z-index: 9999;
        min-width: 300px;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.1);
    `;
    
    notification.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;
    
    document.body.appendChild(notification);
    
    // 5 saniye sonra otomatik kapat
    setTimeout(() => {
        if (notification.parentNode) {
            notification.remove();
        }
    }, 5000);
}

// Debounce fonksiyonu
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

// Sayı formatla
function formatNumber(num) {
    return new Intl.NumberFormat('tr-TR').format(num);
}

// Para formatla
function formatCurrency(amount) {
    return new Intl.NumberFormat('tr-TR', {
        style: 'currency',
        currency: 'TRY'
    }).format(amount);
}

// Tarih formatla
function formatDate(date) {
    return new Intl.DateTimeFormat('tr-TR').format(new Date(date));
}

// Grafik renk paleti
const chartColors = {
    primary: '#667eea',
    secondary: '#764ba2',
    success: '#11998e',
    info: '#38ef7d',
    warning: '#f093fb',
    danger: '#f5576c',
    light: '#f8f9fa',
    dark: '#2c3e50'
};

// Grafik seçenekleri
const chartOptions = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
        legend: {
            position: 'bottom',
            labels: {
                usePointStyle: true,
                padding: 20
            }
        },
        tooltip: {
            backgroundColor: 'rgba(0, 0, 0, 0.8)',
            titleColor: '#fff',
            bodyColor: '#fff',
            borderColor: '#667eea',
            borderWidth: 1,
            cornerRadius: 8,
            displayColors: true
        }
    },
    scales: {
        y: {
            beginAtZero: true,
            grid: {
                color: 'rgba(0, 0, 0, 0.1)'
            },
            ticks: {
                callback: function(value) {
                    return formatNumber(value);
                }
            }
        },
        x: {
            grid: {
                color: 'rgba(0, 0, 0, 0.1)'
            }
        }
    }
};
