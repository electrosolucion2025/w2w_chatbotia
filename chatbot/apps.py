from django.apps import AppConfig
import sys
import os
import logging

logger = logging.getLogger(__name__)

class ChatbotConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'chatbot'

    def ready(self):
        """
        Método que se ejecuta cuando la aplicación está lista.
        Iniciamos el planificador de tareas aquí con consideración para entornos de producción.
        """
        # Evitar iniciar durante comandos de Django como migrate, collectstatic, etc.
        if 'migrate' in sys.argv or 'collectstatic' in sys.argv:
            return
            
        # Obtener el entorno actual
        from django.conf import settings
        environment = settings.ENVIRONMENT
        
        # Determinar si debemos iniciar el scheduler en esta instancia
        should_start = False
        
        if environment == 'development':
            # En desarrollo, solo iniciar si no es una recarga automática
            if os.environ.get('RUN_MAIN', None) != 'true':
                should_start = True
        else:
            # En producción, usar una variable de entorno para designar la instancia primaria
            # o usar una bandera automática (por ejemplo, la primera instancia)
            is_primary = os.environ.get('PRIMARY_INSTANCE', 'false').lower() == 'true'
            if is_primary:
                should_start = True
                
        if should_start:
            logger.info(f"Iniciando scheduler en entorno {environment}")
            try:
                from .scheduler import start_scheduler
                start_scheduler()
            except Exception as e:
                logger.error(f"Error al iniciar el scheduler: {e}")
        else:
            logger.info(f"No se inicia el scheduler en esta instancia ({environment})")