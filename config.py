import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Get the variables
TOKEN = os.getenv('TELEGRAM_BOT_API')
TIMEZONE = os.getenv('TIMEZONE')
TIMEZONE_COMMON_NAME = os.getenv('TIMEZONE_COMMON_NAME')
BOT_USERNAME = os.getenv('TELEGRAM_BOT_USERNAME')
IMG_OCR_API_KEY  = os.getenv('IMG_OCR_API_KEY')  # Corrected line

# Use the variables
print(f"Token: {TOKEN}")
print(f"Timezone: {TIMEZONE}")
print(f"Timezone Common Name: {TIMEZONE_COMMON_NAME}")
print(f"Bot Username: {BOT_USERNAME}")
print(f"IMGOCR API Key: {IMG_OCR_API_KEY}")

# Get the additional variables
MONDAY_API_TOKEN = os.getenv('MONDAY_API_TOKEN')
POLICY_BOARD_ID = os.getenv('POLICY_BOARD_ID')
REFERRER_BOARD_ID = os.getenv('REFERRER_BOARD_ID')
INSURANCE_BOARD_ID = os.getenv('INSURANCE_BOARD_ID')

# Use the additional variables
print(f"Monday API Token: {MONDAY_API_TOKEN}")
print(f"Policy Board ID: {POLICY_BOARD_ID}")
print(f"Referrer Board ID: {REFERRER_BOARD_ID}")
print(f"Insurance Board ID: {INSURANCE_BOARD_ID}")
print(f"IMGOCR API: {IMG_OCR_API_KEY}")
