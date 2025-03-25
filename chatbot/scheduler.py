import logging
from apscheduler.schedulers.background import BackgroundScheduler
from django_apscheduler.jobstores import DjangoJobStore
from django.utils import timezone
from .services.session_service import SessionService
from .services.openai_metrics_service import OpenAIMetricsService

logger = logging.getLogger(__name__)

def close_inactive_sessions():
    """
    Tarea programada para cerrar sesiones inactivas
    """
    logger.info("Ejecutando tarea programada para cerrar sesiones inactivas")
    service = SessionService()
    count = service.end_inactive_sessions(minutes=5)  # Cerrar después de 5 minutos de inactividad
    logger.info(f"Se cerraron {count} sesiones inactivas")

def update_openai_monthly_summaries():
    """
    Tarea programada para actualizar resúmenes mensuales de OpenAI
    """
    logger.info("Ejecutando tarea programada para actualizar resúmenes mensuales de OpenAI")
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

def start_scheduler():
    """
    Configura y arranca el planificador de tareas
    """
    try:
        # Crear el planificador
        scheduler = BackgroundScheduler()
        
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
            next_run_time=timezone.now()  # Ejecutar inmediatamente por primera vez
        )
        
        # Añadir la tarea de actualización de resúmenes mensuales de OpenAI
        # Se ejecutará una vez al día a las 3:00 AM
        scheduler.add_job(
            update_openai_monthly_summaries,
            trigger="cron",
            hour=3,  # A las 3 AM
            minute=0,
            id="update_openai_monthly_summaries",
            replace_existing=True,
            max_instances=1
        )
        
        # Iniciar el planificador
        scheduler.start()
        logger.info("Planificador de tareas iniciado con éxito")
        
    except Exception as e:
        logger.error(f"Error al iniciar el planificador de tareas: {e}")