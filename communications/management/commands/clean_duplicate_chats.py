from django.core.management.base import BaseCommand
from django.db.models import Count
from django.utils.translation import gettext_lazy as _
from django.contrib.auth import get_user_model
from communications.models import MessageGroup, Message, MessageReadStatus

User = get_user_model()

class Command(BaseCommand):
    help = 'Aynı iki kullanıcı arasındaki tekrarlanan direkt mesaj gruplarını temizler'

    def add_arguments(self, parser):
        parser.add_argument(
            '--merge',
            action='store_true',
            dest='merge',
            default=True,
            help='Var olan mesajları en yeni gruba birleştir',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            dest='dry_run',
            default=False,
            help='Değişiklik yapmadan kontrol et',
        )

    def handle(self, *args, **options):
        merge = options['merge']
        dry_run = options['dry_run']
        
        # Tüm kullanıcıları al
        users = User.objects.all()
        
        cleaned_count = 0
        merged_messages = 0
        
        self.stdout.write("Tekrarlanan direkt mesaj gruplarını kontrol ediliyor...")
        
        # Her kullanıcı çifti için kontrol et
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
                    # Birden fazla direkt mesaj grubu tespit edildi
                    self.stdout.write(
                        self.style.WARNING(
                            f"TESPIT: {user1.get_full_name() or user1.username} ve "
                            f"{user2.get_full_name() or user2.username} arasında "
                            f"{direct_groups.count()} adet direkt mesaj grubu var."
                        )
                    )
                    
                    # En yeni grubu al
                    newest_group = direct_groups.first()
                    
                    # Diğer grupları temizle
                    for group in direct_groups[1:]:
                        # Mesaj sayısını say
                        message_count = Message.objects.filter(group=group).count()
                        
                        self.stdout.write(
                            f"  - Grup ID: {group.id}, Oluşturulma: {group.created_at}, "
                            f"Mesaj sayısı: {message_count}"
                        )
                        
                        if not dry_run:
                            if merge:
                                # Mesajları yeni gruba taşı
                                messages_to_move = Message.objects.filter(group=group)
                                for msg in messages_to_move:
                                    # Mesajı kopyala
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
                                    
                                    merged_messages += 1
                                
                            # Grubu sil
                            group.delete()
                            cleaned_count += 1
                        
                    # Bilgilendirme mesajı ekle (eğer dry run değilse ve birleştirme yapıldıysa)
                    if not dry_run and merge and not Message.objects.filter(
                        group=newest_group,
                        message_type='system',
                        content__contains='Aranızda birden fazla sohbet tespit edildi'
                    ).exists():
                        Message.objects.create(
                            sender=None,  # Sistem mesajı
                            group=newest_group,
                            message_type='system',
                            content="Aranızda birden fazla sohbet tespit edildi. Tüm mesajlarınız artık burada toplanacak."
                        )
        
        if dry_run:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Temizlik simülasyonu tamamlandı. {cleaned_count} adet tekrarlanan direkt mesaj grubu bulundu."
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Temizlik tamamlandı. {cleaned_count} adet tekrarlanan direkt mesaj grubu temizlendi. "
                    f"{merged_messages} adet mesaj taşındı."
                )
            ) 