import json
import logging
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.conf import settings

from .services.whatsapp_service import WhatsAppService
from .services.conversation_service import ConversationService
from .services.company_service import CompanyService
from .services.session_service import SessionService

# Inicializa los servicios
company_service = CompanyService()
conversation_service = ConversationService()
session_service = SessionService()

logger = logging.getLogger(__name__)

@csrf_exempt
@require_http_methods(["GET", "POST"])
def webhook(request):
    """
    WhatsApp Webhook endpoint for receiving and sending messages
    """
    # Usar el servicio de WhatsApp predeterminado para verificaciones
    default_whatsapp = WhatsAppService()
    
    if request.method == "GET":
        # Handle webhook verification
        mode = request.GET.get("hub.mode")
        token = request.GET.get("hub.verify_token")
        challenge = request.GET.get("hub.challenge")
        
        logger.info(f"Webhook GET request received with mode: {mode}, token: {token}")
        
        if default_whatsapp.verify_webhook(mode, token, challenge):
            return HttpResponse(challenge)
        else:
            return HttpResponse("Verification failed", status=403)
        
    elif request.method == "POST":
        # Handle incoming messages
        try:
            body = json.loads(request.body)
            logger.debug(f"Webhook POST request body: {body}")
            
            # Check if this is a message or status update
            entry = body.get("entry", [])
            if not entry or not entry[0].get("changes", []):
                return HttpResponse('OK', status=200)
                
            value = entry[0]["changes"][0].get("value", {})
            
            # Handle status updates
            if "statuses" in value:
                logger.info("Processing status update")
                return HttpResponse('OK', status=200)
            
            # Get the phone number ID from the metadata
            metadata = value.get("metadata", {})
            phone_number_id = metadata.get("phone_number_id")
            
            if not phone_number_id:
                logger.warning("No phone_number_id found in webhook")
                return HttpResponse('OK', status=200)
                
            # Find the company associated with this phone number ID
            company = company_service.get_company_by_phone_number_id(phone_number_id)
            
            # Si no se encuentra la compañía, usar la configuración por defecto
            whatsapp = default_whatsapp
            company_info = None
            
            if company:
                logger.info(f"Found company: {company.name} for phone ID: {phone_number_id}")
                
                # Create WhatsApp service with company credentials if available
                if company.whatsapp_api_token and company.whatsapp_phone_number_id:
                    whatsapp = WhatsAppService(
                        api_token=company.whatsapp_api_token,
                        phone_number_id=company.whatsapp_phone_number_id
                    )
                
                # Get company info for OpenAI
                company_info = company_service.get_company_info(company)
            else:
                logger.warning(f"Using default config - no company for phone ID: {phone_number_id}")
            
            # Parse regular messages
            from_phone, message_text, message_id = whatsapp.parse_webhook_message(body)
            
            if from_phone and message_text:
                # Extract contact name if available
                contact_name = None
                contacts = value.get("contacts", [])
                if contacts and len(contacts) > 0:
                    profile = contacts[0].get("profile", {})
                    contact_name = profile.get("name")
                
                # Get or create the user (independent of company)
                user = company_service.get_or_create_user(
                    whatsapp_number=from_phone,
                    name=contact_name
                )
                
                if not user:
                    logger.error(f"No se pudo obtener/crear usuario para {from_phone}")
                    return HttpResponse('OK', status=200)
                
                # If company exists, record the interaction and manage session
                if company:
                    company_service.record_user_company_interaction(user, company)
                    
                    # Create or get session
                    session = session_service.get_or_create_session(user, company)
                    
                    if not session:
                        logger.error(f"No se pudo obtener/crear sesión para {from_phone}")
                
                try:
                    # Log the message safely without encoding issues
                    logger.info(f"Received message from {from_phone} ({contact_name}): {message_text}")
                except UnicodeEncodeError:
                    # Handle encoding issues with non-ASCII characters
                    safe_name = contact_name.encode('ascii', 'replace').decode('ascii') if contact_name else None
                    safe_message = message_text.encode('ascii', 'replace').decode('ascii') if message_text else None
                    logger.info(f"Received message from {from_phone} ({safe_name}): {safe_message}")
                
                # Generate a response using OpenAI
                ai_response = conversation_service.generate_response(
                    user_id=from_phone,
                    message=message_text,
                    company_info=company_info
                )
                
                # Send the AI response back to the user
                try:
                    logger.info(f"Sending AI response to {from_phone}: {ai_response}")
                except UnicodeEncodeError:
                    safe_response = ai_response.encode('ascii', 'replace').decode('ascii')
                    logger.info(f"Sending AI response to {from_phone}: {safe_response}")
                    
                response = whatsapp.send_message(from_phone, ai_response)
                logger.info(f"WhatsApp API Response: {response}")
                
                # Check if this is a farewell message and end session if needed
                farewell_phrases = ['adios', 'adiós', 'chau', 'hasta luego', 'bye', 'nos vemos', 
                                    'gracias por todo', 'hasta pronto', 'me despido']
                
                if any(phrase in message_text.lower() for phrase in farewell_phrases) and company and user:
                    # Look for indications that user is ending conversation in their message
                    session_service.end_session_for_user(user, company)
                    logger.info(f"Sesión finalizada por despedida del usuario: {from_phone}")
            
            # Always return a 200 OK response to WhatsApp
            return HttpResponse('OK', status=200)
        
        except Exception as e:
            logger.error(f"Error processing webhook: {e}")
            return HttpResponse('OK', status=200)