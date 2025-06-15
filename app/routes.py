import json, requests
from flask import Blueprint, request, jsonify
from app import redis_client, valid_token, telegram_token
from datetime import datetime, timedelta
from app.telegram_utils import parse_telegram_update

API_URL = "http://localhost:8080"

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

    if 'user_id' not in req:
        return jsonify({"error": "Missing user_id"}), 400

    user_id = req['user_id']
    user_key = f"user:{user_id}"
    user_data = redis_client.get(user_key)

    if user_data:
        return jsonify({"user_id": user_id, "user_data": json.loads(user_data)})

    default_data = []
    redis_client.set(user_key, json.dumps(default_data))

    return jsonify({"user_id": user_id, "user_data": default_data})


@bp.route('/up_data', methods=['POST'])
def up_data():
    req = request.get_json()

    if not check_token(req):
        return jsonify({"error": "Invalid or missing token"}), 403

    if 'user_id' not in req or 'user_data' not in req:
        return jsonify({"error": "Missing user_id or user_data"}), 400

    user_id = req['user_id']
    user_data = req['user_data']
    user_key = f"user:{user_id}"

    redis_client.set(user_key, json.dumps(user_data))

    return jsonify({"message": "User data updated", "user_id": user_id})

@bp.route('/telegram', methods=['POST'])
def telegram_webhook():
    update = request.get_json()
    message = parse_telegram_update(update)
    time_stemp = generate_name()

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

    elif message.text and message.text=="/start":
        return jsonify({"status": "ok"}), 200
    else:
        delete_message(chat_id=message.chat_id, message_id=message.message_id)
        return jsonify({"status": "ok"}), 200


    # file logik
    # delete message
    delete_message(chat_id=message.chat_id, message_id=message.message_id)

    # get user data
    resp = requests.post(f"{API_URL}/get_data", json={
        "user_id": message.chat_id,
        "token": valid_token
    })

    data = resp.json()
    user_data = data.get("user_data", [])

    new_file = {
        "file_id": file_id,
        "file_type": file_type,
        "file_path": f"/tgDrive/{file_name}"
    }

    user_data.append(new_file)

    # update user data
    response = requests.post(f"{API_URL}/up_data", json={
        "user_id": message.chat_id,
        "token": valid_token,
        "user_data": user_data
    })

    return jsonify({"status": "ok"}), 200


@bp.route('/download', methods=['POST'])
def download():
    req = request.get_json()

    if not check_token(req):
        return jsonify({"error": "Invalid or missing token"}), 403

    user_id = req.get("user_id")
    file_id = req.get("file_id")
    file_type = req.get("file_type")

    if not user_id or not file_id or not file_type:
        return jsonify({"error": "Missing data"}), 400
    
    if file_type == "photo":
        method = "sendPhoto"

    elif file_type == "document":
        method = "sendDocument"

    elif file_type == "audio":
        method = "sendAudio"

    elif file_type == "voice":
        method = "sendVoice"

    elif file_type == "video":
        method = "sendVideo"

    elif file_type == "video_note":
        method = "sendVideoNote"


    send_url = f"https://api.telegram.org/bot{telegram_token}/{method}"
    payload = {
        "chat_id": user_id,
        file_type: file_id
    }
    tg_response = requests.post(send_url, json=payload)
    print(tg_response.text)

    return jsonify({"status": "ok"}), 200