import logging
import threading
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, CallbackContext, ConversationHandler
import os
from dotenv import load_dotenv
from PIL import Image  # For image processing
from PyPDF2 import PdfReader
import time
import json
import pytesseract
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from datetime import datetime
from pathlib import Path



# Explicitly specify the path to tesseract.exe
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files (x64)\Tesseract-OCR\tesseract.exe'

# Load environment variables from .env file
load_dotenv()

# Get the variables
TOKEN = os.getenv('TELEGRAM_BOT_API')
MONDAY_API_TOKEN = os.getenv('MONDAY_API_TOKEN')
POLICY_BOARD_ID = os.getenv('POLICY_BOARD_ID')
REFERRER_BOARD_ID = os.getenv('REFERRER_BOARD_ID')
INSURANCE_BOARD_ID = os.getenv('INSURANCE_BOARD_ID')

# AI model endpoint
AI_MODEL_ENDPOINT = "http://52.221.236.123:8502/extract-pdf" 

# Path to your PDF folder
PDF_FOLDER = Path.home() / "Projects" / "BingoTelegramBot" / "pdf_folder"

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

logger = logging.getLogger(__name__)

CHOOSING, UPLOAD_DRIVER_LICENSE, UPLOAD_IDENTITY_CARD, UPLOAD_LOG_CARD, AGENT_NAME, DEALERSHIP, CONTACT_INFO = range(7)

# Monday board columns ID's

# Referrer info board columns ID
# AGENT_NAME_COLUMN_ID = "text"
DEALERSHIP_COLUMN_ID = "text4"
CONTACT_INFO_COLUMN_ID = "phone"


OWNER_ID = "text13"
OWNER_ID_TYPE = "text"
CONTACT_NUMBER = "phone"
ORIGINAL_REGISTRATION_DATA = "date8"
VEHICLE_MODEL = "text6"
VEHICLE_MAKE = "text2"
ENGINE_NUMBER = "engine_number"
VEHICLE_NO = "text1"


def create_monday_item_from_json(agent_name, json_data):
    url = 'https://api.monday.com/v2'
    headers = {
        'Authorization': f'Bearer {MONDAY_API_TOKEN}',
        'Content-Type': 'application/json'
    }
    
    # Parse the date to the correct format (YYYY-MM-DD)
    original_registration_date = json_data.get("Original_Registration_Date", "")
    if original_registration_date:
        try:
            original_registration_date_obj = datetime.strptime(original_registration_date, "%d %b %Y")
            formatted_date = original_registration_date_obj.strftime("%Y-%m-%d")
        except ValueError:
            formatted_date = None
    else:
        formatted_date = None

    # Map the JSON fields to Monday.com column IDs
    column_values = {
        OWNER_ID: json_data.get("Owner_ID", ""),  # Assuming 'text' is the correct column ID for Owner_ID
        OWNER_ID_TYPE: json_data.get("Owner_ID_Type", ""),  # Updated to use 'text78' for Owner_ID_Type
        CONTACT_NUMBER: {"phone": json_data.get("Contact_Number", ""), "countryShortName": "SG"},
        ORIGINAL_REGISTRATION_DATA: formatted_date,
        VEHICLE_MODEL: json_data.get("Vehicle_Model", ""),
        VEHICLE_MAKE: json_data.get("Vehicle_Make", ""),
        ENGINE_NUMBER: json_data.get("Engine_No", ""),
        VEHICLE_NO: json_data.get("Vehicle_No", ""),
    }

    # Convert the column_values to a string that Monday.com API can accept
    column_values_str = json.dumps(column_values).replace('"', '\\"')

    # Build the GraphQL mutation query
    query = f'''
    mutation {{
        create_item (
            board_id: {POLICY_BOARD_ID},
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

    headers = {
        'Authorization': f'Bearer {MONDAY_API_TOKEN}',
        'Content-Type': 'application/json'
    }
    
    # Parse the date to the correct format (YYYY-MM-DD)
    original_registration_date = json_data.get("Original_Registration_Date", "")
    if original_registration_date:
        try:
            original_registration_date_obj = datetime.strptime(original_registration_date, "%d %b %Y")
            formatted_date = original_registration_date_obj.strftime("%Y-%m-%d")
        except ValueError:
            formatted_date = None
    else:
        formatted_date = None

    # Map the JSON fields to Monday.com column IDs
    column_values = {
        "text": json_data.get("Owner_ID", ""),  # Assuming 'text' is the correct column ID for Owner_ID
        "text5": json_data.get("Owner_ID_Type", ""),  # Assuming 'text5' is the correct column ID for Owner_ID_Type
        CONTACT_NUMBER: {"phone": json_data.get("Contact_Number", ""), "countryShortName": "SG"},
        ORIGINAL_REGISTRATION_DATA: formatted_date,
        VEHICLE_MODEL: json_data.get("Vehicle_Model", ""),
        VEHICLE_MAKE: json_data.get("Vehicle_Make", ""),
        ENGINE_NUMBER: json_data.get("Engine_No", ""),
        VEHICLE_NO: json_data.get("Vehicle_No", ""),
    }

    # Convert the column_values to a string that Monday.com API can accept
    column_values_str = json.dumps(column_values).replace('"', '\\"')

    # Build the GraphQL mutation query
    query = f'''
    mutation {{
        create_item (
            board_id: {POLICY_BOARD_ID},
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




def process_log_card(extracted_data, agent_name):
    """
    Processes the extracted data from a log card and sends it to Monday.com.

    Parameters:
        extracted_data (dict): The data extracted from the PDF by the AI model.
        agent_name (str): The name of the agent handling the log card.
    """
    try:
        # Extract the actual JSON data from the content field
        content = extracted_data.get("content", "")
        
        # Log the content for debugging purposes
        logger.info(f"Extracted content before JSON parsing: {content}")
        
        if not content or content.isspace():
            raise ValueError("Content is empty or whitespace")
        
        if content.startswith("```json"):
            content = content.strip("```json").strip()
        
        # Parse the JSON string into a dictionary
        parsed_data = json.loads(content)

        # Proceed with your existing logic
        create_monday_item_from_json(agent_name, parsed_data)
        logger.info(f"Successfully processed log card for vehicle: {parsed_data.get('Vehicle_No', 'Unknown Vehicle No')}")
    except json.JSONDecodeError as e:
        logger.error(f"Failed to decode JSON from extracted content: {e}")
    except ValueError as e:
        logger.error(f"Content error: {e}")
    except Exception as e:
        logger.error(f"Error processing log card: {e}")



# Function to monitor the PDF folder and process new PDFs
def monitor_pdf_folder():
    processed_files = set()  # Keep track of already processed files
    
    print("Starting to monitor the PDF folder...")  # Debug: Notify that monitoring has started

    # Ensure the PDF_FOLDER exists
    PDF_FOLDER.mkdir(parents=True, exist_ok=True)

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
                    agent_name = "Unknown Agent"  # Replace with actual logic to get agent name
                    process_log_card(extracted_data, agent_name)

                # Mark this file as processed
                processed_files.add(pdf_path)

        # Wait for some time before checking the folder again
        time.sleep(10)  # Check every 10 seconds



# Function to extract text from a PDF using the AI model
def extract_text_from_pdf(pdf_path):
    try:
        with open(pdf_path, 'rb') as pdf_file:
            files = {'file': (os.path.basename(pdf_path), pdf_file, 'application/pdf')}
            response = requests.post(AI_MODEL_ENDPOINT, files=files)

        if response.status_code == 200:
            extracted_data = response.json()
            logger.info(f"Raw AI Model Response: {extracted_data}")

            # Check if the AI model couldn't extract text and is asking for provided text
            if "provide the extracted text" in extracted_data.get("content", "").lower():
                logger.error(f"AI Model couldn't extract text from {pdf_path}.")
                return None

            return extracted_data
        else:
            logger.error(f"Failed to extract text from {pdf_path}: {response.status_code} {response.text}")
            return None
    except Exception as e:
        logger.error(f"Error during PDF text extraction for {pdf_path}: {e}")
        return None


# Function to extract text from an image using OCR
def extract_text_from_image(image_path):
    try:
        with Image.open(image_path) as image:
            text = pytesseract.image_to_string(image)
        return text
    except Exception as e:
        logger.error(f"Error during OCR text extraction for {image_path}: {e}")
        return None

# Function to create a real PDF with text
def create_pdf_with_text(text, pdf_path):
    try:
        c = canvas.Canvas(pdf_path, pagesize=letter)
        text_object = c.beginText(40, 750)
        text_object.setFont("Helvetica", 12)
        for line in text.splitlines():
            text_object.textLine(line)
        c.drawText(text_object)
        c.showPage()
        c.save()
        logger.info(f"PDF created with text at {pdf_path}")
    except Exception as e:
        logger.error(f"Error creating PDF with text: {e}")


# Function to check if a file is a valid PDF
def is_valid_pdf(file_path):
    try:
        with open(file_path, "rb") as file:
            reader = PdfReader(file)
            if len(reader.pages) > 0:
                return True
    except Exception as e:
        logger.error(f"File at {file_path} is not a valid PDF: {e}")
    return False


# Handle image upload and convert to a real PDF with text
async def handle_upload(update: Update, context: CallbackContext, upload_type: str) -> int:
    try:
        # Get the highest resolution image from the user's upload
        photo = update.message.photo[-1]
        photo_file = await photo.get_file()

        # Extract the file name without extension from the file_path
        original_file_name = os.path.basename(photo_file.file_path)
        base_name, _ = os.path.splitext(original_file_name)
        
        # Define the path where the image will be saved
        image_path = os.path.join(PDF_FOLDER, f"{base_name}.jpg")

        # Download the image file to the local file system
        await photo_file.download_to_drive(image_path)

        # Extract text from the image using OCR
        text = extract_text_from_image(image_path)

        # Define the path where the PDF will be saved, using the same name as the image
        pdf_path = os.path.join(PDF_FOLDER, f"{base_name}.pdf")

        if text and text.strip():
            # Create a real PDF with the extracted text
            create_pdf_with_text(text, pdf_path)
        else:
            raise ValueError("OCR failed to extract any text from the image.")

        # Clean up the local image file after saving the PDF
        os.remove(image_path)

        # Validate if the PDF file is correct
        if not is_valid_pdf(pdf_path):
            raise ValueError(f"The generated file at {pdf_path} is not a valid PDF.")

        # Send the PDF to the AI model for further processing
        extracted_data = extract_text_from_pdf(pdf_path)
        if extracted_data:
            logger.info(f"Extracted text from PDF: {json.dumps(extracted_data, indent=4)}")

            # If the upload type is 'log_card', process the JSON data and send it to Monday.com
            if upload_type == 'log_card':
                agent_name = context.user_data.get('agent_name', 'Unknown Agent')  # Default agent name
                process_log_card(extracted_data, agent_name)

        else:
            logger.error("AI model could not extract text from the PDF.")

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
        logger.error(f"Error processing image: {e}")
        await update.message.reply_text(f"Failed to process image. Error: {str(e)}")
        return CHOOSING


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

# Implement missing functions

async def show_remaining_buttons(update: Update, context: CallbackContext) -> int:
    keyboard = []
    if not context.user_data['uploads']['driver_license']:
        keyboard.append([InlineKeyboardButton("Upload Driver's License", callback_data='upload_license')])
    if not context.user_data['uploads']['identity_card']:
        keyboard.append([InlineKeyboardButton("Upload Identity Card", callback_data='upload_identity_card')])
    if not context.user_data['uploads']['log_card']:
        keyboard.append([InlineKeyboardButton("Upload Log Card", callback_data='upload_log_card')])
    
    if keyboard:
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text("Please upload the remaining documents:", reply_markup=reply_markup)
    else:
        await update.message.reply_text("All documents have been uploaded. Thank you!")

    return CHOOSING

async def show_upload_buttons(update: Update, context: CallbackContext) -> int:
    await show_remaining_buttons(update, context)
    return CHOOSING

async def upload_button_click(update: Update, context: CallbackContext) -> int:
    query = update.callback_query
    await query.answer()

    # Check which button was clicked and set the appropriate state
    if query.data == 'upload_license':
        await query.edit_message_text(text="Please upload your Driver's License.")
        return UPLOAD_DRIVER_LICENSE
    elif query.data == 'upload_identity_card':
        await query.edit_message_text(text="Please upload your Identity Card.")
        return UPLOAD_IDENTITY_CARD
    elif query.data == 'upload_log_card':
        await query.edit_message_text(text="Please upload your Log Card.")
        return UPLOAD_LOG_CARD

    return CHOOSING

async def button_click(update: Update, context: CallbackContext) -> int:
    # Handle other button clicks if necessary
    pass

async def license_upload(update: Update, context: CallbackContext) -> int:
    return await handle_upload(update, context, upload_type='driver_license')

async def identity_card_upload(update: Update, context: CallbackContext) -> int:
    return await handle_upload(update, context, upload_type='identity_card')

async def log_card_upload(update: Update, context: CallbackContext) -> int:
    return await handle_upload(update, context, upload_type='log_card')

async def collect_agent_name(update: Update, context: CallbackContext) -> int:
    agent_name = update.message.text
    context.user_data['agent_name'] = agent_name
    await update.message.reply_text(f"Agent name '{agent_name}' received. Please provide the dealership name.")
    return DEALERSHIP

async def collect_dealership(update: Update, context: CallbackContext) -> int:
    dealership = update.message.text
    context.user_data['dealership'] = dealership
    await update.message.reply_text(f"Dealership name '{dealership}' received. Please provide the contact info.")
    return CONTACT_INFO

async def collect_contact_info(update: Update, context: CallbackContext) -> int:
    contact_info = update.message.text
    context.user_data['contact_info'] = contact_info
    await update.message.reply_text(f"Contact info '{contact_info}' received. Thank you!")
    
    # Assuming the next step involves creating an item in Monday.com
    agent_name = context.user_data.get('agent_name')
    dealership = context.user_data.get('dealership')

    # This is where the indentation matters; ensure the following lines are indented
    create_monday_item_from_json(agent_name, {
        "Owner_ID": agent_name,  # Example mapping
        "Contact_Number": contact_info,
        "Vehicle_Model": context.user_data.get('vehicle_model'),
        "Vehicle_Make": context.user_data.get('vehicle_make'),
        "Engine_No": context.user_data.get('engine_number'),
        "Vehicle_No": context.user_data.get('vehicle_no'),
        "Original_Registration_Date": context.user_data.get('original_registration_date')
    })
    
    await show_remaining_buttons(update, context)
    return CHOOSING


# Main function to run the bot
def main():
    application = Application.builder().token(TOKEN).build()

    # Define conversation handler
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
