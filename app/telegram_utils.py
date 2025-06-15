from dataclasses import dataclass, field
from typing import Optional, Any, Dict


@dataclass
class Message:
    chat_id: Optional[str] = None
    message_id: Optional[str] = None
    username: Optional[str] = None
    last_name: Optional[str] = None
    first_name: Optional[str] = None
    text: Optional[str] = None
    photo: Optional[str] = None
    voice: Optional[str] = None
    video_note: Optional[str] = None
    video: Optional[str] = None
    document: Optional[str] = None
    title_document: Optional[str] = None
    callback: Optional[str] = None
    audio: Optional[str] = None
    title_audio: Optional[str] = None


def flatten_json(json_obj: Dict[str, Any], prefix='') -> Dict[str, Any]:
    flat_json = {}
    for key, value in json_obj.items():
        new_key = f"{prefix}{key}"
        if isinstance(value, dict):
            flat_json.update(flatten_json(value, f"{new_key}."))
        else:
            flat_json[new_key] = value
    return flat_json


def parse_telegram_update(update: Dict[str, Any]) -> Message:
    r = flatten_json(update)

    def get(*keys, default=None):
        for k in keys:
            if k in r:
                return r[k]
        return default

    # Extract fields safely
    chat_id = get("message.chat.id", "callback_query.message.chat.id")
    message_id = get("message.message_id", "callback_query.message.message_id")
    username = get("message.from.username", "callback_query.message.chat.username")
    first_name = get("message.from.first_name", "callback_query.message.chat.first_name")
    last_name = get("message.from.last_name", "callback_query.message.chat.last_name")
    text = get("message.text")
    callback = get("callback_query.data")

    photo = get("message.photo", default=[])
    photo_id = photo[-1]["file_id"] if isinstance(photo, list) and photo else None

    voice = get("message.voice.file_id")
    video_note = get("message.video_note.thumbnail.file_id")
    video = get("message.video.thumbnail.file_id")
    document = get("message.document.file_id")
    title_document = get("message.document.file_name")
    audio = get("message.audio.file_id")
    title_audio = get("message.audio.file_name")

    return Message(
        chat_id=str(chat_id) if chat_id else None,
        message_id=str(message_id) if message_id else None,
        username=username,
        first_name=first_name,
        last_name=last_name,
        text=text,
        photo=photo_id,
        voice=voice,
        video_note=video_note,
        video=video,
        document=document,
        title_document=title_document,
        callback=callback,
        audio=audio,
        title_audio=title_audio
    )
