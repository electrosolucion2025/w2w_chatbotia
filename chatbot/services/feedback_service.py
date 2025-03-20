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
        
        Args:
            session: Sesión asociada al feedback
            user: Usuario que envía el feedback
            company: Empresa a la que se refiere el feedback
            feedback_type: Tipo de feedback (positive, negative, neutral)
            comment: Comentario opcional
            
        Returns:
            Feedback: Objeto de feedback creado
        """
        try:
            # Crear o actualizar feedback
            feedback, created = Feedback.objects.update_or_create(
                session=session,
                defaults={
                    'user': user,
                    'company': company,
                    'rating': feedback_type,
                    'comment': comment
                }
            )
            
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