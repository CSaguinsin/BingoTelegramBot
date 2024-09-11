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
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
import subprocess
import glob
import base64
import httpx  # Added for verified HTTPS requests

# Explicitly specify the path to tesseract.exe
pytesseract.pytesseract.tesseract_cmd = '/opt/homebrew/bin/tesseract'

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
IMAGE_FOLDER = Path("/Users/carlsaginsin/Projects/BingoTelegramBot/image_folder")  # Added image folder path

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

logger = logging.getLogger(__name__)

# Conversation states
ASKING_NAME, CHOOSING, UPLOAD_DRIVER_LICENSE, UPLOAD_IDENTITY_CARD, UPLOAD_LOG_CARD, AGENT_NAME_INPUT, DEALERSHIP_INPUT, CONTACT_INFO_INPUT, CONFIRMATION = range(9)

# Monday board columns ID's
AGENT_NAME = "text23"
FULL_NAME = "text9"
AGENT_CONTACT_NUMBER = "phone0"
DEALERSHIP_COLUMN_ID = "text3"
CONTACT_INFO_COLUMN_ID = "phone"

OWNER_ID = "text78"
OWNER_ID_TYPE = "text"
CONTACT_NUMBER = "phone"
ORIGINAL_REGISTRATION_DATA = "date8"
VEHICLE_MODEL = "text6"
VEHICLE_MAKE = "text2"
ENGINE_NUMBER = "engine_number"
VEHICLE_NO = "text1"
CHASSIS_NO = "text775"

# Update the column ID for the source
SOURCE_COLUMN_ID = "text04"  # Column ID for "Software Source"

def create_monday_item_from_json(full_name, agent_name, dealership, agent_contact_info, json_data, source, pdf_path=None, folder_link=None):  # Added folder_link parameter
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

    # Extract Issue Date and License Number from the extracted data
    issue_date = json_data.get("Issue_Date", "")  # Assuming the key in JSON is "Issue_Date"
    license_number = json_data.get("License_Number", "")  # Assuming the key in JSON is "License_Number"

    # Map the JSON fields to Monday.com column IDs for POLICY_BOARD_ID
    column_values = {
        FULL_NAME: full_name,
        AGENT_NAME: agent_name,
        AGENT_CONTACT_NUMBER: {"phone": agent_contact_info, "countryShortName": "SG"},
        DEALERSHIP_COLUMN_ID: dealership,
        OWNER_ID: json_data.get("Owner_ID", ""),
        OWNER_ID_TYPE: json_data.get("Owner_ID_Type", ""),
        CONTACT_NUMBER: {"phone": json_data.get("Contact_Number", ""), "countryShortName": "SG"},
        ORIGINAL_REGISTRATION_DATA: formatted_date,
        VEHICLE_MODEL: json_data.get("Vehicle_Model", ""),
        VEHICLE_MAKE: json_data.get("Vehicle_Make", ""),
        ENGINE_NUMBER: json_data.get("Engine_No", ""),
        CHASSIS_NO: json_data.get("Chassis_No", ""),
        VEHICLE_NO: json_data.get("Vehicle_No", ""),
        SOURCE_COLUMN_ID: source,  # Add the source information here
        "files": pdf_path,  # Add the PDF file path to the column
        "text49": folder_link,  # Store the Google Drive folder link in the Documents Folder column
        "text92": issue_date,  # Store the Issue Date
        "text8": license_number  # Store the License Number
    }

    # Convert the column_values to a string that Monday.com API can accept
    column_values_str = json.dumps(column_values).replace('"', '\\"')

    # Build the GraphQL mutation query for POLICY_BOARD_ID
    query = f'''
    mutation {{
        create_item (
            board_id: {POLICY_BOARD_ID},
            item_name: "{full_name}",  # Use double quotes for item name
            column_values: "{column_values_str}"  # No change needed here
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

    # Now create an item in the REFERRER_BOARD_ID
    referrer_column_values = {
        "text": agent_name,  # Referrer's Name
        "phone": {"phone": agent_contact_info, "countryShortName": "SG"},  # Contact Number
        "text4": dealership  # Dealership
    }

    # Convert the referrer_column_values to a string
    referrer_column_values_str = json.dumps(referrer_column_values).replace('"', '\\"')

    # Build the GraphQL mutation query for REFERRER_BOARD_ID with Dealership as item name
    referrer_query = f'''
    mutation {{
        create_item (
            board_id: {REFERRER_BOARD_ID},
            item_name: "{dealership}",  # Use Dealership as the item name with double quotes
            column_values: "{referrer_column_values_str}"
        ) {{
            id
        }}
    }}
    '''

    referrer_data = {'query': referrer_query}
    logger.info(f"Sending GraphQL query to Monday.com for referrer: {referrer_query}")

    referrer_response = requests.post(url, headers=headers, json=referrer_data)

    if referrer_response.status_code != 200 or 'errors' in referrer_response.json():
        logger.error(f"Failed to create item in Referrer board: {referrer_response.text}")
        return None

    logger.info(f"Successfully created item in Referrer board: {referrer_response.json()}")
    
    # After creating the item, upload the PDF file to the "Documents Uploaded" column
    if pdf_path:
        api_url = "https://api.monday.com/v2/file"
        headers = {
            "Authorization": MONDAY_API_TOKEN
        }
        files = {
            'variables[file]': (pdf_path, open(pdf_path, 'rb'))
        }
        data = {
            'query': f'mutation ($file: File!) {{ add_file_to_column (item_id: {response.json()["id"]}, column_id: "files", file: $file) {{ id }} }}'
        }
        
        upload_response = requests.post(api_url, headers=headers, files=files, data=data)
        if upload_response.status_code == 200:
            logger.info(f"Successfully uploaded PDF file to Documents Uploaded column: {pdf_path}")
        else:
            logger.error(f"Failed to upload PDF file to Documents Uploaded column: {upload_response.text}")

    # After creating the item, update it with Issue Date and License Number
    item_id = response.json().get("id")
    update_monday_item(item_id, issue_date, license_number)  # Call the update function

    return response.json()

def update_monday_item(item_id, issue_date, license_number):
    """Update the Monday.com item with Issue Date and License Number."""
    url = 'https://api.monday.com/v2'
    headers = {
        'Authorization': f'Bearer {MONDAY_API_TOKEN}',
        'Content-Type': 'application/json'
    }

    # Prepare the column values to update
    column_values = {
        "text92": issue_date,  # Store the Issue Date
        "text8": license_number  # Store the License Number
    }

    # Convert the column_values to a string that Monday.com API can accept
    column_values_str = json.dumps(column_values).replace('"', '\\"')

    # Build the GraphQL mutation query to update the item
    query = f'''
    mutation {{
        change_column_values (
            board_id: {POLICY_BOARD_ID},
            item_id: {item_id},
            column_values: "{column_values_str}"
        ) {{
            id
        }}
    }}
    '''

    data = {'query': query}
    response = requests.post(url, headers=headers, json=data)

    if response.status_code != 200 or 'errors' in response.json():
        logger.error(f"Failed to update item in Monday.com: {response.text}")
        return None

    logger.info(f"Successfully updated item in Monday.com: {response.json()}")

# Update the process_log_card function to accept folder_link
def process_log_card(extracted_data, context=None, source="Telegram", pdf_path=None, folder_link=None):  # Added folder_link parameter
    """
    Processes the extracted data from a log card and sends it to Monday.com.

    Parameters:
        extracted_data (dict): The data extracted from the PDF by the AI model.
        context: The callback context. If None, default values are used.
        source (str): The source of the data (e.g., "WhatsApp", "Telegram").
        pdf_path (str): The path to the generated PDF file.
        folder_link (str): The Google Drive folder link.
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

        # Check if context is not None before accessing context.user_data
        if context and hasattr(context, 'user_data'):
            full_name = context.user_data.get('full_name', 'Unknown Agent')
            agent_name = context.user_data.get('agent_name', 'Unknown Agent')
            dealership = context.user_data.get('dealership', 'Unknown Dealership')
            agent_contact_info = context.user_data.get('agent_contact_info', 'Unknown Contact Info')
        else:
            # If no context is provided, use default values
            full_name = 'Unknown Agent'
            agent_name = 'Unknown Agent'
            dealership = 'Unknown Dealership'
            agent_contact_info = 'Unknown Contact Info'
            logger.warning("No context or user data found, using default values.")

        # Proceed with your existing logic to create a Monday.com item
        create_monday_item_from_json(full_name, agent_name, dealership, agent_contact_info, parsed_data, source, pdf_path, folder_link)  # Pass folder_link
        logger.info(f"Successfully processed log card for vehicle: {parsed_data.get('Vehicle_No', 'Unknown Vehicle No')}")
        
    except json.JSONDecodeError as e:
        logger.error(f"Failed to decode JSON from extracted content: {e}")
    except ValueError as e:
        logger.error(f"Content error: {e}")
    except Exception as e:
        logger.error(f"Error processing log card: {e}")

# Modified call to process_log_card in monitor_pdf_folder to handle None context
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
                    # Passing None for context when called from monitor_pdf_folder
                    process_log_card(extracted_data, context=None, source="WhatsApp", pdf_path=pdf_path)  # Pass pdf_path

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
        width, height = letter  # Get the width and height of the page
        text_object = c.beginText(40, height - 40)  # Start at the top of the page
        text_object.setFont("Helvetica", 12)

        # Split the text into lines and add each line to the PDF
        lines = text.splitlines()
        for line in lines:
            text_object.textLine(line)
            if text_object.getY() < 40:  # If the text goes below the bottom margin, start a new page
                c.drawText(text_object)
                c.showPage()
                text_object = c.beginText(40, height - 40)
                text_object.setFont("Helvetica", 12)

        c.drawText(text_object)
        c.showPage()
        c.save()
        logger.info(f"PDF created with selectable text at {pdf_path}")
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

# Load environment variables from .env file
# load_dotenv()

# def upload_to_google_drive(file_path, file_name):
#     SCOPES = ['https://www.googleapis.com/auth/drive.file']
#     SERVICE_ACCOUNT_FILE = os.getenv('SERVICE_ACCOUNT')  # service account creds from env

#     credentials = service_account.Credentials.from_service_account_file(
#         SERVICE_ACCOUNT_FILE, scopes=SCOPES)

#     service = build('drive', 'v3', credentials=credentials)

#     file_metadata = {
#         'name': file_name,
#         'parents': ['1AtdPC6yx-u0SlvV-erAwT2jEJ1HlnxcI']  # Your Google Drive folder ID
#     }
#     media = MediaFileUpload(file_path, mimetype='image/jpeg')  # Adjust MIME type if necessary

#     file = service.files().create(body=file_metadata, media_body=media, fields='id').execute()
#     logger.info(f"Uploaded file to Google Drive with ID: {file.get('id')}")

# Function to create a folder in Google Drive and return its link
def create_drive_folder(service, folder_name):
    # Check if the folder already exists
    query = f"mimeType='application/vnd.google-apps.folder' and name='{folder_name}' and trashed=false"
    response = service.files().list(q=query, fields='files(id)').execute()
    folders = response.get('files', [])

    if folders:
        folder_id = folders[0]['id']
    else:
        # If the folder does not exist, create it
        file_metadata = {
            'name': folder_name,
            'mimeType': 'application/vnd.google-apps.folder',
            'parents': ['1Dk5NwHFTdWcX13PD64Z7Ljaa8NbqP_Ye']  # Parent folder ID
        }
        folder = service.files().create(body=file_metadata, fields='id').execute()
        folder_id = folder.get('id')

    # Return the folder link
    return f"https://drive.google.com/drive/folders/{folder_id}"

# Function to upload a file to Google Drive
def upload_file_to_drive(service, file_path, folder_id):
    file_metadata = {
        'name': os.path.basename(file_path),
        'parents': [folder_id]
    }
    media = MediaFileUpload(file_path, mimetype='image/jpeg')  # Adjust MIME type if necessary
    file = service.files().create(body=file_metadata, media_body=media, fields='id').execute()
    logger.info(f"Uploaded file to Google Drive with ID: {file.get('id')}")

# Function to extract text from an image using ImgOCR API
def extract_text_from_image_ocr(image_path):
    try:
        with open(image_path, 'rb') as image_file:
            file_data = base64.b64encode(image_file.read()).decode('utf-8')
        
        post_data = {
            'api_key': os.getenv('IMG_OCR_API_KEY'),  # Use the API key from the .env file
            'image': file_data
        }
        
        # Example of making a verified HTTPS request with httpx
        response = httpx.post('https://www.imgocr.com/api/imgocr_get_text', data=post_data, verify=True, timeout=10.0)  # Set timeout to 10 seconds

        if response.status_code == 200:
            return response.json().get('text', '')
        else:
            logger.error(f"Failed to extract text from image using ImgOCR: {response.text}")
            return None
    except Exception as e:
        logger.error(f"Error during ImgOCR text extraction for {image_path}: {e}")
        return None

# Update the handle_upload function to extract text using ImgOCR
async def handle_upload(update: Update, context: CallbackContext, upload_type: str) -> int:
    try:
        # Get the highest resolution image from the user's upload
        photo = update.message.photo[-1]
        photo_file = await photo.get_file()

        # Define the name for the image based on the upload type
        image_name = f"{upload_type.replace('_', ' ').title()}.jpg"
        image_path = IMAGE_FOLDER / image_name

        # Download the image file to the local file system
        await photo_file.download_to_drive(image_path)

        # Extract text from the image using ImgOCR
        extracted_text = extract_text_from_image_ocr(image_path)

        # Define the path where the PDF will be saved
        pdf_path = os.path.join(PDF_FOLDER, f"{upload_type.replace('_', ' ').title()}.pdf")

        if extracted_text and extracted_text.strip():
            # Create a real PDF with the extracted text
            create_pdf_with_text(extracted_text, pdf_path)
        else:
            raise ValueError("ImgOCR failed to extract any text from the image.")

        # Validate if the PDF file is correct
        if not is_valid_pdf(pdf_path):
            raise ValueError(f"The generated file at {pdf_path} is not a valid PDF.")

        # Send the PDF to the AI model for further processing
        extracted_data = extract_text_from_pdf(pdf_path)
        if extracted_data:
            logger.info(f"Extracted text from PDF: {json.dumps(extracted_data, indent=4)}")

            # If the upload type is 'log_card', process the JSON data and store it in the context
            if upload_type == 'log_card':
                context.user_data['extracted_data'] = extracted_data  # Store extracted data for later use

        else:
            logger.error("AI model could not extract text from the PDF.")

        # Mark the upload as done
        context.user_data['uploads'][upload_type] = True

        # Google Drive API setup
        SCOPES = ['https://www.googleapis.com/auth/drive.file']
        SERVICE_ACCOUNT_FILE = os.getenv('SERVICE_ACCOUNT')
        credentials = service_account.Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
        service = build('drive', 'v3', credentials=credentials)

        # Create a folder for the user based on their full name only if it doesn't exist
        user_full_name = context.user_data.get('full_name', 'Unknown_User')
        folder_link = create_drive_folder(service, user_full_name)

        # Upload the image to the created folder
        upload_file_to_drive(service, image_path, folder_link.split('/')[-1])

        # Store the folder link in user data for later use
        context.user_data['folder_link'] = folder_link

        # Send a thank you message to the user
        await update.message.reply_text(f"Thank you for uploading your {upload_type.replace('_', ' ')}.")

        # Check if all uploads are done
        if all(context.user_data['uploads'].values()):
            await show_additional_buttons(update, context)
            logger.info("All uploads completed. Transitioning to additional information input.")
            return CHOOSING

        return await show_upload_buttons(update, context)

    except Exception as e:
        logger.error(f"Error processing image: {e}")
        await update.message.reply_text(f"Failed to process image. Error: {str(e)}")
        return CHOOSING

# Function to show additional buttons for further information
async def show_additional_buttons(update: Update, context: CallbackContext) -> int:
    keyboard = [
        [InlineKeyboardButton("Agent Name", callback_data='agent_name')],
        [InlineKeyboardButton("Dealership", callback_data='dealership')],
        [InlineKeyboardButton("Agent Contact Info", callback_data='agent_contact_info')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Debugging log to ensure the additional buttons are being shown
    logger.info("Displaying additional buttons for further information (Agent Name, Dealership, Agent Contact Info).")
    
    await update.message.reply_text("Please provide the following information:", reply_markup=reply_markup)
    return CHOOSING  # Updated to CHOOSING to handle button clicks

# Function to handle the click on additional buttons and transition to the correct state for text input
async def additional_button_click(update: Update, context: CallbackContext) -> int:
    query = update.callback_query
    await query.answer()

    if query.data == 'agent_name':
        # Ask for Agent Name input and move to the AGENT_NAME_INPUT state
        await query.edit_message_text(text="Please enter the Agent Name:")
        logger.info("Transitioning to Agent Name input.")
        return AGENT_NAME_INPUT
    elif query.data == 'dealership':
        # Ask for Dealership input and move to the DEALERSHIP_INPUT state
        await query.edit_message_text(text="Please enter the Dealership:")
        logger.info("Transitioning to Dealership input.")
        return DEALERSHIP_INPUT
    elif query.data == 'agent_contact_info':
        # Ask for Agent Contact Info and move to the CONTACT_INFO_INPUT state
        await query.edit_message_text(text="Please enter the Agent Contact Info:")
        logger.info("Transitioning to Agent Contact Info input.")
        return CONTACT_INFO_INPUT

    return CHOOSING  # If no valid selection, remain in CHOOSING state

async def start(update: Update, context: CallbackContext) -> int:
    await update.message.reply_text("Welcome! Please enter the policy holder's full name:")
    return ASKING_NAME


# Handler to process the user's name and proceed with the welcome message
async def ask_name(update: Update, context: CallbackContext) -> int:
    full_name = update.message.text
    context.user_data['full_name'] = full_name

    company_name = "Bingo"
    welcome_message = (
        f"Hello {full_name}!\n"
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

# Function to show the remaining upload buttons
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

# Function to show additional buttons for further information
# Function to show additional buttons for further information
async def show_additional_buttons(update: Update, context: CallbackContext) -> int:
    keyboard = [
        [InlineKeyboardButton("Agent Name", callback_data='agent_name')],
        [InlineKeyboardButton("Dealership", callback_data='dealership')],
        [InlineKeyboardButton("Agent Contact Info", callback_data='agent_contact_info')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Please provide the following information:", reply_markup=reply_markup)
    return CHOOSING  # Updated to CHOOSING


# Function to handle the click on additional buttons and transition to the correct state for text input
async def additional_button_click(update: Update, context: CallbackContext) -> int:
    query = update.callback_query
    await query.answer()

    if query.data == 'agent_name':
        # Ask for Agent Name input and move to the AGENT_NAME_INPUT state
        await query.edit_message_text(text="Please enter the Agent Name:")
        return AGENT_NAME_INPUT
    elif query.data == 'dealership':
        # Ask for Dealership input and move to the DEALERSHIP_INPUT state
        await query.edit_message_text(text="Please enter the Dealership:")
        return DEALERSHIP_INPUT
    elif query.data == 'agent_contact_info':
        # Ask for Agent Contact Info and move to the CONTACT_INFO_INPUT state
        await query.edit_message_text(text="Please enter the Agent Contact Info:")
        return CONTACT_INFO_INPUT

    return CHOOSING  # If no valid selection, remain in CHOOSING state


# Handle input for Agent Name
async def agent_name_input(update: Update, context: CallbackContext) -> int:
    context.user_data['agent_name'] = update.message.text
    await update.message.reply_text(f"Agent Name saved: {update.message.text}")
    # Go back to additional button options
    await show_additional_buttons(update, context)
    return CHOOSING

# Handle input for Dealership
async def dealership_input(update: Update, context: CallbackContext) -> int:
    context.user_data['dealership'] = update.message.text
    await update.message.reply_text(f"Dealership saved: {update.message.text}")
    # Go back to additional button options
    await show_additional_buttons(update, context)
    return CHOOSING

# Handle input for Agent Contact Info
async def contact_info_input(update: Update, context: CallbackContext) -> int:
    context.user_data['agent_contact_info'] = update.message.text
    await update.message.reply_text(f"Agent Contact Info saved: {update.message.text}")
    # Once all info is entered, ask for confirmation
    await ask_for_confirmation(update, context)
    return CONFIRMATION

# Ask for final confirmation before storing data
async def ask_for_confirmation(update: Update, context: CallbackContext) -> int:
    confirmation_message = (
        "By replying YES, I confirm that I have informed the client that their information "
        "will be collected and used to generate an insurance quote."
    )
    await update.message.reply_text(confirmation_message)
    return CONFIRMATION



# Handle the user's response to the confirmation message
async def handle_confirmation(update: Update, context: CallbackContext) -> int:
    if update.message.text.strip().lower() == "yes":
        # If confirmed, process and store the data in Monday.com
        extracted_data = context.user_data.get('extracted_data', {})
        agent_name = context.user_data.get('agent_name', 'Unknown Agent')  # Get the agent name
        folder_link = context.user_data.get('folder_link', None)  # Get the folder link
        if extracted_data:
            process_log_card(extracted_data, context, source="Telegram", folder_link=folder_link)  # Pass folder_link
            await update.message.reply_text(f"Data has been successfully stored in Monday.com for Agent: {agent_name}.")  # Include agent name
            
            # Gather image paths from the image folder
            image_folder = '/Users/carlsaginsin/Projects/BingoTelegramBot/image_folder/*.jpg'
            image_paths = glob.glob(image_folder)  # Get all image paths

            # Call DocumentUpload.py with the image paths
            # subprocess.run(['python3', 'DocumentUpload.py'] + image_paths)

        else:
            await update.message.reply_text("No data found to store. Please try again.")
    else:
        await update.message.reply_text("Confirmation not received. Data will not be stored.")

    return ConversationHandler.END

# Function to show the upload buttons again
async def show_upload_buttons(update: Update, context: CallbackContext) -> int:
    await show_remaining_buttons(update, context)
    return CHOOSING

# Handle the click on upload buttons
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

# Handle the upload of the driver's license
async def license_upload(update: Update, context: CallbackContext) -> int:
    # Skip PDF creation for driver's license
    photo = update.message.photo[-1]
    photo_file = await photo.get_file()
    image_name = "Driver_License.jpg"
    image_path = IMAGE_FOLDER / image_name
    await photo_file.download_to_drive(image_path)
    
    # Extract text using ImgOCR
    extracted_text = extract_text_from_image_ocr(image_path)
    if extracted_text:
        logger.info(f"Extracted text from Driver's License: {extracted_text}")
        print("Driver's License Extracted Text:", extracted_text)  # Show extracted text in terminal
    
    # Google Drive API setup
    SCOPES = ['https://www.googleapis.com/auth/drive.file']
    SERVICE_ACCOUNT_FILE = os.getenv('SERVICE_ACCOUNT')
    credentials = service_account.Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
    service = build('drive', 'v3', credentials=credentials)

    # Create a folder for the user based on their full name only if it doesn't exist
    user_full_name = context.user_data.get('full_name', 'Unknown_User')
    folder_link = create_drive_folder(service, user_full_name)

    # Upload the image to the created folder
    upload_file_to_drive(service, image_path, folder_link.split('/')[-1])

    # Notify user that the upload was successful
    await update.message.reply_text("Driver's License uploaded successfully and text extracted.")
    context.user_data['uploads']['driver_license'] = True  # Mark as uploaded
    return await show_remaining_buttons(update, context)

# Handle the upload of the identity card
async def identity_card_upload(update: Update, context: CallbackContext) -> int:
    # Skip PDF creation for identity card
    photo = update.message.photo[-1]
    photo_file = await photo.get_file()
    image_name = "Identity_Card.jpg"
    image_path = IMAGE_FOLDER / image_name
    await photo_file.download_to_drive(image_path)
    
    # Extract text using ImgOCR
    extracted_text = extract_text_from_image_ocr(image_path)
    if extracted_text:
        logger.info(f"Extracted text from Identity Card: {extracted_text}")
        print("Identity Card Extracted Text:", extracted_text)  # Show extracted text in terminal
    
    # Google Drive API setup
    SCOPES = ['https://www.googleapis.com/auth/drive.file']
    SERVICE_ACCOUNT_FILE = os.getenv('SERVICE_ACCOUNT')
    credentials = service_account.Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
    service = build('drive', 'v3', credentials=credentials)

    # Create a folder for the user based on their full name only if it doesn't exist
    user_full_name = context.user_data.get('full_name', 'Unknown_User')
    folder_link = create_drive_folder(service, user_full_name)

    # Upload the image to the created folder
    upload_file_to_drive(service, image_path, folder_link.split('/')[-1])

    # Notify user that the upload was successful
    await update.message.reply_text("Identity Card uploaded successfully and text extracted.")
    context.user_data['uploads']['identity_card'] = True  # Mark as uploaded
    return await show_remaining_buttons(update, context)

# Handle the upload of the log card
async def log_card_upload(update: Update, context: CallbackContext) -> int:
    return await handle_upload(update, context, upload_type='log_card')  # Only log card will be processed


# Main function to run the bot
def main():
    application = Application.builder().token(TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],  # Ensure `start` is properly defined
        states={
            ASKING_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_name)],
            CHOOSING: [
                CallbackQueryHandler(upload_button_click, pattern='^upload_'),
                CallbackQueryHandler(additional_button_click, pattern='^(agent_name|dealership|agent_contact_info)$')
            ],
            UPLOAD_DRIVER_LICENSE: [MessageHandler(filters.PHOTO, license_upload)],
            UPLOAD_IDENTITY_CARD: [MessageHandler(filters.PHOTO, identity_card_upload)],
            UPLOAD_LOG_CARD: [MessageHandler(filters.PHOTO, log_card_upload)],
            AGENT_NAME_INPUT: [MessageHandler(filters.TEXT & ~filters.COMMAND, agent_name_input)],
            DEALERSHIP_INPUT: [MessageHandler(filters.TEXT & ~filters.COMMAND, dealership_input)],
            CONTACT_INFO_INPUT: [MessageHandler(filters.TEXT & ~filters.COMMAND, contact_info_input)],
            CONFIRMATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_confirmation)],
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