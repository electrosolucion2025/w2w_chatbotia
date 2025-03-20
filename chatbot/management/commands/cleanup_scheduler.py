from django.core.management.base import BaseCommand
from django_apscheduler.models import DjangoJobExecution
from django.utils import timezone
from datetime import timedelta

class Command(BaseCommand):
    help = 'Elimina registros antiguos de ejecuciones de tareas programadas'

    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=int,
            default=7,
            help='Eliminar registros más antiguos que este número de días'
        )

    def handle(self, *args, **options):
        days = options['days']
        cutoff_date = timezone.now() - timedelta(days=days)
        
        # Eliminar ejecuciones antiguas
        count = DjangoJobExecution.objects.filter(
            run_time__lt=cutoff_date
        ).delete()[0]
        
        self.stdout.write(
            self.style.SUCCESS(f'Se eliminaron {count} registros antiguos de ejecuciones de tareas')
        )