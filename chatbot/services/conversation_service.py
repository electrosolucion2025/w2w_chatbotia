import logging

from django.conf import settings
from django.db import IntegrityError
from django.utils import timezone

from chatbot.models import CompanyAdmin, Ticket, TicketCategory, TicketImage, User
from chatbot.services.image_processing_service import ImageProcessingService
from .openai_service import OpenAIService
from chatbot.services.whatsapp_service import WhatsAppService

logger = logging.getLogger(__name__)

class ConversationService:
    """Service for managing conversations with users"""
    
    def __init__(self, max_context_length=30):
        self.openai_service = OpenAIService()
        self.whatsapp_service = WhatsAppService()
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
    
    def generate_response(self, user_id, message, company_info=None, language_code='es', is_first_message=False, company=None, session=None):
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
                company=company,
                session=session
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
        
    def handle_image_message(self, from_phone, media_id, message_text, company, session):
        """
        Maneja mensajes con imágenes y los procesa como posibles tickets
        """
        try:
            # Verificar si esta imagen ya fue procesada
            from django.core.cache import cache
            cache_key = f"processed_media_{media_id}_{from_phone}"
            
            if cache.get(cache_key):
                logger.warning(f"Imagen duplicada detectada: {media_id}. Ignorando.")
                return "Estoy procesando tu imagen, dame un momento..."
            
            # VERIFICACIÓN DE SESIÓN CERRADA
            # ==============================
            # Verificar si la sesión está cerrada antes de continuar
            if session and hasattr(session, 'is_closed') and session.is_closed:
                logger.warning(f"No se procesará la imagen {media_id} para el usuario {from_phone} porque la sesión {session.id} está cerrada")
                return "Lo siento, tu sesión anterior ha finalizado. Inicia una nueva conversación para enviar imágenes."
            
            # Marcar como en proceso (con TTL de 1 hora)
            cache.set(cache_key, True, 60 * 60)
            
            # Obtener usuario
            user = User.objects.get(whatsapp_number=from_phone)
            
            # Inicializar el servicio de WhatsApp
            self.whatsapp_service = WhatsAppService(
                api_token=company.whatsapp_api_token,
                phone_number_id=company.whatsapp_phone_number_id
            )
            
            # NUEVO: Obtener contexto de la conversación reciente
            conversation_context = self._extract_conversation_context(from_phone)
            
            # Descargar la imagen
            relative_path = self.whatsapp_service.download_media(media_id)
            if not relative_path:
                return "Lo siento, no pude procesar tu imagen. Por favor, intenta nuevamente."
            
            # Convertir a ruta absoluta para el análisis
            from django.conf import settings
            import os
            absolute_path = os.path.join(settings.MEDIA_ROOT, relative_path)
            
            # Verificar que el archivo existe
            if not os.path.exists(absolute_path):
                logger.error(f"El archivo descargado no existe: {absolute_path}")
                return "Lo siento, hubo un problema al procesar la imagen. Por favor, intenta nuevamente."
            
            # CAMBIO: Usar el nuevo método de análisis con detección de categoría
            image_service = ImageProcessingService()
            image_result = image_service.analyze_image_with_category_detection(
                absolute_path,
                company_id=company.id,
                message_text=message_text
            )
            
            # Extraer resultados
            image_analysis = image_result['analysis']
            detected_category_id = image_result['detected_category_id']
            category_certainty = image_result['certainty']
            
            # SIMPLIFICADO: Buscar un ticket existente SOLO en la sesión actual
            active_ticket = None
            if session:
                # Buscar un ticket creado en la sesión actual
                active_ticket = Ticket.objects.filter(
                    session=session,
                    user=user,
                    company=company,
                    status__in=['new', 'reviewing', 'in_progress']
                ).order_by('-created_at').first()
            
                # VERIFICACIÓN ADICIONAL: Si tenemos un ticket activo, verificar que su sesión no esté cerrada
                if active_ticket and active_ticket.session and hasattr(active_ticket.session, 'is_closed') and active_ticket.session.is_closed:
                    logger.warning(f"No se añadirá la imagen al ticket {active_ticket.id} porque su sesión {active_ticket.session.id} está cerrada")
                    # Forzar la creación de un nuevo ticket
                    active_ticket = None
            
            # Si encontramos un ticket activo en la sesión actual, añadir la imagen a ese ticket
            if active_ticket:
                # Verificar que la sesión del ticket esté activa (doble verificación)
                if active_ticket.session and hasattr(active_ticket.session, 'is_closed') and active_ticket.session.is_closed:
                    # Evitar añadir a ticket con sesión cerrada
                    logger.warning(f"No se añadirá la imagen al ticket {active_ticket.id} debido a sesión cerrada")
                    # Crear nuevo ticket en lugar de añadir al existente
                    active_ticket = None
                else:
                    # La sesión está activa, añadir imagen al ticket existente
                    # RESTO DEL CÓDIGO EXISTENTE para añadir imagen...
                    ticket_image = TicketImage(
                        ticket=active_ticket,
                        image=relative_path,
                        ai_description=image_analysis,
                        whatsapp_media_id=media_id  # Añadir este campo
                    )
                    
                    # Intentar guardar, manejar error de duplicado
                    try:
                        ticket_image.save()
                    except IntegrityError:
                        logger.warning(f"Esta imagen ya existe para el ticket {active_ticket.id}")
                        return "Esta imagen ya ha sido procesada para el ticket actual."
                    
                    # MEJORADO: Actualizar descripción del ticket con contexto de la conversación
                    if message_text or conversation_context:
                        update_text = []
                        if message_text:
                            update_text.append(f"Caption de imagen: {message_text}")
                        
                        if conversation_context:
                            update_text.append(f"Contexto de la conversación: {conversation_context}")
                        
                        if update_text:
                            active_ticket.description += f"\n\n--- Actualización {timezone.now().strftime('%d/%m/%Y %H:%M')} ---\n"
                            active_ticket.description += "\n".join(update_text)
                            active_ticket.save()
                            
                    # Re-analizar con el prompt específico de la categoría
                    if active_ticket.category:
                        detailed_analysis = image_service.analyze_image(
                            absolute_path,
                            company_id=company.id,
                            category_id=active_ticket.category.id
                        )
                        
                        # Actualizar la descripción de la imagen si es más detallada
                        if len(detailed_analysis) > len(image_analysis):
                            ticket_image.ai_description = detailed_analysis
                            ticket_image.save()
                            
                    # Notificar a administradores
                    self.notify_new_image(active_ticket, ticket_image)
                    
                    # Mensaje con información más clara para el usuario
                    if ticket_image.ticket.images.count() > 1:
                        response_message = (
                            f"¡Gracias! He añadido esta imagen a tu reporte actual '{active_ticket.title}'. "
                            f"Ahora tienes {ticket_image.ticket.images.count()} imágenes en este reporte. "
                            f"Un técnico lo revisará pronto."
                        )
                    else:
                        response_message = f"¡Gracias! He añadido esta imagen a tu reporte '{active_ticket.title}'. Un técnico lo revisará pronto."
                
            else:
                # MEJORADO: Usar contexto de conversación para crear la descripción
                full_description = message_text or ""
                
                if conversation_context:
                    if full_description:
                        full_description += f"\n\nContexto de la conversación:\n{conversation_context}"
                    else:
                        full_description = f"Contexto de la conversación:\n{conversation_context}"
                
                if not full_description:
                    full_description = "Reporte con imagen sin descripción textual"
                
                # Crear un nuevo ticket
                # Usar categoría detectada si tiene buena certeza
                if detected_category_id and category_certainty > 0.7:
                    category = TicketCategory.objects.get(id=detected_category_id)
                else:
                    # Si no, usar el método existente para detectar categoría
                    category = image_service.detect_issue_category(
                        full_description, 
                        image_analysis, 
                        company.id
                    )
                
                # Crear título automático considerando el contexto completo
                title_prompt = f"Genera un título breve (máximo 10 palabras) para un ticket de soporte basado en esta descripción: '{full_description}' y este análisis de imagen: '{image_analysis[:100]}...'"
                title = self.openai_service.generate_response(title_prompt, context=None)
                title = title.replace('"', '').strip()[:200]  # Limpiar y limitar longitud
                
                # Crear el ticket
                ticket = Ticket(
                    title=title,
                    description=full_description,
                    company=company,
                    category=category,
                    session=session,
                    user=user,
                    status='new'
                )
                ticket.save()
                
                # Añadir la imagen
                ticket_image = TicketImage(
                    ticket=ticket,
                    image=relative_path,
                    ai_description=image_analysis
                )
                ticket_image.save()
                
                # Notificar a administradores
                self.notify_new_ticket(ticket)
                
                # Mensaje más informativo para el usuario
                response_message = (
                    f"He creado un nuevo reporte con tu imagen: '{ticket.title}'. "
                    f"Puedes enviar más fotos o detalles sobre este problema en esta misma conversación "
                    f"y lo añadiré a este mismo reporte."
                )
                
            # NUEVO: Después de procesar la imagen, añadir información al historial de conversación
            # Esto es crítico para que OpenAI tenga contexto en las siguientes interacciones
            
            # 1. Registrar que el usuario envió una imagen
            if message_text:
                image_message = f"[El usuario envió una imagen con el texto: '{message_text}']"
            else:
                image_message = "[El usuario envió una imagen sin texto adicional]"
                
            self.add_message(from_phone, image_message, is_from_user=True)
            
            # 2. Registrar el análisis de la imagen como mensaje del asistente
            # Crear un mensaje resumido del análisis
            analysis_summary = f"[He analizado tu imagen. Puedo ver: {image_analysis}...]"
            
            self.add_message(from_phone, analysis_summary, is_from_user=False)
            
            # 3. Añadir la respuesta al historial de conversación
            self.add_message(from_phone, response_message, is_from_user=False)
            
            # Devolver la respuesta como siempre
            return response_message
                
        except Exception as e:
            logger.error(f"Error procesando imagen: {e}")
            import traceback
            logger.error(traceback.format_exc())  # Añadir stack trace completo
            return "Lo siento, hubo un problema al procesar tu imagen. Por favor, contacta directamente con soporte."
    
    def notify_new_ticket(self, ticket):
        """Notifica a los administradores sobre un nuevo ticket"""
        try:
            from chatbot.services.email_service import EmailService
            email_service = EmailService()
            return email_service.send_ticket_notification(ticket)
        except Exception as e:
            logger.error(f"Error al notificar sobre nuevo ticket: {e}")
            return False
            
    def notify_new_image(self, ticket, image):
        """Notifica a los administradores sobre una nueva imagen en un ticket existente"""
        try:
            from chatbot.services.email_service import EmailService
            email_service = EmailService()
            return email_service.send_ticket_image_notification(ticket, image)
        except Exception as e:
            logger.error(f"Error al notificar sobre nueva imagen: {e}")
            return False

    def _extract_conversation_context(self, user_id, max_messages=5):
        """
        Extrae contexto relevante de los mensajes recientes en la conversación
        
        Args:
            user_id: ID del usuario (número de WhatsApp)
            max_messages: Máximo número de mensajes a considerar
            
        Returns:
            str: Texto con el contexto relevante
        """
        try:
            # Obtener conversación del usuario
            conversation = self.get_conversation(user_id)
            if not conversation:
                return ""
            
            # Tomar solo los últimos N mensajes (excluyendo la última imagen)
            recent_messages = conversation[-max_messages-1:-1] if len(conversation) > max_messages else conversation[:-1]
            
            # Si no hay suficientes mensajes, no hay contexto relevante
            if not recent_messages:
                return ""
                
            # Extraer texto del usuario (ignorar respuestas del bot)
            user_messages = [msg["content"] for msg in recent_messages if msg["role"] == "user"]
            
            # Si no hay mensajes del usuario, no hay contexto relevante
            if not user_messages:
                return ""
                
            # Unir mensajes del usuario en un solo texto
            raw_context = "\n".join(user_messages)
            
            # Opcional: Usar IA para resumir/extraer lo relevante sobre un problema técnico
            if len(raw_context) > 200:  # Solo si es un texto largo
                # Llamada directa a OpenAI sin usar generate_response
                try:
                    # Crear prompt para extraer información relevante
                    summarize_prompt = f"""
                    Extrae información relevante de esta conversación para un ticket de soporte técnico.
                    Ignora saludos y conversación trivial, enfócate solo en la descripción del problema.
                    Si no hay información sobre un problema técnico, responde con "No hay información relevante".
                    
                    Conversación:
                    {raw_context}
                    """
                    
                    # Usar el cliente de OpenAI para resumir el contexto
                    from openai import OpenAI
            
                    # Crear una nueva instancia
                    client = OpenAI(api_key=self.openai_service.api_key)
                    
                    # Llamada directa a la API
                    response = client.chat.completions.create(
                        model="gpt-4o-mini",  # Modelo más económico para resúmenes
                        messages=[{"role": "user", "content": summarize_prompt}],
                        temperature=0.0,  # Sin creatividad, solo análisis objetivo
                        max_tokens=250    # Respuesta corta y concisa
                    )
                    
                    # Extraer resumen
                    summary = response.choices[0].message.content.strip()
                    
                    if "No hay información relevante" not in summary:
                        return summary
                    else:
                        return ""
                        
                except Exception as extract_error:
                    logger.error(f"Error al resumir contexto con IA: {extract_error}")
                    # Si falla el resumen, devolver contexto completo
                    return raw_context
            else:
                # Para textos cortos, usar directamente
                return raw_context
                
        except Exception as e:
            logger.error(f"Error extrayendo contexto de conversación: {e}")
            return ""