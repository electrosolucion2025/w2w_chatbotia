import logging
from django.utils import timezone
from datetime import timedelta
from ..models import Session
from .conversation_analysis_service import ConversationAnalysisService

logger = logging.getLogger(__name__)

class SessionService:
    """Servicio simplificado para gestionar sesiones de usuario"""
    
    def __init__(self):
        self.analysis_service = ConversationAnalysisService()
    
    def get_or_create_session(self, user, company):
        """
        Obtener una sesión activa o crear una nueva
        """
        try:
            # Buscar una sesión activa
            session = Session.objects.filter(
                user=user,
                company=company,
                ended_at__isnull=True
            ).first()
            
            # Crear una nueva sesión si no existe
            if not session:
                session = Session.objects.create(
                    user=user,
                    company=company
                )
                logger.info(f"Nueva sesión creada para {user.whatsapp_number} con {company.name}")
            else:
                logger.info(f"Sesión existente encontrada para {user.whatsapp_number} con {company.name}")
            
            return session
            
        except Exception as e:
            logger.error(f"Error al obtener/crear sesión: {e}")
            return None
    
    def end_session_for_user(self, user, company):
        """
        Finalizar todas las sesiones activas de un usuario con una empresa
        """
        try:
            sessions = Session.objects.filter(
                user=user,
                company=company,
                ended_at__isnull=True
            )
            
            count = 0
            for session in sessions:
                self._process_session_end(session)
                count += 1
            
            if count > 0:
                logger.info(f"Finalizadas {count} sesiones para {user.whatsapp_number} con {company.name}")
            
            return count > 0
            
        except Exception as e:
            logger.error(f"Error al finalizar sesiones: {e}")
            return False
    
    def end_inactive_sessions(self, minutes=60):
        """
        Finalizar sesiones inactivas después de un periodo de tiempo
        """
        try:
            cutoff_time = timezone.now() - timedelta(minutes=minutes)
            
            # Encontrar sesiones activas pero sin actividad reciente
            inactive_sessions = Session.objects.filter(
                ended_at__isnull=True,
                last_activity__lt=cutoff_time
            )
            
            count = 0
            for session in inactive_sessions:
                self._process_session_end(session)
                count += 1
            
            if count > 0:
                logger.info(f"Finalizadas y analizadas {count} sesiones inactivas (> {minutes} minutos)")
            
            return count
            
        except Exception as e:
            logger.error(f"Error al finalizar sesiones inactivas: {e}")
            return 0
    
    def _process_session_end(self, session):
        """
        Finaliza una sesión y ejecuta análisis de conversación
        """
        # Finalizar la sesión
        session.end_session()
        
        # Ejecutar análisis de la conversación
        try:
            # Analizar la sesión
            analysis = self.analysis_service.analyze_session(session)
            
            # Si hay análisis, guardarlo en la sesión
            if analysis:
                session.analysis_results = analysis
                session.save()
                logger.info(f"Análisis completado y guardado para sesión {session.id}")
                
        except Exception as e:
            logger.error(f"Error en análisis de sesión {session.id}: {e}")
    
    def end_session(self, session):
        """
        Finaliza una sesión específica y ejecuta análisis
        """
        try:
            self._process_session_end(session)
            return True
        except Exception as e:
            logger.error(f"Error al finalizar sesión {session.id}: {e}")
            return False