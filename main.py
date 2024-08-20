import logging
import asyncio
import nest_asyncio
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackContext
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
    await update.message.reply_text(f'Hi! I am {BOT_USERNAME}. How can I assist you today?')

async def help_command(update: Update, context: CallbackContext) -> None:
    await update.message.reply_text('Help!')

async def echo(update: Update, context: CallbackContext) -> None:
    await update.message.reply_text(update.message.text)

async def main() -> None:
    # Create the Application and pass it your bot's token.
    application = Application.builder().token(TOKEN).build()

    # on different commands - answer in Telegram
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))

    # on non-command i.e message - echo the message on Telegram
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))

    # Start the Bot
    await application.run_polling()

if __name__ == '__main__':
    asyncio.run(main())
