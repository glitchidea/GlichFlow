from django import template
from django.contrib.auth import get_user_model

User = get_user_model()
register = template.Library()


@register.filter
def has_tag(user, tag_name):
    """
    Kullanıcının belirli bir etikete sahip olup olmadığını kontrol eder.
    """
    if not user or not hasattr(user, 'tags'):
        return False
    
    return user.tags.filter(name=tag_name).exists()


@register.filter
def has_permission_for_event_type(user, event_type):
    """
    Kullanıcının belirli bir etkinlik türü için yetkisi olup olmadığını kontrol eder.
    """
    if not user:
        return False
    
    if event_type == 'payment':
        # Ödeme etkinlikleri sadece muhasebeci ve muhasebeadmin etiketine sahip kullanıcılar görebilir
        return has_tag(user, 'muhasebeci') or has_tag(user, 'muhasebeadmin')
    elif event_type == 'project':
        # Proje etkinlikleri proje yöneticisi ve admin görebilir
        return user.role in ['admin', 'project_manager']
    elif event_type in ['task', 'deadline', 'meeting']:
        # Görev, son tarih ve toplantı etkinlikleri tüm kullanıcılar görebilir
        return True
    else:
        return True


@register.filter
def get_event_type_display(event_type):
    """
    Etkinlik türü için görüntüleme metnini döndürür.
    """
    types = {
        'task': 'Görev',
        'project': 'Proje',
        'payment': 'Ödeme',
        'deadline': 'Son Tarih',
        'meeting': 'Toplantı',
        'milestone': 'Kilometre Taşı',
        'custom': 'Özel Etkinlik'
    }
    return types.get(event_type, event_type)


@register.filter
def get_priority_display(priority):
    """
    Öncelik için görüntüleme metnini döndürür.
    """
    priorities = {
        'urgent': 'Acil',
        'high': 'Yüksek',
        'medium': 'Orta',
        'low': 'Düşük'
    }
    return priorities.get(priority, priority)


@register.filter
def get_priority_class(priority):
    """
    Öncelik için CSS sınıfını döndürür.
    """
    classes = {
        'urgent': 'danger',
        'high': 'warning',
        'medium': 'info',
        'low': 'secondary'
    }
    return classes.get(priority, 'secondary')
