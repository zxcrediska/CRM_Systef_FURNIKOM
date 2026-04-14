from django import forms
from .models import Client, Deal, Interaction, DealProduct, Product


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
            'product': forms.Select(attrs={'class': 'form-select'}),
            'quantity': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0.01'
            }),
            'price': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0'
            }),
        }
        labels = {
            'product': 'Товар',
            'quantity': 'Количество',
            'price': 'Цена за единицу (₽)',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Автоматически подставляем цену товара при выборе
        if self.instance and self.instance.product:
            self.fields['price'].initial = self.instance.product.price