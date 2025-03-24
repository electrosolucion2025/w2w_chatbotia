import logging
from .openai_service import OpenAIService

logger = logging.getLogger(__name__)

class ConversationService:
    """Service for managing conversations with users"""
    
    def __init__(self, max_context_length=30):
        self.openai_service = OpenAIService()
        self.conversations = {}  # Store conversations in memory for now
        self.max_context_length = max_context_length
    
    def get_conversation(self, user_id):
        """Get or create a conversation for a user"""
        if user_id not in self.conversations:
            self.conversations[user_id] = []
        return self.conversations[user_id]
    
    def add_message(self, user_id, message, is_from_user=True):
        """Add a message to a user's conversation history"""
        conversation = self.get_conversation(user_id)
        
        # Add the new message
        role = "user" if is_from_user else "assistant"
        conversation.append({"role": role, "content": message})
        
        # Trim conversation if it's too long
        if len(conversation) > self.max_context_length:
            # Keep the most recent messages
            conversation = conversation[-self.max_context_length:]
            self.conversations[user_id] = conversation
    
    def generate_response(self, user_id, message, company_info=None, language_code='es', is_first_message=False):
        """
        Genera una respuesta para el mensaje del usuario
        
        Args:
            user_id (str): ID del usuario (número de WhatsApp)
            message (str): Mensaje del usuario
            company_info (dict): Información de la empresa
            language_code (str): Código ISO del idioma para la respuesta
            
        Returns:
            str: Respuesta generada
        """
        try:
            # Determinar si es el primer mensaje
            is_first_message = user_id not in self.conversations or len(self.conversations[user_id]) == 0
            
            # Log language code for debugging
            logger.info(f"Generating response in language: {language_code} for user {user_id}")
            
            # Añadir mensaje a la conversación
            self.add_message(user_id, message, is_from_user=True)
            
            # Obtener contexto de la conversación
            conversation = self.get_conversation(user_id)
            
            # Generar una respuesta
            response = self.openai_service.generate_response(
                message=message,
                context=conversation,
                company_info=company_info,
                is_first_message=is_first_message,
                language_code=language_code,  # Pasar el idioma especificado
            )
            
            # Añadir respuesta a la conversación
            self.add_message(user_id, response, is_from_user=False)
            
            return response
            
        except Exception as e:
            logger.error(f"Error generando respuesta: {e}")
            
            # Mensajes de error en diferentes idiomas
            error_messages = {
                'es': "Lo siento, ha ocurrido un error. Por favor, intenta de nuevo más tarde.",
                'en': "I'm sorry, an error occurred. Please try again later.",
                # Puedes añadir más idiomas aquí si lo deseas
            }
            
            return error_messages.get(language_code, "Lo siento, ha ocurrido un error.")
    
    def clear_conversation(self, user_id):
        """Clear a user's conversation history"""
        self.conversations[user_id] = []