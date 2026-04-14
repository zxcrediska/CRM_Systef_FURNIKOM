from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Count, Q
from django.utils import timezone
from django.contrib import messages
from django.contrib.auth.models import User
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from datetime import timedelta
import json

from .models import Client, Deal, Task, Interaction, Product, DealProduct
from .forms import ClientLeadForm, EmailLeadForm, DealEditForm, DealProductForm


@login_required
def dashboard(request):
    """Главная панель с аналитикой"""
    # Статистика по сделкам
    total_deals = Deal.objects.count()
    active_deals = Deal.objects.exclude(status__in=['completed', 'cancelled']).count()
    total_amount = Deal.objects.filter(status='paid').aggregate(Sum('amount'))['amount__sum'] or 0

    # Статистика по статусам
    deals_by_status = Deal.objects.values('status').annotate(count=Count('id'))

    # Задачи текущего пользователя
    my_tasks = Task.objects.filter(
        manager=request.user,
        is_completed=False
    ).select_related('deal', 'deal__client').order_by('due_date')[:10]

    # Просроченные задачи
    overdue_tasks = Task.objects.filter(
        manager=request.user,
        is_completed=False,
        due_date__lt=timezone.now()
    ).count()

    # Последние взаимодействия
    recent_interactions = Interaction.objects.filter(
        manager=request.user
    ).select_related('client', 'deal').order_by('-created_at')[:10]

    # Сделки, требующие внимания
    deals_needing_attention = Deal.objects.filter(
        manager=request.user,
        status='waiting_payment',
        payment_reminder_count__lt=3
    ).count()

    context = {
        'total_deals': total_deals,
        'active_deals': active_deals,
        'total_amount': total_amount,
        'deals_by_status': deals_by_status,
        'my_tasks': my_tasks,
        'overdue_tasks': overdue_tasks,
        'recent_interactions': recent_interactions,
        'deals_needing_attention': deals_needing_attention,
    }
    return render(request, 'crm/dashboard.html', context)


@login_required
def deals_list(request):
    """Список всех сделок (Канбан-доска)"""
    # Группировка сделок по статусам
    deals_by_status = {}

    for status_code, status_name in Deal.STATUS_CHOICES:
        deals = Deal.objects.filter(
            status=status_code
        ).select_related('client', 'manager').prefetch_related('products')

        deals_by_status[status_name] = {
            'code': status_code,
            'deals': deals,
            'count': deals.count()
        }

    context = {
        'deals_by_status': deals_by_status,
    }
    return render(request, 'crm/deals_kanban.html', context)


@login_required
def deal_detail(request, pk):
    """Детальная информация о сделке"""
    deal = get_object_or_404(
        Deal.objects.select_related('client', 'manager').prefetch_related(
            'tasks', 'interactions', 'products__product'
        ),
        pk=pk
    )

    tasks = deal.tasks.all().order_by('-is_completed', 'due_date')
    interactions = deal.interactions.select_related('manager').order_by('-created_at')
    products = deal.products.select_related('product').all()

    context = {
        'deal': deal,
        'tasks': tasks,
        'interactions': interactions,
        'products': products,
    }
    return render(request, 'crm/deal_detail.html', context)


@login_required
def deal_edit(request, pk):
    """Редактирование сделки"""
    deal = get_object_or_404(Deal, pk=pk)

    if request.method == 'POST':
        form = DealEditForm(request.POST, instance=deal)
        if form.is_valid():
            form.save()

            # Создаем запись о взаимодействии
            Interaction.objects.create(
                client=deal.client,
                deal=deal,
                manager=request.user,
                interaction_type='note',
                description=f"Сделка обновлена. Новая сумма: {deal.amount} ₽, Статус: {deal.get_status_display()}"
            )

            messages.success(request, 'Сделка успешно обновлена!')
            return redirect('crm:deal_detail', pk=deal.id)
    else:
        form = DealEditForm(instance=deal)

    context = {
        'form': form,
        'deal': deal,
    }
    return render(request, 'crm/deal_edit.html', context)


@login_required
def deal_add_product(request, pk):
    """Добавление товара в сделку"""
    deal = get_object_or_404(Deal, pk=pk)

    if request.method == 'POST':
        form = DealProductForm(request.POST)
        if form.is_valid():
            deal_product = form.save(commit=False)
            deal_product.deal = deal
            deal_product.save()

            # Пересчитываем общую сумму сделки
            total_amount = deal.products.aggregate(
                total=Sum('total')
            )['total'] or 0
            deal.amount = total_amount
            deal.save()

            messages.success(request, f'Товар "{deal_product.product.name}" добавлен в сделку!')
            return redirect('crm:deal_detail', pk=deal.id)
    else:
        form = DealProductForm()

    context = {
        'form': form,
        'deal': deal,
    }
    return render(request, 'crm/deal_add_product.html', context)


@login_required
def deal_remove_product(request, pk, product_pk):
    """Удаление товара из сделки"""
    deal = get_object_or_404(Deal, pk=pk)
    deal_product = get_object_or_404(DealProduct, pk=product_pk, deal=deal)

    product_name = deal_product.product.name
    deal_product.delete()

    # Пересчитываем общую сумму сделки
    total_amount = deal.products.aggregate(
        total=Sum('total')
    )['total'] or 0
    deal.amount = total_amount
    deal.save()

    messages.success(request, f'Товар "{product_name}" удален из сделки!')
    return redirect('crm:deal_detail', pk=deal.id)


@login_required
def deal_change_status(request, pk, new_status):
    """Быстрая смена статуса сделки"""
    deal = get_object_or_404(Deal, pk=pk)

    # Проверяем, что статус валидный
    valid_statuses = [choice[0] for choice in Deal.STATUS_CHOICES]
    if new_status in valid_statuses:
        old_status = deal.get_status_display()
        deal.status = new_status
        deal.save()

        # Создаем запись о взаимодействии
        Interaction.objects.create(
            client=deal.client,
            deal=deal,
            manager=request.user,
            interaction_type='note',
            description=f"Статус изменен: {old_status} → {deal.get_status_display()}"
        )

        messages.success(request, f'Статус изменен на "{deal.get_status_display()}"')
    else:
        messages.error(request, 'Недопустимый статус!')

    return redirect('crm:deal_detail', pk=deal.id)


@login_required
def clients_list(request):
    """Список клиентов"""
    search_query = request.GET.get('search', '')

    clients = Client.objects.all()

    if search_query:
        clients = clients.filter(
            Q(name__icontains=search_query) |
            Q(contact_person__icontains=search_query) |
            Q(phone__icontains=search_query) |
            Q(email__icontains=search_query)
        )

    clients = clients.annotate(
        deals_count=Count('deals')
    ).order_by('-created_at')

    context = {
        'clients': clients,
        'search_query': search_query,
    }
    return render(request, 'crm/clients_list.html', context)


@login_required
def client_detail(request, pk):
    """Детальная информация о клиенте"""
    client = get_object_or_404(
        Client.objects.prefetch_related('deals', 'interactions'),
        pk=pk
    )

    deals = client.deals.select_related('manager').order_by('-created_at')
    interactions = client.interactions.select_related('manager', 'deal').order_by('-created_at')

    context = {
        'client': client,
        'deals': deals,
        'interactions': interactions,
    }
    return render(request, 'crm/client_detail.html', context)


@login_required
def tasks_list(request):
    """Список задач менеджера"""
    show_completed = request.GET.get('completed', 'false') == 'true'

    tasks = Task.objects.filter(manager=request.user)

    if not show_completed:
        tasks = tasks.filter(is_completed=False)

    tasks = tasks.select_related('deal', 'deal__client').order_by(
        'is_completed', 'due_date'
    )

    context = {
        'tasks': tasks,
        'show_completed': show_completed,
    }
    return render(request, 'crm/tasks_list.html', context)


def public_lead_form(request):
    """Публичная форма для регистрации заявок (доступна без авторизации)"""
    if request.method == 'POST':
        form = ClientLeadForm(request.POST)
        if form.is_valid():
            # Создаем или получаем клиента
            client, created = Client.objects.get_or_create(
                phone=form.cleaned_data['phone'],
                defaults={
                    'name': form.cleaned_data['company_name'],
                    'contact_person': form.cleaned_data['contact_person'],
                    'email': form.cleaned_data['email'],
                }
            )

            # Если клиент уже существовал, обновляем данные
            if not created:
                client.name = form.cleaned_data['company_name']
                client.contact_person = form.cleaned_data['contact_person']
                if form.cleaned_data['email']:
                    client.email = form.cleaned_data['email']
                client.save()

            # Назначаем менеджера (берем первого активного пользователя)
            default_manager = User.objects.filter(is_active=True, is_staff=True).first()

            # Создаем сделку
            deal = Deal.objects.create(
                client=client,
                manager=default_manager,
                title=form.cleaned_data['deal_title'],
                description=f"Источник: {dict(form.fields['source'].choices)[form.cleaned_data['source']]}\n\n{form.cleaned_data['description']}",
                status='new',
                amount=0,
            )

            # Создаем запись о взаимодействии
            Interaction.objects.create(
                client=client,
                deal=deal,
                manager=default_manager,
                interaction_type='note',
                description=f"Новая заявка через веб-форму:\n{form.cleaned_data['description']}"
            )

            # Создаем задачу для менеджера
            Task.objects.create(
                deal=deal,
                manager=default_manager,
                title=f"Обработать новую заявку от {client.name}",
                description=f"Связаться с клиентом по телефону {client.phone}",
                priority='high',
                due_date=timezone.now() + timedelta(hours=2),
                is_completed=False
            )

            return render(request, 'crm/lead_success.html', {
                'company_name': client.name
            })
    else:
        form = ClientLeadForm()

    return render(request, 'crm/public_lead_form.html', {'form': form})


@login_required
def create_lead_from_email(request):
    """Создание заявки из email (для менеджеров)"""
    if request.method == 'POST':
        form = EmailLeadForm(request.POST)
        if form.is_valid():
            # Ищем или создаем клиента по email
            client, created = Client.objects.get_or_create(
                email=form.cleaned_data['sender_email'],
                defaults={
                    'name': form.cleaned_data['sender_name'],
                    'contact_person': form.cleaned_data['sender_name'],
                    'phone': form.cleaned_data.get('phone', 'Не указан'),
                }
            )

            # Создаем сделку
            deal = Deal.objects.create(
                client=client,
                manager=request.user,
                title=form.cleaned_data['subject'],
                description=form.cleaned_data['body'],
                status='new',
                amount=0,
            )

            # Создаем запись о взаимодействии
            Interaction.objects.create(
                client=client,
                deal=deal,
                manager=request.user,
                interaction_type='email',
                description=form.cleaned_data['body']
            )

            messages.success(request, f'Заявка от {client.name} успешно создана!')
            return redirect('crm:deal_detail', pk=deal.id)
    else:
        form = EmailLeadForm()

    return render(request, 'crm/create_lead_from_email.html', {'form': form})


@csrf_exempt
def api_create_lead(request):
    """API для создания заявки из внешних источников (Telegram, WhatsApp)"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)

            # Валидация обязательных полей
            required_fields = ['name', 'phone', 'message']
            if not all(field in data for field in required_fields):
                return JsonResponse({
                    'status': 'error',
                    'message': 'Отсутствуют обязательные поля: name, phone, message'
                }, status=400)

            # Создаем или получаем клиента
            client, created = Client.objects.get_or_create(
                phone=data['phone'],
                defaults={
                    'name': data.get('company_name', data['name']),
                    'contact_person': data['name'],
                    'email': data.get('email', ''),
                }
            )

            # Назначаем менеджера
            default_manager = User.objects.filter(is_active=True, is_staff=True).first()

            # Определяем источник
            source = data.get('source', 'api')
            interaction_type_map = {
                'telegram': 'telegram',
                'whatsapp': 'whatsapp',
                'api': 'note',
            }

            # Создаем сделку
            deal = Deal.objects.create(
                client=client,
                manager=default_manager,
                title=data.get('subject', f"Заявка от {client.name}"),
                description=f"Источник: {source}\n\n{data['message']}",
                status='new',
                amount=0,
            )

            # Создаем запись о взаимодействии
            Interaction.objects.create(
                client=client,
                deal=deal,
                manager=default_manager,
                interaction_type=interaction_type_map.get(source, 'note'),
                description=data['message']
            )

            # Создаем задачу
            Task.objects.create(
                deal=deal,
                manager=default_manager,
                title=f"Обработать заявку из {source}: {client.name}",
                description=f"Связаться с клиентом по телефону {client.phone}",
                priority='high',
                due_date=timezone.now() + timedelta(hours=2),
            )

            return JsonResponse({
                'status': 'success',
                'deal_id': deal.id,
                'message': 'Заявка успешно создана'
            })

        except json.JSONDecodeError:
            return JsonResponse({
                'status': 'error',
                'message': 'Неверный формат JSON'
            }, status=400)
        except Exception as e:
            return JsonResponse({
                'status': 'error',
                'message': str(e)
            }, status=500)

    return JsonResponse({
        'status': 'error',
        'message': 'Метод не поддерживается'
    }, status=405)