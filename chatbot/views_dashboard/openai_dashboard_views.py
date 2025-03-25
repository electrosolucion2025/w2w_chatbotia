import csv
from datetime import datetime, timedelta
import json

from django.views.generic import TemplateView, View
from django.contrib.admin.views.decorators import staff_member_required
from django.utils.decorators import method_decorator
from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse, JsonResponse
from django.contrib import messages
from django.utils import timezone
from django.db.models import Sum, Count, Avg

from ..models import Company, OpenAIUsageRecord, OpenAIMonthlySummary
from ..services.openai_metrics_service import OpenAIMetricsService

@method_decorator(staff_member_required, name='dispatch')
class OpenAIDashboardView(TemplateView):
    """Vista principal del dashboard de OpenAI"""
    template_name = 'chatbot/openai_dashboard/dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Obtener resúmenes del mes actual
        today = timezone.now().date()
        current_month = today.month
        current_year = today.year
        
        # Calcular mes anterior
        prev_month = current_month - 1
        prev_year = current_year
        if prev_month == 0:
            prev_month = 12
            prev_year -= 1
        
        # Obtener resúmenes del mes actual
        current_summaries = OpenAIMonthlySummary.objects.filter(
            year=current_year, 
            month=current_month
        ).select_related('company')
        
        # Obtener resúmenes del mes anterior
        prev_summaries = OpenAIMonthlySummary.objects.filter(
            year=prev_year, 
            month=prev_month
        ).select_related('company')
        
        # Crear diccionario para acceso rápido a los datos del mes anterior
        prev_data = {s.company_id: s for s in prev_summaries}
        
        # Preparar datos para la plantilla
        companies_data = []
        total_current_tokens = 0
        total_current_cost = 0
        
        for summary in current_summaries:
            # Obtener datos del mes anterior para esta empresa
            prev_summary = prev_data.get(summary.company_id)
            
            # Calcular variación
            token_change = 0
            cost_change = 0
            
            if prev_summary:
                if prev_summary.total_tokens > 0:
                    token_change = ((summary.total_tokens - prev_summary.total_tokens) / prev_summary.total_tokens) * 100
                
                if prev_summary.total_cost > 0:
                    cost_change = ((summary.total_cost - prev_summary.total_cost) / prev_summary.total_cost) * 100
            
            # Agregar a la lista
            companies_data.append({
                'company': summary.company,
                'total_tokens': summary.total_tokens,
                'total_cost': summary.total_cost,
                'token_change': token_change,
                'cost_change': cost_change
            })
            
            # Actualizar totales
            total_current_tokens += summary.total_tokens
            total_current_cost += summary.total_cost
            
        # Ordenar por coste descendente
        companies_data.sort(key=lambda x: x['total_cost'], reverse=True)
        
        # Añadir empresas sin resumen (aquellas que aún no han generado datos este mes)
        companies_without_summary = Company.objects.exclude(
            id__in=[s.company_id for s in current_summaries]
        ).filter(active=True)
        
        for company in companies_without_summary:
            companies_data.append({
                'company': company,
                'total_tokens': 0,
                'total_cost': 0,
                'token_change': 0,
                'cost_change': 0
            })
            
        context.update({
            'companies_data': companies_data,
            'current_month': today.strftime("%B %Y"),
            'total_tokens': total_current_tokens,
            'total_cost': total_current_cost,
            'monthly_data': self.get_monthly_trend_data()
        })
        
        return context
        
    def get_monthly_trend_data(self):
        """Obtiene datos de tendencia mensual para gráficos"""
        # Obtener totales por mes para los últimos 12 meses
        today = timezone.now().date()
        
        # Preparar array de 12 meses hacia atrás
        months_data = []
        for i in range(11, -1, -1):  # 11 meses atrás hasta actual
            # Calcular el mes/año
            month = today.month - i
            year = today.year
            
            while month <= 0:
                month += 12
                year -= 1
                
            # Obtener datos agregados para este mes
            month_summary = OpenAIMonthlySummary.objects.filter(
                year=year,
                month=month
            ).aggregate(
                tokens=Sum('total_tokens'),
                cost=Sum('total_cost')
            )
            
            # Añadir a la lista
            months_data.append({
                'month': f"{month}/{year}",
                'month_name': datetime(year, month, 1).strftime("%b %Y"),
                'tokens': month_summary['tokens'] or 0,
                'cost': float(month_summary['cost'] or 0)
            })
            
        return months_data

@method_decorator(staff_member_required, name='dispatch')
class CompanyDetailView(TemplateView):
    """Vista detallada de una empresa"""
    template_name = 'chatbot/openai_dashboard/company_detail.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        company_id = self.kwargs.get('company_id')
        company = get_object_or_404(Company, id=company_id)
        
        metrics_service = OpenAIMetricsService()
        
        # Determinar período
        period = self.request.GET.get('period', '30days')
        
        today = timezone.now().date()
        if period == '30days':
            start_date = today - timedelta(days=29)
            title_period = "últimos 30 días"
            end_date = today
        elif period == 'month':
            start_date = today.replace(day=1)
            title_period = f"mes actual ({start_date.strftime('%d/%m/%Y')} - {today.strftime('%d/%m/%Y')})"
            end_date = today
        elif period == 'previous_month':
            last_month_end = today.replace(day=1) - timedelta(days=1)
            start_date = last_month_end.replace(day=1)
            end_date = last_month_end
            title_period = f"mes anterior ({start_date.strftime('%d/%m/%Y')} - {end_date.strftime('%d/%m/%Y')})"
        else:
            start_date = today - timedelta(days=29)
            title_period = "últimos 30 días"
            end_date = today
            
        # Obtener estadísticas
        stats = metrics_service.get_company_usage(company, start_date, end_date)
        
        # Obtener datos para gráficos
        chart_data = metrics_service.get_daily_usage_data(company, days=30)
        
        # Preparar datos para gráficos
        chart_labels = [item['date'].strftime("%d/%m") for item in chart_data]
        chart_tokens = [item['tokens'] for item in chart_data]
        chart_costs = [float(item['cost']) for item in chart_data]
        
        context.update({
            'company': company,
            'stats': stats,
            'period': period,
            'title_period': title_period,
            'chart_labels': json.dumps(chart_labels),
            'chart_tokens': json.dumps(chart_tokens),
            'chart_costs': json.dumps(chart_costs),
        })
        
        return context

@method_decorator(staff_member_required, name='dispatch')
class UpdateMonthlySummaryView(View):
    """Vista para actualizar resúmenes mensuales"""
    
    def get(self, request):
        try:
            metrics_service = OpenAIMetricsService()
            now = timezone.now()
            
            metrics_service.generate_monthly_summary(year=now.year, month=now.month)
            
            messages.success(request, "Resúmenes mensuales actualizados correctamente")
        except Exception as e:
            messages.error(request, f"Error al actualizar resúmenes: {e}")
            
        return redirect('openai_dashboard')

@method_decorator(staff_member_required, name='dispatch')
class ExportCompanyDataView(View):
    """Vista para exportar datos de una empresa"""
    
    def get(self, request, company_id):
        try:
            company = get_object_or_404(Company, id=company_id)
            
            # Determinar período
            period = request.GET.get('period', '30days')
            today = timezone.now().date()
            
            if period == '30days':
                start_date = today - timedelta(days=29)
                period_name = "ultimos_30_dias"
                end_date = today
            elif period == 'month':
                start_date = today.replace(day=1)
                period_name = f"mes_actual_{today.strftime('%Y%m')}"
                end_date = today
            elif period == 'previous_month':
                last_month_end = today.replace(day=1) - timedelta(days=1)
                start_date = last_month_end.replace(day=1)
                end_date = last_month_end
                period_name = f"mes_anterior_{last_month_end.strftime('%Y%m')}"
            else:
                start_date = today - timedelta(days=29)
                period_name = "ultimos_30_dias"
                end_date = today
            
            # Obtener registros
            records = OpenAIUsageRecord.objects.filter(
                company=company,
                timestamp__date__range=(start_date, end_date)
            ).order_by('timestamp')
            
            # Crear respuesta CSV
            response = HttpResponse(content_type='text/csv')
            filename = f"openai_usage_{company.name.replace(' ', '_')}_{period_name}.csv"
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            
            writer = csv.writer(response)
            writer.writerow([
                'Fecha', 'Hora', 'Modelo', 'Tokens Entrada', 'Tokens Salida', 
                'Total Tokens', 'Cacheado', 'Coste Entrada ($)', 'Coste Salida ($)', 
                'Coste Total ($)'
            ])
            
            for record in records:
                writer.writerow([
                    record.timestamp.strftime('%Y-%m-%d'),
                    record.timestamp.strftime('%H:%M:%S'),
                    record.model,
                    record.tokens_input,
                    record.tokens_output,
                    record.tokens_total,
                    'Sí' if record.cached_request else 'No',
                    record.cost_input,
                    record.cost_output,
                    record.cost_total
                ])
                
            return response
            
        except Exception as e:
            messages.error(request, f"Error al exportar datos: {e}")
            return redirect('openai_dashboard')