import os
import django
import logging
import re
from django.core.management.base import BaseCommand
from django.conf import settings
from django.contrib.auth.models import User
from crm.models import Client, Deal, Interaction
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'crm_project.settings')
django.setup()

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

TOKEN = settings.TELEGRAM_BOT_TOKEN

NAME, PHONE, REQUEST, CONFIRMATION = range(4)


def normalize_phone(phone: str) -> str:
    """Приводит номер к формату +7XXXXXXXXXX (10 цифр после +7)."""
    # Удаляем всё кроме цифр и +
    cleaned = re.sub(r'[^\d+]', '', phone.strip())
    # Если начинается с 8 и всего 11 цифр -> +7...
    if cleaned.startswith('8') and len(cleaned) == 11:
        return '+7' + cleaned[1:]
    # Если уже +7 и 12 символов
    if cleaned.startswith('+7') and len(cleaned) == 12:
        return cleaned
    # Если просто 10 цифр
    if cleaned.isdigit() and len(cleaned) == 10:
        return '+7' + cleaned
    # fallback
    return phone


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Очищаем временные данные при новом старте
    context.user_data.clear()
    await update.message.reply_text(
        "Здравствуйте! Я бот для приёма заявок в CRM «ФУРНИКОМ».\n\n"
        "Чтобы создать заявку, пожалуйста, ответьте на несколько вопросов.\n\n"
        "Как я могу к вам обращаться? (Введите ваше имя)"
    )
    return NAME


async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_name = update.message.text
    context.user_data['name'] = user_name

    await update.message.reply_text(
        f"Приятно познакомиться, {user_name}!\n\n"
        "Теперь, пожалуйста, введите ваш контактный номер телефона.\n"
        "Можно в формате +7 999 999-99-99 или 89999999999"
    )
    return PHONE


async def get_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    raw_phone = update.message.text
    normalized = normalize_phone(raw_phone)

    # Если есть неразрешённый конфликт (т.е. пользователь вводит номер повторно)
    conflict_client = context.user_data.get('conflict_client')

    if conflict_client:
        # Если введённый номер совпадает с номером клиента, вызвавшего конфликт
        if normalized == conflict_client.phone:
            # Используем этого клиента
            context.user_data['client'] = conflict_client
            # Убираем флаг конфликта
            del context.user_data['conflict_client']
            # Переходим к запросу
            await update.message.reply_text(
                "Отлично! Теперь подробно опишите ваш запрос или что вас интересует."
            )
            return REQUEST
        else:
            # Пользователь ввёл другой номер – проверяем его
            existing = await Client.objects.filter(phone=normalized).afirst()
            if existing:
                # Снова конфликт
                context.user_data['conflict_client'] = existing
                await update.message.reply_text(
                    f"Этот номер телефона уже зарегистрирован на имя: {existing.name}.\n"
                    "Если это вы, введите этот же номер ещё раз.\n"
                    "Если нет – введите другой корректный номер.\n\n"
                    "Пример формата: +7-999-999-99-99"
                )
                return PHONE
            else:
                # Номер свободен
                context.user_data['phone'] = normalized
                # Убираем старый конфликт
                context.user_data.pop('conflict_client', None)
                await update.message.reply_text(
                    "Отлично! Теперь подробно опишите ваш запрос или что вас интересует."
                )
                return REQUEST
    else:
        # Обычная ситуация – проверяем, существует ли клиент с таким номером
        existing = await Client.objects.filter(phone=normalized).afirst()
        if existing:
            # Конфликт – запоминаем клиента и просим подтверждение
            context.user_data['conflict_client'] = existing
            await update.message.reply_text(
                f"⚠️ Этот номер телефона уже зарегистрирован на имя: {existing.name}.\n\n"
                "Если это вы – введите этот же номер ещё раз.\n"
                "Если это другой человек – введите его корректный номер.\n\n"
                "Пример: +7-999-999-99-99"
            )
            return PHONE
        else:
            # Номер свободен – сохраняем
            context.user_data['phone'] = normalized
            await update.message.reply_text(
                "Отлично! Теперь подробно опишите ваш запрос или что вас интересует."
            )
            return REQUEST


async def get_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_request = update.message.text
    context.user_data['request'] = user_request

    user_data = context.user_data
    text_to_confirm = (
        "Пожалуйста, проверьте введённые данные:\n\n"
        f"<b>Имя:</b> {user_data['name']}\n"
        f"<b>Телефон:</b> {user_data['phone']}\n"
        f"<b>Запрос:</b> {user_data['request']}\n\n"
        "Всё верно?"
    )

    reply_keyboard = [['Да, всё верно', 'Нет, начать заново']]

    await update.message.reply_text(
        text_to_confirm,
        reply_markup=ReplyKeyboardMarkup(
            reply_keyboard, one_time_keyboard=True, resize_keyboard=True
        ),
        parse_mode='HTML'
    )
    return CONFIRMATION


async def process_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_choice = update.message.text
    user_data = context.user_data

    if user_choice.lower().startswith('да'):
        try:
            phone = user_data['phone']
            name = user_data['name']
            request_text = user_data['request']

            # Берём клиента: либо из уже решённого конфликта, либо создаём/находим
            client = user_data.get('client')
            if not client:
                # Пытаемся найти существующего (маловероятно, т.к. конфликт уже обработан, но на всякий случай)
                client, created = await Client.objects.aget_or_create(
                    phone=phone,
                    defaults={'name': name, 'contact_person': name}
                )
            else:
                # Клиент уже определён из конфликта – не меняем имя
                # Но убедимся, что в базе такой клиент есть
                if client.phone != phone:
                    # На всякий случай синхронизируем номер
                    client.phone = phone
                    await client.asave()
                created = False  # не новый клиент

            # Назначаем менеджера
            manager = await User.objects.filter(is_superuser=True).afirst()
            if not manager:
                manager = await User.objects.filter(is_active=True).afirst()
                if not manager:
                    raise Exception("Нет ни одного пользователя для назначения менеджером")

            # Создаём сделку
            deal = await Deal.objects.acreate(
                client=client,
                manager=manager,
                title=f"Заявка из Telegram от {client.name} ({client.phone})",
                description=f"Источник: Telegram\n\n{request_text}",
                status='new',
            )

            # Создаём запись о взаимодействии (задача)
            await Interaction.objects.acreate(
                client=client,
                deal=deal,
                manager=manager,
                interaction_type='telegram',
                description=f"Получена новая заявка: {request_text}"
            )

            logging.info(f"Создана новая сделка #{deal.id} (клиент {client.id}) из Telegram.")

            await update.message.reply_text(
                "Спасибо! Ваша заявка успешно создана. Наш менеджер скоро с вами свяжется.",
                reply_markup=ReplyKeyboardRemove(),
            )
        except Exception as e:
            logging.error(f"Ошибка при создании заявки: {e}", exc_info=True)
            await update.message.reply_text(
                "Произошла техническая ошибка. Пожалуйста, попробуйте позже.",
                reply_markup=ReplyKeyboardRemove(),
            )
    else:
        await update.message.reply_text(
            "Хорошо, давайте начнём заново.",
            reply_markup=ReplyKeyboardRemove()
        )
        return await start(update, context)

    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Создание заявки отменено.", reply_markup=ReplyKeyboardRemove()
    )
    return ConversationHandler.END


class Command(BaseCommand):
    help = 'Запускает Telegram-бота для приёма заявок в диалоговом режиме'

    def handle(self, *args, **kwargs):
        self.stdout.write("Запуск Telegram-бота...")

        application = Application.builder().token(TOKEN).build()

        conv_handler = ConversationHandler(
            entry_points=[CommandHandler('start', start)],
            states={
                NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)],
                PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_phone)],
                REQUEST: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_request)],
                CONFIRMATION: [MessageHandler(
                    filters.Regex('^(Да, всё верно|Нет, начать заново)$'),
                    process_confirmation
                )],
            },
            fallbacks=[CommandHandler('cancel', cancel)],
        )

        application.add_handler(conv_handler)

        self.stdout.write("Бот запущен и ожидает сообщений.")
        application.run_polling()