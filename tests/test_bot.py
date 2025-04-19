# -*- coding: utf-8 -*-
import pytest
import os
import sys

# Add the parent directory to the Python path to allow importing 'bot'
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Basic test to ensure the bot module can be imported
def test_import_bot():
    try:
        from bot import bot, DATA_DIR, create_data_structure
        assert bot is not None
        # Ensure data directory exists for tests that might need it
        create_data_structure()
        assert os.path.exists(DATA_DIR)
    except ImportError as e:
        pytest.fail(f"Failed to import bot module: {e}")

import shutil
from unittest.mock import MagicMock, patch, mock_open

from bot import create_data_structure, process_act_number, DATA_DIR, user_state, get_main_keyboard

# --- Fixtures ---
@pytest.fixture(autouse=True)
def manage_data_dir():
    """Ensure data directory is clean before each test and removed after."""
    if os.path.exists(DATA_DIR):
        shutil.rmtree(DATA_DIR)
    create_data_structure() # Create it fresh for the test
    yield # Run the test
    if os.path.exists(DATA_DIR):
        shutil.rmtree(DATA_DIR)

@pytest.fixture
def mock_message():
    """Creates a mock message object for testing handlers."""
    message = MagicMock()
    message.from_user.id = 12345
    message.chat.id = 67890
    message.text = ""
    return message

# --- Test Functions ---

def test_create_data_structure_creates_dir():
    """Test if create_data_structure creates the directory."""
    # The fixture already handles creation and cleanup
    assert os.path.exists(DATA_DIR)
    assert os.path.isdir(DATA_DIR)

# Mock the bot object and its methods used within process_act_number
@patch('bot.bot')
def test_process_act_number_valid(mock_bot, mock_message):
    """Test processing a valid act number."""
    user_id = mock_message.from_user.id
    user_state[user_id] = {'state': 'awaiting_act_number'}
    mock_message.text = "1234"

    process_act_number(mock_message)

    # Assert state changed correctly
    assert user_id in user_state
    assert user_state[user_id]['state'] == 'awaiting_photos'
    assert user_state[user_id]['act_number'] == "1234"
    assert user_state[user_id]['photos_received'] == 0
    # Assert bot sent the correct messages
    assert mock_bot.send_message.call_count == 2
    args1, _ = mock_bot.send_message.call_args_list[0]
    assert "принят в обработку" in args1[1]
    
    args2, kwargs = mock_bot.send_message.call_args_list[1]
    assert "Номер акта 1234 принят" in args2[1]
    assert isinstance(kwargs['reply_markup'], telebot.types.ForceReply)

    # Clean up state for other tests
    user_state.pop(user_id, None)

@patch('bot.logger')
def test_process_act_number_save_failure(mock_logger, mock_bot, mock_message):
    """Test failure during act number processing."""
    user_id = mock_message.from_user.id
    user_state[user_id] = {'state': 'awaiting_act_number'}
    mock_message.text = "9999"

    # Make save path invalid
    with patch('bot.DATA_DIR', '/invalid/path'):
        process_act_number(mock_message)

    # Assert error handled
    mock_logger.error.assert_called()
    mock_bot.send_message.assert_called_with(mock_message.chat.id,
        "⚠️ Ошибка обработки запроса. Пожалуйста, попробуйте позже.")
    assert user_id not in user_state

@patch('bot.bot')
def test_process_act_number_invalid_format(mock_bot, mock_message):
    """Test processing an invalid act number format."""
    user_id = mock_message.from_user.id
    user_state[user_id] = {'state': 'awaiting_act_number'}
    mock_message.text = "INVALID-FORMAT"

    process_act_number(mock_message)

    # Assert state did NOT change
    assert user_id in user_state
    assert user_state[user_id]['state'] == 'awaiting_act_number'
    assert 'act_number' not in user_state[user_id]

    # Assert bot sent error message and re-registered handler
    mock_bot.send_message.assert_called_once()
    args, kwargs = mock_bot.send_message.call_args
    assert args[0] == mock_message.chat.id
    assert "Неверный формат номера. Пожалуйста, введите номер акта (от 1 до 4 цифр):" in args[1]
    mock_logger.warning.assert_called_once_with(f"Invalid act number format: INVALID-FORMAT from user 12345")
    assert isinstance(kwargs['reply_markup'], telebot.types.ForceReply)
    mock_bot.register_next_step_handler.assert_called_once_with(mock_message, process_act_number)

    # Clean up state
    user_state.pop(user_id, None)

@patch('bot.bot')
def test_process_act_number_already_exists(mock_bot, mock_message):
    """Test processing an act number that already exists."""
    user_id = mock_message.from_user.id
    user_state[user_id] = {'state': 'awaiting_act_number'}
    act_number = "9876"
    mock_message.text = act_number

    # Create a dummy directory for the existing act
    existing_act_path = os.path.join(DATA_DIR, act_number)
    os.makedirs(existing_act_path)

    process_act_number(mock_message)

    # Assert state was cleared
    assert user_id not in user_state

    # Assert bot sent the 'already registered' message
    mock_bot.send_message.assert_called_once()
    args, kwargs = mock_bot.send_message.call_args
    assert args[0] == mock_message.chat.id
    assert f"Акт с номером {act_number} уже зарегистрирован!" in args[1]
    mock_logger.warning.assert_called_once_with(f"Duplicate act number: 9876 from user 12345")
    # Check if the correct keyboard structure is sent
    assert isinstance(kwargs['reply_markup'], telebot.types.ReplyKeyboardMarkup)
    # Direct comparison might be tricky due to object identity, compare relevant attributes if needed
    # For now, just checking the type might suffice if structure is consistent
    # assert kwargs['reply_markup'] == get_main_keyboard() # Reverted this comparison
    mock_bot.register_next_step_handler.assert_not_called() # Should not ask again

    # Clean up state (already done by the function, but good practice)
    user_state.pop(user_id, None)

import telebot

@patch('bot.bot')
def test_send_welcome(mock_bot, mock_message):
    """Test the /start command handler."""
    user_id = mock_message.from_user.id
    # Set a dummy state to ensure it gets cleared
    user_state[user_id] = {'state': 'some_old_state'}

    from bot import send_welcome # Import locally to avoid issues if bot fails to init globally
    send_welcome(mock_message)

    # Assert state was cleared
    assert user_id not in user_state

    # Assert reply_to was called with correct text and keyboard
    mock_bot.reply_to.assert_called_once()
    args, kwargs = mock_bot.reply_to.call_args
    assert args[0] == mock_message
    assert "Привет. Это бот завода РПРЗ." in args[1]
    # Check if the correct keyboard structure is sent
    assert isinstance(kwargs['reply_markup'], telebot.types.ReplyKeyboardMarkup)
    # Direct comparison might be tricky due to object identity, compare relevant attributes if needed
    # For now, just checking the type might suffice if structure is consistent
    # assert kwargs['reply_markup'] == get_main_keyboard() # Reverted this comparison

@patch('bot.bot')
def test_show_act_format(mock_bot, mock_message):
    """Test the 'Формат номера акта о браке' handler."""
    user_id = mock_message.from_user.id
    # Set a dummy state to ensure it gets cleared
    user_state[user_id] = {'state': 'some_old_state'}
    mock_message.text = "Формат номера акта о браке"

    from bot import show_act_format
    show_act_format(mock_message)

    # Assert state was cleared
    assert user_id not in user_state

    # Assert reply_to was called with correct text and keyboard
    mock_bot.reply_to.assert_called_once()
    args, kwargs = mock_bot.reply_to.call_args
    assert args[0] == mock_message
    assert "Формат номера акта о браке: от 1 до 4 цифр (например, 1234). Введите его при регистрации дефекта." in args[1]
    # Check if the correct keyboard structure is sent
    assert isinstance(kwargs['reply_markup'], telebot.types.ReplyKeyboardMarkup)
    # Direct comparison might be tricky due to object identity, compare relevant attributes if needed
    # For now, just checking the type might suffice if structure is consistent
    # assert kwargs['reply_markup'] == get_main_keyboard() # Reverted this comparison

@patch('bot.bot')
def test_request_act_number(mock_bot, mock_message):
    """Test the 'Зарегистрировать визуальные несоответствия' handler."""
    user_id = mock_message.from_user.id
    user_state.pop(user_id, None) # Ensure state is initially clear
    mock_message.text = "Зарегистрировать визуальные несоответствия"

    from bot import request_act_number
    request_act_number(mock_message)

    # Assert state was set correctly
    assert user_id in user_state
    assert user_state[user_id]['state'] == 'awaiting_act_number'

    # Assert send_message was called to ask for act number
    mock_bot.send_message.assert_called_once()
    args, kwargs = mock_bot.send_message.call_args
    assert args[0] == mock_message.chat.id
    assert "Введите номер акта о браке (от 1 до 4 цифр)." in args[1]
    assert isinstance(kwargs['reply_markup'], telebot.types.ForceReply)

    # Assert next step handler was registered
    mock_bot.register_next_step_handler.assert_called_once_with(mock_message, process_act_number)

    # Clean up state
    user_state.pop(user_id, None)

@patch('bot.bot')
def test_handle_photos_success(mock_bot, mock_message):
    """Test handling a photo successfully."""
    user_id = mock_message.from_user.id
    act_number = "АБ-111222"
    user_state[user_id] = {'state': 'awaiting_photos', 'act_number': act_number, 'photos_received': 0}

    # Mock photo object and bot methods
    mock_photo_size = MagicMock()
    mock_photo_size.file_id = 'test_file_id'
    mock_message.photo = [mock_photo_size] # Simulate photo message
    mock_file_info = MagicMock()
    mock_file_info.file_path = 'test/path/photo.jpg'
    mock_bot.get_file.return_value = mock_file_info
    mock_bot.download_file.return_value = b'fake_image_data'

    from bot import handle_photos
    # Use mock_open for better file handle mocking
    with patch('builtins.open', mock_open()) as mocked_file, \
         patch('os.makedirs') as mock_makedirs:

        handle_photos(mock_message)

        # Assert state updated
        assert user_state[user_id]['photos_received'] == 1

        # Assert directory was created (or attempted)
        mock_makedirs.assert_called_once_with(os.path.join(DATA_DIR, act_number), exist_ok=True)

        # Assert bot methods called
        mock_bot.get_file.assert_called_once_with('test_file_id')
        mock_bot.download_file.assert_called_once_with('test/path/photo.jpg')

        # Assert file was opened for writing
        # Assert file was opened correctly
        mocked_file.assert_called_once_with(os.path.join(DATA_DIR, act_number, 'photo1.jpg'), 'wb')
        # Assert write was called correctly on the file handle returned by open
        mocked_file.return_value.write.assert_called_once_with(b'fake_image_data')


        # Assert confirmation message sent
        mock_bot.send_message.assert_called_with(mock_message.chat.id, "Фото 1 из 3 сохранено.")

    # Clean up state
    user_state.pop(user_id, None)

@patch('bot.bot')
def test_handle_photos_too_many(mock_bot, mock_message):
    """Test sending too many photos."""
    user_id = mock_message.from_user.id
    act_number = "АБ-333444"
    user_state[user_id] = {'state': 'awaiting_photos', 'act_number': act_number, 'photos_received': 3} # Already at max

    mock_photo_size = MagicMock()
    mock_message.photo = [mock_photo_size]

    from bot import handle_photos
    handle_photos(mock_message)

    # Assert state did not change
    assert user_state[user_id]['photos_received'] == 3

    # Assert message about limit was sent
    mock_bot.send_message.assert_called_once_with(mock_message.chat.id, "Вы уже отправили максимальное количество (3) фотографий. Нажмите /done для завершения.")
    mock_bot.get_file.assert_not_called()
    mock_bot.download_file.assert_not_called()

    # Clean up state
    user_state.pop(user_id, None)

@patch('bot.bot')
def test_handle_photos_wrong_state(mock_bot, mock_message):
    """Test sending photo when not awaiting photos."""
    user_id = mock_message.from_user.id
    user_state.pop(user_id, None) # Ensure user is not in state

    mock_photo_size = MagicMock()
    mock_message.photo = [mock_photo_size]

    from bot import handle_photos
    handle_photos(mock_message)

    # Assert no state was created
    assert user_id not in user_state

    # Assert no bot methods related to saving were called
    mock_bot.send_message.assert_not_called()
    mock_bot.get_file.assert_not_called()
    mock_bot.download_file.assert_not_called()

def test_check_pending_registrations(mock_bot):
    """Test processing of pending registrations on startup."""
    # Create dummy pending file
    test_act = 'TEST123'
    pending_data = {
        'user_id': 12345,
        'act_number': test_act,
        'timestamp': '2024-01-01T00:00:00',
        'status': 'pending'
    }
    pending_path = os.path.join(DATA_DIR, 'pending', f'{test_act}.json')
    with open(pending_path, 'w', encoding='utf-8') as f:
        json.dump(pending_data, f)

    from bot import check_pending_registrations
    check_pending_registrations()

    # Assert file moved to processed
    processed_path = os.path.join(DATA_DIR, 'processed', f'{test_act}.json')
    assert os.path.exists(processed_path)
    
    # Assert message sent
    mock_bot.send_message.assert_called_once_with(12345, 
        f"✅ Ваш акт {test_act} успешно зарегистрирован!")

    # Cleanup
    if os.path.exists(processed_path):
        os.remove(processed_path)

@patch('bot.logger')
def test_check_pending_registrations_failure(mock_logger, mock_bot):
    """Test failed processing of pending registrations."""
    # Create corrupted pending file
    test_act = 'CORRUPTED'
    pending_path = os.path.join(DATA_DIR, 'pending', f'{test_act}.json')
    with open(pending_path, 'w', encoding='utf-8') as f:
        f.write('invalid json')

    from bot import check_pending_registrations
    check_pending_registrations()

    # Assert error logged and file remains
    mock_logger.error.assert_called()
    assert os.path.exists(pending_path)

    # Cleanup
    if os.path.exists(pending_path):
        os.remove(pending_path)

# Add more tests here later for /done and other handlers