from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.utils.text import slugify
from django.urls import reverse
import markdown
from django.utils.html import strip_tags

User = get_user_model()


class Article(models.Model):
    """Makale modeli - Blog benzeri makaleler için"""
    
    STATUS_CHOICES = [
        ('draft', 'Taslak'),
        ('published', 'Yayınlandı'),
        ('archived', 'Arşivlendi'),
    ]
    
    CATEGORY_CHOICES = [
        ('tutorial', 'Eğitim'),
        ('guide', 'Rehber'),
        ('review', 'İnceleme'),
        ('news', 'Haber'),
        ('technical', 'Teknik'),
        ('other', 'Diğer'),
    ]
    
    title = models.CharField('Başlık', max_length=255)
    slug = models.SlugField('URL Kodu', max_length=255, unique=True, blank=True)
    content = models.TextField('İçerik (Markdown)', help_text='Markdown formatında yazın')
    excerpt = models.TextField('Özet', max_length=500, blank=True, help_text='Makale özeti (opsiyonel)')
    category = models.CharField('Kategori', max_length=20, choices=CATEGORY_CHOICES, default='other')
    status = models.CharField('Durum', max_length=20, choices=STATUS_CHOICES, default='draft')
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='articles', verbose_name='Yazar')
    tags = models.CharField('Etiketler', max_length=255, blank=True, help_text='Virgülle ayırın: linux, ubuntu, kurulum')
    featured_image = models.ImageField('Öne Çıkan Görsel', upload_to='articles/images/', blank=True, null=True)
    view_count = models.PositiveIntegerField('Görüntülenme Sayısı', default=0)
    is_featured = models.BooleanField('Öne Çıkan', default=False, help_text='Ana sayfada öne çıkarılsın mı?')
    created_at = models.DateTimeField('Oluşturulma Tarihi', auto_now_add=True)
    updated_at = models.DateTimeField('Güncellenme Tarihi', auto_now=True)
    published_at = models.DateTimeField('Yayınlanma Tarihi', null=True, blank=True)
    
    class Meta:
        verbose_name = 'Makale'
        verbose_name_plural = 'Makaleler'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'created_at']),
            models.Index(fields=['author', 'created_at']),
            models.Index(fields=['category', 'status']),
        ]
    
    def __str__(self):
        return self.title
    
    def save(self, *args, **kwargs):
        # Slug oluştur
        if not self.slug:
            self.slug = slugify(self.title)
        
        # Yayınlandıysa published_at'i ayarla
        if self.status == 'published' and not self.published_at:
            self.published_at = timezone.now()
        
        super().save(*args, **kwargs)
    
    def get_absolute_url(self):
        return reverse('articles:article_detail', kwargs={'slug': self.slug})
    
    def get_content_html(self):
        """Markdown içeriği HTML'e çevir"""
        # Önce özel formatları düzelt
        content = self._preprocess_content(self.content)
        
        md = markdown.Markdown(extensions=[
            'codehilite', 
            'fenced_code', 
            'tables', 
            'toc',
            'extra',
            'nl2br',
            'def_list',
            'attr_list'
        ])
        return md.convert(content)
    
    def _preprocess_content(self, content):
        """İçeriği Markdown parse etmeden önce özel formatları düzelt"""
        import re
        
        # Önce kod bloklarını düzelt
        # 4 tane backtick olan yerleri 3 tane yap
        content = re.sub(r'````', '```', content)
        
        # Eksik kapanan kod bloklarını düzelt
        # ``` ile başlayan ama ``` ile bitmeyen satırları bul
        lines = content.split('\n')
        fixed_lines = []
        in_code_block = False
        code_block_start = -1
        
        for i, line in enumerate(lines):
            stripped = line.strip()
            
            # Kod bloğu başlangıcı
            if stripped.startswith('```') and not in_code_block:
                in_code_block = True
                code_block_start = i
                fixed_lines.append(line)
            # Kod bloğu kapanışı
            elif stripped.startswith('```') and in_code_block:
                in_code_block = False
                code_block_start = -1
                fixed_lines.append(line)
            # Kod bloğu içindeki satır
            elif in_code_block:
                fixed_lines.append(line)
            # Normal satır
            else:
                fixed_lines.append(line)
        
        # Eğer kod bloğu açık kaldıysa, kapat
        if in_code_block:
            fixed_lines.append('```')
        
        content = '\n'.join(fixed_lines)
        
        # Şimdi kod bloklarını korumak için geçici olarak değiştir
        code_blocks = []
        code_counter = 0
        
        def replace_code_block(match):
            nonlocal code_counter
            placeholder = f"__CODE_BLOCK_{code_counter}__"
            code_blocks.append((placeholder, match.group(0)))
            code_counter += 1
            return placeholder
        
        # Kod bloklarını bul ve geçici olarak değiştir
        content = re.sub(r'```[\s\S]*?```', replace_code_block, content)
        
        lines = content.split('\n')
        processed_lines = []
        
        for i, line in enumerate(lines):
            stripped = line.strip()
            
            # Kod bloğu placeholder'ı ise, olduğu gibi bırak
            if stripped.startswith('__CODE_BLOCK_'):
                processed_lines.append(line)
                continue
            
            # Boş satırları koru
            if not stripped:
                processed_lines.append('')
                continue
            
            # Kod bloğu dışında sadece belirli formatları işle
            # Zaten markdown listesi olan satırları değiştirme
            if stripped.startswith('* ') or stripped.startswith('- ') or stripped.startswith('+ '):
                processed_lines.append(line)
                continue
            if stripped.startswith('1. ') or stripped.startswith('2. ') or stripped.startswith('3. '):
                processed_lines.append(line)
                continue
            if stripped.startswith('  * ') or stripped.startswith('  - ') or stripped.startswith('  + '):
                processed_lines.append(line)
                continue
            if stripped.startswith('  1. ') or stripped.startswith('  2. ') or stripped.startswith('  3. '):
                processed_lines.append(line)
                continue
            
            # Alt maddeleme formatını tespit et (2.1, 2.2, vb.)
            if re.match(r'^\d+\.\d+', stripped):
                # Alt madde formatını Markdown listesine çevir
                processed_lines.append(f'  1. {stripped}')
            # "Alt madde X.Y" formatını tespit et
            elif re.match(r'^Alt madde \d+\.\d+', stripped):
                # Alt madde formatını Markdown listesine çevir
                processed_lines.append(f'  1. {stripped}')
            # A.B formatını tespit et (İkinci.A, İkinci.B, vb.)
            elif re.match(r'^[A-Za-zÇĞIİÖŞÜçğıiöşü]+\.\w+', stripped):
                # Alt alt madde formatını Markdown listesine çevir
                processed_lines.append(f'      1. {stripped}')
            # Normal madde formatını tespit et (sadece kelime, 3+ karakter)
            elif re.match(r'^[A-Za-zÇĞIİÖŞÜçğıiöşü]{3,}$', stripped):
                # Normal madde formatını Markdown listesine çevir
                processed_lines.append(f'1. {stripped}')
            else:
                # Normal satır
                processed_lines.append(line)
        
        result = '\n'.join(processed_lines)
        
        # Kod bloklarını geri yerleştir
        for placeholder, code_block in code_blocks:
            result = result.replace(placeholder, code_block)
        
        return result
    
    def get_excerpt_html(self):
        """Özeti HTML'e çevir veya içerikten otomatik oluştur"""
        if self.excerpt:
            md = markdown.Markdown()
            return md.convert(self.excerpt)
        else:
            # İçerikten ilk 200 karakteri al
            html_content = self.get_content_html()
            plain_text = strip_tags(html_content)
            return plain_text[:200] + '...' if len(plain_text) > 200 else plain_text
    
    def get_tags_list(self):
        """Etiketleri liste olarak döndür"""
        if self.tags:
            return [tag.strip() for tag in self.tags.split(',') if tag.strip()]
        return []
    
    def increment_view_count(self):
        """Görüntülenme sayısını artır"""
        self.view_count += 1
        self.save(update_fields=['view_count'])
    
    @property
    def reading_time(self):
        """Tahmini okuma süresi (dakika)"""
        word_count = len(self.content.split())
        return max(1, word_count // 200)  # Dakikada 200 kelime varsayımı
    
    @property
    def status_color(self):
        """Durum rengi"""
        colors = {
            'draft': 'secondary',
            'published': 'success',
            'archived': 'warning'
        }
        return colors.get(self.status, 'secondary')
    
    @property
    def category_color(self):
        """Kategori rengi"""
        colors = {
            'tutorial': 'primary',
            'guide': 'info',
            'review': 'warning',
            'news': 'danger',
            'technical': 'dark',
            'other': 'secondary'
        }
        return colors.get(self.category, 'secondary')


class ArticleComment(models.Model):
    """Makale yorumları"""
    
    article = models.ForeignKey(Article, on_delete=models.CASCADE, related_name='comments', verbose_name='Makale')
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='article_comments', verbose_name='Yazar')
    content = models.TextField('Yorum', max_length=1000)
    is_approved = models.BooleanField('Onaylandı', default=False)
    created_at = models.DateTimeField('Oluşturulma Tarihi', auto_now_add=True)
    updated_at = models.DateTimeField('Güncellenme Tarihi', auto_now=True)
    
    class Meta:
        verbose_name = 'Makale Yorumu'
        verbose_name_plural = 'Makale Yorumları'
        ordering = ['-created_at']
    
    def __str__(self):
        return f'{self.author.username} - {self.article.title[:50]}'