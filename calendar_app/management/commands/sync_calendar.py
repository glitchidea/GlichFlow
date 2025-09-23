from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from calendar_app.utils import sync_calendar_events

User = get_user_model()


class Command(BaseCommand):
    help = 'Takvim etkinliklerini diğer modellerle senkronize eder'

    def add_arguments(self, parser):
        parser.add_argument(
            '--user',
            type=str,
            help='Belirli bir kullanıcı için senkronizasyon yap (username)',
        )
        parser.add_argument(
            '--all',
            action='store_true',
            help='Tüm kullanıcılar için senkronizasyon yap',
        )

    def handle(self, *args, **options):
        if options['user']:
            try:
                user = User.objects.get(username=options['user'])
                self.stdout.write(f'{user.username} için takvim senkronizasyonu başlatılıyor...')
                sync_calendar_events(user)
                self.stdout.write(
                    self.style.SUCCESS(f'{user.username} için takvim senkronizasyonu tamamlandı.')
                )
            except User.DoesNotExist:
                self.stdout.write(
                    self.style.ERROR(f'Kullanıcı bulunamadı: {options["user"]}')
                )
        elif options['all']:
            users = User.objects.filter(is_active=True)
            self.stdout.write(f'{users.count()} kullanıcı için takvim senkronizasyonu başlatılıyor...')
            
            for user in users:
                try:
                    sync_calendar_events(user)
                    self.stdout.write(f'✓ {user.username}')
                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(f'✗ {user.username}: {str(e)}')
                    )
            
            self.stdout.write(
                self.style.SUCCESS('Tüm kullanıcılar için takvim senkronizasyonu tamamlandı.')
            )
        else:
            self.stdout.write(
                self.style.ERROR('--user veya --all parametresi gerekli')
            )
