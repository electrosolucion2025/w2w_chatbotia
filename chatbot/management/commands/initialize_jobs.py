import logging
from django.core.management.base import BaseCommand
from django_apscheduler.models import DjangoJob
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger
from django.utils import timezone
import json

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = "Inicializa los jobs programados en la base de datos"

    def handle(self, *args, **options):
        self.stdout.write("Verificando jobs programados...")
        
        # Verificar y crear job para cerrar sesiones inactivas
        self.create_or_update_job(
            id="close_inactive_sessions",
            name="Cierre de sesiones inactivas",
            trigger=IntervalTrigger(minutes=5),
            func_path="chatbot.scheduler:close_inactive_sessions"
        )
        
        # Verificar y crear job para actualizar resúmenes de OpenAI
        self.create_or_update_job(
            id="update_openai_monthly_summaries",
            name="Actualización de resúmenes mensuales de OpenAI",
            trigger=CronTrigger(hour=3, minute=0),  # 3:00 AM
            func_path="chatbot.scheduler:update_openai_monthly_summaries"
        )
        
        # Verificar y crear job para limpiar registros antiguos
        self.create_or_update_job(
            id="cleanup_old_job_executions",
            name="Limpieza de registros antiguos",
            trigger=CronTrigger(day_of_week="mon", hour=0, minute=0),
            func_path="chatbot.scheduler:cleanup_old_job_executions"
        )
        
        self.stdout.write(self.style.SUCCESS("Jobs programados inicializados correctamente"))

    def create_or_update_job(self, id, name, trigger, func_path):
        """Crea o actualiza un job en la base de datos"""
        try:
            # Verificar si el job ya existe
            job_exists = DjangoJob.objects.filter(id=id).exists()
            
            if not job_exists:
                # Crear un nuevo job
                next_run = trigger.get_next_fire_time(None, timezone.now())
                
                # Serializar el trigger para almacenarlo
                trigger_dict = {}
                if isinstance(trigger, IntervalTrigger):
                    trigger_dict = {
                        "trigger": "interval",
                        "interval": int(trigger.interval_length),
                        "interval_unit": "seconds"
                    }
                elif isinstance(trigger, CronTrigger):
                    trigger_dict = {
                        "trigger": "cron",
                        "hour": trigger.fields[5],
                        "minute": trigger.fields[6]
                    }
                
                # Crear el job en la base de datos
                DjangoJob.objects.create(
                    id=id,
                    next_run_time=next_run,
                    job_state=json.dumps({
                        "id": id,
                        "name": name,
                        "func": func_path,
                        "trigger": trigger_dict,
                        "next_run_time": next_run.timestamp() if next_run else None
                    })
                )
                self.stdout.write(f"Creado job: {id}")
            else:
                self.stdout.write(f"Job {id} ya existe")
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error creando job {id}: {e}"))