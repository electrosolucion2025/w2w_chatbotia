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
    list_display = ('id', 'user', 'company', 'started_at', 'ended_at')
    list_filter = ('company', 'started_at')
    search_fields = ('user__name', 'user__whatsapp_number')

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
