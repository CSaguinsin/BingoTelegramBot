import logging
import asyncio
import nest_asyncio
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, CallbackContext
from config import TOKEN, MONDAY_API_TOKEN, MONDAY_BOARD_ID
import os
from dotenv import load_dotenv

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

# Function to get updates from Telegram bot
def get_telegram_updates():
    url = f'https://api.telegram.org/bot{TOKEN}/getUpdates'
    response = requests.get(url)
    return response.json()

# Function to create an item in Monday.com
def create_monday_item(agent_name, dealership, contact_info):
    url = 'https://api.monday.com/v2'
    headers = {
        'Authorization': MONDAY_API_TOKEN,
        'Content-Type': 'application/json'
    }
    query = f'''
    mutation {{
        create_item (
            board_id: {BOARD_ID},
            item_name: "{agent_name}",
            column_values: {{
                "{AGENT_NAME_COLUMN_ID}": "{agent_name}",
                "{DEALERSHIP_COLUMN_ID}": "{dealership}",
                "{CONTACT_INFO_COLUMN_ID}": "{contact_info}"
            }}
        ) {{
            id
        }}
    }}
    '''
    data = {'query': query}
    response = requests.post(url, headers=headers, json=data)
    return response.json()

# Main function to process updates and create items in Monday.com
def process_updates():
    updates = get_telegram_updates()
    for update in updates['result']:
        if 'message' in update and 'text' in update['message']:
            text = update['message']['text']
            if text.startswith('/agent'):
                agent_name = text.split(' ', 1)[1]
                # Assuming the next messages contain dealership and contact info
                dealership = updates['result'][updates['result'].index(update) + 1]['message']['text']
                contact_info = updates['result'][updates['result'].index(update) + 2]['message']['text']
                response = create_monday_item(agent_name, dealership, contact_info)
                print(response)

# Define the start command handler
async def start(update: Update, context: CallbackContext) -> None:
    user = update.effective_user
    agent_name = user.first_name if user.first_name else user.username
    company_name = "Bingo"
    welcome_message = (
        f"Hello {agent_name}!\n"
        f"I'm your {company_name} Assistant.\n"
        "By chatting with us, you agree to share sensitive information. How can we help you today?"
    )
    await update.message.reply_text(welcome_message)

    # Create the initial upload buttons
    keyboard = [
        [InlineKeyboardButton("Upload Driver's License", callback_data='upload_drivers_license')],
        [InlineKeyboardButton("Upload Identity Card", callback_data='upload_identity_card')],
        [InlineKeyboardButton("Upload Log Card", callback_data='upload_log_card')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Please upload the following documents:", reply_markup=reply_markup)

# Define the button handler
async def button(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    await query.answer()

    context.user_data['clicked_buttons'] = context.user_data.get('clicked_buttons', set())
    context.user_data['clicked_buttons'].add(query.data)

    logger.info(f"Setting personal_info_step: {query.data}")
    context.user_data['personal_info_step'] = query.data

    if query.data in {'upload_drivers_license', 'upload_identity_card', 'upload_log_card'}:
        if query.data == 'upload_drivers_license':
            await query.edit_message_text(text="Please upload your Driver's License (jpg or png format).")
            context.user_data['expected_document'] = 'drivers_license'
        elif query.data == 'upload_identity_card':
            await query.edit_message_text(text="Please upload your Identity Card (jpg or png format).")
            context.user_data['expected_document'] = 'identity_card'
        elif query.data == 'upload_log_card':
            await query.edit_message_text(text="Please upload your Log Card (jpg or png format).")
            context.user_data['expected_document'] = 'log_card'

    elif query.data in {'comprehensive', 'tpft', 'tpo'}:
        if query.data == 'comprehensive':
            await query.edit_message_text(text="Please upload your Comprehensive insurance document (jpg or png format).")
            context.user_data['expected_document'] = 'comprehensive'
        elif query.data == 'tpft':
            await query.edit_message_text(text="Please upload your TPFT insurance document (jpg or png format).")
            context.user_data['expected_document'] = 'tpft'
        elif query.data == 'tpo':
            await query.edit_message_text(text="Please upload your TPO insurance document (jpg or png format).")
            context.user_data['expected_document'] = 'tpo'

    elif query.data in {'agent_name', 'dealership', 'contact_info'}:
        context.user_data['personal_info_clicks'] = context.user_data.get('personal_info_clicks', set())
        context.user_data['personal_info_clicks'].add(query.data)

        if query.data == 'contact_info':
            await query.edit_message_text(text="Please reply with your Contact Info (numbers only).")
        else:
            await query.edit_message_text(text=f"Please reply with your {query.data.replace('_', ' ').title()}.")

# Define the document upload handler
async def handle_document(update: Update, context: CallbackContext) -> None:
    logger.info("handle_document called")
    document = update.message.document
    expected_document = context.user_data.get('expected_document')

    if document.mime_type in ['image/jpeg', 'image/png']:
        logger.info(f"Received document: {expected_document}")
        
        # Step 1: Download the file from Telegram
        file_id = document.file_id
        file = await context.bot.get_file(file_id)
        file_name = document.file_name
        local_file_path = f"./{file_name}"
        await file.download_to_drive(local_file_path)
        
        # Step 2: Upload the file to Monday.com
        uploaded_successfully = upload_to_monday(local_file_path, expected_document)

        if uploaded_successfully:
            await update.message.reply_text(f"{expected_document.replace('_', ' ').title()} uploaded successfully to Monday.com.")
        else:
            await update.message.reply_text(f"Failed to upload {expected_document.replace('_', ' ').title()} to Monday.com.")
        
        # Track uploaded documents
        context.user_data['uploaded_documents'] = context.user_data.get('uploaded_documents', set())
        context.user_data['uploaded_documents'].add(expected_document)

        # Display remaining document upload buttons or next set of options
        remaining_buttons = []
        if expected_document in {'drivers_license', 'identity_card', 'log_card'}:
            if 'upload_drivers_license' not in context.user_data['clicked_buttons']:
                remaining_buttons.append([InlineKeyboardButton("Upload Driver's License", callback_data='upload_drivers_license')])
            if 'upload_identity_card' not in context.user_data['clicked_buttons']:
                remaining_buttons.append([InlineKeyboardButton("Upload Identity Card", callback_data='upload_identity_card')])
            if 'upload_log_card' not in context.user_data['clicked_buttons']:
                remaining_buttons.append([InlineKeyboardButton("Upload Log Card", callback_data='upload_log_card')])

            if remaining_buttons:
                try:
                    reply_markup = InlineKeyboardMarkup(remaining_buttons)
                    await update.message.reply_text("Please upload the remaining documents:", reply_markup=reply_markup)
                except Exception as e:
                    logger.error(f"Failed to send remaining document buttons: {e}")
                    await update.message.reply_text("There was an error sending the remaining document options.")

            if {'upload_drivers_license', 'upload_identity_card', 'upload_log_card'}.issubset(context.user_data['clicked_buttons']):
                next_keyboard = [
                    [InlineKeyboardButton("Upload Comprehensive", callback_data='comprehensive')],
                    [InlineKeyboardButton("Upload TPFT", callback_data='tpft')],
                    [InlineKeyboardButton("Upload TPO", callback_data='tpo')]
                ]
                try:
                    next_reply_markup = InlineKeyboardMarkup(next_keyboard)
                    await update.message.reply_text("Please upload your insurance documents:", reply_markup=next_reply_markup)
                except Exception as e:
                    logger.error(f"Failed to send insurance document buttons: {e}")
                    await update.message.reply_text("There was an error sending the insurance document options.")

        elif expected_document in {'comprehensive', 'tpft', 'tpo'}:
            if 'comprehensive' not in context.user_data['uploaded_documents']:
                remaining_buttons.append([InlineKeyboardButton("Upload Comprehensive", callback_data='comprehensive')])
            if 'tpft' not in context.user_data['uploaded_documents']:
                remaining_buttons.append([InlineKeyboardButton("Upload TPFT", callback_data='tpft')])
            if 'tpo' not in context.user_data['uploaded_documents']:
                remaining_buttons.append([InlineKeyboardButton("Upload TPO", callback_data='tpo')])

            if remaining_buttons:
                try:
                    reply_markup = InlineKeyboardMarkup(remaining_buttons)
                    await update.message.reply_text("Please upload the remaining insurance documents:", reply_markup=reply_markup)
                except Exception as e:
                    logger.error(f"Failed to send remaining insurance document buttons: {e}")
                    await update.message.reply_text("There was an error sending the remaining insurance document options.")

            if {'comprehensive', 'tpft', 'tpo'}.issubset(context.user_data['uploaded_documents']):
                try:
                    info_keyboard = [
                        [InlineKeyboardButton("Agent Name", callback_data='agent_name')],
                        [InlineKeyboardButton("Dealership", callback_data='dealership')],
                        [InlineKeyboardButton("Contact Info", callback_data='contact_info')]
                    ]
                    info_reply_markup = InlineKeyboardMarkup(info_keyboard)
                    await update.message.reply_text("Please provide the following information:", reply_markup=info_reply_markup)
                except Exception as e:
                    logger.error(f"Failed to send personal information buttons: {e}")
                    await update.message.reply_text("There was an error sending the personal information options.")
    else:
        await update.message.reply_text("Please upload a valid image file (jpg or png format).")

# Upload to Monday.com function
def upload_to_monday(file_path, document_type):
    """Uploads a file to Monday.com under the appropriate column and group"""
    url = "https://api.monday.com/v2/file"
    
    # GraphQL mutation to upload the file to Monday.com's column
    query = """
    mutation ($file: File!) {
      add_file_to_column (file: $file, item_id: 123456789, column_id: "files") {
        id
      }
    }
    """
    
    headers = {
        'Authorization': MONDAY_API_TOKEN
    }
    
    # Open the file to upload
    files = {
        'query': (None, query),
        'variables[file]': open(file_path, 'rb')
    }
    
    # Perform the HTTP POST request to Monday.com's API
    response = requests.post(url, headers=headers, files=files)
    
    # Check for success
    if response.status_code == 200:
        logger.info(f"File uploaded successfully to Monday.com for {document_type}")
        return True
    else:
        logger.error(f"Failed to upload file to Monday.com: {response.status_code}, {response.text}")
        return False

# Define function to update Monday.com with text
def update_monday_text(item_id, column_id, value):
    """Updates Monday.com text column with a specific value"""
    url = "https://api.monday.com/v2"
    
    query = """
    mutation {
      change_simple_column_value (board_id: %s, item_id: %s, column_id: "%s", value: "%s") {
        id
      }
    }
    """ % (BOARD_ID, item_id, column_id, value)
    
    headers = {
        'Authorization': MONDAY_API_TOKEN,
        'Content-Type': 'application/json'
    }
    
    response = requests.post(url, headers=headers, json={"query": query})
    
    if response.status_code == 200:
        logger.info(f"Text updated successfully for {column_id}")
        return True
    else:
        logger.error(f"Failed to update text: {response.status_code}, {response.text}")
        return False

# Define the text input handler
async def handle_text(update: Update, context: CallbackContext) -> None:
    if update.message is None:
        return

    user_response = update.message.text.strip()

    # Safely get the current step
    personal_info_key = context.user_data.get('personal_info_step')
    logger.info(f"Accessing personal_info_step: {personal_info_key}")

    if personal_info_key:
        # Process the user's input based on the current step
        logger.info(f"Processing step: {personal_info_key} with response: {user_response}")

        if personal_info_key == 'contact_info' and not user_response.isdigit():
            await update.message.reply_text("Please enter a valid number for Contact Info.")
            return

        column_mapping = {
            'agent_name': AGENT_NAME_COLUMN_ID,
            'dealership': DEALERSHIP_COLUMN_ID,
            'contact_info': CONTACT_INFO_COLUMN_ID
        }

        # Ensure key exists in the mapping
        column_id = column_mapping.get(personal_info_key)
        if column_id:
            upload_successful = update_monday_text(123456789, column_id, user_response)

            if upload_successful:
                await update.message.reply_text(f"Your {personal_info_key.replace('_', ' ').title()} has been recorded.")
            else:
                await update.message.reply_text(f"Failed to update {personal_info_key.replace('_', ' ').title()} in Monday.com.")
        else:
            logger.error(f"Invalid personal_info_key: {personal_info_key}")
            await update.message.reply_text("An error occurred while processing your information. Please try again.")
        
        # Reset the step after processing
        logger.info(f"Resetting personal_info_step from {personal_info_key} to None")
        context.user_data['personal_info_step'] = None

        # Check remaining steps and guide the user
        remaining_buttons = []
        if 'agent_name' not in context.user_data.get('personal_info_clicks', set()):
            remaining_buttons.append([InlineKeyboardButton("Agent Name", callback_data='agent_name')])
        if 'dealership' not in context.user_data.get('personal_info_clicks', set()):
            remaining_buttons.append([InlineKeyboardButton("Dealership", callback_data='dealership')])
        if 'contact_info' not in context.user_data.get('personal_info_clicks', set()):
            remaining_buttons.append([InlineKeyboardButton("Contact Info", callback_data='contact_info')])

        if remaining_buttons:
            reply_markup = InlineKeyboardMarkup(remaining_buttons)
            await update.message.reply_text("Please provide the remaining information:", reply_markup=reply_markup)

        if {'agent_name', 'dealership', 'contact_info'}.issubset(context.user_data['personal_info_clicks']):
            context.user_data['awaiting_confirmation'] = True
            await update.message.reply_text(
                "By replying YES, I confirm that I have informed the client that their information will be collected and used to generate an insurance quote."
            )
    elif context.user_data.get('awaiting_confirmation'):
        if user_response.lower() == 'yes':
            context.user_data['awaiting_confirmation'] = False
            context.user_data['awaiting_submit'] = True
            await update.message.reply_text("Please reply with SUBMIT to confirm.")
        else:
            await update.message.reply_text("Please type YES to confirm or correct the information provided.")
    elif context.user_data.get('awaiting_submit'):
        if user_response.lower() == 'submit':
            await update.message.reply_text("Thank you! Have a nice day!")
            context.user_data.clear()
        else:
            await update.message.reply_text("Please type SUBMIT to complete the process.")

# Main function to start the bot
async def main() -> None:
    application = Application.builder().token(TOKEN).build()
    application.add_handler(CommandHandler('start', start))
    application.add_handler(CallbackQueryHandler(button))
    application.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    await application.run_polling()

if __name__ == '__main__':
    asyncio.run(main())
