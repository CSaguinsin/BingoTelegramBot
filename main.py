import logging
import threading
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, CallbackContext, ConversationHandler
import os
from dotenv import load_dotenv
from PIL import Image  # For image to PDF conversion
from PyPDF2 import PdfFileReader
import time
import mimetypes
import json

# Load environment variables from .env file
load_dotenv()

# Get the variables
TOKEN = os.getenv('TELEGRAM_BOT_API')
MONDAY_API_TOKEN = os.getenv('MONDAY_API_TOKEN')
BOARD_ID = os.getenv('MONDAY_BOARD_ID')

# AI model endpoint
AI_MODEL_ENDPOINT = "http://52.221.236.123:8502/extract-pdf"

# Path to your PDF folder
PDF_FOLDER = r"C:\Users\Celine\projects\BingoTeleBot\pdf_folder"

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

logger = logging.getLogger(__name__)

# Define states
CHOOSING, UPLOAD_DRIVER_LICENSE, UPLOAD_IDENTITY_CARD, UPLOAD_LOG_CARD, AGENT_NAME, DEALERSHIP, CONTACT_INFO = range(7)

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

# Function to check if a file is a valid PDF
def is_valid_pdf(file_path):
    try:
        with open(file_path, "rb") as file:
            reader = PdfFileReader(file)
            if reader.getNumPages() > 0:
                return True
    except Exception as e:
        logger.error(f"File at {file_path} is not a valid PDF: {e}")
    return False

# Function to extract text from a PDF using the AI model
def extract_text_from_pdf(pdf_path):
    try:
        # Verify the file's MIME type
        mime_type, _ = mimetypes.guess_type(pdf_path)
        logger.info(f"MIME type of {pdf_path}: {mime_type}")

        if mime_type != 'application/pdf':
            logger.error(f"File {pdf_path} is not recognized as a PDF by MIME type.")
            return None

        # Send the PDF to the AI model
        with open(pdf_path, 'rb') as pdf_file:
            files = {'file': ('file.pdf', pdf_file, 'application/pdf')}
            response = requests.post(AI_MODEL_ENDPOINT, files=files)

        if response.status_code == 200:
            try:
                # Parse the response as JSON
                extracted_data = response.json()
                logger.info(f"Extracted data from {pdf_path}: {json.dumps(extracted_data, indent=2)}")

                # Debug: Display the extracted JSON data
                print(f"Extracted JSON data from {pdf_path}:\n{json.dumps(extracted_data, indent=2)}\n")
                
                return extracted_data
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse JSON from AI response: {e}")
                return None
        else:
            error_message = f"Failed to extract text from {pdf_path}: {response.status_code} {response.text}"
            logger.error(error_message)
            print(error_message)
            return None
    except Exception as e:
        error_message = f"Error during PDF text extraction for {pdf_path}: {e}"
        logger.error(error_message)
        print(error_message)
        return None

# Function to monitor the PDF folder and process new PDFs
def monitor_pdf_folder():
    processed_files = set()  # Keep track of already processed files
    
    print("Starting to monitor the PDF folder...")  # Debug: Notify that monitoring has started

    while True:
        # Get the list of all PDF files in the folder
        pdf_files = [f for f in os.listdir(PDF_FOLDER) if f.endswith('.pdf')]

        for pdf_file in pdf_files:
            pdf_path = os.path.join(PDF_FOLDER, pdf_file)

            if pdf_path not in processed_files:
                logger.info(f"Processing file: {pdf_path}")

                # Extract text from the PDF
                extracted_data = extract_text_from_pdf(pdf_path)

                if extracted_data:
                    logger.info(f"Successfully processed {pdf_file}")

                # Mark this file as processed
                processed_files.add(pdf_path)

        # Wait for some time before checking the folder again
        time.sleep(10)  # Check every 10 seconds

# Define the start command handler
async def start(update: Update, context: CallbackContext) -> int:
    user = update.effective_user
    agent_name = user.first_name if user.first_name else user.username
    company_name = "Bingo"
    welcome_message = (
        f"Hello {agent_name}!\n"
        f"I'm your {company_name} Assistant.\n"
        "By chatting with us, you agree to share sensitive information. How can we help you today?\n\n"
        "Please select an option to upload the required documents:"
    )

    # Initialize available buttons in user data
    context.user_data['uploads'] = {'driver_license': False, 'identity_card': False, 'log_card': False}

    # Create inline buttons for uploads
    keyboard = [
        [InlineKeyboardButton("Upload Driver's License", callback_data='upload_license')],
        [InlineKeyboardButton("Upload Identity Card", callback_data='upload_identity_card')],
        [InlineKeyboardButton("Upload Log Card", callback_data='upload_log_card')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(welcome_message, reply_markup=reply_markup)
    return CHOOSING

# Handle upload button clicks
async def upload_button_click(update: Update, context: CallbackContext) -> int:
    query = update.callback_query
    await query.answer()

    clicked_button = query.data

    if clicked_button == 'upload_license':
        await query.edit_message_text("Please upload your Driver's License image (JPG or PNG):")
        return UPLOAD_DRIVER_LICENSE
    elif clicked_button == 'upload_identity_card':
        await query.edit_message_text("Please upload your Identity Card image (JPG or PNG):")
        return UPLOAD_IDENTITY_CARD
    elif clicked_button == 'upload_log_card':
        await query.edit_message_text("Please upload your Log Card image (JPG or PNG):")
        return UPLOAD_LOG_CARD

# Handle image upload and convert to PDF without sending back to the user
async def handle_upload(update: Update, context: CallbackContext, upload_type: str) -> int:
    try:
        # Get the highest resolution image from the user's upload
        photo = update.message.photo[-1]
        photo_file = await photo.get_file()

        # Define the path where the image will be saved
        image_path = f"{photo_file.file_id}.jpg"

        # Download the image file to the local file system
        await photo_file.download_to_drive(image_path)

        # Convert the image to PDF
        pdf_folder = PDF_FOLDER
        os.makedirs(pdf_folder, exist_ok=True)  # Create the folder if it doesn't exist
        pdf_path = os.path.join(pdf_folder, f"{upload_type}_{photo_file.file_id}.pdf")

        # Open the image and convert to RGB before saving as PDF
        with Image.open(image_path) as image:
            # Convert the image to RGB (necessary for saving as PDF)
            rgb_image = image.convert('RGB')
            rgb_image.save(pdf_path)

        # Clean up the local image file after saving the PDF
        os.remove(image_path)

        # Validate if the PDF file is correct
        if not is_valid_pdf(pdf_path):
            raise ValueError(f"The generated file at {pdf_path} is not a valid PDF.")

        # Mark the upload as done
        context.user_data['uploads'][upload_type] = True

        # Send a thank you message to the user
        await update.message.reply_text(f"Thank you for uploading your {upload_type.replace('_', ' ')}.")

        # Check if all uploads are done
        if all(context.user_data['uploads'].values()):
            await show_remaining_buttons(update, context)
            return CHOOSING

        # Otherwise, show remaining upload buttons
        return await show_upload_buttons(update, context)
    
    except Exception as e:
        # Handle errors
        logger.error(f"Error converting image to PDF: {e}")
        await update.message.reply_text(f"Failed to convert image to PDF. Error: {str(e)}")
        return CHOOSING

# Function to show remaining upload buttons
async def show_upload_buttons(update: Update, context: CallbackContext) -> int:
    remaining_buttons = []
    if not context.user_data['uploads']['driver_license']:
        remaining_buttons.append([InlineKeyboardButton("Upload Driver's License", callback_data='upload_license')])
    if not context.user_data['uploads']['identity_card']:
        remaining_buttons.append([InlineKeyboardButton("Upload Identity Card", callback_data='upload_identity_card')])
    if not context.user_data['uploads']['log_card']:
        remaining_buttons.append([InlineKeyboardButton("Upload Log Card", callback_data='upload_log_card')])

    if remaining_buttons:
        reply_markup = InlineKeyboardMarkup(remaining_buttons)
        await update.message.reply_text("Please upload the remaining documents:", reply_markup=reply_markup)
        return CHOOSING

# Function to show remaining buttons after uploads
async def show_remaining_buttons(update: Update, context: CallbackContext) -> int:
    # Display buttons for entering Agent Name, Dealership, and Contact Info
    keyboard = [
        [InlineKeyboardButton("Agent Name", callback_data='agent_name')],
        [InlineKeyboardButton("Dealership", callback_data='dealership')],
        [InlineKeyboardButton("Contact Info", callback_data='contact_info')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("All documents uploaded. Please provide the following information:", reply_markup=reply_markup)
    return CHOOSING

# Handle the driver's license upload button
async def license_upload(update: Update, context: CallbackContext) -> int:
    return await handle_upload(update, context, 'driver_license')

# Handle the identity card upload button
async def identity_card_upload(update: Update, context: CallbackContext) -> int:
    return await handle_upload(update, context, 'identity_card')

# Handle the log card upload button
async def log_card_upload(update: Update, context: CallbackContext) -> int:
    return await handle_upload(update, context, 'log_card')

# Handle button click for entering information
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

    return ConversationHandler.END

# Main function to run the bot
def main():
    application = Application.builder().token(TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            CHOOSING: [CallbackQueryHandler(upload_button_click, pattern='^upload_'), CallbackQueryHandler(button_click)],
            UPLOAD_DRIVER_LICENSE: [MessageHandler(filters.PHOTO, license_upload)],
            UPLOAD_IDENTITY_CARD: [MessageHandler(filters.PHOTO, identity_card_upload)],
            UPLOAD_LOG_CARD: [MessageHandler(filters.PHOTO, log_card_upload)],
            AGENT_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, collect_agent_name)],
            DEALERSHIP: [MessageHandler(filters.TEXT & ~filters.COMMAND, collect_dealership)],
            CONTACT_INFO: [MessageHandler(filters.TEXT & ~filters.COMMAND, collect_contact_info)]
        },
        fallbacks=[]
    )

    application.add_handler(conv_handler)

    # Start the PDF monitoring in a separate thread
    threading.Thread(target=monitor_pdf_folder, daemon=True).start()

    # Start the bot's polling in the main thread
    application.run_polling()

if __name__ == '__main__':
    main()
