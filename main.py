import logging
import asyncio
import nest_asyncio
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, CallbackContext, ConversationHandler
from config import TOKEN, MONDAY_API_TOKEN, MONDAY_BOARD_ID
import os
from dotenv import load_dotenv
import json

# Load environment variables from .env file
load_dotenv()

# Get the variables
TOKEN = os.getenv('TELEGRAM_BOT_API')
MONDAY_API_TOKEN = os.getenv('MONDAY_API_TOKEN')
BOARD_ID = os.getenv('MONDAY_BOARD_ID')

# Column IDs (replace with actual IDs)
AGENT_NAME_COLUMN_ID = 'text23'
DEALERSHIP_COLUMN_ID = 'text3'
CONTACT_INFO_COLUMN_ID = 'numbers0'

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

logger = logging.getLogger(__name__)

# Apply nest_asyncio
nest_asyncio.apply()

# Define states
AGENT_NAME, DEALERSHIP, CONTACT_INFO = range(3)

# Function to create an item in Monday.com
def create_monday_item(agent_name, dealership, contact_info):
    url = 'https://api.monday.com/v2'
    headers = {
        'Authorization': f'Bearer {MONDAY_API_TOKEN}',
        'Content-Type': 'application/json'
    }
    column_values = {
        AGENT_NAME_COLUMN_ID: agent_name,
        DEALERSHIP_COLUMN_ID: dealership,
        CONTACT_INFO_COLUMN_ID: contact_info
    }
    # Properly escape the JSON string
    column_values_str = json.dumps(column_values).replace('"', '\\"')
    query = f'''
    mutation {{
        create_item (
            board_id: {BOARD_ID},
            item_name: "{agent_name}",
            column_values: "{column_values_str}"
        ) {{
            id
        }}
    }}
    '''
    data = {'query': query}

    logger.info(f"Sending GraphQL query to Monday.com: {query}")
    
    response = requests.post(url, headers=headers, json=data)

    if response.status_code != 200 or 'errors' in response.json():
        logger.error(f"Failed to create item in Monday.com: {response.text}")
        return None

    logger.info(f"Successfully created item in Monday.com: {response.json()}")
    return response.json()

# Define the start command handler
async def start(update: Update, context: CallbackContext) -> int:
    user = update.effective_user
    agent_name = user.first_name if user.first_name else user.username
    company_name = "Bingo"
    welcome_message = (
        f"Hello {agent_name}!\n"
        f"I'm your {company_name} Assistant.\n"
        "By chatting with us, you agree to share sensitive information. How can we help you today?\n\n"
        "Please enter your Agent Name:"
    )
    await update.message.reply_text(welcome_message)
    return AGENT_NAME

# Define the handler to collect Agent Name
async def collect_agent_name(update: Update, context: CallbackContext) -> int:
    context.user_data['agent_name'] = update.message.text
    await update.message.reply_text("Please enter your Dealership:")
    return DEALERSHIP

# Define the handler to collect Dealership
async def collect_dealership(update: Update, context: CallbackContext) -> int:
    context.user_data['dealership'] = update.message.text
    await update.message.reply_text("Please enter your Contact Info:")
    return CONTACT_INFO

# Define the handler to collect Contact Info and display all details
async def collect_contact_info(update: Update, context: CallbackContext) -> int:
    context.user_data['contact_info'] = update.message.text
    agent_name = context.user_data['agent_name']
    dealership = context.user_data['dealership']
    contact_info = context.user_data['contact_info']
    
    response_message = (
        f"Agent Name: {agent_name}\n"
        f"Dealership: {dealership}\n"
        f"Contact Info: {contact_info}"
    )
    await update.message.reply_text(response_message)
    
    # Create an item in Monday.com
    create_monday_item(agent_name, dealership, contact_info)
    
    return ConversationHandler.END

# Main function to run the bot
def main():
    application = Application.builder().token(TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            AGENT_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, collect_agent_name)],
            DEALERSHIP: [MessageHandler(filters.TEXT & ~filters.COMMAND, collect_dealership)],
            CONTACT_INFO: [MessageHandler(filters.TEXT & ~filters.COMMAND, collect_contact_info)],
        },
        fallbacks=[]
    )

    application.add_handler(conv_handler)

    # Add more handlers as needed

    application.run_polling()

if __name__ == '__main__':
    main()
