import os
from dotenv import load_dotenv

load_dotenv()

URL_DATABASE = os.getenv("URL_DATABASE")
SECRET_KEY = os.getenv("SECRET_KEY")