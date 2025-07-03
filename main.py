from dotenv import load_dotenv
import os

load_dotenv('token.env') #Имя файла с токеном
TOKEN = os.getenv("TOKEN")