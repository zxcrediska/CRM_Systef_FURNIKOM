from django import forms
from .models import Client, Deal, Interaction, DealProduct, Product, Task


class ClientCreateForm(forms.ModelForm):
    """Форма для создания нового клиента"""

    class Meta:
        model = Client

        fields = ['name', 'contact_person', 'phone', 'email', 'address', 'inn', 'notes']

        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'ООО "Ромашка"'}),
            'contact_person': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Иванов Иван Иванович'}),
            'phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '+7 (999) 123-45-67'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'info@romashka.ru'}),
            'address': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'г. Москва, ул. Ленина, д. 1'}),
            'inn': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '1234567890'}),
            'notes': forms.Textarea(
                attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'Дополнительная информация о клиенте'}),
        }

        labels = {
            'name': 'Название компании',
            'contact_person': 'Контактное лицо',
            'phone': 'Телефон',
            'email': 'Email',
            'address': 'Адрес',
            'inn': 'ИНН',
            'notes': 'Примечания',
        }


class ClientLeadForm(forms.Form):
    """Форма для регистрации заявки от клиента"""
    company_name = forms.CharField(
        label='Название компании',
        max_length=200,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'ООО "Ваша компания"'
        })
    )
    contact_person = forms.CharField(
        label='Контактное лицо',
        max_length=100,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Иван Иванов'
        })
    )
    phone = forms.CharField(
        label='Телефон',
        max_length=20,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '+7 (999) 123-45-67'
        })
    )
    email = forms.EmailField(
        label='Email',
        required=False,
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'info@company.ru'
        })
    )
    deal_title = forms.CharField(
        label='Тема заявки',
        max_length=200,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Поставка фурнитуры для корпусной мебели'
        })
    )
    description = forms.CharField(
        label='Описание запроса',
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 5,
            'placeholder': 'Опишите подробно ваш запрос...'
        })
    )
    source = forms.ChoiceField(
        label='Откуда узнали о нас?',
        choices=[
            ('website', 'Сайт'),
            ('recommendation', 'Рекомендация'),
            ('advertising', 'Реклама'),
            ('social', 'Социальные сети'),
            ('other', 'Другое'),
        ],
        widget=forms.Select(attrs={'class': 'form-select'})
    )


class EmailLeadForm(forms.Form):
    """Форма для создания заявки из email"""
    sender_email = forms.EmailField(
        label='Email отправителя',
        widget=forms.EmailInput(attrs={'class': 'form-control'})
    )
    sender_name = forms.CharField(
        label='Имя отправителя',
        max_length=100,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    subject = forms.CharField(
        label='Тема письма',
        max_length=200,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    body = forms.CharField(
        label='Текст письма',
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 6})
    )
    phone = forms.CharField(
        label='Телефон',
        max_length=20,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )


class DealEditForm(forms.ModelForm):
    """Форма для редактирования сделки"""

    class Meta:
        model = Deal
        fields = ['title', 'description', 'amount', 'status', 'expected_close_date']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'expected_close_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
        }
        labels = {
            'title': 'Название сделки',
            'description': 'Описание',
            'amount': 'Сумма (₽)',
            'status': 'Статус',
            'expected_close_date': 'Ожидаемая дата закрытия',
        }


class DealProductForm(forms.ModelForm):
    """Форма для добавления товара в сделку"""

    class Meta:
        model = DealProduct
        fields = ['product', 'quantity', 'price']
        widgets = {
            'product': forms.Select(attrs={'class': 'form-select', 'id': 'id_product'}),
            'quantity': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0.01',
                'value': '1',
            }),
            'price': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0',
            }),
        }
        labels = {
            'product': 'Товар',
            'quantity': 'Количество',
            'price': 'Цена за единицу (₽)',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['product'].queryset = Product.objects.all()
        self.fields['product'].empty_label = '--- Выберите товар ---'

        # Делаем цену необязательной при заполнении формы —
        # она подставится автоматически, если не указана
        self.fields['price'].required = False

    def clean(self):
        cleaned_data = super().clean()
        product = cleaned_data.get('product')
        price = cleaned_data.get('price')

        # Если цена не указана, берём из товара
        if product and not price:
            cleaned_data['price'] = product.price

        if not cleaned_data.get('price'):
            raise forms.ValidationError('Укажите цену или выберите товар с ценой.')

        return cleaned_data


class DealAmountForm(forms.ModelForm):
    """Форма для быстрого изменения суммы сделки"""

    class Meta:
        model = Deal
        fields = ['amount']
        widgets = {
            'amount': forms.NumberInput(attrs={
                'class': 'form-control form-control-lg',
                'step': '0.01',
                'min': '0',
                'autofocus': True,
            }),
        }
        labels = {
            'amount': 'Сумма сделки (₽)',
        }

from .models import Client, Deal, Interaction, DealProduct, Product, Task


class TaskCreateForm(forms.ModelForm):
    """Форма для создания задачи"""

    class Meta:
        model = Task
        fields = ['title', 'description', 'deal', 'priority', 'status', 'due_date']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'deal': forms.Select(attrs={'class': 'form-select'}),
            'priority': forms.Select(attrs={'class': 'form-select'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'due_date': forms.DateTimeInput(attrs={
                'class': 'form-control',
                'type': 'datetime-local',
            }),
        }
        labels = {
            'title': 'Название задачи',
            'description': 'Описание',
            'deal': 'Сделка',
            'priority': 'Приоритет',
            'status': 'Статус',
            'due_date': 'Срок выполнения',
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        self.fields['deal'].queryset = Deal.objects.exclude(
            status__in=['completed', 'cancelled']
        ).select_related('client').order_by('-created_at')
        self.fields['deal'].empty_label = '--- Выберите сделку ---'


class TaskEditForm(forms.ModelForm):
    """Форма для редактирования задачи"""

    class Meta:
        model = Task
        fields = ['title', 'description', 'priority', 'status', 'due_date']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'priority': forms.Select(attrs={'class': 'form-select'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'due_date': forms.DateTimeInput(attrs={
                'class': 'form-control',
                'type': 'datetime-local',
            }),
        }
        labels = {
            'title': 'Название задачи',
            'description': 'Описание',
            'priority': 'Приоритет',
            'status': 'Статус',
            'due_date': 'Срок выполнения',
        }