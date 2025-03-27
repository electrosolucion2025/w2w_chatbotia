import os
import logging
from typing import List
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
        
    def send_ticket_notification(self, ticket):
        """
        Envía una notificación por email cuando se crea un nuevo ticket
        
        Args:
            ticket: Objeto Ticket con los datos del ticket
        
        Returns:
            bool: True si se envió correctamente, False en caso contrario
        """
        try:
            # Verificar destinatarios
            admin_emails = self._get_admin_emails_for_company(ticket.company)
            
            if not admin_emails:
                logger.warning(f"No se puede enviar notificación de ticket para {ticket.id} porque no hay destinatarios")
                return False
                
            # Preparar contenido del email
            severity_level = ticket.priority
            severity_color = {
                'low': '#28a745',       # Verde
                'medium': '#ffc107',    # Amarillo
                'high': '#dc3545',      # Rojo
                'urgent': '#721c24'     # Rojo oscuro
            }.get(severity_level, '#6c757d')  # Gris por defecto
            
            severity_text = {
                'low': 'BAJA',
                'medium': 'MEDIA',
                'high': 'ALTA',
                'urgent': 'URGENTE'
            }.get(severity_level, 'NO ESPECIFICADA')

            # Obtener la primera imagen si existe
            first_image = None
            image_html = ""
            
            if ticket.images.exists():
                first_image = ticket.images.first()
                # Crear URL de la imagen (absoluta)
                image_url = f"{settings.BASE_URL}{first_image.image.url}" if first_image and first_image.image else ""
                
                if image_url:
                    image_html = f"""
                    <div style="margin: 20px 0; text-align: center;">
                        <h3>Imagen principal:</h3>
                        <img src="{image_url}" alt="Imagen del ticket" style="max-width: 100%; max-height: 400px; border: 1px solid #ddd; border-radius: 4px;">
                    </div>
                    """
            
            # Obtener información adicional
            subject = f"[Ticket #{ticket.id}] {ticket.title}"
            
            # Formatear contenido HTML con diseño mejorado
            message_html = f"""
            <!DOCTYPE html>
            <html lang="es">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>{subject}</title>
            </head>
            <body style="font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; line-height: 1.6; color: #333; max-width: 700px; margin: 0 auto; background-color: #f9f9f9; padding: 20px;">
                <div style="background-color: #ffffff; border-radius: 8px; overflow: hidden; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
                    <!-- Encabezado con logo y título -->
                    <div style="background-color: #273c75; color: white; padding: 20px; text-align: center;">
                        <h1 style="margin: 0; font-size: 24px;">Nuevo Ticket de Soporte</h1>
                        <p style="margin: 5px 0 0 0; font-size: 16px;">ID: #{ticket.id}</p>
                    </div>
                    
                    <!-- Información principal del ticket -->
                    <div style="padding: 25px;">
                        <!-- Título y prioridad -->
                        <div style="margin-bottom: 20px; border-bottom: 1px solid #eee; padding-bottom: 15px;">
                            <h2 style="margin: 0; font-size: 20px; color: #273c75;">{ticket.title}</h2>
                            <div style="display: inline-block; margin-top: 10px; padding: 5px 15px; background-color: {severity_color}; color: white; border-radius: 30px; font-size: 14px; font-weight: bold;">
                                Prioridad: {severity_text}
                            </div>
                        </div>
                        
                        <!-- Detalles del ticket en formato de tabla -->
                        <table style="width: 100%; border-collapse: collapse; margin-bottom: 20px;">
                            <tr>
                                <td style="padding: 10px; border-bottom: 1px solid #eee; width: 30%; font-weight: bold; color: #555;">Cliente:</td>
                                <td style="padding: 10px; border-bottom: 1px solid #eee;">{ticket.user.name or ticket.user.whatsapp_number}</td>
                            </tr>
                            <tr>
                                <td style="padding: 10px; border-bottom: 1px solid #eee; font-weight: bold; color: #555;">WhatsApp:</td>
                                <td style="padding: 10px; border-bottom: 1px solid #eee;">{ticket.user.whatsapp_number}</td>
                            </tr>
                            <tr>
                                <td style="padding: 10px; border-bottom: 1px solid #eee; font-weight: bold; color: #555;">Fecha de creación:</td>
                                <td style="padding: 10px; border-bottom: 1px solid #eee;">{ticket.created_at.strftime('%d/%m/%Y %H:%M')}</td>
                            </tr>
                            <tr>
                                <td style="padding: 10px; border-bottom: 1px solid #eee; font-weight: bold; color: #555;">Categoría:</td>
                                <td style="padding: 10px; border-bottom: 1px solid #eee;">{ticket.category.name if ticket.category else 'Sin categorizar'}</td>
                            </tr>
                            <tr>
                                <td style="padding: 10px; border-bottom: 1px solid #eee; font-weight: bold; color: #555;">Estado:</td>
                                <td style="padding: 10px; border-bottom: 1px solid #eee;">{ticket.get_status_display()}</td>
                            </tr>
                            <tr>
                                <td style="padding: 10px; border-bottom: 1px solid #eee; font-weight: bold; color: #555;">Imágenes adjuntas:</td>
                                <td style="padding: 10px; border-bottom: 1px solid #eee;">{ticket.images.count()}</td>
                            </tr>
                            <tr>
                                <td style="padding: 10px; border-bottom: 1px solid #eee; font-weight: bold; color: #555;">Empresa:</td>
                                <td style="padding: 10px; border-bottom: 1px solid #eee;">{ticket.company.name}</td>
                            </tr>
                        </table>
                        
                        <!-- Descripción completa del ticket -->
                        <div style="margin-bottom: 25px;">
                            <h3 style="color: #273c75; font-size: 18px; margin-bottom: 10px;">Descripción del problema</h3>
                            <div style="background-color: #f5f6fa; padding: 15px; border-radius: 8px; border-left: 4px solid #273c75;">
                                <p style="white-space: pre-line; margin: 0; line-height: 1.7;">{ticket.description}</p>
                            </div>
                        </div>
                        
                        <!-- Imagen adjunta (si existe) -->
                        {image_html}
                        
                        <!-- Análisis AI de la primera imagen (si existe) -->
                        {f'''
                        <div style="margin-bottom: 25px;">
                            <h3 style="color: #273c75; font-size: 18px; margin-bottom: 10px;">Análisis de la imagen</h3>
                            <div style="background-color: #f5f6fa; padding: 15px; border-radius: 8px; border-left: 4px solid #3498db;">
                                <p style="white-space: pre-line; margin: 0; line-height: 1.7;">{first_image.ai_description}</p>
                            </div>
                        </div>
                        ''' if first_image and hasattr(first_image, 'ai_description') and first_image.ai_description else ''}
                        
                        <!-- Botón de acción -->
                        <div style="text-align: center; margin: 30px 0;">
                            <a href="{settings.BASE_URL}/admin/chatbot/ticket/{ticket.id}/change/" 
                            style="display: inline-block; background-color: #273c75; color: white; padding: 12px 30px; text-decoration: none; border-radius: 4px; font-weight: bold; text-transform: uppercase; font-size: 14px;">
                                Ver y Gestionar Ticket
                            </a>
                        </div>
                        
                        <!-- Información de la IA -->
                        <div style="background-color: #f0f8ff; padding: 15px; border-radius: 8px; margin-top: 25px; font-size: 14px; color: #555;">
                            <p style="margin: 0;">
                                <strong>Nota:</strong> Este ticket ha sido generado por un sistema de chatbot AI que ha interpretado la conversación con el cliente.
                                La categorización y el análisis realizado son preliminares y pueden requerir revisión.
                            </p>
                        </div>
                    </div>
                    
                    <!-- Footer -->
                    <div style="background-color: #f1f2f6; padding: 15px; text-align: center; color: #777; font-size: 13px;">
                        <p>&copy; {timezone.now().year} W2W Chatbot IA - Todos los derechos reservados.</p>
                        <p>Este es un mensaje automático. Por favor no responda directamente a este correo.</p>
                    </div>
                </div>
            </body>
            </html>
            """
            
            # Mensaje en texto plano como alternativa
            text_content = f"""
            TICKET #{ticket.id}: {ticket.title}
            
            INFORMACIÓN PRINCIPAL:
            =====================
            Cliente: {ticket.user.name or ticket.user.whatsapp_number}
            WhatsApp: {ticket.user.whatsapp_number}
            Fecha: {ticket.created_at.strftime('%d/%m/%Y %H:%M')}
            Categoría: {ticket.category.name if ticket.category else 'Sin categorizar'}
            Prioridad: {severity_text}
            Estado: {ticket.get_status_display()}
            
            DESCRIPCIÓN DEL PROBLEMA:
            ======================
            {ticket.description}
            
            {f'ANÁLISIS AI DE LA IMAGEN:\\n{first_image.ai_description}\\n' if first_image and hasattr(first_image, 'ai_description') and first_image.ai_description else ''}
            
            El ticket incluye {ticket.images.count()} imagen(es).
            
            Ver y gestionar ticket: {settings.BASE_URL}/admin/chatbot/ticket/{ticket.id}/change/
            """
            
            # Enviar emails a cada destinatario
            success_count = 0
            for recipient in admin_emails:
                if self.send_email(
                    to_email=recipient,
                    subject=subject,
                    html_content=message_html,
                    text_content=text_content,
                    attachment_path=first_image.image.path if first_image and first_image.image else None
                ):
                    success_count += 1
                    
            logger.info(f"Notificación de ticket enviada a {success_count} de {len(admin_emails)} destinatarios")
            return success_count > 0
            
        except Exception as e:
            logger.error(f"Error al enviar notificación de ticket: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False
    
    def send_ticket_image_notification(self, ticket, image):
        """
        Envía una notificación por email cuando se añade una imagen a un ticket existente
        
        Args:
            ticket: Objeto Ticket que recibió la nueva imagen
            image: Objeto TicketImage con la imagen añadida
            
        Returns:
            bool: True si se envió correctamente, False en caso contrario
        """
        try:
            # Verificar si ya se envió notificación para esta imagen
            from django.core.cache import cache
            cache_key = f"email_sent_image_{image.id}"
            
            if cache.get(cache_key):
                logger.info(f"Notificación ya enviada para imagen {image.id}. Evitando duplicado.")
                return True
            
            # Marcar como enviada (con TTL de 24 horas)
            cache.set(cache_key, True, 60 * 60 * 24)
            
            # Verificar destinatarios
            admin_emails = self._get_admin_emails_for_company(ticket.company)
            
            if not admin_emails:
                logger.warning(f"No se puede enviar notificación de imagen para ticket {ticket.id} porque no hay destinatarios")
                return False
                
            # Preparar información del ticket
            severity_level = ticket.priority
            severity_color = {
                'low': '#28a745',       # Verde
                'medium': '#ffc107',    # Amarillo
                'high': '#dc3545',      # Rojo
                'urgent': '#721c24'     # Rojo oscuro
            }.get(severity_level, '#6c757d')  # Gris por defecto
            
            severity_text = {
                'low': 'BAJA',
                'medium': 'MEDIA',
                'high': 'ALTA',
                'urgent': 'URGENTE'
            }.get(severity_level, 'NO ESPECIFICADA')
            
            # Preparar URL de imagen y miniatura
            image_url = ""
            if image and image.image:
                image_url = f"{settings.BASE_URL}{image.image.url}"
            
            # Preparar asunto del correo
            subject = f"[Ticket #{ticket.id}] Nueva imagen añadida - {ticket.title}"

            # Formatear contenido HTML con diseño mejorado
            message_html = f"""
            <!DOCTYPE html>
            <html lang="es">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>{subject}</title>
            </head>
            <body style="font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; line-height: 1.6; color: #333; max-width: 700px; margin: 0 auto; background-color: #f9f9f9; padding: 20px;">
                <div style="background-color: #ffffff; border-radius: 8px; overflow: hidden; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
                    <!-- Encabezado con logo y título -->
                    <div style="background-color: #3498db; color: white; padding: 20px; text-align: center;">
                        <h1 style="margin: 0; font-size: 24px;">Nueva Imagen en Ticket</h1>
                        <p style="margin: 5px 0 0 0; font-size: 16px;">ID: #{ticket.id}</p>
                    </div>
                    
                    <!-- Información principal del ticket -->
                    <div style="padding: 25px;">
                        <!-- Aviso destacado -->
                        <div style="background-color: #f8f9fc; border-left: 4px solid #3498db; padding: 15px; margin-bottom: 25px;">
                            <p style="margin: 0; font-size: 16px;">
                                <strong>Actualización:</strong> Se ha añadido una nueva imagen al ticket <strong>#{ticket.id}</strong>.
                            </p>
                        </div>
                    
                        <!-- Título y prioridad -->
                        <div style="margin-bottom: 20px; border-bottom: 1px solid #eee; padding-bottom: 15px;">
                            <h2 style="margin: 0; font-size: 20px; color: #273c75;">{ticket.title}</h2>
                            <div style="display: inline-block; margin-top: 10px; padding: 5px 15px; background-color: {severity_color}; color: white; border-radius: 30px; font-size: 14px; font-weight: bold;">
                                Prioridad: {severity_text}
                            </div>
                        </div>
                        
                        <!-- Detalles del ticket en formato de tabla -->
                        <table style="width: 100%; border-collapse: collapse; margin-bottom: 20px;">
                            <tr>
                                <td style="padding: 10px; border-bottom: 1px solid #eee; width: 30%; font-weight: bold; color: #555;">Cliente:</td>
                                <td style="padding: 10px; border-bottom: 1px solid #eee;">{ticket.user.name or ticket.user.whatsapp_number}</td>
                            </tr>
                            <tr>
                                <td style="padding: 10px; border-bottom: 1px solid #eee; font-weight: bold; color: #555;">WhatsApp:</td>
                                <td style="padding: 10px; border-bottom: 1px solid #eee;">{ticket.user.whatsapp_number}</td>
                            </tr>
                            <tr>
                                <td style="padding: 10px; border-bottom: 1px solid #eee; font-weight: bold; color: #555;">Estado del ticket:</td>
                                <td style="padding: 10px; border-bottom: 1px solid #eee;">{ticket.get_status_display()}</td>
                            </tr>
                            <tr>
                                <td style="padding: 10px; border-bottom: 1px solid #eee; font-weight: bold; color: #555;">Imágenes totales:</td>
                                <td style="padding: 10px; border-bottom: 1px solid #eee;">{ticket.images.count()}</td>
                            </tr>
                        </table>
                        
                        <!-- Nueva imagen -->
                        <div style="margin-bottom: 25px;">
                            <h3 style="color: #273c75; font-size: 18px; margin-bottom: 10px;">Nueva Imagen Añadida</h3>
                            <div style="text-align: center; background-color: #f5f6fa; padding: 20px; border-radius: 8px;">
                                <img src="{image_url}" alt="Nueva imagen del ticket" style="max-width: 100%; max-height: 400px; border: 1px solid #ddd; border-radius: 4px; margin-bottom: 15px;">
                            </div>
                        </div>
                        
                        <!-- Análisis AI de la imagen -->
                        {f'''
                        <div style="margin-bottom: 25px;">
                            <h3 style="color: #273c75; font-size: 18px; margin-bottom: 10px;">Análisis de la imagen</h3>
                            <div style="background-color: #f5f6fa; padding: 15px; border-radius: 8px; border-left: 4px solid #3498db;">
                                <p style="white-space: pre-line; margin: 0; line-height: 1.7;">{image.ai_description}</p>
                            </div>
                        </div>
                        ''' if hasattr(image, 'ai_description') and image.ai_description else ''}
                        
                        <!-- Botones de acción -->
                        <div style="text-align: center; margin: 30px 0;">
                            <a href="{settings.BASE_URL}/admin/chatbot/ticket/{ticket.id}/change/" 
                            style="display: inline-block; background-color: #273c75; color: white; padding: 12px 30px; text-decoration: none; border-radius: 4px; font-weight: bold; text-transform: uppercase; font-size: 14px; margin-right: 10px;">
                                Gestionar Ticket
                            </a>
                            
                            <a href="{settings.BASE_URL}/admin/chatbot/ticketimage/{image.id}/change/" 
                            style="display: inline-block; background-color: #3498db; color: white; padding: 12px 30px; text-decoration: none; border-radius: 4px; font-weight: bold; text-transform: uppercase; font-size: 14px;">
                                Ver Detalles de Imagen
                            </a>
                        </div>
                        
                        <!-- Resumen del ticket -->
                        <div style="background-color: #f8f9fc; padding: 15px; border-radius: 8px; margin-top: 25px; font-size: 14px; border-left: 4px solid #273c75;">
                            <h4 style="margin-top: 0; color: #273c75;">Resumen del Ticket</h4>
                            <p style="white-space: pre-line; margin: 0; line-height: 1.7;">
                                {ticket.description[:300]}{"..." if len(ticket.description) > 300 else ""}
                            </p>
                            <p style="margin-top: 10px;">
                                <a href="{settings.BASE_URL}/admin/chatbot/ticket/{ticket.id}/change/" style="color: #3498db; text-decoration: none; font-weight: bold;">
                                    Ver descripción completa →
                                </a>
                            </p>
                        </div>
                        
                        <!-- Información de la IA -->
                        <div style="background-color: #f0f8ff; padding: 15px; border-radius: 8px; margin-top: 25px; font-size: 14px; color: #555;">
                            <p style="margin: 0;">
                                <strong>Nota:</strong> Esta notificación ha sido generada por un sistema de chatbot AI.
                                El análisis de la imagen es preliminar y puede requerir revisión.
                            </p>
                        </div>
                    </div>
                    
                    <!-- Footer -->
                    <div style="background-color: #f1f2f6; padding: 15px; text-align: center; color: #777; font-size: 13px;">
                        <p>&copy; {timezone.now().year} W2W Chatbot IA - Todos los derechos reservados.</p>
                        <p>Este es un mensaje automático. Por favor no responda directamente a este correo.</p>
                    </div>
                </div>
            </body>
            </html>
            """
            
            # Mensaje en texto plano como alternativa
            text_content = f"""
            NUEVA IMAGEN AÑADIDA AL TICKET #{ticket.id}: {ticket.title}
            
            INFORMACIÓN DEL TICKET:
            =====================
            Cliente: {ticket.user.name or ticket.user.whatsapp_number}
            WhatsApp: {ticket.user.whatsapp_number}
            Estado: {ticket.get_status_display()}
            Prioridad: {severity_text}
            Imágenes totales: {ticket.images.count()}
            
            ANÁLISIS DE LA NUEVA IMAGEN:
            ======================
            {image.ai_description if hasattr(image, 'ai_description') and image.ai_description else "No hay análisis disponible"}
            
            RESUMEN DEL TICKET:
            ======================
            {ticket.description[:300]}{"..." if len(ticket.description) > 300 else ""}
            
            Ver y gestionar ticket: {settings.BASE_URL}/admin/chatbot/ticket/{ticket.id}/change/
            Ver detalles de la imagen: {settings.BASE_URL}/admin/chatbot/ticketimage/{image.id}/change/
            """
            
            # Enviar emails a cada destinatario
            success_count = 0
            for recipient in admin_emails:
                if self.send_email(
                    to_email=recipient,
                    subject=subject,
                    html_content=message_html,
                    text_content=text_content,
                    attachment_path=image.image.path if image and image.image else None
                ):
                    success_count += 1
                    
            logger.info(f"Notificación de nueva imagen enviada a {success_count} de {len(admin_emails)} destinatarios")
            return success_count > 0
            
        except Exception as e:
            logger.error(f"Error al enviar notificación de imagen: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False
    
    def _get_admin_emails_for_company(self, company):
        """
        Obtiene la lista de emails de administradores para una empresa
        
        Args:
            company: Objeto Company
        
        Returns:
            list: Lista de direcciones de email
        """
        from chatbot.models import CompanyAdmin
        
        admin_emails = []
        
        # Obtener emails de CompanyAdmin
        company_admins = CompanyAdmin.objects.filter(company=company)
        for admin in company_admins:
            if admin.user.email:
                admin_emails.append(admin.user.email)
        
        # Si no hay emails específicos, usar la configuración de la empresa
        if not admin_emails and hasattr(company, 'contact_email') and company.contact_email:
            admin_emails.append(company.contact_email)
            
        return admin_emails
    
    def send_email(self, to_email: str, subject: str, 
                  html_content: str, text_content: str = None, 
                  cc: List[str] = None, bcc: List[str] = None,
                  attachment_path: str = None) -> bool:
        """
        Envía un email usando SendGrid con soporte mejorado para adjuntos
        """
        try:
            sg = SendGridAPIClient(self.api_key)
            
            # Establecer email origen
            from_email = Email(self.from_email, name=self.from_name)
            
            # Crear contenido
            if not text_content:
                text_content = "Este email requiere un cliente que soporte HTML para visualizarse correctamente"
            
            # Crear mensaje
            message = Mail(
                from_email=from_email,
                subject=subject,
                to_emails=[to_email],
                plain_text_content=Content("text/plain", text_content),
                html_content=Content("text/html", html_content)
            )
            
            # Añadir adjunto si existe
            if attachment_path and os.path.exists(attachment_path):
                import base64
                from sendgrid.helpers.mail import (Attachment, FileContent, FileName, FileType, Disposition)
                
                attachment_filename = os.path.basename(attachment_path)
                with open(attachment_path, 'rb') as f:
                    encoded_file = base64.b64encode(f.read()).decode()
                    
                    attachment = Attachment()
                    attachment.file_content = FileContent(encoded_file)
                    
                    # Detectar tipo de archivo
                    mime_type = "application/octet-stream"  # Valor por defecto
                    if attachment_path.lower().endswith(('.jpg', '.jpeg')):
                        mime_type = "image/jpeg"
                    elif attachment_path.lower().endswith('.png'):
                        mime_type = "image/png"
                    elif attachment_path.lower().endswith('.pdf'):
                        mime_type = "application/pdf"
                    
                    attachment.file_type = FileType(mime_type)
                    attachment.file_name = FileName(attachment_filename)
                    attachment.disposition = Disposition('attachment')
                    message.attachment = attachment
            
            # Enviar email
            response = sg.send(message)
            
            # Verificar respuesta
            if response.status_code in (200, 202):
                logger.info(f"Email enviado correctamente a {to_email}")
                return True
            else:
                logger.error(f"Error enviando email: {response.status_code} - {response.body}")
                return False
                
        except Exception as e:
            logger.error(f"Error en EmailService.send_email: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False