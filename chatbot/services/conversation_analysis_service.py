import logging
import json
from openai import OpenAI
from django.conf import settings
# Importamos el nuevo servicio de email
from .email_service import EmailService

logger = logging.getLogger(__name__)

class ConversationAnalysisService:
    """Servicio para analizar conversaciones y extraer insights"""
    
    def __init__(self):
        self.client = OpenAI(api_key=settings.OPENAI_API_KEY)
        self.model = "gpt-4o-mini" if hasattr(settings, 'OPENAI_MODEL_ANALYSIS') else "gpt-4o-mini"
        # Inicializar servicios necesarios
        self.email_service = EmailService()
    
    def analyze_session(self, session):
        """
        Analiza todos los mensajes de una sesión y genera un resumen con insights
        
        Args:
            session: Objeto Session con la conversación completa
            
        Returns:
            dict: Resultados del análisis con insights extraídos
        """
        try:
            # Extraer mensajes de la sesión
            messages = session.messages.all().order_by('id')
            
            if not messages or messages.count() < 3:
                logger.info(f"Sesión {session.id} tiene muy pocos mensajes para analizar")
                return None
                
            # Formatear la conversación para análisis
            conversation_text = self._format_conversation(messages)
            
            # Crear prompt para análisis
            system_prompt = """
            Eres un analista de conversaciones de chatbot especializado en identificar oportunidades de negocio.
            Analiza la siguiente conversación entre un cliente y un asistente virtual para extraer información clave.
            
            INSTRUCCIONES:
            1. Identifica la intención principal del usuario (consulta, queja, interés en productos/servicios).
            2. Si hay interés en productos o servicios específicos, extráelos y detállalos.
            3. Analiza el sentimiento general del usuario (positivo, neutral, negativo).
            4. Evalúa si el usuario mostró interés genuino en realizar una compra o contratar un servicio.
            5. Identifica información de contacto o preferencias que el usuario haya compartido.
            6. Detecta cualquier seguimiento que la empresa debería realizar.
            
            Devuelve tu análisis en formato JSON con los siguientes campos exactos:
            {
                "primary_intent": "string", // intención principal (consulta_informacion, interes_producto, interes_servicio, queja, otro)
                "user_sentiment": "string", // positivo, neutral, negativo
                "purchase_interest_level": "string", // alto, medio, bajo, ninguno
                "specific_interests": ["string"], // lista de productos/servicios de interés
                "contact_info": {"type": "string", "value": "string"}, // información de contacto adicional si fue proporcionada
                "follow_up_needed": boolean, // true si se requiere seguimiento
                "follow_up_reason": "string", // razón para el seguimiento
                "summary": "string" // breve resumen de la conversación (máx 150 palabras)
            }
            """
            
            # Llamar a OpenAI para análisis
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Aquí está la conversación para analizar:\n\n{conversation_text}"}
                ],
                temperature=0.2,
                response_format={"type": "json_object"}
            )
            
            # Extraer y parsear la respuesta
            analysis_text = response.choices[0].message.content.strip()
            analysis = json.loads(analysis_text)
            
            logger.info(f"Análisis completado para sesión {session.id}")
            
            # Si el análisis fue exitoso
            if analysis:
                # Guardamos el análisis en la sesión
                session.analysis_results = analysis
                session.save()
                
                # Si es un lead de alta/media calidad, enviar notificación por email
                interest_level = analysis.get('purchase_interest_level', 'ninguno')
                if interest_level in ['alto', 'medio']:
                    # Enviar notificación por email
                    self.email_service.send_lead_notification(session.company, session)
                
                return analysis
            return None
            
        except Exception as e:
            logger.error(f"Error analizando sesión {session.id}: {str(e)}")
            return None
    
    def _format_conversation(self, messages):
        """Formatea los mensajes de una sesión para análisis"""
        conversation = []
        
        for msg in messages:
            role = "Cliente" if msg.is_from_user else "Asistente"
            conversation.append(f"{role}: {msg.message_text}")
            
        return "\n".join(conversation)