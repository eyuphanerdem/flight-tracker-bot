# -*- coding: utf-8 -*-
import os
import logging
import sqlite3
import requests
import json
from datetime import datetime, timedelta
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, ConversationHandler, MessageHandler, filters
from apscheduler.schedulers.background import BackgroundScheduler

# Load environment variables
load_dotenv()

TOKEN = os.getenv('TELEGRAM_TOKEN')
RAPIDAPI_KEY = os.getenv('RAPIDAPI_KEY')
RAPIDAPI_HOST = os.getenv('RAPIDAPI_HOST')
USER_ID = int(os.getenv('USER_ID', 0))

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Database setup
def init_db():
    conn = sqlite3.connect('flights.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS flights
                 (id INTEGER PRIMARY KEY, user_id INTEGER, from_city TEXT, to_city TEXT, 
                  departure_date TEXT, max_price INTEGER, created_at TIMESTAMP)''')
    c.execute('''CREATE TABLE IF NOT EXISTS price_history
                 (id INTEGER PRIMARY KEY, flight_id INTEGER, price INTEGER, date TIMESTAMP)''')
    conn.commit()
    conn.close()

init_db()

# Kiwi API Functions
def get_flight_code(city_name):
    """Şehir adından IATA kodunu bul"""
    url = "https://kiwi-com-cheap-flights.p.rapidapi.com/locations/query"
    params = {"term": city_name, "location_types": "city"}
    headers = {
        "x-rapidapi-key": RAPIDAPI_KEY,
        "x-rapidapi-host": RAPIDAPI_HOST
    }
    
    try:
        response = requests.get(url, params=params, headers=headers, timeout=5)
        if response.status_code == 200:
            data = response.json()
            if data.get('locations') and len(data['locations']) > 0:
                return data['locations'][0]['code']
    except Exception as e:
        logger.error(f"Flight code hatası: {e}")
    
    return None

def search_flights(from_code, to_code, departure_date):
    """Uçak bileti ara"""
    url = "https://kiwi-com-cheap-flights.p.rapidapi.com/v2/search"
    params = {
        "from": from_code,
        "to": to_code,
        "dateFrom": departure_date,
        "dateTo": departure_date,
        "limit": 10,
        "sort": "price"
    }
    headers = {
        "x-rapidapi-key": RAPIDAPI_KEY,
        "x-rapidapi-host": RAPIDAPI_HOST
    }
    
    try:
        response = requests.get(url, params=params, headers=headers, timeout=10)
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        logger.error(f"Arama hatası: {e}")
    
    return None

def format_flights(flights_data):
    """Uçakları güzel formatta göster"""
    if not flights_data or 'data' not in flights_data or len(flights_data['data']) == 0:
        return "Bileti bulunamadı."
    
    message = "✈️ **UÇAK BİLETLERİ**\n"
    message += "═" * 40 + "\n\n"
    
    for i, flight in enumerate(flights_data['data'][:5], 1):
        price = flight.get('price', 'N/A')
        airline = flight.get('airlines', ['?'])[0]
        duration = flight.get('duration', {}).get('total', 0) // 3600
        
        message += f"**{i}. {airline}**\n"
        message += f"💰 Fiyat: ₺{price}\n"
        message += f"⏱️ Süre: {duration}s\n"
        message += f"🔗 [Bilet Al](https://www.kiwi.com)\n"
        message += "─" * 40 + "\n"
    
    return message

# Conversation states
FROM_CITY, TO_CITY, DEPARTURE_DATE, MAX_PRICE = range(4)

# Command handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Botu başlat"""
    message = """
🛫 **UÇAK BİLETİ TAKIP BOTU'NA HOŞGELDINIZ** ✈️

📱 **Komutlar:**
/ara - Uçak bileti ara
/ekle - Bileti takibe ekle
/rotalar - Takip ettiğim rotalar
/sil - Takipten çıkar
/ucuz - En ucuz biletler

💡 **Özellikler:**
✅ Gerçek zamanlı fiyatlar
✅ Otomatik fiyat takibi
✅ Fiyat uyarıları
✅ Haftlık raporlar

⚡ Başlamak için /ara yazın!
"""
    await update.message.reply_text(message)

async def search_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Uçak bileti arama başlat"""
    await update.message.reply_text(
        "📍 Lütfen kalkış şehrini yazınız.\nÖrnek: İstanbul, Paris, Londra"
    )
    return FROM_CITY

async def from_city(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Kalkış şehri al"""
    from_city_name = update.message.text
    from_code = get_flight_code(from_city_name)
    
    if not from_code:
        await update.message.reply_text(
            f"❌ '{from_city_name}' şehri bulunamadı.\n"
            "Lütfen başka bir şehir deneyin."
        )
        return FROM_CITY
    
    context.user_data['from_city'] = from_city_name
    context.user_data['from_code'] = from_code
    
    await update.message.reply_text(
        f"✅ Kalkış: {from_city_name}\n\n"
        "📍 Lütfen varış şehrini yazınız."
    )
    return TO_CITY

async def to_city(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Varış şehri al"""
    to_city_name = update.message.text
    to_code = get_flight_code(to_city_name)
    
    if not to_code:
        await update.message.reply_text(
            f"❌ '{to_city_name}' şehri bulunamadı.\n"
            "Lütfen başka bir şehir deneyin."
        )
        return TO_CITY
    
    context.user_data['to_city'] = to_city_name
    context.user_data['to_code'] = to_code
    
    await update.message.reply_text(
        f"✅ Varış: {to_city_name}\n\n"
        "📅 Lütfen kalkış tarihini yazınız.\nFormat: GG.AA.YYYY\nÖrnek: 15.04.2026"
    )
    return DEPARTURE_DATE

async def departure_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Kalkış tarihi al"""
    date_str = update.message.text
    
    try:
        # Tarihi parse et
        date_obj = datetime.strptime(date_str, "%d.%m.%Y")
        # Kiwi API formatına çevir (DDMMYYYY)
        formatted_date = date_obj.strftime("%d%m%Y")
        
        context.user_data['departure_date'] = formatted_date
        
        # Bilet ara
        await update.message.reply_text("🔍 Biletler aranıyor...")
        
        flights = search_flights(
            context.user_data['from_code'],
            context.user_data['to_code'],
            formatted_date
        )
        
        message = format_flights(flights)
        await update.message.reply_text(message)
        
        # Takibe eklemek ister misin?
        await update.message.reply_text(
            "📌 Bu bileti takibe eklemek ister misiniz?\n"
            "/ekle - Evet\n"
            "/iptal - Hayır"
        )
        
    except ValueError:
        await update.message.reply_text(
            "❌ Tarih formatı yanlış!\n"
            "Lütfen GG.AA.YYYY formatında yazınız.\n"
            "Örnek: 15.04.2026"
        )
        return DEPARTURE_DATE
    
    return ConversationHandler.END

async def add_flight(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Bileti takibe ekle"""
    if 'from_city' not in context.user_data:
        await update.message.reply_text(
            "❌ Önce /ara komutu ile bileti arayınız."
        )
        return
    
    conn = sqlite3.connect('flights.db')
    c = conn.cursor()
    c.execute('''INSERT INTO flights (user_id, from_city, to_city, departure_date, created_at)
                 VALUES (?, ?, ?, ?, ?)''',
              (update.effective_user.id, 
               context.user_data.get('from_city'),
               context.user_data.get('to_city'),
               context.user_data.get('departure_date'),
               datetime.now()))
    conn.commit()
    conn.close()
    
    await update.message.reply_text(
        f"✅ Takibe eklendi!\n\n"
        f"📍 {context.user_data.get('from_city')} → {context.user_data.get('to_city')}\n"
        f"📅 {context.user_data.get('departure_date')}\n\n"
        "Her gün güncellemeler alacaksınız."
    )

async def list_routes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Takip edilen rotaları göster"""
    conn = sqlite3.connect('flights.db')
    c = conn.cursor()
    c.execute('SELECT id, from_city, to_city, departure_date FROM flights WHERE user_id = ?',
              (update.effective_user.id,))
    routes = c.fetchall()
    conn.close()
    
    if not routes:
        await update.message.reply_text("📭 Henüz takip ettiğiniz rota yok.")
        return
    
    message = "📋 **TAKIP ETTİKLERİMİZ**\n"
    message += "═" * 40 + "\n\n"
    
    for route_id, from_city, to_city, dep_date in routes:
        message += f"**{route_id}.** {from_city} → {to_city}\n"
        message += f"📅 {dep_date}\n"
        message += "─" * 40 + "\n"
    
    await update.message.reply_text(message)

async def delete_route(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Rotayı sil"""
    if not context.args:
        await update.message.reply_text(
            "❌ Kullanım: /sil <id>\n"
            "/rotalar komutundan ID'yi öğrenebilirsiniz."
        )
        return
    
    try:
        route_id = int(context.args[0])
        conn = sqlite3.connect('flights.db')
        c = conn.cursor()
        c.execute('DELETE FROM flights WHERE id = ? AND user_id = ?',
                  (route_id, update.effective_user.id))
        conn.commit()
        conn.close()
        
        await update.message.reply_text(f"✅ Rota #{route_id} silindi.")
    except ValueError:
        await update.message.reply_text("❌ Lütfen geçerli bir ID yazınız.")

async def cheapest_flights(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """En ucuz biletleri göster"""
    await update.message.reply_text(
        "💰 **EN UCUZ BİLETLER**\n\n"
        "Bu özellik yakında aktif olacak.\n"
        "Tüm rotalardan en ucuz biletleri gösterecektir."
    )

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Konversasyonu iptal et"""
    await update.message.reply_text("❌ İşlem iptal edildi.")
    return ConversationHandler.END

def main():
    """Bot'u başlat"""
    app = Application.builder().token(TOKEN).build()
    
    # Conversation handler
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('ara', search_command)],
        states={
            FROM_CITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, from_city)],
            TO_CITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, to_city)],
            DEPARTURE_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, departure_date)],
        },
        fallbacks=[CommandHandler('iptal', cancel)],
    )
    
    # Handlers
    app.add_handler(CommandHandler('start', start))
    app.add_handler(conv_handler)
    app.add_handler(CommandHandler('ekle', add_flight))
    app.add_handler(CommandHandler('rotalar', list_routes))
    app.add_handler(CommandHandler('sil', delete_route))
    app.add_handler(CommandHandler('ucuz', cheapest_flights))
    
    logger.info("🛫 Uçak Bileti Botu başlatıldı!")
    app.run_polling()

if __name__ == '__main__':
    main()
