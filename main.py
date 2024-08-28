import logging
import asyncio
import nest_asyncio
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputFile
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, CallbackContext, ConversationHandler
import os
from dotenv import load_dotenv
import json
from PIL import Image  # For image to PDF conversion

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
AGENT_NAME, DEALERSHIP, CONTACT_INFO, CHOOSING, UPLOAD_DRIVER_LICENSE = range(5)

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
        "Please select an option to enter the information:"
    )

    # Initialize available buttons in user data
    context.user_data['buttons'] = {'agent_name': True, 'dealership': True, 'contact_info': True}

    # Create inline buttons
    keyboard = [
        [
            InlineKeyboardButton("Agent Name", callback_data='agent_name'),
            InlineKeyboardButton("Dealership", callback_data='dealership'),
            InlineKeyboardButton("Contact Info", callback_data='contact_info'),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(welcome_message, reply_markup=reply_markup)
    return CHOOSING

# Handle button click and remove buttons temporarily
async def button_click(update: Update, context: CallbackContext) -> int:
    query = update.callback_query
    await query.answer()

    clicked_button = query.data

    # Hide all buttons while waiting for the user's reply
    await query.edit_message_text(f"Please enter {clicked_button.replace('_', ' ').capitalize()}:")

    # Set the next state based on which button was clicked
    if clicked_button == 'agent_name':
        return AGENT_NAME
    elif clicked_button == 'dealership':
        return DEALERSHIP
    elif clicked_button == 'contact_info':
        return CONTACT_INFO

# Define the handler to collect Agent Name
async def collect_agent_name(update: Update, context: CallbackContext) -> int:
    context.user_data['agent_name'] = update.message.text
    await update.message.reply_text("Agent Name saved.")
    
    # Show remaining buttons
    return await show_remaining_buttons(update, context)

# Define the handler to collect Dealership
async def collect_dealership(update: Update, context: CallbackContext) -> int:
    context.user_data['dealership'] = update.message.text
    await update.message.reply_text("Dealership saved.")
    
    # Show remaining buttons
    return await show_remaining_buttons(update, context)

# Define the handler to collect Contact Info
async def collect_contact_info(update: Update, context: CallbackContext) -> int:
    context.user_data['contact_info'] = update.message.text

    await update.message.reply_text("Contact Info saved.")

    # Show all details collected
    agent_name = context.user_data.get('agent_name', 'N/A')
    dealership = context.user_data.get('dealership', 'N/A')
    contact_info = context.user_data.get('contact_info', 'N/A')

    response_message = (
        f"Agent Name: {agent_name}\n"
        f"Dealership: {dealership}\n"
        f"Contact Info: {contact_info}"
    )
    await update.message.reply_text(response_message)

    # Create an item in Monday.com
    create_monday_item(agent_name, dealership, contact_info)

    # After collecting all info, prompt to upload driver's license
    await update.message.reply_text(
        "Please upload a Driver's License (JPG or PNG).",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Upload Driver's License", callback_data="upload_license")]])
    )
    
    return UPLOAD_DRIVER_LICENSE

# Handle the driver's license upload button
async def license_upload_prompt(update: Update, context: CallbackContext) -> int:
    query = update.callback_query
    await query.answer()

    await query.edit_message_text("Please upload a Driver's License image (JPG or PNG):")
    return UPLOAD_DRIVER_LICENSE

# Handle image upload and convert to PDF
async def handle_license_upload(update: Update, context: CallbackContext) -> int:
    try:
        # Get the highest resolution image from the user's upload
        photo = update.message.photo[-1]
        photo_file = await photo.get_file()

        # Define the path where the image will be saved
        image_path = f"{photo_file.file_id}.jpg"

        # Download the image file to the local file system
        await photo_file.download_to_drive(image_path)

        # Convert the image to PDF
        pdf_folder = "pdf_folder"
        os.makedirs(pdf_folder, exist_ok=True)  # Create the folder if it doesn't exist
        pdf_path = os.path.join(pdf_folder, f"{photo_file.file_id}.pdf")

        # Open the image and convert to RGB before saving as PDF
        with Image.open(image_path) as image:
            # Convert the image to RGB (necessary for saving as PDF)
            rgb_image = image.convert('RGB')
            rgb_image.save(pdf_path)

        # Send the generated PDF back to the user
        await update.message.reply_document(InputFile(pdf_path), filename="drivers_license.pdf")

        # Clean up the local files after sending the PDF
        os.remove(image_path)
        os.remove(pdf_path)

        # Send confirmation message
        await update.message.reply_text("Driver's License successfully converted to PDF and sent back to you.")
    
    except Exception as e:
        # Handle errors
        logger.error(f"Error converting image to PDF: {e}")
        await update.message.reply_text(f"Failed to convert image to PDF. Error: {str(e)}")

    return ConversationHandler.END



# Function to dynamically show remaining buttons
async def show_remaining_buttons(update: Update, context: CallbackContext) -> int:
    # Update which buttons are still available
    remaining_buttons = []
    if not context.user_data.get('agent_name'):
        remaining_buttons.append(InlineKeyboardButton("Agent Name", callback_data='agent_name'))
    if not context.user_data.get('dealership'):
        remaining_buttons.append(InlineKeyboardButton("Dealership", callback_data='dealership'))
    if not context.user_data.get('contact_info'):
        remaining_buttons.append(InlineKeyboardButton("Contact Info", callback_data='contact_info'))

    if remaining_buttons:
        reply_markup = InlineKeyboardMarkup([remaining_buttons])
        await update.message.reply_text("Please select another option:", reply_markup=reply_markup)
        return CHOOSING
    else:
        await update.message.reply_text("All information collected.")
        return ConversationHandler.END

# Main function to run the bot
def main():
    application = Application.builder().token(TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            CHOOSING: [CallbackQueryHandler(button_click)],
            AGENT_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, collect_agent_name)],
            DEALERSHIP: [MessageHandler(filters.TEXT & ~filters.COMMAND, collect_dealership)],
            CONTACT_INFO: [MessageHandler(filters.TEXT & ~filters.COMMAND, collect_contact_info)],
            UPLOAD_DRIVER_LICENSE: [
                CallbackQueryHandler(license_upload_prompt, pattern='^upload_license$'),
                MessageHandler(filters.PHOTO, handle_license_upload)
            ]
        },
        fallbacks=[]
    )

    application.add_handler(conv_handler)

    # Add more handlers as needed

    application.run_polling()

if __name__ == '__main__':
    main()
