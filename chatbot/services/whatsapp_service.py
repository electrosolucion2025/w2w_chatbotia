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
        
    def send_interactive_message(self, phone_number, body_text, buttons, header_text=None, footer_text=None):
        """
        Envía un mensaje interactivo con botones
        
        Args:
            phone_number (str): Número de teléfono del destinatario
            body_text (str): Texto principal del mensaje
            buttons (list): Lista de diccionarios con id y title para cada botón
            header_text (str, optional): Texto del encabezado
            footer_text (str, optional): Texto del pie de página
            
        Returns:
            dict: Respuesta de la API de WhatsApp
        """
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
        
        # Añadir footer si está presente
        if footer_text:
            payload["interactive"]["footer"] = {
                "text": footer_text
            }
        
        try:
            # Usar el mismo endpoint y encabezados que se utilizan para enviar mensajes normales
            endpoint = f"{self.BASE_URL}/{self.phone_number_id}/messages"
            
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_token}"
            }
            
            response = requests.post(
                endpoint,
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
                    
            elif message_type == "audio":
                # Procesar mensaje de audio
                audio = message.get("audio", {})
                audio_id = audio.get("id")
                
                if not audio_id:
                    logger.error(f"Mensaje de audio sin ID recibido de {from_phone}")
                    return None, None, None, None
                
                logger.info(f"Mensaje de audio recibido de {from_phone}, ID: {audio_id}")
                
                # Añadir ID del audio a los metadatos
                metadata["audio_id"] = audio_id
                
                # Devolver información básica para el mensaje de audio
                return from_phone, "[Audio Message]", message_id, metadata
            
            elif message_type == "image":
                # Procesar mensaje de imagen
                image_data = message.get("image", {})
                media_id = image_data.get("id")
                caption = image_data.get("caption", "")
                
                if not media_id:
                    logger.error(f"Mensaje de imagen sin ID recibido de {from_phone}")
                    return None, None, None, None
                
                logger.info(f"Mensaje de imagen recibido de {from_phone}, ID: {media_id}, Caption: {caption}")
                
                # Añadir información de la imagen a los metadatos
                metadata["image"] = {
                    "id": media_id,
                    "caption": caption
                }
                
                # Devolver información para el mensaje de imagen
                return from_phone, caption or "[Imagen]", message_id, metadata
                    
            else:
                # Otros tipos de mensajes (imagen, audio, etc.)
                logger.info(f"Received non-text message type: {message_type}")
                return None, None, None, None
        
        except Exception as e:
            logger.error(f"Error parsing webhook message: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None, None, None, None

    def send_policy_acceptance_message(self, phone_number, policy):
        """
        Envía un mensaje interactivo con los términos y condiciones para aceptación
        
        Args:
            phone_number (str): Número de teléfono del destinatario
            policy: Objeto PolicyVersion o diccionario con los campos necesarios
        
        Returns:
            dict: Respuesta de la API de WhatsApp
        """
        import logging
        logger = logging.getLogger(__name__)
        
        # Extraer campos de la política (sea un objeto o diccionario)
        if hasattr(policy, 'title'):
            # Es un objeto PolicyVersion
            title = policy.title
            description = policy.description
            version = policy.version
            logger.info(f"Processing policy object: title={title}, version={version}")
        else:
            # Es un diccionario
            title = policy.get('title', 'Políticas de Privacidad')
            description = policy.get('description', 'Para utilizar nuestro servicio, necesitas aceptar nuestras políticas.')
            version = policy.get('version', '1.0')
        
        # Crear el mensaje con formato adecuado
        header_text = title
        
        # Formatear el cuerpo del mensaje - mantenemos el mensaje principal conciso
        body_text = f"{description}\n\n¿Aceptas nuestras políticas de privacidad y términos de servicio (v{version})?"
        
        # Botones de aceptación/rechazo y ver detalles
        buttons = [
            {"id": "accept_policies", "title": "✅ Acepto"},
            {"id": "reject_policies", "title": "❌ No acepto"},
            {"id": "view_full_policies", "title": "📋 Ver detalles"}
        ]
        
        # Footer con información adicional
        footer_text = f"Versión {version} • Powered by Whats2Want Global S.L."
        
        # Enviar el mensaje interactivo
        return self.send_interactive_message(
            phone_number=phone_number,
            header_text=header_text,
            body_text=body_text,
            buttons=buttons,
            footer_text=footer_text
        )
        
    def send_full_policy_details(self, phone_number, policy):
        """
        Envía una serie de mensajes con los detalles completos de la política
        
        Args:
            phone_number (str): Número de teléfono del destinatario
            policy: Objeto PolicyVersion o diccionario con los campos necesarios
        
        Returns:
            List: Lista de respuestas de la API de WhatsApp
        """
        import logging
        logger = logging.getLogger(__name__)
        responses = []
        
        # Extraer campos de la política
        if hasattr(policy, 'privacy_policy_text'):
            # Es un objeto PolicyVersion
            title = policy.title
            privacy_text = policy.privacy_policy_text
            terms_text = policy.terms_text
            version = policy.version
            logger.info(f"Sending full policy details for {title} v{version}")
        else:
            # Es un diccionario
            title = policy.get('title', 'Políticas de Privacidad')
            privacy_text = policy.get('privacy_policy_text', '')
            terms_text = policy.get('terms_text', '')
            version = policy.get('version', '1.0')
        
        # Enviar un mensaje introductorio
        intro_response = self.send_message(
            phone_number,
            f"*{title} - v{version}*\n\nA continuación te enviamos los detalles completos de nuestras políticas y términos."
        )
        responses.append(intro_response)
        
        # Enviar políticas de privacidad (dividir si es necesario por límites de longitud)
        if privacy_text:
            # WhatsApp tiene un límite de ~4000 caracteres por mensaje
            max_length = 3500  # Dejamos margen para encabezados
            
            if len(privacy_text) <= max_length:
                # Enviar todo en un solo mensaje
                privacy_response = self.send_message(
                    phone_number,
                    f"*POLÍTICA DE PRIVACIDAD*\n\n{privacy_text}"
                )
                responses.append(privacy_response)
            else:
                # Dividir en múltiples mensajes
                parts = self._split_long_text(privacy_text, max_length)
                for i, part in enumerate(parts):
                    prefix = f"*POLÍTICA DE PRIVACIDAD (Parte {i+1}/{len(parts)})*\n\n"
                    privacy_response = self.send_message(
                        phone_number,
                        f"{prefix}{part}"
                    )
                    responses.append(privacy_response)
        
        # Enviar términos de servicio (también dividir si es necesario)
        if terms_text:
            max_length = 3500
            
            if len(terms_text) <= max_length:
                terms_response = self.send_message(
                    phone_number,
                    f"*TÉRMINOS DE SERVICIO*\n\n{terms_text}"
                )
                responses.append(terms_response)
            else:
                parts = self._split_long_text(terms_text, max_length)
                for i, part in enumerate(parts):
                    prefix = f"*TÉRMINOS DE SERVICIO (Parte {i+1}/{len(parts)})*\n\n"
                    terms_response = self.send_message(
                        phone_number,
                        f"{prefix}{part}"
                    )
                    responses.append(terms_response)
        
        # Enviar mensaje final para solicitar aceptación nuevamente
        final_response = self.send_interactive_message(
            phone_number=phone_number,
            header_text="Confirmar Aceptación",
            body_text=f"Ahora que has revisado todos los detalles, ¿aceptas nuestras políticas de privacidad y términos de servicio (v{version})?",
            buttons=[
                {"id": "accept_policies", "title": "✅ Acepto"},
                {"id": "reject_policies", "title": "❌ No acepto"}
            ],
            footer_text=f"Versión {version} • Powered by Whats2Want Global S.L."
        )
        responses.append(final_response)
        
        return responses
    
    def get_media_url(self, media_id):
        """
        Obtiene la URL de descarga para un archivo multimedia
        """
        try:
            # URL para obtener información del recurso
            endpoint = f"https://graph.facebook.com/v22.0/{media_id}"
            
            # Headers de autorización
            headers = {
                "Authorization": f"Bearer {self.api_token}",
                "Content-Type": "application/json"
            }
            
            # Log para depuración
            logger.debug(f"Obteniendo URL para media ID: {media_id}")
            
            # Hacer solicitud a la API
            response = requests.get(endpoint, headers=headers)
            
            # Verificar si la solicitud fue exitosa
            if response.status_code != 200:
                # Mostrar error detallado para depuración
                logger.error(f"Error obteniendo URL: {response.status_code}")
                logger.error(f"Respuesta: {response.text}")
                return None
            
            # Parsear respuesta JSON
            data = response.json()
            
            # La URL está en el campo 'url' del objeto JSON
            if 'url' in data:
                return data['url']
            else:
                logger.error(f"No se encontró URL en la respuesta: {data}")
                return None
                
        except Exception as e:
            logger.error(f"Error obteniendo URL del medio: {e}")
            return None
        
    def _split_long_text(self, text, max_length):
        """
        Divide un texto largo en partes más pequeñas respetando párrafos
        
        Args:
            text (str): Texto a dividir
            max_length (int): Longitud máxima por parte
            
        Returns:
            List[str]: Lista de partes del texto
        """
        if len(text) <= max_length:
            return [text]
            
        parts = []
        current_part = ""
        
        # Dividir por párrafos primero
        paragraphs = text.split('\n\n')
        
        for paragraph in paragraphs:
            # Si añadir este párrafo excede el límite, comenzar nueva parte
            if len(current_part) + len(paragraph) + 2 > max_length:
                if current_part:  # Solo guardar si hay contenido
                    parts.append(current_part.strip())
                current_part = paragraph + "\n\n"
            else:
                current_part += paragraph + "\n\n"
        
        # Añadir la última parte si tiene contenido
        if current_part:
            parts.append(current_part.strip())
        
        # Si alguna parte todavía es demasiado larga, dividirla más
        final_parts = []
        for part in parts:
            if len(part) <= max_length:
                final_parts.append(part)
            else:
                # División simple por longitud si los párrafos son muy largos
                i = 0
                while i < len(part):
                    # Tratar de encontrar un punto o espacio cercano al límite
                    end_pos = min(i + max_length, len(part))
                    if end_pos < len(part):
                        # Buscar hacia atrás para encontrar un buen punto de corte
                        for j in range(min(end_pos, i + max_length), i, -1):
                            if part[j] in '.!? ' and j - i > max_length / 2:
                                end_pos = j + 1
                                break
                    
                    final_parts.append(part[i:end_pos])
                    i = end_pos
        
        return final_parts
    
    def send_language_selection_message(self, phone_number):
        """
        Envía un mensaje interactivo para selección de idioma
        
        Args:
            phone_number (str): Número de teléfono del destinatario
            
        Returns:
            dict: Respuesta de la API de WhatsApp
        """
        try:
            # Botones para selección de idioma
            buttons = [
                {"id": "lang_es", "title": "🇪🇸 Español"},
                {"id": "lang_en", "title": "🇬🇧 English"},
                {"id": "lang_detect", "title": "🌐 Auto-detect"}
            ]
            
            # Texto del mensaje
            body_text = "👋 ¡Bienvenido! Por favor, selecciona tu idioma preferido.\n\nWelcome! Please select your preferred language."
            
            # Enviar mensaje interactivo
            return self.send_interactive_message(
                phone_number=phone_number,
                header_text="Idioma / Language",
                body_text=body_text,
                buttons=buttons,
                footer_text="• Powered by Whats2Want Global S.L. •"
            )
            
        except Exception as e:
            logger.error(f"Error enviando selección de idioma: {e}")
            return None
        
    def download_media(self, media_id):
        """
        Descarga un archivo multimedia de WhatsApp usando su media_id
        
        Args:
            media_id (str): ID del archivo multimedia
            
        Returns:
            str: Ruta al archivo descargado o None en caso de error
        """
        try:
            import os
            import tempfile
            import uuid
            from django.core.files import File
            from django.conf import settings
            
            # 1. Obtener la URL de descarga
            media_url = self.get_media_url(media_id)
            
            if not media_url:
                logger.error(f"No se pudo obtener la URL para media_id: {media_id}")
                return None
            
            # 2. Configurar encabezados con el token de autenticación
            headers = {"Authorization": f"Bearer {self.api_token}"}
            
            logger.debug(f"Descargando medio desde: {media_url}")
            
            # 3. Descargar el archivo
            response = requests.get(media_url, headers=headers, stream=True)
            
            if response.status_code != 200:
                logger.error(f"Error descargando media: {response.status_code}")
                logger.error(f"Respuesta: {response.text}")
                return None
                
            # 4. Determinar extensión basada en Content-Type
            content_type = response.headers.get('Content-Type', 'application/octet-stream')
            extension = self._get_extension_from_mime(content_type)
            
            # 5. Guardar en archivo temporal
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=extension)
            temp_path = temp_file.name
            
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    temp_file.write(chunk)
            temp_file.close()
            
            # 6. Crear directorio para archivos de medios si no existe
            media_dir = os.path.join(settings.MEDIA_ROOT, 'whatsapp_media')
            os.makedirs(media_dir, exist_ok=True)
            
            # 7. Generar nombre de archivo único
            file_name = f"{uuid.uuid4()}{extension}"
            file_path = os.path.join('whatsapp_media', file_name)
            
            # 8. Usar API de Django para guardar archivo
            with open(temp_path, 'rb') as f:
                from django.core.files.storage import default_storage
                default_storage.save(file_path, File(f))
            
            # 9. Eliminar archivo temporal
            try:
                os.unlink(temp_path)
            except:
                pass
            
            return file_path
            
        except Exception as e:
            logger.error(f"Error descargando media: {e}", exc_info=True)
            return None
        
    def _get_extension_from_mime(self, mime_type):
        """Obtiene la extensión de archivo según el tipo MIME"""
        mime_map = {
            "image/jpeg": ".jpg",
            "image/png": ".png",
            "image/webp": ".webp",
            "image/gif": ".gif",
            "audio/ogg": ".ogg",
            "audio/mpeg": ".mp3",
            "video/mp4": ".mp4",
            "application/pdf": ".pdf",
        }
        
        return mime_map.get(mime_type.lower(), ".bin")