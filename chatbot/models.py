from django.db import models
from django.conf import settings

class ChatSession(models.Model):
    """Model representing a chat session between a user and the AI assistant."""
    
    MODEL_CHOICES = (
        ('gemma3:4b', 'Gemma 3 (4B) - Hızlı ve Verimli'),
        ('deepseek-r1:8b', 'DeepSeek R1 (8B) - Gelişmiş Akıl Yürütme'),
    )
    
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    title = models.CharField(max_length=255, default="New Chat")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    language = models.CharField(max_length=10, default="tr", help_text='AI yanıtlarının tercih edilen dili (tr, en, vb.)')
    session_id = models.CharField(max_length=100, blank=True, null=True, unique=True, help_text='Harici API için session ID. Kullanıcı bazında benzersiz olmalıdır.')
    ai_model = models.CharField(max_length=20, choices=MODEL_CHOICES, default='deepseek-r1:8b', help_text='Kullanılacak AI modeli')
    
    def __str__(self):
        return f"{self.title} - {self.user.username}"

class OllamaSettings(models.Model):
    """Kullanıcıya özel Ollama API ayarları"""
    
    LANGUAGE_CHOICES = (
        ('tr', 'Türkçe'),
        ('en', 'English'),
        ('fr', 'Français'),
        ('de', 'Deutsch'),
    )
    
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE,
        related_name='ollama_settings',
        verbose_name='Kullanıcı'
    )
    api_url = models.URLField(
        default='http://localhost:11434',
        help_text='Ollama API URL (örn: http://192.168.1.100:11434)',
        verbose_name='API URL'
    )
    default_model = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text='Varsayılan AI modeli (boş bırakılırsa otomatik seçilir)',
        verbose_name='Varsayılan Model'
    )
    default_language = models.CharField(
        max_length=5,
        choices=LANGUAGE_CHOICES,
        default='tr',
        help_text='AI yanıtlarının varsayılan dili',
        verbose_name='Varsayılan Dil'
    )
    is_active = models.BooleanField(
        default=True,
        help_text='Bu ayarların aktif olup olmadığı',
        verbose_name='Aktif'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Ollama Ayarları'
        verbose_name_plural = 'Ollama Ayarları'
    
    def __str__(self):
        return f"{self.user.username} - {self.api_url}"
    
    def get_available_models(self):
        """Kullanıcının API'sinden mevcut modelleri getir"""
        try:
            import requests
            test_url = f"{self.api_url}/api/tags" if not self.api_url.endswith('/api/tags') else self.api_url
            if not test_url.endswith('/api/tags'):
                test_url = f"{test_url}/api/tags"
            
            response = requests.get(test_url, timeout=15)
            if response.status_code == 200:
                data = response.json()
                models = data.get('models', [])
                return [model.get('name', 'Bilinmeyen') for model in models]
        except Exception:
            pass
        return []

class ChatMessage(models.Model):
    """Model representing individual messages in a chat session."""
    SENDER_CHOICES = (
        ('user', 'User'),
        ('assistant', 'Assistant'),
    )
    
    session = models.ForeignKey(ChatSession, on_delete=models.CASCADE, related_name='messages')
    sender = models.CharField(max_length=10, choices=SENDER_CHOICES)
    content = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['timestamp']
    
    def __str__(self):
        return f"{self.sender}: {self.content[:50]}{'...' if len(self.content) > 50 else ''}"
