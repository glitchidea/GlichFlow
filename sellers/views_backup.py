from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden, JsonResponse
from django.contrib import messages
from django.db.models import Sum, Count, Q
from django.core.paginator import Paginator
from django.utils import timezone
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
import json

from accounts.models import CustomUser
from .models import Customer, ProjectSale, ProjectFile, SaleExtraService, AdditionalCost
from .forms import (
    CustomerForm, ProjectSaleForm, ProjectFileForm, 
    SaleExtraServiceForm, AdditionalCostForm, PriceCalculatorForm
)
from accounting.models import Package, ExtraService


def _user_is_seller(user: CustomUser) -> bool:
    """Kullanıcının seller etiketine sahip olup olmadığını kontrol eder"""
    return getattr(user, 'has_tag', lambda t: False)('seller')


def seller_required(view_func):
    """Seller etiketi gerektiren decorator"""
    def wrapper(request, *args, **kwargs):
        if not _user_is_seller(request.user):
            return HttpResponseForbidden('Bu sayfaya erişim için seller etiketi gerekir.')
        return view_func(request, *args, **kwargs)
    return wrapper


@login_required
@seller_required
def index(request):
    """Ana dashboard sayfası"""
    # İstatistikler
    total_customers = Customer.objects.filter(created_by=request.user).count()
    total_projects = ProjectSale.objects.filter(seller=request.user).count()
    active_projects = ProjectSale.objects.filter(
        seller=request.user, 
        status__in=['quoted', 'in_progress']
    ).count()
    
    # Bu ay tamamlanan projeler (kazanılan para)
    current_month = timezone.now().month
    current_year = timezone.now().year
    monthly_revenue = ProjectSale.objects.filter(
        seller=request.user,
        status='completed',
        created_at__year=current_year,
        created_at__month=current_month
    ).aggregate(total=Sum('final_price'))['total'] or 0
    
    # Toplam gelir (sadece tamamlanan projeler)
    total_revenue = ProjectSale.objects.filter(
        seller=request.user,
        status='completed'
    ).aggregate(total=Sum('final_price'))['total'] or 0
    
    # Son projeler
    recent_projects = ProjectSale.objects.filter(
        seller=request.user
    ).order_by('-created_at')[:5]
    
    # Müşteri dağılımı
    customer_stats = Customer.objects.filter(
        created_by=request.user
    ).values('customer_type').annotate(count=Count('id'))
    
    context = {
        'total_customers': total_customers,
        'total_projects': total_projects,
        'active_projects': active_projects,
        'monthly_revenue': monthly_revenue,
        'total_revenue': total_revenue,
        'recent_projects': recent_projects,
        'customer_stats': customer_stats,
    }
    return render(request, 'sellers/index.html', context)


# Müşteri Yönetimi
@login_required
@seller_required
def customer_list(request):
    """Müşteri listesi"""
    customers = Customer.objects.filter(created_by=request.user).order_by('-created_at')
    
    # Arama
    search = request.GET.get('search')
    if search:
        customers = customers.filter(
            Q(first_name__icontains=search) |
            Q(last_name__icontains=search) |
            Q(company_name__icontains=search) |
            Q(email__icontains=search)
        )
    
    # Filtreleme
    customer_type = request.GET.get('type')
    if customer_type:
        customers = customers.filter(customer_type=customer_type)
    
    # Sayfalama
    paginator = Paginator(customers, 20)
    page_number = request.GET.get('page')
    customers = paginator.get_page(page_number)
    
    context = {
        'customers': customers,
        'search': search,
        'customer_type': customer_type,
    }
    return render(request, 'sellers/customers/customer_list.html', context)


@login_required
@seller_required
def customer_detail(request, pk):
    """Müşteri detay sayfası"""
    customer = get_object_or_404(Customer, pk=pk, created_by=request.user)
    projects = customer.projects.filter(seller=request.user).order_by('-created_at')
    
    # İstatistikler
    total_projects = projects.count()
    total_revenue = projects.aggregate(total=Sum('final_price'))['total'] or 0
    active_projects = projects.filter(status__in=['won', 'in_progress']).count()
    
    context = {
        'customer': customer,
        'projects': projects,
        'total_projects': total_projects,
        'total_revenue': total_revenue,
        'active_projects': active_projects,
    }
    return render(request, 'sellers/customers/customer_detail.html', context)


@login_required
@seller_required
def customer_create(request):
    """Yeni müşteri oluşturma"""
    if request.method == 'POST':
        form = CustomerForm(request.POST)
        if form.is_valid():
            customer = form.save(commit=False)
            customer.created_by = request.user
            customer.save()
            messages.success(request, 'Müşteri başarıyla oluşturuldu.')
            return redirect('sellers:customer_detail', pk=customer.pk)
    else:
        form = CustomerForm()
    
    context = {'form': form}
    return render(request, 'sellers/customers/customer_form.html', context)


@login_required
@seller_required
def customer_update(request, pk):
    """Müşteri güncelleme"""
    customer = get_object_or_404(Customer, pk=pk, created_by=request.user)
    
    if request.method == 'POST':
        form = CustomerForm(request.POST, instance=customer)
        if form.is_valid():
            form.save()
            messages.success(request, 'Müşteri başarıyla güncellendi.')
            return redirect('sellers:customer_detail', pk=customer.pk)
    else:
        form = CustomerForm(instance=customer)
    
    context = {'form': form, 'customer': customer}
    return render(request, 'sellers/customers/customer_form.html', context)


# Proje Satış Yönetimi
@login_required
@seller_required
def sale_list(request):
    """Proje satış listesi"""
    sales = ProjectSale.objects.filter(seller=request.user).order_by('-created_at')
    
    # Arama
    search = request.GET.get('search')
    if search:
        sales = sales.filter(
            Q(project_name__icontains=search) |
            Q(customer__first_name__icontains=search) |
            Q(customer__last_name__icontains=search) |
            Q(customer__company_name__icontains=search)
        )
    
    # Filtreleme
    status = request.GET.get('status')
    if status:
        sales = sales.filter(status=status)
    
    customer_id = request.GET.get('customer')
    if customer_id:
        sales = sales.filter(customer_id=customer_id)
    
    # Sayfalama
    paginator = Paginator(sales, 20)
    page_number = request.GET.get('page')
    sales = paginator.get_page(page_number)
    
    # Filtre seçenekleri
    customers = Customer.objects.filter(created_by=request.user).order_by('company_name', 'first_name', 'last_name')
    
    context = {
        'sales': sales,
        'search': search,
        'status': status,
        'customer_id': customer_id,
        'customers': customers,
    }
    return render(request, 'sellers/sales/sale_list.html', context)


@login_required
@seller_required
def sale_detail(request, pk):
    """Proje satış detay sayfası"""
    sale = get_object_or_404(ProjectSale, pk=pk, seller=request.user)
    
    # İlişkili veriler
    project_files = sale.get_project_files()
    extra_services = sale.extra_services.all()
    additional_costs = sale.additional_costs.all()
    
    # Formlar
    file_form = ProjectFileForm()
    extra_service_form = SaleExtraServiceForm()
    additional_cost_form = AdditionalCostForm()
    
    context = {
        'sale': sale,
        'project_files': project_files,
        'extra_services': extra_services,
        'additional_costs': additional_costs,
        'file_form': file_form,
        'extra_service_form': extra_service_form,
        'additional_cost_form': additional_cost_form,
    }
    return render(request, 'sellers/sales/sale_detail.html', context)


@login_required
@seller_required
def sale_create(request):
    """Yeni proje satış oluşturma"""
    if request.method == 'POST':
        form = ProjectSaleForm(request.POST, user=request.user)
        if form.is_valid():
            sale = form.save(commit=False)
            sale.seller = request.user
            sale.save()
            messages.success(request, 'Proje satışı başarıyla oluşturuldu.')
            return redirect('sellers:sale_detail', pk=sale.pk)
    else:
        form = ProjectSaleForm(user=request.user)
    
    context = {'form': form}
    return render(request, 'sellers/sales/sale_form.html', context)


@login_required
@seller_required
def sale_update(request, pk):
    """Proje satış güncelleme"""
    sale = get_object_or_404(ProjectSale, pk=pk, seller=request.user)
    
    if request.method == 'POST':
        form = ProjectSaleForm(request.POST, instance=sale, user=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Proje satışı başarıyla güncellendi.')
            return redirect('sellers:sale_detail', pk=sale.pk)
    else:
        form = ProjectSaleForm(instance=sale, user=request.user)
    
    context = {'form': form, 'sale': sale}
    return render(request, 'sellers/sales/sale_form.html', context)


# Dosya Yönetimi
@login_required
@seller_required
def file_upload(request, sale_pk):
    """Proje dosyası yükleme"""
    sale = get_object_or_404(ProjectSale, pk=sale_pk, seller=request.user)
    
    if request.method == 'POST':
        form = ProjectFileForm(request.POST, request.FILES)
        if form.is_valid():
            file_obj = form.save(commit=False)
            file_obj.sale = sale
            file_obj.uploaded_by = request.user
            file_obj.save()
            messages.success(request, 'Dosya başarıyla yüklendi.')
            return redirect('sellers:sale_detail', pk=sale.pk)
        else:
            messages.error(request, 'Dosya yüklenirken hata oluştu.')
    
    return redirect('sellers:sale_detail', pk=sale.pk)


@login_required
@seller_required
def file_delete(request, pk):
    """Proje dosyası silme"""
    file_obj = get_object_or_404(ProjectFile, pk=pk, uploaded_by=request.user)
    sale_pk = file_obj.sale.pk
    file_obj.delete()
    messages.success(request, 'Dosya başarıyla silindi.')
    return redirect('sellers:sale_detail', pk=sale_pk)


# Fiyatlandırma
@login_required
@seller_required
def price_calculator(request, sale_pk):
    """Fiyat hesaplayıcı"""
    sale = get_object_or_404(ProjectSale, pk=sale_pk, seller=request.user)
    
    if request.method == 'POST':
        form = PriceCalculatorForm(request.POST)
        if form.is_valid():
            # Fiyat hesaplama mantığı burada olacak
            pass
    
    form = PriceCalculatorForm()
    context = {'form': form, 'sale': sale}
    return render(request, 'sellers/pricing/price_calculator.html', context)


@login_required
@seller_required
@require_http_methods(["POST"])
def add_extra_service(request, sale_pk):
    """Ek hizmet ekleme"""
    sale = get_object_or_404(ProjectSale, pk=sale_pk, seller=request.user)
    
    form = SaleExtraServiceForm(request.POST)
    if form.is_valid():
        extra_service = form.save(commit=False)
        extra_service.sale = sale
        
        # Özel hizmet kullanılıyorsa custom_service_name'ı kaydet
        if form.cleaned_data.get('use_custom_service'):
            extra_service.custom_service_name = form.cleaned_data.get('custom_service_name')
            extra_service.extra_service = None
        
        extra_service.save()
        
        # Toplam fiyatı güncelle
        sale.extra_services_total = sale.extra_services.aggregate(
            total=Sum('total_price')
        )['total'] or 0
        sale.save()
        
        messages.success(request, 'Ek hizmet başarıyla eklendi.')
    else:
        messages.error(request, 'Ek hizmet eklenirken hata oluştu.')
        for field, errors in form.errors.items():
            for error in errors:
                messages.error(request, f'{field}: {error}')
    
    return redirect('sellers:sale_detail', pk=sale.pk)


@login_required
@seller_required
@require_http_methods(["POST"])
def add_additional_cost(request, sale_pk):
    """Ek maliyet ekleme"""
    sale = get_object_or_404(ProjectSale, pk=sale_pk, seller=request.user)
    
    form = AdditionalCostForm(request.POST)
    if form.is_valid():
        additional_cost = form.save(commit=False)
        additional_cost.sale = sale
        additional_cost.save()
        
        # Toplam maliyeti güncelle
        sale.additional_costs_total = sale.additional_costs.aggregate(
            total=Sum('cost')
        )['total'] or 0
        sale.save()
        
        messages.success(request, 'Ek maliyet başarıyla eklendi.')
    else:
        messages.error(request, 'Ek maliyet eklenirken hata oluştu.')
    
    return redirect('sellers:sale_detail', pk=sale.pk)


# AJAX Endpoints
@login_required
@seller_required
@csrf_exempt
def get_package_price(request):
    """Paket fiyatını AJAX ile getir"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            package_id = data.get('package_id')
            
            if package_id:
                package = Package.objects.get(id=package_id)
                return JsonResponse({
                    'success': True,
                    'price': float(package.base_price)
                })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            })
    
    return JsonResponse({'success': False, 'error': 'Invalid request'})


@login_required
@seller_required
def revenue_report(request):
    """Gelir raporu sayfası"""
    from django.db.models import Sum, Q
    from datetime import datetime, timedelta
    import calendar
    
    # Filtreleme parametreleri
    filter_type = request.GET.get('filter_type', 'all')  # all, monthly, date_range
    month = request.GET.get('month')
    year = request.GET.get('year')
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    
    # Temel queryset
    sales = ProjectSale.objects.filter(seller=request.user)
    
    # Filtreleme
    if filter_type == 'monthly' and month and year:
        try:
            month_int = int(month)
            year_int = int(year)
            start_of_month = datetime(year_int, month_int, 1)
            if month_int == 12:
                end_of_month = datetime(year_int + 1, 1, 1) - timedelta(days=1)
            else:
                end_of_month = datetime(year_int, month_int + 1, 1) - timedelta(days=1)
            
            sales = sales.filter(
                created_at__date__gte=start_of_month.date(),
                created_at__date__lte=end_of_month.date()
            )
        except (ValueError, TypeError):
            pass
    
    elif filter_type == 'date_range' and start_date and end_date:
        try:
            start_date_obj = datetime.strptime(start_date, '%Y-%m-%d').date()
            end_date_obj = datetime.strptime(end_date, '%Y-%m-%d').date()
            sales = sales.filter(
                created_at__date__gte=start_date_obj,
                created_at__date__lte=end_date_obj
            )
        except ValueError:
            pass
    
    # İstatistikler
    total_revenue = sales.aggregate(total=Sum('final_price'))['total'] or 0
    total_projects = sales.count()
    completed_projects = sales.filter(status='completed').count()
    
    # Aylık gelir dağılımı (son 12 ay)
    monthly_data = []
    current_date = datetime.now()
    for i in range(12):
        month_date = current_date - timedelta(days=30 * i)
        month_start = month_date.replace(day=1)
        if month_date.month == 12:
            month_end = month_date.replace(year=month_date.year + 1, month=1, day=1) - timedelta(days=1)
        else:
            month_end = month_date.replace(month=month_date.month + 1, day=1) - timedelta(days=1)
        
        month_revenue = ProjectSale.objects.filter(
            seller=request.user,
            created_at__date__gte=month_start.date(),
            created_at__date__lte=month_end.date()
        ).aggregate(total=Sum('final_price'))['total'] or 0
        
        monthly_data.append({
            'month': month_start.strftime('%Y-%m'),
            'month_name': month_start.strftime('%B %Y'),
            'revenue': float(month_revenue)
        })
    
    monthly_data.reverse()  # Eski tarihten yeni tarihe sırala
    
    # Durum dağılımı
    status_stats = sales.values('status').annotate(
        count=models.Count('id'),
        total_revenue=Sum('final_price')
    ).order_by('-total_revenue')
    
    # Müşteri türü dağılımı
    customer_type_stats = sales.values('customer__customer_type').annotate(
        count=models.Count('id'),
        total_revenue=Sum('final_price')
    ).order_by('-total_revenue')
    
    context = {
        'sales': sales.order_by('-created_at')[:50],  # Son 50 satış
        'total_revenue': total_revenue,
        'total_projects': total_projects,
        'completed_projects': completed_projects,
        'monthly_data': monthly_data,
        'status_stats': status_stats,
        'customer_type_stats': customer_type_stats,
        'filter_type': filter_type,
        'month': month,
        'year': year,
        'start_date': start_date,
        'end_date': end_date,
        'months': [(i, calendar.month_name[i]) for i in range(1, 13)],
        'years': range(2020, datetime.now().year + 2),
    }
    
    return render(request, 'sellers/reports/revenue_report.html', context)


@login_required
@seller_required
@csrf_exempt
def get_project_data(request):
    """Bağlı proje verilerini AJAX ile getir"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            project_id = data.get('project_id')
            
            if project_id:
                from projects.models import Project
                project = Project.objects.get(id=project_id)
                
                # Proje verilerini döndür
                return JsonResponse({
                    'success': True,
                    'data': {
                        'name': project.name,
                        'description': project.description,
                        'start_date': project.start_date.strftime('%Y-%m-%d') if project.start_date else None,
                        'end_date': project.end_date.strftime('%Y-%m-%d') if project.end_date else None,
                        'budget': float(project.budget) if project.budget else None,
                        'cost': float(project.cost) if project.cost else None,
                        'status': project.status,
                        'priority': project.priority,
                        'manager': project.manager.get_full_name() if project.manager else None,
                    }
                })
        except Project.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': 'Proje bulunamadı'
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            })
    
    return JsonResponse({'success': False, 'error': 'Invalid request'})


@login_required
@seller_required
def revenue_report(request):
    """Gelir raporu sayfası"""
    from django.db.models import Sum, Q
    from datetime import datetime, timedelta
    import calendar
    
    # Filtreleme parametreleri
    filter_type = request.GET.get('filter_type', 'all')  # all, monthly, date_range
    month = request.GET.get('month')
    year = request.GET.get('year')
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    
    # Temel queryset
    sales = ProjectSale.objects.filter(seller=request.user)
    
    # Filtreleme
    if filter_type == 'monthly' and month and year:
        try:
            month_int = int(month)
            year_int = int(year)
            start_of_month = datetime(year_int, month_int, 1)
            if month_int == 12:
                end_of_month = datetime(year_int + 1, 1, 1) - timedelta(days=1)
            else:
                end_of_month = datetime(year_int, month_int + 1, 1) - timedelta(days=1)
            
            sales = sales.filter(
                created_at__date__gte=start_of_month.date(),
                created_at__date__lte=end_of_month.date()
            )
        except (ValueError, TypeError):
            pass
    
    elif filter_type == 'date_range' and start_date and end_date:
        try:
            start_date_obj = datetime.strptime(start_date, '%Y-%m-%d').date()
            end_date_obj = datetime.strptime(end_date, '%Y-%m-%d').date()
            sales = sales.filter(
                created_at__date__gte=start_date_obj,
                created_at__date__lte=end_date_obj
            )
        except ValueError:
            pass
    
    # İstatistikler
    total_revenue = sales.aggregate(total=Sum('final_price'))['total'] or 0
    total_projects = sales.count()
    completed_projects = sales.filter(status='completed').count()
    
    # Aylık gelir dağılımı (son 12 ay)
    monthly_data = []
    current_date = datetime.now()
    for i in range(12):
        month_date = current_date - timedelta(days=30 * i)
        month_start = month_date.replace(day=1)
        if month_date.month == 12:
            month_end = month_date.replace(year=month_date.year + 1, month=1, day=1) - timedelta(days=1)
        else:
            month_end = month_date.replace(month=month_date.month + 1, day=1) - timedelta(days=1)
        
        month_revenue = ProjectSale.objects.filter(
            seller=request.user,
            created_at__date__gte=month_start.date(),
            created_at__date__lte=month_end.date()
        ).aggregate(total=Sum('final_price'))['total'] or 0
        
        monthly_data.append({
            'month': month_start.strftime('%Y-%m'),
            'month_name': month_start.strftime('%B %Y'),
            'revenue': float(month_revenue)
        })
    
    monthly_data.reverse()  # Eski tarihten yeni tarihe sırala
    
    # Durum dağılımı
    status_stats = sales.values('status').annotate(
        count=models.Count('id'),
        total_revenue=Sum('final_price')
    ).order_by('-total_revenue')
    
    # Müşteri türü dağılımı
    customer_type_stats = sales.values('customer__customer_type').annotate(
        count=models.Count('id'),
        total_revenue=Sum('final_price')
    ).order_by('-total_revenue')
    
    context = {
        'sales': sales.order_by('-created_at')[:50],  # Son 50 satış
        'total_revenue': total_revenue,
        'total_projects': total_projects,
        'completed_projects': completed_projects,
        'monthly_data': monthly_data,
        'status_stats': status_stats,
        'customer_type_stats': customer_type_stats,
        'filter_type': filter_type,
        'month': month,
        'year': year,
        'start_date': start_date,
        'end_date': end_date,
        'months': [(i, calendar.month_name[i]) for i in range(1, 13)],
        'years': range(2020, datetime.now().year + 2),
    }
    
    return render(request, 'sellers/reports/revenue_report.html', context)


@login_required
@seller_required
@csrf_exempt
def get_extra_service_price(request):
    """Ek hizmet fiyatını AJAX ile getir"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            service_id = data.get('service_id')
            base_price = data.get('base_price', 0)
            quantity = data.get('quantity', 1)
            
            if service_id:
                service = ExtraService.objects.get(id=service_id)
                price = service.calculate_price(base_price, quantity)
                return JsonResponse({
                    'success': True,
                    'price': float(price)
                })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            })
    
    return JsonResponse({'success': False, 'error': 'Invalid request'})


@login_required
@seller_required
def revenue_report(request):
    """Gelir raporu sayfası"""
    from django.db.models import Sum, Q
    from datetime import datetime, timedelta
    import calendar
    
    # Filtreleme parametreleri
    filter_type = request.GET.get('filter_type', 'all')  # all, monthly, date_range
    month = request.GET.get('month')
    year = request.GET.get('year')
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    
    # Temel queryset
    sales = ProjectSale.objects.filter(seller=request.user)
    
    # Filtreleme
    if filter_type == 'monthly' and month and year:
        try:
            month_int = int(month)
            year_int = int(year)
            start_of_month = datetime(year_int, month_int, 1)
            if month_int == 12:
                end_of_month = datetime(year_int + 1, 1, 1) - timedelta(days=1)
            else:
                end_of_month = datetime(year_int, month_int + 1, 1) - timedelta(days=1)
            
            sales = sales.filter(
                created_at__date__gte=start_of_month.date(),
                created_at__date__lte=end_of_month.date()
            )
        except (ValueError, TypeError):
            pass
    
    elif filter_type == 'date_range' and start_date and end_date:
        try:
            start_date_obj = datetime.strptime(start_date, '%Y-%m-%d').date()
            end_date_obj = datetime.strptime(end_date, '%Y-%m-%d').date()
            sales = sales.filter(
                created_at__date__gte=start_date_obj,
                created_at__date__lte=end_date_obj
            )
        except ValueError:
            pass
    
    # İstatistikler
    total_revenue = sales.aggregate(total=Sum('final_price'))['total'] or 0
    total_projects = sales.count()
    completed_projects = sales.filter(status='completed').count()
    
    # Aylık gelir dağılımı (son 12 ay)
    monthly_data = []
    current_date = datetime.now()
    for i in range(12):
        month_date = current_date - timedelta(days=30 * i)
        month_start = month_date.replace(day=1)
        if month_date.month == 12:
            month_end = month_date.replace(year=month_date.year + 1, month=1, day=1) - timedelta(days=1)
        else:
            month_end = month_date.replace(month=month_date.month + 1, day=1) - timedelta(days=1)
        
        month_revenue = ProjectSale.objects.filter(
            seller=request.user,
            created_at__date__gte=month_start.date(),
            created_at__date__lte=month_end.date()
        ).aggregate(total=Sum('final_price'))['total'] or 0
        
        monthly_data.append({
            'month': month_start.strftime('%Y-%m'),
            'month_name': month_start.strftime('%B %Y'),
            'revenue': float(month_revenue)
        })
    
    monthly_data.reverse()  # Eski tarihten yeni tarihe sırala
    
    # Durum dağılımı
    status_stats = sales.values('status').annotate(
        count=models.Count('id'),
        total_revenue=Sum('final_price')
    ).order_by('-total_revenue')
    
    # Müşteri türü dağılımı
    customer_type_stats = sales.values('customer__customer_type').annotate(
        count=models.Count('id'),
        total_revenue=Sum('final_price')
    ).order_by('-total_revenue')
    
    context = {
        'sales': sales.order_by('-created_at')[:50],  # Son 50 satış
        'total_revenue': total_revenue,
        'total_projects': total_projects,
        'completed_projects': completed_projects,
        'monthly_data': monthly_data,
        'status_stats': status_stats,
        'customer_type_stats': customer_type_stats,
        'filter_type': filter_type,
        'month': month,
        'year': year,
        'start_date': start_date,
        'end_date': end_date,
        'months': [(i, calendar.month_name[i]) for i in range(1, 13)],
        'years': range(2020, datetime.now().year + 2),
    }
    
    return render(request, 'sellers/reports/revenue_report.html', context)


@login_required
@seller_required
@csrf_exempt
def get_project_data(request):
    """Bağlı proje verilerini AJAX ile getir"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            project_id = data.get('project_id')
            
            if project_id:
                from projects.models import Project
                project = Project.objects.get(id=project_id)
                
                # Proje verilerini döndür
                return JsonResponse({
                    'success': True,
                    'data': {
                        'name': project.name,
                        'description': project.description,
                        'start_date': project.start_date.strftime('%Y-%m-%d') if project.start_date else None,
                        'end_date': project.end_date.strftime('%Y-%m-%d') if project.end_date else None,
                        'budget': float(project.budget) if project.budget else None,
                        'cost': float(project.cost) if project.cost else None,
                        'status': project.status,
                        'priority': project.priority,
                        'manager': project.manager.get_full_name() if project.manager else None,
                    }
                })
        except Project.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': 'Proje bulunamadı'
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            })
    
    return JsonResponse({'success': False, 'error': 'Invalid request'})


@login_required
@seller_required
def revenue_report(request):
    """Gelir raporu sayfası"""
    from django.db.models import Sum, Q
    from datetime import datetime, timedelta
    import calendar
    
    # Filtreleme parametreleri
    filter_type = request.GET.get('filter_type', 'all')  # all, monthly, date_range
    month = request.GET.get('month')
    year = request.GET.get('year')
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    
    # Temel queryset
    sales = ProjectSale.objects.filter(seller=request.user)
    
    # Filtreleme
    if filter_type == 'monthly' and month and year:
        try:
            month_int = int(month)
            year_int = int(year)
            start_of_month = datetime(year_int, month_int, 1)
            if month_int == 12:
                end_of_month = datetime(year_int + 1, 1, 1) - timedelta(days=1)
            else:
                end_of_month = datetime(year_int, month_int + 1, 1) - timedelta(days=1)
            
            sales = sales.filter(
                created_at__date__gte=start_of_month.date(),
                created_at__date__lte=end_of_month.date()
            )
        except (ValueError, TypeError):
            pass
    
    elif filter_type == 'date_range' and start_date and end_date:
        try:
            start_date_obj = datetime.strptime(start_date, '%Y-%m-%d').date()
            end_date_obj = datetime.strptime(end_date, '%Y-%m-%d').date()
            sales = sales.filter(
                created_at__date__gte=start_date_obj,
                created_at__date__lte=end_date_obj
            )
        except ValueError:
            pass
    
    # İstatistikler
    total_revenue = sales.aggregate(total=Sum('final_price'))['total'] or 0
    total_projects = sales.count()
    completed_projects = sales.filter(status='completed').count()
    
    # Aylık gelir dağılımı (son 12 ay)
    monthly_data = []
    current_date = datetime.now()
    for i in range(12):
        month_date = current_date - timedelta(days=30 * i)
        month_start = month_date.replace(day=1)
        if month_date.month == 12:
            month_end = month_date.replace(year=month_date.year + 1, month=1, day=1) - timedelta(days=1)
        else:
            month_end = month_date.replace(month=month_date.month + 1, day=1) - timedelta(days=1)
        
        month_revenue = ProjectSale.objects.filter(
            seller=request.user,
            created_at__date__gte=month_start.date(),
            created_at__date__lte=month_end.date()
        ).aggregate(total=Sum('final_price'))['total'] or 0
        
        monthly_data.append({
            'month': month_start.strftime('%Y-%m'),
            'month_name': month_start.strftime('%B %Y'),
            'revenue': float(month_revenue)
        })
    
    monthly_data.reverse()  # Eski tarihten yeni tarihe sırala
    
    # Durum dağılımı
    status_stats = sales.values('status').annotate(
        count=models.Count('id'),
        total_revenue=Sum('final_price')
    ).order_by('-total_revenue')
    
    # Müşteri türü dağılımı
    customer_type_stats = sales.values('customer__customer_type').annotate(
        count=models.Count('id'),
        total_revenue=Sum('final_price')
    ).order_by('-total_revenue')
    
    context = {
        'sales': sales.order_by('-created_at')[:50],  # Son 50 satış
        'total_revenue': total_revenue,
        'total_projects': total_projects,
        'completed_projects': completed_projects,
        'monthly_data': monthly_data,
        'status_stats': status_stats,
        'customer_type_stats': customer_type_stats,
        'filter_type': filter_type,
        'month': month,
        'year': year,
        'start_date': start_date,
        'end_date': end_date,
        'months': [(i, calendar.month_name[i]) for i in range(1, 13)],
        'years': range(2020, datetime.now().year + 2),
    }
    
    return render(request, 'sellers/reports/revenue_report.html', context)