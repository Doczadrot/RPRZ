# -*- coding: utf-8 -*-
import telebot
from telebot import types
import os
import re
import shutil
import sys
from datetime import datetime
import json
import logging
from logging.handlers import RotatingFileHandler

# Configure logging
logger = logging.getLogger('defectbot')
logger.setLevel(logging.DEBUG)

handler = RotatingFileHandler(
    'defectbot.log',
    maxBytes=1024*1024*5,  # 5MB
    backupCount=3,
    encoding='utf-8'
)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

# --- Constants ---
BOT_TOKEN = "7831050216:AAE8RZ7cN82t2Yj_ulJsaRT7yf9hPDgzjhc"  # TODO: Replace with your actual bot token
DATA_DIR = "data"
MAX_PHOTOS = 3
ACT_NUMBER_REGEX = r"^\d{1,4}$"

# Emojis
BACK_ARROW = "⬅️"
REGISTER_ICON = "📝"
INFO_ICON = "ℹ️"
WAVE_ICON = "👋"
CAMERA_ICON = "📷"
CHECK_MARK = "✅"
CROSS_MARK = "❌"
WARNING_ICON = "⚠️"
FOLDER_ICON = "📁"
CLOCK_ICON = "⏰"

def create_data_structure():
    """Creates the base data directory structure if it doesn't exist."""
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        os.makedirs(os.path.join(DATA_DIR, 'pending'), exist_ok=True)
        os.makedirs(os.path.join(DATA_DIR, 'processed'), exist_ok=True)
        print(f"Created directory structure: {DATA_DIR} with pending/processed subdirectories")
    except OSError as e:
        print(f"Error creating directory structure: {e}")
        # Consider exiting for critical errors

def check_pending_registrations():
    """Processes any pending registrations from previous sessions."""
    pending_dir = os.path.join(DATA_DIR, 'pending')
    for filename in os.listdir(pending_dir):
        if filename.endswith('.json'):
            filepath = os.path.join(pending_dir, filename)
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                # Move to processed
                try:
                    # Notify user first
                    bot.send_message(data['user_id'], 
                        f"{CHECK_MARK} Ваш акт {data['act_number']} успешно зарегистрирован!")
                    
                    # Move to processed after successful notification
                    processed_path = os.path.join(DATA_DIR, 'processed', filename)
                    shutil.move(filepath, processed_path)
                    logger.info(f"Processed pending registration: {filename}")
                except Exception as e:
                    logger.error(f"Failed to process pending registration {filename}: {e}")
                    # Keep file in pending for retry
            except Exception as e:
                logger.error(f"Error processing {filename}: {e}")

# --- Bot Initialization ---
create_data_structure()
try:
    bot = telebot.TeleBot(BOT_TOKEN)
    print("Bot initialized successfully.")
    check_pending_registrations()
except Exception as e:
    print(f"Error initializing bot: {e}")
    sys.exit(1)

# --- User State Management (Simple dictionary) ---
user_state = {}  # {user_id: {'state': 'awaiting_act_number'/'awaiting_photos', 'act_number': 'АБ-123456'}}

# --- Helper Functions ---


def get_main_keyboard():
    """Returns the main ReplyKeyboardMarkup."""
    keyboard = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=False)
    btn_register = telebot.types.KeyboardButton(f"{REGISTER_ICON} Зарегистрировать визуальные несоответствия")
    btn_format = telebot.types.KeyboardButton(f"{INFO_ICON} Формат номера акта о браке")
    keyboard.add(btn_register)
    keyboard.add(btn_format)
    return keyboard

def get_photo_upload_keyboard():
    """Returns the keyboard for the photo upload stage."""
    keyboard = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=False)
    btn_done = telebot.types.KeyboardButton(f"{CHECK_MARK} Завершить (/done)")
    btn_back = telebot.types.KeyboardButton(f"{BACK_ARROW} Назад")
    keyboard.add(btn_done)
    keyboard.add(btn_back)
    return keyboard

# --- Message Handlers ---
@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    """Handles the /start and /help commands."""
    user_id = message.from_user.id
    user_state.pop(user_id, None) # Clear any previous state
    bot.reply_to(message,
                 f"{WAVE_ICON} Привет. Это бот завода РПРЗ.",
                 reply_markup=get_main_keyboard())
    logger.info(f"User {message.from_user.id} started the bot")

@bot.message_handler(func=lambda message: message.text == f"{INFO_ICON} Формат номера акта о браке")
def show_act_format(message):
    """Shows the format for the act number."""
    user_id = message.from_user.id
    user_state.pop(user_id, None) # Clear any previous state
    bot.reply_to(message,
                 f"{INFO_ICON} Формат номера акта о браке: от 1 до 4 цифр (например, 1234). Введите его при регистрации дефекта.",
                 reply_markup=get_main_keyboard())
    logger.info(f"User {message.from_user.id} requested act number format")

@bot.message_handler(func=lambda message: message.text == f"{REGISTER_ICON} Зарегистрировать визуальные несоответствия")
def request_act_number(message):
    """Requests the act number from the user."""
    user_id = message.from_user.id
    user_state[user_id] = {'state': 'awaiting_act_number'}
    # Use force_reply to make the user's next message a reply to this one
    markup = telebot.types.ForceReply(selective=False)
    bot.send_message(message.chat.id,
                     f"{REGISTER_ICON} Введите номер акта о браке (от 1 до 4 цифр).",
                     reply_markup=markup)
    # Register the next step handler to process the entered act number
    bot.register_next_step_handler(message, process_act_number)

def process_act_number(message):
    """Processes the entered act number."""
    user_id = message.from_user.id
    act_number = message.text.strip().upper()

    try:
        # Save pending registration
        pending_data = {
            'user_id': user_id,
            'act_number': act_number,
            'timestamp': datetime.now().isoformat(),
            'status': 'pending'
        }
        pending_path = os.path.join(DATA_DIR, 'pending', f'{act_number}.json')
        with open(pending_path, 'w', encoding='utf-8') as f:
            json.dump(pending_data, f)

        logger.info(f"Saved pending registration for act {act_number}")
        
        # Attempt to send immediate confirmation
        bot.send_message(message.chat.id, 
            f"{CHECK_MARK} Ваш акт {act_number} принят в обработку. Мы уведомим вас о результате.")
        
    except Exception as e:
        logger.error(f"Failed to process act {act_number}: {e}")
        if os.path.exists(pending_path):
            os.remove(pending_path)
        bot.send_message(message.chat.id,
            f"{WARNING_ICON} Ошибка обработки запроса. Пожалуйста, попробуйте позже.")

    # Check for existing processed acts
    processed_path = os.path.join(DATA_DIR, 'processed', f'{act_number}.json')
    if os.path.exists(processed_path):
        try:
            bot.send_message(message.chat.id, f"{CROSS_MARK} Акт {act_number} уже зарегистрирован!")
        except Exception as e:
            logger.error(f"Failed to send duplicate warning for {act_number}: {e}")
        logger.warning(f"Duplicate act number attempt: {act_number}")
        return

    # Check if user is in the correct state (basic check)
    if user_id not in user_state or user_state[user_id].get('state') != 'awaiting_act_number':
        # User might have sent text unexpectedly, guide them back
        bot.send_message(message.chat.id, f"{WARNING_ICON} Пожалуйста, используйте кнопки.")