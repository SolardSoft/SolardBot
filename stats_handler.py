"""
Обработчик команд статистики для Telegram бота
"""

import os
import logging
from datetime import datetime, timedelta
from typing import Dict
from telegram import Update
from telegram.ext import ContextTypes

from statistics import StatisticsManager

# Константы для админов
ADMIN_CHAT_ID = "-1003131568927"
ADMIN_IDS = [550680968, 332518486, 7068694127, 1118098514]

logger = logging.getLogger(__name__)


class StatsHandler:
    """Класс для обработки команд статистики"""
    
    def __init__(self, stats_manager: StatisticsManager, devices: Dict):
        self.stats_manager = stats_manager
        self.devices = devices
    
    def format_stats_message(self, stats: Dict) -> str:
        """Форматирование сообщения со статистикой"""
        message = f"📊 <b>Статистика Solard бота за {stats['date']}</b>\n\n"
        
        # Общая статистика
        message += f"👥 <b>Пользователи:</b>\n"
        message += f"• Всего пользователей: {stats['total_users']}\n"
        message += f"• Новых за день: {stats['new_users']}\n"
        message += f"• Всего действий: {stats['total_actions']}\n\n"
        
        # Статистика по номерам устройств
        if stats['device_stats']:
            message += f"🔧 <b>Популярные номера устройств:</b>\n"
            for number, count in stats['device_stats'].items():
                message += f"• {number}: {count}\n"
            message += "\n"
        
        # Статистика по вопросам
        if stats['question_stats']:
            message += f"❓ <b>Популярные вопросы:</b>\n"
            for question, count in list(stats['question_stats'].items())[:5]:
                message += f"• {question}: {count}\n"
            message += "\n"
        
        # Топ пользователей
        if stats['top_users']:
            message += f"⭐ <b>Активные пользователи:</b>\n"
            for user_id, username, first_name, action_count in stats['top_users']:
                display_name = username or first_name or f"ID{user_id}"
                message += f"• {display_name}: {action_count} действий\n"
        
        return message
    
    async def send_daily_stats(self, context: ContextTypes.DEFAULT_TYPE):
        """Отправка ежедневной статистики в админский чат"""
        if not ADMIN_CHAT_ID:
            logger.warning("ADMIN_CHAT_ID не настроен, статистика не будет отправлена")
            return
        
        try:
            # Получаем статистику за вчерашний день
            yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
            stats = self.stats_manager.get_daily_stats(yesterday)
            
            # Сохраняем статистику
            self.stats_manager.save_daily_stats(yesterday, stats)
            
            # Форматируем и отправляем сообщение
            message = self.format_stats_message(stats)
            
            await context.bot.send_message(
                chat_id=ADMIN_CHAT_ID,
                text=message,
                parse_mode='HTML'
            )
            
            logger.info(f"Ежедневная статистика отправлена в админский чат за {yesterday}")
            
        except Exception as e:
            logger.error(f"Ошибка при отправке ежедневной статистики: {e}")
    
    async def stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда для получения статистики"""
        if not update.message:
            return
        
        user_id = update.message.from_user.id
        
        # Проверяем, является ли пользователь админом
        # Отладочная информация
        logger.info(f"Пользователь {user_id} пытается получить статистику")
        logger.info(f"ADMIN_CHAT_ID: {ADMIN_CHAT_ID}")
        logger.info(f"ADMIN_IDS: {ADMIN_IDS}")
        logger.info(f"Проверка прав: user_id in ADMIN_IDS = {user_id in ADMIN_IDS}")
        logger.info(f"Проверка прав: str(user_id) == ADMIN_CHAT_ID = {str(user_id) == ADMIN_CHAT_ID}")
        
        if user_id not in ADMIN_IDS and str(user_id) != ADMIN_CHAT_ID:
            await update.message.reply_text(f"❌ У вас нет прав для просмотра статистики\nВаш ID: {user_id}\nОжидаемые ID: {ADMIN_IDS}\n\nИспользуйте команды:\n• /statsb1 - статистика за день\n• /mystatsb1 - персональная статистика\n• /weekstatsb1 - статистика за неделю\n• /monthstatsb1 - статистика за месяц")
            return
        
        try:
            # Получаем статистику за сегодня
            logger.info("Получаем ежедневную статистику...")
            today_stats = self.stats_manager.get_daily_stats()
            logger.info(f"Ежедневная статистика: {today_stats}")
            
            # Получаем недельную статистику
            logger.info("Получаем недельную статистику...")
            weekly_stats = self.stats_manager.get_weekly_stats()
            logger.info(f"Недельная статистика: {weekly_stats}")
            
            message = self.format_stats_message(today_stats)
            
            # Добавляем недельную статистику
            message += f"\n📈 <b>Статистика за неделю:</b>\n"
            message += f"• Уникальных пользователей: {weekly_stats['unique_users']}\n"
            message += f"• Всего действий: {weekly_stats['total_actions']}\n"
            
            if weekly_stats['daily_actions']:
                message += f"\n📅 <b>Активность по дням:</b>\n"
                for date, actions in weekly_stats['daily_actions'].items():
                    message += f"• {date}: {actions} действий\n"
            
            logger.info(f"Отправляем сообщение: {message}")
            await update.message.reply_text(message, parse_mode='HTML')
            
        except Exception as e:
            logger.error(f"Ошибка при получении статистики: {e}", exc_info=True)
            await update.message.reply_text(f"❌ Ошибка при получении статистики: {str(e)}")
    
    async def user_stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда для получения статистики конкретного пользователя"""
        if not update.message:
            return
        
        user_id = update.message.from_user.id
        
        # Проверяем права доступа
        # Отладочная информация
        logger.info(f"Пользователь {user_id} пытается получить персональную статистику")
        logger.info(f"ADMIN_CHAT_ID: {ADMIN_CHAT_ID}")
        logger.info(f"ADMIN_IDS: {ADMIN_IDS}")
        
        if user_id not in ADMIN_IDS and str(user_id) != ADMIN_CHAT_ID:
            await update.message.reply_text(f"❌ У вас нет прав для просмотра статистики\nВаш ID: {user_id}\nОжидаемые ID: {ADMIN_IDS}\n\nИспользуйте команды:\n• /statsb1 - статистика за день\n• /mystatsb1 - персональная статистика\n• /weekstatsb1 - статистика за неделю\n• /monthstatsb1 - статистика за месяц")
            return
        
        try:
            # Получаем статистику пользователя
            user_stats = self.stats_manager.get_user_stats(user_id)
            
            if not user_stats:
                await update.message.reply_text("❌ Статистика пользователя не найдена")
                return
            
            message = f"👤 <b>Статистика пользователя</b>\n\n"
            
            user_info = user_stats['user_info']
            message += f"<b>Информация:</b>\n"
            message += f"• Username: @{user_info['username'] or 'не указан'}\n"
            message += f"• Имя: {user_info['first_name'] or 'не указано'}\n"
            message += f"• Фамилия: {user_info['last_name'] or 'не указана'}\n"
            message += f"• Первый визит: {user_info['first_seen']}\n"
            message += f"• Последний визит: {user_info['last_seen']}\n"
            message += f"• Всего действий: {user_stats['total_actions']}\n\n"
            
            if user_stats['device_stats']:
                message += f"<b>Популярные номера устройств:</b>\n"
                for number, count in user_stats['device_stats'].items():
                    message += f"• {number}: {count}\n"
                message += "\n"
            
            if user_stats['recent_actions']:
                message += f"<b>Последние действия:</b>\n"
                for action in user_stats['recent_actions'][:5]:
                    action_type, device_type, model, number, question, timestamp = action
                    action_text = f"{action_type}"
                    if device_type:
                        action_text += f" ({device_type}"
                        if model:
                            action_text += f" {model}"
                        if number:
                            action_text += f" {number}"
                        action_text += ")"
                    message += f"• {action_text}: {timestamp}\n"
            
            await update.message.reply_text(message, parse_mode='HTML')
            
        except Exception as e:
            logger.error(f"Ошибка при получении статистики пользователя: {e}")
            await update.message.reply_text("❌ Ошибка при получении статистики пользователя")
    
    async def weekly_stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда для получения недельной статистики"""
        try:
            user_id = update.message.from_user.id
            
            # Проверяем права доступа
            if user_id not in ADMIN_IDS and str(user_id) != ADMIN_CHAT_ID:
                await update.message.reply_text(f"❌ У вас нет прав для просмотра статистики\nВаш ID: {user_id}\nОжидаемые ID: {ADMIN_IDS}\n\nИспользуйте команды:\n• /statsb1 - статистика за день\n• /mystatsb1 - персональная статистика\n• /weekstatsb1 - статистика за неделю\n• /monthstatsb1 - статистика за месяц")
                return
            
            # Получаем недельную статистику
            weekly_stats = self.stats_manager.get_weekly_stats()
            
            # Форматируем сообщение
            message = f"📊 <b>Статистика Solard за неделю</b>\n\n"
            message += f"👥 <b>Пользователи:</b>\n"
            message += f"• Уникальных пользователей: {weekly_stats['unique_users']}\n"
            message += f"• Всего действий: {weekly_stats['total_actions']}\n\n"
            
            # Статистика по дням
            if weekly_stats['daily_actions']:
                message += f"📅 <b>Активность по дням:</b>\n"
                for date, actions in weekly_stats['daily_actions'].items():
                    message += f"• {date}: {actions} действий\n"
                message += "\n"
            
            # Статистика по номерам устройств
            if weekly_stats['device_stats']:
                message += f"🔧 <b>Популярные номера устройств:</b>\n"
                for number, count in weekly_stats['device_stats'].items():
                    message += f"• {number}: {count}\n"
                message += "\n"
            
            # Статистика по вопросам
            if weekly_stats['question_stats']:
                message += f"❓ <b>Популярные вопросы:</b>\n"
                for question, count in list(weekly_stats['question_stats'].items())[:5]:
                    message += f"• {question}: {count}\n"
                message += "\n"
            
            # Топ пользователи
            if weekly_stats['top_users']:
                message += f"⭐ <b>Топ пользователи:</b>\n"
                for user_id, username, first_name, action_count in weekly_stats['top_users']:
                    display_name = username or first_name or f"ID{user_id}"
                    message += f"• {display_name}: {action_count} действий\n"
                message += "\n"
            
            await update.message.reply_text(message, parse_mode='HTML')
            
        except Exception as e:
            logger.error(f"Ошибка при получении недельной статистики: {e}")
            await update.message.reply_text("❌ Ошибка при получении недельной статистики")
    
    async def monthly_stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда для получения месячной статистики"""
        try:
            user_id = update.message.from_user.id
            
            # Проверяем права доступа
            if user_id not in ADMIN_IDS and str(user_id) != ADMIN_CHAT_ID:
                await update.message.reply_text(f"❌ У вас нет прав для просмотра статистики\nВаш ID: {user_id}\nОжидаемые ID: {ADMIN_IDS}\n\nИспользуйте команды:\n• /statsb1 - статистика за день\n• /mystatsb1 - персональная статистика\n• /weekstatsb1 - статистика за неделю\n• /monthstatsb1 - статистика за месяц\n• /monthstatsb1 - статистика за месяц")
                return
            
            # Получаем месячную статистику
            monthly_stats = self.stats_manager.get_monthly_stats()
            
            # Форматируем сообщение
            message = f"📊 <b>Статистика Solard за месяц</b>\n\n"
            message += f"👥 <b>Пользователи:</b>\n"
            message += f"• Уникальных пользователей: {monthly_stats['unique_users']}\n"
            message += f"• Всего действий: {monthly_stats['total_actions']}\n\n"
            
            # Статистика по неделям
            if monthly_stats['weekly_actions']:
                message += f"📅 <b>Активность по неделям:</b>\n"
                for week, actions in monthly_stats['weekly_actions'].items():
                    message += f"• Неделя {week}: {actions} действий\n"
                message += "\n"
            
            # Статистика по дням (показываем только последние 7 дней для краткости)
            if monthly_stats['daily_actions']:
                recent_days = dict(list(monthly_stats['daily_actions'].items())[-7:])
                message += f"📅 <b>Активность по дням (последние 7 дней):</b>\n"
                for date, actions in recent_days.items():
                    message += f"• {date}: {actions} действий\n"
                message += "\n"
            
            # Статистика по номерам устройств
            if monthly_stats['device_stats']:
                message += f"🔧 <b>Популярные номера устройств:</b>\n"
                for number, count in monthly_stats['device_stats'].items():
                    message += f"• {number}: {count}\n"
                message += "\n"
            
            # Статистика по вопросам
            if monthly_stats['question_stats']:
                message += f"❓ <b>Популярные вопросы:</b>\n"
                for question, count in list(monthly_stats['question_stats'].items())[:5]:
                    message += f"• {question}: {count}\n"
                message += "\n"
            
            # Топ пользователи
            if monthly_stats['top_users']:
                message += f"⭐ <b>Топ пользователи:</b>\n"
                for user_id, username, first_name, action_count in monthly_stats['top_users']:
                    display_name = username or first_name or f"ID{user_id}"
                    message += f"• {display_name}: {action_count} действий\n"
                message += "\n"
            
            await update.message.reply_text(message, parse_mode='HTML')
            
        except Exception as e:
            logger.error(f"Ошибка при получении месячной статистики: {e}")
            await update.message.reply_text("❌ Ошибка при получении месячной статистики")
