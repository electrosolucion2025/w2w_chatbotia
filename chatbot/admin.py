from django.contrib import admin
from django.urls import reverse, path
from django.utils.html import format_html
from django.http import HttpResponseRedirect
from django.contrib import messages

from chatbot.services.conversation_analysis_service import ConversationAnalysisService
from .models import *
from .services.feedback_service import FeedbackService

# Inicializar servicio de feedback
feedback_service = FeedbackService()

class CompanyInfoInline(admin.TabularInline):
    model = CompanyInfo
    extra = 1

@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ('logo_thumbnail', 'name', 'tax_id', 'phone_number', 'contact_email', 'active', 'subscription_status')
    list_filter = ('active', 'business_category', 'city', 'subscription_plan')
    search_fields = ('name', 'legal_name', 'tax_id', 'phone_number', 'contact_email', 'contact_name')
    date_hierarchy = 'created_at'
    actions = ['activate_companies', 'deactivate_companies', 'extend_subscription_month']
    
    fieldsets = [
        ("Información Básica", {
            "fields": (
                ("name", "legal_name"),
                "tax_id",
                "active",
                "logo",
            )
        }),
        ("Configuración WhatsApp", {
            "fields": (
                "phone_number",
                "whatsapp_phone_number_id",
                "whatsapp_api_token",
            ),
            "description": "Configuración para la API de WhatsApp",
        }),
        ("Contacto", {
            "fields": (
                "contact_name",
                "contact_email",
                "contact_phone",
            ),
        }),
        ("Dirección", {
            "fields": (
                "address_line1",
                "address_line2",
                ("city", "postal_code"),
                ("state", "country"),
            ),
        }),
        ("Presencia Online", {
            "fields": (
                "website",
                ("facebook", "instagram"),
                ("twitter", "linkedin"),
            ),
            "classes": ("collapse",),
        }),
        ("Información de Negocio", {
            "fields": (
                "business_category",
                "business_description",
                ("founding_year", "employee_count"),
            ),
            "classes": ("collapse",),
        }),
        ("Suscripción", {
            "fields": (
                "subscription_plan",
                "subscription_end_date",
            ),
            "description": "Detalles del plan contratado",
        }),
    ]
    
    # Solo mostrar estadísticas en modo edición
    def get_readonly_fields(self, request, obj=None):
        if not obj:  # En modo creación
            return ['created_at', 'updated_at']
        # En modo edición
        return ['created_at', 'updated_at', 'feedback_summary', 'feedback_detailed_stats']
    
    # Mostrar la imagen en miniatura en la lista
    def logo_thumbnail(self, obj):
        if obj.logo:
            return format_html('<img src="{}" width="25" height="25" style="border-radius:50%" />', obj.logo.url)
        # Usar format_html también para cuando no hay logo, mostrando un marcador de posición visual
        return format_html('<div style="width:25px; height:25px; border-radius:50%; background:#eee; display:flex; align-items:center; justify-content:center; font-size:20px; color:#aaa;">?</div>')
    logo_thumbnail.short_description = ""
    
    # Mostrar estado de suscripción con colores
    def subscription_status(self, obj):
        if not obj.subscription_end_date:
            return format_html('<span style="color: #999;">Sin fecha de fin</span>')
        
        from datetime import date
        today = date.today()
        days_left = (obj.subscription_end_date - today).days
        
        if days_left < 0:
            return format_html(
                '<span style="color: #e74c3c; font-weight: bold;">Expirado</span> '
                '<span style="color: #777;">({} días)</span>', abs(days_left)
            )
        elif days_left <= 7:
            return format_html(
                '<span style="color: #e67e22; font-weight: bold;">Por expirar</span> '
                '<span style="color: #777;">({} días)</span>', days_left
            )
        else:
            return format_html(
                '<span style="color: #2ecc71;">Activa</span> '
                '<span style="color: #777;">({} días)</span>', days_left
            )
    subscription_status.short_description = "Estado Suscripción"
    
    # Funciones para el feedback
    def feedback_summary(self, obj):
        """Muestra un resumen del feedback de la empresa"""
        # Verificar que la empresa existe y tiene un ID
        if not obj or not obj.pk:
            return "Nueva empresa - Guardar primero para ver estadísticas"
            
        stats = feedback_service.get_cached_feedback_stats(obj, days=30)
        
        if "error" in stats:
            return "Error al cargar stats"
        
        if stats["total"] == 0:
            return "Sin feedback en los últimos 30 días"
            
        # Crear barras de progreso para visualización
        positive_bar = self._create_progress_bar(
            stats["positive_percent"], 
            "green", 
            f"{stats['positive']} ({stats['positive_percent']}%)"
        )
        
        negative_bar = self._create_progress_bar(
            stats["negative_percent"], 
            "red", 
            f"{stats['negative']} ({stats['negative_percent']}%)"
        )
        
        # Mostrar comentarios en lugar de neutral
        comment_bar = self._create_progress_bar(
            stats["comment_percent"], 
            "#3498db",  # Azul para comentarios
            f"{stats['comment']} ({stats['comment_percent']}%)"
        )
        
        # Formatear el resultado con HTML
        return format_html(
            '<div style="font-size: 0.9em;">'
            'Total: <strong>{}</strong><br>'
            'Positivos: {}<br>'
            'Negativos: {}<br>'
            'Comentarios: {}'
            '</div>',
            stats["total"],
            positive_bar,
            negative_bar,
            comment_bar
        )
    feedback_summary.short_description = "Feedback (30 días)"
    
    def _create_progress_bar(self, percentage, color, text=""):
        """Crea una barra de progreso visual con HTML/CSS"""
        return format_html(
            '<div style="display:flex; align-items: center;">'
            '<div style="width: 150px; background-color: #f0f0f0; height: 10px; border-radius: 5px; margin-right: 10px;">'
            '<div style="width: {}%; background-color: {}; height: 100%; border-radius: 5px;"></div>'
            '</div>'
            '<div>{}</div>'
            '</div>',
            percentage, color, text
        )
    
    def feedback_detailed_stats(self, obj):
        """Muestra estadísticas detalladas de feedback"""
        # Verificar que el objeto exista y tenga ID
        if not obj or not obj.pk:
            return "Las estadísticas de feedback estarán disponibles después de guardar."
    
        # Añadir botón para refrescar estadísticas
        refresh_url = reverse('admin:company_refresh_stats', args=[obj.pk])
        refresh_button = f'<a href="{refresh_url}" class="button">Actualizar estadísticas</a>'
        
        # Obtener estadísticas para diferentes períodos
        stats_7 = feedback_service.get_cached_feedback_stats(obj, days=7)
        stats_30 = feedback_service.get_cached_feedback_stats(obj, days=30)
        stats_90 = feedback_service.get_cached_feedback_stats(obj, days=90)
        
        # Crear tabla HTML
        html = f"""
        <div style="margin-bottom: 20px;">
            <div style="margin-bottom: 10px;">{refresh_button}</div>
            <table class="table" style="border-collapse: collapse; width: 100%;">
                <thead>
                    <tr style="background-color: #f8f9fa;">
                        <th style="text-align: left; padding: 8px; border: 1px solid #dee2e6;">Período</th>
                        <th style="text-align: center; padding: 8px; border: 1px solid #dee2e6;">Total</th>
                        <th style="text-align: center; padding: 8px; border: 1px solid #dee2e6;">Positivos</th>
                        <th style="text-align: center; padding: 8px; border: 1px solid #dee2e6;">Negativos</th>
                        <th style="text-align: center; padding: 8px; border: 1px solid #dee2e6;">Comentarios</th>
                    </tr>
                </thead>
                <tbody>
                    {self._create_stats_row("7 días", stats_7)}
                    {self._create_stats_row("30 días", stats_30)}
                    {self._create_stats_row("90 días", stats_90)}
                </tbody>
            </table>
        </div>
        """
        
        # Añadir comentarios recientes
        html += self._get_recent_comments_html(obj)
        
        return format_html(html)
    feedback_detailed_stats.short_description = "Estadísticas de Feedback"
    
    def _create_stats_row(self, label, stats):
        """Crea una fila de tabla con estadísticas"""
        if stats.get("total", 0) == 0:
            return f'<tr><td>{label}</td><td colspan="4" style="text-align: center; padding: 8px; border: 1px solid #dee2e6;">Sin datos</td></tr>'
        
        return f'''
            <tr>
                <td style="padding: 8px; border: 1px solid #dee2e6;">{label}</td>
                <td style="text-align: center; padding: 8px; border: 1px solid #dee2e6;">{stats["total"]}</td>
                <td style="text-align: center; padding: 8px; border: 1px solid #dee2e6;">{stats["positive"]} ({stats["positive_percent"]}%)</td>
                <td style="text-align: center; padding: 8px; border: 1px solid #dee2e6;">{stats["negative"]} ({stats["negative_percent"]}%)</td>
                <td style="text-align: center; padding: 8px; border: 1px solid #dee2e6;">{stats["comment"]} ({stats["comment_percent"]}%)</td>
            </tr>
        '''
    
    def _get_recent_comments_html(self, obj):
        """Obtiene HTML con comentarios recientes"""
        from django.utils import timezone
        from datetime import timedelta
        
        # Comentarios de los últimos 30 días
        thirty_days_ago = timezone.now() - timedelta(days=30)
        recent_comments = Feedback.objects.filter(
            company=obj, 
            created_at__gte=thirty_days_ago,
            comment__isnull=False
        ).exclude(comment='').order_by('-created_at')[:5]
        
        if not recent_comments:
            return '<p>No hay comentarios recientes.</p>'
            
        html = '<div><h3>Comentarios recientes</h3>'
        
        for feedback in recent_comments:
            # Obtener emoji según el rating
            if feedback.rating == 'positive':
                rating_emoji = '👍'
            elif feedback.rating == 'negative':
                rating_emoji = '👎'
            else:
                rating_emoji = '💬'
                
            # Nombre del usuario
            user_name = feedback.user.name or feedback.user.whatsapp_number
            
            # Formatear fecha
            date_str = feedback.created_at.strftime('%d/%m/%Y %H:%M')
            
            html += f'''
                <div style="margin-bottom: 10px; padding: 10px; border-left: 4px solid #ddd;">
                    <p style="margin: 0 0 5px 0;"><strong>{rating_emoji} {user_name}</strong> <span style="color: #777;">{date_str}</span></p>
                    <p style="margin: 0;">{feedback.comment}</p>
                </div>
            '''
        
        html += '</div>'
        return html
    
    # URLs y vistas personalizadas
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                '<uuid:pk>/refresh_stats/',
                self.admin_site.admin_view(self.refresh_stats_view),
                name='company_refresh_stats'),
        ]
        return custom_urls + urls
        
    def refresh_stats_view(self, request, pk):
        """Vista para refrescar estadísticas"""
        company = self.get_object(request, pk)
        
        # Invalidar caché
        from django.core.cache import cache
        cache_key_patterns = [
            f"feedback_stats_{pk}_7",
            f"feedback_stats_{pk}_30", 
            f"feedback_stats_{pk}_90"
        ]
        for key in cache_key_patterns:
            cache.delete(key)
            
        # Redireccionar de vuelta a la página de la empresa
        messages.success(request, "Estadísticas de feedback actualizadas correctamente")
        return HttpResponseRedirect("../")
    
    def change_view(self, request, object_id, form_url='', extra_context=None):
        """Personalizar la vista de edición para agregar botones personalizados"""
        extra_context = extra_context or {}
        if object_id:  # Solo si estamos editando
            refresh_url = reverse('admin:company_refresh_stats', args=[object_id])
            extra_context['refresh_stats_url'] = refresh_url
            
        return super().change_view(
            request, object_id, form_url, extra_context=extra_context
        )
        
    def add_view(self, request, form_url='', extra_context=None):
        """Vista personalizada para creación"""
        extra_context = extra_context or {}
        # No agregar botones específicos de edición
        return super().add_view(
            request, form_url, extra_context=extra_context
        )
    
    # Acciones en masa
    def activate_companies(self, request, queryset):
        """Activa las empresas seleccionadas"""
        updated = queryset.update(active=True)
        self.message_user(request, f'Se activaron {updated} empresas correctamente.')
    activate_companies.short_description = "Activar empresas seleccionadas"
    
    def deactivate_companies(self, request, queryset):
        """Desactiva las empresas seleccionadas"""
        updated = queryset.update(active=False)
        self.message_user(request, f'Se desactivaron {updated} empresas correctamente.')
    deactivate_companies.short_description = "Desactivar empresas seleccionadas"
    
    def extend_subscription_month(self, request, queryset):
        """Extiende la suscripción por un mes"""
        from datetime import date, timedelta
        count = 0
        for company in queryset:
            if company.subscription_end_date:
                company.subscription_end_date = company.subscription_end_date + timedelta(days=30)
            else:
                company.subscription_end_date = date.today() + timedelta(days=30)
            company.save()
            count += 1
        self.message_user(request, f'Se extendió la suscripción de {count} empresas por 30 días.')
    extend_subscription_month.short_description = "Extender suscripción por 1 mes"

class UserCompanyInteractionInline(admin.TabularInline):
    model = UserCompanyInteraction
    extra = 0
    readonly_fields = ('first_interaction', 'last_interaction')

@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ('whatsapp_number', 'name', 'created_at', 'policies_status')
    search_fields = ('whatsapp_number', 'name', 'email')
    list_filter = ('policies_accepted', 'created_at')
    
    def policies_status(self, obj):
        if obj.policies_accepted:
            return format_html(
                '<span style="color: green;">✅ Aceptadas</span><br>'
                '<small>Versión: {} - {}</small>',
                obj.policies_version,
                obj.policies_accepted_date.strftime('%d/%m/%Y %H:%M')
            )
        elif obj.waiting_policy_acceptance:
            return format_html('<span style="color: orange;">⏳ Pendiente de respuesta</span>')
        else:
            return format_html('<span style="color: red;">❌ No aceptadas</span>')
    
    policies_status.short_description = "Políticas"

@admin.register(UserCompanyInteraction)
class UserCompanyInteractionAdmin(admin.ModelAdmin):
    list_display = ('user', 'company', 'first_interaction', 'last_interaction')
    list_filter = ('company', 'first_interaction', 'last_interaction')
    search_fields = ('user__name', 'user__whatsapp_number', 'company__name')

# Registro para ver los mensajes relacionados con una sesión
class MessageInline(admin.TabularInline):
    model = Message
    extra = 0
    fields = ('created_at', 'is_from_user', 'message_text')
    readonly_fields = ('created_at', 'is_from_user', 'message_text')
    ordering = ('created_at',)
    can_delete = False
    max_num = 0  # Solo mostrar registros existentes

@admin.register(Session)
class SessionAdmin(admin.ModelAdmin):
    list_display = ('id', 'user_info', 'company_name', 'started_at', 'status', 'duration', 'message_count', 'lead_interest')
    list_filter = ('company', 'started_at', 'ended_at')
    search_fields = ('user__name', 'user__whatsapp_number', 'company__name')
    inlines = [MessageInline]
    readonly_fields = ('user_info', 'company_name', 'status', 'duration', 'message_count', 'analysis_display')
    
    def user_info(self, obj):
        if obj.user.name:
            return f"{obj.user.name} ({obj.user.whatsapp_number})"
        return obj.user.whatsapp_number
    
    def company_name(self, obj):
        return obj.company.name
    
    def status(self, obj):
        return "Activa" if obj.ended_at is None else "Finalizada"
    
    def duration(self, obj):
        if obj.ended_at:
            delta = obj.ended_at - obj.started_at
            minutes = delta.total_seconds() // 60
            if minutes < 60:
                return f"{int(minutes)} min"
            hours = int(minutes // 60)
            minutes = int(minutes % 60)
            return f"{hours}h {minutes}m"
        return "En curso"
    
    def message_count(self, obj):
        return obj.messages.count()
    
    def lead_interest(self, obj):
        """Muestra el nivel de interés del lead basado en el análisis"""
        if not hasattr(obj, 'analysis_results') or not obj.analysis_results:
            return "-"
        
        interest_level = obj.analysis_results.get('purchase_interest_level', 'ninguno')
        
        if interest_level == 'alto':
            return format_html('<span style="color: green; font-weight: bold;">ALTO</span>')
        elif interest_level == 'medio':
            return format_html('<span style="color: orange; font-weight: bold;">MEDIO</span>')
        elif interest_level == 'bajo':
            return format_html('<span style="color: blue;">BAJO</span>')
        else:
            return format_html('<span style="color: gray;">NINGUNO</span>')
    
    def analysis_display(self, obj):
        """Muestra el análisis de la conversación en formato legible"""
        if not hasattr(obj, 'analysis_results') or not obj.analysis_results:
            return format_html("<p>No hay análisis disponible para esta sesión.</p>")
            
        analysis = obj.analysis_results
        html = "<div style='max-width: 800px'>"
        html += "<h3>Análisis de la Conversación</h3>"
        
        # Intención principal
        html += "<div style='margin-bottom: 10px'>"
        html += "<p style='font-weight: bold; margin-bottom: 5px'>Intención Principal:</p>"
        intent = analysis.get('primary_intent', 'desconocida')
        if intent == 'interes_producto':
            html += "<p style='background-color: #000000; padding: 5px;'>Interés en Productos</p>"
        elif intent == 'interes_servicio':
            html += "<p style='background-color: #000000; padding: 5px;'>Interés en Servicios</p>"
        elif intent == 'consulta_informacion':
            html += "<p style='background-color: #f2f2f2; padding: 5px;'>Consulta de Información</p>"
        elif intent == 'queja':
            html += "<p style='background-color: #000000; padding: 5px;'>Queja o Reclamación</p>"
        else:
            html += f"<p style='background-color: #f2f2f2; padding: 5px;'>{intent}</p>"
        html += "</div>"
        
        # Nivel de interés de compra
        html += "<div style='margin-bottom: 10px'>"
        html += "<p style='font-weight: bold; margin-bottom: 5px'>Nivel de Interés:</p>"
        interest = analysis.get('purchase_interest_level', 'ninguno')
        if interest == 'alto':
            html += "<p style='color: green; font-weight: bold; padding: 5px;'>ALTO</p>"
        elif interest == 'medio':
            html += "<p style='color: orange; font-weight: bold; padding: 5px;'>MEDIO</p>"
        elif interest == 'bajo':
            html += "<p style='color: blue; padding: 5px;'>BAJO</p>"
        else:
            html += "<p style='color: gray; padding: 5px;'>NINGUNO</p>"
        html += "</div>"
        
        # Sentimiento
        html += "<div style='margin-bottom: 10px'>"
        html += "<p style='font-weight: bold; margin-bottom: 5px'>Sentimiento del Usuario:</p>"
        sentiment = analysis.get('user_sentiment', 'neutral')
        if sentiment == 'positivo':
            html += "<p style='color: green; padding: 5px;'>Positivo</p>"
        elif sentiment == 'negativo':
            html += "<p style='color: red; padding: 5px;'>Negativo</p>"
        else:
            html += "<p style='color: gray; padding: 5px;'>Neutral</p>"
        html += "</div>"
        
        # Intereses específicos
        if analysis.get('specific_interests'):
            html += "<div style='margin-bottom: 10px'>"
            html += "<p style='font-weight: bold; margin-bottom: 5px'>Intereses Específicos:</p>"
            html += "<ul style='margin-top: 0px'>"
            for interest in analysis.get('specific_interests', []):
                html += f"<li>{interest}</li>"
            html += "</ul>"
            html += "</div>"
        
        # Información de contacto
        if analysis.get('contact_info', {}).get('value'):
            html += "<div style='margin-bottom: 10px'>"
            html += "<p style='font-weight: bold; margin-bottom: 5px'>Información de Contacto:</p>"
            contact_type = analysis.get('contact_info', {}).get('type', '')
            contact_value = analysis.get('contact_info', {}).get('value', '')
            html += f"<p style='padding: 5px;'>{contact_type}: {contact_value}</p>"
            html += "</div>"
        
        # Seguimiento necesario
        if analysis.get('follow_up_needed'):
            html += "<div style='margin-bottom: 10px'>"
            html += "<p style='font-weight: bold; color: red; margin-bottom: 5px'>SEGUIMIENTO REQUERIDO:</p>"
            html += f"<p style='background-color: #000000; padding: 5px;'>{analysis.get('follow_up_reason', '')}</p>"
            html += "</div>"
        
        # Resumen
        html += "<div style='margin-bottom: 10px'>"
        html += "<p style='font-weight: bold; margin-bottom: 5px'>Resumen:</p>"
        html += f"<p style='background-color: #000000; padding: 10px; border-left: 4px solid #ddd;'>{analysis.get('summary', '')}</p>"
        html += "</div>"
        
        html += "</div>"
        return format_html(html)
    
    user_info.short_description = "Usuario"
    company_name.short_description = "Empresa"
    status.short_description = "Estado"
    duration.short_description = "Duración"
    message_count.short_description = "Mensajes"
    lead_interest.short_description = "Interés"
    analysis_display.short_description = "Análisis de Conversación"

    def analyze_session(self, request, queryset):
        """Acción para analizar manualmente las sesiones seleccionadas"""
        service = ConversationAnalysisService()
        analyzed = 0
        
        for session in queryset:
            analysis = service.analyze_session(session)
            if analysis:
                session.analysis_results = analysis
                session.save()
                analyzed += 1

    analyze_session.short_description = "Analizar conversaciones seleccionadas"
    actions = [analyze_session]

@admin.register(LeadStatistics)
class LeadStatisticsPanel(admin.ModelAdmin):
    change_list_template = 'admin/lead_statistics.html'
    
    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        
        # Obtener estadísticas de intenciones para PostgreSQL
        from django.db import connection
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT 
                    analysis_results_json::json->>'primary_intent' as intent,
                    COUNT(*) as count
                FROM 
                    chatbot_session
                WHERE 
                    analysis_results_json IS NOT NULL
                GROUP BY 
                    intent
                ORDER BY 
                    count DESC
            """)
            intent_stats = cursor.fetchall()
            
        # Obtener estadísticas de nivel de interés para PostgreSQL
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT 
                    analysis_results_json::json->>'purchase_interest_level' as interest,
                    COUNT(*) as count
                FROM 
                    chatbot_session
                WHERE 
                    analysis_results_json IS NOT NULL
                GROUP BY 
                    interest
                ORDER BY 
                    count DESC
            """)
            interest_stats = cursor.fetchall()
        
        # Preparar datos para gráficos
        extra_context['intent_stats'] = intent_stats
        extra_context['interest_stats'] = interest_stats
        
        return super().changelist_view(request, extra_context=extra_context)

@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ('short_text', 'direction', 'user_info', 'company_name', 'session_link', 'created_at')
    list_filter = ('company', 'is_from_user', 'created_at')
    search_fields = ('message_text', 'user__name', 'user__whatsapp_number', 'company__name')
    readonly_fields = ('id', 'created_at', 'session_link')
    
    def short_text(self, obj):
        max_length = 50
        if len(obj.message_text) > max_length:
            return f"{obj.message_text[:max_length]}..."
        return obj.message_text
    
    def direction(self, obj):
        return "Usuario → Bot" if obj.is_from_user else "Bot → Usuario"
    
    def user_info(self, obj):
        if obj.user.name:
            return f"{obj.user.name} ({obj.user.whatsapp_number})"
        return obj.user.whatsapp_number
    
    def company_name(self, obj):
        return obj.company.name
    
    def session_link(self, obj):
        if obj.session:
            url = reverse('admin:chatbot_session_change', args=[obj.session.id])
            return format_html('<a href="{}">{}</a>', url, obj.session.id)
        return "-"
    
    short_text.short_description = "Mensaje"
    direction.short_description = "Dirección"
    user_info.short_description = "Usuario"
    company_name.short_description = "Empresa"
    session_link.short_description = "Sesión"

@admin.register(CompanyInfo)
class CompanyInfoAdmin(admin.ModelAdmin):
    list_display = ('company', 'title', 'created_at', 'updated_at')
    list_filter = ('company',)
    search_fields = ('title', 'content')

@admin.register(Feedback)
class FeedbackAdmin(admin.ModelAdmin):
    list_display = ('user', 'company', 'rating', 'has_comment', 'session_link', 'created_at')
    list_filter = ('rating', 'company', 'created_at')
    search_fields = ('user__name', 'user__whatsapp_number', 'comment', 'company__name')
    readonly_fields = ('session_link',)
    
    def has_comment(self, obj):
        return bool(obj.comment)
    
    def session_link(self, obj):
        if obj.session:
            url = reverse('admin:chatbot_session_change', args=[obj.session.id])
            return format_html('<a href="{}">{}</a>', url, obj.session.id)
        return "-"
    
    has_comment.boolean = True
    has_comment.short_description = "Tiene comentario"
    session_link.short_description = "Sesión"

# Actualizar el PolicyVersionAdmin para manejar cambios de versión

@admin.register(PolicyVersion)
class PolicyVersionAdmin(admin.ModelAdmin):
    list_display = ('version', 'title', 'active', 'created_at', 'acceptance_count')
    list_filter = ('active', 'created_at')
    search_fields = ('title', 'description', 'version')
    readonly_fields = ('acceptance_count', 'created_at')
    
    fieldsets = (
        ("Información Básica", {
            "fields": ("version", "title", "active")
        }),
        ("Contenido", {
            "fields": ("description", "privacy_policy_text", "terms_text")
        }),
        ("Estadísticas", {
            "fields": ("acceptance_count", "created_at")
        })
    )
    
    def acceptance_count(self, obj):
        """Muestra el número de usuarios que han aceptado esta versión"""
        try:
            # Intentar contar aceptaciones si existe el modelo PolicyAcceptance
            count = PolicyAcceptance.objects.filter(policy_version=obj).count()
            return f"{count} usuario(s)"
        except (ImportError, AttributeError):
            # Fallback si no existe el modelo
            users = User.objects.filter(policies_version=obj.version, policies_accepted=True).count()
            return f"{users} usuario(s) [estimado]"
            
    acceptance_count.short_description = "Aceptaciones"
    
    # Al activar una política, desactivar las demás
    def save_model(self, request, obj, form, change):
        # Si se está activando esta política
        if obj.active:
            # Verificar si es una versión nueva (mayor)
            try:
                if change:  # Solo para ediciones, no creaciones nuevas
                    old_obj = self.model.objects.get(pk=obj.pk)
                    
                    # Si estamos cambiando de inactivo a activo
                    if not old_obj.active and obj.active:
                        # Informar al administrador sobre el impacto del cambio
                        old_active = self.model.objects.filter(active=True).first()
                        if old_active:
                            old_version = old_active.version.split('.')
                            new_version = obj.version.split('.')
                            
                            if len(old_version) > 0 and len(new_version) > 0:
                                if int(new_version[0]) > int(old_version[0]):
                                    # Es un cambio mayor, mostrar advertencia
                                    self.message_user(
                                        request, 
                                        f"¡ATENCIÓN! Has activado una versión mayor ({obj.version}). " +
                                        "Los usuarios tendrán que aceptar nuevamente las políticas.", 
                                        level='WARNING'
                                    )
            except Exception as e:
                # Error al comparar versiones, ignorar
                pass
                
            # Desactivar otras versiones
            self.model.objects.exclude(id=obj.pk).update(active=False)
            
        super().save_model(request, obj, form, change)

# Si implementaste PolicyAcceptance, añade esto también:
@admin.register(PolicyAcceptance)
class PolicyAcceptanceAdmin(admin.ModelAdmin):
    list_display = ('user', 'policy_version', 'accepted_at', 'ip_address')
    list_filter = ('accepted_at', 'policy_version')
    search_fields = ('user__name', 'user__whatsapp_number', 'policy_version__version')
    readonly_fields = ('user', 'policy_version', 'accepted_at', 'ip_address', 'user_agent')

from django.contrib import admin
from django.utils.html import format_html
from .models import AudioMessage

@admin.register(AudioMessage)
class AudioMessageAdmin(admin.ModelAdmin):
    list_display = ('id', 'message_info', 'created_at', 'processing_status', 'audio_player', 'short_transcription')
    list_filter = ('processing_status', 'created_at')
    search_fields = ('transcription', 'message__message_text')
    readonly_fields = ('created_at', 'updated_at', 'audio_player', 'full_transcription')
    
    def message_info(self, obj):
        if obj.message:
            return f"{obj.message.user.whatsapp_number} - {obj.message.created_at.strftime('%d/%m/%Y %H:%M')}"
        return "No message"
    
    def audio_player(self, obj):
        if obj.audio_file:
            return format_html(
                '<audio controls style="width:300px"><source src="{}" type="audio/ogg">Tu navegador no soporta audio</audio>',
                obj.audio_file.url
            )
        return "No audio File"
    
    def short_transcription(self, obj):
        if obj.transcription:
            text = obj.transcription[:50]
            if len(obj.transcription) > 50:
                text += "..."
            return text
        return "No transcription"
    
    def full_transcription(self, obj):
        if obj.transcription:
            return obj.transcription
        return "No transcription"
    
    audio_player.short_description = "Player"
    short_transcription.short_description = "Transcription"
    full_transcription.short_description = "Full transcription"
    message_info.short_description = "Message"

def get_app_list_with_openai_dashboard(self, request):
    """Agregar enlace al dashboard de OpenAI en el menú lateral"""
    app_list = admin.AdminSite.get_app_list(self, request)
    
    # Solo para staff/admin
    if request.user.is_staff:
        # Buscar la aplicación chatbot
        for app in app_list:
            if app['app_label'] == 'chatbot':
                # Añadir enlace personalizado
                app['models'].append({
                    'name': 'OpenAI Dashboard',
                    'object_name': 'OpenAIDashboard',
                    'admin_url': '/openai-dashboard/',
                    'view_only': True,
                    'perms': {'view': True}
                })
    
    return app_list

# Aplicar el método a la instancia del sitio de administración
admin.site.get_app_list = get_app_list_with_openai_dashboard.__get__(admin.site)