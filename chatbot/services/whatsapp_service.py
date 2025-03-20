import requests
import json
import logging
from django.conf import settings

logger = logging.getLogger(__name__)

class WhatsAppService:
    """Service for handling WhatsApp messages."""
    
    BASE_URL = "https://graph.facebook.com/v22.0"
    
    def __init__(self, api_token=None, phone_number_id=None):
        # Si se proporcionan credenciales de WhatsApp en settings, se utilizan
        # de lo contrario, se utilizan las credenciales de la empresa
        self.api_token = api_token or settings.WHATSAPP_API_TOKEN
        self.phone_number_id = phone_number_id or settings.WHATSAPP_PHONE_NUMBER_ID
        
    def _get_headers(self):
        """Get headers for the API request."""
        return {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json"
        }
    
    def send_message(self, to_phone, message_text):
        """
        Send a text message to a WhatsApp number
        
        Args:
            to_phone (str): Recipient's phone number
            message_text (str): The message to send
        
        Returns:
            dict: The API response or None if error
        """
        endpoint = f"{self.BASE_URL}/{self.phone_number_id}/messages"
        
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to_phone,
            "type": "text",
            "text": {
                "body": message_text
            }
        }
        
        try:
            response = requests.post(
                endpoint,
                headers=self._get_headers(),
                data=json.dumps(payload)
            )
            
            # Verificar si la respuesta fue exitosa
            if response.status_code == 200:
                return response.json()
            
            # Manejar errores comunes
            error_data = response.json()
            logger.error(f"Error sending message to {to_phone}: {response.status_code} {response.reason}")
            logger.error(f"Error response: {error_data}")
            
            # Verificar si es un error de token expirado
            if response.status_code == 401:
                error_obj = error_data.get("error", {})
                if error_obj.get("code") == 190 and error_obj.get("error_subcode") == 463:
                    logger.critical("WhatsApp TOKEN EXPIRED! Please generate a new token in Meta Developer Portal")
                
            return None
            
        except Exception as e:
            logger.error(f"Exception sending message: {str(e)}")
            return None
        
    def send_interactive_message(self, phone_number, body_text, buttons, header_text=None):
        """
        Envía un mensaje interactivo con botones
        
        Args:
            phone_number (str): Número de teléfono del destinatario
            body_text (str): Texto principal del mensaje
            buttons (list): Lista de diccionarios con id y title para cada botón
            header_text (str, optional): Texto del encabezado
            
        Returns:
            dict: Respuesta de la API de WhatsApp
        """
        logger = logging.getLogger(__name__)
        
        # Validar inputs
        if not phone_number or not body_text or not buttons:
            return {"error": "Missing required parameters"}
        
        if len(buttons) > 3:
            buttons = buttons[:3]  # WhatsApp permite máximo 3 botones
        
        # Preparar el payload para botones
        buttons_payload = []
        for btn in buttons:
            buttons_payload.append({
                "type": "reply",
                "reply": {
                    "id": btn.get("id", ""),
                    "title": btn.get("title", "")
                }
            })
        
        # Construir el payload completo
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": phone_number,
            "type": "interactive",
            "interactive": {
                "type": "button",
                "body": {
                    "text": body_text
                },
                "action": {
                    "buttons": buttons_payload
                }
            }
        }
        
        # Añadir header si está presente
        if header_text:
            payload["interactive"]["header"] = {
                "type": "text",
                "text": header_text
            }
        
        try:
            # Usar el mismo endpoint y encabezados que se utilizan para enviar mensajes normales
            api_url = f"https://graph.facebook.com/v22.0/{self.phone_number_id}/messages"
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_token}"
            }
            
            response = requests.post(
                api_url,
                headers=headers,
                data=json.dumps(payload)
            )
            
            # Verificar respuesta
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Error al enviar mensaje interactivo. Código: {response.status_code}, Respuesta: {response.text}")
                return {"error": f"Error {response.status_code}: {response.text}"}
                
        except Exception as e:
            logger.error(f"Error sending interactive message: {e}")
            return {"error": str(e)}
        
    def verify_webhook(self, mode, token, challenge):
        """
        Verify the webhook with the token from Meta
        
        Args:
            mode (str): The hub mode
            token (str): The verify token
            challenge (str): The challenge string
            
        Returns:
            bool: True if verification is successful, False otherwise
        """
        expected_token = settings.WHATSAPP_VERIFY_TOKEN
        
        if mode == "subscribe" and token == expected_token:
            return True
        return False
    
    def parse_webhook_message(self, body):
        """
        Parse an incoming webhook message from WhatsApp
        
        Args:
            body (dict): The webhook event body
            
        Returns:
            tuple: (phone_number, message_text, message_id, metadata) or (None, None, None, None) if not a processable message
                   metadata contains additional information like button_id for interactive messages
        """
        try:
            entry = body.get("entry", [])
            if not entry:
                return None, None, None, None
            
            changes = entry[0].get("changes", [])
            if not changes:
                return None, None, None, None
            
            value = changes[0].get("value", {})
            
            if "statuses" in value:
                logger.info("Received a status update, not a message")
                return None, None, None, None
            
            # Extraer el phone_number_id para identificar la empresa
            phone_number_id = value.get("metadata", {}).get("phone_number_id")
            
            messages = value.get("messages", [])
            
            if not messages:
                return None, None, None, None
            
            message = messages[0]
            from_phone = message.get("from")
            message_id = message.get("id")
            message_type = message.get("type")
            
            # Objeto para información adicional
            metadata = {
                "phone_number_id": phone_number_id,
                "type": message_type,
                "contacts": value.get("contacts", [])
            }
            
            # Procesar según el tipo de mensaje
            if message_type == "text":
                # Mensaje de texto normal
                text = message.get("text", {}).get("body")
                logger.info(f"Received text message from {from_phone}: {text}")
                return from_phone, text, message_id, metadata
                
            elif message_type == "interactive":
                # Mensaje interactivo (respuesta a botones)
                interactive = message.get("interactive", {})
                interactive_type = interactive.get("type")
                
                if interactive_type == "button_reply":
                    button_reply = interactive.get("button_reply", {})
                    button_id = button_reply.get("id")
                    button_title = button_reply.get("title")
                    
                    logger.info(f"Received button reply from {from_phone}: {button_title} (ID: {button_id})")
                    metadata["button_id"] = button_id
                    metadata["button_title"] = button_title
                    
                    # Devolver el ID del botón como mensaje
                    return from_phone, f"BUTTON:{button_id}", message_id, metadata
                    
                elif interactive_type == "list_reply":
                    list_reply = interactive.get("list_reply", {})
                    list_id = list_reply.get("id")
                    list_title = list_reply.get("title")
                    
                    logger.info(f"Received list selection from {from_phone}: {list_title} (ID: {list_id})")
                    metadata["list_id"] = list_id
                    metadata["list_title"] = list_title
                    
                    # Devolver el ID de la lista como mensaje
                    return from_phone, f"LIST:{list_id}", message_id, metadata
                    
                else:
                    logger.info(f"Received unsupported interactive type: {interactive_type}")
                    return None, None, None, None
                    
            else:
                # Otros tipos de mensajes (imagen, audio, etc.)
                logger.info(f"Received non-text message type: {message_type}")
                return None, None, None, None
        
        except Exception as e:
            logger.error(f"Error parsing webhook message: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None, None, None, None