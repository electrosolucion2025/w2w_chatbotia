import logging
from ..models import Company, CompanyInfo

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