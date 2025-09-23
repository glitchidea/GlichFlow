from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q, Max, Count, F, Subquery, OuterRef
from django.core.paginator import Paginator
from django.utils import timezone
from django.http import JsonResponse, HttpResponseForbidden
from django.urls import reverse
import os
from django import forms

from accounts.models import CustomUser
from projects.models import Project
from tasks.models import Task
from .models import (
    Message, MessageGroup, MessageGroupMember, MessageReadStatus, 
    Notification, DirectMessage, DirectMessageContent
)

@login_required
def inbox(request):
    """Kullanıcının gelen mesajlarını listeleyen view."""
    # GitHub issue'larla ilişkili görevlerin ID'lerini al (exclude edilecek)
    github_task_ids = Task.objects.filter(github_issue__isnull=False).values_list('id', flat=True)
    
    # GitHub ile ilişkili olmayan mesajları al
    message_list = Message.objects.filter(
        recipient=request.user
    ).exclude(
        # Mesaj grubuna sahip ve bu grup GitHub issue ile ilişkili bir göreve ait mesajları hariç tut
        group__related_task_id__in=github_task_ids
    ).order_by('-created_at')
    
    paginator = Paginator(message_list, 10)  # Her sayfada 10 mesaj
    page_number = request.GET.get('page')
    messages_page = paginator.get_page(page_number)
    
    # Okunmamış mesaj sayısı
    unread_count = message_list.filter(is_read=False).count()
    
    context = {
        'title': 'Gelen Mesajlar',
        'messages_page': messages_page,
        'unread_count': unread_count,
        'active_tab': 'inbox'
    }
    return render(request, 'communications/message_list.html', context)

@login_required
def sent(request):
    """Kullanıcının gönderdiği mesajları listeleyen view."""
    # GitHub issue'larla ilişkili görevlerin ID'lerini al (exclude edilecek)
    github_task_ids = Task.objects.filter(github_issue__isnull=False).values_list('id', flat=True)
    
    # GitHub ile ilişkili olmayan mesajları al
    message_list = Message.objects.filter(
        sender=request.user
    ).exclude(
        # Mesaj grubuna sahip ve bu grup GitHub issue ile ilişkili bir göreve ait mesajları hariç tut
        group__related_task_id__in=github_task_ids
    ).order_by('-created_at')
    
    paginator = Paginator(message_list, 10)  # Her sayfada 10 mesaj
    page_number = request.GET.get('page')
    messages_page = paginator.get_page(page_number)
    
    # Gelen mesajlardaki okunmamış mesaj sayısı (tab için)
    unread_count = Message.objects.filter(
        recipient=request.user, 
        is_read=False
    ).exclude(
        # GitHub issue ile ilişkili mesajları hariç tut
        group__related_task_id__in=github_task_ids
    ).count()
    
    context = {
        'title': 'Gönderilen Mesajlar',
        'messages_page': messages_page,
        'unread_count': unread_count,
        'active_tab': 'sent'
    }
    return render(request, 'communications/message_list.html', context)

@login_required
def message_detail(request, message_id):
    """Mesaj detayını gösteren view."""
    # Q sorgusu filter ile kullanılmalı
    message_obj = Message.objects.filter(
        id=message_id
    ).filter(
        Q(recipient=request.user) | Q(sender=request.user)
    ).first()
    
    if not message_obj:
        messages.error(request, 'Mesaj bulunamadı.')
        return redirect('communications:inbox')
    
    # Mesajı okudu olarak işaretle (sadece alıcıysa)
    if message_obj.recipient == request.user and not message_obj.is_read:
        message_obj.is_read = True
        message_obj.read_at = timezone.now()
        message_obj.save()
    
    context = {
        'title': 'Mesaj Detayı',
        'message_obj': message_obj,
    }
    return render(request, 'communications/message_detail.html', context)

@login_required
def message_create(request):
    """Yeni mesaj oluşturmayı sağlayan view."""
    reply_to = request.GET.get('reply_to')
    initial_recipient = request.GET.get('to')
    initial_subject = ''
    initial_content = ''
    
    # Yanıtlama durumunda varsayılan değerleri ayarla
    if reply_to:
        try:
            # Q sorgusu filter ile kullanılmalı
            original_message = Message.objects.filter(
                id=reply_to
            ).filter(
                Q(recipient=request.user) | Q(sender=request.user)
            ).first()
            
            if original_message:
                initial_recipient = original_message.sender.id if original_message.recipient == request.user else None
                initial_subject = f"Yanıt: {original_message.subject}" if not original_message.subject.startswith("Yanıt: ") else original_message.subject
                initial_content = f"\n\n\n--- {original_message.created_at.strftime('%d/%m/%Y %H:%M')} tarihinde {original_message.sender.get_full_name()} yazdı: ---\n{original_message.content}"
        except Message.DoesNotExist:
            pass
    
    # Kullanıcı listesini al (kendisi hariç)
    users = CustomUser.objects.exclude(id=request.user.id).order_by('first_name', 'last_name')
    
    if request.method == 'POST':
        recipient_id = request.POST.get('recipient')
        subject = request.POST.get('subject')
        content = request.POST.get('content')
        
        if not recipient_id or not content:
            messages.error(request, 'Alıcı ve mesaj içeriği zorunludur.')
            return redirect('communications:message_create')
        
        try:
            recipient = CustomUser.objects.get(id=recipient_id)
            
            # Mesajı oluştur
            message = Message.objects.create(
                sender=request.user,
                recipient=recipient,
                subject=subject,
                content=content
            )
            
            messages.success(request, 'Mesaj başarıyla gönderildi.')
            return redirect('communications:inbox')
            
        except CustomUser.DoesNotExist:
            messages.error(request, 'Geçersiz alıcı.')
            return redirect('communications:message_create')
    
    context = {
        'title': 'Yeni Mesaj',
        'users': users,
        'initial_recipient': initial_recipient,
        'initial_subject': initial_subject,
        'initial_content': initial_content,
    }
    return render(request, 'communications/message_form.html', context)

@login_required
def message_delete(request, message_id):
    """Mesajı silmeyi sağlayan view."""
    # Q sorgusu içeren kısım değiştirildi
    message_obj = Message.objects.filter(
        id=message_id
    ).filter(
        Q(recipient=request.user) | Q(sender=request.user)
    ).first()
    
    if not message_obj:
        messages.error(request, 'Mesaj bulunamadı.')
        return redirect('communications:inbox')
    
    # POST isteği ise mesajı sil
    if request.method == 'POST':
        is_sender = message_obj.sender == request.user
        message_obj.delete()
        messages.success(request, 'Mesaj başarıyla silindi.')
        return redirect('communications:sent' if is_sender else 'communications:inbox')
    
    context = {
        'title': 'Mesaj Sil',
        'message_obj': message_obj,
    }
    return render(request, 'communications/message_confirm_delete.html', context)

# ---------- Mesaj Grupları ---------- #

@login_required
def chat_list(request):
    """Kullanıcının mesaj gruplarını ve son mesajlarını listeleyen view."""
    # GitHub issue'larla ilişkili görevlerin ID'lerini al (exclude edilecek)
    github_task_ids = Task.objects.filter(github_issue__isnull=False).values_list('id', flat=True)
    
    # Kullanıcının üye olduğu ve GitHub ile ilişkili olmayan tüm gruplar
    user_groups = MessageGroup.objects.filter(
        members=request.user
    ).exclude(
        # GitHub issue ile ilişkili görevlerin mesaj gruplarını hariç tut
        related_task_id__in=github_task_ids
    ).annotate(
        # Her grup için son mesaj tarihini bul
        last_message_date=Max('messages__created_at'),
        # Okunmamış mesaj sayısını bul
        unread_count=Count(
            'messages',
            filter=Q(
                messages__read_status__user=request.user,
                messages__read_status__is_read=False
            )
        )
    ).order_by('-last_message_date')
    
    context = {
        'title': 'Mesajlar',
        'groups': user_groups,
    }
    return render(request, 'communications/chat_list.html', context)

@login_required
def chat_detail(request, group_id):
    """Mesaj grubunun detayını ve mesajlarını gösteren view."""
    group = get_object_or_404(MessageGroup, id=group_id)
    
    # Kullanıcının grupta olup olmadığını kontrol et
    if not group.members.filter(id=request.user.id).exists():
        messages.error(request, 'Bu mesaj grubuna erişim izniniz yok.')
        return redirect('communications:chat_list')
    
    # Mesajları getir
    messages_list = group.messages.all().order_by('created_at')
    
    # Kullanıcı için tüm okunmamış mesajları okundu olarak işaretle
    unread_statuses = MessageReadStatus.objects.filter(
        message__group=group,
        user=request.user,
        is_read=False
    )
    for status in unread_statuses:
        status.mark_as_read()
    
    # Grup üyelerini getir
    group_members = group.group_members.select_related('user').all()
    
    # Eğer bu bir direkt mesaj ise, sohbet edilen diğer kullanıcıyı belirle
    other_user = None
    if group.type == 'direct':
        # Kullanıcı dışındaki ilk (ve tek) üyeyi al
        for member in group_members:
            if member.user.id != request.user.id:
                other_user = member.user
                break
    
    context = {
        'title': group.name,
        'group': group,
        'messages_list': messages_list,
        'group_members': group_members,
        'other_user': other_user,  # Direkt mesajlar için karşı kullanıcı
    }
    return render(request, 'communications/chat_detail.html', context)

@login_required
def create_message(request, group_id):
    """Mesaj grubu içine yeni mesaj gönderir."""
    group = get_object_or_404(MessageGroup, id=group_id)
    
    # Kullanıcının bu gruba üye olup olmadığını kontrol et
    if not group.members.filter(id=request.user.id).exists():
        messages.error(request, "Bu sohbete mesaj gönderme izniniz yok.")
        return redirect('communications:chat_list')
    
    if request.method == 'POST':
        content = request.POST.get('content')
        parent_id = request.POST.get('parent_id')
        
        # İçerik boş mu kontrol et
        if not content or content.isspace():
            return JsonResponse({'status': 'error', 'message': 'Lütfen bir mesaj yazın.'}, status=400)
        
        # Yanıtlanan mesaj varsa kontrol et
        parent_message = None
        if parent_id:
            try:
                parent_message = Message.objects.get(id=parent_id, group=group)
            except Message.DoesNotExist:
                pass
        
        # Mesaj oluştur
        message = Message.objects.create(
            sender=request.user,
            group=group,
            parent_message=parent_message,
            content=content,
            message_type='text'
        )
        
        # Grup son güncelleme zamanını güncelleyelim
        group.save()  # Bu otomatik olarak updated_at'i günceller
        
        # Okuma durumları oluştur
        for member in group.members.all():
            if member != request.user:  # Gönderen hariç
                MessageReadStatus.objects.create(
                    message=message,
                    user=member,
                    is_read=False
                )
                
                # Bildirim oluştur - direkt mesajlar için veya parent_message varsa
                if group.type == 'direct' or parent_message:
                    # Bildirim içeriğini belirle
                    notification_title = f"Yeni mesaj: {group.name}"
                    
                    if group.type == 'direct':
                        notification_content = f"{request.user.get_full_name() or request.user.username} size mesaj gönderdi"
                    elif parent_message:
                        notification_content = f"{request.user.get_full_name() or request.user.username} bir mesajı yanıtladı"
                    else:
                        notification_content = f"{request.user.get_full_name() or request.user.username} gruba mesaj gönderdi: {group.name}"
                    
                    # İlgili proje ve görevi bul
                    related_project = group.related_project
                    related_task = group.related_task
                    
                    # Mesaj içeriğinden bir kısmını ekle
                    if len(content) > 50:
                        notification_content += f": {content[:50]}..."
                    else:
                        notification_content += f": {content}"
                    
                    # Bildirim oluştur
                    Notification.objects.create(
                        recipient=member,
                        sender=request.user,
                        title=notification_title,
                        content=notification_content,
                        notification_type="info",
                        related_message_group=group,
                        related_project=related_project,
                        related_task=related_task
                    )
        
        # Yanıt olarak, mesaj bilgilerini içeren HTML döndür
        message_data = {
            'id': message.id,
            'sender_name': message.sender.get_full_name() or message.sender.username,
            'sender_id': message.sender.id,
            'content': message.content,
            'created_at': timezone.localtime(message.created_at).strftime('%H:%M'),
            'is_sender': True,  # Bu mesajı gönderen kişi şu anki kullanıcı
            'parent_message': None,
            'profile_picture': message.sender.profile_picture.url if message.sender.profile_picture else None,
        }
        
        if parent_message:
            message_data['parent_message'] = {
                'id': parent_message.id,
                'sender_name': parent_message.sender.get_full_name() or parent_message.sender.username,
                'content': parent_message.content[:100] + ('...' if len(parent_message.content) > 100 else '')
            }
        
        return JsonResponse({'status': 'success', 'message': message_data})
    
    # POST olmayan istekleri reddet
    return JsonResponse({'status': 'error', 'message': 'Geçersiz istek metodu.'}, status=405)

@login_required
def create_group(request):
    """Yeni bir mesaj grubu oluşturmayı sağlayan view."""
    # Tüm kullanıcıları getir (kendisi hariç)
    users = CustomUser.objects.exclude(id=request.user.id).order_by('first_name', 'last_name')
    projects = Project.objects.all().order_by('name')
    tasks = Task.objects.all().order_by('title')
    
    if request.method == 'POST':
        name = request.POST.get('name')
        description = request.POST.get('description', '')
        group_type = request.POST.get('type')
        image = request.FILES.get('image')
        member_ids = request.POST.getlist('members')
        project_id = request.POST.get('project')
        task_id = request.POST.get('task')
        
        if not name:
            messages.error(request, 'Grup adı zorunludur.')
            return redirect('communications:create_group')
        
        if group_type not in dict(MessageGroup.GROUP_TYPE_CHOICES):
            group_type = 'group'
        
        # İlişkili proje ve görevi kontrol et
        related_project = None
        related_task = None
        
        if project_id:
            try:
                related_project = Project.objects.get(id=project_id)
            except Project.DoesNotExist:
                pass
                
        if task_id:
            try:
                related_task = Task.objects.get(id=task_id)
                # Görevin projesini otomatik olarak ayarla
                if related_task and not related_project:
                    related_project = related_task.project
            except Task.DoesNotExist:
                pass
        
        # Grubu oluştur
        group = MessageGroup.objects.create(
            name=name,
            description=description,
            type=group_type,
            image=image,
            related_project=related_project,
            related_task=related_task
        )
        
        # Oluşturan kişiyi admin olarak ekle
        MessageGroupMember.objects.create(
            group=group,
            user=request.user,
            role='admin'
        )
        
        # Diğer üyeleri ekle
        if member_ids:
            members = CustomUser.objects.filter(id__in=member_ids)
            for member in members:
                MessageGroupMember.objects.create(
                    group=group,
                    user=member,
                    role='member'
                )
                
                # Üyelere bildirim gönder
                Notification.objects.create(
                    recipient=member,
                    sender=request.user,
                    title=f"Yeni mesaj grubu: {name}",
                    content=f"{request.user.get_full_name() or request.user.username} sizi '{name}' grubuna ekledi.",
                    notification_type='info',
                    related_message_group=group
                )
        
        # Grup oluşturulduğuna dair sistem mesajı ekle
        system_message = Message.objects.create(
            sender=request.user,
            group=group,
            message_type='system',
            content=f"'{name}' grubu oluşturuldu."
        )
        
        # Tüm üyeler için okunma durumu oluştur
        for member in group.members.all():
            MessageReadStatus.objects.create(
                message=system_message,
                user=member,
                is_read=True,
                read_at=timezone.now()
            )
        
        messages.success(request, 'Mesaj grubu başarıyla oluşturuldu.')
        return redirect('communications:chat_detail', group_id=group.id)
    
    context = {
        'title': 'Yeni Mesaj Grubu',
        'users': users,
        'projects': projects,
        'tasks': tasks,
    }
    return render(request, 'communications/group_form.html', context)

@login_required
def edit_group(request, group_id):
    """Mesaj grubunu düzenlemeyi sağlayan view."""
    group = get_object_or_404(MessageGroup, id=group_id)
    
    # Kullanıcının grup yöneticisi olup olmadığını kontrol et
    if not group.group_members.filter(user=request.user, role='admin').exists():
        messages.error(request, 'Bu grubu düzenleme izniniz yok.')
        return redirect('communications:chat_detail', group_id=group.id)
    
    # Tüm kullanıcıları getir (kendisi hariç)
    users = CustomUser.objects.exclude(id=request.user.id).order_by('first_name', 'last_name')
    projects = Project.objects.all().order_by('name')
    tasks = Task.objects.all().order_by('title')
    
    # Grupta mevcut üyeleri işaretle
    current_members = group.members.values_list('id', flat=True)
    
    if request.method == 'POST':
        name = request.POST.get('name')
        description = request.POST.get('description', '')
        image = request.FILES.get('image')
        member_ids = request.POST.getlist('members')
        project_id = request.POST.get('project')
        task_id = request.POST.get('task')
        
        if not name:
            messages.error(request, 'Grup adı zorunludur.')
            return redirect('communications:edit_group', group_id=group.id)
        
        # İlişkili proje ve görevi kontrol et
        related_project = None
        related_task = None
        
        if project_id:
            try:
                related_project = Project.objects.get(id=project_id)
            except Project.DoesNotExist:
                pass
                
        if task_id:
            try:
                related_task = Task.objects.get(id=task_id)
            except Task.DoesNotExist:
                pass
        
        # Grubu güncelle
        group.name = name
        group.description = description
        if image:
            group.image = image
        group.related_project = related_project
        group.related_task = related_task
        group.save()
        
        # Mevcut üyeler
        old_members = set(current_members)
        # Yeni üyeler
        new_members = set([int(mid) for mid in member_ids])
        
        # Eklenecek üyeler
        members_to_add = new_members - old_members
        # Çıkarılacak üyeler
        members_to_remove = old_members - new_members - {request.user.id}  # Kendimizi çıkarmıyoruz
        
        # Yeni üyeleri ekle
        if members_to_add:
            for member_id in members_to_add:
                try:
                    member = CustomUser.objects.get(id=member_id)
                    MessageGroupMember.objects.create(
                        group=group,
                        user=member,
                        role='member'
                    )
                    
                    # Sistem mesajı ekle
                    system_message = Message.objects.create(
                        sender=request.user,
                        group=group,
                        message_type='system',
                        content=f"{member.get_full_name() or member.username} gruba eklendi."
                    )
                    
                    # Tüm üyeler için okunma durumu oluştur
                    for user in group.members.all():
                        MessageReadStatus.objects.create(
                            message=system_message,
                            user=user,
                            is_read=user == request.user,
                            read_at=timezone.now() if user == request.user else None
                        )
                    
                    # Üyeye bildirim gönder
                    Notification.objects.create(
                        recipient=member,
                        sender=request.user,
                        title=f"Gruba eklendiz: {name}",
                        content=f"{request.user.get_full_name() or request.user.username} sizi '{name}' grubuna ekledi.",
                        notification_type='info',
                        related_message_group=group
                    )
                except CustomUser.DoesNotExist:
                    pass
        
        # Üyeleri çıkar
        if members_to_remove:
            for member_id in members_to_remove:
                try:
                    member = CustomUser.objects.get(id=member_id)
                    MessageGroupMember.objects.filter(group=group, user=member).delete()
                    
                    # Sistem mesajı ekle
                    system_message = Message.objects.create(
                        sender=request.user,
                        group=group,
                        message_type='system',
                        content=f"{member.get_full_name() or member.username} gruptan çıkarıldı."
                    )
                    
                    # Tüm üyeler için okunma durumu oluştur
                    for user in group.members.all():
                        MessageReadStatus.objects.create(
                            message=system_message,
                            user=user,
                            is_read=user == request.user,
                            read_at=timezone.now() if user == request.user else None
                        )
                    
                    # Çıkarılan üyeye bildirim gönder
                    Notification.objects.create(
                        recipient=member,
                        sender=request.user,
                        title=f"Gruptan çıkarıldınız: {name}",
                        content=f"{request.user.get_full_name() or request.user.username} sizi '{name}' grubundan çıkardı.",
                        notification_type='info'
                    )
                except CustomUser.DoesNotExist:
                    pass
        
        messages.success(request, 'Grup başarıyla güncellendi.')
        return redirect('communications:chat_detail', group_id=group.id)
    
    context = {
        'title': 'Grubu Düzenle',
        'group': group,
        'users': users,
        'projects': projects,
        'tasks': tasks,
        'current_members': current_members,
    }
    return render(request, 'communications/group_form.html', context)

@login_required
def leave_group(request, group_id):
    """Kullanıcının bir gruptan ayrılmasını sağlayan view."""
    group = get_object_or_404(MessageGroup, id=group_id)
    
    # Kullanıcının grupta olup olmadığını kontrol et
    if not group.members.filter(id=request.user.id).exists():
        messages.error(request, 'Bu gruptan ayrılamazsınız çünkü üye değilsiniz.')
        return redirect('communications:chat_list')
    
    # Direkt mesajlaşma (DM) gruplarından ayrılmaya izin verme
    if group.type == 'direct':
        messages.error(request, 'Bireysel mesajlaşma gruplarından ayrılamazsınız.')
        return redirect('communications:chat_detail', group_id=group.id)
    
    if request.method == 'POST':
        # Kullanıcıyı gruptan çıkar
        MessageGroupMember.objects.filter(group=group, user=request.user).delete()
        
        # Sistem mesajı ekle
        system_message = Message.objects.create(
            sender=request.user,
            group=group,
            message_type='system',
            content=f"{request.user.get_full_name() or request.user.username} gruptan ayrıldı."
        )
        
        # Tüm üyeler için okunma durumu oluştur
        for user in group.members.all():
            MessageReadStatus.objects.create(
                message=system_message,
                user=user,
                is_read=False
            )
        
        messages.success(request, f"'{group.name}' grubundan başarıyla ayrıldınız.")
        return redirect('communications:chat_list')
    
    context = {
        'title': 'Gruptan Ayrıl',
        'group': group,
    }
    return render(request, 'communications/leave_group_confirm.html', context)

@login_required
def delete_group(request, group_id):
    """Mesaj grubunu silmeyi sağlayan view."""
    group = get_object_or_404(MessageGroup, id=group_id)
    
    # Kullanıcının grup yöneticisi olup olmadığını kontrol et
    if not group.group_members.filter(user=request.user, role='admin').exists():
        messages.error(request, 'Bu grubu silme izniniz yok.')
        return redirect('communications:chat_detail', group_id=group.id)
    
    # Direkt mesajlaşma (DM) gruplarını silmeye izin verme
    if group.type == 'direct':
        messages.error(request, 'Bireysel mesajlaşma grupları silinemez.')
        return redirect('communications:chat_detail', group_id=group.id)
    
    if request.method == 'POST':
        group_name = group.name
        
        # Gruba ait tüm üyelere bildirim gönder
        for member in group.members.exclude(id=request.user.id):
            Notification.objects.create(
                recipient=member,
                sender=request.user,
                title=f"Grup silindi: {group_name}",
                content=f"{request.user.get_full_name() or request.user.username} '{group_name}' grubunu sildi.",
                notification_type='info'
            )
        
        # Grubu sil
        group.delete()
        
        messages.success(request, f"'{group_name}' grubu başarıyla silindi.")
        return redirect('communications:chat_list')
    
    context = {
        'title': 'Grubu Sil',
        'group': group,
    }
    return render(request, 'communications/delete_group_confirm.html', context)

@login_required
def create_direct_message(request, user_id):
    """İki kullanıcı arasında direkt mesaj grubu oluşturur veya var olan gruba yönlendirir."""
    # Diğer kullanıcının varlığını kontrol et
    try:
        other_user = CustomUser.objects.get(id=user_id)
    except CustomUser.DoesNotExist:
        messages.error(request, 'Kullanıcı bulunamadı.')
        return redirect('communications:chat_list')
    
    # Kendisine mesaj göndermeyi engelle
    if request.user.id == other_user.id:
        messages.error(request, 'Kendinize mesaj gönderemezsiniz.')
        return redirect('communications:chat_list')
    
    # İki kullanıcı arasında zaten bir DM grubu var mı kontrol et
    existing_groups = MessageGroup.objects.filter(
        type='direct',
        members=request.user
    ).filter(
        members=other_user
    ).annotate(
        member_count=Count('members')
    ).filter(
        member_count=2
    ).order_by('-created_at')
    
    if existing_groups.exists():
        # Zaten direkt mesaj grubu var, en son oluşturulana yönlendir
        existing_group = existing_groups.first()
        
        # Eski gruplar varsa, aynı iki kullanıcı arasında - temizleme yapabilirsiniz
        if existing_groups.count() > 1:
            # Sistem mesajı ekle
            Message.objects.create(
                sender=request.user,
                group=existing_group,
                message_type='system',
                content=f"Aranızda birden fazla sohbet tespit edildi. Tüm mesajlarınız artık burada toplanacak."
            )
            
            # İlk grup dışındaki eski grupları temizle
            for old_group in existing_groups[1:]:
                # Silmeden önce mesajları yeni gruba taşı
                messages_to_move = Message.objects.filter(group=old_group)
                for msg in messages_to_move:
                    # Mesajı kopyala
                    new_msg = Message.objects.create(
                        sender=msg.sender,
                        group=existing_group,
                        message_type=msg.message_type,
                        content=msg.content,
                        file=msg.file,
                        parent_message=None,  # İlişki kaybolacak ama bu kabul edilebilir
                        created_at=msg.created_at
                    )
                    
                    # Okunma durumlarını kopyala
                    for status in msg.read_status.all():
                        MessageReadStatus.objects.create(
                            message=new_msg,
                            user=status.user,
                            is_read=status.is_read,
                            read_at=status.read_at
                        )
                
                # Eski grubu sil
                old_group.delete()
        
        return redirect('communications:chat_detail', group_id=existing_group.id)
    
    # Yeni bir DM grubu oluştur
    group_name = f"{request.user.get_full_name()} ve {other_user.get_full_name()}"
    new_group = MessageGroup.objects.create(
        name=group_name,
        type='direct'
    )
    
    # Her iki kullanıcıyı da mesaj grubuna üye olarak ekle
    MessageGroupMember.objects.create(
        group=new_group,
        user=request.user,
        role='admin'
    )
    
    MessageGroupMember.objects.create(
        group=new_group,
        user=other_user,
        role='member'
    )
    
    # Bildirim gönder
    notification_title = f"Yeni mesaj talebi"
    notification_content = f"{request.user.get_full_name() or request.user.username} size mesaj göndermek istiyor"
    
    Notification.objects.create(
        recipient=other_user,
        sender=request.user,
        title=notification_title,
        content=notification_content,
        notification_type="info",
        related_message_group=new_group
    )
    
    return redirect('communications:chat_detail', group_id=new_group.id)

@login_required
def create_direct_message_page(request):
    """Kullanıcıların listesini göstererek direkt mesaj başlatmayı sağlayan view."""
    # Tüm kullanıcıları getir (kendisi hariç)
    users = CustomUser.objects.exclude(id=request.user.id).order_by('first_name', 'last_name')
    
    # Her kullanıcı için mevcut bir direkt mesajlaşma olup olmadığını kontrol et
    for user in users:
        # İki kullanıcı arasında direkt mesaj grubu var mı?
        direct_chats = MessageGroup.objects.filter(
            type='direct',
            members=request.user
        ).filter(
            members=user
        ).annotate(
            member_count=Count('members')
        ).filter(
            member_count=2
        ).order_by('-created_at')
        
        # Eğer direkt mesaj grubu varsa, en yenisinin ID'sini kaydet
        if direct_chats.exists():
            user.existing_chat_id = direct_chats.first().id
            
            # Birden fazla sohbet varsa ve bunlar aktif olarak gösteriliyorsa temizle
            if direct_chats.count() > 1:
                newest_group = direct_chats.first()
                
                # En eski grup dışındaki diğer grupları sil
                for old_group in direct_chats[1:]:
                    # Mesajları yeni gruba taşı
                    for msg in Message.objects.filter(group=old_group):
                        # Mesajı kopyala
                        new_msg = Message.objects.create(
                            sender=msg.sender,
                            group=newest_group,
                            message_type=msg.message_type,
                            content=msg.content,
                            file=msg.file,
                            parent_message=None,  # İlişki kaybolacak ama bu kabul edilebilir
                            created_at=msg.created_at
                        )
                        
                        # Okunma durumlarını kopyala
                        for status in msg.read_status.all():
                            MessageReadStatus.objects.create(
                                message=new_msg,
                                user=status.user,
                                is_read=status.is_read,
                                read_at=status.read_at
                            )
                    
                    # Eski grubu sil
                    old_group.delete()
                
                # Sistem mesajı daha önce eklenmemişse ekle
                duplicate_warning_exists = Message.objects.filter(
                    group=newest_group,
                    message_type='system',
                    content__contains='Aranızda birden fazla sohbet tespit edildi'
                ).exists()
                
                if not duplicate_warning_exists:
                    # Sistem mesajı ekle
                    Message.objects.create(
                        sender=request.user,
                        group=newest_group,
                        message_type='system',
                        content=f"Aranızda birden fazla sohbet tespit edildi. Tüm mesajlarınız artık burada toplanacak."
                    )
        else:
            user.existing_chat_id = None
    
    context = {
        'title': 'Kişisel Mesaj Başlat',
        'users': users,
    }
    return render(request, 'communications/user_list.html', context)

@login_required
def clean_duplicate_direct_messages(request):
    """
    Bir kullanıcı için tekrarlanan direkt mesaj gruplarını temizler.
    Bu fonksiyon sadece yöneticiler tarafından çalıştırılabilir.
    """
    if not request.user.is_staff:
        messages.error(request, 'Bu işlemi yapma yetkiniz yok.')
        return redirect('communications:chat_list')
    
    # Tüm kullanıcıları al
    users = CustomUser.objects.all()
    
    cleaned_count = 0
    for user1 in users:
        for user2 in users.filter(id__gt=user1.id):  # Her çifti sadece bir kez işle
            # İki kullanıcı arasındaki tüm direkt mesaj gruplarını bul
            direct_groups = MessageGroup.objects.filter(
                type='direct',
                members=user1
            ).filter(
                members=user2
            ).annotate(
                member_count=Count('members')
            ).filter(
                member_count=2
            ).order_by('-created_at')
            
            # Eğer birden fazla grup varsa, en yenisini tutup diğerlerini temizle
            if direct_groups.count() > 1:
                # En yeni grubu al
                newest_group = direct_groups.first()
                
                # Diğer grupları temizle
                for group in direct_groups[1:]:
                    # Silmeden önce mesajları yeni gruba taşı
                    messages_to_move = Message.objects.filter(group=group)
                    for msg in messages_to_move:
                        new_msg = Message.objects.create(
                            sender=msg.sender,
                            group=newest_group,
                            message_type=msg.message_type,
                            content=msg.content,
                            file=msg.file,
                            created_at=msg.created_at,
                            updated_at=msg.updated_at
                        )
                        
                        # Okunma durumlarını da kopyala
                        for status in msg.read_status.all():
                            MessageReadStatus.objects.create(
                                message=new_msg,
                                user=status.user,
                                is_read=status.is_read,
                                read_at=status.read_at
                            )
                    
                    # Grubu sil
                    group.delete()
                    cleaned_count += 1
    
    messages.success(request, f'{cleaned_count} adet tekrarlanan direkt mesaj grubu temizlendi.')
    return redirect('communications:chat_list')

# ---------- API Endpoints ---------- #

@login_required
def get_unread_count(request):
    """Okunmamış mesaj ve bildirim sayısını API olarak döndürür."""
    # GitHub issue'larla ilişkili görevlerin ID'lerini al (exclude edilecek)
    github_task_ids = Task.objects.filter(github_issue__isnull=False).values_list('id', flat=True)
    
    # Okunmamış mesaj sayısı (GitHub ile ilişkili olmayan)
    unread_message_count = MessageReadStatus.objects.filter(
        user=request.user,
        is_read=False
    ).exclude(
        # GitHub issue ile ilişkili mesajları hariç tut
        message__group__related_task_id__in=github_task_ids
    ).count()
    
    # Okunmamış bildirim sayısı
    unread_notification_count = Notification.objects.filter(
        recipient=request.user,
        is_read=False
    ).count()
    
    return JsonResponse({
        'unread_message_count': unread_message_count,
        'unread_notification_count': unread_notification_count
    })

@login_required
def notification_list(request):
    """Kullanıcının bildirimlerini listeleyen view."""
    # Bildirimler
    notifications = Notification.objects.filter(recipient=request.user).order_by('-created_at')
    
    # Sayfalama
    paginator = Paginator(notifications, 10)  # Her sayfada 10 bildirim
    page_number = request.GET.get('page')
    notifications_page = paginator.get_page(page_number)
    
    # Okunmamış bildirim sayısı
    unread_count = notifications.filter(is_read=False).count()
    
    context = {
        'title': 'Bildirimler',
        'notifications_page': notifications_page,
        'unread_count': unread_count,
    }
    return render(request, 'communications/notification_list.html', context)

@login_required
def notification_detail(request, notification_id):
    """Bildirim detayını gösteren view."""
    notification = get_object_or_404(Notification, id=notification_id, recipient=request.user)
    
    # Bildirimi okundu olarak işaretle
    if not notification.is_read:
        notification.mark_as_read()
    
    # Sohbet silme onayı işlemi
    if 'sohbeti silmek istiyor' in notification.content and notification.related_message_group:
        if request.method == 'POST':
            action = request.POST.get('action')
            group = notification.related_message_group
            
            if action == 'approve':
                # Onay verildi, grubu tamamen sil
                group_name = group.name
                
                # Silme işlemi yapılıyor, kalan üyelere bildirim gönder
                remaining_members = group.members.all()
                for member in remaining_members:
                    if member != request.user:  # Kendimize bildirim göndermeye gerek yok
                        Notification.objects.create(
                            recipient=member,
                            sender=request.user,
                            title="Sohbet Silindi",
                            content=f"{request.user.get_full_name() or request.user.username} sohbeti silme isteğini onayladı ve sohbet tamamen silindi.",
                            notification_type='info'
                        )
                
                # Grubu sil
                group.delete()
                
                messages.success(request, f"Sohbet silme isteği onaylandı ve sohbet tamamen silindi.")
                return redirect('communications:chat_list')
            elif action == 'reject':
                # Red edildi, bildirim gönderilen kullanıcıya bildir ve grubu yeniden erişilebilir yap
                sender = notification.sender
                
                # Red bildirimi gönder
                Notification.objects.create(
                    recipient=sender,
                    sender=request.user,
                    title="Sohbet Silme İsteği Reddedildi",
                    content=f"{request.user.get_full_name() or request.user.username} sohbeti silme isteğinizi reddetti.",
                    notification_type='info'
                )
                
                # Sistem mesajı ekle
                Message.objects.create(
                    sender=request.user,
                    group=group,
                    message_type='system',
                    content=f"{request.user.get_full_name() or request.user.username} sohbet silme isteğini reddetti."
                )
                
                # Kullanıcıyı yeniden gruba ekle
                if not MessageGroupMember.objects.filter(group=group, user=sender).exists():
                    MessageGroupMember.objects.create(
                        group=group,
                        user=sender,
                        role='member'
                    )
                
                messages.success(request, f"Sohbet silme isteğini reddettiniz.")
                return redirect('communications:chat_detail', group_id=group.id)
            
        # Onay ekranını göster
        return render(request, 'communications/delete_direct_chat_approve.html', {
            'notification': notification,
            'group': notification.related_message_group
        })
    
    # İlgili içeriğe yönlendirme
    if notification.related_project:
        return redirect('projects:project_detail', project_id=notification.related_project.id)
    elif notification.related_task:
        return redirect('tasks:task_detail', task_id=notification.related_task.id)
    elif notification.related_message_group:
        return redirect('communications:chat_detail', group_id=notification.related_message_group.id)
    
    # İlişkili bir içerik yoksa, bildirimler sayfasına geri dön
    messages.info(request, 'Bu bildirimle ilişkili içerik bulunamadı.')
    return redirect('communications:notification_list')

@login_required
def mark_all_notifications_as_read(request):
    """Tüm bildirimleri okundu olarak işaretler."""
    # Kullanıcının tüm okunmamış bildirimlerini getir
    Notification.objects.filter(recipient=request.user, is_read=False).update(
        is_read=True,
        read_at=timezone.now()
    )
    
    messages.success(request, 'Tüm bildirimler okundu olarak işaretlendi.')
    return redirect('communications:notification_list')

@login_required
def load_more_messages(request, group_id):
    """
    Belirli bir gruptan belirli bir ID'den sonraki yeni mesajları yükler.
    AJAX çağrıları için JSON yanıt döndürür.
    """
    group = get_object_or_404(MessageGroup, id=group_id)
    
    # Kullanıcının grupta olup olmadığını kontrol et
    if not group.members.filter(id=request.user.id).exists():
        return JsonResponse({'error': 'Bu gruba erişim izniniz yok.'}, status=403)
    
    last_message_id = request.GET.get('last_message_id', 0)
    
    # Son mesaj ID'sinden sonraki mesajları al
    new_messages = group.messages.filter(id__gt=last_message_id).order_by('created_at')
    
    messages_data = []
    
    for message in new_messages:
        # Mesaj okundu olarak işaretle
        if message.sender != request.user:
            if hasattr(message, 'read_status'):
                status, created = MessageReadStatus.objects.get_or_create(
                    message=message,
                    user=request.user,
                    defaults={'is_read': True, 'read_at': timezone.now()}
                )
                if not status.is_read:
                    status.is_read = True
                    status.read_at = timezone.now()
                    status.save()
        
        # Mesaj verisini hazırla
        message_data = {
            'id': message.id,
            'content': message.content,
            'sender_name': message.sender.get_full_name() or message.sender.username,
            'created_at': message.created_at.strftime('%d.%m.%Y %H:%M'),
            'is_sender': message.sender == request.user,
            'is_system': message.message_type == 'system',
        }
        
        # Yanıtlanan mesaj varsa ekle
        if message.parent_message:
            message_data['parent_message'] = message.parent_message.content[:100] + ('...' if len(message.parent_message.content) > 100 else '')
        
        # Dosya varsa ekle
        if message.file:
            message_data['file'] = True
            message_data['file_url'] = message.file.url
            message_data['file_name'] = os.path.basename(message.file.name)
        
        # Okunma durumunu ekle
        if message.sender == request.user:
            read_count = message.read_status.filter(is_read=True).count()
            message_data['read_count'] = read_count
            message_data['total_members'] = group.members.count()
        
        messages_data.append(message_data)
    
    return JsonResponse({'messages': messages_data})

@login_required
def get_unread_notifications(request):
    """
    Kullanıcının okunmamış bildirimlerini getiren API endpoint'i.
    Son görüntülenen bildirim ID'sinden sonrakileri getirir.
    """
    last_id = request.GET.get('last_id', 0)
    try:
        last_id = int(last_id)
    except ValueError:
        last_id = 0
        
    # Okunmamış bildirimleri al
    notifications = Notification.objects.filter(
        recipient=request.user,
        is_read=False,
        id__gt=last_id
    ).order_by('-created_at')[:10]  # Sadece son 10 bildirimi getir
    
    # Bildirimleri JSON formatına dönüştür
    notifications_data = []
    for notification in notifications:
        notifications_data.append({
            'id': notification.id,
            'title': notification.title,
            'content': notification.content,
            'notification_type': notification.notification_type,
            'created_at': notification.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            'url': notification.get_absolute_url(),
            'sender': notification.sender.get_full_name() if notification.sender else None,
        })
    
    return JsonResponse({
        'notifications': notifications_data,
        'count': len(notifications_data)
    })

# ----- Direkt Mesajlaşma Sistemi (Yeni) -----

@login_required
def direct_messages_list(request):
    """Kullanıcının direkt mesajlaşmalarını listeleyen view."""
    # Kullanıcının tüm direkt mesajlaşmalarını bul
    user_direct_messages = DirectMessage.objects.filter(
        Q(user1=request.user) | Q(user2=request.user)
    ).order_by('-updated_at')
    
    # Son mesajları ve diğer kullanıcı bilgilerini ekle
    for dm in user_direct_messages:
        dm.other_user = dm.get_other_user(request.user)
        dm.last_message = dm.get_last_message()
        dm.unread_count = dm.get_unread_count(request.user)
    
    context = {
        'title': 'Direkt Mesajlar',
        'direct_messages': user_direct_messages
    }
    return render(request, 'communications/direct_messages_list.html', context)

@login_required
def direct_message_detail(request, dm_id):
    """Direkt mesajlaşma detayını gösteren view."""
    # Mesajlaşmayı bul ve erişim kontrolü yap
    direct_message = get_object_or_404(
        DirectMessage,
        Q(id=dm_id) & (Q(user1=request.user) | Q(user2=request.user))
    )
    
    # Diğer kullanıcıyı belirle
    other_user = direct_message.get_other_user(request.user)
    
    # Mesajları okundu olarak işaretle
    direct_message.mark_as_read(request.user)
    
    # Mesajları getir
    messages_list = direct_message.messages.all().order_by('sent_at')
    
    # Yeni mesaj formu için
    if request.method == 'POST':
        content = request.POST.get('content', '')
        file = request.FILES.get('file')
        
        if content or file:
            # Mesaj tipini belirle
            message_type = 'text'
            if file:
                # Resim kontrolü yapabilirsiniz
                message_type = 'image' if file.content_type.startswith('image/') else 'file'
                # Dosya adını mesaj içeriği olarak ayarla, eğer içerik yoksa
                if not content:
                    filename = os.path.basename(file.name)
                    if message_type == 'image':
                        content = f"Görsel: {filename}"
                    else:
                        content = f"Dosya: {filename}"
            
            # Mesajı oluştur
            message = DirectMessageContent.objects.create(
                direct_message=direct_message,
                sender=request.user,
                content=content,
                file=file,
                message_type=message_type
            )
            
            # AJAX isteği ise JSON yanıt döndür
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'status': 'success',
                    'message': {
                        'id': message.id,
                        'content': message.content,
                        'file_url': message.file.url if message.file else None,
                        'file_name': os.path.basename(message.file.name) if message.file else None,
                        'message_type': message.message_type,
                        'sent_at': message.sent_at.strftime('%H:%M'),
                        'is_sender': True
                    }
                })
            
            # Normal POST ise sayfayı yenile
            return redirect('communications:direct_message_detail', dm_id=direct_message.id)
    
    context = {
        'title': f'Mesajlaşma: {other_user.get_full_name() or other_user.username}',
        'direct_message': direct_message,
        'other_user': other_user,
        'messages_list': messages_list
    }
    return render(request, 'communications/direct_message_detail.html', context)

@login_required
def new_direct_message(request):
    """Yeni direkt mesajlaşma başlatmak için kullanıcı listesi."""
    # Tüm kullanıcıları getir (kendisi hariç)
    users = CustomUser.objects.exclude(id=request.user.id).order_by('first_name', 'last_name')
    
    # Basit bir form tanımlayalım
    class DirectMessageForm(forms.Form):
        recipient = forms.ModelChoiceField(
            queryset=users,
            required=True,
            label="Alıcı"
        )
        content = forms.CharField(
            widget=forms.Textarea(attrs={'rows': 5, 'placeholder': 'Mesajınızı yazın...'}),
            required=True,
            label="Mesaj"
        )
    
    # POST isteği ise form işleme
    if request.method == 'POST':
        form = DirectMessageForm(request.POST)
        if form.is_valid():
            recipient = form.cleaned_data['recipient']
            content = form.cleaned_data['content']
            
            # Bu iki kullanıcı arasında zaten bir mesajlaşma var mı kontrol et
            dm = DirectMessage.objects.filter(
                (Q(user1=request.user) & Q(user2=recipient)) |
                (Q(user1=recipient) & Q(user2=request.user))
            ).first()
            
            # Yoksa yeni bir mesajlaşma oluştur
            if not dm:
                dm = DirectMessage.objects.create(
                    user1=request.user,
                    user2=recipient
                )
                
                # Sistem mesajı ekle
                DirectMessageContent.objects.create(
                    direct_message=dm,
                    sender=request.user,
                    content=f"Mesajlaşma başlatıldı",
                    message_type='system'
                )
            
            # Mesajı ekle
            DirectMessageContent.objects.create(
                direct_message=dm,
                sender=request.user,
                content=content,
                message_type='text'
            )
            
            # Mesajlaşma detayına yönlendir
            return redirect('communications:direct_message_detail', dm_id=dm.id)
    else:
        form = DirectMessageForm()
    
    # Her kullanıcı için mevcut bir direkt mesajlaşma var mı kontrol et
    for user in users:
        # İki kullanıcı arasında direkt mesajlaşma var mı?
        dm = DirectMessage.objects.filter(
            (Q(user1=request.user) & Q(user2=user)) |
            (Q(user1=user) & Q(user2=request.user))
        ).first()
        
        user.existing_dm_id = dm.id if dm else None
    
    context = {
        'title': 'Yeni Direkt Mesaj',
        'users': users,
        'form': form
    }
    return render(request, 'communications/direct_message_new.html', context)

@login_required
def start_direct_message(request, user_id):
    """Belirli bir kullanıcıyla direkt mesajlaşma başlat veya var olan mesajlaşmayı aç."""
    # Hedef kullanıcıyı bul
    other_user = get_object_or_404(CustomUser, id=user_id)
    
    # Kendisiyle mesajlaşmayı engelle
    if other_user.id == request.user.id:
        messages.error(request, 'Kendinizle mesajlaşamazsınız.')
        return redirect('communications:direct_messages_list')
    
    # Bu iki kullanıcı arasında zaten bir mesajlaşma var mı kontrol et
    dm = DirectMessage.objects.filter(
        (Q(user1=request.user) & Q(user2=other_user)) |
        (Q(user1=other_user) & Q(user2=request.user))
    ).first()
    
    # Yoksa yeni bir mesajlaşma oluştur
    if not dm:
        dm = DirectMessage.objects.create(
            user1=request.user,
            user2=other_user
        )
        
        # Sistem mesajı ekle
        DirectMessageContent.objects.create(
            direct_message=dm,
            sender=request.user,
            content=f"Mesajlaşma başlatıldı",
            message_type='system'
        )
        
    # Mesajlaşma detayına yönlendir
    return redirect('communications:direct_message_detail', dm_id=dm.id)

@login_required
def load_more_direct_messages(request, dm_id):
    """AJAX çağrısı için, belirli bir tarihten sonraki mesajları yükler."""
    # Mesajlaşmayı bul ve erişim kontrolü yap
    direct_message = get_object_or_404(
        DirectMessage, 
        Q(id=dm_id) & (Q(user1=request.user) | Q(user2=request.user))
    )
    
    # Son yüklenen mesaj ID'sini al
    last_message_id = request.GET.get('last_message_id', 0)
    
    # Bu ID'den sonraki mesajları getir
    new_messages = direct_message.messages.filter(id__gt=last_message_id).order_by('sent_at')
    
    # Mesajları JSON formatında hazırla
    messages_data = []
    for message in new_messages:
        message_data = {
            'id': message.id,
            'content': message.content,
            'sent_at': message.sent_at.strftime('%H:%M'),
            'is_sender': message.sender == request.user,
            'is_system': message.message_type == 'system'
        }
        
        if message.file:
            message_data['file_url'] = message.file.url
            message_data['file_name'] = os.path.basename(message.file.name)
            message_data['message_type'] = message.message_type
            
        messages_data.append(message_data)
    
    # Mesajları okundu olarak işaretle
    direct_message.mark_as_read(request.user)
    
    return JsonResponse({'messages': messages_data})

@login_required
def get_unread_dm_count(request):
    """Kullanıcının okunmamış direkt mesaj sayısını döndürür."""
    # Kullanıcının tüm direkt mesajlaşmalarında okunmamış mesaj sayısı
    unread_count = DirectMessage.objects.filter(
        Q(user1=request.user, user1_unread__gt=0) |
        Q(user2=request.user, user2_unread__gt=0)
    ).count()
    
    return JsonResponse({'unread_count': unread_count})

@login_required
def delete_direct_message(request, dm_id):
    """Direkt mesajlaşmayı siler."""
    # Mesajlaşmayı bul ve erişim kontrolü yap
    direct_message = get_object_or_404(
        DirectMessage, 
        Q(id=dm_id) & (Q(user1=request.user) | Q(user2=request.user))
    )
    
    if request.method == 'POST':
        try:
            # Mesajlaşmaya ait tüm içerikleri sil
            DirectMessageContent.objects.filter(direct_message=direct_message).delete()
            
            # Direkt mesajlaşmayı sil
            direct_message.delete()
            
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'status': 'success', 'message': 'Konuşma başarıyla silindi.'})
            else:
                messages.success(request, 'Konuşma başarıyla silindi.')
                return redirect('communications:direct_messages_list')
        except Exception as e:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'status': 'error', 'message': str(e)})
            else:
                messages.error(request, f'Konuşma silinirken bir hata oluştu: {str(e)}')
                return redirect('communications:direct_message_detail', dm_id=dm_id)
    
    # GET isteği ise direkt mesajlaşma sayfasına yönlendir
    return redirect('communications:direct_message_detail', dm_id=dm_id)

@login_required
def request_delete_direct_chat(request, group_id):
    """
    Direkt mesaj grubunu silme isteği gönderir.
    Silme isteği, kullanıcının kendi tarafından sohbeti kaldırır ve
    karşı taraf onaylarsa tamamen silinir.
    """
    # Grubu bul
    try:
        group = MessageGroup.objects.get(id=group_id)
    except MessageGroup.DoesNotExist:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'status': 'error', 'message': 'Grup bulunamadı.'})
        messages.error(request, 'Grup bulunamadı.')
        return redirect('communications:chat_list')
    
    # Sadece direkt mesaj grupları için izin ver
    if group.type != 'direct':
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'status': 'error', 'message': 'Bu işlem sadece direkt mesajlar için kullanılabilir.'})
        messages.error(request, 'Bu işlem sadece direkt mesajlar için kullanılabilir.')
        return redirect('communications:chat_detail', group_id=group.id)
    
    # Kullanıcının grupta olduğunu kontrol et
    if not request.user in group.members.all():
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'status': 'error', 'message': 'Bu gruba erişiminiz yok.'})
        messages.error(request, 'Bu gruba erişiminiz yok.')
        return redirect('communications:chat_list')
    
    if request.method == 'POST':
        # Grupta diğer kullanıcıyı bul
        other_user = group.members.exclude(id=request.user.id).first()
        
        # Silme isteği bildirimi oluştur
        Notification.objects.create(
            recipient=other_user,
            sender=request.user,
            title="Sohbet Silme İsteği",
            content=f"{request.user.get_full_name() or request.user.username} sizinle olan sohbeti silmek istiyor. Onaylıyor musunuz?",
            notification_type='warning',
            related_message_group=group
        )
        
        # Sistem mesajı ekle
        Message.objects.create(
            sender=request.user,
            group=group,
            message_type='system',
            content=f"{request.user.get_full_name() or request.user.username} sohbeti silmek istiyor."
        )
        
        # Kullanıcıyı gruptan çıkar (tamamen silmiyoruz çünkü karşı taraf hala görebilmeli)
        MessageGroupMember.objects.filter(group=group, user=request.user).delete()
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'status': 'success', 'message': 'Silme isteği gönderildi.'})
        
        messages.success(request, 'Silme isteği gönderildi ve sohbet sizin tarafınızdan kaldırıldı.')
        return redirect('communications:chat_list')
    
    # GET isteği ise onay sayfasını göster
    context = {
        'title': 'Sohbeti Sil',
        'group': group,
    }
    return render(request, 'communications/delete_direct_chat_confirm.html', context)
