import logging
from openai import OpenAI
from django.conf import settings

logger = logging.getLogger(__name__)

class LanguageService:
    """Servicio para la detección y gestión de idiomas"""
    
    def __init__(self):
        self.client = OpenAI(api_key=settings.OPENAI_API_KEY)
        
    def detect_language_with_openai(self, text):
        """
        Detecta el idioma de un texto usando OpenAI
        
        Args:
            text (str): Texto para detectar idioma
            
        Returns:
            dict: Información sobre el idioma detectado
        """
        try:
            # Si el texto es muy corto, no es confiable
            if len(text.strip()) < 3:
                return {"code": "es", "name": "español"}
                
            # Prompt para OpenAI para detectar cualquier idioma
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "Eres un detector preciso de idiomas. Identifica el idioma de cualquier texto proporcionado. Responde SOLAMENTE con formato 'código_ISO,nombre_idioma', por ejemplo: 'es,español' o 'zh,chino'."},
                    {"role": "user", "content": f"Detecta el idioma del siguiente texto: '{text}'"}
                ],
                max_tokens=20,
                temperature=0.3
            )
            
            # Procesar respuesta
            result = response.choices[0].message.content.strip()
            logger.info(f"Detección de idioma para texto '{text[:20]}...': {result}")
            
            if "," in result:
                code, name = result.split(",", 1)
                return {
                    "code": code.strip().lower(),
                    "name": name.strip()
                }
            else:
                # Fallback si no viene en formato esperado
                logger.warning(f"Formato inesperado en detección: {result}")
                import re
                codes = re.findall(r'\b[a-z]{2}\b', result.lower())
                if codes:
                    return {
                        "code": codes[0],
                        "name": result.strip()
                    }
                else:
                    # Si todo falla, devolver español como fallback
                    return {
                        "code": "es",
                        "name": "español"
                    }
                    
        except Exception as e:
            logger.error(f"Error detectando idioma con OpenAI: {e}", exc_info=True)
            return {
                "code": "es",
                "name": "español"
            }