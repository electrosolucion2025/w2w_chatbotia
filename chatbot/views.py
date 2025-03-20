import json
import logging
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.conf import settings

from .services.whatsapp_service import WhatsAppService
from .services.conversation_service import ConversationService

# Create a global conversation service instance
conversation_service = ConversationService()

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
                    return HttpResponse('OK', status=200)
                
                # Get the phone number ID from the metadata
                metadata = value.get("metadata", {})
                phone_number_id = metadata.get("phone_number_id")
                
                if not phone_number_id:
                    logger.warning("No phone_number_id found in webhook")
                    return HttpResponse('OK', status=200)
            
            # Parse regular messages
            phone_number, message_text, message_id = whatsapp.parse_webhook_message(body)
            
            if phone_number and message_text:
                # Format company_info to match what the OpenAI service expects
                company_info = {
                    "name": "AutoMasters Concesionario",
                    "sections": [
                        {
                            "title": "Sobre Nosotros", 
                            "content": "AutoMasters es un concesionario de vehículos nuevos y usados con más de 20 años de experiencia en el mercado español. Somos distribuidores oficiales de las marcas Mercedes-Benz, BMW, Audi y Volkswagen."
                        },
                        {
                            "title": "Vehículos Nuevos", 
                            "content": "Ofrecemos toda la gama de modelos 2025 de nuestras marcas principales. Destacan el Mercedes EQS, BMW i4, Audi e-tron y Volkswagen ID.4. Todos con financiación flexible y garantía oficial del fabricante."
                        },
                        {
                            "title": "Vehículos de Ocasión", 
                            "content": "Disponemos de más de 150 vehículos de ocasión certificados con menos de 5 años y garantía mínima de 1 año. Todos revisados en 100 puntos de control y con historial de mantenimiento verificado."
                        },
                        {
                            "title": "Servicios de Financiación", 
                            "content": "Ofrecemos opciones de financiación a medida: leasing, renting, préstamo clásico y pago flexible. Tipos de interés desde 3,9% TAE y entrada desde 10%. Aprovecha nuestras ofertas especiales de financiación sin intereses en modelos seleccionados."
                        },
                        {
                            "title": "Taller y Mantenimiento", 
                            "content": "Nuestro taller oficial ofrece mantenimiento y reparación con técnicos certificados y piezas originales. Servicio rápido para operaciones básicas sin cita previa. Disponemos de vehículos de cortesía para reparaciones de larga duración."
                        },
                        {
                            "title": "Horarios y Contacto", 
                            "content": "Exposición: Lunes a viernes de 9:00 a 20:00, Sábados de 10:00 a 14:00. Taller: Lunes a viernes de 8:00 a 19:00. Teléfono principal: 912 345 678. Ubicación: Avenida de los Automóviles 123, Madrid."
                        }
                    ]
                }
                
                logger.info(f"Received message from {phone_number}: {message_text}")
                
                # Generate a response using OpenAI
                ai_response = conversation_service.generate_response(
                    user_id=phone_number,
                    message=message_text,
                    company_info=company_info
                )
                
                # Set up WhatsApp service with the correct phone number ID
                service = WhatsAppService()
                service.phone_number_id = phone_number_id
                
                # Send the AI response back to the user
                logger.info(f"Sending AI response to {phone_number}: {ai_response}")
                response = service.send_message(phone_number, ai_response)
                logger.info(f"WhatsApp API Response: {response}")
            
            # Always return a 200 OK response to WhatsApp
            return HttpResponse('OK', status=200)
        
        except Exception as e:
            logger.error(f"Error processing webhook: {str(e)}")
            return HttpResponse('OK', status=200)