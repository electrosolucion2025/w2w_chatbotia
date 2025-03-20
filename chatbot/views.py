import json
import logging
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from .services.whatsapp_service import WhatsAppService
from .services.conversation_service import ConversationService
from .services.company_service import CompanyService
from .services.session_service import SessionService
from .models import Message, Session
from .services.message_service import MessageService
from .services.feedback_service import FeedbackService

# Inicializa los servicios
company_service = CompanyService()
conversation_service = ConversationService()
session_service = SessionService()
message_service = MessageService()
feedback_service = FeedbackService()

logger = logging.getLogger(__name__)

@csrf_exempt
@require_http_methods(["GET", "POST"])
def webhook(request):
    if request.method == "GET":
        # Verificación del webhook
        mode = request.GET.get("hub.mode")
        token = request.GET.get("hub.verify_token")
        challenge = request.GET.get("hub.challenge")
        
        logger.info(f"Webhook GET request received with mode: {mode}, token: {token}")
        
        # Crear servicio de WhatsApp para verificación
        default_whatsapp = WhatsAppService()
        if default_whatsapp.verify_webhook(mode, token, challenge):
            return HttpResponse(challenge)
        else:
            return HttpResponse("Verification failed", status=403)
        
    elif request.method == "POST":
        try:
            # Obtener el cuerpo del webhook
            body = json.loads(request.body)
            
            # Inicializar servicio de WhatsApp por defecto
            default_whatsapp = WhatsAppService()
            
            # Parsear el mensaje entrante
            from_phone, message_text, message_id, metadata = default_whatsapp.parse_webhook_message(body)
            
            # Verificar si es una actualización de estado o si no se pudo extraer información
            if not from_phone or not message_text:
                return HttpResponse('OK', status=200)
            
            # Extraer el phone_number_id para identificar la empresa
            phone_number_id = metadata.get("phone_number_id")
            
            # Obtener información de contacto del remitente
            contact_name = None
            contacts = metadata.get("contacts", [])
            if contacts and len(contacts) > 0:
                profile = contacts[0].get("profile", {})
                contact_name = profile.get("name")
            
            # Buscar la empresa asociada a este número
            company = company_service.get_company_by_phone_number_id(phone_number_id)
            
            if not company:
                logger.warning(f"No se encontró empresa para phone_number_id: {phone_number_id}")
                return HttpResponse('OK', status=200)
                
            logger.info(f"Found company: {company.name} for phone ID: {phone_number_id}")
            
            # Configurar el servicio WhatsApp con las credenciales de la empresa si están disponibles
            whatsapp = default_whatsapp
            if company.whatsapp_api_token and company.whatsapp_phone_number_id:
                whatsapp = WhatsAppService(
                    api_token=company.whatsapp_api_token,
                    phone_number_id=company.whatsapp_phone_number_id
                )
            
            # Obtener o crear el usuario
            user = company_service.get_or_create_user(
                whatsapp_number=from_phone,
                name=contact_name
            )
            
            if not user:
                logger.error(f"No se pudo obtener/crear usuario para {from_phone}")
                return HttpResponse('OK', status=200)
            
            # Registrar la interacción y crear/obtener sesión
            company_service.record_user_company_interaction(user, company)
            session = session_service.get_or_create_session(user, company)
            
            if not session:
                logger.error(f"No se pudo crear/obtener sesión para {user.whatsapp_number}")
                return HttpResponse('OK', status=200)
            
            # PROCESAMIENTO DE MENSAJES INTERACTIVOS (BOTONES)
            if metadata.get("type") == "interactive" and "button_id" in metadata:
                button_id = metadata.get("button_id")
                
                # Procesar botones de feedback
                if button_id in ["positive", "negative", "comment"]:
                    # Buscar la última sesión finalizada para feedback
                    from django.utils import timezone
                    from datetime import timedelta
                    
                    recent_time = timezone.now() - timedelta(hours=48)
                    recent_session = Session.objects.filter(
                        user=user,
                        company=company,
                        ended_at__isnull=False,
                        ended_at__gt=recent_time,
                        feedback_requested=True
                    ).order_by('-ended_at').first()
                    
                    if not recent_session:
                        # No hay sesión reciente para feedback
                        whatsapp.send_message(from_phone, "No encontramos una sesión reciente para valorar. Gracias por tu interés.")
                        return HttpResponse('OK', status=200)
                    
                    if button_id == "positive":
                        # Feedback positivo
                        feedback_service.process_feedback_response(recent_session, user, company, 'positive')
                        whatsapp.send_message(from_phone, "¡Gracias por tu valoración positiva! Nos alegra saber que fue una buena experiencia.")
                        
                    elif button_id == "negative":
                        # Feedback negativo
                        feedback_service.process_feedback_response(recent_session, user, company, 'negative')
                        whatsapp.send_message(from_phone, "Lamentamos que tu experiencia no fuera satisfactoria. Trabajaremos para mejorar nuestro servicio.")
                        
                    elif button_id == "comment":
                        # Usuario quiere dejar un comentario
                        whatsapp.send_message(from_phone, "Por favor, cuéntanos tu experiencia o sugerencia para mejorar nuestro servicio:")
                        
                        # Marcar que estamos esperando un comentario
                        from django.core.cache import cache
                        cache_key = f"waiting_feedback_comment_{from_phone}"
                        cache.set(cache_key, recent_session.id, 60*30)  # Esperar comentario por 30 minutos
                    
                    return HttpResponse('OK', status=200)
                
            # PROCESAMIENTO DE COMENTARIOS DE FEEDBACK
            from django.core.cache import cache
            cache_key = f"waiting_feedback_comment_{from_phone}"
            waiting_session_id = cache.get(cache_key)
            
            if waiting_session_id and message_text and not message_text.startswith("BUTTON:"):
                try:
                    feedback_session = Session.objects.get(id=waiting_session_id)
                    
                    # Guardar el comentario
                    feedback_service.process_feedback_response(feedback_session, user, company, 'neutral', comment=message_text)
                    
                    # Agradecer al usuario
                    whatsapp.send_message(from_phone, "¡Gracias por compartir tu experiencia! Tu comentario nos ayuda a mejorar nuestro servicio.")
                    
                    # Eliminar la marca de espera
                    cache.delete(cache_key)
                    
                    return HttpResponse('OK', status=200)
                    
                except Exception as e:
                    logger.error(f"Error procesando comentario de feedback: {e}")
            
            # PROCESAMIENTO DE MENSAJES REGULARES
            # Guardar el mensaje entrante
            try:
                incoming_message = Message.objects.create(
                    company=company,
                    session=session,
                    user=user,
                    message_text=message_text,
                    is_from_user=True
                )
                logger.info(f"Mensaje entrante guardado: {incoming_message.id}")
            except Exception as e:
                logger.error(f"Error al guardar mensaje entrante: {e}")
            
            # Obtener información de la empresa para OpenAI
            company_info = company_service.get_company_info(company)
            
            # Registrar el mensaje recibido
            try:
                logger.info(f"Received message from {from_phone} ({contact_name}): {message_text}")
            except UnicodeEncodeError:
                safe_name = contact_name.encode('ascii', 'replace').decode('ascii') if contact_name else None
                safe_message = message_text.encode('ascii', 'replace').decode('ascii') if message_text else None
                logger.info(f"Received message from {from_phone} ({safe_name}): {safe_message}")
            
            # Generar respuesta con OpenAI
            ai_response = conversation_service.generate_response(
                user_id=from_phone,
                message=message_text,
                company_info=company_info
            )
            
            # Enviar respuesta al usuario
            try:
                logger.info(f"Sending AI response to {from_phone}: {ai_response}")
            except UnicodeEncodeError:
                safe_response = ai_response.encode('ascii', 'replace').decode('ascii')
                logger.info(f"Sending AI response to {from_phone}: {safe_response}")
                
            response = whatsapp.send_message(from_phone, ai_response)
            logger.info(f"WhatsApp API Response: {response}")
            
            # Guardar la respuesta de la IA
            try:
                outgoing_message = Message.objects.create(
                    company=company,
                    session=session,
                    user=user,
                    message_text=ai_response,
                    is_from_user=False
                )
                logger.info(f"Mensaje saliente guardado: {outgoing_message.id}")
            except Exception as e:
                logger.error(f"Error al guardar mensaje saliente: {e}")
            
            # Verificar cierre de sesión por respuesta de IA
            ai_farewell_phrases = ['chat finalizado', 'conversación finalizada', 'sesión finalizada', 
                                 'ha sido un placer atenderte', 'gracias por contactarnos']

            if any(phrase in ai_response.lower() for phrase in ai_farewell_phrases):
                # La IA indicó que la conversación ha terminado
                session_service.end_session_for_user(user, company)
                logger.info(f"Sesión finalizada por respuesta de cierre de la IA: {from_phone}")
                
                # Enviar solicitud de feedback con delay
                from threading import Timer
                Timer(3.0, send_delayed_feedback_request, args=[from_phone, session.id]).start()
                
            # Verificar cierre de sesión por mensaje del usuario
            elif any(phrase in message_text.lower() for phrase in ['adios', 'adiós', 'chau', 'hasta luego', 
                                                                'bye', 'nos vemos', 'gracias por todo', 
                                                                'hasta pronto', 'me despido', 'finalizar', 
                                                                'terminar']):
                session_service.end_session_for_user(user, company)
                logger.info(f"Sesión finalizada por despedida del usuario: {from_phone}")
            
            return HttpResponse('OK', status=200)
            
        except Exception as e:
            logger.error(f"Error processing webhook: {e}")
            import traceback
            logger.error(traceback.format_exc())
            
        return HttpResponse('OK', status=200)

# Función para enviar feedback con delay
def send_delayed_feedback_request(phone_number, session_id):
    try:
        session = Session.objects.get(id=session_id)
        company = session.company
        
        # Crear servicio de WhatsApp usando credenciales de la empresa
        whatsapp = WhatsAppService(
            api_token=company.whatsapp_api_token,
            phone_number_id=company.whatsapp_phone_number_id
        )
        
        # Enviar solicitud de feedback
        feedback_service.send_feedback_request(whatsapp, phone_number, session)
        
    except Exception as e:
        logger.error(f"Error al enviar feedback con delay: {e}")