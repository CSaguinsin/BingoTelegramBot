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


# Get the additional variables
MONDAY_API_TOKEN = os.getenv('MONDAY_API_TOKEN')
MONDAY_BOARD_ID = os.getenv('MONDAY_BOARD_ID')

# Use the additional variables
print(f"Monday API Token: {MONDAY_API_TOKEN}")
print(f"Monday Board ID: {MONDAY_BOARD_ID}")

