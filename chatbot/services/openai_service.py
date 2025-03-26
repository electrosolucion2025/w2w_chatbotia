import logging
import openai
from django.conf import settings
from django.utils import timezone

from chatbot.models import TicketCategory

logger = logging.getLogger(__name__)

class OpenAIService:
    """Service for handling interactions with OpenAI's API."""
    
    def __init__(self):
        self.api_key = settings.OPENAI_API_KEY
        self.model = settings.OPENAI_MODEL
        openai.api_key = self.api_key
        
    def generate_response(self, message, context=None, company_info=None, is_first_message=False, 
                         language_code='es', company=None, session=None):
        """
        Generate a response using OpenAI
        
        Args:
            message (str): The user's message
            context (list): Previous conversation messages (optional)
            company_info (dict): Information about the company (optional)
            is_first_message (bool): Whether this is the user's first message
            language_code (str): Language code for the response
            company (Company): The company object for tracking usage
            session (Session): The session object for tracking usage
            
        Returns:
            str: The generated response
        """
        try:
            # AÑADIR AQUÍ: Asegurar que company_info tiene el ID de la empresa
            if company and (not company_info or not company_info.get('id')):
                company_info = company_info or {}
                company_info['id'] = company.id  # Añadir directamente el ID de la empresa
                logger.info(f"DEBUG - Añadido ID de empresa {company.id} a company_info")
            
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
            else:
                # If no context, just add the user message
                messages.append({"role": "user", "content": message})
            
            # Call the OpenAI API
            from openai import OpenAI
            client = OpenAI(api_key=self.api_key)
            response = client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.7
            )
            
            # Extract the text response
            result = response.choices[0].message.content
            
            # Registrar uso de la API si hay una empresa asociada
            if company:
                try:
                    logger.info(f"DEBUG - Intentando acceder a response.usage...")
                    
                    # MÉTODOS PARA EXTRAER USO
                    usage_data = None
                    
                    # 1. Intentar la nueva estructura mediante model_dump (APIs más nuevas)
                    try:
                        if hasattr(response, 'model_dump'):
                            response_dict = response.model_dump()
                            if isinstance(response_dict, dict) and 'usage' in response_dict:
                                usage = response_dict['usage']
                                usage_data = {
                                    'prompt_tokens': usage.get('prompt_tokens', 0),
                                    'completion_tokens': usage.get('completion_tokens', 0),
                                    'total_tokens': usage.get('total_tokens', 0)
                                }
                                logger.info(f"DEBUG - Tokens encontrados con model_dump: {usage_data}")
                    except Exception as e:
                        logger.error(f"Error con model_dump: {e}")
                        
                    # 2. Acceso directo a usage como propiedad
                    if not usage_data:
                        try:
                            if hasattr(response, 'usage'):
                                usage = response.usage
                                if hasattr(usage, 'prompt_tokens'):
                                    usage_data = {
                                        'prompt_tokens': usage.prompt_tokens,
                                        'completion_tokens': usage.completion_tokens,
                                        'total_tokens': usage.total_tokens
                                    }
                                    logger.info(f"DEBUG - Tokens encontrados con acceso directo: {usage_data}")
                        except Exception as e:
                            logger.error(f"Error con acceso directo: {e}")
                            
                    # 3. Método de diccionario usando to_dict o __dict__
                    if not usage_data:
                        try:
                            dict_method = getattr(response, 'to_dict', None) or (lambda: response.__dict__)
                            response_dict = dict_method()
                            if 'usage' in response_dict:
                                usage = response_dict['usage']
                                usage_data = {
                                    'prompt_tokens': usage.get('prompt_tokens', 0),
                                    'completion_tokens': usage.get('completion_tokens', 0),
                                    'total_tokens': usage.get('total_tokens', 0)
                                }
                                logger.info(f"DEBUG - Tokens encontrados con to_dict: {usage_data}")
                        except Exception as e:
                            logger.error(f"Error con to_dict: {e}")
                            
                    # 4. Si todo falla, usar estimación
                    if not usage_data:
                        # Hacer una estimación aproximada basada en la longitud de los mensajes y la respuesta
                        total_input_chars = sum(len(str(m.get('content', ''))) for m in messages)
                        total_output_chars = len(result)
                        
                        # Estimación: aproximadamente 4 caracteres por token
                        estimated_input_tokens = total_input_chars // 4
                        estimated_output_tokens = total_output_chars // 4
                        estimated_total_tokens = estimated_input_tokens + estimated_output_tokens
                        
                        usage_data = {
                            'prompt_tokens': estimated_input_tokens,
                            'completion_tokens': estimated_output_tokens,
                            'total_tokens': estimated_total_tokens
                        }
                        logger.info(f"DEBUG - Tokens estimados: {usage_data}")
                    
                    # Crear diccionario con datos de uso
                    response_dict = {
                        'id': response.id,
                        'model': response.model,
                        'usage': usage_data
                    }
                    
                    # Registrar uso con log detallado
                    logger.info(f"Registrando uso de OpenAI para {company.name}: {usage_data['total_tokens']} tokens")
                    
                    # Importar aquí para evitar circular imports
                    from .openai_metrics_service import OpenAIMetricsService
                    metrics_service = OpenAIMetricsService()
                    
                    record = metrics_service.record_api_usage(
                        company=company, 
                        session=session,
                        response_data=response_dict
                    )
                    
                    if record:
                        logger.info(f"✓ Registro de uso guardado: ID={record.id}, Tokens={record.tokens_total}, Costo=${record.cost_total}")
                    
                except Exception as e:
                    logger.error(f"Error registrando uso de OpenAI: {e}")
                    import traceback
                    logger.error(traceback.format_exc())
            
            return result
            
        except Exception as e:
            logger.error(f"Error generando respuesta: {e}")
            return f"Error en el servicio: {str(e)}"
        
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
        
        # PREPARAR TODAS LAS CATEGORÍAS DE INFORMACIÓN Y TICKETS
        all_categories = []
        ticket_categories_data = []
        
        # 1. Recopilar información de CompanyInfo (secciones)
        if 'sections' in company_info and company_info['sections']:
            for section in company_info['sections']:
                title = section.get('title', '')
                content = section.get('content', '')
                if title and content:
                    # Añadir a la lista de todas las categorías
                    emoji = section.get('emoji', '')  # Emoji predeterminado si no hay específico
                    all_categories.append({
                        'type': 'info',
                        'title': f"{emoji} {title}",
                        'content': content
                    })
        
        # 2. Recopilar categorías de tickets
        company_id = company_info.get('id')
        if company_id:
            logger.info(f"DEBUG - Buscando categorías de tickets para company_id: {company_id}")
            try:
                # Obtener categorías de tickets
                from chatbot.models import TicketCategory, Company
                
                # Intentar buscar por ID directamente
                ticket_categories = TicketCategory.objects.filter(company_id=company_id)
                if not ticket_categories.exists() and company_info.get('name'):
                    # Intentar buscar por nombre
                    try:
                        company = Company.objects.get(name=company_info.get('name'))
                        ticket_categories = TicketCategory.objects.filter(company=company)
                    except Exception as e:
                        logger.error(f"Error buscando empresa por nombre: {e}")
                
                # Recopilar datos de categorías de tickets
                for category in ticket_categories:
                    ticket_categories_data.append({
                        'name': category.name,
                        'instructions': category.prompt_instructions,
                        'ask_for_photos': category.ask_for_photos
                    })
                    
                    # Añadir a la lista de todas las categorías
                    all_categories.append({
                        'type': 'ticket',
                        'title': f"🔧 {category.name}",
                        'content': category.prompt_instructions or "Reporta problemas relacionados con esta categoría. Si precisas, puedes recibir fotos en el mismo chat."
                    })
                    
                logger.info(f"DEBUG - Categorías de tickets encontradas: {len(ticket_categories_data)}")
                
            except Exception as e:
                logger.error(f"Error procesando categorías de tickets: {e}")
                import traceback
                logger.error(traceback.format_exc())
        
        # CONSTRUIR EL PROMPT CON TODA LA INFORMACIÓN
        
        # 1. Primero añadir explicación de todas las categorías disponibles
        if all_categories:
            prompt += "\n\n--- CATEGORÍAS DE INFORMACIÓN Y AYUDA ---\n"
            for category in all_categories:
                prompt += f"- {category['title']}\n"
        
        # 2. Luego añadir secciones detalladas
        prompt += "\n\n--- INFORMACIÓN DETALLADA POR CATEGORÍA ---\n"
        
        # 2.1 Información general
        info_categories = [c for c in all_categories if c['type'] == 'info']
        if info_categories:
            prompt += "\n### INFORMACIÓN GENERAL ###\n"
            for category in info_categories:
                prompt += f"\n#### {category['title']} ####\n{category['content']}\n"
        
        # 2.2 Categorías de tickets/problemas
        ticket_categories = [c for c in all_categories if c['type'] == 'ticket']
        if ticket_categories:
            prompt += "\n### REPORTES DE PROBLEMAS Y DESPERFECTOS ###\n"
            prompt += "Puedes ayudar a reportar problemas o desperfectos en las siguientes categorías:\n\n"
            
            for category in ticket_categories:
                prompt += f"#### {category['title']} ####\n{category['content']}\n\n"
            
            # Instrucciones para categorías que requieren fotos 
            photo_categories = [c['name'] for c in ticket_categories_data if c.get('ask_for_photos')]
            if photo_categories:
                categories_str = ", ".join([f"'{cat}'" for cat in photo_categories])
                prompt += f"\nPara reportes de {categories_str}, solicita amablemente al usuario "
                prompt += "que envíe fotos del problema para facilitar su evaluación. Que envie fotos a este mismo chat.\n"
                prompt += "Las fotos son muy útiles para diagnosticar correctamente el problema.\n"
        
        # Añadir instrucciones especiales
        prompt += "\n\n--- INSTRUCCIONES ESPECIALES ---\n"
        prompt += "0. Utiliza emojis para hacer la conversación más amena y amigable.\n"
        prompt += "1. En tu primer mensaje a un nuevo usuario, preséntate brevemente y menciona TODAS las categorías en formato lista (tanto de información como de reportes de problemas) para orientarle.\n"
        prompt += "2. Sé conciso pero completo en tus respuestas.\n"
        prompt += "3. Si la información por la que te preguntan es extensa, haz una lista primero y solicita que te pregunten por lo que quieran.\n"
        prompt += "4. Utiliza un tono amable y profesional.\n"
        prompt += "5. Si desconoces la respuesta a una pregunta específica, indícalo amablemente y ofrece poner al cliente en contacto con un asesor.\n"
        
        # Resto de instrucciones igual...
        
        return prompt