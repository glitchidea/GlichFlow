from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q
from django.http import HttpResponseForbidden

from .models import Team, TeamMember
from accounts.models import CustomUser
from projects.models import Project

@login_required
def team_list(request):
    """
    Ekiplerin listesini gösterir.
    """
    # Kullanıcının rolüne göre filtreleme
    if request.user.role in ['admin', 'project_manager']:
        # Admin ve proje yöneticileri tüm ekipleri görebilir
        teams = Team.objects.all()
    else:
        # Diğer kullanıcılar sadece üye oldukları veya lider oldukları ekipleri görebilir
        teams = Team.objects.filter(
            Q(members=request.user) | Q(leader=request.user)
        ).distinct()
    
    context = {
        'title': 'Ekipler',
        'teams': teams
    }
    
    return render(request, 'teams/team_list.html', context)

@login_required
def team_detail(request, team_id):
    """
    Ekip detaylarını gösterir.
    """
    team = get_object_or_404(Team, id=team_id)
    
    # Kullanıcının ekibi görme yetkisi var mı kontrol et
    if request.user.role not in ['admin', 'project_manager'] and request.user not in team.members.all() and request.user != team.leader:
        messages.error(request, 'Bu ekibi görüntüleme yetkiniz yok.')
        return redirect('teams:team_list')
    
    # Ekip üyeleri
    team_members = TeamMember.objects.filter(team=team).select_related('user')
    
    context = {
        'title': team.name,
        'team': team,
        'team_members': team_members
    }
    
    return render(request, 'teams/team_detail.html', context)

@login_required
def team_create(request):
    """
    Yeni ekip oluşturma.
    """
    # Sadece admin ve proje yöneticileri ekip oluşturabilir
    if request.user.role not in ['admin', 'project_manager']:
        messages.error(request, 'Ekip oluşturma yetkiniz yok.')
        return redirect('teams:team_list')
    
    if request.method == 'POST':
        name = request.POST.get('name')
        description = request.POST.get('description', '')
        leader_id = request.POST.get('leader')
        members = request.POST.getlist('members')
        projects = request.POST.getlist('projects')
        
        if not name:
            messages.error(request, 'Ekip adı gereklidir.')
        else:
            # Yeni ekip oluştur
            team = Team(
                name=name,
                description=description
            )
            
            # Lider atama
            if leader_id:
                try:
                    leader = CustomUser.objects.get(id=leader_id)
                    team.leader = leader
                except CustomUser.DoesNotExist:
                    pass
            
            team.save()
            
            # Üyeleri ekle
            for member_id in members:
                try:
                    user = CustomUser.objects.get(id=member_id)
                    # Üyeyi ekip üyeleri arasına ekle
                    team_member = TeamMember(
                        team=team,
                        user=user,
                        role='member'  # Varsayılan rol: üye
                    )
                    
                    # Eğer bu üye aynı zamanda lider olarak seçildiyse, rolünü güncelle
                    if user == team.leader:
                        team_member.role = 'lead'
                    
                    team_member.save()
                except CustomUser.DoesNotExist:
                    continue
            
            # Projeleri ekle
            if projects:
                team.projects.set(Project.objects.filter(id__in=projects))
            
            messages.success(request, 'Ekip başarıyla oluşturuldu.')
            return redirect('teams:team_detail', team_id=team.id)
    
    # Potansiyel üyeler ve liderler
    users = CustomUser.objects.all()
    # Projeler listesini al
    all_projects = Project.objects.all()
    
    context = {
        'title': 'Yeni Ekip',
        'users': users,
        'projects': all_projects
    }
    
    return render(request, 'teams/team_form.html', context)

@login_required
def team_update(request, team_id):
    """
    Ekip bilgilerini güncelleme.
    """
    team = get_object_or_404(Team, id=team_id)
    
    # Sadece admin, proje yöneticileri ve ekip lideri güncelleyebilir
    if request.user.role not in ['admin', 'project_manager'] and request.user != team.leader:
        messages.error(request, 'Bu ekibi düzenleme yetkiniz yok.')
        return redirect('teams:team_detail', team_id=team.id)
    
    if request.method == 'POST':
        name = request.POST.get('name')
        description = request.POST.get('description', '')
        leader_id = request.POST.get('leader')
        members = request.POST.getlist('members')
        projects = request.POST.getlist('projects')
        
        if not name:
            messages.error(request, 'Ekip adı gereklidir.')
        else:
            # Ekip bilgilerini güncelle
            team.name = name
            team.description = description
            
            # Lider atama
            old_leader = team.leader
            if leader_id:
                try:
                    leader = CustomUser.objects.get(id=leader_id)
                    team.leader = leader
                except CustomUser.DoesNotExist:
                    pass
            else:
                team.leader = None
            
            team.save()
            
            # Mevcut üyeleri temizle ve yeniden ekle
            TeamMember.objects.filter(team=team).delete()
            
            # Üyeleri ekle
            for member_id in members:
                try:
                    user = CustomUser.objects.get(id=member_id)
                    # Üyeyi ekip üyeleri arasına ekle
                    team_member = TeamMember(
                        team=team,
                        user=user,
                        role='member'  # Varsayılan rol: üye
                    )
                    
                    # Eğer bu üye aynı zamanda lider olarak seçildiyse, rolünü güncelle
                    if user == team.leader:
                        team_member.role = 'lead'
                    
                    team_member.save()
                except CustomUser.DoesNotExist:
                    continue
            
            # Projeleri güncelle
            team.projects.set(Project.objects.filter(id__in=projects))
            
            messages.success(request, 'Ekip başarıyla güncellendi.')
            return redirect('teams:team_detail', team_id=team.id)
    
    # Mevcut üyeler
    team_members = TeamMember.objects.filter(team=team).values_list('user_id', flat=True)
    
    # Potansiyel üyeler ve liderler
    users = CustomUser.objects.all()
    # Projeler listesini al
    all_projects = Project.objects.all()
    
    context = {
        'title': f'{team.name} - Düzenle',
        'team': team,
        'users': users,
        'team_members': list(team_members),
        'projects': all_projects
    }
    
    return render(request, 'teams/team_form.html', context)

@login_required
def team_delete(request, team_id):
    """
    Ekip silme.
    """
    team = get_object_or_404(Team, id=team_id)
    
    # Sadece admin ve proje yöneticileri ekip silebilir
    if request.user.role not in ['admin', 'project_manager']:
        messages.error(request, 'Bu ekibi silme yetkiniz yok.')
        return redirect('teams:team_detail', team_id=team.id)
    
    if request.method == 'POST':
        team_name = team.name
        team.delete()
        messages.success(request, f'"{team_name}" ekibi başarıyla silindi.')
        return redirect('teams:team_list')
    
    context = {
        'title': f'{team.name} - Sil',
        'team': team
    }
    
    return render(request, 'teams/team_confirm_delete.html', context)
