import json
import logging

from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from .services.whatsapp_service import WhatsAppService
from .models import Company, User, Message, Session

logger = logging.getLogger(__name__)

@csrf_exempt
@require_http_methods(["GET", "POST"])
def webhook(request):
    """
    WhatsApp Webhook endpoint for receiving and sending messages
    """
    whatsapp = WhatsAppService()
    
    if request.method == "GET":
        # Handle webhook verification
        mode = request.GET.get("hub.mode")
        token = request.GET.get("hub.verify_token")
        challenge = request.GET.get("hub.challenge")
        
        logger.info(f"Webhook GET request received with mode: {mode}, token: {token}")
        
        if whatsapp.verify_webhook(mode, token, challenge):
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
            if entry and entry[0].get("changes", []):
                value = entry[0]["changes"][0].get("value", {})
                
                # Handle status updates
                if "statuses" in value:
                    logger.info("Processing status update")
                    # You can process message status updates here if needed
                    return HttpResponse('OK', status=200)
            
            # Parse regular messages
            phone_number, message_text, message_id = whatsapp.parse_webhook_message(body)
            
            if phone_number and message_text:
                # For now, just echo the message back
                logger.info(f"Received message from {phone_number}: {message_text}")
                response = whatsapp.send_message(phone_number, message_text)
                
                # Here you would typically:
                # 1. Find or create the user
                # 2. Find their company
                # 3. Save the message to the database
                # 4. Process the message with AI
                # But for now, we're just echoing
                
                logger.info(f"WhatsApp API Response: {response}")
                
            # Alaways return a 200 OK response to WhatsApp
            return HttpResponse('OK', status=200)
        
        except Exception as e:
            logger.error(f"Error processing webhook: {str(e)}")
            # Still return 200 to Whatsapp to avoid retries
            return HttpResponse('OK', status=200)