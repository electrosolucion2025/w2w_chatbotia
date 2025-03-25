from django.urls import path
from . import views
from .views_dashboard import openai_dashboard_views  # Usaremos un nombre diferente para el módulo

urlpatterns = [
    path('webhook', views.webhook, name='webhook'),
    
    # URLs para el dashboard de OpenAI
    path('openai-dashboard/', openai_dashboard_views.OpenAIDashboardView.as_view(), name='openai_dashboard'),
    path('openai-dashboard/company/<uuid:company_id>/', openai_dashboard_views.CompanyDetailView.as_view(), name='openai_company_detail'),
    path('openai-dashboard/update-summary/', openai_dashboard_views.UpdateMonthlySummaryView.as_view(), name='openai_update_summary'),
    path('openai-dashboard/export/<uuid:company_id>/', openai_dashboard_views.ExportCompanyDataView.as_view(), name='openai_export_company'),
]