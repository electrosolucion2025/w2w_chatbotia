from django.contrib.admin.views.main import ChangeList
from django.db.models import Q
from django.urls import resolve

class CompanyFilterMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated and hasattr(request.user, 'company_admin'):
            # Guarda la empresa del usuario en la sesión para uso posterior
            request.session['admin_company_id'] = str(request.user.company_admin.company.id)
        
        response = self.get_response(request)
        return response