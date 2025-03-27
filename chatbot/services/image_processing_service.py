# services/image_processing_service.py
import logging
from chatbot.models import TicketCategory
from chatbot.services.openai_service import OpenAIService

logger = logging.getLogger(__name__)

class ImageProcessingService:
    def __init__(self):
        self.openai_service = OpenAIService()
    
    def analyze_image(self, image_path, company_id=None, category_id=None):
        """
        Analiza una imagen con OpenAI Vision API usando prompts personalizados
        
        Args:
            image_path: Ruta al archivo de imagen
            company_id: ID de la empresa (para buscar prompts específicos)
            category_id: ID de categoría (opcional, para prompts más específicos)
        
        Returns:
            str: Análisis textual de la imagen
        """
        try:
            # Cargar la imagen como base64
            with open(image_path, "rb") as image_file:
                import base64
                base64_image = base64.b64encode(image_file.read()).decode('utf-8')
            
            # Seleccionar el prompt adecuado
            prompt, model, max_tokens = self._get_appropriate_prompt(company_id, category_id)
            
            # Llamar a OpenAI para análisis
            from openai import OpenAI
            client = OpenAI()
            response = client.chat.completions.create(
                model=model,
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
                max_tokens=max_tokens,
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            logger.error(f"Error al analizar imagen: {e}")
            return "No fue posible analizar la imagen automáticamente."
    
    def _get_appropriate_prompt(self, company_id, category_id=None):
        """
        Selecciona el prompt más apropiado según la empresa y categoría
        
        Returns:
            tuple: (texto_prompt, modelo, max_tokens)
        """
        try:
            from chatbot.models import ImageAnalysisPrompt
            
            # Primero intentar encontrar prompt específico para esta categoría
            if category_id:
                category_prompt = ImageAnalysisPrompt.objects.filter(
                    company_id=company_id,
                    category_id=category_id,
                    is_default=True
                ).first()
                
                if category_prompt:
                    return (
                        category_prompt.prompt_text,
                        category_prompt.model,
                        category_prompt.max_tokens
                    )
            
            # Si no hay prompt específico para la categoría, buscar el default de la empresa
            company_prompt = ImageAnalysisPrompt.objects.filter(
                company_id=company_id,
                category=None,
                is_default=True
            ).first()
            
            if company_prompt:
                return (
                    company_prompt.prompt_text,
                    company_prompt.model,
                    company_prompt.max_tokens
                )
            
            # Si no hay prompts configurados, usar el predeterminado del sistema
            default_prompt = """
            Analiza detalladamente esta imagen que muestra un posible desperfecto o problema.
            Describe:
            1. Qué se observa en la imagen (objetos, lugar, daños)
            2. El tipo y gravedad aparente del problema
            3. Si hay algún riesgo de seguridad evidente
            4. Qué información adicional podría ser necesaria para evaluar el problema
            
            Estructura tu respuesta en párrafos cortos, con lenguaje técnico pero comprensible.
            """
            
            return (default_prompt, "gpt-4o", 500)
            
        except Exception as e:
            logger.error(f"Error al obtener prompt: {e}")
            # Devolver valores por defecto en caso de error
            default_prompt = "Describe detalladamente lo que ves en esta imagen."
            return (default_prompt, "gpt-4o", 300)
    
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

    def analyze_image_with_category_detection(self, image_path, company_id, message_text=None):
        """
        Analiza una imagen determinando primero su posible categoría
        
        Args:
            image_path: Ruta al archivo de imagen
            company_id: ID de la empresa
            message_text: Texto del mensaje que acompaña la imagen (opcional)
        
        Returns:
            dict: {
                'analysis': texto del análisis general,
                'detected_category_id': ID de la categoría detectada,
                'certainty': nivel de certeza (0-1)
            }
        """
        try:
            # 1. Primero hacer un análisis básico para identificar lo que hay en la imagen
            base_analysis = self._perform_basic_analysis(image_path)
            
            # 2. Obtener las categorías disponibles para esta empresa
            from chatbot.models import TicketCategory
            categories = TicketCategory.objects.filter(company_id=company_id)
            
            if not categories:
                # Si no hay categorías, devolver solo el análisis básico
                return {
                    'analysis': base_analysis,
                    'detected_category_id': None,
                    'certainty': 0
                }
            
            # 3. Determinar la categoría más probable usando IA
            category_info = self._detect_most_likely_category(
                base_analysis, 
                message_text,
                [(cat.id, cat.name) for cat in categories]
            )
            
            # 4. Si tenemos una categoría con buena certeza, hacer análisis específico
            if category_info['category_id'] and category_info['certainty'] > 0.6:
                # Análisis con el prompt específico de esa categoría
                detailed_analysis = self.analyze_image(
                    image_path,
                    company_id=company_id,
                    category_id=category_info['category_id']
                )
                
                return {
                    'analysis': detailed_analysis,
                    'detected_category_id': category_info['category_id'],
                    'certainty': category_info['certainty']
                }
            else:
                # Si no hay buena certeza, devolver el análisis básico
                return {
                    'analysis': base_analysis,
                    'detected_category_id': category_info['category_id'] if category_info['certainty'] > 0.4 else None,
                    'certainty': category_info['certainty']
                }
                
        except Exception as e:
            logger.error(f"Error en análisis con detección de categoría: {e}")
            # Análisis de respaldo simple
            try:
                return {
                    'analysis': self.analyze_image(image_path, company_id),
                    'detected_category_id': None,
                    'certainty': 0
                }
            except:
                return {
                    'analysis': "No se pudo analizar la imagen",
                    'detected_category_id': None,
                    'certainty': 0
                }
            
    def _perform_basic_analysis(self, image_path):
        """Realiza un análisis básico de la imagen sin contexto específico"""
        try:
            # Cargar la imagen como base64
            with open(image_path, "rb") as image_file:
                import base64
                base64_image = base64.b64encode(image_file.read()).decode('utf-8')
            
            # Prompt para análisis general
            prompt = """
            Describe lo que ves en esta imagen de forma detallada.
            Identifica:
            - Objetos principales
            - Contexto (lugar, ambiente)
            - Características específicas relevantes
            - Estado o condición
            """
            
            # Llamada a OpenAI
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
                max_tokens=300,
            )
            
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"Error en análisis básico: {e}")
            return "No se pudo realizar el análisis básico de la imagen."
    
    def _detect_most_likely_category(self, image_analysis, message_text, categories):
        """
        Determina la categoría más probable para la imagen y texto
        
        Args:
            image_analysis: Análisis textual de la imagen
            message_text: Texto del mensaje (opcional)
            categories: Lista de tuples (id, name) de categorías disponibles
            
        Returns:
            dict: {'category_id': id, 'category_name': name, 'certainty': 0-1}
        """
        try:
            # Construir prompt para determinar categoría
            category_descriptions = "\n".join([f"- {name} (ID: {id})" for id, name in categories])
            
            context = message_text or ""
            
            prompt = f"""
            Basándote en la siguiente descripción de una imagen y el posible texto de contexto,
            determina a qué categoría pertenece con mayor probabilidad.
            
            Descripción de la imagen:
            {image_analysis}
            
            Contexto del usuario:
            {context}
            
            Categorías disponibles:
            {category_descriptions}
            
            Responde SOLAMENTE con el formato JSON:
            {{
                "category_id": "ID de la categoría más probable (como aparece arriba)",
                "category_name": "Nombre de la categoría seleccionada",
                "certainty": "Número entre 0 y 1 que indica tu nivel de confianza",
                "explanation": "Breve explicación de tu elección"
            }}
            
            Si no puedes determinar con certeza (menos del 40%), establece certainty en 0.3 o menos.
            """
            
            # Usar OpenAI para clasificación
            from openai import OpenAI
            client = OpenAI()
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
                temperature=0.1  # Baja temperatura para decisiones más consistentes
            )
            
            # Procesar respuesta
            import json
            try:
                result = json.loads(response.choices[0].message.content)
                # Verificar que el ID sea válido (existe en nuestras categorías)
                valid_ids = [str(id) for id, _ in categories]
                if str(result.get('category_id')) in valid_ids:
                    return {
                        'category_id': result.get('category_id'),
                        'category_name': result.get('category_name'),
                        'certainty': float(result.get('certainty', 0))
                    }
                else:
                    return {'category_id': None, 'category_name': None, 'certainty': 0}
            except:
                return {'category_id': None, 'category_name': None, 'certainty': 0}
                
        except Exception as e:
            logger.error(f"Error detectando categoría: {e}")
            return {'category_id': None, 'category_name': None, 'certainty': 0}