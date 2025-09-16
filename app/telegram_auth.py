import hashlib
import hmac
import json
import time
from urllib.parse import parse_qsl, unquote


def validate_telegram_init_data(init_data: str, bot_token: str, max_age_seconds: int = 86400) -> dict:
    """
    Validate Telegram Web App initData and return parsed user data.

    Args:
        init_data: Raw initData string from Telegram Web App
        bot_token: Telegram bot token
        max_age_seconds: Maximum age of initData in seconds (default 24 hours)

    Returns:
        dict: Parsed and validated user data

    Raises:
        ValueError: If validation fails
    """
    print(f"[DEBUG] Validating initData: {init_data[:50]}..." if init_data else "[DEBUG] initData is empty")

    if not init_data:
        raise ValueError("initData is required")

    if not bot_token:
        raise ValueError("bot_token is required for validation")

    # Parse the initData
    try:
        parsed_data = dict(parse_qsl(init_data))
    except Exception:
        raise ValueError("Invalid initData format")

    # Extract and validate hash
    received_hash = parsed_data.pop('hash', None)
    if not received_hash:
        raise ValueError("Hash missing from initData")

    # Check auth_date
    auth_date = parsed_data.get('auth_date')
    if not auth_date:
        raise ValueError("auth_date missing from initData")

    try:
        auth_timestamp = int(auth_date)
        current_timestamp = int(time.time())

        if current_timestamp - auth_timestamp > max_age_seconds:
            raise ValueError("initData is too old")
    except ValueError as e:
        if "invalid literal" in str(e):
            raise ValueError("Invalid auth_date format")
        raise

    # Create data check string
    data_check_arr = []
    for key, value in sorted(parsed_data.items()):
        data_check_arr.append(f"{key}={value}")
    data_check_string = '\n'.join(data_check_arr)

    # Create secret key using HMAC-SHA256 with bot token
    secret_key = hmac.new(
        b"WebAppData",
        bot_token.encode(),
        hashlib.sha256
    ).digest()

    # Calculate expected hash
    calculated_hash = hmac.new(
        secret_key,
        data_check_string.encode(),
        hashlib.sha256
    ).hexdigest()

    # Verify hash
    if not hmac.compare_digest(calculated_hash, received_hash):
        raise ValueError("Invalid hash - authentication failed")

    # Parse user data if present
    user_data = None
    if 'user' in parsed_data:
        try:
            user_data = json.loads(unquote(parsed_data['user']))
        except (json.JSONDecodeError, ValueError):
            raise ValueError("Invalid user data format")

    return {
        'valid': True,
        'auth_date': auth_timestamp,
        'user': user_data,
        'raw_data': parsed_data
    }


def extract_user_id_from_init_data(init_data: str, bot_token: str) -> int:
    """
    Extract and validate user ID from Telegram initData.

    Args:
        init_data: Raw initData string from Telegram Web App
        bot_token: Telegram bot token

    Returns:
        int: Validated user ID

    Raises:
        ValueError: If validation fails or user ID not found
    """
    validation_result = validate_telegram_init_data(init_data, bot_token)

    user_data = validation_result.get('user')
    if not user_data or 'id' not in user_data:
        raise ValueError("User ID not found in initData")

    return user_data['id']