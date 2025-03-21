from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html
from django.http import HttpResponseRedirect
from .models import *
from .services.feedback_service import FeedbackService

# Inicializar servicio de feedback
feedback_service = FeedbackService()

class CompanyInfoInline(admin.TabularInline):
    model = CompanyInfo
    extra = 1

@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ('name', 'phone_number', 'active', 'created_at', 'feedback_summary')
    search_fields = ('name', 'phone_number')
    list_filter = ('active', 'created_at')
    inlines = [CompanyInfoInline]
    
    fieldsets = (
        ("Información Básica", {
            "fields": ("name", "active")
        }),
        ("WhatsApp API", {
            "fields": ("whatsapp_phone_number_id", "phone_number", "whatsapp_api_token")
        }),
        ("Estadísticas de Feedback", {
            "fields": ("feedback_detailed_stats",)
        })
    )
    
    readonly_fields = ('feedback_detailed_stats',)
    
    def feedback_summary(self, obj):
        """Muestra un resumen del feedback de la empresa"""
        stats = feedback_service.get_cached_feedback_stats(obj, days=30)
        
        if "error" in stats:
            return "Error al cargar stats"
        
        if stats["total"] == 0:
            return "Sin feedback"
            
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
        
        neutral_bar = self._create_progress_bar(
            stats["neutral_percent"], 
            "gray", 
            f"{stats['neutral']} ({stats['neutral_percent']}%)"
        )
        
        # Formatear el resultado con HTML
        return format_html(
            '<div style="font-size: 0.9em;">'
            'Total: <strong>{}</strong><br>'
            'Positivos: {}<br>'
            'Negativos: {}<br>'
            'Neutral: {}'
            '</div>',
            stats["total"],
            positive_bar,
            negative_bar,
            neutral_bar
        )
    
    def _create_progress_bar(self, percentage, color, text):
        """Crea una barra de progreso HTML"""
        return format_html(
            '<div style="display: flex; align-items: center; gap: 5px;">'
            '<div style="flex-grow: 1; background-color: #eee; border-radius: 3px; height: 10px;">'
            '<div style="width: {}%; background-color: {}; height: 100%; border-radius: 3px;"></div>'
            '</div>'
            '<div style="min-width: 80px;">{}</div>'
            '</div>',
            percentage, color, text
        )
        
    def feedback_detailed_stats(self, obj):
        """Muestra estadísticas detalladas de feedback"""
        # Añadir botón para refrescar estadísticas
        refresh_url = reverse('admin:company_refresh_stats', args=[obj.pk])
        refresh_button = f'<a href="{refresh_url}" class="button">Actualizar estadísticas</a>'
        
        # Obtener estadísticas para diferentes períodos
        last_7 = feedback_service.get_cached_feedback_stats(obj, days=7)
        last_30 = feedback_service.get_cached_feedback_stats(obj, days=30)
        last_90 = feedback_service.get_cached_feedback_stats(obj, days=90)
        
        # Crear gráficos con datos de diferentes períodos
        html = '<div style="max-width: 600px;">'
        html += f'<div style="margin-bottom: 10px;">{refresh_button}</div>'
        
        html += '<h3>Resumen de Feedback</h3>'
        html += '<table style="width: 100%; border-collapse: collapse;">'
        html += '<tr style="background-color: #000;"><th>Período</th><th>Total</th><th>👍 Positivos</th><th>👎 Negativos</th><th>💬 Con comentarios</th></tr>'
        
        # Últimos 7 días
        html += self._create_stats_row('Últimos 7 días', last_7)
        # Últimos 30 días
        html += self._create_stats_row('Últimos 30 días', last_30)
        # Últimos 90 días
        html += self._create_stats_row('Últimos 90 días', last_90)
        
        html += '</table>'
        
        # Agregar visualización de últimos comentarios
        html += self._get_recent_comments_html(obj)
        
        html += '</div>'
        
        return format_html(html)
    
    def _create_stats_row(self, label, stats):
        """Crea una fila de tabla con estadísticas"""
        if stats.get("total", 0) == 0:
            return f'<tr><td>{label}</td><td colspan="4" style="text-align: center;">Sin datos</td></tr>'
        
        return f'''
            <tr>
                <td>{label}</td>
                <td style="text-align: center;">{stats["total"]}</td>
                <td style="text-align: center;">{stats["positive"]} ({stats["positive_percent"]}%)</td>
                <td style="text-align: center;">{stats["negative"]} ({stats["negative_percent"]}%)</td>
                <td style="text-align: center;">{stats["comment"]} ({stats["comment_percent"]}%)</td>
            </tr>
        '''
    
    def _get_recent_comments_html(self, obj):
        """Obtiene HTML con comentarios recientes"""
        # Obtener los 5 comentarios más recientes
        recent_comments = Feedback.objects.filter(
            company=obj, 
            comment__isnull=False
        ).exclude(
            comment=""
        ).order_by(
            '-created_at'
        )[:5]
        
        if not recent_comments:
            return '<p><em>No hay comentarios recientes.</em></p>'
        
        html = '<h3>Comentarios Recientes</h3>'
        html += '<div style="max-height: 300px; overflow-y: auto;">'
        
        for feedback in recent_comments:
            rating_emoji = "👍" if feedback.rating == "positive" else "👎" if feedback.rating == "negative" else "🗣️"
            date_str = feedback.created_at.strftime("%d/%m/%Y %H:%M")
            user_name = feedback.user.name or feedback.user.whatsapp_number
            
            html += f'''
                <div style="margin-bottom: 10px; padding: 10px; border-left: 4px solid #ddd;">
                    <p style="margin: 0 0 5px 0;"><strong>{rating_emoji} {user_name}</strong> <span style="color: #777;">{date_str}</span></p>
                    <p style="margin: 0;">{feedback.comment}</p>
                </div>
            '''
        
        html += '</div>'
        return html
    
    feedback_summary.short_description = "Feedback (30 días)"
    feedback_summary.allow_tags = True
    feedback_detailed_stats.short_description = "Estadísticas de Feedback"
    
    def get_urls(self):
        from django.urls import path
        urls = super().get_urls()
        custom_urls = [
            path('<uuid:pk>/refresh_stats/', self.admin_site.admin_view(self.refresh_stats_view), name='company_refresh_stats'),
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
        from django.contrib import messages
        messages.success(request, "Estadísticas de feedback actualizadas correctamente")
        return HttpResponseRedirect(f"../")

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
    list_display = ('id', 'user_info', 'company_name', 'started_at', 'status', 'duration', 'message_count')
    list_filter = ('company', 'started_at', 'ended_at')
    search_fields = ('user__name', 'user__whatsapp_number', 'company__name')
    inlines = [MessageInline]
    
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
    
    user_info.short_description = "Usuario"
    company_name.short_description = "Empresa"
    status.short_description = "Estado"
    duration.short_description = "Duración"
    message_count.short_description = "Mensajes"

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
