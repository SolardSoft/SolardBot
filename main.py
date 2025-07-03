from dotenv import load_dotenv
import os

load_dotenv('token.env')
TOKEN = os.getenv("TOKEN")
print(f"Ваш токен: {TOKEN}")  # Проверка