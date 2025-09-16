import json, requests, os
from flask import Blueprint, request, jsonify, render_template
from app import redis_client, telegram_token
from datetime import datetime, timedelta
from app.telegram_utils import parse_telegram_update
from app.telegram_auth import extract_user_id_from_init_data, validate_telegram_init_data
# import markdown

API_URL = "http://localhost:8080"

HELLO_MESSAGE = "👋 Привет! Добро пожаловать в tgDrive — твое личное файловое хранилище.\n\nЗагружать файлы очень просто: отправь их в этот чат, и они сразу появятся в приложении. Там ты сможешь навести порядок — разложить всё по папкам, быстро найти нужное через поиск и в любой момент скачать обратно."

bp = Blueprint('routes', __name__)

def authenticate_request(req_json):
    """
    Authenticate request using Telegram initData validation only.
    Returns (is_valid: bool, user_id: int or None, error_message: str or None)
    """
    init_data = req_json.get("initData")

    if not init_data:
        return False, None, "Missing initData - Telegram authentication required"

    try:
        validated_user_id = extract_user_id_from_init_data(init_data, telegram_token)

        # Verify the user_id in request matches the authenticated user (if provided)
        request_user_id = req_json.get("user_id")
        if request_user_id and str(request_user_id) != str(validated_user_id):
            return False, None, "User ID mismatch - potential security violation"

        return True, validated_user_id, None
    except ValueError as e:
        return False, None, f"Telegram authentication failed: {str(e)}"


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

    # Use new authentication system
    is_valid, authenticated_user_id, error_msg = authenticate_request(req)
    if not is_valid:
        return jsonify({"error": error_msg}), 403

    # Use authenticated user ID to prevent user impersonation
    user_id = authenticated_user_id
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

    # Use new authentication system
    is_valid, authenticated_user_id, error_msg = authenticate_request(req)
    if not is_valid:
        return jsonify({"error": error_msg}), 403

    # Use authenticated user ID to prevent user impersonation
    user_id = authenticated_user_id
    user_data = req.get('user_data')

    if not user_data:
        return jsonify({"error": "Missing user_data"}), 400

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

    # Get user data directly from Redis (no need for HTTP call since we're already in the backend)
    user_key = f"user:{message.chat_id}"
    try:
        user_data_raw = redis_client.get(user_key)
        if user_data_raw:
            user_data = json.loads(user_data_raw)
        else:
            # Initialize default structure if not found
            user_data = {
                "last_message_id": "none",
                "files": []
            }

        files = user_data.get("files", [])
        last_id = user_data.get("last_message_id", "none")
    except Exception as e:
        return jsonify({"error": f"Failed to retrieve user data: {str(e)}"}), 500

    # Append new file
    new_file = {
        "file_id": file_id,
        "file_type": file_type,
        "file_path": f"/{file_name}"
    }
    files.append(new_file)

    # Save updated data directly to Redis
    try:
        updated_user_data = {
            "last_message_id": last_id,
            "files": files
        }
        redis_client.set(user_key, json.dumps(updated_user_data))
    except Exception as e:
        return jsonify({"error": f"Failed to save user data: {str(e)}"}), 500

    return jsonify({"status": "ok"}), 200



@bp.route('/download', methods=['POST'])
def download():
    req = request.get_json()

    # Use new authentication system
    is_valid, authenticated_user_id, error_msg = authenticate_request(req)
    if not is_valid:
        return jsonify({"error": error_msg}), 403

    # Use authenticated user ID to prevent user impersonation
    user_id = authenticated_user_id
    file_id = req.get("file_id")
    file_type = req.get("file_type")

    # Validate required fields
    if not all([file_id, file_type]):
        return jsonify({"error": "Missing file_id or file_type"}), 400

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

    # Get current user data directly from Redis
    user_key = f"user:{user_id}"
    try:
        user_data_raw = redis_client.get(user_key)
        if user_data_raw:
            current_data = json.loads(user_data_raw)
        else:
            current_data = {
                "last_message_id": "none",
                "files": []
            }

        if not isinstance(current_data, dict):
            return jsonify({"error": "Invalid user data format"}), 500

        current_files = current_data.get("files", [])
        previous_message_id = current_data.get("last_message_id", "none")
    except Exception as e:
        return jsonify({"error": f"Failed to retrieve user data: {str(e)}"}), 500

    if previous_message_id != "none":
        try:
            delete_message(chat_id=user_id, message_id=previous_message_id)
        except Exception as e:
            print(f"Warning: Failed to delete previous message: {e}")

    # Update user data directly in Redis
    try:
        updated_data = {
            "last_message_id": new_last_message_id,
            "files": current_files
        }
        redis_client.set(user_key, json.dumps(updated_data))
    except Exception as e:
        return jsonify({"error": f"Failed to update user data: {str(e)}"}), 500
    return jsonify({"status": "ok"}), 200

