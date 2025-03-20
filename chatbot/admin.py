from django.contrib import admin
from .models import Company, CompanyInfo, User, Session, Message

class CompanyInfoInline(admin.TabularInline):
    model = CompanyInfo
    extra = 1

@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ('name', 'phone_number', 'active', 'created_at')
    search_fields = ('name', 'phone_number')
    list_filter = ('active', 'created_at')
    inlines = [CompanyInfoInline]
    
    fieldsets = (
        ('Información Básica', {
            'fields': ('name', 'phone_number', 'active')
        }),
        ('Configuración de WhatsApp', {
            'fields': ('whatsapp_api_token', 'whatsapp_phone_number_id'),
        }),
    )

@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ('name', 'whatsapp_number', 'company', 'created_at')
    list_filter = ('company',)
    search_fields = ('name', 'whatsapp_number')

@admin.register(Session)
class SessionAdmin(admin.ModelAdmin):
    list_display = ('id', 'company', 'user', 'started_at', 'ended_at')
    list_filter = ('company', 'started_at')

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
