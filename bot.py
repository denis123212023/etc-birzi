import os
import asyncio
import logging
from typing import List

from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from web3 import Web3
from dotenv import load_dotenv

# Load settings from .env file
load_dotenv()

# Configuration
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID", "")
MONITORED_ADDRESSES_RAW = os.getenv(
    "MONITORED_ADDRESSES",
    "0x216D44960291E4129435c719217a7ECAe8c29927,"
    "0x0D0707963952f2fBA59dD06f2b425ace40b492Fe,"
    "0x5a52E96BAcdaBb82fd05763E25335261B270Efcb,"
    "0x8793291670607dDF746A49B6B3faf6627A5E494f,"
    "0xa12105Efa0663147bddee178f6a741ac15676b79"
)

MONITORED_ADDRESSES = {
    addr.strip().lower()
    for addr in MONITORED_ADDRESSES_RAW.split(",")
    if addr.strip()
}

ETC_RPC_URL = os.getenv("ETC_RPC_URL", "https://etc.rivet.link")
THRESHOLD_ETC = float(os.getenv("THRESHOLD_ETC", 5000.0))

# Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Initialize Web3
w3 = Web3(Web3.HTTPProvider(ETC_RPC_URL))

# Initialize Bot and Dispatcher
bot = Bot(token=TELEGRAM_BOT_TOKEN)
dp = Dispatcher()


async def send_notification(tx_hash, from_addr, to_addr, value):
    """Sends a Telegram notification to the admin chat ID."""
    blockscout_url = f"https://blockscout.com/etc/mainnet/tx/{tx_hash}"

    message = (
        f"🚨 **Крупная транзакция в ETC!** 🚨\n\n"
        f"💳 **От:** `{from_addr}`\n"
        f"📥 **Кому:** `{to_addr}`\n"
        f"💰 **Сумма:** {value:.2f} ETC\n"
        f"🔗 <a href=\"{blockscout_url}\">Посмотреть в Blockscout</a>"
    )

    try:
        if ADMIN_CHAT_ID:
            await bot.send_message(ADMIN_CHAT_ID, message, parse_mode="Markdown")
        else:
            logger.warning("ADMIN_CHAT_ID not set, skipping notification.")
    except Exception as e:
        logger.error(f"Error sending Telegram message: {e}")


async def monitor_blocks():
    """Background task to poll for new blocks and check transactions."""
    if not w3.is_connected():
        logger.error("Failed to connect to ETC RPC.")
        return

    logger.info("Starting ETC block monitor...")
    last_block = w3.eth.block_number

    while True:
        try:
            current_block = w3.eth.block_number

            if current_block > last_block:
                for block_num in range(last_block + 1, current_block + 1):
                    logger.info(f"Processing block: {block_num}")
                    block = w3.eth.get_block(block_num, full_transactions=True)

                    for tx in block.transactions:
                        from_addr = tx["from"].lower()
                        to_addr = tx["to"].lower() if tx["to"] else ""
                        value_etc = w3.from_wei(tx["value"], "ether")

                        is_target = (
                            from_addr in MONITORED_ADDRESSES
                            or to_addr in MONITORED_ADDRESSES
                        )

                        if is_target and value_etc >= THRESHOLD_ETC:
                            logger.info(
                                f"🔔 Транзакция по кошельку: {tx['hash'].hex()} | {value_etc} ETC."
                            )
                            await send_notification(
                                tx["hash"].hex(), from_addr, to_addr, value_etc
                            )

                last_block = current_block

            await asyncio.sleep(10)

        except Exception as e:
            logger.error(f"An error occurred in the monitor loop: {e}")
            await asyncio.sleep(5)


@dp.message(Command("start"))
async def start_cmd(message: types.Message):
    await message.answer("Бот работает и мониторит крупные транзакции ETC.")


async def main():
    # Start block monitor in background
    asyncio.create_task(monitor_blocks())

    # Start Telegram bot
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
