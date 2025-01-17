import os

from dotenv import find_dotenv, load_dotenv
from telethon import TelegramClient
from telethon.tl.functions.messages import SaveDraftRequest
import settings
import agent
import time

load_dotenv(find_dotenv())

# Remember to use your own values from my.telegram.org!
api_id = os.environ["TELEGRAM_API_ID"]
api_hash = os.environ["TELEGRAM_API_HASH"]
client = TelegramClient("ambient_client", api_id, api_hash)

def format_messages_as_chat(messages):
    """
    Формирует строку в виде чата из списка сообщений.
    """
    chat_log = []
    for message in messages:
        if message.text:  # Пропускаем сообщения без текста
            # Преобразуем дату и время сообщения в строку
            timestamp = message.date.strftime("%Y-%m-%d %H:%M:%S")
            # Определяем имя отправителя (если доступно)
            sender = (
                message.sender.first_name  if message.sender and message.sender.first_name
                else "Unknown Sender"
            )
            forward_info = ""
            if message.forward:
                forward_info = " (Forwarded message) "
            content = ""
            if message.video:
                content += " <к сообщению приложено видео>"
            if message.photo:
                content = " <к сообщению приложено изображение>"
            # Формируем строку для сообщения
            chat_log.insert(0, f"[{timestamp}] {sender}: {forward_info} {message.text} {content}\n")
    return "\n".join(chat_log)

async def main():
    # Проход по всем диалогам
    async for dialog in client.iter_dialogs():
        if dialog.archived: # Skip archived dialogs
            continue
        if hasattr(dialog.entity, 'bot') and dialog.entity.bot: # Skip bots
            continue
        if dialog.is_user:
            # Проверяем количество непрочитанных сообщений
            if dialog.unread_count > 0:
                if dialog.draft.text == "":
                    messages = await client.get_messages(
                        dialog.entity, limit=dialog.unread_count + settings.history_size
                    )
                    chat_log = format_messages_as_chat(messages)

                    resp = agent.answer(chat_log) + settings.postfix
                    print(f"Saving draft for dialog: {dialog.id}")
                    await client(
                        SaveDraftRequest(
                            peer=dialog.id,
                            message=resp.strip(),
                            no_webpage=True,
                        )
                    )


while(True):
    with client:
        start_time = time.time()
        print("Scanning for new messages...")
        client.loop.run_until_complete(main())
        client.disconnect()
        end_time = time.time()
        print(f"Scan finished in {end_time - start_time:.2f} seconds")
    time.sleep(settings.scan_period)