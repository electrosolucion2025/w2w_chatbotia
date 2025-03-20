from django.core.management.base import BaseCommand
from chatbot.scheduler import start_scheduler
import time

class Command(BaseCommand):
    help = 'Inicia el planificador de tareas en primer plano'

    def handle(self, *args, **options):
        self.stdout.write('Iniciando el planificador de tareas...')
        start_scheduler()
        
        # Mantener el programa en ejecución para que las tareas se ejecuten
        try:
            self.stdout.write(self.style.SUCCESS('Planificador iniciado. Presiona Ctrl+C para detener.'))
            while True:
                time.sleep(10)  # Espera infinita
        except KeyboardInterrupt:
            self.stdout.write(self.style.WARNING('Deteniendo planificador...'))