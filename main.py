import os
import pickle
import time
from collections import deque
from pathlib import Path

from dotenv import find_dotenv, load_dotenv
from telethon import TelegramClient
from telethon.tl.functions.messages import SaveDraftRequest
from tenacity import retry, stop_after_attempt, wait_fixed

import agent
import settings
import storage

load_dotenv(find_dotenv())

# Remember to use your own values from my.telegram.org!
api_id = os.environ["TELEGRAM_API_ID"]
api_hash = os.environ["TELEGRAM_API_HASH"]
client = TelegramClient("ambient_client", api_id, api_hash)
processed_ids = storage.load_processed_ids()


def format_messages_as_chat(messages):
    """
    Формирует строку в виде чата из списка сообщений.
    """
    chat_log = []
    for message in messages:
        if (
            message.text or message.photo or message.video or message.sticker or message.voice or message.audio
        ):  # Пропускаем сообщения без понятного контента
            # Преобразуем дату и время сообщения в строку
            timestamp = message.date.strftime("%Y-%m-%d %H:%M:%S")
            # Определяем имя отправителя (если доступно)
            sender = (
                message.sender.first_name
                if message.sender and message.sender.first_name
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
            if message.sticker:
                content = " <к сообщению приложен стикер>"
            if message.voice or message.audio:
                content = " <к сообщению приложено аудио>"
            # Формируем строку для сообщения
            chat_log.insert(
                0, f"[{timestamp}] {sender}: {forward_info} {message.text} {content}\n"
            )
    return "\n".join(chat_log)

@retry(stop=stop_after_attempt(3))
async def scan():
    me = await client.get_me()

    # Проход по всем диалогам
    async for dialog in client.iter_dialogs():
        if dialog.archived:  # Skip archived dialogs
            continue
        if hasattr(dialog.entity, "bot") and dialog.entity.bot:  # Skip bots
            continue
        if me.id == dialog.id:  # Skip self saved messages
            continue
        if dialog.is_user:
            # Проверяем количество непрочитанных сообщений
            if dialog.unread_count > 0:
                if dialog.draft.text == "":
                    messages = await client.get_messages(
                        dialog.entity, limit=dialog.unread_count + settings.history_size
                    )

                    # Каждое сообщение обрабатываем не более одного раза
                    unique_message_id = f"{dialog.id}_{messages[0].id}"
                    if processed_ids.count(unique_message_id) > 0:
                        continue
                    processed_ids.append(unique_message_id)
                    storage.save_processed_ids(processed_ids)

                    chat_log = format_messages_as_chat(messages).strip()
                    if chat_log == "":
                        continue

                    resp = agent.answer(str(dialog.id), chat_log)
                    if resp and resp.values["need_to_send"]:
                        ans = resp.values["answer"] + settings.postfix
                        print(f"Saving draft for dialog: {dialog.id}")
                        await client(
                            SaveDraftRequest(
                                peer=dialog.id,
                                message=ans.strip(),
                                no_webpage=True,
                            )
                        )
                    else:
                        print(f"Skipping draft for dialog: {dialog.id}")


while True:
    with client:
        start_time = time.time()
        print("Scanning for new messages...")
        client.loop.run_until_complete(scan())
        client.disconnect()
        end_time = time.time()
        print(f"Scan finished in {end_time - start_time:.2f} seconds")
    time.sleep(settings.scan_period)
