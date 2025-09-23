from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.forms import PasswordChangeForm
from .models import CustomUser
from django import forms
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Submit, Row, Column, Field, Div, HTML

# Check if the user is an admin or has edit permissions
def can_edit_profile(user):
    return user.role in ['admin', 'project_manager']

# Create your views here.

@login_required
def user_profile(request, user_id):
    """
    Kullanıcı profil sayfasını görüntüler
    """
    user = get_object_or_404(CustomUser, id=user_id)
    
    # If this is the user's own profile and they submitted a request to edit
    # and they have permission to edit
    if user == request.user and request.method == 'POST' and can_edit_profile(request.user):
        form = ProfileSettingsForm(request.POST, request.FILES, instance=user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Profil bilgileriniz başarıyla güncellendi.')
            return redirect('accounts:user_profile', user_id=user.id)
    elif user == request.user:
        # Form is for display purposes only unless user has edit permissions
        form = ProfileDisplayForm(instance=user)
    else:
        form = None
    
    context = {
        'profile_user': user,
        'is_own_profile': user == request.user,
        'form': form,
        'can_edit': can_edit_profile(request.user)
    }
    
    return render(request, 'accounts/user_profile.html', context)

class ProfileDisplayForm(forms.ModelForm):
    """Form for displaying user profile settings (read-only)"""
    class Meta:
        model = CustomUser
        fields = ['first_name', 'last_name', 'email', 'department', 'phone', 'bio', 'role']
        widgets = {
            'bio': forms.Textarea(attrs={'rows': 4, 'readonly': 'readonly'}),
            'first_name': forms.TextInput(attrs={'readonly': 'readonly'}),
            'last_name': forms.TextInput(attrs={'readonly': 'readonly'}),
            'email': forms.EmailInput(attrs={'readonly': 'readonly'}),
            'department': forms.TextInput(attrs={'readonly': 'readonly'}),
            'phone': forms.TextInput(attrs={'readonly': 'readonly'}),
            'role': forms.TextInput(attrs={'readonly': 'readonly'}),
        }
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.form_tag = False  # The form tag will be in the template
        
        for field_name, field in self.fields.items():
            field.disabled = True
            field.widget.attrs.update({'class': 'form-control'})

class ProfileSettingsForm(forms.ModelForm):
    """Form for user profile settings (for admins and managers)"""
    class Meta:
        model = CustomUser
        fields = ['first_name', 'last_name', 'department', 'bio', 'profile_picture', 'role']
        widgets = {
            'bio': forms.Textarea(attrs={'rows': 4}),
        }
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.form_tag = False  # The form tag will be in the template
        
        self.fields['first_name'].widget.attrs.update({'class': 'form-control'})
        self.fields['last_name'].widget.attrs.update({'class': 'form-control'})
        self.fields['department'].widget.attrs.update({'class': 'form-control'})
        self.fields['bio'].widget.attrs.update({'class': 'form-control'})
        self.fields['role'].widget.attrs.update({'class': 'form-control'})
        
        # Only admin users can change roles, project managers see it as read-only
        if not kwargs.get('instance') or kwargs.get('instance').role != 'admin':
            self.fields['role'].disabled = True
            self.fields['role'].widget.attrs.update({'readonly': 'readonly'})
            self.fields['role'].help_text = 'Rol değişikliği sadece yöneticiler tarafından yapılabilir.'

class SecurityDisplayForm(forms.ModelForm):
    """Form for displaying security settings (read-only)"""
    class Meta:
        model = CustomUser
        fields = ['email', 'phone']
        widgets = {
            'email': forms.EmailInput(attrs={'readonly': 'readonly'}),
            'phone': forms.TextInput(attrs={'readonly': 'readonly'}),
        }
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.form_tag = False  # The form tag will be in the template
        
        for field_name, field in self.fields.items():
            field.disabled = True
            field.widget.attrs.update({'class': 'form-control'})

class SecuritySettingsForm(forms.ModelForm):
    """Form for security settings (for admins only)"""
    class Meta:
        model = CustomUser
        fields = ['email', 'phone']
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.form_tag = False  # The form tag will be in the template
        
        self.fields['email'].widget.attrs.update({'class': 'form-control'})
        self.fields['phone'].widget.attrs.update({'class': 'form-control'})

@login_required
def user_settings(request):
    """
    Kullanıcı hesap ayarları sayfasını görüntüler ve form gönderimlerini işler
    """
    user = request.user
    active_tab = request.GET.get('tab', 'profile')
    is_admin = can_edit_profile(user)
    
    if request.method == 'POST' and is_admin:
        if 'profile-form' in request.POST:
            profile_form = ProfileSettingsForm(request.POST, request.FILES, instance=user)
            security_form = SecuritySettingsForm(instance=user) if is_admin else SecurityDisplayForm(instance=user)
            password_form = PasswordChangeForm(user)
            
            if profile_form.is_valid():
                profile_form.save()
                messages.success(request, 'Profil bilgileriniz başarıyla güncellendi.')
                return redirect('accounts:user_settings')
            active_tab = 'profile'
                
        elif 'security-form' in request.POST:
            security_form = SecuritySettingsForm(request.POST, instance=user)
            profile_form = ProfileSettingsForm(instance=user) if is_admin else ProfileDisplayForm(instance=user)
            password_form = PasswordChangeForm(user)
            
            if security_form.is_valid():
                security_form.save()
                messages.success(request, 'Güvenlik bilgileriniz başarıyla güncellendi.')
                return redirect('accounts:user_settings?tab=security')
            active_tab = 'security'
                
        elif 'password-form' in request.POST:
            password_form = PasswordChangeForm(user, request.POST)
            profile_form = ProfileSettingsForm(instance=user) if is_admin else ProfileDisplayForm(instance=user)
            security_form = SecuritySettingsForm(instance=user) if is_admin else SecurityDisplayForm(instance=user)
            
            if password_form.is_valid():
                user = password_form.save()
                # Keep the user logged in
                update_session_auth_hash(request, user)
                messages.success(request, 'Şifreniz başarıyla değiştirildi.')
                return redirect('accounts:user_settings?tab=security')
            active_tab = 'security'
    else:
        # Regular users get read-only forms
        profile_form = ProfileSettingsForm(instance=user) if is_admin else ProfileDisplayForm(instance=user)
        security_form = SecuritySettingsForm(instance=user) if is_admin else SecurityDisplayForm(instance=user)
        password_form = PasswordChangeForm(user)
    
    context = {
        'profile_form': profile_form,
        'security_form': security_form,
        'password_form': password_form,
        'active_tab': active_tab,
        'can_edit': is_admin
    }
    
    return render(request, 'accounts/user_settings.html', context)

@login_required
def security_settings(request):
    """
    Kullanıcı güvenlik ayarları sayfasını görüntüler ve form gönderimlerini işler
    """
    return redirect('accounts:user_settings', tab='security')
