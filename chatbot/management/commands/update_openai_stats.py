from django.core.management.base import BaseCommand
from django.utils import timezone
from chatbot.services.openai_metrics_service import OpenAIMetricsService

class Command(BaseCommand):
    help = 'Actualiza los resúmenes mensuales de OpenAI'

    def handle(self, *args, **options):
        service = OpenAIMetricsService()
        now = timezone.now()
        
        self.stdout.write(self.style.SUCCESS(f'Actualizando resumen de {now.month}/{now.year}...'))
        
        service.generate_monthly_summary(year=now.year, month=now.month)
        
        self.stdout.write(self.style.SUCCESS('Resumen actualizado correctamente'))
        
        # Si estamos en los primeros días del mes, actualizar también el mes anterior
        if now.day <= 5:
            previous_month = now.month - 1
            previous_year = now.year
            
            if previous_month == 0:
                previous_month = 12
                previous_year -= 1
                
            self.stdout.write(self.style.SUCCESS(f'Actualizando resumen del mes anterior {previous_month}/{previous_year}...'))
            service.generate_monthly_summary(year=previous_year, month=previous_month)
            self.stdout.write(self.style.SUCCESS('Resumen del mes anterior actualizado correctamente'))