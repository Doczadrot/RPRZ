import pytest
from telegram import Update, Message, User, Chat, Document, PhotoSize
from telegram.ext import ContextTypes, ConversationHandler
from main import start_registration, process_act_number, process_photos, finish_registration, show_acts_menu, search_act, ENTER_ACT_NUMBER, UPLOAD_PHOTOS, validate_act_number, SUPPORTED_FORMATS, start, help_command

class DummyContext:
    def __init__(self):
        self.user_data = {}

class DummyDocument:
    def __init__(self, file_name="test.jpg"):
        self.file_name = file_name
    async def get_file(self):
        if self.file_name == "error.jpg":
            return None
        return DummyFile(self.file_name)

class DummyPhotoSize:
    def __init__(self, error=False):
        self.error = error
    async def get_file(self):
        if self.error:
            return None
        return DummyFile("photo.jpg")

class DummyMessage:
    def __init__(self, text):
        self.text = text
        self.replies = []
        self.photo = []
        self.document = None
        self.from_user = User(id=12345, first_name='Test', is_bot=False)
    async def reply_text(self, text, reply_markup=None):
        self.replies.append(text)
        return text

class DummyFile:
    def __init__(self, file_name="test.jpg"):
        self.file_name = file_name
    async def download_to_drive(self, path):
        pass

class DummyUpdate:
    def __init__(self, text, photo=None, document=None, photo_error=False):
        self.message = DummyMessage(text)
        if photo:
            self.message.photo = [DummyPhotoSize(error=photo_error)]
        if document:
            self.message.document = DummyDocument(document)

@pytest.mark.asyncio
async def test_registration_flow():
    context = DummyContext()
    update = DummyUpdate('📝 Рег. несоответствия')
    result = await start_registration(update, context)
    assert result == ENTER_ACT_NUMBER
    
    update = DummyUpdate('123')
    result = await process_act_number(update, context)
    assert context.user_data['act_number'] == '123'
    assert result == UPLOAD_PHOTOS
    
    # Тест загрузки фото
    update = DummyUpdate('', photo=True)
    result = await process_photos(update, context)
    assert result == UPLOAD_PHOTOS
    assert len(context.user_data.get('photos', [])) == 1
    
@pytest.mark.asyncio
async def test_photo_processing():
    # Тест обработки фотографий
    context = DummyContext()
    context.user_data['act_number'] = '123'
    
    # Тест загрузки фото как изображения
    update = DummyUpdate('', photo=True)
    result = await process_photos(update, context)
    assert result == UPLOAD_PHOTOS
    assert len(context.user_data.get('photos', [])) == 1
    
    # Тест загрузки фото как документа
    update = DummyUpdate('', document='test.jpg')
    result = await process_photos(update, context)
    assert result == UPLOAD_PHOTOS
    assert len(context.user_data.get('photos', [])) == 2
    
    # Тест загрузки неподдерживаемого формата
    update = DummyUpdate('', document='test.txt')
    result = await process_photos(update, context)
    assert result == UPLOAD_PHOTOS
    assert len(context.user_data.get('photos', [])) == 2  # Не должно измениться
    assert "Неподдерживаемый формат файла" in update.message.replies[-1]
    
    # Тест загрузки файла без расширения
    update = DummyUpdate('', document='testfile')
    result = await process_photos(update, context)
    assert result == UPLOAD_PHOTOS
    assert len(context.user_data.get('photos', [])) == 2  # Не должно измениться
    assert "Неподдерживаемый формат файла" in update.message.replies[-1]
    
    # Тест ошибки при получении файла документа
    update = DummyUpdate('', document='error.jpg')
    result = await process_photos(update, context)
    assert result == UPLOAD_PHOTOS
    assert len(context.user_data.get('photos', [])) == 2  # Не должно измениться
    assert "Произошла ошибка при обработке" in update.message.replies[-1]
    
    # Тест ошибки при получении файла фото
    update = DummyUpdate('', photo=True, photo_error=True)
    result = await process_photos(update, context)
    assert result == UPLOAD_PHOTOS
    assert len(context.user_data.get('photos', [])) == 2  # Не должно измениться
    assert "Произошла ошибка при обработке" in update.message.replies[-1]
    
    # Тест достижения лимита фотографий
    update = DummyUpdate('', photo=True)
    result = await process_photos(update, context)
    assert len(context.user_data.get('photos', [])) == 3
    
    # Попытка загрузить больше максимума
    update = DummyUpdate('', photo=True)
    result = await process_photos(update, context)
    assert len(context.user_data.get('photos', [])) == 3  # Не должно измениться
    assert "Достигнут лимит фотографий" in update.message.replies[-1]  # Не должно измениться

@pytest.mark.asyncio
async def test_validate_act_number():
    # Тест валидации номера акта
    assert validate_act_number('123') == True
    assert validate_act_number('1234') == True
    assert validate_act_number('12345') == False  # Слишком длинный
    assert validate_act_number('abc') == False    # Не цифры
    assert validate_act_number('12a') == False    # Смешанный
    assert validate_act_number('') == False       # Пустой

@pytest.mark.asyncio
async def test_search_flow():
    context = DummyContext()
    update = DummyUpdate('🔍 Поиск акта')
    await search_act(update, context)
    assert len(update.message.replies) > 0
    assert "Функция поиска акта находится в разработке" in update.message.replies[-1]

@pytest.mark.asyncio
async def test_show_acts_menu():
    context = DummyContext()
    update = DummyUpdate('📜 Акты о браке')
    await show_acts_menu(update, context)
    assert len(update.message.replies) > 0
    
@pytest.mark.asyncio
async def test_start_command():
    context = DummyContext()
    update = DummyUpdate('/start')
    await start(update, context)
    assert len(update.message.replies) > 0
    assert "Привет!" in update.message.replies[-1]
    assert "/help" in update.message.replies[-1]
    
@pytest.mark.asyncio
async def test_help_command():
    context = DummyContext()
    update = DummyUpdate('/help')
    await help_command(update, context)
    assert len(update.message.replies) > 0
    assert "Бот учета несоответствий РПРЗ" in update.message.replies[-1]
    assert "Основные функции" in update.message.replies[-1]
    
@pytest.mark.asyncio
async def test_cancel_registration():
    from main import cancel_registration
    context = DummyContext()
    update = DummyUpdate('/cancel')
    result = await cancel_registration(update, context)
    assert result == ConversationHandler.END
    assert "Регистрация акта отменена" in update.message.replies[-1]