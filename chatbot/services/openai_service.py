import logging
import openai
from django.conf import settings

logger = logging.getLogger(__name__)

class OpenAIService:
    """Service for handling interactions with OpenAI's API."""
    
    def __init__(self):
        self.api_key = settings.OPENAI_API_KEY
        self.model = settings.OPENAI_MODEL
        openai.api_key = self.api_key
        
    def generate_response(self, message, context=None, company_info=None, is_first_message=False):
        """
        Generate a response using OpenAI
        
        Args:
            message (str): The user's message
            context (list): Previous conversation messages (optional)
            company_info (dict): Information about the company (optional)
            is_first_message (bool): Whether this is the user's first message
            
        Returns:
            str: The generated response
        """
        try:
            system_prompt = self._create_system_prompt(company_info)
            
            # Add first message indicator if needed
            if is_first_message:
                system_prompt += "\n\nEste es el primer mensaje del usuario. Preséntate, menciona que eres un asistente virtual y enumera brevemente las categorías de información disponibles para ayudarle."
            
            # Start with a system message to set the context
            messages = [
                {
                    "role": "system",
                    "content": system_prompt
                }
            ]
            
            # Add conversation history if provided
            if context:
                for msg in context:
                    messages.append(msg)
            
            # Add the user's message
            messages.append(
                {
                    "role": "user",
                    "content": message
                }
            )
            
            # Call the OpenAI API
            response = openai.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.7,
            )
            
            # Extract the assistant's reply from the response
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            logger.error(f"Error generating response: {e}")
            return "Lo siento, en este momento no puedo procesar tu solicitud. Por favor, intenta de nuevo más tarde."
        
    def _create_system_prompt(self, company_info):
        """
        Create a system prompt based on company information
        
        Args:
            company_info (dict): Information about the company
                
        Returns:
            str: The system prompt
        """
        if not company_info:
            return "Eres un asistente virtual que ayuda a los clientes con sus consultas."
        
        # Start with the company name
        company_name = company_info.get('name', 'la empresa')
        prompt = f"Eres el asistente virtual de {company_name}. "
        
        # Add a general instruction
        prompt += "Tu objetivo es ayudar a los clientes respondiendo sus preguntas de manera amable y profesional. "
        prompt += "Utiliza la siguiente información para responder consultas específicas. "
        
        # Add company information sections
        sections = []
        if 'sections' in company_info and company_info['sections']:
            prompt += "\n\n--- INFORMACIÓN DISPONIBLE ---\n"
            
            for section in company_info['sections']:
                title = section.get('title', '')
                content = section.get('content', '')
                if title and content:
                    prompt += f"\n### {title} ###\n{content}\n"
                    sections.append(title)
        
        # Add specific instructions about mentioning available sections
        prompt += "\n\n--- INSTRUCCIONES ESPECIALES ---\n"
        prompt += "1. En tu primer mensaje a un nuevo usuario, preséntate brevemente y menciona las categorías en formato lista de información disponibles para orientarle.\n"
        prompt += "2. Sé conciso pero completo en tus respuestas.\n"
        prompt += "3. Utiliza un tono amable y profesional.\n"
        prompt += "4. Si desconoces la respuesta a una pregunta específica, indícalo amablemente y ofrece poner al cliente en contacto con un asesor humano.\n"
        prompt += "5. Cuando el usuario indique que quiere terminar la conversación o se despida, despídete cordialmente y agradece por utilizar el servicio.\n"
        prompt += "6. Cuando finalice la sesion di: Chat finalizado.\n"
        # Add the list of available sections for easy reference
        if sections:
            prompt += "\n--- CATEGORÍAS DE INFORMACIÓN DISPONIBLES ---\n"
            prompt += ", ".join(sections)
        
        return prompt