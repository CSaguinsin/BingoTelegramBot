import logging
import asyncio
import nest_asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, CallbackContext
from config import TOKEN

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname=s - %(message)s',
    level=logging.INFO
)

logger = logging.getLogger(__name__)

# Apply nest_asyncio
nest_asyncio.apply()

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
        # Store clicked buttons for personal info
        context.user_data['personal_info_clicks'] = context.user_data.get('personal_info_clicks', set())
        context.user_data['personal_info_clicks'].add(query.data)
        context.user_data['personal_info_step'] = query.data

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
        if expected_document == 'drivers_license':
            await update.message.reply_text("Driver's License received successfully.")
        elif expected_document == 'identity_card':
            await update.message.reply_text("Identity Card received successfully.")
        elif expected_document == 'log_card':
            await update.message.reply_text("Log Card received successfully.")
        elif expected_document == 'comprehensive':
            await update.message.reply_text("Comprehensive document received successfully.")
        elif expected_document == 'tpft':
            await update.message.reply_text("TPFT document received successfully.")
        elif expected_document == 'tpo':
            await update.message.reply_text("TPO document received successfully.")

        # Track uploaded documents
        context.user_data['uploaded_documents'] = context.user_data.get('uploaded_documents', set())
        context.user_data['uploaded_documents'].add(expected_document)

        # After the document is uploaded, show the remaining buttons
        remaining_buttons = []
        if expected_document in {'drivers_license', 'identity_card', 'log_card'}:
            if 'upload_drivers_license' not in context.user_data['clicked_buttons']:
                remaining_buttons.append([InlineKeyboardButton("Upload Driver's License", callback_data='upload_drivers_license')])
            if 'upload_identity_card' not in context.user_data['clicked_buttons']:
                remaining_buttons.append([InlineKeyboardButton("Upload Identity Card", callback_data='upload_identity_card')])
            if 'upload_log_card' not in context.user_data['clicked_buttons']:
                remaining_buttons.append([InlineKeyboardButton("Upload Log Card", callback_data='upload_log_card')])

            if remaining_buttons:
                reply_markup = InlineKeyboardMarkup(remaining_buttons)
                await update.message.reply_text("Please upload the remaining documents:", reply_markup=reply_markup)

            # Check if all initial documents are uploaded
            if {'upload_drivers_license', 'upload_identity_card', 'upload_log_card'}.issubset(context.user_data['clicked_buttons']):
                # Show the next set of buttons for insurance options
                next_keyboard = [
                    [InlineKeyboardButton("Upload Comprehensive", callback_data='comprehensive')],
                    [InlineKeyboardButton("Upload TPFT", callback_data='tpft')],
                    [InlineKeyboardButton("Upload TPO", callback_data='tpo')]
                ]
                next_reply_markup = InlineKeyboardMarkup(next_keyboard)
                await update.message.reply_text("Please upload your insurance documents:", reply_markup=next_reply_markup)

        elif expected_document in {'comprehensive', 'tpft', 'tpo'}:
            if 'comprehensive' not in context.user_data['uploaded_documents']:
                remaining_buttons.append([InlineKeyboardButton("Upload Comprehensive", callback_data='comprehensive')])
            if 'tpft' not in context.user_data['uploaded_documents']:
                remaining_buttons.append([InlineKeyboardButton("Upload TPFT", callback_data='tpft')])
            if 'tpo' not in context.user_data['uploaded_documents']:
                remaining_buttons.append([InlineKeyboardButton("Upload TPO", callback_data='tpo')])

            if remaining_buttons:
                reply_markup = InlineKeyboardMarkup(remaining_buttons)
                await update.message.reply_text("Please upload the remaining insurance documents:", reply_markup=reply_markup)

            # Check if all insurance documents are uploaded
            if {'comprehensive', 'tpft', 'tpo'}.issubset(context.user_data['uploaded_documents']):
                next_keyboard = [
                    [InlineKeyboardButton("Agent Name", callback_data='agent_name')],
                    [InlineKeyboardButton("Dealership", callback_data='dealership')],
                    [InlineKeyboardButton("Contact Info", callback_data='contact_info')]
                ]
                next_reply_markup = InlineKeyboardMarkup(next_keyboard)
                await update.message.reply_text("Please provide the following information:", reply_markup=next_reply_markup)
    else:
        await update.message.reply_text("Please upload a valid image file (jpg or png format).")

# Define the text input handler
async def handle_text(update: Update, context: CallbackContext) -> None:
    if update.message is None:
        return

    user_response = update.message.text.strip()

    if 'personal_info_step' in context.user_data:
        personal_info_key = context.user_data['personal_info_step']

        if personal_info_key == 'contact_info' and not user_response.isdigit():
            await update.message.reply_text("Please enter a valid number for Contact Info.")
            return

        context.user_data[personal_info_key] = user_response
        context.user_data['personal_info_step'] = None  # Reset the state

        await update.message.reply_text(f"Your {personal_info_key.replace('_', ' ').title()} has been recorded.")

        # Show remaining personal info buttons
        remaining_buttons = []
        if 'agent_name' not in context.user_data['personal_info_clicks']:
            remaining_buttons.append([InlineKeyboardButton("Agent Name", callback_data='agent_name')])
        if 'dealership' not in context.user_data['personal_info_clicks']:
            remaining_buttons.append([InlineKeyboardButton("Dealership", callback_data='dealership')])
        if 'contact_info' not in context.user_data['personal_info_clicks']:
            remaining_buttons.append([InlineKeyboardButton("Contact Info", callback_data='contact_info')])

        if remaining_buttons:
            reply_markup = InlineKeyboardMarkup(remaining_buttons)
            await update.message.reply_text("Please provide the remaining information:", reply_markup=reply_markup)

        # Check if all personal information is provided
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
            # Reset all user data after submission
            context.user_data.clear()
        else:
            await update.message.reply_text("Please type SUBMIT to complete the process.")

# Main function to start the bot
async def main() -> None:
    # Initialize the bot application
    application = Application.builder().token(TOKEN).build()
    # Add handlers
    application.add_handler(CommandHandler('start', start))
    application.add_handler(CallbackQueryHandler(button))
    application.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    # Start the bot
    await application.run_polling()

if __name__ == '__main__':
    asyncio.run(main())