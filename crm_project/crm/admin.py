from django.contrib import admin
from .models import Client, Deal, Task, Interaction, Product, DealProduct


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ['name', 'contact_person', 'phone', 'email', 'created_at']
    search_fields = ['name', 'contact_person', 'phone', 'email', 'inn']
    list_filter = ['created_at']
    date_hierarchy = 'created_at'

    fieldsets = (
        ('Основная информация', {
            'fields': ('name', 'contact_person')
        }),
        ('Контакты', {
            'fields': ('phone', 'email', 'address')
        }),
        ('Реквизиты', {
            'fields': ('inn',)
        }),
        ('Дополнительно', {
            'fields': ('notes',),
            'classes': ('collapse',)
        }),
    )


class DealProductInline(admin.TabularInline):
    model = DealProduct
    extra = 1
    fields = ['product', 'quantity', 'price', 'total']
    readonly_fields = ['total']


@admin.register(Deal)
class DealAdmin(admin.ModelAdmin):
    list_display = ['title', 'client', 'manager', 'amount', 'status', 'created_at', 'updated_at']
    list_filter = ['status', 'created_at', 'manager']
    search_fields = ['title', 'client__name', 'description']
    date_hierarchy = 'created_at'
    readonly_fields = ['payment_reminder_count', 'created_at', 'updated_at']
    inlines = [DealProductInline]

    fieldsets = (
        ('Основная информация', {
            'fields': ('client', 'manager', 'title', 'description', 'amount')
        }),
        ('Статус', {
            'fields': ('status', 'expected_close_date')
        }),
        ('Напоминания', {
            'fields': ('payment_reminder_count', 'max_payment_reminders'),
            'classes': ('collapse',)
        }),
        ('Системная информация', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ['title', 'deal', 'manager', 'priority', 'due_date', 'is_completed']
    list_filter = ['priority', 'is_completed', 'manager', 'due_date']
    search_fields = ['title', 'description', 'deal__title']
    date_hierarchy = 'due_date'

    fieldsets = (
        ('Задача', {
            'fields': ('deal', 'manager', 'title', 'description')
        }),
        ('Параметры', {
            'fields': ('priority', 'due_date')
        }),
        ('Статус', {
            'fields': ('is_completed', 'completed_at')
        }),
    )


@admin.register(Interaction)
class InteractionAdmin(admin.ModelAdmin):
    list_display = ['client', 'interaction_type', 'manager', 'deal', 'created_at']
    list_filter = ['interaction_type', 'created_at', 'manager']
    search_fields = ['client__name', 'description', 'deal__title']
    date_hierarchy = 'created_at'

    fieldsets = (
        ('Взаимодействие', {
            'fields': ('client', 'deal', 'manager', 'interaction_type')
        }),
        ('Описание', {
            'fields': ('description',)
        }),
    )


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ['article', 'name', 'category', 'price', 'unit', 'in_stock']
    list_filter = ['category', 'in_stock']
    search_fields = ['name', 'article', 'description']

    fieldsets = (
        ('Основная информация', {
            'fields': ('name', 'article', 'category', 'description')
        }),
        ('Цена и наличие', {
            'fields': ('price', 'unit', 'in_stock')
        }),
    )