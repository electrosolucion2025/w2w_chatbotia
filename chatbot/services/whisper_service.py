import os
import tempfile
import requests
import logging
import uuid
from django.core.files import File
from openai import OpenAI

logger = logging.getLogger(__name__)

class WhisperService:
    def __init__(self, api_key=None):
        # Obtener la API key de las variables de entorno o settings
        from django.conf import settings
        self.api_key = api_key or getattr(settings, 'OPENAI_API_KEY', None)
        self.client = OpenAI(api_key=self.api_key)
    
    def process_whatsapp_audio(self, message, audio_id, company):
        """
        Procesa un audio de WhatsApp: descarga, transcribe y guarda
        
        Args:
            message (Message): El mensaje asociado al audio
            audio_id (str): ID del audio en la API de WhatsApp
            company (Company): La empresa asociada al mensaje
            
        Returns:
            dict: Resultado del procesamiento con transcripción o error
        """
        from ..models import AudioMessage
        
        try:
            # Crear una instancia de WhatsApp usando las credenciales de la empresa
            from .whatsapp_service import WhatsAppService
            whatsapp = WhatsAppService(
                api_token=company.whatsapp_api_token,
                phone_number_id=company.whatsapp_phone_number_id
            )
            
            # 1. Obtener la URL del audio
            audio_url = whatsapp.get_media_url(audio_id)
            if not audio_url:
                logger.error(f"No se pudo obtener URL para audio_id: {audio_id}")
                return {"success": False, "error": "No se pudo obtener URL del audio"}
                
            # 2. Crear registro AudioMessage
            audio_message = AudioMessage.objects.create(
                message=message,
                processing_status='processing'
            )
            
            # 3. Descargar el audio
            temp_path = None
            try:
                # Preparar headers para la descarga
                headers = {"Authorization": f"Bearer {company.whatsapp_api_token}"}
                
                # Descargar el archivo
                response = requests.get(audio_url, headers=headers, stream=True)
                
                if response.status_code != 200:
                    logger.error(f"Error al descargar audio: {response.status_code}")
                    audio_message.processing_status = 'failed'
                    audio_message.error_message = f"Error de descarga: {response.status_code}"
                    audio_message.save()
                    return {"success": False, "error": "Error al descargar audio"}
                
                # Guardar en archivo temporal
                temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.ogg')
                temp_path = temp_file.name
                
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        temp_file.write(chunk)
                temp_file.close()
                
                # Guardar el archivo en el modelo
                with open(temp_path, 'rb') as f:
                    file_name = f"{uuid.uuid4()}.ogg"
                    audio_message.audio_file.save(file_name, File(f))
                
                # 4. Transcribir el audio con Whisper
                with open(temp_path, 'rb') as audio_file:
                    # Llamar a la API de OpenAI Whisper
                    result = self.client.audio.transcriptions.create(
                        model="whisper-1",
                        file=audio_file,
                        language="es"
                    )
                    
                    # Obtener el texto transcrito
                    text = result.text
                    
                # 5. Actualizar el mensaje de audio
                audio_message.transcription = text
                audio_message.transcription_model = "whisper-1"
                audio_message.processing_status = 'completed'
                audio_message.save()
                
                # 6. Actualizar el mensaje original
                message.message_text = text
                message.save()
                
                # 7. Limpiar archivo temporal
                if temp_path and os.path.exists(temp_path):
                    os.unlink(temp_path)
                
                logger.info(f"Audio transcrito exitosamente: {text[:100]}")
                return {
                    "success": True,
                    "transcription": text
                }
                    
            except Exception as e:
                logger.error(f"Error en procesamiento de audio: {str(e)}", exc_info=True)
                
                # Actualizar estado de error
                audio_message.processing_status = 'failed'
                audio_message.error_message = str(e)
                audio_message.save()
                
                # Limpiar archivo temporal en caso de error
                if temp_path and os.path.exists(temp_path):
                    try:
                        os.unlink(temp_path)
                    except:
                        pass
                
                return {
                    "success": False,
                    "error": str(e)
                }
                
        except Exception as e:
            logger.error(f"Error general en proceso de audio: {str(e)}", exc_info=True)
            return {
                "success": False,
                "error": str(e)
            }