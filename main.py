import keep_alive
keep_alive.keep_alive()

import os
import httpx
import csv
from io import StringIO
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update, InputFile
from telegram.ext import (
    Updater, CommandHandler, MessageHandler, Filters,
    CallbackContext, CallbackQueryHandler, ConversationHandler
)
import logging
from datetime import datetime

# Logging
logging.basicConfig(level=logging.INFO)

# Supabase setup
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY")
HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json"
}
TABLE = "hakam_motorcycle_maintenance"

# Telegram token
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")

# States for /logstep conversation
DATE, MAINT_TYPE, PRICE, LOCATION, REMARKS, MILEAGE = range(6)

# === Quick /log ===
def log_maintenance(update, context):
    try:
        text = ' '.join(context.args)
        date, maint_type, price, location, remarks, mileage = [s.strip() for s in text.split(',')]
        payload = {
            "date": date,
            "maintenance_type": maint_type,
            "price": price,
            "location": location,
            "remarks": remarks,
            "total_mileage": mileage
        }
        res = httpx.post(f"{SUPABASE_URL}/rest/v1/{TABLE}", headers=HEADERS, json=payload)
        if res.status_code == 201:
            update.message.reply_text("✅ Maintenance logged!")
        else:
            logging.error(res.text)
            update.message.reply_text("❌ Failed to log maintenance.")
    except Exception as e:
        logging.error(e)
        update.message.reply_text(
            "⚠️ Use: /log YYYY-MM-DD, Type, Price, Location, Remarks, Mileage"
        )

# === Step-by-step /logstep ===
def start_logstep(update: Update, context: CallbackContext):
    keyboard = [[InlineKeyboardButton("Today", callback_data="today")]]
    update.message.reply_text("📅 Enter maintenance date or choose:", reply_markup=InlineKeyboardMarkup(keyboard))
    return DATE


def date_handler(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    context.user_data['date'] = datetime.now().strftime("%Y-%m-%d")
    return ask_maint_type(query, context)


def date_text(update: Update, context: CallbackContext):
    context.user_data['date'] = update.message.text.strip()
    return ask_maint_type(update, context)


def ask_maint_type(origin, context):
    options = ["Engine Oil","Air Filter","Spark Plug","Brake Pad","Coolant Flush","Brake Flush","Tyre Change"]
    keyboard = [[InlineKeyboardButton(opt, callback_data=opt) for opt in options[i:i+2]] for i in range(0,len(options),2)]
    send = origin.message if hasattr(origin, 'message') else origin
    send.reply_text("🔧 Select maintenance type or type your own:", reply_markup=InlineKeyboardMarkup(keyboard))
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
    locations = ["WeiTek JB","Choong Kok Agency","Myself"]
    keyboard = [[InlineKeyboardButton(loc, callback_data=loc)] for loc in locations]
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
    payload = {
        "date": context.user_data['date'],
        "maintenance_type": context.user_data['maint_type'],
        "price": context.user_data['price'],
        "location": context.user_data['location'],
        "remarks": context.user_data['remarks'],
        "total_mileage": context.user_data['mileage']
    }
    res = httpx.post(f"{SUPABASE_URL}/rest/v1/{TABLE}", headers=HEADERS, json=payload)
    if res.status_code == 201:
        update.message.reply_text("✅ Maintenance logged successfully!")
    else:
        logging.error(res.text)
        update.message.reply_text("❌ Failed to log maintenance.")
    return ConversationHandler.END


def cancel(update: Update, context: CallbackContext):
    update.message.reply_text("🚫 Cancelled.")
    return ConversationHandler.END

# === /viewlast ===
def viewlast_command(update: Update, context: CallbackContext):
    options = ["Engine Oil","Air Filter","Spark Plug","Brake Pad","Coolant Flush","Brake Flush","Tyre Change"]
    keyboard = [[InlineKeyboardButton(opt, callback_data=f"viewlast_{opt}")] for opt in options]
    keyboard.append([InlineKeyboardButton("Latest Entry", callback_data="viewlast_latest")])
    update.message.reply_text("🔍 Select type to view last record:", reply_markup=InlineKeyboardMarkup(keyboard))


def viewlast_handler(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    sel = query.data.replace("viewlast_", "")
    if sel.lower() == "latest":
        url = f"{SUPABASE_URL}/rest/v1/{TABLE}?select=*&order=id.desc&limit=1"
    else:
        url = (f"{SUPABASE_URL}/rest/v1/{TABLE}?select=*&"
               f"maintenance_type=eq.{sel}&order=id.desc&limit=1")
    res = httpx.get(url, headers=HEADERS)
    data = res.json() if res.is_success else []
    if not data:
        query.message.reply_text(f"❌ No records found for '{sel}'.")
        return
    row = data[0]
    msg = (f"📅 *Date:* {row['date']}\n"
           f"🔧 *Type:* {row['maintenance_type']}\n"
           f"💵 *Price:* {row['price']}\n"
           f"📍 *Location:* {row['location']}\n"
           f"📝 *Remarks:* {row['remarks']}\n"
           f"📈 *Mileage:* {row['total_mileage']}")
    query.message.reply_text(msg, parse_mode="Markdown")

# === /updatelast ===
def updatelast(update: Update, context: CallbackContext):
    args = context.args
    if len(args) < 2:
        update.message.reply_text("Usage: /updatelast <field> <new_value>")
        return
    field = args[0]
    valid = ["date","maintenance_type","price","location","remarks","total_mileage"]
    if field not in valid:
        update.message.reply_text(f"Field must be one of: {', '.join(valid)}")
        return
    new_val = ' '.join(args[1:])
    url_id = f"{SUPABASE_URL}/rest/v1/{TABLE}?select=id&order=id.desc&limit=1"
    r = httpx.get(url_id, headers=HEADERS)
    rec = r.json() if r.is_success else []
    if not rec:
        update.message.reply_text("❌ No record found to update.")
        return
    rid = rec[0]['id']
    res = httpx.patch(f"{SUPABASE_URL}/rest/v1/{TABLE}?id=eq.{rid}", headers=HEADERS, json={field: new_val})
    if res.status_code in (204,200):
        update.message.reply_text(f"✅ Updated record {rid} field {field}.")
    else:
        logging.error(res.text)
        update.message.reply_text("❌ Update failed.")

# === /updaterecord ===
def updaterecord(update: Update, context: CallbackContext):
    args = context.args
    if len(args) < 3:
        update.message.reply_text("Usage: /updaterecord <id> <field> <new_value>")
        return
    rid, field = args[0], args[1]
    new_val = ' '.join(args[2:])
    valid = ["date","maintenance_type","price","location","remarks","total_mileage"]
    if field not in valid:
        update.message.reply_text(f"Field must be one of: {', '.join(valid)}")
        return
    res = httpx.patch(f"{SUPABASE_URL}/rest/v1/{TABLE}?id=eq.{rid}", headers=HEADERS, json={field: new_val})
    if res.status_code in (204,200):
        update.message.reply_text(f"✅ Updated record {rid} field {field}.")
    else:
        logging.error(res.text)
        update.message.reply_text("❌ Update failed.")

# === /deletelast ===
def deletelast(update: Update, context: CallbackContext):
    # Get the latest record with full details
    url = f"{SUPABASE_URL}/rest/v1/{TABLE}?select=*&order=id.desc&limit=1"
    r = httpx.get(url, headers=HEADERS)
    rec = r.json() if r.is_success else []
    if not rec:
        update.message.reply_text("❌ No record to delete.")
        return
    
    record = rec[0]
    # Show record details and confirmation
    msg = (f"⚠️ **Are you sure you want to delete this record?**\n\n"
           f"📅 *Date:* {record['date']}\n"
           f"🔧 *Type:* {record['maintenance_type']}\n"
           f"💵 *Price:* {record['price']}\n"
           f"📍 *Location:* {record['location']}\n"
           f"📝 *Remarks:* {record['remarks']}\n"
           f"📈 *Mileage:* {record['total_mileage']}")
    
    keyboard = [
        [InlineKeyboardButton("✅ Yes, Delete", callback_data=f"confirm_delete_{record['id']}"),
         InlineKeyboardButton("❌ Cancel", callback_data="cancel_delete")]
    ]
    update.message.reply_text(msg, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

# === /deleterecord ===
def deleterecord(update: Update, context: CallbackContext):
    args = context.args
    if len(args) < 1:
        update.message.reply_text("Usage: /deleterecord <id>")
        return
    
    rid = args[0]
    # First, get the record details to show user what they're deleting
    url = f"{SUPABASE_URL}/rest/v1/{TABLE}?select=*&id=eq.{rid}"
    r = httpx.get(url, headers=HEADERS)
    rec = r.json() if r.is_success else []
    
    if not rec:
        update.message.reply_text(f"❌ No record found with ID {rid}.")
        return
    
    record = rec[0]
    # Show record details and confirmation
    msg = (f"⚠️ **Are you sure you want to delete record {rid}?**\n\n"
           f"📅 *Date:* {record['date']}\n"
           f"🔧 *Type:* {record['maintenance_type']}\n"
           f"💵 *Price:* {record['price']}\n"
           f"📍 *Location:* {record['location']}\n"
           f"📝 *Remarks:* {record['remarks']}\n"
           f"📈 *Mileage:* {record['total_mileage']}")
    
    keyboard = [
        [InlineKeyboardButton("✅ Yes, Delete", callback_data=f"confirm_delete_{record['id']}"),
         InlineKeyboardButton("❌ Cancel", callback_data="cancel_delete")]
    ]
    update.message.reply_text(msg, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

# === Delete confirmation handlers ===
def delete_confirmation_handler(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    
    if query.data == "cancel_delete":
        query.message.edit_text("🚫 Delete cancelled.")
        return
    
    # Extract record ID from callback data
    if query.data.startswith("confirm_delete_"):
        rid = query.data.replace("confirm_delete_", "")
        
        # Perform the actual deletion
        res = httpx.delete(f"{SUPABASE_URL}/rest/v1/{TABLE}?id=eq.{rid}", headers=HEADERS)
        
        if res.status_code == 204:
            query.message.edit_text(f"✅ Record {rid} has been deleted successfully.")
        else:
            logging.error(res.text)
            query.message.edit_text("❌ Delete failed. Please try again.")

# === /export ===
def export_data(update: Update, context: CallbackContext):
    try:
        res = httpx.get(f"{SUPABASE_URL}/rest/v1/{TABLE}?select=*&order=date.desc", headers=HEADERS)
        if not res.is_success:
            update.message.reply_text("❌ Failed to fetch data.")
            return
        
        data = res.json()
        if not data:
            update.message.reply_text("❌ No data to export.")
            return
        
        # Create CSV
        output = StringIO()
        writer = csv.writer(output)
        writer.writerow(["ID", "Date", "Maintenance Type", "Price", "Location", "Remarks", "Total Mileage"])
        
        for row in data:
            writer.writerow([
                row.get('id', ''),
                row.get('date', ''),
                row.get('maintenance_type', ''),
                row.get('price', ''),
                row.get('location', ''),
                row.get('remarks', ''),
                row.get('total_mileage', '')
            ])
        
        csv_content = output.getvalue()
        output.close()
        
        # Send as document
        csv_file = InputFile(StringIO(csv_content), filename="maintenance_records.csv")
        update.message.reply_document(csv_file, caption="📊 Your maintenance records")
        
    except Exception as e:
        logging.error(f"Export error: {e}")
        update.message.reply_text("❌ Export failed.")

# === /help ===
def help_command(update: Update, context: CallbackContext):
    help_text = """
🏍️ **Bot Commands:**

**Logging:**
• `/log` - Quick log: date,type,price,location,remarks,mileage
• `/logstep` - Step-by-step guided logging

**Viewing:**
• `/viewlast` - View last maintenance record by type

**Updating:**
• `/updatelast <field> <value>` - Update last record
• `/updaterecord <id> <field> <value>` - Update specific record

**Deleting:**
• `/deletelast` - Delete last record
• `/deleterecord <id>` - Delete specific record

**Export:**
• `/export` - Export all records as CSV
    """
    update.message.reply_text(help_text, parse_mode="Markdown")

def main():
    """Start the bot."""
    # Create the Updater and pass it your bot's token
    updater = Updater(TELEGRAM_TOKEN, use_context=True)
    
    # Get the dispatcher to register handlers
    dp = updater.dispatcher
    
    # Command handlers
    dp.add_handler(CommandHandler("log", log_maintenance))
    dp.add_handler(CommandHandler("updatelast", updatelast))
    dp.add_handler(CommandHandler("updaterecord", updaterecord))
    dp.add_handler(CommandHandler("deletelast", deletelast))
    dp.add_handler(CommandHandler("deleterecord", deleterecord))
    dp.add_handler(CommandHandler("export", export_data))
    dp.add_handler(CommandHandler("help", help_command))
    dp.add_handler(CommandHandler("start", help_command))
    
    # Callback query handlers
    dp.add_handler(CallbackQueryHandler(viewlast_handler, pattern="^viewlast_"))
    dp.add_handler(CallbackQueryHandler(delete_confirmation_handler, pattern="^(confirm_delete_|cancel_delete)"))
    
    # View last command
    dp.add_handler(CommandHandler("viewlast", viewlast_command))
    
    # Conversation handler for /logstep
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('logstep', start_logstep)],
        states={
            DATE: [
                CallbackQueryHandler(date_handler, pattern="^today$"),
                MessageHandler(Filters.text & ~Filters.command, date_text)
            ],
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
        fallbacks=[CommandHandler('cancel', cancel)]
    )
    
    dp.add_handler(conv_handler)
    
    # Start the Bot
    logging.info("Starting Bot...")
    updater.start_polling()
    
    # Run the bot until you press Ctrl-C or the process receives SIGINT,
    # SIGTERM or SIGABRT. This should be used most of the time, since
    # start_polling() is non-blocking and will stop the bot gracefully.
    updater.idle()

if __name__ == '__main__':
    main()
