from flask import Flask
from flask_cors import CORS
from redis import Redis
from dotenv import load_dotenv
import os

redis_client = None
telegram_token = None

def create_app():
    global redis_client, telegram_token
    load_dotenv()

    app = Flask(__name__)
    CORS(app)

    redis_host = os.getenv("REDIS_HOST", "redis")
    telegram_token = os.getenv("TELEGRAM_BOT_TOKEN")

    # Redis connection
    redis_client = Redis(host=redis_host, port=6379, decode_responses=True)

    try:
        redis_client.ping()
        print("Connected to Redis!")
    except Exception as e:
        print("Redis connection failed:", e)
        exit(1)

    # Register routes
    from app.routes import bp
    app.register_blueprint(bp)

    return app
