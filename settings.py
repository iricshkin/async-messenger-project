import os

from dotenv import load_dotenv

load_dotenv()

HOST = os.getenv('HOST', '127.0.0.1')
PORT = os.getenv('PORT', 8000)
LIMIT_COMPLAINT = 3
LIMIT_MESSAGE = 20
