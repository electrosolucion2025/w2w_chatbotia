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
            tuple: (phone_number, message_text) or (None, None) if not a text message
        """
        try:
            entry = body.get("entry", [])
            if not entry:
                return None, None
            
            changes = entry[0].get("changes", [])
            if not changes:
                return None, None
            
            value = changes[0].get("value", {})
            
            if "statuses" in value:
                logger.info("Received a status update, not a message")
                return None, None
            
            messages = value.get("messages", [])
            
            if not messages:
                return None, None
            
            message = messages[0]
            
            # Check if it's a text message
            if message.get("type") != "text":
                logger.info(f"Received non-text message type: {message.get('type')}")
                return None, None

            # Extract phone number and message text
            from_phone = message.get("from")
            message_id = message.get("id")
            text = message.get("text", {}).get("body")
            
            logger.info(f"Received message from {from_phone}: {text}")
            return from_phone, text, message_id
        
        except Exception as e:
            logger.error(f"Error parsing webhook message: {e}")
            return None, None, None