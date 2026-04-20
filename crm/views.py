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
from .forms import ClientCreateForm


from .forms import (
    ClientLeadForm, EmailLeadForm, DealEditForm,
    DealProductForm, DealAmountForm, TaskCreateForm, TaskEditForm
)


@login_required
def client_create(request):
    """Представление для создания нового клиента"""
    if request.method == 'POST':
        form = ClientCreateForm(request.POST)
        if form.is_valid():
            client = form.save()
            messages.success(request, f'Клиент "{client.name}" успешно создан!')
            return redirect('crm:clients_list')
        else:
            messages.error(request, 'Пожалуйста, исправьте ошибки в форме.')
    else:
        form = ClientCreateForm()

    return render(request, 'crm/client_form.html', {'form': form})


@login_required
def dashboard(request):
    """Главная панель с аналитикой"""
    now = timezone.now()

    # Статистика по сделкам
    total_deals = Deal.objects.count()
    active_deals = Deal.objects.exclude(status__in=['completed', 'cancelled']).count()
    total_amount = Deal.objects.filter(status='paid').aggregate(Sum('amount'))['amount__sum'] or 0

    # Статистика по статусам сделок
    status_dict = dict(Deal.STATUS_CHOICES)
    deals_by_status_raw = Deal.objects.values('status').annotate(count=Count('id')).order_by('status')
    deals_by_status = [
        {
            'status': item['status'],
            'status_display': status_dict.get(item['status'], item['status']),
            'count': item['count'],
        }
        for item in deals_by_status_raw
    ]

    # Задачи текущего пользователя (активные)
    my_tasks = Task.objects.filter(
        manager=request.user,
        is_completed=False
    ).select_related('deal', 'deal__client').order_by('due_date')[:10]

    # Статистика задач по статусам
    task_status_dict = dict(Task.STATUS_CHOICES)
    tasks_by_status_raw = Task.objects.filter(
        manager=request.user
    ).values('status').annotate(count=Count('id'))
    tasks_by_status = [
        {
            'status': item['status'],
            'status_display': task_status_dict.get(item['status'], item['status']),
            'count': item['count'],
        }
        for item in tasks_by_status_raw
    ]

    # Просроченные задачи
    overdue_tasks_count = Task.objects.filter(
        manager=request.user,
        is_completed=False,
        due_date__lt=now
    ).count()

    # Срочные задачи (приоритет urgent или high, не завершены)
    urgent_tasks = Task.objects.filter(
        manager=request.user,
        is_completed=False,
        priority__in=['urgent', 'high']
    ).select_related('deal', 'deal__client').order_by(
        '-priority', 'due_date'
    )

    # Просроченные задачи (список)
    overdue_tasks = Task.objects.filter(
        manager=request.user,
        is_completed=False,
        due_date__lt=now
    ).select_related('deal', 'deal__client').order_by('due_date')

    # Объединяем просроченные и срочные без дублей
    attention_task_ids = set(
        list(urgent_tasks.values_list('id', flat=True)) +
        list(overdue_tasks.values_list('id', flat=True))
    )
    attention_tasks = Task.objects.filter(
        id__in=attention_task_ids
    ).select_related('deal', 'deal__client').order_by('due_date')

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
        'tasks_by_status': tasks_by_status,
        'overdue_tasks_count': overdue_tasks_count,
        'attention_tasks': attention_tasks,
        'recent_interactions': recent_interactions,
        'deals_needing_attention': deals_needing_attention,
        'now': now,
    }
    return render(request, 'crm/dashboard.html', context)


@login_required
def tasks_list(request):
    """Список задач менеджера"""
    show_completed = request.GET.get('completed', 'false') == 'true'
    status_filter = request.GET.get('status', '')
    priority_filter = request.GET.get('priority', '')

    tasks = Task.objects.filter(manager=request.user)

    if not show_completed:
        tasks = tasks.filter(is_completed=False)

    if status_filter:
        tasks = tasks.filter(status=status_filter)

    if priority_filter:
        tasks = tasks.filter(priority=priority_filter)

    tasks = tasks.select_related('deal', 'deal__client').order_by(
        'is_completed', 'due_date'
    )

    context = {
        'tasks': tasks,
        'show_completed': show_completed,
        'status_filter': status_filter,
        'priority_filter': priority_filter,
        'status_choices': Task.STATUS_CHOICES,
        'priority_choices': Task.PRIORITY_CHOICES,
    }
    return render(request, 'crm/tasks_list.html', context)


@login_required
def task_create(request):
    """Создание новой задачи"""
    deal_pk = request.GET.get('deal')

    if request.method == 'POST':
        form = TaskCreateForm(request.POST, user=request.user)
        if form.is_valid():
            task = form.save(commit=False)
            task.manager = request.user
            task.save()
            messages.success(request, f'Задача "{task.title}" создана!')

            # Возвращаемся к сделке если создавали из неё
            if task.deal:
                return redirect('crm:deal_detail', pk=task.deal.id)
            return redirect('crm:tasks_list')
    else:
        initial = {}
        if deal_pk:
            initial['deal'] = deal_pk
        form = TaskCreateForm(user=request.user, initial=initial)

    context = {
        'form': form,
        'title': 'Создать задачу',
    }
    return render(request, 'crm/task_form.html', context)


@login_required
def task_detail(request, pk):
    """Детальная информация о задаче"""
    task = get_object_or_404(
        Task.objects.select_related('deal', 'deal__client', 'manager'),
        pk=pk,
        manager=request.user
    )
    context = {
        'task': task,
    }
    return render(request, 'crm/task_detail.html', context)


@login_required
def task_edit(request, pk):
    """Редактирование задачи"""
    task = get_object_or_404(Task, pk=pk, manager=request.user)

    if request.method == 'POST':
        form = TaskEditForm(request.POST, instance=task)
        if form.is_valid():
            form.save()
            messages.success(request, f'Задача "{task.title}" обновлена!')
            return redirect('crm:task_detail', pk=task.id)
    else:
        # Форматируем дату для datetime-local input
        initial = {}
        if task.due_date:
            initial['due_date'] = task.due_date.strftime('%Y-%m-%dT%H:%M')
        form = TaskEditForm(instance=task, initial=initial)

    context = {
        'form': form,
        'task': task,
        'title': 'Редактировать задачу',
    }
    return render(request, 'crm/task_form.html', context)


@login_required
def tasks_list(request):
    """Список задач менеджера"""
    show_completed = request.GET.get('completed', 'false') == 'true'
    status_filter = request.GET.get('status', '')
    priority_filter = request.GET.get('priority', '')

    tasks = Task.objects.filter(manager=request.user)

    if not show_completed:
        tasks = tasks.exclude(status__in=['completed', 'cancelled'])

    if status_filter:
        tasks = tasks.filter(status=status_filter)

    if priority_filter:
        tasks = tasks.filter(priority=priority_filter)

    tasks = tasks.select_related('deal', 'deal__client').order_by(
        'is_completed', 'due_date'
    )

    context = {
        'tasks': tasks,
        'show_completed': show_completed,
        'status_filter': status_filter,
        'priority_filter': priority_filter,
        'status_choices': Task.STATUS_CHOICES,
        'priority_choices': Task.PRIORITY_CHOICES,
        'now': timezone.now(),
    }
    return render(request, 'crm/tasks_list.html', context)

@login_required
def task_change_status(request, pk, new_status):
    """Быстрая смена статуса задачи"""
    task = get_object_or_404(Task, pk=pk, manager=request.user)

    valid_statuses = [choice[0] for choice in Task.STATUS_CHOICES]
    if new_status in valid_statuses:
        old_status = task.get_status_display()
        task.status = new_status
        task.save()
        messages.success(request, f'Статус задачи изменён: "{old_status}" → "{task.get_status_display()}"')
    else:
        messages.error(request, 'Недопустимый статус!')

    # Возвращаемся туда откуда пришли
    next_url = request.GET.get('next', '')
    if next_url:
        return redirect(next_url)
    return redirect('crm:task_detail', pk=task.id)


from .forms import ClientLeadForm, EmailLeadForm, DealEditForm, DealProductForm, DealAmountForm


@login_required
def deal_change_amount(request, pk):
    """Быстрое изменение суммы сделки"""
    deal = get_object_or_404(Deal, pk=pk)

    if request.method == 'POST':
        form = DealAmountForm(request.POST, instance=deal)
        if form.is_valid():
            old_amount = Deal.objects.get(pk=pk).amount
            form.save()

            # Создаем запись о взаимодействии
            Interaction.objects.create(
                client=deal.client,
                deal=deal,
                manager=request.user,
                interaction_type='note',
                description=f"Сумма сделки изменена: {old_amount} ₽ → {deal.amount} ₽"
            )

            messages.success(request, f'Сумма сделки изменена на {deal.amount} ₽')
            return redirect('crm:deal_detail', pk=deal.id)
    else:
        form = DealAmountForm(instance=deal)

    context = {
        'form': form,
        'deal': deal,
    }
    return render(request, 'crm/deal_change_amount.html', context)


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

    # Проверяем, есть ли товары вообще
    if not Product.objects.filter(in_stock=True).exists():
        messages.warning(request, 'Нет доступных товаров. Сначала добавьте товары в справочник.')
        return redirect('crm:deal_detail', pk=deal.id)

    if request.method == 'POST':
        form = DealProductForm(request.POST)
        if form.is_valid():
            deal_product = form.save(commit=False)
            deal_product.deal = deal

            # Если цена не была указана, берём из товара
            if not deal_product.price:
                deal_product.price = deal_product.product.price

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
            messages.error(request, 'Исправьте ошибки в форме.')
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