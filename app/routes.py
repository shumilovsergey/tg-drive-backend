import json, requests, os
from flask import Blueprint, request, jsonify, render_template
from app import redis_client, valid_token, telegram_token
from datetime import datetime, timedelta
from app.telegram_utils import parse_telegram_update
# import markdown

API_URL = "http://localhost:8080"

HELLO_MESSAGE = "👋 Привет! Добро пожаловать в tgDrive — твое личное файловое хранилище.\n\nЗагружать файлы очень просто: отправь их в этот чат, и они сразу появятся в приложении. Там ты сможешь навести порядок — разложить всё по папкам, быстро найти нужное через поиск и в любой момент скачать обратно."

bp = Blueprint('routes', __name__)

def check_token(req_json):
    token = req_json.get("token")
    return token == valid_token

def generate_name():
    now = datetime.utcnow() + timedelta(hours=3)  # UTC+3
    timestamp = now.strftime("%H:%M-%d.%m.%y")
    return timestamp

def delete_message(chat_id, message_id):
    url = f"https://api.telegram.org/bot{telegram_token}/deleteMessage"
    requests.post(url, json={"chat_id": chat_id, "message_id": message_id})

@bp.route('/get_data', methods=['POST'])
def get_data():
    req = request.get_json()

    if not check_token(req):
        return jsonify({"error": "Invalid or missing token"}), 403

    user_id = req.get('user_id')
    if not user_id:
        return jsonify({"error": "Missing user_id"}), 400

    user_key = f"user:{user_id}"

    try:
        user_data_raw = redis_client.get(user_key)
        if user_data_raw:
            user_data = json.loads(user_data_raw)
            return jsonify({"user_id": user_id, "user_data": user_data}), 200
    except Exception as e:
        return jsonify({"error": f"Failed to retrieve data: {str(e)}"}), 500

    # Initialize default structure if not found
    default_data = {
        "last_message_id": "none",
        "files": []
    }

    try:
        redis_client.set(user_key, json.dumps(default_data))
    except Exception as e:
        return jsonify({"error": f"Failed to initialize user data: {str(e)}"}), 500

    return jsonify({"user_id": user_id, "user_data": default_data}), 200


@bp.route('/up_data', methods=['POST'])
def up_data():
    req = request.get_json()

    if not check_token(req):
        return jsonify({"error": "Invalid or missing token"}), 403

    user_id = req.get('user_id')
    user_data = req.get('user_data')

    if not user_id or not user_data:
        return jsonify({"error": "Missing user_id or user_data"}), 400

    if not isinstance(user_data, dict):
        return jsonify({"error": "user_data must be a dictionary"}), 400

    try:
        user_key = f"user:{user_id}"
        redis_client.set(user_key, json.dumps(user_data))
    except Exception as e:
        return jsonify({"error": f"Failed to update Redis: {str(e)}"}), 500

    return jsonify({"message": "User data updated", "user_id": user_id}), 200


@bp.route('/telegram', methods=['POST'])
def telegram_webhook():
    update = request.get_json()
    message = parse_telegram_update(update)
    time_stemp = generate_name()

    file_name = None
    file_id = None
    file_type = None

    # Determine file type and name
    if message.document:
        file_name = message.title_document
        file_id = message.document
        file_type = "document"
    elif message.audio:
        file_name = message.title_audio
        file_id = message.audio
        file_type = "audio"
    elif message.photo:
        file_name = f"{time_stemp}.png"
        file_id = message.photo
        file_type = "photo"
    elif message.voice:
        file_name = f"голос_{time_stemp}.mp3"
        file_id = message.voice
        file_type = "voice"
    elif message.video:
        file_name = f"видео_{time_stemp}.mp4"
        file_id = message.video
        file_type = "video"
    elif message.video_note:
        file_name = f"кружок_{time_stemp}.mp4"
        file_id = message.video_note
        file_type = "video_note"
    elif message.text and message.text == "/start":
        # Send hello message
        # send_url = f"https://api.telegram.org/bot{telegram_token}/sendMessage"
        # payload = {
        #     "chat_id": message.chat_id,
        #     "text": HELLO_MESSAGE
        # }

        send_url = f"https://api.telegram.org/bot{telegram_token}/sendMessage"
        payload = {
            "chat_id": message.chat_id,
            "text": HELLO_MESSAGE,
            "reply_markup": json.dumps({
                "inline_keyboard": [
                    [
                        {
                            "text": "tgDrive",
                            "web_app": {"url": "https://shumilovsergey.github.io/telegram-drive-frontend/"}
                        },
                        {
                            "text": "Обо мне",
                            "url": "https://sh-development.ru"
                        }
                    ]
                ]
            })
        }


        requests.post(send_url, json=payload)
        return jsonify({"status": "ok"}), 200
    else:
        delete_message(chat_id=message.chat_id, message_id=message.message_id)
        return jsonify({"status": "ok"}), 200

    # If we got here, we received a valid file
    delete_message(chat_id=message.chat_id, message_id=message.message_id)

    # Get user data from Redis
    resp = requests.post(f"{API_URL}/get_data", json={
        "user_id": message.chat_id,
        "token": valid_token
    })

    if not resp.ok:
        return jsonify({"error": "Failed to fetch user data"}), 500

    data = resp.json()
    user_data = data.get("user_data", {})
    files = user_data.get("files", [])
    last_id = user_data.get("last_message_id", "none")

    # Append new file
    new_file = {
        "file_id": file_id,
        "file_type": file_type,
        "file_path": f"/{file_name}"
    }
    files.append(new_file)

    # Save updated data
    requests.post(f"{API_URL}/up_data", json={
        "user_id": message.chat_id,
        "token": valid_token,
        "user_data": {
            "last_message_id": last_id,
            "files": files
        }
    })

    return jsonify({"status": "ok"}), 200



@bp.route('/download', methods=['POST'])
def download():
    req = request.get_json()

    # Validate token
    if not check_token(req):
        return jsonify({"error": "Invalid or missing token"}), 403

    user_id = req.get("user_id")
    file_id = req.get("file_id")
    file_type = req.get("file_type")

    # Validate required fields
    if not all([user_id, file_id, file_type]):
        return jsonify({"error": "Missing user_id, file_id, or file_type"}), 400

    # Map file_type to Telegram send method
    method_map = {
        "photo": "sendPhoto",
        "document": "sendDocument",
        "audio": "sendAudio",
        "voice": "sendVoice",
        "video": "sendVideo",
        "video_note": "sendVideoNote"
    }
    method = method_map.get(file_type)
    if not method:
        return jsonify({"error": "Unsupported file_type"}), 400

    # Send file
    send_url = f"https://api.telegram.org/bot{telegram_token}/{method}"
    payload = {
        "chat_id": user_id,
        file_type: file_id
    }
    tg_response = requests.post(send_url, json=payload)

    if not tg_response.ok:
        return jsonify({"error": "Telegram API failed", "details": tg_response.text}), 500

    # Get message ID of sent file
    new_last_message_id = tg_response.json().get("result", {}).get("message_id", "none")

    # Get current user data
    get_resp = requests.post(f"{API_URL}/get_data", json={
        "user_id": user_id,
        "token": valid_token
    })
    if not get_resp.ok:
        return jsonify({"error": "Failed to fetch user data"}), 500
    
    user_data_resp = get_resp.json()
    current_data = user_data_resp.get("user_data", {})

    if not isinstance(current_data, dict):
        return jsonify({"error": "Invalid user data format"}), 500
    
    current_files = current_data.get("files", [])
    previous_message_id = current_data.get("last_message_id", "none")

    if previous_message_id != "none":
        try:
            delete_message(chat_id=user_id, message_id=previous_message_id)
        except Exception as e:
            print(f"Warning: Failed to delete previous message: {e}")

    update_payload = {
        "user_id": user_id,
        "token": valid_token,
        "user_data": {
            "last_message_id": new_last_message_id,
            "files": current_files
        }
    }  

    update_resp = requests.post(f"{API_URL}/up_data", json=update_payload)

    if not update_resp.ok:
        return jsonify({"error": "Failed to update user data"}), 500
    return jsonify({"status": "ok"}), 200

