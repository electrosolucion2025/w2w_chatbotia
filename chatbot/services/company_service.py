import logging

from chatbot.services.whatsapp_service import WhatsAppService
from ..models import Company, CompanyInfo, User, UserCompanyInteraction

logger = logging.getLogger(__name__)

class CompanyService:
    """Service for fetching and formatting company information."""
    
    def get_company_by_phone_number_id(self, phone_number_id):
        """
        Get a company by WhatsApp phone number ID.
        
        Args:
            phone_number_id (str): The WhatsApp phone number ID.
            
        Returns:
            Company: The company object if found, else None.
        """
        try:
            return Company.objects.get(whatsapp_phone_number_id=phone_number_id)
        except Company.DoesNotExist:
            logger.warning(f"No company found for WhatsApp phone number ID: {phone_number_id}")
            return None
    
    def get_company_by_phone(self, phone_number_id):
        """Get a company by WhatsApp phone number ID."""
        try:
            return Company.objects.get(phone_number=phone_number_id)
        except Company.DoesNotExist:
            logger.warning(f"No company found for phone number ID: {phone_number_id}")
            return None
            
    def get_company_info(self, company):
        """
        Get formatted company information.
        
        Returns a dict with the company name and sections.
        """
        if not company:
            return None
            
        # Start with basic company info
        company_info = {
            "name": company.name,
            "sections": []
        }
        
        # Add sections from CompanyInfo model
        try:
            info_items = CompanyInfo.objects.filter(company=company)
            
            for item in info_items:
                company_info["sections"].append({
                    "title": item.title,
                    "content": item.content
                })
                
        except Exception as e:
            logger.error(f"Error fetching company info: {e}")
        
        return company_info

    def get_or_create_user(self, whatsapp_number, name=None):
        """
        Get an existing user or create a new one based on WhatsApp number.
        Updates the name if it has changed.
        
        Args:
            whatsapp_number (str): The WhatsApp number of the user
            name (str, optional): The user's name from WhatsApp profile
            
        Returns:
            User: The user object
        """
        try:
            # Try to find the user by WhatsApp number
            try:
                user = User.objects.get(whatsapp_number=whatsapp_number)
                
                # If user exists and name has changed, update it
                if name and user.name != name:
                    logger.info(f"Updating name for user {whatsapp_number} from '{user.name}' to '{name}'")
                    user.name = name
                    user.save()
                    
                return user
            except User.DoesNotExist:
                # User doesn't exist, create a new one
                logger.info(f"Creating new user with WhatsApp number {whatsapp_number}")
                user = User(
                    whatsapp_number=whatsapp_number,
                    name=name
                )
                user.save()
                return user
        except Exception as e:
            logger.error(f"Error getting/creating user {whatsapp_number}: {e}")
            return None

    def record_user_company_interaction(self, user, company):
        """
        Record an interaction between a user and a company.
        
        Args:
            user (User): The user object
            company (Company): The company object
            
        Returns:
            UserCompanyInteraction: The interaction object
        """
        try:
            # Get or create the interaction
            interaction, created = UserCompanyInteraction.objects.get_or_create(
                user=user,
                company=company
            )
            
            # Always update the last_interaction time
            if not created:
                interaction.save()  # This will update the auto_now field
                
            return interaction
        except Exception as e:
            logger.error(f"Error recording interaction between {user} and {company}: {e}")
            return None
        
    def get_company_user_and_whatsapp_service(self, metadata, from_phone, default_whatsapp=None):
        """
        Extrae la información de empresa, usuario y configura el servicio de WhatsApp
        
        Args:
            metadata: Diccionario con los metadatos del mensaje de WhatsApp
            from_phone: Número de teléfono del remitente
            default_whatsapp: Instancia por defecto del servicio WhatsApp (opcional)
            
        Returns:
            tuple: (company, user, contact_name, whatsapp_service)
        """
        # Extraer el phone_number_id para identificar la empresa
        phone_number_id = metadata.get("phone_number_id")
        
        # Obtener información de contacto del remitente
        contact_name = None
        contacts = metadata.get("contacts", [])
        if contacts and len(contacts) > 0:
            profile = contacts[0].get("profile", {})
            contact_name = profile.get("name")
        
        # Obtener la empresa asociada al phone_number_id
        company = self.get_company_by_phone_number_id(phone_number_id)
        
        if not company:
            logger.warning(f"No se encontró empresa para phone_number_id: {phone_number_id}")
            return None, None, contact_name, default_whatsapp
            
        logger.info(f"Found company: {company.name} for phone ID: {phone_number_id}")
        
        # Configurar el servicio WhatsApp con las credenciales de la empresa
        whatsapp = default_whatsapp
        if company.whatsapp_api_token and company.whatsapp_phone_number_id:
            whatsapp = WhatsAppService(
                api_token=company.whatsapp_api_token,
                phone_number_id=company.whatsapp_phone_number_id
            )
        
        # Obtener o crear el usuario
        user = self.get_or_create_user(
            whatsapp_number=from_phone,
            name=contact_name
        )
        
        if not user:
            logger.error(f"No se pudo obtener/crear usuario para {from_phone}")
            return company, None, contact_name, whatsapp
        
        return company, user, contact_name, whatsapp