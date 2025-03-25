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
    
    def end_inactive_sessions(self, minutes=5):
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
        if not session.ended_at:
            session.ended_at = timezone.now()
            session.save()
            logger.info(f"Sesión {session.id} finalizada")
            
        try:
            # Obtener las credenciales especificas de la empresa
            company = session.company
            api_token = company.whatsapp_api_token
            phone_number_id = company.whatsapp_phone_number_id
            
            # Verificar que las credenciales existe
            if not api_token or not phone_number_id:
                logger.error(f"Credenciales de WhatsApp no encontradas para la empresa {company.name}")
                return
            
            # Enviar mensaje de despedida al usuario
            from django.conf import settings
            from .whatsapp_service import WhatsAppService
            
            whatsapp_service = WhatsAppService(
                api_token=api_token,
                phone_number_id=phone_number_id,
            )
            
            # Mensaje de despedida
            farewell_message = (
                "Parece que ha pasado un tiempo desde tu último mensaje. "
                "He finalizado esta conversación por inactividad. "
                "Si necesitas más ayuda, no dudes en escribir de nuevo en cualquier momento. "
                "¡Gracias por contactar con nosotros!"
            )
            
            # Enviar mensaje de despedida
            whatsapp_service.send_message(
                to_phone=session.user.whatsapp_number,
                message_text=farewell_message,
            )
            
            # Guardar mensaje en la BD
            from ..models import Message
            Message.objects.create(
                session=session,
                company=session.company,
                user=session.user,
                message_text=farewell_message,
                message_type="text",
                is_from_user=False,
            )
            
            # Actualizar el estado de la sesión
            logger.info(f"Enviado mensaje de despedida automático para sesión {session.id}")
            
            # Enviar feedback
            import time
            time.sleep(2) # Esperar un poco antes de enviar el feedback
            
            try:
                # Importar el servicio de feedback
                from .feedback_service import FeedbackService
                feedback_service = FeedbackService()
                
                # Enviar solicitud de feedback	
                feedback_service.send_feedback_request(
                    whatsapp_service=whatsapp_service,
                    phone_number=session.user.whatsapp_number,
                    session=session
                )
                
                # Actualizar la sesión para indicar que se solicito feedback
                session.feedback_requested = True
                session.feedback_requested_at = timezone.now()
                session.save()
                
                logger.info(f"Solicitud de feedback enviada a {session.user.whatsapp_number} para sesión {session.id}")
                
            except Exception as e:
                logger.error(f"Error al enviar solicitud de feedback: {e}")
            
        except Exception as e:
            logger.error(f"Error al enviar mensaje de despedida para sesión {session.id}: {e}")
        
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