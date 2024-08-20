import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Get the variables
TOKEN = os.getenv('TELEGRAM_BOT_API')
TIMEZONE = os.getenv('TIMEZONE')
TIMEZONE_COMMON_NAME = os.getenv('TIMEZONE_COMMON_NAME')
BOT_USERNAME = os.getenv('TELEGRAM_BOT_USERNAME')

# Use the variables
print(f"Token: {TOKEN}")
print(f"Timezone: {TIMEZONE}")
print(f"Timezone Common Name: {TIMEZONE_COMMON_NAME}")
print(f"Bot Username: {BOT_USERNAME}")

