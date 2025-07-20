from dotenv import load_dotenv
from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Update,
    ReplyKeyboardMarkup,
    KeyboardButton,
    InputFile
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

# Настройка логгирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

load_dotenv('token.env')
TOKEN = os.getenv("TOKEN")

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
        self.content_base_path = r"D:\programs\SolardBot"
        self.devices = {
            'scanner': Device(
                name="Сканер",
                models={
                    'netum': DeviceModel(name="Netum", numbers=["c750", "x200", "v100"]),
                    'kefar': DeviceModel(name="Kefar", numbers=["k10", "k20"])
                },
                common_questions={
                    "Инструкция": Solution(text="Инструкция на русском языке:", content_type="file")
                }
            ),
            'printer': Device(
                name="Принтер",
                models={
                    'xprinter': DeviceModel(name="XPrinter", numbers=["p100", "p200"])
                },
                common_questions={}
            ),
            'pager': Device(
                name="Пейджер",
                models={
                    'td': DeviceModel(name="TD", numbers=["td100"])
                },
                common_questions={}
            )
        }
        
        self.model_questions = {
            'scanner/netum/c750': {
                "Не включается": Solution(text="Проверьте питание и кнопку включения"),
                "Не сканирует": Solution(text="Проверьте подключение к компьютеру")
            },
            'scanner/kefar/k10': {
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
Хорошо. Теперь выберите модель устройства, она указана на коробке или маркетплейсе, где приобрели товар.
Следующим шагом нужно будет выбрать номер.

Пример: модель - Netum, номер - C750
""",

#################

            'number': """
Выберите номер устройства.

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
""",

#################

            'no_content': """
[Контент недоступен]
"""
        }

        # Reply-клавиатура с кнопкой /start
        self.reply_keyboard = ReplyKeyboardMarkup(
            [[KeyboardButton("/start")]],
            resize_keyboard=True,
            one_time_keyboard=False
        )

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
        
        if content_type == "image":
            path = os.path.join(
                self.content_base_path,
                "images",
                safe_device,
                safe_model,
                safe_number,
                f"{safe_question}.jpg"
            )
        elif content_type == "file":
            path = os.path.join(
                self.content_base_path,
                "files",
                safe_device,
                safe_model,
                safe_number,
                f"{safe_question}.pdf"
            )
        return path

    async def send_content(self, query, solution: Solution, device_type: str, model: str, number: str, question: str) -> None:
        content_path = self.get_content_path(device_type, model, number, question, solution.content_type)
        
        try:
            if not content_path:
                await query.message.reply_text(
                    solution.text,
                    reply_markup=self.reply_keyboard
                )
            elif solution.content_type == "image":
                with open(content_path, 'rb') as photo:
                    await query.message.reply_photo(
                        photo=photo,
                        caption=solution.text,
                        reply_markup=self.reply_keyboard
                    )
            elif solution.content_type == "file":
                with open(content_path, 'rb') as file:
                    await query.message.reply_document(
                        document=file,
                        caption=solution.text,
                        reply_markup=self.reply_keyboard
                    )
            await query.delete_message()
        except FileNotFoundError:
            await query.edit_message_text(
                text=f"{solution.text}\n\n{self.messages['no_content']}",
                reply_markup=self.reply_keyboard
            )
        except Exception as e:
            logger.error(f"Ошибка при отправке контента: {e}")
            await query.edit_message_text(
                text=f"Произошла ошибка: {str(e)}",
                reply_markup=self.reply_keyboard
            )

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not update.message:
            return
            
        device_buttons = [
            [
                InlineKeyboardButton("Сканер", callback_data="device_scanner"),
                InlineKeyboardButton("Принтер", callback_data="device_printer")
            ],
            [
                InlineKeyboardButton("Пейджер", callback_data="device_pager"),
                InlineKeyboardButton("Другое", callback_data="other")
            ]
        ]
        
        await update.message.reply_text(
            text=self.messages['start'],
            reply_markup=InlineKeyboardMarkup(device_buttons)
        )
        
        await update.message.reply_text(
            text=" ",
            reply_markup=self.reply_keyboard
        )

    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        await query.answer()
        data = query.data
        
        try:
            if data == "other":
                await query.edit_message_text(
                    text=self.messages['other'],
                    reply_markup=None
                )
            elif data.startswith("back_to_"):
                await self.handle_back(query, data)
            elif data.startswith("device_"):
                device_type = data.split("_")[1]
                await self.show_models(query, device_type)
            elif data.startswith("model_"):
                _, device_type, model = data.split("_")
                await self.show_numbers(query, device_type, model)
            elif data.startswith("number_"):
                _, device_type, model, number = data.split("_")
                await self.show_questions(query, device_type, model, number)
            elif data.startswith("question_"):
                await self.process_question(query, data)
                
            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text=" ",
                reply_markup=self.reply_keyboard
            )
                
        except Exception as e:
            logger.error(f"Ошибка обработки callback: {e}")
            await query.edit_message_text(
                text="Произошла ошибка при обработке запроса",
                reply_markup=self.reply_keyboard
            )

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

    async def start_callback(self, query) -> None:
        device_buttons = [
            [
                InlineKeyboardButton("Сканер", callback_data="device_scanner"),
                InlineKeyboardButton("Принтер", callback_data="device_printer")
            ],
            [
                InlineKeyboardButton("Пейджер", callback_data="device_pager"),
                InlineKeyboardButton("Другое", callback_data="other")
            ]
        ]
        
        await query.edit_message_text(
            text=self.messages['start'],
            reply_markup=InlineKeyboardMarkup(device_buttons)
        )

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
        
        question_buttons = [
            [InlineKeyboardButton(q[:64], callback_data=f"question_{device_type}_{model}_{number}_{q}")]
            for q in questions.keys()
        ]
        
        question_buttons.append(self.create_back_button(f"back_to_numbers_{device_type}_{model}"))
        
        await query.edit_message_text(
            text=f"{self.devices[device_type].name} {self.devices[device_type].models[model].name} {number}. {self.messages['questions']}",
            reply_markup=InlineKeyboardMarkup(question_buttons)
        )

    async def process_question(self, query, callback_data: str) -> None:
        _, device_type, model, number, question = callback_data.split("_", 4)
        model_key = f"{device_type}/{model}/{number}"
        
        solution = (
            self.model_questions.get(model_key, {}).get(question) or
            self.devices[device_type].common_questions.get(question)
        )
        
        if not solution:
            await query.edit_message_text(
                text="Решение не найдено",
                reply_markup=self.reply_keyboard
            )
            return
        
        await self.send_content(query, solution, device_type, model, number, question)

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error(f"Ошибка: {context.error}")

def main() -> None:
    bot_handler = BotHandler()
    application = Application.builder().token(TOKEN).build()
    
    application.add_error_handler(error_handler)
    application.add_handler(CommandHandler("start", bot_handler.start))
    application.add_handler(CallbackQueryHandler(bot_handler.handle_callback))
    application.add_handler(MessageHandler(filters.Text(["/start"]), bot_handler.start))
    
    logger.info("Бот запущен...")
    application.run_polling()

if __name__ == '__main__':
    main()