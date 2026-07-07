import os
import logging
from io import BytesIO
from PIL import Image
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackQueryHandler, ContextTypes
import requests

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Bot token from environment variable
TOKEN = os.environ.get('BOT_TOKEN')

# Supported formats
SUPPORTED_FORMATS = {
    'JPEG': 'jpeg',
    'PNG': 'png',
    'WEBP': 'webp',
    'GIF': 'gif',
    'BMP': 'bmp',
    'TIFF': 'tiff',
    'PDF': 'pdf'
}

# Store user data temporarily
user_data = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a message when /start is issued."""
    user = update.effective_user
    await update.message.reply_text(
        f"Hi {user.first_name}! 👋\n\n"
        "I'm an Image Converter Bot. Send me an image and I'll convert it to your desired format.\n\n"
        "📤 How to use:\n"
        "1. Send me any image\n"
        "2. Choose the format you want to convert to\n"
        "3. I'll send you back the converted image\n\n"
        "Supported formats: JPEG, PNG, WEBP, GIF, BMP, TIFF, PDF"
    )

async def handle_image(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle received images."""
    user_id = update.effective_user.id
    
    # Get the image file
    photo_file = await update.message.photo[-1].get_file()
    file_path = photo_file.file_path
    
    # Download image
    response = requests.get(file_path)
    image_data = response.content
    
    # Store in user data
    user_data[user_id] = {
        'image_data': image_data,
        'original_format': 'jpg'  # Default format from Telegram
    }
    
    # Create inline keyboard for format selection
    keyboard = []
    formats = list(SUPPORTED_FORMATS.keys())
    for i in range(0, len(formats), 3):
        row = []
        for fmt in formats[i:i+3]:
            row.append(InlineKeyboardButton(fmt, callback_data=fmt))
        keyboard.append(row)
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "🔄 Choose the format you want to convert to:",
        reply_markup=reply_markup
    )

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle document images."""
    user_id = update.effective_user.id
    document = update.message.document
    
    # Check if it's an image
    if document.mime_type and document.mime_type.startswith('image/'):
        file = await document.get_file()
        image_data = await file.download_as_bytearray()
        
        # Store in user data
        user_data[user_id] = {
            'image_data': image_data,
            'original_format': document.mime_type.split('/')[-1]
        }
        
        # Create inline keyboard for format selection
        keyboard = []
        formats = list(SUPPORTED_FORMATS.keys())
        for i in range(0, len(formats), 3):
            row = []
            for fmt in formats[i:i+3]:
                row.append(InlineKeyboardButton(fmt, callback_data=fmt))
            keyboard.append(row)
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "🔄 Choose the format you want to convert to:",
            reply_markup=reply_markup
        )
    else:
        await update.message.reply_text("❌ Please send an image file.")

async def format_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle format selection callback."""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    selected_format = query.data
    
    if user_id not in user_data:
        await query.edit_message_text("❌ Please send an image first.")
        return
    
    # Get stored image
    image_data = user_data[user_id]['image_data']
    
    try:
        # Convert image
        converted_image = await convert_image(image_data, selected_format)
        
        # Send converted image
        format_lower = SUPPORTED_FORMATS[selected_format]
        filename = f"converted.{format_lower}"
        
        # Check if it's PDF
        if format_lower == 'pdf':
            await query.message.reply_document(
                document=converted_image,
                filename=filename,
                caption=f"✅ Converted to {selected_format}"
            )
        else:
            await query.message.reply_photo(
                photo=converted_image,
                filename=filename,
                caption=f"✅ Converted to {selected_format}"
            )
        
        # Clean up user data
        del user_data[user_id]
        
    except Exception as e:
        logger.error(f"Conversion error: {e}")
        await query.edit_message_text("❌ Sorry, failed to convert the image. Please try again.")

async def convert_image(image_data, target_format):
    """Convert image to target format."""
    # Open image
    img = Image.open(BytesIO(image_data))
    
    # Convert RGBA to RGB for JPEG
    if target_format in ['JPEG'] and img.mode == 'RGBA':
        # Create a white background
        background = Image.new('RGB', img.size, (255, 255, 255))
        background.paste(img, mask=img.split()[3])  # Use alpha channel as mask
        img = background
    elif img.mode not in ['RGB', 'L'] and target_format != 'PDF':
        img = img.convert('RGB')
    
    # Save to bytes
    output = BytesIO()
    format_lower = SUPPORTED_FORMATS[target_format]
    
    if format_lower == 'pdf':
        # For PDF, we need to use save with PDF format
        img.save(output, format='PDF', resolution=100.0)
    else:
        img.save(output, format=format_lower, quality=95)
    
    output.seek(0)
    return output

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a message when /help is issued."""
    await update.message.reply_text(
        "📖 Help Center\n\n"
        "How to use:\n"
        "1. Send me an image (photo or document)\n"
        "2. Choose your desired format from the buttons\n"
        "3. Wait for me to convert and send it back\n\n"
        "Supported formats:\n"
        "• JPEG (best for photos)\n"
        "• PNG (supports transparency)\n"
        "• WEBP (modern format)\n"
        "• GIF (animation support)\n"
        "• BMP (lossless)\n"
        "• TIFF (high quality)\n"
        "• PDF (document format)"
    )

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Log errors."""
    logger.error(f"Update {update} caused error {context.error}")

def main():
    """Start the bot."""
    # Create the Application
    application = Application.builder().token(TOKEN).build()

    # Add command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    
    # Add message handlers
    application.add_handler(MessageHandler(filters.PHOTO, handle_image))
    application.add_handler(MessageHandler(filters.Document.IMAGE, handle_document))
    
    # Add callback handler for format selection
    application.add_handler(CallbackQueryHandler(format_callback))
    
    # Add error handler
    application.add_error_handler(error_handler)

    # Start the Bot
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
