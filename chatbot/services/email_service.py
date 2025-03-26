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
            subject = f"Nuevo ticket: {ticket.title}"
            
            # Formatear contenido HTML
            message_html = f"""
            <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                <h2 style="color: #333; border-bottom: 1px solid #ddd; padding-bottom: 10px;">Nuevo Ticket Recibido</h2>
                
                <div style="margin: 20px 0;">
                    <p><strong>Título:</strong> {ticket.title}</p>
                    <p><strong>Cliente:</strong> {ticket.user.name or ticket.user.whatsapp_number}</p>
                    <p><strong>Categoría:</strong> {ticket.category.name if ticket.category else 'Sin categorizar'}</p>
                    <p><strong>Fecha:</strong> {ticket.created_at.strftime('%d/%m/%Y %H:%M')}</p>
                    <p><strong>Imágenes:</strong> {ticket.images.count()}</p>
                </div>
                
                <div style="background-color: #f7f7f7; padding: 15px; border-left: 4px solid #3498db; margin: 20px 0;">
                    <h3 style="margin-top: 0;">Descripción:</h3>
                    <p style="white-space: pre-line;">{ticket.description}</p>
                </div>
                
                <div style="margin-top: 30px;">
                    <a href="{settings.BASE_URL}/admin/chatbot/ticket/{ticket.id}/change/" 
                       style="background-color: #3498db; color: white; padding: 10px 15px; text-decoration: none; border-radius: 4px;">
                        Ver detalles del ticket
                    </a>
                </div>
                
                <p style="color: #777; font-size: 0.8em; margin-top: 30px; border-top: 1px solid #ddd; padding-top: 10px;">
                    Este es un mensaje automático. Por favor no responda directamente a este correo.
                </p>
            </div>
            """
            
            # Mensaje en texto plano
            text_content = f"""
            Nuevo Ticket Recibido
            
            Título: {ticket.title}
            Cliente: {ticket.user.name or ticket.user.whatsapp_number}
            Categoría: {ticket.category.name if ticket.category else 'Sin categorizar'}
            Descripción: {ticket.description}
            
            El ticket incluye {ticket.images.count()} imagen(es).
            
            Ver detalle: {settings.BASE_URL}/admin/chatbot/ticket/{ticket.id}/change/
            """
            
            # Enviar emails a cada destinatario
            success_count = 0
            for recipient in admin_emails:
                if self.send_email(
                    to_email=recipient,
                    subject=subject,
                    html_content=message_html,
                    text_content=text_content
                ):
                    success_count += 1
                    
            logger.info(f"Notificación de ticket enviada a {success_count} de {len(admin_emails)} destinatarios")
            return success_count > 0
            
        except Exception as e:
            logger.error(f"Error al enviar notificación de ticket: {e}")
            return False
    
    def send_ticket_image_notification(self, ticket, image):
        """
        Envía una notificación por email cuando se añade una nueva imagen a un ticket
        
        Args:
            ticket: Objeto Ticket con los datos del ticket
            image: Objeto TicketImage con los datos de la imagen
        
        Returns:
            bool: True si se envió correctamente, False en caso contrario
        """
        try:
            # Verificar destinatarios
            admin_emails = self._get_admin_emails_for_company(ticket.company)
            
            if not admin_emails:
                logger.warning(f"No se puede enviar notificación de imagen para ticket {ticket.id} porque no hay destinatarios")
                return False
                
            # Preparar contenido del email
            subject = f"Nueva imagen en ticket: {ticket.title}"
            
            # Formatear contenido HTML
            message_html = f"""
            <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                <h2 style="color: #333; border-bottom: 1px solid #ddd; padding-bottom: 10px;">Nueva Imagen en Ticket Existente</h2>
                
                <div style="margin: 20px 0;">
                    <p><strong>Ticket:</strong> {ticket.title}</p>
                    <p><strong>Cliente:</strong> {ticket.user.name or ticket.user.whatsapp_number}</p>
                    <p><strong>Imágenes totales:</strong> {ticket.images.count()}</p>
                </div>
                
                <div style="background-color: #f7f7f7; padding: 15px; border-left: 4px solid #3498db; margin: 20px 0;">
                    <h3 style="margin-top: 0;">Descripción de la imagen:</h3>
                    <p style="white-space: pre-line;">{image.ai_description[:500]}</p>
                </div>
                
                <div style="margin-top: 30px;">
                    <a href="{settings.BASE_URL}/admin/chatbot/ticket/{ticket.id}/change/" 
                    style="background-color: #3498db; color: white; padding: 10px 15px; text-decoration: none; border-radius: 4px;">
                        Ver detalles del ticket
                    </a>
                </div>
            </div>
            """
            
            # Mensaje en texto plano
            text_content = f"""
            Nueva imagen en ticket: {ticket.title}
            
            Cliente: {ticket.user.name or ticket.user.whatsapp_number}
            Imágenes totales: {ticket.images.count()}
            
            Descripción de la nueva imagen:
            {image.ai_description[:500]}
            
            Ver detalle: {settings.BASE_URL}/admin/chatbot/ticket/{ticket.id}/change/
            """
            
            # Enviar emails a cada destinatario
            success_count = 0
            for recipient in admin_emails:
                if self.send_email(
                    to_email=recipient,
                    subject=subject,
                    html_content=message_html,
                    text_content=text_content
                ):
                    success_count += 1
                    
            logger.info(f"Notificación de imagen enviada a {success_count} de {len(admin_emails)} destinatarios")
            return success_count > 0
            
        except Exception as e:
            logger.error(f"Error al enviar notificación de imagen: {e}")
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
        Envía un email usando SendGrid
        
        Args:
            to_email (str): Email del destinatario
            subject (str): Asunto del email
            html_content (str): Contenido HTML del email
            text_content (str, optional): Contenido texto plano alternativo
            cc (List[str], optional): Lista de emails para CC
            bcc (List[str], optional): Lista de emails para BCC
            attachment_path (str, optional): Ruta al archivo adjunto
            
        Returns:
            bool: True si se envió correctamente, False en caso contrario
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
            
            # # Añadir CC si existe
            # if cc:
            #     personalization = Personalization()
            #     for cc_email in cc:
            #         personalization.add_cc(Email(cc_email))
            #     message.add_personalization(personalization)
            
            # # Añadir BCC si existe
            # if bcc:
            #     personalization = Personalization()
            #     for bcc_email in bcc:
            #         personalization.add_bcc(Email(bcc_email))
            #     message.add_personalization(personalization)
            
            # # Añadir adjunto si existe
            # if attachment_path:
            #     import base64
            #     attachment_filename = attachment_path.split('/')[-1]
            #     with open(attachment_path, 'rb') as f:
            #         data = base64.b64encode(f.read()).decode()
                    
            #         attachment = Attachment()
            #         attachment.file_content = FileContent(data)
            #         attachment.file_type = FileType('application/octet-stream')
            #         attachment.file_name = FileName(attachment_filename)
            #         attachment.disposition = Disposition('attachment')
                    
            #         message.add_attachment(attachment)
            
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
            logger.error(f"Error en SendGridService.send_email: {e}")
            return False