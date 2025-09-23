from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from django.db.models import Q
from django.core.paginator import Paginator
from datetime import datetime, timedelta
import json

from .models import CalendarEvent, CalendarSettings
from .utils import get_user_events, has_permission_for_event_type, sync_calendar_events

User = get_user_model()


@login_required
def calendar_view(request):
    """
    Ana takvim görünümü.
    """
    # Kullanıcı ayarlarını al veya oluştur
    settings, created = CalendarSettings.objects.get_or_create(
        user=request.user,
        defaults={
            'default_view': 'month',
        }
    )
    
    # Debug için etkinlik sayısını kontrol et
    events = get_user_events(request.user, settings)
    print(f"User: {request.user.username}, Events count: {events.count()}")
    
    # URL'den tarih parametrelerini al
    year = request.GET.get('year', timezone.now().year)
    month = request.GET.get('month', timezone.now().month)
    view_type = request.GET.get('view', settings.default_view)
    
    try:
        year = int(year)
        month = int(month)
        current_date = datetime(year, month, 1)
    except (ValueError, TypeError):
        current_date = timezone.now().replace(day=1)
    
    # Kullanıcının etkinliklerini al
    events = get_user_events(request.user, settings)
    
    # Tarih aralığına göre filtrele
    if view_type == 'month':
        start_date = current_date.replace(day=1)
        if start_date.month == 12:
            end_date = start_date.replace(year=start_date.year + 1, month=1)
        else:
            end_date = start_date.replace(month=start_date.month + 1)
    elif view_type == 'week':
        # Haftanın başlangıcını bul (Pazartesi)
        start_date = current_date - timedelta(days=current_date.weekday())
        end_date = start_date + timedelta(days=7)
    else:  # day
        start_date = current_date
        end_date = start_date + timedelta(days=1)
    
    # Etkinlikleri tarih aralığına göre filtrele
    events = events.filter(
        start_date__gte=start_date,
        start_date__lt=end_date
    ).order_by('start_date', 'priority')
    
    context = {
        'events': events,
        'settings': settings,
        'current_date': current_date,
        'view_type': view_type,
        'year': year,
        'month': month,
    }
    
    return render(request, 'calendar/calendar.html', context)


@login_required
def calendar_events_api(request):
    """
    Takvim etkinlikleri için AJAX API.
    """
    if request.method != 'GET':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    print(f"Events API called by user: {request.user.username}")
    print(f"GET parameters: {dict(request.GET)}")
    
    # Kullanıcı ayarlarını al
    try:
        settings = CalendarSettings.objects.get(user=request.user)
    except CalendarSettings.DoesNotExist:
        settings = CalendarSettings.objects.create(user=request.user)
    
    # Tarih parametrelerini al
    start = request.GET.get('start')
    end = request.GET.get('end')
    
    # Eğer start ve end yoksa, tüm etkinlikleri döndür
    if not start or not end:
        print("No start/end dates provided, returning all events")
        events = get_user_events(request.user, settings)
    else:
        try:
            start_date = datetime.fromisoformat(start.replace('Z', '+00:00'))
            end_date = datetime.fromisoformat(end.replace('Z', '+00:00'))
            events = get_user_events(request.user, settings).filter(
                start_date__gte=start_date,
                start_date__lt=end_date
            )
        except ValueError:
            return JsonResponse({'error': 'Invalid date format'}, status=400)
    
    print(f"Events found: {events.count()}")
    
    # Etkinlikleri JSON formatına çevir
    events_data = []
    for event in events:
        event_data = {
            'id': event.id,
            'title': event.title,
            'start': event.start_date.isoformat(),
            'end': event.end_date.isoformat() if event.end_date else None,
            'allDay': event.is_all_day,
            'color': event.color,
            'textColor': '#ffffff' if event.priority == 'urgent' else '#000000',
            'url': event.get_absolute_url(),
            'extendedProps': {
                'event_type': event.event_type,
                'priority': event.priority,
                'description': event.description,
                'is_completed': event.is_completed,
                'is_overdue': event.is_overdue,
            }
        }
        events_data.append(event_data)
    
    return JsonResponse(events_data, safe=False)


@login_required
def event_detail(request, event_id):
    """
    Etkinlik detay sayfası.
    """
    event = get_object_or_404(CalendarEvent, id=event_id, user=request.user)
    
    context = {
        'event': event,
    }
    
    return render(request, 'calendar/event_detail.html', context)


@login_required
def calendar_settings(request):
    """
    Takvim ayarları sayfası.
    """
    settings, created = CalendarSettings.objects.get_or_create(
        user=request.user,
        defaults={
            'default_view': 'month',
        }
    )
    
    if request.method == 'POST':
        # Ayarları güncelle - sadece renk ve görünüm ayarları
        settings.default_view = request.POST.get('default_view', 'month')
        
        # Renk ayarları
        settings.task_color = request.POST.get('task_color', '#28a745')
        settings.project_color = request.POST.get('project_color', '#007bff')
        settings.payment_color = request.POST.get('payment_color', '#ffc107')
        settings.deadline_color = request.POST.get('deadline_color', '#dc3545')
        settings.meeting_color = request.POST.get('meeting_color', '#6f42c1')
        
        settings.save()
        
        return redirect('calendar:settings')
    
    context = {
        'settings': settings,
    }
    
    return render(request, 'calendar/settings.html', context)


@login_required
@require_http_methods(["POST"])
@csrf_exempt
def toggle_event_completion(request, event_id):
    """
    Etkinlik tamamlanma durumunu değiştir.
    """
    try:
        event = CalendarEvent.objects.get(id=event_id, user=request.user)
        event.is_completed = not event.is_completed
        event.save()
        
        return JsonResponse({
            'success': True,
            'is_completed': event.is_completed
        })
    except CalendarEvent.DoesNotExist:
        return JsonResponse({'error': 'Event not found'}, status=404)


@login_required
def agenda_view(request):
    """
    Ajanda görünümü - liste halinde etkinlikler.
    """
    # Kullanıcı ayarlarını al
    try:
        settings = CalendarSettings.objects.get(user=request.user)
    except CalendarSettings.DoesNotExist:
        settings = CalendarSettings.objects.create(user=request.user)
    
    # Tarih filtresi
    date_filter = request.GET.get('date', 'all')
    today = timezone.now().date()
    
    # Kullanıcının etkinliklerini al
    events = get_user_events(request.user, settings)
    
    if date_filter == 'today':
        events = events.filter(start_date__date=today)
    elif date_filter == 'week':
        week_start = today - timedelta(days=today.weekday())
        week_end = week_start + timedelta(days=7)
        events = events.filter(start_date__date__gte=week_start, start_date__date__lt=week_end)
    elif date_filter == 'month':
        month_start = today.replace(day=1)
        if month_start.month == 12:
            month_end = month_start.replace(year=month_start.year + 1, month=1)
        else:
            month_end = month_start.replace(month=month_start.month + 1)
        events = events.filter(start_date__date__gte=month_start, start_date__date__lt=month_end)
    elif date_filter == 'overdue':
        events = events.filter(
            end_date__lt=timezone.now(),
            is_completed=False
        )
    
    # Sayfalama
    paginator = Paginator(events, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'settings': settings,
        'date_filter': date_filter,
        'today': today,
    }
    
    return render(request, 'calendar/agenda.html', context)


@login_required
@require_http_methods(["POST"])
@csrf_exempt
def sync_calendar(request):
    """
    Takvimi diğer modellerle senkronize eder.
    """
    try:
        sync_calendar_events(request.user)
        return JsonResponse({'success': True, 'message': 'Takvim başarıyla senkronize edildi.'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)
