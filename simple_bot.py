import os
import asyncio
import aiohttp
from datetime import datetime
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

TOKEN = "8432859889:AAFt-Dia4jO8AFfH6xcvCJKoLxtGEyNDc6E"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🤖 Бот запущен!")

async def check_cookie(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📝 Отправьте куку для проверки")

def main():
    app = Application.builder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("check", check_cookie))
    
    print("✅ Бот запускается...")
    app.run_polling()

if __name__ == "__main__":

    main()
