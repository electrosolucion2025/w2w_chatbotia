from django.apps import AppConfig
import sys

class ChatbotConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'chatbot'

    def ready(self):
        """
        Método que se ejecuta cuando la aplicación está lista.
        Iniciamos el planificador de tareas aquí.
        """
        # Evitar iniciar el planificador en comandos de gestión y en ciertos casos
        if 'runserver' in sys.argv or 'uwsgi' in sys.argv or 'gunicorn' in sys.argv:
            # Solo iniciar en modo servidor web y no en tareas de gestión como migrate
            # También evitar iniciar dos veces en modo de desarrollo
            import os
            if os.environ.get('RUN_MAIN', None) != 'true':
                # Importar e iniciar el planificador
                from .scheduler import start_scheduler
                start_scheduler()