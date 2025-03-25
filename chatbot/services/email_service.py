import os
import logging
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, Email, To, Content, HtmlContent
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)

class EmailService:
    """Servicio para envío de emails usando SendGrid"""
    
    def __init__(self):
        """Inicializa el servicio con la API key de SendGrid"""
        self.api_key = settings.SENDGRID_API_KEY
        self.from_email = settings.SENDGRID_FROM_EMAIL
        self.from_name = settings.SENDGRID_FROM_NAME
        
    def send_lead_notification(self, company, session):
        """
        Envía una notificación por email cuando un lead es calificado como alta/media intención
        
        Args:
            company: Objeto Company con los datos de la empresa
            session: Objeto Session con la información del lead
        
        Returns:
            bool: True si se envió correctamente, False en caso contrario
        """
        try:
            # Verificar que hay una dirección de correo para enviar
            if not company.contact_email:
                logger.warning(f"No se puede enviar notificación de lead para la empresa {company.name} porque no tiene email de contacto")
                return False
                
            # Verificar que hay análisis de la conversación
            if not session.analysis_results:
                logger.warning(f"No se puede enviar notificación de lead para la sesión {session.id} porque no tiene análisis")
                return False
                
            # Obtener nivel de interés
            interest_level = session.analysis_results.get('purchase_interest_level', 'ninguno')
            
            # Solo enviar si es alto o medio
            if interest_level not in ['alto', 'medio']:
                logger.debug(f"No se envía notificación para sesión {session.id} porque el interés es {interest_level}")
                return False
                
            # Preparar datos para el correo
            user = session.user
            user_name = user.name or user.whatsapp_number
            
            # Obtener un resumen de la conversación
            summary = session.analysis_results.get('summary', 'No hay resumen disponible')
            
            # Obtener info de contacto si existe
            contact_info = session.analysis_results.get('contact_info', {})
            contact_type = contact_info.get('type', '')
            contact_value = contact_info.get('value', '')
            
            # Obtener intereses específicos
            specific_interests = session.analysis_results.get('specific_interests', [])
            interests_html = ""
            if specific_interests:
                interests_html = "<ul>"
                for interest in specific_interests:
                    interests_html += f"<li>{interest}</li>"
                interests_html += "</ul>"
            else:
                interests_html = "<p>No se identificaron intereses específicos</p>"
                
            # Determinar color del encabezado según nivel de interés
            header_color = "#28a745" if interest_level == "alto" else "#ffc107"  # Verde para alto, amarillo para medio
            
            # Usar start_time en lugar de created_at
            # Verificamos primero que exista el campo
            session_date = session.start_time if hasattr(session, 'start_time') else timezone.now()
            current_year = timezone.now().year
            
            # Crear el HTML del email
            html_content = f"""
            <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                <div style="background-color: {header_color}; padding: 15px; color: white; text-align: center;">
                    <h1 style="margin: 0;">LEAD {interest_level.upper()}</h1>
                </div>
                
                <div style="padding: 20px; border: 1px solid #ddd; border-top: none;">
                    <h2>Información del Cliente</h2>
                    <table style="width: 100%; border-collapse: collapse;">
                        <tr>
                            <td style="padding: 8px; border-bottom: 1px solid #eee;"><strong>Nombre:</strong></td>
                            <td style="padding: 8px; border-bottom: 1px solid #eee;">{user_name}</td>
                        </tr>
                        <tr>
                            <td style="padding: 8px; border-bottom: 1px solid #eee;"><strong>WhatsApp:</strong></td>
                            <td style="padding: 8px; border-bottom: 1px solid #eee;">{user.whatsapp_number}</td>
                        </tr>
                        <tr>
                            <td style="padding: 8px; border-bottom: 1px solid #eee;"><strong>Fecha:</strong></td>
                            <td style="padding: 8px; border-bottom: 1px solid #eee;">{session_date.strftime('%d/%m/%Y %H:%M')}</td>
                        </tr>
                        <tr>
                            <td style="padding: 8px; border-bottom: 1px solid #eee;"><strong>Nivel de Interés:</strong></td>
                            <td style="padding: 8px; border-bottom: 1px solid #eee; font-weight: bold; color: {header_color};">
                                {interest_level.upper()}
                            </td>
                        </tr>
                    """
            
            # Añadir información de contacto si existe
            if contact_value:
                html_content += f"""
                        <tr>
                            <td style="padding: 8px; border-bottom: 1px solid #eee;"><strong>{contact_type}:</strong></td>
                            <td style="padding: 8px; border-bottom: 1px solid #eee;">{contact_value}</td>
                        </tr>
                """
                
            html_content += f"""
                    </table>
                    
                    <h2>Resumen de la Conversación</h2>
                    <p style="line-height: 1.6;">{summary}</p>
                    
                    <h2>Intereses Identificados</h2>
                    {interests_html}
                    
                    <div style="margin-top: 30px; background-color: #f9f9f9; padding: 15px; border-radius: 5px;">
                        <p style="margin: 0;">
                            Para ver la conversación completa, acceda al 
                            <a href="{settings.BASE_URL}/admin/chatbot/session/{session.id}/change/">panel de administración</a>.
                        </p>
                    </div>
                </div>
                
                <div style="background-color: #f2f2f2; padding: 15px; text-align: center; font-size: 12px; color: #666;">
                    <p>Este es un mensaje automático generado por el sistema de chatbot.</p>
                    <p>© {current_year} W2W Chatbot IA</p>
                </div>
            </div>
            """
            
            # Configurar el mensaje
            message = Mail(
                from_email=(self.from_email, self.from_name),
                to_emails=company.contact_email,
                subject=f"[LEAD {interest_level.upper()}] Nuevo cliente interesado - {user_name}",
                html_content=html_content
            )
            
            # Enviar el email
            sg = SendGridAPIClient(self.api_key)
            response = sg.send(message)
            
            # Verificar respuesta
            if response.status_code >= 200 and response.status_code < 300:
                logger.info(f"Email de notificación de lead enviado correctamente para la sesión {session.id}")
                return True
            else:
                logger.error(f"Error al enviar email de notificación: {response.body}")
                return False
                
        except Exception as e:
            logger.error(f"Error al enviar notificación de lead: {e}")
            return False