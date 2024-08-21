import logging
import asyncio
import nest_asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, CallbackContext
from config import TOKEN, TIMEZONE, TIMEZONE_COMMON_NAME, BOT_USERNAME

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

logger = logging.getLogger(__name__)

# Apply nest_asyncio
nest_asyncio.apply()

# Define a few command handlers
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

    # Create the upload buttons
    keyboard = [
        [InlineKeyboardButton("Upload Identity Card", callback_data='upload_identity_card')],
        [InlineKeyboardButton("Upload Log Card", callback_data='upload_log_card')],
        [InlineKeyboardButton("Upload Driver's License", callback_data='upload_drivers_license')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Please upload the following documents:", reply_markup=reply_markup)

async def button(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    await query.answer()

    context.user_data['clicked_buttons'] = context.user_data.get('clicked_buttons', set())
    context.user_data['clicked_buttons'].add(query.data)

    if query.data == 'upload_identity_card':
        await query.edit_message_text(text="Please upload your Identity Card (jpg or png format).")
        context.user_data['expected_document'] = 'identity_card'
    elif query.data == 'upload_log_card':
        await query.edit_message_text(text="Please upload your Log Card (jpg or png format).")
        context.user_data['expected_document'] = 'log_card'
    elif query.data == 'upload_drivers_license':
        await query.edit_message_text(text="Please upload your Driver's License (jpg or png format).")
        context.user_data['expected_document'] = 'drivers_license'
    elif query.data in {'comprehensive', 'tpft', 'tpo', 'dealership', 'agent_name', 'contact_info'}:
        context.user_data['selected_options'] = context.user_data.get('selected_options', set())
        context.user_data['selected_options'].add(query.data)
        await query.edit_message_text(text=f"Option {query.data.replace('_', ' ').title()} selected.")

        # Check if all options are selected
        if {'comprehensive', 'tpft', 'tpo', 'dealership', 'agent_name', 'contact_info'}.issubset(context.user_data['selected_options']):
            await update.effective_chat.send_message(
                "By typing Submit, I confirm that I have informed the client that their information will be collected and used to generate an insurance quote."
            )

async def handle_document(update: Update, context: CallbackContext) -> None:
    logger.info("handle_document called")
    document = update.message.document
    expected_document = context.user_data.get('expected_document')

    if document.mime_type in ['image/jpeg', 'image/png']:
        logger.info(f"Received document: {expected_document}")
        if expected_document == 'identity_card':
            await update.message.reply_text("Identity Card received successfully.")
        elif expected_document == 'log_card':
            await update.message.reply_text("Log Card received successfully.")
        elif expected_document == 'drivers_license':
            await update.message.reply_text("Driver's License received successfully.")
        else:
            await update.message.reply_text("Document received successfully.")

        # Check if all documents are uploaded
        if {'upload_identity_card', 'upload_log_card', 'upload_drivers_license'}.issubset(context.user_data['clicked_buttons']):
            # Show the next set of buttons
            next_keyboard = [
                [InlineKeyboardButton("Comprehensive", callback_data='comprehensive')],
                [InlineKeyboardButton("TPFT", callback_data='tpft')],
                [InlineKeyboardButton("TPO", callback_data='tpo')],
                [InlineKeyboardButton("Dealership", callback_data='dealership')],
                [InlineKeyboardButton("Agent Name", callback_data='agent_name')],
                [InlineKeyboardButton("Contact Info", callback_data='contact_info')]
            ]
            next_reply_markup = InlineKeyboardMarkup(next_keyboard)
            await update.message.reply_text("Please choose options below:", reply_markup=next_reply_markup)
        else:
            # Show the remaining buttons
            remaining_buttons = []
            if 'upload_identity_card' not in context.user_data['clicked_buttons']:
                remaining_buttons.append([InlineKeyboardButton("Upload Identity Card", callback_data='upload_identity_card')])
            if 'upload_log_card' not in context.user_data['clicked_buttons']:
                remaining_buttons.append([InlineKeyboardButton("Upload Log Card", callback_data='upload_log_card')])
            if 'upload_drivers_license' not in context.user_data['clicked_buttons']:
                remaining_buttons.append([InlineKeyboardButton("Upload Driver's License", callback_data='upload_drivers_license')])

            if remaining_buttons:
                reply_markup = InlineKeyboardMarkup(remaining_buttons)
                await update.message.reply_text("Please upload the remaining documents:", reply_markup=reply_markup)
    else:
        await update.message.reply_text("Please upload a valid image file (jpg or png format).")

async def handle_text(update: Update, context: CallbackContext) -> None:
    text = update.message.text.strip().lower()
    if text == "submit":
        await update.message.reply_text("Thank you for your submission. Have a great day!")
    else:
        await update.message.reply_text(update.message.text)

async def help_command(update: Update, context: CallbackContext) -> None:
    await update.message.reply_text('Help!')

async def main() -> None:
    # Create the Application and pass it your bot's token.
    application = Application.builder().token(TOKEN).build()

    # on different commands - answer in Telegram
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CallbackQueryHandler(button))
    application.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    # Start the Bot
    await application.run_polling()

if __name__ == '__main__':
    asyncio.run(main())
