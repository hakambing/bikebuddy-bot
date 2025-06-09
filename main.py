import keep_alive
keep_alive.keep_alive()

import gspread
import json
import os
from oauth2client.service_account import ServiceAccountCredentials
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Updater, CommandHandler, MessageHandler, Filters,
    CallbackContext, CallbackQueryHandler, ConversationHandler
)
import logging
from datetime import datetime

# Logging
logging.basicConfig(level=logging.INFO)

# Google Sheets setup
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds_json = json.loads(os.getenv("GOOGLE_CREDENTIALS_JSON"))
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_json, scope)
client = gspread.authorize(creds)
sheet = client.open("Motorcycle Maintenance Log").sheet1

# Telegram token from environment
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")

# Step-by-step states
DATE, MAINT_TYPE, PRICE, LOCATION, REMARKS, MILEAGE = range(6)

# === Quick /log ===
def log_maintenance(update, context):
    try:
        text = ' '.join(context.args)
        date, maint_type, price, location, remarks, mileage = [s.strip() for s in text.split(',')]
        sheet.append_row([date, maint_type, price, location, remarks, mileage])
        update.message.reply_text("✅ Maintenance logged!")
    except Exception as e:
        logging.error(str(e))
        update.message.reply_text("⚠️ Format error. Use:\n/log 2025-06-09, Maintenance Type, Price, Location, Remarks, Current Mileage")

# === Step-by-step /logstep ===
def start_logstep(update: Update, context: CallbackContext):
    keyboard = [[InlineKeyboardButton("Today", callback_data="today")]]
    update.message.reply_text("📅 Enter maintenance date or choose:", reply_markup=InlineKeyboardMarkup(keyboard))
    return DATE

def date_handler(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    today_str = datetime.now().strftime("%Y-%m-%d")
    context.user_data['date'] = today_str
    return ask_maint_type(query, context)

def date_text(update: Update, context: CallbackContext):
    context.user_data['date'] = update.message.text.strip()
    return ask_maint_type(update, context)

def ask_maint_type(origin, context):
    keyboard = [
        [InlineKeyboardButton("Engine Oil", callback_data="Engine Oil"), InlineKeyboardButton("Air Filter", callback_data="Air Filter")],
        [InlineKeyboardButton("Spark Plug", callback_data="Spark Plug"), InlineKeyboardButton("Brake Pad", callback_data="Brake Pad")],
        [InlineKeyboardButton("Coolant Flush", callback_data="Coolant Flush"), InlineKeyboardButton("Brake Flush", callback_data="Brake Flush")],
        [InlineKeyboardButton("Tyre Change", callback_data="Tyre Change")]
    ]
    if hasattr(origin, 'message'):
        origin.message.reply_text("🔧 Select maintenance type or type your own:", reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        origin.edit_message_text("🔧 Select maintenance type or type your own:", reply_markup=InlineKeyboardMarkup(keyboard))
    return MAINT_TYPE

def maint_type_handler(update: Update, context: CallbackContext):
    if update.callback_query:
        query = update.callback_query
        query.answer()
        context.user_data['maint_type'] = query.data
        query.message.reply_text("💵 Enter price:")
    else:
        context.user_data['maint_type'] = update.message.text.strip()
        update.message.reply_text("💵 Enter price:")
    return PRICE

def price_handler(update: Update, context: CallbackContext):
    context.user_data['price'] = update.message.text.strip()
    keyboard = [
        [InlineKeyboardButton("Sports Motor Woodlands", callback_data="Sports Motor Woodlands")],
        [InlineKeyboardButton("WeiTek JB", callback_data="WeiTek JB")],
        [InlineKeyboardButton("AhBoy JB", callback_data="AhBoy JB")],
        [InlineKeyboardButton("Myself", callback_data="Myself")]
    ]
    update.message.reply_text("📍 Select location:", reply_markup=InlineKeyboardMarkup(keyboard))
    return LOCATION

def location_handler(update: Update, context: CallbackContext):
    if update.callback_query:
        query = update.callback_query
        query.answer()
        context.user_data['location'] = query.data
        query.message.reply_text("📝 Enter remarks:")
    else:
        context.user_data['location'] = update.message.text.strip()
        update.message.reply_text("📝 Enter remarks:")
    return REMARKS

def remarks_handler(update: Update, context: CallbackContext):
    context.user_data['remarks'] = update.message.text.strip()
    update.message.reply_text("📈 Enter total mileage:")
    return MILEAGE

def mileage_handler(update: Update, context: CallbackContext):
    context.user_data['mileage'] = update.message.text.strip()
    data = [
        context.user_data['date'],
        context.user_data['maint_type'],
        context.user_data['price'],
        context.user_data['location'],
        context.user_data['remarks'],
        context.user_data['mileage']
    ]
    sheet.append_row(data)
    update.message.reply_text("✅ Maintenance logged successfully!")
    return ConversationHandler.END

def cancel(update: Update, context: CallbackContext):
    update.message.reply_text("🚫 Cancelled.")
    return ConversationHandler.END

# === MAIN ===
updater = Updater(TELEGRAM_TOKEN, use_context=True)
dp = updater.dispatcher

# /log (quick)
dp.add_handler(CommandHandler("log", log_maintenance))

# /logstep (guided)
conv_handler = ConversationHandler(
    entry_points=[CommandHandler('logstep', start_logstep)],
    states={
        DATE: [CallbackQueryHandler(date_handler), MessageHandler(Filters.text & ~Filters.command, date_text)],
        MAINT_TYPE: [
            CallbackQueryHandler(maint_type_handler),
            MessageHandler(Filters.text & ~Filters.command, maint_type_handler)
        ],
        PRICE: [MessageHandler(Filters.text & ~Filters.command, price_handler)],
        LOCATION: [
            CallbackQueryHandler(location_handler),
            MessageHandler(Filters.text & ~Filters.command, location_handler)
        ],
        REMARKS: [MessageHandler(Filters.text & ~Filters.command, remarks_handler)],
        MILEAGE: [MessageHandler(Filters.text & ~Filters.command, mileage_handler)]
    },
    fallbacks=[CommandHandler('cancel', cancel)],
    per_message=False
)

dp.add_handler(conv_handler)
updater.start_polling()
