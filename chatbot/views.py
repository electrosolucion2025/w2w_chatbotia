import json
import logging
from django.http import HttpResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.core.cache import cache as django_cache  # Renombrado para evitar confusiones

from .services.whatsapp_service import WhatsAppService
from .services.conversation_service import ConversationService
from .services.company_service import CompanyService
from .services.session_service import SessionService
from .models import Message, Session, PolicyVersion
from .services.message_service import MessageService
from .services.feedback_service import FeedbackService
from .services.policy_service import PolicyService
from .services.whisper_service import WhisperService
from .services.language_service import LanguageService

# Inicializa los servicios
company_service = CompanyService()
conversation_service = ConversationService()
session_service = SessionService()
message_service = MessageService()
feedback_service = FeedbackService()
policy_service = PolicyService()
whisper_service = WhisperService()
language_service = LanguageService()

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
            is_feedback_flow = False; # Variable para controlar el flujo de feedback
            
            # Obtener el cuerpo del webhook
            body = json.loads(request.body)
            
            # Inicializar servicio de WhatsApp por defecto
            default_whatsapp = WhatsAppService()
            
            # PASO 1: Deduplicación temprana basada en ID de mensaje
            try:
                # Extraer datos del cuerpo del webhook
                entry = body.get('entry', [{}])[0]
                change = entry.get('changes', [{}])[0]
                value = change.get('value', {})
                
                # Verificar si es una actualización de estado
                if 'statuses' in value:
                    logger.info("Recibida actualización de estado, no un mensaje")
                    return HttpResponse('OK', status=200)
                
                # Verificar si hay mensajes
                messages = value.get('messages', [])
                if not messages:
                    logger.info("Webhook sin mensajes")
                    return HttpResponse('OK', status=200)
                    
                # Verificar ID del primer mensaje
                message_id = messages[0].get('id')
                if message_id:
                    cache_key = f"processed_message_{message_id}"
                    if django_cache.get(cache_key):  # Usar django_cache aquí
                        logger.warning(f"Mensaje duplicado con ID: {message_id}. Ignorando.")
                        return HttpResponse('Duplicado ignorado', status=200)
                    
                    # Marcar como procesado
                    django_cache.set(cache_key, True, 60 * 60 * 24)  # Y aquí también
            except Exception as e:
                # Si hay error en esta parte, seguir con el procesamiento normal
                logger.error(f"Error en deduplicación inicial: {e}")
            
            # PASO 2: Parsear el mensaje con el servicio WhatsApp
            from_phone, message_text, message_id, metadata = default_whatsapp.parse_webhook_message(body)
            
            # Si metadata es None, es probable que sea una actualización de estado u otro tipo de webhook
            if metadata is None:
                return HttpResponse('OK', status=200)
            
            # NUEVO: Primero obtener la empresa y la sesión antes de procesar cualquier tipo de mensaje
            # Extraer el phone_number_id para identificar la empresa
            phone_number_id = metadata.get("phone_number_id")
            
            # Obtener información de contacto del remitente
            contact_name = None
            contacts = metadata.get("contacts", [])
            if contacts and len(contacts) > 0:
                profile = contacts[0].get("profile", {})
                contact_name = profile.get("name")
            
            # IMPORTANTE: Obtener la empresa ANTES de procesar cualquier tipo de mensaje
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
            
            # Obtener o crear la sesión activa
            session = session_service.get_or_create_session(user, company)
            
            # PASO 3: Procesamiento específico según tipo de mensaje
            message_type = metadata.get("type", "unknown")
            
            # Para imágenes, verificar duplicación específica
            if message_type == "image":
                media_id = None
                
                # Extraer media_id según la estructura
                if "image" in metadata:
                    media_id = metadata["image"].get("id")
                    caption = metadata["image"].get("caption", "")
                else:
                    media_obj = metadata.get("media", {})
                    media_id = media_obj.get("id") or metadata.get("media_id")
                    caption = media_obj.get("caption", "") or metadata.get("caption", "")
                
                if media_id:
                    # Verificar duplicación de imagen
                    img_cache_key = f"processed_image_{media_id}_{from_phone}"
                    if django_cache.get(img_cache_key):  # Usar django_cache aquí
                        logger.warning(f"Imagen duplicada: {media_id}. Ignorando.")
                        return HttpResponse('OK', status=200)
                    
                    # Marcar como procesada
                    django_cache.set(img_cache_key, True, 60 * 60 * 24)  # Y aquí también
            
                    # Procesar imagen como potencial ticket
                    response = conversation_service.handle_image_message(
                        from_phone=from_phone,
                        media_id=media_id,
                        message_text=caption,
                        company=company,
                        session=session
                    )
                    
                    # Enviar respuesta
                    whatsapp.send_message(from_phone, response)
                    
                    # Guardar mensaje en BD
                    Message.objects.create(
                        company=company,
                        session=session,
                        user=user,
                        message_text=caption or "[Imagen sin texto]",
                        message_type="image",
                        is_from_user=True
                    )
                    
                    Message.objects.create(
                        company=company,
                        session=session,
                        user=user,
                        message_text=response,
                        message_type="text",
                        is_from_user=False
                    )
                    
                    return HttpResponse('OK', status=200)
            
            # NUEVO: Segunda verificación en caso de que el ID se extraiga aquí
            if message_id and not from_phone:
                # Es probablemente una actualización de estado, verificar duplicado
                cache_key = f"processed_status_{message_id}"
                if django_cache.get(cache_key):  # Usar django_cache aquí
                    logger.info(f"Actualización de estado duplicada: {message_id}")
                    return HttpResponse('OK', status=200)
                django_cache.set(cache_key, True, 60 * 60 * 6)  # Y aquí también
            
            # Verificar primero si es una respuesta de feedback
            if message_text and is_feedback_response(message_text, from_phone):
                handle_feedback_response(from_phone, message_text)
                return HttpResponse('OK', status=200)
            
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

            # Verificar si es una nueva conversación - SIMPLIFICADO
            is_new_conversation = False

            # Si el usuario no tiene mensajes previos o es nuevo, es una nueva conversación
            message_count = Message.objects.filter(user=user).count()
            if message_count == 0:
                logger.info(f"Usuario nuevo detectado: {from_phone}")
                is_new_conversation = True

            # Verificar si requiere selección de idioma (no tiene idioma Y no está esperando uno)
            is_language_selection_needed = False
            if (not hasattr(user, 'language') or not user.language):
                # Solo si no está esperando selección de idioma
                if not hasattr(user, 'waiting_for_language') or not user.waiting_for_language:
                    logger.info(f"Usuario sin idioma configurado y no esperando: {from_phone}")
                    is_language_selection_needed = True
                else:
                    logger.info(f"Usuario esperando selección de idioma: {from_phone}")

            # Si el mensaje es tipo "text" (no botón interactivo) y es nueva conversación
            if is_language_selection_needed and metadata.get("type") == "text":
                logger.info(f"Enviando selector de idioma a {from_phone}")
                
                # Obtener o crear sesión
                session = session_service.get_or_create_session(user, company)
                
                # Enviar mensaje de selección de idioma
                response = whatsapp.send_language_selection_message(from_phone)
                if not response:
                    logger.error(f"Error enviando selector de idioma a {from_phone}")
                
                # Guardar mensaje entrante
                Message.objects.create(
                    company=company,
                    session=session,
                    user=user,
                    message_text=message_text,
                    message_type="text",
                    is_from_user=True
                )
                
                # Guardar mensaje de selección de idioma
                Message.objects.create(
                    company=company,
                    session=session,
                    user=user,
                    message_text="[Mensaje de selección de idioma]",
                    message_type="interactive",
                    is_from_user=False
                )
                
                return HttpResponse('OK', status=200)

            # Obtener o crear la sesión activa
            if 'session' not in locals() or not session:
                session = session_service.get_or_create_session(user, company)

            # PROCESAR BOTONES DE IDIOMA
            if metadata.get("type") == "interactive" and "button_id" in metadata:
                button_id = metadata.get("button_id")
                
                # Si es un botón de selección de idioma
                if button_id.startswith("lang_"):
                    language_code = button_id.replace("lang_", "")
                    logger.info(f"Usuario {from_phone} seleccionó detección automática de idioma")
                    
                    if language_code == "detect":
                        logger.info(f"Usuario {from_phone} seleccionó detección automática de idioma")
                        user.waiting_for_language = True
                        user.save()  # Guardar explícitamente
                        
                        # Verificar que se guardó correctamente
                        user.refresh_from_db()
                        logger.info(f"Estado de waiting_for_language después de guardar: {user.waiting_for_language}")
                        
                        # Pedir que escriba en su idioma pero de forma más natural
                        request_message = "Por favor, escribe tu pregunta o mensaje en tu idioma preferido y te responderé automáticamente en ese mismo idioma.\n\nPlease write your question or message in your preferred language and I'll respond automatically in that same language."
                        whatsapp.send_message(from_phone, request_message)
                        
                        # Guardar interacción en BD
                        Message.objects.create(
                            company=company,
                            session=session,
                            user=user,
                            message_text="[Seleccionó: Auto-detect]",
                            message_type="interactive",
                            is_from_user=True
                        )
                        
                        Message.objects.create(
                            company=company,
                            session=session,
                            user=user,
                            message_text=request_message,
                            message_type="text",
                            is_from_user=False
                        )       
                        
                        return HttpResponse('OK', status=200)         
                    else:
                        # Usuario seleccionó un idioma específico (es, en, etc.)
                        user.language = language_code
                        user.waiting_for_language = False
                        user.save()
                        
                        logger.info(f"Idioma {language_code} establecido para usuario {from_phone}")
                        
                        # Guardar selección en la BD
                        Message.objects.create(
                            company=company,
                            session=session, 
                            user=user,
                            message_text=f"[Seleccionó idioma: {language_code}]",
                            message_type="interactive",
                            is_from_user=True
                        )
                        
                        # Enviar mensaje de bienvenida directamente
                        company_info = company_service.get_company_info(company)
                        
                        # Generar mensaje de bienvenida del bot
                        welcome_response = conversation_service.generate_response(
                            user_id=from_phone,
                            message="Hola", 
                            company_info=company_info,
                            language_code=language_code,
                            is_first_message=True,
                            company=company,
                            session=session
                        )
                        
                        # Enviar mensaje de bienvenida
                        whatsapp.send_message(from_phone, welcome_response)
                        
                        # Guardar mensaje en BD
                        Message.objects.create(
                            company=company,
                            session=session,
                            user=user,
                            message_text=welcome_response,
                            message_type="text",
                            is_from_user=False
                        )
                        
                        return HttpResponse('OK', status=200)

            # PROCESAR RESPUESTA DE DETECCIÓN DE IDIOMA
            if hasattr(user, 'waiting_for_language') and user.waiting_for_language and metadata.get("type") == "text":
                # Detectar idioma del texto enviado
                detected_language = language_service.detect_language_with_openai(message_text)
                
                # Actualizar idioma del usuario
                user.language = detected_language["code"]
                user.waiting_for_language = False
                user.save()
                
                logger.info(f"Idioma detectado para {from_phone}: {detected_language['name']} ({detected_language['code']})")
                
                # NO enviar confirmación de idioma detectado
                # En su lugar, procesar directamente este mensaje como pregunta
                
                # Crear sesión si no existe
                session = session_service.get_or_create_session(user, company)
                
                # Guardar mensaje entrante del usuario
                Message.objects.create(
                    company=company,
                    session=session,
                    user=user,
                    message_text=message_text,
                    message_type="text",
                    is_from_user=True
                )
                
                # Obtener información de la empresa
                company_info = company_service.get_company_info(company)
                
                # Generar respuesta de la IA usando el idioma detectado
                ai_response = conversation_service.generate_response(
                    user_id=from_phone,
                    message=message_text,
                    company_info=company_info,
                    language_code=user.language,
                    company=company,
                    session=session
                )
                
                # Enviar respuesta
                whatsapp.send_message(from_phone, ai_response)
                
                # Guardar respuesta en BD
                Message.objects.create(
                    company=company,
                    session=session,
                    user=user,
                    message_text=ai_response,
                    message_type="text",
                    is_from_user=False
                )
                
                return HttpResponse('OK', status=200)

            # MOSTRAR SELECCIÓN DE IDIOMA PARA CONVERSACIONES NUEVAS
            if is_new_conversation:
                # Enviar mensaje de selección de idioma
                whatsapp.send_language_selection_message(from_phone)
                
                # Guardar mensaje entrante inicial
                Message.objects.create(
                    company=company,
                    session=session,
                    user=user,
                    message_text=message_text,
                    message_type=metadata.get("type", "text"),
                    is_from_user=True
                )
                
                # Guardar mensaje de selección de idioma
                Message.objects.create(
                    company=company,
                    session=session,
                    user=user,
                    message_text="[Mensaje de selección de idioma]",
                    message_type="interactive",
                    is_from_user=False
                )
                
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
                        company_info=company_service.get_company_info(company),
                        language_code=user.language,
                        company=company,
                        session=session,
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
                        django_cache.set(cache_key, recent_session.id, 60*30)  # Esperar comentario por 30 minutos
                    
                    return HttpResponse('OK', status=200)
                
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
                    company_info=company_info,
                    language_code=user.language,
                    company=company,
                    session=session
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
                    
                    if not session.feedback_requested:
                        # Enviar solicitud de feedback con delay
                        from threading import Timer
                        Timer(2.0, send_delayed_feedback_request, args=[from_phone, session.id]).start()
                    
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
        
        if session.feedback_requested:
            logger.info(f"Feedback ya solicitado para sesión {session.id}, no se enviará nuevamente.")
            return
        
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
        
def is_feedback_response(message, phone_number=None):
    """
    Determina si un mensaje es una respuesta a una solicitud de feedback
    """
    # Verificar si estamos esperando un comentario para este número
    if phone_number:
        from django.core.cache import cache
        cache_key = f"waiting_feedback_comment_{phone_number}"
        waiting_session_id = django_cache.get(cache_key)  # Usar django_cache aquí
        
        if waiting_session_id:
            # Estamos esperando un comentario, tratar cualquier mensaje como feedback
            return True
    
    # Posibles respuestas a botones de feedback
    feedback_responses = [
        "👍 Buena", "👍 Bueno",
        "👎 Mejorable",
        "💬 Comentar",
        # Si el usuario escribe el emoji directamente
        "👍", "👎", "💬"
    ]
    
    # También verificar IDs de botones que podrían enviarse
    button_ids = ["positive", "negative", "comment"]
    
    # Si el mensaje exacto coincide con alguna de las respuestas de feedback
    if message in feedback_responses:
        return True
    
    # Si el mensaje contiene algún ID de botón
    if any(button_id in message for button_id in button_ids):
        return True
    
    return False

def handle_feedback_response(phone_number, feedback_message):
    """
    Procesa una respuesta de feedback sin crear una nueva sesión
    """
    try:
        from .models import User, Session, Feedback
        from django.utils import timezone
        from django.core.cache import cache
        
        # Buscar usuario por número de teléfono
        user = User.objects.filter(whatsapp_number=phone_number).first()
        if not user:
            logger.error(f"No se encontró usuario para el número {phone_number} al procesar feedback")
            return
            
        # Verificar si estamos esperando un comentario
        cache_key = f"waiting_feedback_comment_{phone_number}"
        waiting_session_id = django_cache.get(cache_key)  # Usar django_cache aquí
        
        # Obtener la sesión relevante
        session = None
        if waiting_session_id:
            # Estamos esperando un comentario para una sesión específica
            session = Session.objects.filter(id=waiting_session_id).first()
            
            if session:
                # Estamos procesando un comentario
                feedback_type = "comment"
                comment_text = feedback_message
                response_message = "¡Gracias por tu comentario! Lo tendremos en cuenta para seguir mejorando."
                
                # Limpiar el estado de espera
                django_cache.delete(cache_key)  # Usar django_cache aquí
                
                # Guardar en el modelo Feedback directamente
                from .services.feedback_service import FeedbackService
                feedback_service = FeedbackService()
                feedback_service.process_feedback_response(
                    session, user, session.company, 
                    feedback_type, comment=comment_text
                )
                
                # También guardar en la sesión
                session.feedback_response = feedback_type
                session.feedback_comment = comment_text
                session.feedback_received_at = timezone.now()
                session.save(update_fields=['feedback_response', 'feedback_comment', 'feedback_received_at'])
                
                # Enviar agradecimiento
                from .services.whatsapp_service import WhatsAppService
                whatsapp_service = WhatsAppService(
                    api_token=session.company.whatsapp_api_token,
                    phone_number_id=session.company.whatsapp_phone_number_id
                )
                whatsapp_service.send_message(phone_number, response_message)
                
                logger.info(f"Comentario de feedback procesado para sesión {session.id}")
                return
        
        # Si no estamos procesando un comentario, buscar la última sesión cerrada
        if not session:
            session = Session.objects.filter(
                user=user,
                ended_at__isnull=False,
                feedback_requested=True
            ).order_by('-ended_at').first()
        
        if not session:
            logger.error(f"No se encontró sesión cerrada reciente para usuario {user.id} al procesar feedback")
            return
        
        # Obtener empresa
        company = session.company
        
        # Determinar tipo de feedback
        if "👍" in feedback_message or "positive" in feedback_message or "Buena" in feedback_message or "Bueno" in feedback_message:
            feedback_type = "positive"
            response_message = "¡Gracias por tu valoración positiva! Nos alegra haber podido ayudarte."
        elif "👎" in feedback_message or "negative" in feedback_message or "Mejorable" in feedback_message:
            feedback_type = "negative"
            response_message = "Gracias por tu sinceridad. Trabajaremos en mejorar nuestra atención."
        elif "💬" in feedback_message or "comment" in feedback_message or "Comentar" in feedback_message:
            feedback_type = "comment_requested"
            response_message = "Agradecemos que quieras dejarnos un comentario. Por favor, escribe tu opinión o sugerencia."
            
            # Marcar que estamos esperando un comentario
            session.feedback_comment_requested = True
            session.save(update_fields=['feedback_comment_requested'])
            
            # Guardar el ID de la sesión en caché
            django_cache.set(cache_key, session.id, 60*30)  # Usar django_cache aquí
        else:
            feedback_type = "neutral"
            response_message = "Gracias por tu respuesta. Hemos registrado tu feedback."
        
        # Guardar en Session
        session.feedback_response = feedback_type
        session.feedback_received_at = timezone.now()
        session.save()
        
        # Guardar en Feedback si no es solicitud de comentario
        if feedback_type != "comment_requested":
            from .services.feedback_service import FeedbackService
            feedback_service = FeedbackService()
            feedback_service.process_feedback_response(session, user, company, feedback_type)
        
        # Enviar respuesta al usuario
        from .services.whatsapp_service import WhatsAppService
        whatsapp_service = WhatsAppService(
            api_token=company.whatsapp_api_token,
            phone_number_id=company.whatsapp_phone_number_id
        )
        whatsapp_service.send_message(phone_number, response_message)
        
        logger.info(f"Procesado feedback '{feedback_type}' para sesión {session.id}")
        
    except Exception as e:
        logger.error(f"Error procesando feedback: {e}", exc_info=True)