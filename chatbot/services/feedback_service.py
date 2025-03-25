import logging
from ..models import Feedback, Session, User, Company

logger = logging.getLogger(__name__)

class FeedbackService:
    """Servicio para gestionar el feedback de los usuarios"""
    
    def send_feedback_request(self, whatsapp_service, phone_number, session):
        """
        Envía una solicitud de feedback al usuario
        
        Args:
            whatsapp_service: Servicio de WhatsApp para enviar mensajes
            phone_number: Número de teléfono del usuario
            session: Sesión que ha finalizado
            
        Returns:
            dict: Respuesta de la API de WhatsApp
        """
        try:
            # Marcar la sesión como pendiente de feedback
            session.feedback_requested = True
            session.save()
            
            # Enviar mensaje interactivo con botones
            response = whatsapp_service.send_interactive_message(
                phone_number=phone_number,
                header_text="¡Gracias por contactarnos!",
                body_text="¿Qué te pareció nuestro servicio? Tu opinión nos ayuda a mejorar.",
                buttons=[
                    {"id": "positive", "title": "👍 Bueno"},
                    {"id": "negative", "title": "👎 Mejorable"},
                    {"id": "comment", "title": "💬 Comentario"}
                ]
            )
            
            logger.info(f"Solicitud de feedback enviada a {phone_number}, sesión {session.id}")
            return response
            
        except Exception as e:
            logger.error(f"Error al enviar solicitud de feedback: {e}")
            return None
    
    def process_feedback_response(self, session, user, company, feedback_type, comment=None):
        """
        Procesa la respuesta de feedback del usuario
        """
        try:
            db_feedback_type = feedback_type
            
            # Si es una solicitud de comentario, marcarla como tal en la sesión
            if feedback_type == "comment_requested":
                # Marca en la sesión que estamos esperando un comentario
                session.feedback_comment_requested = True
                session.save(update_fields=['feedback_comment_requested'])
            
                # No crear el feedback todavía, esperar el comentario real
                return None
            
            # Crear o actualizar feedback
            feedback, created = Feedback.objects.update_or_create(
                session=session,
                defaults={
                    'user': user,
                    'company': company,
                    'rating': db_feedback_type,
                    'comment': comment if comment else ""
                }
            )
            
            # Invalidar caché de estadísticas
            from django.core.cache import cache
            cache_key_patterns = [
                f"feedback_stats_{company.id}_7",
                f"feedback_stats_{company.id}_30",
                f"feedback_stats_{company.id}_90"
            ]
            for key in cache_key_patterns:
                cache.delete(key)
            
            if created:
                logger.info(f"Nuevo feedback creado para sesión {session.id}: {feedback_type}")
            else:
                logger.info(f"Feedback actualizado para sesión {session.id}: {feedback_type}")
            
            return feedback
            
        except Exception as e:
            logger.error(f"Error al procesar feedback: {e}")
            return None
    
    def get_feedback_stats(self, company, days=30):
        """
        Obtiene estadísticas de feedback para una empresa
        
        Args:
            company: Empresa para la que se obtienen estadísticas
            days: Número de días hacia atrás para calcular estadísticas
            
        Returns:
            dict: Estadísticas de feedback
        """
        from django.utils import timezone
        from datetime import timedelta
        from django.db.models import Count
        
        try:
            # Calcular fecha de inicio
            start_date = timezone.now() - timedelta(days=days)
            
            # Obtener todos los feedbacks en el período
            feedbacks = Feedback.objects.filter(
                company=company,
                created_at__gte=start_date
            )
            
            # Calcular estadísticas
            total = feedbacks.count()
            if total == 0:
                return {"total": 0, "positive": 0, "negative": 0, "neutral": 0, "comment": 0}
                
            stats = feedbacks.values('rating').annotate(count=Count('rating'))
            stats_dict = {item['rating']: item['count'] for item in stats}
            
            # Calcular porcentajes
            positive = stats_dict.get('positive', 0)
            negative = stats_dict.get('negative', 0)
            neutral = stats_dict.get('neutral', 0)
            with_comments = feedbacks.exclude(comment__isnull=True).exclude(comment='').count()
            
            return {
                "total": total,
                "positive": positive,
                "positive_percent": round(positive * 100 / total, 1) if total > 0 else 0,
                "negative": negative,
                "negative_percent": round(negative * 100 / total, 1) if total > 0 else 0,
                "neutral": neutral,
                "neutral_percent": round(neutral * 100 / total, 1) if total > 0 else 0,
                "comment": with_comments,
                "comment_percent": round(with_comments * 100 / total, 1) if total > 0 else 0
            }
            
        except Exception as e:
            logger.error(f"Error al obtener estadísticas de feedback: {e}")
            return {"error": str(e)}
    
    def get_cached_feedback_stats(self, company, days=30, cache_time=3600):
        """
        Obtiene estadísticas de feedback para una empresa con caché
        
        Args:
            company: Empresa para la que se obtienen estadísticas
            days: Número de días hacia atrás para calcular estadísticas
            cache_time: Tiempo en segundos para mantener las estadísticas en caché
            
        Returns:
            dict: Estadísticas de feedback
        """
        from django.core.cache import cache
        
        # Crear una clave única para esta consulta
        cache_key = f"feedback_stats_{company.id}_{days}"
        
        # Intentar obtener del caché primero
        cached_stats = cache.get(cache_key)
        if cached_stats is not None:
            return cached_stats
        
        # Si no está en caché, calcular estadísticas
        stats = self.get_feedback_stats(company, days)
        
        # Guardar en caché para consultas futuras
        cache.set(cache_key, stats, cache_time)
        
        return stats