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

# Load environment variables
load_dotenv()

TOKEN = os.getenv('TELEGRAM_TOKEN')
RAPIDAPI_KEY = os.getenv('RAPIDAPI_KEY')
RAPIDAPI_HOST = os.getenv('RAPIDAPI_HOST')
USER_ID = int(os.getenv('USER_ID', 0))

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Şehir & Havalimanı Veritabanı
CITIES = {
    # Türkiye Şehirleri
    'istanbul': {'code': 'IST', 'name': 'İstanbul', 'airports': ['IST (SAW)', 'SAW (Sabiha Gökçen)']},
    'ankara': {'code': 'ESB', 'name': 'Ankara', 'airports': ['ESB (Esenboğa)']},
    'izmir': {'code': 'ADB', 'name': 'İzmir', 'airports': ['ADB (Adnan Menderes)']},
    'antalya': {'code': 'GNY', 'name': 'Antalya', 'airports': ['GNY (Antalya Havalimanı)']},
    'gaziantep': {'code': 'GNY', 'name': 'Gaziantep', 'airports': ['GZT (Gaziantep)']},
    'kayseri': {'code': 'ASR', 'name': 'Kayseri', 'airports': ['ASR (Kayseri Havalimanı)']},
    'adana': {'code': 'ADA', 'name': 'Adana', 'airports': ['ADA (Şakirpaşa)']},
    'diyarbakır': {'code': 'DIY', 'name': 'Diyarbakır', 'airports': ['DIY (Diyarbakır Havalimanı)']},
    'erzurum': {'code': 'ERZ', 'name': 'Erzurum', 'airports': ['ERZ (Erzurum Havalimanı)']},
    'trabzon': {'code': 'TZX', 'name': 'Trabzon', 'airports': ['TZX (Rize-Trabzon Havalimanı)']},
    'bursa': {'code': 'YEŞ', 'name': 'Bursa', 'airports': ['YEŞ (Yenişehir Havalimanı)']},
    'eskişehir': {'code': 'ESK', 'name': 'Eskişehir', 'airports': ['ESK (Anadolu Havalimanı)']},

    # Dünya Şehirleri - Avrupa
    'londra': {'code': 'LHR', 'name': 'Londra', 'airports': ['LHR (Heathrow)', 'LGW (Gatwick)']},
    'paris': {'code': 'CDG', 'name': 'Paris', 'airports': ['CDG (Charles de Gaulle)', 'ORY (Orly)']},
    'berlin': {'code': 'BER', 'name': 'Berlin', 'airports': ['BER (Brandenburg)']},
    'roma': {'code': 'FCO', 'name': 'Roma', 'airports': ['FCO (Fiumicino)', 'CIA (Ciampino)']},
    'barselona': {'code': 'BCN', 'name': 'Barcelona', 'airports': ['BCN (El Prat)']},
    'madrid': {'code': 'MAD', 'name': 'Madrid', 'airports': ['MAD (Adolfo Suárez)']},
    'amsterdam': {'code': 'AMS', 'name': 'Amsterdam', 'airports': ['AMS (Schiphol)']},
    'viyana': {'code': 'VIE', 'name': 'Viyana', 'airports': ['VIE (Schwechat)']},
    'zürih': {'code': 'ZRH', 'name': 'Zürih', 'airports': ['ZRH (Zürich)']},
    'münih': {'code': 'MUC', 'name': 'Münih', 'airports': ['MUC (München)']},
    'lizbon': {'code': 'LIS', 'name': 'Lizbon', 'airports': ['LIS (Humberto Delgado)']},
    'prag': {'code': 'PRG', 'name': 'Prag', 'airports': ['PRG (Václav Havel)']},

    # Dünya Şehirleri - Asya
    'dubai': {'code': 'DXB', 'name': 'Dubai', 'airports': ['DXB (Dubai International)', 'DWC (Al Maktoum)']},
    'bangkok': {'code': 'BKK', 'name': 'Bangkok', 'airports': ['BKK (Suvarnabhumi)', 'DMK (Don Muang)']},
    'singapur': {'code': 'SIN', 'name': 'Singapur', 'airports': ['SIN (Changi)']},
    'hong kong': {'code': 'HKG', 'name': 'Hong Kong', 'airports': ['HKG (Hong Kong)']},
    'tokyo': {'code': 'TYO', 'name': 'Tokyo', 'airports': ['NRT (Narita)', 'HND (Haneda)']},
    'şangay': {'code': 'SHA', 'name': 'Şangay', 'airports': ['PVG (Pudong)', 'SHA (Hongqiao)']},
    'seul': {'code': 'ICN', 'name': 'Seul', 'airports': ['ICN (Incheon)', 'GMP (Gimpo)']},
    'bali': {'code': 'DPS', 'name': 'Bali', 'airports': ['DPS (Denpasar)']},
    'delhi': {'code': 'DEL', 'name': 'Delhi', 'airports': ['DEL (Indira Gandhi)']},
    'mumbai': {'code': 'BOM', 'name': 'Mumbai', 'airports': ['BOM (Bombay)']},

    # Dünya Şehirleri - Amerika
    'new york': {'code': 'NYC', 'name': 'New York', 'airports': ['JFK (Kennedy)', 'LGA (LaGuardia)', 'EWR (Newark)']},
    'los angeles': {'code': 'LAX', 'name': 'Los Angeles', 'airports': ['LAX (LAX)', 'BUR (Burbank)']},
    'miami': {'code': 'MIA', 'name': 'Miami', 'airports': ['MIA (Miami International)']},
    'chicago': {'code': 'ORD', 'name': 'Chicago', 'airports': ['ORD (O\'Hare)', 'MDW (Midway)']},
    'toronto': {'code': 'YYZ', 'name': 'Toronto', 'airports': ['YYZ (Pearson)']},
    'mexico city': {'code': 'MEX', 'name': 'Mexico City', 'airports': ['MEX (Mexico City)']},
    'buenos aires': {'code': 'EZE', 'name': 'Buenos Aires', 'airports': ['EZE (Ministro Pistarini)']},

    # Dünya Şehirleri - Afrika, Orta Doğu
    'kahire': {'code': 'CAI', 'name': 'Kahire', 'airports': ['CAI (Cairo International)']},
    'johannesburg': {'code': 'JNB', 'name': 'Johannesburg', 'airports': ['JNB (O.R. Tambo)']},
    'teheran': {'code': 'IKA', 'name': 'Tahran', 'airports': ['IKA (Imam Khomeini)', 'MHD (Mehrabad)']},
    'riyad': {'code': 'RUH', 'name': 'Riyad', 'airports': ['RUH (King Fahd)']},
    'doha': {'code': 'DOH', 'name': 'Doha', 'airports': ['DOH (Hamad International)']},
}

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
        return "❌ Bileti bulunamadı."
    
    message = "✈️ **UÇAK BİLETLERİ**\n"
    message += "═" * 40 + "\n\n"
    
    for i, flight in enumerate(flights_data['data'][:5], 1):
        price = flight.get('price', 'N/A')
        airline = flight.get('airlines', ['?'])[0]
        duration = flight.get('duration', {}).get('total', 0) // 3600
        
        message += f"**{i}. {airline}**\n"
        message += f"💰 Fiyat: ₺{price}\n"
        message += f"⏱️ Süre: {duration}s\n"
        message += "─" * 40 + "\n"
    
    return message

# Conversation states
FROM_CITY, TO_CITY, DEPARTURE_DATE = range(3)

# Command handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Botu başlat"""
    message = """
🛫 **UÇAK BİLETİ TAKIP BOTU'NA HOŞGELDINIZ** ✈️

📱 **ANA KOMUTLAR:**
/ara - Uçak bileti ara
/ekle - Bileti takibe ekle
/rotalar - Takip ettiğim rotalar
/sil - Takipten çıkar

📍 **ŞEHİRLER:**
/şehirler - Tüm şehirleri göster
/havalimanlar - Havalimanları göster

💡 **HIZLI ARAMA:**
/ara - Adım adım arama
/arayüz - Doğrudan arayüz

🌍 **DÜNYA ŞEHİRLERİ:**
New York, Londra, Paris, Tokyo, Dubai, Bangkok, 
Amsterdam, Roma, Barcelona, Madrid...

🇹🇷 **TÜRKİYE ŞEHİRLERİ:**
Istanbul, Ankara, Izmir, Antalya, Bursa...

⚡ Başlamak için /ara yazın!
"""
    await update.message.reply_text(message)

async def list_cities(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Tüm şehirleri listele"""
    message = "🌍 **TÜM ŞEHIRLER**\n"
    message += "═" * 40 + "\n\n"
    
    message += "🇹🇷 **TÜRKİYE:**\n"
    turkey_cities = [city for city in CITIES.keys() if CITIES[city]['code'] in ['IST', 'ESB', 'ADB', 'GNY', 'GZT', 'ASR', 'ADA', 'DIY', 'ERZ', 'TZX', 'YEŞ', 'ESK']]
    for city in sorted(turkey_cities):
        message += f"• {CITIES[city]['name']} ({CITIES[city]['code']})\n"
    
    message += "\n🌍 **DÜNYA:**\n"
    world_cities = [city for city in CITIES.keys() if city not in turkey_cities]
    for city in sorted(world_cities):
        message += f"• {CITIES[city]['name']} ({CITIES[city]['code']})\n"
    
    message += "\n**Kullanım:** /ara yazıp şehir adını yazınız"
    
    await update.message.reply_text(message)

async def list_airports(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Havalimanları listele"""
    message = "✈️ **HAVALIMANLAR**\n"
    message += "═" * 40 + "\n\n"
    
    for city, data in sorted(CITIES.items()):
        message += f"**{data['name']} ({data['code']}):**\n"
        for airport in data['airports']:
            message += f"  • {airport}\n"
        message += "\n"
    
    await update.message.reply_text(message)

async def search_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Uçak bileti arama başlat"""
    await update.message.reply_text(
        "📍 Lütfen kalkış şehrini yazınız.\n\n"
        "**Örnek:** Istanbul, Paris, Londra, Dubai, New York\n\n"
        "Tüm şehirler için: /şehirler"
    )
    return FROM_CITY

async def from_city(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Kalkış şehri al"""
    from_city_name = update.message.text.lower()
    
    if from_city_name not in CITIES:
        await update.message.reply_text(
            f"❌ '{from_city_name}' şehri bulunamadı.\n\n"
            "Lütfen şu şehirlerden birini yazınız:\n"
            "/şehirler komutu ile listeyi görebilirsiniz."
        )
        return FROM_CITY
    
    context.user_data['from_city'] = from_city_name
    context.user_data['from_code'] = CITIES[from_city_name]['code']
    
    await update.message.reply_text(
        f"✅ Kalkış: {CITIES[from_city_name]['name']}\n\n"
        "📍 Lütfen varış şehrini yazınız."
    )
    return TO_CITY

async def to_city(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Varış şehri al"""
    to_city_name = update.message.text.lower()
    
    if to_city_name not in CITIES:
        await update.message.reply_text(
            f"❌ '{to_city_name}' şehri bulunamadı.\n\n"
            "Lütfen başka bir şehir deneyin."
        )
        return TO_CITY
    
    context.user_data['to_city'] = to_city_name
    context.user_data['to_code'] = CITIES[to_city_name]['code']
    
    await update.message.reply_text(
        f"✅ Varış: {CITIES[to_city_name]['name']}\n\n"
        "📅 Lütfen kalkış tarihini yazınız.\n"
        "**Format:** GG.AA.YYYY\n"
        "**Örnek:** 15.04.2026"
    )
    return DEPARTURE_DATE

async def departure_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Kalkış tarihi al"""
    date_str = update.message.text
    
    try:
        date_obj = datetime.strptime(date_str, "%d.%m.%Y")
        formatted_date = date_obj.strftime("%d%m%Y")
        
        context.user_data['departure_date'] = formatted_date
        
        await update.message.reply_text("🔍 Biletler aranıyor...")
        
        flights = search_flights(
            context.user_data['from_code'],
            context.user_data['to_code'],
            formatted_date
        )
        
        message = format_flights(flights)
        await update.message.reply_text(message)
        
        await update.message.reply_text(
            "📌 Bu bileti takibe eklemek ister misiniz?\n"
            "/ekle - Evet\n"
            "/iptal - Hayır"
        )
        
    except ValueError:
        await update.message.reply_text(
            "❌ Tarih formatı yanlış!\n"
            "Lütfen GG.AA.YYYY formatında yazınız.\n"
            "**Örnek:** 15.04.2026"
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
               CITIES[context.user_data.get('from_city')]['name'],
               CITIES[context.user_data.get('to_city')]['name'],
               context.user_data.get('departure_date'),
               datetime.now()))
    conn.commit()
    conn.close()
    
    await update.message.reply_text(
        f"✅ **Takibe Eklendi!**\n\n"
        f"📍 {CITIES[context.user_data.get('from_city')]['name']} → {CITIES[context.user_data.get('to_city')]['name']}\n"
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
        message += f"**#{route_id}** {from_city} → {to_city}\n"
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
    app.add_handler(CommandHandler('şehirler', list_cities))
    app.add_handler(CommandHandler('havalimanlar', list_airports))
    app.add_handler(conv_handler)
    app.add_handler(CommandHandler('ekle', add_flight))
    app.add_handler(CommandHandler('rotalar', list_routes))
    app.add_handler(CommandHandler('sil', delete_route))
    
    logger.info("🛫 Uçak Bileti Botu başlatıldı!")
    app.run_polling()

if __name__ == '__main__':
    main()
