from django.core.management.base import BaseCommand
from chatbot.services.session_service import SessionService

class Command(BaseCommand):
    help = 'Cierra las sesiones inactivas después de un periodo de tiempo'

    def add_arguments(self, parser):
        parser.add_argument(
            '--minutes',
            type=int,
            default=60,
            help='Minutos de inactividad antes de cerrar una sesión'
        )

    def handle(self, *args, **options):
        minutes = options['minutes']
        self.stdout.write(f"Buscando sesiones inactivas (más de {minutes} minutos)...")
        
        service = SessionService()
        count = service.end_inactive_sessions(minutes)
        
        self.stdout.write(self.style.SUCCESS(f"Se cerraron {count} sesiones inactivas"))