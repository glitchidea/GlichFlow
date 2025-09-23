from django import forms
from django.utils.translation import gettext_lazy as _
from .models import GitHubRepository, GitHubProfile
from django.conf import settings

class GitHubAuthForm(forms.Form):
    """
    GitHub OAuth yetkilendirme formu.
    """
    accept_auth = forms.BooleanField(
        label=_('GitHub hesabımı bağlamak için izin veriyorum'),
        required=True,
        help_text=_('GitHub hesabınızı bağlamak için izin vermeniz gerekiyor.')
    )

class GitHubRepositoryForm(forms.Form):
    """
    GitHub repository bağlama veya oluşturma formu.
    """
    REPOSITORY_CHOICES = (
        ('existing', _('Varolan bir repository bağla')),
        ('new', _('Yeni bir repository oluştur')),
    )
    
    repository_choice = forms.ChoiceField(
        label=_('Repository Seçeneği'),
        choices=REPOSITORY_CHOICES,
        required=True,
        widget=forms.RadioSelect,
        initial='existing'
    )
    
    existing_repository = forms.ChoiceField(
        label=_('Repository'),
        required=False,
        help_text=_('Projeye bağlamak istediğiniz mevcut repository\'yi seçin.')
    )
    
    repository_name = forms.CharField(
        label=_('Repository Adı'),
        max_length=100,
        required=False,
        help_text=_('Oluşturulacak yeni repository\'nin adı.')
    )
    
    is_private = forms.BooleanField(
        label=_('Özel Repository'),
        required=False,
        initial=True,
        help_text=_('Repository sadece belirli kullanıcılar tarafından görülebilir.')
    )
    
    def __init__(self, *args, **kwargs):
        repositories = kwargs.pop('repositories', None)
        super(GitHubRepositoryForm, self).__init__(*args, **kwargs)
        
        if repositories:
            choices = [(f"{repo.get('owner', {}).get('login')}/{repo.get('name')}", 
                       f"{repo.get('owner', {}).get('login')}/{repo.get('name')}") 
                      for repo in repositories]
            self.fields['existing_repository'].choices = [('', _('Repository seçin'))] + choices
    
    def clean(self):
        cleaned_data = super().clean()
        repository_choice = cleaned_data.get('repository_choice')
        
        if repository_choice == 'existing':
            if not cleaned_data.get('existing_repository'):
                self.add_error('existing_repository', _('Lütfen bir repository seçin.'))
        elif repository_choice == 'new':
            if not cleaned_data.get('repository_name'):
                self.add_error('repository_name', _('Repository adı gerekli.'))
        
        return cleaned_data

class GitHubIssueImportForm(forms.Form):
    """
    GitHub issue'larını içe aktarma formu.
    """
    import_all = forms.BooleanField(
        label=_('Tüm issue\'ları içe aktar'),
        required=False,
        initial=True,
        help_text=_('Tüm açık ve kapalı issue\'ları içe aktarır.')
    )
    
    import_closed = forms.BooleanField(
        label=_('Kapalı issue\'ları da içe aktar'),
        required=False,
        initial=False,
        help_text=_('Kapalı issue\'lar, tamamlanmış görev olarak içe aktarılır.')
    )
    
    issue_numbers = forms.CharField(
        label=_('Issue Numaraları (virgülle ayrılmış)'),
        required=False,
        help_text=_('Örnek: 1,4,7,12'),
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    
    def clean(self):
        cleaned_data = super().clean()
        import_all = cleaned_data.get('import_all')
        import_closed = cleaned_data.get('import_closed')
        issue_numbers = cleaned_data.get('issue_numbers')
        
        if not import_all and not import_closed and not issue_numbers:
            raise forms.ValidationError(_('Tüm issue\'ları içe aktarmak istemiyor iseniz, belirli issue numaralarını girmelisiniz.'))
        
        return cleaned_data

class GitHubOAuthSettingsForm(forms.ModelForm):
    """
    Kullanıcının GitHub OAuth ayarlarını düzenlemesi için form.
    """
    class Meta:
        model = GitHubProfile
        fields = ['client_id', 'client_secret', 'redirect_uri', 'use_personal_oauth']
        widgets = {
            'client_secret': forms.PasswordInput(render_value=True),
        }
        
    def __init__(self, *args, **kwargs):
        super(GitHubOAuthSettingsForm, self).__init__(*args, **kwargs)
        self.fields['client_id'].widget.attrs.update({'class': 'form-control'})
        self.fields['client_secret'].widget.attrs.update({'class': 'form-control'})
        self.fields['redirect_uri'].widget.attrs.update({'class': 'form-control'})
        self.fields['redirect_uri'].initial = f"{settings.GITHUB_REDIRECT_URI}" if not self.instance.redirect_uri else self.instance.redirect_uri
        
        self.fields['client_id'].help_text = _('GitHub Developer Settings\'ten aldığınız Client ID')
        self.fields['client_secret'].help_text = _('GitHub Developer Settings\'ten aldığınız Client Secret')
        self.fields['redirect_uri'].help_text = _('GitHub callback URL\'i, genellikle: http://[alan-adınız]/github/callback/')
        self.fields['use_personal_oauth'].help_text = _('Bu seçenek etkinleştirildiğinde, sistem aşağıdaki kimlik bilgilerini kullanarak GitHub\'a bağlanır.') 