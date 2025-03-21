import json
import logging
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from .services.whatsapp_service import WhatsAppService
from .services.conversation_service import ConversationService
from .services.company_service import CompanyService
from .services.session_service import SessionService
from .models import Message, Session, PolicyVersion
from .services.message_service import MessageService
from .services.feedback_service import FeedbackService
from .services.policy_service import PolicyService
from .services.whisper_service import WhisperService

# Inicializa los servicios
company_service = CompanyService()
conversation_service = ConversationService()
session_service = SessionService()
message_service = MessageService()
feedback_service = FeedbackService()
policy_service = PolicyService()
whisper_service = WhisperService()

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
            # Crear una variable para rastrear si estamos en el flujo de feedback
            is_feedback_flow = False

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
            
            # Verificar si el usuario ya aceptó las políticas
            # Primero, obtén la política activa
            policy = PolicyVersion.objects.filter(active=True).first()

            # Verificar si necesita aceptar o actualizar políticas
            needs_acceptance = not user.policies_accepted
            needs_update = False

            if user.policies_accepted and policy:
                # Ya tiene políticas aceptadas, pero verificar si hay una nueva versión
                try:
                    if user.policies_version != policy.version:
                        # Comparar versiones semánticas
                        user_version = [int(x) for x in user.policies_version.split(".")]
                        policy_version = [int(x) for x in policy.version.split(".")]
                        
                        # Si el número principal de versión ha cambiado (1.x → 2.x)
                        if policy_version[0] > user_version[0]:
                            needs_update = True
                            logger.info(f"Usuario {user.whatsapp_number} necesita actualizar política: {user.policies_version} → {policy.version}")
                except (ValueError, IndexError, AttributeError) as e:
                    logger.warning(f"Error comparando versiones: {e}")
                    # En caso de error, ser conservadores y pedir actualización
                    needs_update = True

            # Procesar si necesita aceptar inicialmente o actualizar
            if needs_acceptance or needs_update:
                if user.waiting_policy_acceptance and metadata.get("type") == "interactive" and "button_id" in metadata:
                    button_id = metadata.get("button_id")
                    
                    # Obtener la política activa
                    active_policy = policy_service.get_active_policy()
                    
                    if button_id == "accept_policies":
                        # El usuario aceptó las políticas
                        policy_service.record_policy_acceptance(
                            user, 
                            active_policy or "1.0",  # Usar versión activa o "1.0" como fallback
                            ip_address=request.META.get('REMOTE_ADDR', None)
                        )
                        
                        # Si hay un mensaje pendiente, procesarlo ahora
                        pending_message = user.pending_message_text
                        if pending_message:
                            # Resetear el mensaje pendiente
                            user.pending_message_text = None
                            user.save()
                            
                            # Procesar el mensaje como si fuera nuevo
                            message_text = pending_message
                            
                            # Enviar mensaje de confirmación
                            whatsapp.send_message(from_phone, 
                                "¡Gracias por aceptar nuestras políticas! Ahora podemos ayudarte.")
                            
                        else:
                            # No hay mensaje pendiente, enviar bienvenida
                            whatsapp.send_message(from_phone, 
                                f"¡Bienvenido/a a {company.name}! ¿En qué podemos ayudarte hoy?")
                            
                            # Terminar procesamiento
                            return HttpResponse('OK', status=200)
                            
                    elif button_id == "reject_policies":
                        # El usuario rechazó las políticas
                        whatsapp.send_message(from_phone, 
                            "Entendemos tu decisión. Para poder utilizar nuestro servicio es necesario aceptar las políticas de privacidad. " +
                            "Si cambias de opinión, puedes escribirnos nuevamente.")
                        
                        # No procesar más mensajes
                        user.waiting_policy_acceptance = False
                        user.save()
                        return HttpResponse('OK', status=200)
                        
                else:
                    # Primer mensaje o mensaje sin respuesta a políticas
                    user.pending_message_text = message_text
                    user.waiting_policy_acceptance = True
                    user.save()
                    
                    # Mensaje apropiado según sea aceptación inicial o actualización
                    if needs_update:
                        header_text = f"Actualización de Políticas v{policy.version}"
                        intro_text = f"Hemos actualizado nuestras políticas. Para continuar usando nuestro servicio, necesitas aceptar la nueva versión."
                    else:
                        header_text = "Políticas de Privacidad"
                        intro_text = policy.description
                    
                    # Obtener la política activa
                    policy = policy_service.get_active_policy()
                    
                    # Registrar lo que estamos utilizando
                    if hasattr(policy, 'id'):
                        logger.info(f"Usando política activa de la DB: ID={policy.id}, título={policy.title}, versión={policy.version}")
                    else:
                        logger.info(f"Usando política predeterminada: {policy.get('title')}, v{policy.get('version')}")
                    
                    # Enviar mensaje interactivo para aceptación de políticas
                    response = whatsapp.send_policy_acceptance_message(from_phone, policy)
                    
                    # Si el usuario responde a este mensaje con "más detalles" o similar, podríamos
                    # implementar el envío de políticas completas, pero por ahora es suficiente
                    
                    # No procesar más este mensaje
                    return HttpResponse('OK', status=200)

            # Registrar la interacción y crear/obtener sesión
            company_service.record_user_company_interaction(user, company)
            session = session_service.get_or_create_session(user, company)
            
            if not session:
                logger.error(f"No se pudo crear/obtener sesión para {user.whatsapp_number}")
                return HttpResponse('OK', status=200)
            
            # Detectar primero el tipo de mensaje para aplicar flujo específico
            message_type = metadata.get("type")

            # Manejar primero los mensajes de audio ya que tienen un flujo especial
            if message_type == "audio":
                # Procesar mensaje de audio
                audio_id = metadata.get("audio_id")
                
                if not audio_id:
                    logger.error("Mensaje de audio recibido sin ID")
                    return HttpResponse('OK', status=200)
                
                # Crear sesión para el usuario
                session = session_service.get_or_create_session(user, company)
                
                # Crear mensaje inicial (se actualizará después con la transcripción)
                message = Message.objects.create(
                    company=company,
                    session=session,
                    user=user,
                    message_text="[Procesando mensaje de audio...]",
                    message_type="audio",
                    is_from_user=True
                )
                
                # Notificar al usuario que estamos procesando
                whatsapp.send_message(
                    from_phone, 
                    "Estoy procesando tu mensaje de voz, dame un momento..."
                )
                
                # Procesar el audio (descargar y transcribir)
                result = whisper_service.process_whatsapp_audio(message, audio_id, company)
                
                if result["success"]:
                    # Transcripción exitosa
                    transcription = result["transcription"]
                    logger.info(f"Audio transcrito: {transcription[:100]}...")
                    
                    # Procesar el texto transcrito para obtener respuesta
                    # IMPORTANTE: Corregimos los argumentos para coincidir con la firma del método
                    ai_response = conversation_service.generate_response(
                        user_id=from_phone,
                        message=transcription,
                        company_info=company_service.get_company_info(company)
                    )
                    
                    # Crear mensaje de respuesta
                    response_message = Message.objects.create(
                        company=company,
                        session=session,
                        user=user,
                        message_text=ai_response,
                        message_type="text",
                        is_from_user=False
                    )
                    
                    # Enviar respuesta al usuario
                    whatsapp.send_message(from_phone, ai_response)
                    
                else:
                    # Error en la transcripción
                    error_msg = "Lo siento, no pude entender tu mensaje de voz. ¿Podrías intentar de nuevo o enviar un mensaje de texto?"
                    whatsapp.send_message(from_phone, error_msg)
                    logger.error(f"Error procesando audio: {result.get('error', 'Unknown error')}")
                
                return HttpResponse('OK', status=200)

            # PROCESAMIENTO DE MENSAJES INTERACTIVOS (BOTONES)
            if metadata.get("type") == "interactive" and "button_id" in metadata:
                button_id = metadata.get("button_id")
                
                # Manejar botón para ver políticas completas
                if button_id == "view_full_policies":
                    logger.info(f"Usuario {user.whatsapp_number} solicita ver políticas completas")
                    
                    # Obtener la política activa
                    policy = PolicyVersion.objects.filter(active=True).first()
                    if not policy:
                        whatsapp.send_message(from_phone, "Lo sentimos, no se encontraron las políticas detalladas. Por favor, contacta con soporte.")
                        return HttpResponse('OK', status=200)
                        
                    # Enviar políticas detalladas
                    responses = whatsapp.send_full_policy_details(from_phone, policy)
                    logger.info(f"Enviados {len(responses)} mensajes con detalles de políticas al usuario {user.whatsapp_number}")
                    
                    # No procesar más este mensaje
                    return HttpResponse('OK', status=200)
                
                # Procesar botones de feedback
                if button_id in ["positive", "negative", "comment"]:
                    is_feedback_flow = True
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
                        
                    if button_id == "comment":
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
                is_feedback_flow = True
                try:
                    feedback_session = Session.objects.get(id=waiting_session_id)
                    
                    # Guardar el comentario
                    feedback_service.process_feedback_response(feedback_session, user, company, 'neutral', comment=message_text)
                    
                    # Agradecer al usuario sin reiniciar la conversación completa
                    whatsapp.send_message(from_phone, "¡Gracias por compartir tu experiencia! Tu comentario nos ayuda a mejorar nuestro servicio.")
                    
                    # Eliminar la marca de espera
                    cache.delete(cache_key)
                    
                    # NO UTILIZAR EL CONVERSATION SERVICE AQUÍ
                    # De esta forma no se crea una nueva entrada en self.conversations
                    # y no se considera como primer mensaje de una nueva conversación
                    
                    return HttpResponse('OK', status=200)
                    
                except Exception as e:
                    logger.error(f"Error procesando comentario de feedback: {e}")
            
            # PROCESAMIENTO DE MENSAJES REGULARES
            if not is_feedback_flow:
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