"""Quick script to get your Telegram user ID. Run this, then send any message to your bot."""

import asyncio
from telegram import Bot

BOT_TOKEN = "8561956789:AAEmfUioMauOiyWGy7ed5W44sBnpwOfz0bo"

async def main():
    bot = Bot(token=BOT_TOKEN)
    print("Send a message to your bot on Telegram, then press Enter here...")
    input()
    updates = await bot.get_updates()
    if updates:
        for update in updates:
            if update.message:
                print(f"\nYour Telegram User ID: {update.message.from_user.id}")
                print(f"Chat ID: {update.message.chat_id}")
                print(f"Username: {update.message.from_user.username}")
                return
    print("No messages found. Make sure you sent a message to the bot first.")

asyncio.run(main())
