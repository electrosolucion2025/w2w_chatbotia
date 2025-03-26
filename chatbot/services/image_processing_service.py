# services/image_processing_service.py
import logging
from chatbot.models import TicketCategory
from chatbot.services.openai_service import OpenAIService

logger = logging.getLogger(__name__)

class ImageProcessingService:
    def __init__(self):
        self.openai_service = OpenAIService()
    
    def analyze_image(self, image_path):
        """
        Analiza una imagen con OpenAI Vision API para describir su contenido
        """
        try:
            # Cargar la imagen como base64
            with open(image_path, "rb") as image_file:
                import base64
                base64_image = base64.b64encode(image_file.read()).decode('utf-8')
            
            # Crear prompt para análisis
            prompt = """
            Analiza detalladamente esta imagen que muestra un posible desperfecto o problema.
            Describe:
            1. Qué se observa en la imagen (objetos, lugar, daños)
            2. El tipo y gravedad aparente del problema
            3. Si hay algún riesgo de seguridad evidente
            4. Qué información adicional podría ser necesaria para evaluar el problema
            
            Estructura tu respuesta en párrafos cortos, con lenguaje técnico pero comprensible.
            """
            
            # Llamar a OpenAI para análisis
            from openai import OpenAI
            client = OpenAI()
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{base64_image}",
                                },
                            },
                        ],
                    }
                ],
                max_tokens=500,
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            logger.error(f"Error al analizar imagen: {e}")
            return "No fue posible analizar la imagen automáticamente."
    
    def detect_issue_category(self, description, image_analysis, company_id):
        """
        Intenta categorizar automáticamente el problema basado en la descripción y análisis de imagen
        """
        try:
            # Obtener categorías de la empresa
            categories = TicketCategory.objects.filter(company_id=company_id)
            category_names = [cat.name for cat in categories]
            
            if not category_names:
                return None
            
            # Crear prompt para categorización
            prompt = f"""
            Basándome en la siguiente descripción de un problema y el análisis de una imagen relacionada, 
            determina la categoría más apropiada para clasificar este ticket. 
            
            Descripción del problema: "{description}"
            
            Análisis de imagen: "{image_analysis}"
            
            Las categorías disponibles son: {', '.join(category_names)}
            
            Responde únicamente con el nombre exacto de la categoría que mejor se ajuste.
            """
            
            response = self.openai_service.generate_response(
                message=prompt,
                context=None
            )
            
            # Buscar la categoría que coincida con la respuesta
            for category in categories:
                if category.name.lower() in response.lower():
                    return category
            
            return None
            
        except Exception as e:
            logger.error(f"Error al categorizar problema: {e}")
            return None