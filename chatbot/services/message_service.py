import logging
from ..models import Message, User, Company, Session

logger = logging.getLogger(__name__)

class MessageService:
    """Servicio para gestionar mensajes"""
    
    def save_user_message(self, company, session, user, message_text):
        """
        Guarda un mensaje enviado por un usuario
        
        Args:
            company (Company): La empresa
            session (Session): La sesión activa
            user (User): El usuario que envía el mensaje
            message_text (str): El texto del mensaje
            
        Returns:
            Message: El objeto de mensaje creado
        """
        try:
            message = Message.objects.create(
                company=company,
                session=session,
                user=user,
                message_text=message_text,
                is_from_user=True
            )
            logger.info(f"Mensaje de usuario guardado: {message.id}")
            return message
        except Exception as e:
            logger.error(f"Error al guardar mensaje de usuario: {e}")
            return None
    
    def save_bot_message(self, company, session, user, message_text):
        """
        Guarda un mensaje enviado por el bot
        
        Args:
            company (Company): La empresa
            session (Session): La sesión activa
            user (User): El usuario al que se envía el mensaje
            message_text (str): El texto del mensaje
            
        Returns:
            Message: El objeto de mensaje creado
        """
        try:
            message = Message.objects.create(
                company=company,
                session=session,
                user=user,
                message_text=message_text,
                is_from_user=False
            )
            logger.info(f"Mensaje del bot guardado: {message.id}")
            return message
        except Exception as e:
            logger.error(f"Error al guardar mensaje del bot: {e}")
            return None
    
    def get_conversation_history(self, session, limit=10):
        """
        Obtiene el historial de conversación de una sesión
        
        Args:
            session (Session): La sesión
            limit (int): Número máximo de mensajes a recuperar
            
        Returns:
            QuerySet: Los mensajes de la conversación
        """
        return Message.objects.filter(session=session).order_by('-created_at')[:limit]
    
    def get_last_messages_for_user_company(self, user, company, limit=5):
        """
        Obtiene los últimos mensajes entre un usuario y una empresa
        
        Args:
            user (User): El usuario
            company (Company): La empresa
            limit (int): Número máximo de mensajes a recuperar
            
        Returns:
            QuerySet: Los últimos mensajes
        """
        return Message.objects.filter(
            user=user,
            company=company
        ).order_by('-created_at')[:limit]