from dotenv import load_dotenv
from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Update,
    ReplyKeyboardMarkup,
    KeyboardButton
)
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    MessageHandler,
    filters
)
from dataclasses import dataclass
from typing import Dict, List, Optional
import os
import re
import logging
import hashlib
from datetime import datetime, time, timedelta
import pytz
import asyncio
import threading
import time

from statistics import StatisticsManager
from stats_handler import StatsHandler

# Настройка логгирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

load_dotenv('token.env')
TOKEN = os.getenv("TOKEN")

# ID админского чата для отправки ежедневной статистики
ADMIN_CHAT_ID = "-1003131568927"

# ID администраторов бота
ADMIN_IDS = [550680968, 332518486, 7068694127, 1118098514]

@dataclass
class Solution:
    text: str
    content_type: str = "none"  # image/file

@dataclass
class DeviceModel:
    name: str
    numbers: List[str]

@dataclass
class Device:
    name: str
    models: Dict[str, DeviceModel]
    common_questions: Dict[str, Solution]

class BotHandler:
    def __init__(self):
        self.content_base_path = os.getenv("CONTENT_BASE_PATH", "data")
        self.stats_manager = StatisticsManager()
        self.devices = {
            'scanner': Device(
                name="Сканер",
                models={
                    'netum': DeviceModel(name="Netum", numbers=["C750", "1228BL"]),
                    'kefar': DeviceModel(name="Kefar", numbers=["H4W/H4B", "C70"]),
                    'holyhah': DeviceModel(name="Holyhah", numbers=["A60DZ/A66DZ", "A30D/A3D"]),
                    'chiypos': DeviceModel(name="Chiypos", numbers=["1680SW", "1690SW"]),
                },
                common_questions={
                    "Инструкция": Solution(text="Инструкция на русском языке:", content_type="file"),
                    "Сброс настроек": Solution(text="Отсканируйте код(ы) для сброса настроек:", content_type="image")
                }
            ),
            'printer': Device(
                name="Принтер",
                models={
                    'xprinter': DeviceModel(name="XPrinter", numbers=["XP365B", "XP422"]),
                    'niimbot': DeviceModel(name="NIIMBOT", numbers=["B21", "D11", "D110"])
                },
                common_questions={
                    "Инструкция": Solution(text="Инструкция на русском языке:", content_type="file")
                }
            ),
            'pager': Device(
                name="Пейджеры",
                models={
                    'td': DeviceModel(name="TD", numbers=["TD175", "TD157"])
                },
                common_questions={
                    "Инструкция": Solution(text="Инструкция на русском языке:", content_type="file")
                }
            )
        }
        
        self.model_questions = {
            'scanner/netum/C750': {
                "Не включается": Solution(text="Возможно, он сильно разряжен, или вы его некорректно заряжали. Убедитесь, что мощность зарядки не более 5В-1А"),
                "Не сканирует": Solution(text="Помогите, меня держат в плену :'(", ),
                "Установка драйвера": Solution(text="Hut uuit")
            },
            'scanner/kefar/1': {
                "Греется": Solution(text="Дайте устройству остыть")
            }
        }
        
        self.messages = {
            'start': """
Доброго времени суток!

Данная версия бота является тестовой, просим прощения за неудобства. Будем благодарны, если сообщите о проблеме: @SOLARDTEX

Выберите тип устройства, с которым возникли проблемы:
""",

#################

            'model': """

Хорошо. Теперь выберите модель устройства, она указана на коробке или маркетплейсе, где был приобретён товар.
Следующим шагом нужно будет выбрать номер.

Пример: модель - Netum, номер - C750
""",

#################

            'number': """

Осталось выбрать номер устройства.

Пример: модель - Xprinter, номер - XP365B
""",

#################

            'questions': """

Выберите проблему, с которой вы столкнулись.

В случае, если возникли трудности и вы ознакомились с инструкцией, напишите нашим специалистам: @SOLARDTEX
""",

#################

            'other': """           
Пожалуйста, опишите вашу проблему нашему специалисту: @SOLARDTEX
"""

#################
        }

        self.reply_keyboard = ReplyKeyboardMarkup(
            [[KeyboardButton("/start")]],
            resize_keyboard=True,
            one_time_keyboard=False
        )

        # Хранилище ID вопросов (временное)
        self.question_map = {}
        
        # Инициализация обработчика статистики
        self.stats_handler = StatsHandler(self.stats_manager, self.devices)
    

    def create_back_button(self, back_data: str) -> List[InlineKeyboardButton]:
        return [InlineKeyboardButton("« Назад", callback_data=back_data)]

    def sanitize_filename(self, text: str) -> str:
        text = text.lower()
        text = re.sub(r'[^a-zа-я0-9]+', '_', text)
        return text.strip('_')

    def get_content_path(self, device_type: str, model: str, number: str, question: str, content_type: str) -> Optional[str]:
        if content_type == "none":
            return None
            
        safe_device = self.sanitize_filename(device_type)
        safe_model = self.sanitize_filename(model)
        safe_number = self.sanitize_filename(number)
        safe_question = self.sanitize_filename(question)
        
        path = os.path.join(
            self.content_base_path,
            "images" if content_type == "image" else "files",
            safe_device,
            safe_model,
            safe_number,
            f"{safe_question}.{'jpg' if content_type == 'image' else 'pdf'}"
        )
        
        if not os.path.exists(path):
            logger.error(f"Файл не найден: {path}")  
        
        return path

    def make_question_id(self, device_type, model, number, question_text):
        q_hash = hashlib.md5(question_text.encode()).hexdigest()[:8]
        q_id = f"{device_type}_{model}_{number}_{q_hash}"
        self.question_map[q_id] = (device_type, model, number, question_text)
        return q_id

    async def send_content(self, query, solution: Solution, device_type: str, model: str, number: str, question: str) -> None:
        content_path = self.get_content_path(device_type, model, number, question, solution.content_type)
        back_button = self.create_back_button(f"back_to_questions_{device_type}_{model}_{number}")
        reply_markup = InlineKeyboardMarkup([back_button])

        try:
            if not content_path:
                await query.edit_message_text(text=solution.text, reply_markup=reply_markup)
            elif solution.content_type == "image":
                with open(content_path, 'rb') as photo:
                    await query.message.reply_photo(photo=photo, reply_markup=self.reply_keyboard)
                await query.message.reply_text(text=solution.text, reply_markup=reply_markup)
                await query.delete_message()
            elif solution.content_type == "file":
                with open(content_path, 'rb') as file:
                    await query.message.reply_document(document=file, reply_markup=self.reply_keyboard)
                await query.message.reply_text(text=solution.text, reply_markup=reply_markup)
                await query.delete_message()
        except FileNotFoundError:
            error_msg = (
                f"{solution.text}\n\n"
                f"⚠ Контент недоступен\n"
                f"Путь: {content_path}\n"
                f"Причина: файл не найден"
            )
            await query.edit_message_text(
                text=error_msg,
                reply_markup=reply_markup
            )
        except Exception as e:
            error_msg = (
                f"{solution.text}\n\n"
                f"⚠ Произошла ошибка\n"
                f"Путь: {content_path}\n"
                f"Причина: {str(e)}"
            )
            await query.edit_message_text(
                text=error_msg,
                reply_markup=reply_markup
            )

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not update.message:
            return
        
        user = update.message.from_user
        
        # Обновляем информацию о пользователе
        self.stats_manager.update_user_info(
            user_id=user.id,
            username=user.username,
            first_name=user.first_name,
            last_name=user.last_name
        )
        
        # Логируем действие
        self.stats_manager.log_action(user.id, "start")
            
        device_buttons = [
            [
                InlineKeyboardButton("Сканер", callback_data="device_scanner"),
                InlineKeyboardButton("Принтер", callback_data="device_printer")
            ],
            [
                InlineKeyboardButton("Пейджеры", callback_data="device_pager"),
                InlineKeyboardButton("Другое", callback_data="other")
            ]
        ]
        
        await update.message.reply_text(
            text=self.messages['start'],
            reply_markup=InlineKeyboardMarkup(device_buttons)
        )
        
        await update.message.reply_text(" ", reply_markup=self.reply_keyboard)

    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        await query.answer()
        data = query.data
        user_id = query.from_user.id

        if data == "other":
            self.stats_manager.log_action(user_id, "other_selected")
            await query.edit_message_text(text=self.messages['other'], reply_markup=None)
        elif data.startswith("back_to_"):
            await self.handle_back(query, data)
        elif data.startswith("device_"):
            device_type = data.split("_")[1]
            self.stats_manager.log_action(user_id, "device_selected", device_type=device_type)
            await self.show_models(query, device_type)
        elif data.startswith("model_"):
            _, device_type, model = data.split("_")
            self.stats_manager.log_action(user_id, "model_selected", device_type=device_type, model=model)
            await self.show_numbers(query, device_type, model)
        elif data.startswith("number_"):
            _, device_type, model, number = data.split("_")
            self.stats_manager.log_action(user_id, "number_selected", device_type=device_type, model=model, number=number)
            await self.show_questions(query, device_type, model, number)
        elif data.startswith("question_"):
            await self.process_question(query, data)
                
        await context.bot.send_message(chat_id=query.message.chat_id, text=" ", reply_markup=self.reply_keyboard)

    async def handle_back(self, query, data: str) -> None:
        back_type = data.split("_")[2]
        if back_type == "start":
            await self.start_callback(query)
        elif back_type == "models":
            device_type = data.split("_")[3]
            await self.show_models(query, device_type)
        elif back_type == "numbers":
            _, _, _, device_type, model = data.split("_")
            await self.show_numbers(query, device_type, model)
        elif back_type == "questions":
            _, _, _, device_type, model, number = data.split("_")
            await self.show_questions(query, device_type, model, number)

    async def start_callback(self, query) -> None:
        device_buttons = [
            [
                InlineKeyboardButton("Сканер", callback_data="device_scanner"),
                InlineKeyboardButton("Принтер", callback_data="device_printer")
            ],
            [
                InlineKeyboardButton("Пейджеры", callback_data="device_pager"),
                InlineKeyboardButton("Другое", callback_data="other")
            ]
        ]
        await query.edit_message_text(text=self.messages['start'], reply_markup=InlineKeyboardMarkup(device_buttons))

    async def show_models(self, query, device_type: str) -> None:
        device = self.devices[device_type]
        models = list(device.models.items())
        
        model_buttons = [
            [
                InlineKeyboardButton(model1.name, callback_data=f"model_{device_type}_{model_key1}"),
                InlineKeyboardButton(model2.name, callback_data=f"model_{device_type}_{model_key2}")
            ]
            for (model_key1, model1), (model_key2, model2) in zip(models[::2], models[1::2])
        ]
        
        if len(models) % 2 != 0:
            model_key, model = models[-1]
            model_buttons.append([InlineKeyboardButton(model.name, callback_data=f"model_{device_type}_{model_key}")])
        
        model_buttons.append(self.create_back_button("back_to_start"))
        
        await query.edit_message_text(
            text=f"{device.name}. {self.messages['model']}",
            reply_markup=InlineKeyboardMarkup(model_buttons)
        )

    async def show_numbers(self, query, device_type: str, model: str) -> None:
        numbers = self.devices[device_type].models[model].numbers
        number_buttons = [
            [InlineKeyboardButton(num, callback_data=f"number_{device_type}_{model}_{num}")]
            for num in numbers
        ]
        
        number_buttons.append(self.create_back_button(f"back_to_models_{device_type}"))
        
        await query.edit_message_text(
            text=f"{self.devices[device_type].name} {self.devices[device_type].models[model].name}. {self.messages['number']}",
            reply_markup=InlineKeyboardMarkup(number_buttons)
        )

    async def show_questions(self, query, device_type: str, model: str, number: str) -> None:
        model_key = f"{device_type}/{model}/{number}"
        questions = {
            **self.model_questions.get(model_key, {}),
            **self.devices[device_type].common_questions
        }
        
        question_list = list(questions.keys())
        question_buttons = []

        for q1, q2 in zip(question_list[::2], question_list[1::2]):
            q1_id = self.make_question_id(device_type, model, number, q1)
            q2_id = self.make_question_id(device_type, model, number, q2)
            question_buttons.append([
                InlineKeyboardButton(q1[:64], callback_data=f"question_{q1_id}"),
                InlineKeyboardButton(q2[:64], callback_data=f"question_{q2_id}")
            ])

        if len(question_list) % 2 != 0:
            last_question = question_list[-1]
            last_id = self.make_question_id(device_type, model, number, last_question)
            question_buttons.append([
                InlineKeyboardButton(last_question[:64], callback_data=f"question_{last_id}")
            ])
        
        question_buttons.append(self.create_back_button(f"back_to_numbers_{device_type}_{model}"))
        
        await query.edit_message_text(
            text=f"{self.devices[device_type].name} {self.devices[device_type].models[model].name} {number}. {self.messages['questions']}",
            reply_markup=InlineKeyboardMarkup(question_buttons)
        )

    async def process_question(self, query, callback_data: str) -> None:
        _, q_id = callback_data.split("_", 1)
        user_id = query.from_user.id

        if q_id not in self.question_map:
            await query.edit_message_text("Решение не найдено", reply_markup=self.reply_keyboard)
            return

        device_type, model, number, question_text = self.question_map.pop(q_id)  # pop удаляет после использования
        model_key = f"{device_type}/{model}/{number}"

        # Логируем выбор вопроса
        self.stats_manager.log_action(
            user_id, 
            "question_selected", 
            device_type=device_type, 
            model=model, 
            number=number, 
            question=question_text
        )

        solution = (
            self.model_questions.get(model_key, {}).get(question_text) or
            self.devices[device_type].common_questions.get(question_text)
        )

        if not solution:
            await query.edit_message_text("Решение не найдено", reply_markup=self.reply_keyboard)
            return

        await self.send_content(query, solution, device_type, model, number, question_text)

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error(f"Ошибка: {context.error}")

async def test_daily_stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Команда для тестирования отправки ежедневной статистики"""
    if not update.message:
        return
    
    user_id = update.message.from_user.id
    
    # Проверяем, что команду запускает администратор
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("❌ У вас нет прав для выполнения этой команды.")
        return
    
    await update.message.reply_text("🔄 Тестируем отправку ежедневной статистики...")
    
    try:
        # Вызываем функцию отправки статистики
        await daily_stats_job(context)
        await update.message.reply_text("✅ Тест прошел успешно! Статистика отправлена.")
    except Exception as e:
        logger.error(f"Ошибка при тестировании статистики: {e}")
        await update.message.reply_text(f"❌ Ошибка при тестировании: {str(e)}")

def get_moscow_time():
    """Получение текущего времени в МСК"""
    moscow_tz = pytz.timezone('Europe/Moscow')
    return datetime.now(moscow_tz)

async def daily_stats_job(context: ContextTypes.DEFAULT_TYPE):
    """Задача для ежедневной отправки статистики"""
    try:
        bot_handler = context.bot_data.get('bot_handler')
        if not bot_handler:
            logger.error("BotHandler не найден в bot_data")
            return
            
        moscow_time = get_moscow_time()
        logger.info(f"Начинаем отправку ежедневной статистики... Время МСК: {moscow_time.strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Получаем статистику за текущий день (по МСК)
        today = moscow_time.strftime('%Y-%m-%d')
        stats = bot_handler.stats_manager.get_daily_stats(today)
        
        # Сохраняем статистику
        bot_handler.stats_manager.save_daily_stats(today, stats)
        
        # Форматируем сообщение
        message = bot_handler.stats_handler.format_stats_message(stats)
        
        # Отправляем сообщение
        await context.bot.send_message(
            chat_id=ADMIN_CHAT_ID,
            text=message,
            parse_mode='HTML'
        )
        
        logger.info(f"Ежедневная статистика отправлена в чат за {today}")
        
    except Exception as e:
        logger.error(f"Ошибка при отправке ежедневной статистики: {e}")
        # Пытаемся уведомить администратора об ошибке
        try:
            await context.bot.send_message(
                chat_id=ADMIN_CHAT_ID,
                text=f"❌ Ошибка при отправке ежедневной статистики: {str(e)}"
            )
        except Exception as notify_err:
            logger.error(f"Не удалось отправить сообщение об ошибке администратору: {notify_err}")

def scheduler_worker(application):
    """Рабочий поток планировщика"""
    while True:
        try:
            moscow_time = get_moscow_time()
            
            # Проверяем, наступило ли время отправки (23:55 МСК)
            if moscow_time.hour == 23 and moscow_time.minute == 55:
                logger.info(f"Наступило время отправки статистики: {moscow_time.strftime('%Y-%m-%d %H:%M:%S')} МСК")
                
                # Создаем контекст для отправки статистики
                class MockContext:
                    def __init__(self, app):
                        self.bot_data = app.bot_data
                        self.bot = app.bot
                
                context = MockContext(application)
                
                # Запускаем отправку статистики в новом потоке событий
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(daily_stats_job(context))
                loop.close()
                
                # Ждем минуту, чтобы не отправить дважды
                time.sleep(60)
            
            # Проверяем каждые 30 секунд
            time.sleep(30)
            
        except Exception as e:
            logger.error(f"Ошибка в планировщике: {e}")
            time.sleep(60)

def start_scheduler(application):
    """Запуск планировщика в отдельном потоке"""
    scheduler_thread = threading.Thread(target=scheduler_worker, args=(application,), daemon=True)
    scheduler_thread.start()
    logger.info("Планировщик ежедневной статистики запущен в отдельном потоке")


def main() -> None:
    bot_handler = BotHandler()
    application = Application.builder().token(TOKEN).job_queue(None).build()
    
    # Сохраняем экземпляр бота в bot_data для доступа из задач
    application.bot_data['bot_handler'] = bot_handler
    
    application.add_error_handler(error_handler)
    application.add_handler(CommandHandler("start", bot_handler.start))
    application.add_handler(CommandHandler("statsb1", bot_handler.stats_handler.stats_command))
    application.add_handler(CommandHandler("mystatsb1", bot_handler.stats_handler.user_stats_command))
    application.add_handler(CommandHandler("weekstatsb1", bot_handler.stats_handler.weekly_stats_command))
    application.add_handler(CommandHandler("monthstatsb1", bot_handler.stats_handler.monthly_stats_command))
    application.add_handler(CommandHandler("teststatsb1", test_daily_stats_command))
    application.add_handler(CallbackQueryHandler(bot_handler.handle_callback))
    application.add_handler(MessageHandler(filters.Text(["/start"]), bot_handler.start))
    
    # Запускаем планировщик ежедневной статистики
    start_scheduler(application)
    
    logger.info("Бот запущен с интегрированным планировщиком ежедневной статистики...")
    application.run_polling()

if __name__ == '__main__':
    main()
