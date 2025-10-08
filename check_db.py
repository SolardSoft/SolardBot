import sqlite3
import os

# Проверяем базу данных статистики
db_path = "bot_statistics.db"

if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Проверяем таблицы
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()
    print("Таблицы в базе данных:")
    for table in tables:
        print(f"  - {table[0]}")
    
    # Проверяем количество пользователей
    cursor.execute("SELECT COUNT(*) FROM users;")
    user_count = cursor.fetchone()[0]
    print(f"\nКоличество пользователей: {user_count}")
    
    # Проверяем количество действий
    cursor.execute("SELECT COUNT(*) FROM user_actions;")
    action_count = cursor.fetchone()[0]
    print(f"Количество действий: {action_count}")
    
    # Показываем последние действия
    cursor.execute("SELECT * FROM user_actions ORDER BY timestamp DESC LIMIT 5;")
    recent_actions = cursor.fetchall()
    print(f"\nПоследние 5 действий:")
    for action in recent_actions:
        print(f"  {action}")
    
    conn.close()
else:
    print("База данных не найдена!")
