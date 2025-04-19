import os
import json
import logging
import shutil
from datetime import datetime, timedelta
from telegram import (
    Update,
    ReplyKeyboardMarkup,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ConversationHandler,
    ContextTypes,
    CallbackQueryHandler,
    PicklePersistence,
)
# Конфигурация бота
# TOKEN - уникальный ключ для доступа к API Telegram
# STORAGE_PATH - путь к директории для хранения данных
# LOG_FILE - файл для записи логов
# EDIT_TIMEOUT - время, в течение которого можно редактировать акт
TOKEN = "7831050216:AAE8RZ7cN82t2Yj_ulJsaRT7yf9hPDgzjhc"
STORAGE_PATH = "storage"
LOG_FILE = "bot.log"
EDIT_TIMEOUT = 2 * 60 * 60  # 2 часа в секундах

# Поддерживаемые форматы изображений
SUPPORTED_FORMATS = ["jpg", "jpeg", "png", "gif", "bmp"]

# Состояния для ConversationHandler (машины состояний)
# ENTER_ACT_NUMBER - состояние ввода номера акта
# UPLOAD_PHOTOS - состояние загрузки фотографий
ENTER_ACT_NUMBER, UPLOAD_PHOTOS = range(2)

# Настройка логирования
# Настраиваем запись всех действий в файл для отслеживания работы бота
logging.basicConfig(
    filename=LOG_FILE,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

# Дополнительный логгер для вывода в консоль
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
console_handler.setFormatter(console_formatter)
logging.getLogger().addHandler(console_handler)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /start - показывает приветственное сообщение и основное меню"""
    # Создаем клавиатуру с основными функциями бота
    markup = ReplyKeyboardMarkup(
        [["📝 Рег. несоответствия", "📋 Акты о браке"], ["🔎 Поиск акта", "🤖 Помощник РПРЗ"]],
        resize_keyboard=True,
    )
    # Отправляем приветственное сообщение с информацией о команде /help
    await update.message.reply_text(
        "👋 Привет! Это информационный бот завода РПРЗ для учета несоответствий.\n\n"
        "🔹 Используйте кнопки меню для работы с ботом\n"
        "🔹 Для получения справки введите команду /help",
        reply_markup=markup
    )
    # Логируем действие пользователя
    logging.info(f"Пользователь {update.message.from_user.id} запустил бота")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /help - показывает справочную информацию"""
    help_text = (
        "🤖 *Бот учета несоответствий РПРЗ* 🤖\n\n"
        "📋 *Основные функции:*\n"
        "🔸 Регистрация актов о несоответствиях\n"
        "🔸 Загрузка фотографий (до 3 шт.)\n"
        "🔸 Просмотр актов по месяцам\n"
        "🔸 Поиск актов\n\n"
        "📱 *Команды:*\n"
        "🔹 /start - запуск бота и показ меню\n"
        "🔹 /help - показ этой справки\n"
        "🔹 /cancel - отмена текущей операции\n\n"
        "📸 *При загрузке фотографий:*\n"
        "• Отправляйте фото в максимальном качестве\n"
        "• Поддерживаемые форматы: PNG, JPG, JPEG, GIF, BMP\n"
        "• Максимум 3 фотографии на один акт"
    )
    await update.message.reply_text(help_text, parse_mode="Markdown")
    logging.info(f"Пользователь {update.message.from_user.id} запросил справку")

def validate_act_number(number: str) -> bool:
    """Проверяет корректность номера акта (должен содержать от 1 до 4 цифр)"""
    # Проверяем, что номер состоит только из цифр и имеет длину от 1 до 4 символов
    return number.isdigit() and 1 <= len(number) <= 4

# Вспомогательные функции для работы с файлами
async def save_act(act_number: str, user_id: int, photos: list) -> str:
    """Сохраняет акт о браке с фотографиями и метаданными"""
    # Создаем папку для хранения акта в формате ГГГГ-ММ-ДД/номер_акта
    date_folder = datetime.now().strftime("%Y-%m-%d")
    act_folder = os.path.join(STORAGE_PATH, date_folder, act_number)
    os.makedirs(act_folder, exist_ok=True)

    # Сохраняем все фотографии (от 1 до 3 штук)
    saved_photos = 0
    for i, photo in enumerate(photos[:3], 1):
        try:
            # Получаем расширение файла
            ext = photo.file_name.split('.')[-1].lower() if '.' in photo.file_name else ''
            # Проверяем, что формат поддерживается
            if not ext or ext not in SUPPORTED_FORMATS:
                logging.warning(f"Неподдерживаемый формат файла при сохранении: {ext if ext else 'неизвестный'}")
                ext = "jpg"  # Используем jpg по умолчанию
            
            photo_path = os.path.join(act_folder, f"photo_{i}.{ext}")
            await photo.download_to_drive(photo_path)
            saved_photos += 1
            logging.info(f"Сохранено фото {i} для акта {act_number}")
        except Exception as e:
            logging.error(f"Ошибка при сохранении фото {i} для акта {act_number}: {str(e)}")
            # Продолжаем с следующим фото
    
    logging.info(f"Всего сохранено {saved_photos} фото для акта {act_number}")

    # Сохраняем метаданные в JSON-файл
    metadata = {
        "номер_акта": act_number,
        "дата_регистрации": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "telegram_id": str(user_id),
        "количество_фото": saved_photos,
        "поддерживаемые_форматы": ", ".join(SUPPORTED_FORMATS).upper()
    }
    with open(os.path.join(act_folder, "info.json"), "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)

    # Логируем действие
    log_action(user_id, "создание", act_number)
    return act_folder

def log_action(user_id: int, action_type: str, act_number: str) -> None:
    """Записывает действия пользователя в лог-файл"""
    # Формируем строку лога с информацией о действии
    log_entry = (
        f"{datetime.now()} - UserID: {user_id} - {action_type} акта №{act_number}\n"
    )
    # Записываем в файл
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(log_entry)
    
    # Выводим в консоль для мониторинга в реальном времени
    logging.info(f"ДЕЙСТВИЕ: {action_type} акта №{act_number} пользователем {user_id}")

# Обработчики для регистрации акта
async def start_registration(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Начинает процесс регистрации нового акта о браке"""
    # Логируем начало регистрации
    user_id = update.message.from_user.id
    logging.info(f"Пользователь {user_id} начал регистрацию акта")
    
    # Создаем клавиатуру с кнопкой "Назад"
    reply_kb = ReplyKeyboardMarkup(
        [["◀️ Назад"]],
        resize_keyboard=True
    )
    
    # Запрашиваем номер акта
    await update.message.reply_text("Введите номер акта о браке (от 1 до 4 цифр):", reply_markup=reply_kb)
    return ENTER_ACT_NUMBER

async def process_act_number(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обрабатывает введенный пользователем номер акта"""
    act_number = update.message.text
    user_id = update.message.from_user.id
    
    # Проверяем корректность номера акта
    if not validate_act_number(act_number):
        logging.warning(f"Пользователь {user_id} ввел некорректный номер акта: {act_number}")
        await update.message.reply_text(
            "❌ Ошибка! Номер акта должен содержать от 1 до 4 цифр. Без пробелов и букв. Попробуйте снова."
        )
        return ENTER_ACT_NUMBER

    # Сохраняем номер акта в данных пользователя
    context.user_data["act_number"] = act_number
    logging.info(f"Пользователь {user_id} ввел номер акта: {act_number}")
    
    # Создаем клавиатуру с кнопкой "Назад"
    reply_kb = ReplyKeyboardMarkup(
        [["◀️ Назад"]],
        resize_keyboard=True
    )
    
    # Запрашиваем фотографии с улучшенной подсказкой
    await update.message.reply_text(
        "📸 Теперь загрузите фотографии несоответствия (от 1 до 3 шт.):\n\n" 
        "⚠️ Важно! Отправляйте фото в максимальном качестве!\n"
        "✅ Поддерживаемые форматы: PNG, JPG, JPEG",
        reply_markup=reply_kb
    )
    return UPLOAD_PHOTOS

async def get_image_file(message):
    """Возвращает File-объект и расширение, или None, None"""
    try:
        if message.photo and len(message.photo) > 0:
            file = await message.photo[-1].get_file()
            if not file:
                return None, None
            # Добавляем имя файла с расширением jpg для обычных фотографий
            file.file_name = f"photo.jpg"
            return file, "jpg"
        elif message.document and hasattr(message.document, 'mime_type') and message.document.mime_type and message.document.mime_type.startswith("image/"):
            file = await message.document.get_file()
            if not file or not hasattr(file, 'file_name') or not file.file_name:
                return None, None
                
            ext = file.file_name.split('.')[-1].lower() if '.' in file.file_name else ''
            if not ext or ext not in SUPPORTED_FORMATS:
                return None, None
                
            return file, ext
    except Exception as e:
        logging.error(f"Ошибка при получении файла изображения: {str(e)}")
    
    return None, None

async def handle_bad_image(update, user_id):
    """Обрабатывает случай, когда изображение не может быть обработано"""
    logging.warning(f"Пользователь {user_id} отправил неподдерживаемый формат или не изображение")
    # Создаем клавиатуру с кнопкой "Назад"
    reply_kb = ReplyKeyboardMarkup(
        [["◀️ Назад"]],
        resize_keyboard=True
    )
    await update.message.reply_text(
        f"❌ Пожалуйста, отправьте фото в формате: {', '.join(SUPPORTED_FORMATS).upper()}."
        "\n\nСовет: Если фото не принимается, попробуйте отправить его как файл (документ) через скрепку."
        "\n\nИспользуйте кнопку ◀️ Назад для отмены.",
        reply_markup=reply_kb
    )
    return UPLOAD_PHOTOS

async def process_photos(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обрабатывает загруженные пользователем фотографии"""
    user_data = context.user_data
    user_id = update.message.from_user.id
    
    # Инициализируем список фотографий, если его еще нет
    if "photos" not in user_data:
        user_data["photos"] = []

    # Проверяем, не достигнут ли лимит фотографий
    if len(user_data["photos"]) >= 3:
        logging.info(f"Пользователь {user_id} пытается загрузить больше 3 фотографий")
        await update.message.reply_text("📸 Достигнут лимит фотографий (максимум 3).")
        return await finish_registration(update, context)

    try:
        # Получаем файл изображения с помощью вспомогательной функции
        file, ext = await get_image_file(update.message)
        if not file:
            return await handle_bad_image(update, user_id)
        
        # Устанавливаем имя файла, если оно не было установлено
        if not hasattr(file, 'file_name') or not file.file_name:
            file.file_name = f"photo_{len(user_data['photos']) + 1}.{ext}"
            
        # Добавляем файл в список
        user_data["photos"].append(file)
        logging.info(f"Получено изображение от пользователя {user_id}: {file.file_name}")
        
        # Сообщаем пользователю, сколько еще фото можно загрузить
        remaining = 3 - len(user_data["photos"])
        await update.message.reply_text(f"✅ Фото принято ({len(user_data['photos'])}/3). Осталось можно загрузить: {remaining} 📸")
        
        # Если загружено максимальное количество фото, завершаем регистрацию
        if len(user_data["photos"]) >= 3:
            return await finish_registration(update, context)
            
        return UPLOAD_PHOTOS
    except Exception as e:
        logging.error(f"Непредвиденная ошибка при обработке фото от пользователя {user_id}: {str(e)}")
        await update.message.reply_text("❌ Произошла ошибка при обработке фото. Попробуйте еще раз.")
        return UPLOAD_PHOTOS

async def finish_registration(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Завершает процесс регистрации акта и сохраняет данные"""
    act_number = context.user_data["act_number"]
    user_id = update.message.from_user.id
    
    # Проверяем, есть ли хотя бы одно фото
    if "photos" not in context.user_data or not context.user_data["photos"]:
        logging.warning(f"Пользователь {user_id} пытается завершить регистрацию без фотографий")
        await update.message.reply_text("Необходимо загрузить хотя бы одну фотографию!")
        return UPLOAD_PHOTOS
    
    # Сохраняем акт
    try:
        act_folder = await save_act(act_number, user_id, context.user_data["photos"])
        logging.info(f"Акт №{act_number} успешно зарегистрирован пользователем {user_id}")
        
        # Очищаем данные пользователя
        context.user_data.clear()
        
        # Отправляем сообщение об успешной регистрации
        await update.message.reply_text(f"✅ Акт №{act_number} успешно зарегистрирован!")
        return ConversationHandler.END
    except Exception as e:
        logging.error(f"Ошибка при сохранении акта №{act_number}: {str(e)}")
        await update.message.reply_text("Произошла ошибка при сохранении акта. Попробуйте еще раз.")
        return ConversationHandler.END

async def cancel_registration(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Отменяет процесс регистрации акта"""
    user_id = update.message.from_user.id
    logging.info(f"Пользователь {user_id} отменил регистрацию акта")
    
    # Очищаем данные пользователя
    context.user_data.clear()
    
    # Отправляем сообщение об отмене
    await update.message.reply_text("❌ Регистрация акта отменена.")
    return ConversationHandler.END

async def go_back(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработчик кнопки 'Назад' - возвращает в главное меню"""
    user_id = update.message.from_user.id
    logging.info(f"Пользователь {user_id} вернулся в главное меню")
    
    # Очищаем данные пользователя
    context.user_data.clear()
    
    # Показываем главное меню
    await start(update, context)
    return ConversationHandler.END

async def show_acts_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отображает меню с выбором месяца для просмотра актов"""
    user_id = update.message.from_user.id
    logging.info(f"Пользователь {user_id} запросил просмотр актов")
    
    try:
        # Проверяем существование директории хранения
        if not os.path.exists(STORAGE_PATH):
            logging.warning(f"Директория {STORAGE_PATH} не существует")
            await update.message.reply_text('Актов не найдено')
            return
            
        # Получаем список месяцев с актами
        months = {}
        for entry in os.listdir(STORAGE_PATH):
            if os.path.isdir(os.path.join(STORAGE_PATH, entry)):
                try:
                    month = datetime.strptime(entry, '%Y-%m-%d').strftime('%Y-%m')
                    months[month] = months.get(month, 0) + 1
                except ValueError:
                    # Пропускаем директории с неправильным форматом даты
                    logging.warning(f"Пропущена директория с неправильным форматом: {entry}")
                    continue

        if not months:
            logging.info(f"Пользователь {user_id} запросил просмотр актов, но акты не найдены")
            await update.message.reply_text('📂 Актов не найдено')
            return

        # Формируем клавиатуру
        keyboard = []
        for month in sorted(months.keys(), reverse=True):
            month_name = datetime.strptime(month, '%Y-%m').strftime('%B %Y')
            keyboard.append([InlineKeyboardButton(
                text=f"{month_name} ({months[month]} актов)",
                callback_data=f'month:{month}'
            )])

        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text('📅 Выберите месяц для просмотра актов:', reply_markup=reply_markup)
        logging.info(f"Пользователю {user_id} отображено меню с {len(months)} месяцами")

    except Exception as e:
        logging.error(f'Ошибка отображения меню для пользователя {user_id}: {str(e)}')
        await update.message.reply_text('❌ Ошибка при загрузке меню. Попробуйте позже.')
        print(f"ОШИБКА: Не удалось отобразить меню актов: {str(e)}")

async def search_act(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает запрос на поиск акта (заглушка для будущей реализации)"""
    user_id = update.message.from_user.id
    logging.info(f"Пользователь {user_id} запросил поиск акта")
    
    # Пока это заглушка, в будущем здесь будет реализован поиск
    await update.message.reply_text("🔍 Функция поиска акта находится в разработке и будет доступна в ближайшее время.")

async def assistant_rprs(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик для кнопки Помощник РПРЗ"""
    # Заглушка для функции помощника (будет реализована позже)
    await update.message.reply_text(
        "🤖 Функция Помощник РПРЗ находится в разработке и будет доступна в ближайшее время."
    )
    logging.info(f"Пользователь {update.message.from_user.id} запросил помощника РПРЗ")

# Инициализация и запуск бота
def cleanup_old_data():
    """Удаляет акты старше 90 дней для экономии места"""
    try:
        # Вычисляем дату, старше которой акты будут удалены
        threshold = datetime.now() - timedelta(days=90)
        deleted = 0
        
        # Проверяем существование директории хранения
        if not os.path.exists(STORAGE_PATH):
            os.makedirs(STORAGE_PATH)
            logging.info(f"Создана директория для хранения актов: {STORAGE_PATH}")
            return
        
        # Обходим все директории с актами
        for root, dirs, files in os.walk(STORAGE_PATH):
            if 'info.json' in files:
                try:
                    # Читаем метаданные акта
                    with open(os.path.join(root, 'info.json'), 'r', encoding='utf-8') as f:
                        metadata = json.load(f)
                        reg_date = datetime.strptime(metadata['дата_регистрации'], '%Y-%m-%d %H:%M')
                        
                        # Если акт старше 90 дней, удаляем его
                        if reg_date < threshold:
                            shutil.rmtree(root)
                            deleted += 1
                            logging.info(f'Удален старый акт: {root}')
                except Exception as e:
                    logging.error(f'Ошибка обработки {root}: {str(e)}')
        
        # Логируем результат очистки
        logging.info(f'Удалено старых актов: {deleted}')
        print(f"Очистка завершена: удалено {deleted} старых актов")
    except Exception as e:
        logging.error(f'Ошибка очистки данных: {str(e)}')


async def main() -> None:
    """Основная функция для инициализации и запуска бота"""
    # Настраиваем сохранение состояния бота
    persistence = PicklePersistence(filepath="bot_data.pkl")
    
    # Создаем экземпляр приложения с нашим токеном и поддержкой сохранения состояния
    application = Application.builder().token(TOKEN).persistence(persistence).build()
    
    # Настраиваем обработчик диалога для регистрации акта
    conv_handler = ConversationHandler(
        # Точки входа - команды или сообщения, которые запускают диалог
        entry_points=[MessageHandler(filters.Regex("^📝 Рег. несоответствия$"), start_registration)],
        # Состояния диалога и обработчики для каждого состояния
        states={
            # Состояние ввода номера акта
            ENTER_ACT_NUMBER: [
                MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex("^◀️ Назад$"), process_act_number),
                MessageHandler(filters.Regex("^◀️ Назад$"), go_back)
            ],
            # Состояние загрузки фотографий
            UPLOAD_PHOTOS: [
                MessageHandler(filters.PHOTO | filters.Document.ALL, process_photos),
                MessageHandler(filters.Regex("^◀️ Назад$"), go_back),
                MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex("^◀️ Назад$"), process_photos)
            ],
        },
        # Обработчики для выхода из диалога
        fallbacks=[CommandHandler("cancel", cancel_registration)],
        # Включаем сохранение состояния
        name="registration_conversation",
        persistent=True,
    )

    # Добавляем обработчики команд и сообщений
    application.add_handler(CommandHandler("start", start))  # Команда /start
    application.add_handler(CommandHandler("help", help_command))  # Команда /help
    application.add_handler(conv_handler)  # Диалог регистрации акта
    application.add_handler(MessageHandler(filters.Regex("^📋 Акты о браке$"), show_acts_menu))  # Просмотр актов
    application.add_handler(MessageHandler(filters.Regex("^🔎 Поиск акта$"), search_act))  # Поиск акта
    application.add_handler(MessageHandler(filters.Regex("^🤖 Помощник РПРЗ$"), assistant_rprs))  # Помощник РПРЗ

    # Запуск бота с корректным завершением
    logging.info("Инициализация бота...")
    await application.initialize()
    await application.start()
    await application.updater.start_polling()
    print("✅ Бот запущен и готов к работе!")
    logging.info("Бот запущен и готов к работе")
    
    # Ожидание сигнала завершения
    import asyncio
    try:
        await asyncio.Future()  # Бесконечное ожидание до прерывания
    except (KeyboardInterrupt, SystemExit):
        logging.info("Получен сигнал завершения работы")
        print("Завершение работы бота...")
        pass

if __name__ == "__main__":
    # Создаем директорию для хранения, если она не существует
    if not os.path.exists(STORAGE_PATH):
        os.makedirs(STORAGE_PATH)
        print(f"Создана директория для хранения: {STORAGE_PATH}")
    
    # Выводим информацию о запуске
    print("=" * 50)
    print("ЗАПУСК БОТА УЧЕТА НЕСООТВЕТСТВИЙ РПРЗ")
    print(f"Поддерживаемые форматы изображений: {', '.join(SUPPORTED_FORMATS)}")
    print(f"Хранение данных: {os.path.abspath(STORAGE_PATH)}")
    print(f"Лог-файл: {os.path.abspath(LOG_FILE)}")
    print("=" * 50)
    
    # Очистка старых данных при запуске
    cleanup_old_data()
    
    # Запускаем бота
    import asyncio
    try:
        asyncio.run(main())
    except Exception as e:
        logging.critical(f"Критическая ошибка при запуске бота: {str(e)}")
        print(f"КРИТИЧЕСКАЯ ОШИБКА: {str(e)}")
        print("Бот аварийно завершил работу")