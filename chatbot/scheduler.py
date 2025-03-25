import logging
from apscheduler.schedulers.background import BackgroundScheduler
from django_apscheduler.jobstores import DjangoJobStore
from django.utils import timezone
from .services.session_service import SessionService

logger = logging.getLogger(__name__)

def close_inactive_sessions():
    """
    Tarea programada para cerrar sesiones inactivas
    """
    logger.info("Ejecutando tarea programada para cerrar sesiones inactivas")
    service = SessionService()
    count = service.end_inactive_sessions(minutes=5)  # Cerrar después de 5 minutos de inactividad
    logger.info(f"Se cerraron {count} sesiones inactivas")

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
        # Se ejecutará cada 30 minutos
        scheduler.add_job(
            close_inactive_sessions,
            trigger="interval",
            minutes=5, # Cada 5 minutos
            id="close_inactive_sessions",
            replace_existing=True,
            max_instances=1,
            next_run_time=timezone.now()  # Ejecutar inmediatamente por primera vez
        )
        
        # Iniciar el planificador
        scheduler.start()
        logger.info("Planificador de tareas iniciado con éxito")
        
    except Exception as e:
        logger.error(f"Error al iniciar el planificador de tareas: {e}")