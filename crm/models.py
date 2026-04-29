from django.db import models
from django.contrib.auth.models import User


class Client(models.Model):
    """Модель клиента"""
    name = models.CharField('Название компании', max_length=200)
    contact_person = models.CharField('Контактное лицо', max_length=100)
    phone = models.CharField('Телефон', max_length=20)
    email = models.EmailField('Email', blank=True)
    address = models.CharField('Адрес', max_length=300, blank=True)
    inn = models.CharField('ИНН', max_length=12, blank=True)
    created_at = models.DateTimeField('Дата создания', auto_now_add=True)
    notes = models.TextField('Примечания', blank=True)

    class Meta:
        verbose_name = 'Клиент'
        verbose_name_plural = 'Клиенты'
        ordering = ['-created_at']

    def __str__(self):
        return self.name


class Deal(models.Model):
    """Модель сделки"""
    STATUS_CHOICES = [
        ('new', 'Новая заявка'),
        ('processing', 'В обработке'),
        ('offer_sent', 'Отправлено КП'),
        ('negotiation', 'Согласование'),
        ('waiting_payment', 'Ожидание оплаты'),
        ('paid', 'Оплачена'),
        ('in_production', 'В производстве'),
        ('ready', 'Готова к отгрузке'),
        ('completed', 'Завершена'),
        ('cancelled', 'Отменена'),
    ]

    client = models.ForeignKey(
        Client,
        on_delete=models.CASCADE,
        verbose_name='Клиент',
        related_name='deals'
    )
    manager = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        verbose_name='Менеджер',
        related_name='managed_deals'
    )
    title = models.CharField('Название сделки', max_length=200)
    description = models.TextField('Описание', blank=True)
    amount = models.DecimalField('Сумма', max_digits=12, decimal_places=2, default=0)
    status = models.CharField('Статус', max_length=20, choices=STATUS_CHOICES, default='new')

    created_at = models.DateTimeField('Дата создания', auto_now_add=True)
    updated_at = models.DateTimeField('Дата обновления', auto_now=True)

    payment_reminder_count = models.IntegerField('Количество напоминаний об оплате', default=0)
    max_payment_reminders = models.IntegerField('Максимум напоминаний', default=3)

    expected_close_date = models.DateField('Ожидаемая дата закрытия', null=True, blank=True)

    class Meta:
        verbose_name = 'Сделка'
        verbose_name_plural = 'Сделки'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.title} - {self.client.name}"

    def can_send_reminder(self):
        """Проверка, можно ли отправить напоминание"""
        return self.payment_reminder_count < self.max_payment_reminders


class Task(models.Model):
    """Модель задачи для менеджера"""
    PRIORITY_CHOICES = [
        ('low', 'Низкий'),
        ('medium', 'Средний'),
        ('high', 'Высокий'),
        ('urgent', 'Срочно'),
    ]

    STATUS_CHOICES = [
        ('new', 'Новая'),
        ('in_progress', 'В работе'),
        ('waiting', 'Ожидание'),
        ('completed', 'Выполнена'),
        ('cancelled', 'Отменена'),
    ]

    deal = models.ForeignKey(
        Deal,
        on_delete=models.CASCADE,
        verbose_name='Сделка',
        related_name='tasks'
    )
    manager = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        verbose_name='Ответственный'
    )
    title = models.CharField('Название задачи', max_length=200)
    description = models.TextField('Описание', blank=True)
    priority = models.CharField('Приоритет', max_length=10, choices=PRIORITY_CHOICES, default='medium')
    status = models.CharField('Статус', max_length=20, choices=STATUS_CHOICES, default='new')
    due_date = models.DateTimeField('Срок выполнения')
    is_completed = models.BooleanField('Выполнена', default=False)
    completed_at = models.DateTimeField('Дата выполнения', null=True, blank=True)
    created_at = models.DateTimeField('Дата создания', auto_now_add=True)

    class Meta:
        verbose_name = 'Задача'
        verbose_name_plural = 'Задачи'
        ordering = ['is_completed', 'due_date']

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        # Синхронизируем is_completed со статусом
        if self.status == 'completed':
            self.is_completed = True
            if not self.completed_at:
                from django.utils import timezone
                self.completed_at = timezone.now()
        elif self.status == 'cancelled':
            self.is_completed = True
        else:
            self.is_completed = False
            self.completed_at = None
        super().save(*args, **kwargs)


class Interaction(models.Model):
    """История взаимодействий с клиентом"""
    INTERACTION_TYPES = [
        ('call_in', 'Входящий звонок'),
        ('call_out', 'Исходящий звонок'),
        ('email', 'Email'),
        ('meeting', 'Встреча'),
        ('note', 'Заметка'),
        ('whatsapp', 'WhatsApp'),
        ('telegram', 'Telegram'),
    ]

    client = models.ForeignKey(
        Client,
        on_delete=models.CASCADE,
        verbose_name='Клиент',
        related_name='interactions'
    )
    deal = models.ForeignKey(
        Deal,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='Сделка',
        related_name='interactions'
    )
    manager = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        verbose_name='Менеджер'
    )
    interaction_type = models.CharField('Тип взаимодействия', max_length=20, choices=INTERACTION_TYPES)
    description = models.TextField('Описание')
    created_at = models.DateTimeField('Дата', auto_now_add=True)

    class Meta:
        verbose_name = 'Взаимодействие'
        verbose_name_plural = 'История взаимодействий'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.get_interaction_type_display()} - {self.client.name} ({self.created_at.strftime('%d.%m.%Y %H:%M')})"


class Product(models.Model):
    """Модель товара/услуги для торгово-производственного предприятия"""
    CATEGORY_CHOICES = [
        ('furniture_hardware', 'Фурнитура для корпусной мебели'),
        ('soft_furniture', 'Комплектующие для мягкой мебели'),
        ('materials', 'Материалы и полуфабрикаты'),
        ('fasteners', 'Крепёжные изделия'),
        ('profiles', 'Профильные изделия'),
        ('mattress', 'Матрасные комплектующие'),
    ]

    name = models.CharField('Название', max_length=200)
    article = models.CharField('Артикул', max_length=50, unique=True)
    category = models.CharField('Категория', max_length=30, choices=CATEGORY_CHOICES)
    description = models.TextField('Описание', blank=True)
    price = models.DecimalField('Цена', max_digits=10, decimal_places=2)
    unit = models.CharField('Единица измерения', max_length=20, default='шт.')
    stock_quantity = models.DecimalField(
        'Количество на складе',
        max_digits=10,
        decimal_places=2,
        default=0.00,
        help_text='Укажите точное количество товара на складе.'
    )
    in_stock = models.BooleanField('В наличии (быстрый доступ)', default=True, editable=False)
    created_at = models.DateTimeField('Дата добавления', auto_now_add=True)

    class Meta:
        verbose_name = 'Товар'
        verbose_name_plural = 'Товары'
        ordering = ['category', 'name']

    def __str__(self):
        return f"{self.article} - {self.name}"




class DealProduct(models.Model):
    """Связь между сделкой и товарами"""
    deal = models.ForeignKey(Deal, on_delete=models.CASCADE, related_name='products')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.DecimalField('Количество', max_digits=10, decimal_places=2)
    price = models.DecimalField('Цена за единицу', max_digits=10, decimal_places=2)
    total = models.DecimalField('Итого', max_digits=12, decimal_places=2)

    class Meta:
        verbose_name = 'Товар в сделке'
        verbose_name_plural = 'Товары в сделке'

    def save(self, *args, **kwargs):
        self.total = self.quantity * self.price
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.product.name} x {self.quantity}"