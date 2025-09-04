# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

### Local Development
- **Start the application**: `python run.py` (runs on `0.0.0.0:8080`)
- **Install dependencies**: `pip install -r requirements.txt`

### Docker Development
- **Build and run with Docker Compose**: `docker-compose up --build`
  - Web service runs on `localhost:9000` (mapped to container port 8080)
  - Redis runs on `localhost:9001` (mapped to container port 6379)
- **Stop services**: `docker-compose down`

## Architecture Overview

This is a Flask-based Telegram bot backend that provides cloud storage functionality through Telegram. The application consists of:

### Core Components
- **Flask Application** (`app/__init__.py`): Main app factory with CORS, Redis connection, and environment setup
- **API Routes** (`app/routes.py`): REST endpoints for data management and Telegram webhook handling
- **Telegram Utils** (`app/telegram_utils.py`): Message parsing and data classes for Telegram updates

### Key Functionality
- **File Storage**: Users can upload files via Telegram which are stored as Telegram file references in Redis
- **File Retrieval**: Files can be downloaded/sent back to users through the `/download` endpoint
- **Data Management**: User data is stored in Redis with keys in format `user:{user_id}`

### API Endpoints
- `POST /get_data`: Retrieve user data from Redis (requires token authentication)
- `POST /up_data`: Update user data in Redis (requires token authentication)  
- `POST /telegram`: Telegram webhook handler for processing file uploads
- `POST /download`: Send files back to users via Telegram API

### Data Storage
- **Redis**: Primary storage for user data and file metadata
- **User Data Structure**: 
  ```json
  {
    "last_message_id": "string",
    "files": [{"file_id": "string", "file_type": "string", "file_path": "string"}]
  }
  ```

## Environment Configuration

Required environment variables in `.env`:
- `SECRET_TOKEN`: Authentication token for API endpoints
- `REDIS_HOST`: Redis host (defaults to "redis" for Docker)
- `TELEGRAM_BOT_TOKEN`: Telegram bot token for API operations

## File Types Supported
- Documents, audio files, photos, voice messages, videos, video notes
- Automatic filename generation with UTC+3 timestamps for media without names

## Dependencies
- Flask: Web framework
- Redis: Data storage and caching
- python-dotenv: Environment variable management
- flask-cors: Cross-origin request handling
- requests: HTTP client for Telegram API calls