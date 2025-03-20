from django.contrib import admin
from .models import Company, CompanyInfo, User, UserCompanyInteraction, Session, Message

class CompanyInfoInline(admin.TabularInline):
    model = CompanyInfo
    extra = 1

@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ('name', 'phone_number', 'active', 'created_at')
    search_fields = ('name', 'phone_number')
    list_filter = ('active', 'created_at')
    inlines = [CompanyInfoInline]

class UserCompanyInteractionInline(admin.TabularInline):
    model = UserCompanyInteraction
    extra = 0
    readonly_fields = ('first_interaction', 'last_interaction')

@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ('name', 'whatsapp_number', 'created_at')
    search_fields = ('name', 'whatsapp_number')
    inlines = [UserCompanyInteractionInline]

@admin.register(UserCompanyInteraction)
class UserCompanyInteractionAdmin(admin.ModelAdmin):
    list_display = ('user', 'company', 'first_interaction', 'last_interaction')
    list_filter = ('company', 'first_interaction', 'last_interaction')
    search_fields = ('user__name', 'user__whatsapp_number', 'company__name')

@admin.register(Session)
class SessionAdmin(admin.ModelAdmin):
    list_display = ('id', 'user_info', 'company', 'started_at', 'last_activity', 'status', 'duration')
    list_filter = ('company', 'started_at', 'ended_at')
    search_fields = ('user__name', 'user__whatsapp_number')
    
    def user_info(self, obj):
        if obj.user.name:
            return f"{obj.user.name} ({obj.user.whatsapp_number})"
        return obj.user.whatsapp_number
    
    def status(self, obj):
        return "Activa" if obj.ended_at is None else "Finalizada"
    
    def duration(self, obj):
        end = obj.ended_at or timezone.now()
        delta = end - obj.started_at
        minutes = delta.seconds // 60
        
        if minutes < 60:
            return f"{minutes} min"
        
        hours = minutes // 60
        minutes = minutes % 60
        return f"{hours}h {minutes}m"
    
    user_info.short_description = "Usuario"
    status.short_description = "Estado"
    duration.short_description = "Duración"

@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ('get_short_message', 'company', 'user', 'is_from_user', 'created_at')
    list_filter = ('company', 'is_from_user', 'created_at')
    search_fields = ('message_text',)
    
    def get_short_message(self, obj):
        return obj.message_text[:50] + ('...' if len(obj.message_text) > 50 else '')
    get_short_message.short_description = 'Message'

@admin.register(CompanyInfo)
class CompanyInfoAdmin(admin.ModelAdmin):
    list_display = ('company', 'title', 'created_at', 'updated_at')
    list_filter = ('company',)
    search_fields = ('title', 'content')
