"""
Модуль для работы со статистикой Telegram бота техподдержки
"""

import sqlite3
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class StatisticsManager:
    """Класс для управления статистикой бота"""
    
    def __init__(self, db_path: str = "bot_statistics.db"):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """Инициализация базы данных для статистики"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Таблица для отслеживания пользователей
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Таблица для отслеживания действий пользователей
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_actions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                action_type TEXT NOT NULL,
                device_type TEXT,
                model TEXT,
                number TEXT,
                question TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
        ''')
        
        # Таблица для ежедневной статистики
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS daily_stats (
                date TEXT PRIMARY KEY,
                total_users INTEGER DEFAULT 0,
                new_users INTEGER DEFAULT 0,
                total_actions INTEGER DEFAULT 0,
                device_stats TEXT,  -- JSON строка с статистикой по устройствам
                question_stats TEXT,  -- JSON строка с статистикой по вопросам
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def update_user_info(self, user_id: int, username: str = None, first_name: str = None, last_name: str = None):
        """Обновление информации о пользователе"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Проверяем, существует ли пользователь
        cursor.execute('SELECT user_id FROM users WHERE user_id = ?', (user_id,))
        exists = cursor.fetchone()
        
        if exists:
            # Обновляем существующего пользователя
            cursor.execute('''
                UPDATE users 
                SET username = ?, first_name = ?, last_name = ?, last_seen = CURRENT_TIMESTAMP
                WHERE user_id = ?
            ''', (username, first_name, last_name, user_id))
        else:
            # Добавляем нового пользователя
            cursor.execute('''
                INSERT INTO users (user_id, username, first_name, last_name)
                VALUES (?, ?, ?, ?)
            ''', (user_id, username, first_name, last_name))
        
        conn.commit()
        conn.close()
    
    def log_action(self, user_id: int, action_type: str, device_type: str = None, 
                   model: str = None, number: str = None, question: str = None):
        """Логирование действия пользователя"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO user_actions (user_id, action_type, device_type, model, number, question)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (user_id, action_type, device_type, model, number, question))
        
        conn.commit()
        conn.close()
    
    def get_daily_stats(self, date: str = None) -> Dict:
        """Получение статистики за день"""
        if date is None:
            date = datetime.now().strftime('%Y-%m-%d')
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Общее количество пользователей
        cursor.execute('SELECT COUNT(*) FROM users')
        total_users = cursor.fetchone()[0]
        
        # Новые пользователи за день
        cursor.execute('''
            SELECT COUNT(*) FROM users 
            WHERE DATE(first_seen) = ?
        ''', (date,))
        new_users = cursor.fetchone()[0]
        
        # Общее количество действий за день
        cursor.execute('''
            SELECT COUNT(*) FROM user_actions 
            WHERE DATE(timestamp) = ?
        ''', (date,))
        total_actions = cursor.fetchone()[0]
        
        # Статистика по моделям и номерам устройств за день
        cursor.execute('''
            SELECT number, COUNT(*) as count
            FROM user_actions
            WHERE DATE(timestamp) = ? AND number IS NOT NULL
            GROUP BY number
            ORDER BY count DESC
        ''', (date,))
        device_stats = dict(cursor.fetchall())
        
        # Статистика по вопросам за день
        cursor.execute('''
            SELECT question, COUNT(*) as count
            FROM user_actions 
            WHERE DATE(timestamp) = ? AND question IS NOT NULL
            GROUP BY question
            ORDER BY count DESC
            LIMIT 10
        ''', (date,))
        question_stats = dict(cursor.fetchall())
        
        # Топ пользователей за день
        cursor.execute('''
            SELECT u.user_id, u.username, u.first_name, COUNT(ua.id) as action_count
            FROM users u
            JOIN user_actions ua ON u.user_id = ua.user_id
            WHERE DATE(ua.timestamp) = ?
            GROUP BY u.user_id, u.username, u.first_name
            ORDER BY action_count DESC
            LIMIT 5
        ''', (date,))
        top_users = cursor.fetchall()
        
        conn.close()
        
        return {
            'date': date,
            'total_users': total_users,
            'new_users': new_users,
            'total_actions': total_actions,
            'device_stats': device_stats,
            'question_stats': question_stats,
            'top_users': top_users
        }
    
    def get_weekly_stats(self) -> Dict:
        """Получение статистики за неделю"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Статистика по дням недели
        cursor.execute('''
            SELECT DATE(timestamp) as date, COUNT(*) as actions
            FROM user_actions 
            WHERE timestamp >= datetime('now', '-7 days')
            GROUP BY DATE(timestamp)
            ORDER BY date
        ''')
        daily_actions = dict(cursor.fetchall())
        
        # Общая статистика за неделю
        cursor.execute('''
            SELECT COUNT(DISTINCT user_id) as unique_users, COUNT(*) as total_actions
            FROM user_actions 
            WHERE timestamp >= datetime('now', '-7 days')
        ''')
        weekly_total = cursor.fetchone()
        
        # Статистика по номерам устройств за неделю
        cursor.execute('''
            SELECT number, COUNT(*) as count
            FROM user_actions
            WHERE timestamp >= datetime('now', '-7 days') AND number IS NOT NULL
            GROUP BY number
            ORDER BY count DESC
        ''')
        device_stats = dict(cursor.fetchall())
        
        # Статистика по вопросам за неделю
        cursor.execute('''
            SELECT question, COUNT(*) as count
            FROM user_actions
            WHERE timestamp >= datetime('now', '-7 days') AND question IS NOT NULL
            GROUP BY question
            ORDER BY count DESC
        ''')
        question_stats = dict(cursor.fetchall())
        
        # Топ пользователи за неделю
        cursor.execute('''
            SELECT u.user_id, u.username, u.first_name, COUNT(*) as action_count
            FROM user_actions ua
            JOIN users u ON ua.user_id = u.user_id
            WHERE ua.timestamp >= datetime('now', '-7 days')
            GROUP BY ua.user_id
            ORDER BY action_count DESC
            LIMIT 5
        ''')
        top_users = cursor.fetchall()
        
        conn.close()
        
        return {
            'daily_actions': daily_actions,
            'unique_users': weekly_total[0],
            'total_actions': weekly_total[1],
            'device_stats': device_stats,
            'question_stats': question_stats,
            'top_users': top_users
        }
    
    def get_monthly_stats(self) -> Dict:
        """Получение статистики за месяц"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Статистика по дням месяца
        cursor.execute('''
            SELECT DATE(timestamp) as date, COUNT(*) as actions
            FROM user_actions 
            WHERE timestamp >= datetime('now', '-30 days')
            GROUP BY DATE(timestamp)
            ORDER BY date
        ''')
        daily_actions = dict(cursor.fetchall())
        
        # Общая статистика за месяц
        cursor.execute('''
            SELECT COUNT(DISTINCT user_id) as unique_users, COUNT(*) as total_actions
            FROM user_actions 
            WHERE timestamp >= datetime('now', '-30 days')
        ''')
        monthly_total = cursor.fetchone()
        
        # Статистика по номерам устройств за месяц
        cursor.execute('''
            SELECT number, COUNT(*) as count
            FROM user_actions
            WHERE timestamp >= datetime('now', '-30 days') AND number IS NOT NULL
            GROUP BY number
            ORDER BY count DESC
        ''')
        device_stats = dict(cursor.fetchall())
        
        # Статистика по вопросам за месяц
        cursor.execute('''
            SELECT question, COUNT(*) as count
            FROM user_actions
            WHERE timestamp >= datetime('now', '-30 days') AND question IS NOT NULL
            GROUP BY question
            ORDER BY count DESC
        ''')
        question_stats = dict(cursor.fetchall())
        
        # Топ пользователи за месяц
        cursor.execute('''
            SELECT u.user_id, u.username, u.first_name, COUNT(*) as action_count
            FROM user_actions ua
            JOIN users u ON ua.user_id = u.user_id
            WHERE ua.timestamp >= datetime('now', '-30 days')
            GROUP BY ua.user_id
            ORDER BY action_count DESC
            LIMIT 10
        ''')
        top_users = cursor.fetchall()
        
        # Статистика по неделям месяца
        cursor.execute('''
            SELECT strftime('%Y-%W', timestamp) as week, COUNT(*) as actions
            FROM user_actions 
            WHERE timestamp >= datetime('now', '-30 days')
            GROUP BY strftime('%Y-%W', timestamp)
            ORDER BY week
        ''')
        weekly_actions = dict(cursor.fetchall())
        
        conn.close()
        
        return {
            'daily_actions': daily_actions,
            'weekly_actions': weekly_actions,
            'unique_users': monthly_total[0],
            'total_actions': monthly_total[1],
            'device_stats': device_stats,
            'question_stats': question_stats,
            'top_users': top_users
        }
    
    def save_daily_stats(self, date: str, stats: Dict):
        """Сохранение ежедневной статистики"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO daily_stats 
            (date, total_users, new_users, total_actions, device_stats, question_stats)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            date, 
            stats['total_users'], 
            stats['new_users'], 
            stats['total_actions'],
            json.dumps(stats['device_stats']),
            json.dumps(stats['question_stats'])
        ))
        
        conn.commit()
        conn.close()
    
    def get_user_stats(self, user_id: int) -> Dict:
        """Получение статистики конкретного пользователя"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Информация о пользователе
        cursor.execute('''
            SELECT username, first_name, last_name, first_seen, last_seen
            FROM users WHERE user_id = ?
        ''', (user_id,))
        user_info = cursor.fetchone()
        
        if not user_info:
            conn.close()
            return None
        
        # Количество действий пользователя
        cursor.execute('''
            SELECT COUNT(*) FROM user_actions WHERE user_id = ?
        ''', (user_id,))
        total_actions = cursor.fetchone()[0]
        
        # Статистика по моделям и номерам устройств
        cursor.execute('''
            SELECT number, COUNT(*) as count
            FROM user_actions
            WHERE user_id = ? AND number IS NOT NULL
            GROUP BY number
            ORDER BY count DESC
        ''', (user_id,))
        device_stats = dict(cursor.fetchall())
        
        # Последние действия
        cursor.execute('''
            SELECT action_type, device_type, model, number, question, timestamp
            FROM user_actions 
            WHERE user_id = ?
            ORDER BY timestamp DESC
            LIMIT 10
        ''', (user_id,))
        recent_actions = cursor.fetchall()
        
        conn.close()
        
        return {
            'user_info': {
                'username': user_info[0],
                'first_name': user_info[1],
                'last_name': user_info[2],
                'first_seen': user_info[3],
                'last_seen': user_info[4]
            },
            'total_actions': total_actions,
            'device_stats': device_stats,
            'recent_actions': recent_actions
        }
    
    def cleanup_old_data(self, days_to_keep: int = 90):
        """Очистка старых данных (по умолчанию оставляем 90 дней)"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Удаляем старые действия
        cursor.execute('''
            DELETE FROM user_actions 
            WHERE timestamp < datetime('now', '-{} days')
        '''.format(days_to_keep))
        
        deleted_actions = cursor.rowcount
        
        # Удаляем старую ежедневную статистику
        cursor.execute('''
            DELETE FROM daily_stats 
            WHERE date < date('now', '-{} days')
        '''.format(days_to_keep))
        
        deleted_stats = cursor.rowcount
        
        conn.commit()
        conn.close()
        
        logger.info(f"Очищено {deleted_actions} старых действий и {deleted_stats} записей статистики")
        return deleted_actions, deleted_stats
