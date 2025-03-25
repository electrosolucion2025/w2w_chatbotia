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
        
    def generate_response(self, message, context=None, company_info=None, is_first_message=False, language_code='es'):
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
            system_prompt = self._create_system_prompt(company_info, language_code)
            
            # Log language code for debugging
            logger.info(f"Generating response in language: {language_code}")
            
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
                temperature=0.5,
            )
            
            # Extract the assistant's reply from the response
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            logger.error(f"Error generating response: {e}")
            return "Lo siento, en este momento no puedo procesar tu solicitud. Por favor, intenta de nuevo más tarde."
        
    def _create_system_prompt(self, company_info, language_code='es'):
        """
        Create a system prompt based on company information
        
        Args:
            company_info (dict): Information about the company
                
        Returns:
            str: The system prompt
        """
        # Instrucción clara de idioma
        prompt = f"INSTRUCCIÓN IMPORTANTE: Traduce tu respuesta al siguiente codigo ISO / lenguage: '{language_code}'. Adapta tu tono y estilo a este idioma.\n"
        prompt += "Si te solicitan un cambio de idioma a mitad de conversación, cambialo y traduce tu respuesta al nuevo idioma solicitado.\n\n"
    
        if not company_info:
            return "Eres un asistente virtual que ayuda a los clientes con sus consultas."
        
        # Start with the company name
        company_name = company_info.get('name', 'la empresa')
        prompt += f"Eres el asistente virtual de {company_name}. "
        
        # Add a general instruction
        prompt += "Tu objetivo es ayudar a los clientes respondiendo sus preguntas de manera amable y profesional. "
        prompt += "Utiliza la siguiente información para responder consultas específicas. "
        prompt += "Traduce tanto los titulos como las secciones de los mismos al idioma indicado en el codigo ISO / lenguage.\n\n"
        
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
        prompt += "3. Si la información por la que te preguntan es extensa, haz una lista primero y solicita que te pregunten por lo que quieran.\n"
        prompt += "4. Utiliza un tono amable y profesional.\n"
        prompt += "5. Si desconoces la respuesta a una pregunta específica, indícalo amablemente y ofrece poner al cliente en contacto con un asesor.\n"
        
        # NUEVO: Mejora de la detección de solicitud de contacto y cierre de sesión
        prompt += "6. Si el cliente solicita contacto con un asesor, agente o persona real, detecta esta intención y sigue estos pasos:\n"
        prompt += "   a) Solicita su nombre para el registro\n" 
        prompt += "   b) Pregunta si tiene alguna preferencia de horario o forma de contacto\n"
        prompt += "   c) Recopila toda la información relevante sobre su consulta específica\n"
        prompt += "   d) Al final, SIEMPRE pregúntale: '¿Hay algo más en lo que pueda ayudarte ahora, o prefieres finalizar la conversación y esperar el contacto del asesor?'\n"
        
        prompt += "7. Posteriormente informale que el agente se pondra en contacto con él y muestrale los datos de contacto por si es urgente.\n"
        prompt += "8. Cuando el usuario indique que quiere terminar la conversación o se despida, despídete cordialmente y agradece por utilizar el servicio.\n"
        
        # NUEVO: Mejora para manejar el cierre de sesión
        prompt += "8. Cuando detectes intenciones de despedida o cierre de la conversación:\n"
        prompt += "   a) Si hay ambigüedad sobre si el usuario ha terminado, pregunta explícitamente: '¿Deseas finalizar nuestra conversación o tienes alguna otra consulta?'\n"
        prompt += "   b) Si el usuario no ha interactuado por un tiempo, pregunta: '¿Sigues ahí? ¿Puedo ayudarte con algo más o prefieres que finalicemos la conversación?'\n"
        
        prompt += "9. Cuando finalice la sesion di: Chat finalizado.\n"
        
        # Add the list of available sections for easy reference
        if sections:
            prompt += "\n--- CATEGORÍAS DE INFORMACIÓN DISPONIBLES ---\n"
            prompt += ", ".join(sections)
        
        return prompt