import logging
import sys
from apscheduler.schedulers.background import BackgroundScheduler
from django_apscheduler.jobstores import DjangoJobStore
from django.utils import timezone
from django.conf import settings
from .services.session_service import SessionService
from .services.openai_metrics_service import OpenAIMetricsService
from django_apscheduler.models import DjangoJobExecution
import time
import threading
import random

logger = logging.getLogger(__name__)

# Variable global para el scheduler
scheduler = None

def close_inactive_sessions():
    """
    Tarea programada para cerrar sesiones inactivas
    """
    logger.info("Ejecutando tarea programada para cerrar sesiones inactivas")
    try:
        service = SessionService()
        
        # Añadir un pequeño retraso aleatorio para evitar colisiones en entornos múltiples
        if settings.ENVIRONMENT == 'production':
            time.sleep(random.uniform(0, 2))
            
        count = service.end_inactive_sessions(minutes=5)  # Cerrar después de 5 minutos de inactividad
        logger.info(f"Se cerraron {count} sesiones inactivas")
        
        # Actualizar última ejecución exitosa
        update_last_success("close_inactive_sessions")
    except Exception as e:
        logger.error(f"Error cerrando sesiones inactivas: {e}")
        raise

def update_openai_monthly_summaries():
    """
    Tarea programada para actualizar resúmenes mensuales de OpenAI
    """
    logger.info("Ejecutando tarea programada para actualizar resúmenes mensuales de OpenAI")
    try:
        service = OpenAIMetricsService()
        
        # Actualizar mes actual
        now = timezone.now()
        service.generate_monthly_summary(year=now.year, month=now.month)
        
        # Si estamos en los primeros días del mes, actualizar también el mes anterior
        if now.day <= 5:
            previous_month = now.month - 1
            previous_year = now.year
            
            if previous_month == 0:
                previous_month = 12
                previous_year -= 1
                
            service.generate_monthly_summary(year=previous_year, month=previous_month)
        
        logger.info("Resúmenes mensuales de OpenAI actualizados")
        
        # Actualizar última ejecución exitosa
        update_last_success("update_openai_monthly_summaries")
    except Exception as e:
        logger.error(f"Error actualizando resúmenes de OpenAI: {e}")
        raise

def update_last_success(job_id):
    """Actualiza el tiempo de la última ejecución exitosa"""
    try:
        from django_apscheduler.models import DjangoJobExecution
        
        # Obtener la última ejecución exitosa
        job_execution = DjangoJobExecution.objects.filter(
            job_id=job_id, 
            status=DjangoJobExecution.SUCCESS
        ).order_by('-run_time').first()
        
        if job_execution:
            # En lugar de usar finished, crear una nueva entrada
            # Esto es más seguro ya que algunos backends de APScheduler
            # tienen requisitos específicos de formato
            now = timezone.now()
            DjangoJobExecution.objects.create(
                job=job_execution.job,
                status=DjangoJobExecution.SUCCESS,
                run_time=now,
                finished=now,
                duration=0.0
            )
            logger.info(f"Registrada nueva ejecución exitosa para {job_id}")
    except Exception as e:
        logger.error(f"Error actualizando registro de éxito para {job_id}: {str(e)}")

def cleanup_old_job_executions():
    """
    Elimina registros antiguos de ejecuciones de trabajos
    para mantener la tabla de base de datos limpia
    """
    DjangoJobExecution.objects.delete_old_job_executions(
        timezone.now() - timezone.timedelta(days=7)
    )
    logger.info("Registros antiguos de ejecuciones de trabajos eliminados")

def start_scheduler():
    """
    Configura y arranca el planificador de tareas
    con protección contra inicios múltiples
    """
    global scheduler
    
    if scheduler is not None and scheduler.running:
        logger.warning("El planificador ya está en ejecución. No se iniciará nuevamente.")
        return
    
    try:
        # Crear el planificador
        scheduler = BackgroundScheduler(timezone=settings.TIME_ZONE)
        
        # Configurar el almacenamiento de trabajos en la base de datos
        scheduler.add_jobstore(DjangoJobStore(), "default")
        
        # Añadir la tarea de limpieza de sesiones
        scheduler.add_job(
            close_inactive_sessions,
            trigger="interval",
            minutes=5,  # Cada 5 minutos
            id="close_inactive_sessions",
            replace_existing=True,
            max_instances=1,
            next_run_time=timezone.now() + timezone.timedelta(seconds=30)  # Pequeño retraso inicial
        )
        
        # Añadir la tarea de actualización de resúmenes mensuales de OpenAI
        scheduler.add_job(
            update_openai_monthly_summaries,
            trigger="cron",
            hour=3,  # A las 3 AM
            minute=0,
            id="update_openai_monthly_summaries",
            replace_existing=True,
            max_instances=1
        )
        
        # Añadir tarea de limpieza de registros antiguos
        scheduler.add_job(
            cleanup_old_job_executions,
            trigger="cron",
            day_of_week="mon", hour=0, minute=0,  # Cada lunes a medianoche
            id="cleanup_old_job_executions",
            replace_existing=True,
            max_instances=1
        )
        
        # Iniciar el planificador
        # En producción, añadir un pequeño retraso aleatorio para evitar condiciones de carrera
        if settings.ENVIRONMENT == 'production':
            delay = random.uniform(1, 5)
            logger.info(f"Retrasando inicio del planificador por {delay:.2f} segundos")
            time.sleep(delay)
            
        scheduler.start()
        logger.info("Planificador de tareas iniciado con éxito")
        
    except Exception as e:
        logger.error(f"Error al iniciar el planificador de tareas: {e}")
        if scheduler and scheduler.running:
            try:
                scheduler.shutdown()
            except:
                pass
        scheduler = None
        raise