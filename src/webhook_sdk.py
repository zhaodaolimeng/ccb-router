#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Feishu Webhook Server with SDK
Uses larksuiteoapi SDK for event handling
"""

from flask import Flask, request, jsonify
import json
import os
import sys

# Import CCB bridge
from ccb_bridge_v2 import get_bridge

# Import Feishu SDK
import larksuiteoapi as lark
from larksuiteoapi import Config, DOMAIN_FEISHU
from larksuiteoapi.event import handle_event, set_event_callback
from larksuiteoapi.model import OapiHeader, OapiRequest
from larksuiteoapi.service.im.v1 import *
from larksuiteoapi.service.im.v1.event import MessageReceiveEvent


app = Flask(__name__)

# Config
CONFIG = {
    'feishu': {
        'app_id': os.environ.get('FEISHU_APP_ID', ''),
        'app_secret': os.environ.get('FEISHU_APP_SECRET', ''),
        'verification_token': os.environ.get('FEISHU_VERIFICATION_TOKEN', ''),
        'encrypt_key': os.environ.get('FEISHU_ENCRYPT_KEY', ''),
    }
}

# Load config from config.json
CONFIG_PATH = 'config.json'
if os.path.exists(CONFIG_PATH):
    try:
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            file_config = json.load(f)
            if 'feishu' in file_config:
                CONFIG['feishu'].update(file_config['feishu'])
    except Exception as e:
        print(f"Warning: Could not load config.json: {e}")


# Initialize
bridge = get_bridge()
sdk_config = None


def init_sdk():
    """Initialize SDK config"""
    global sdk_config
    app_id = CONFIG['feishu'].get('app_id', '')
    app_secret = CONFIG['feishu'].get('app_secret', '')
    encrypt_key = CONFIG['feishu'].get('encrypt_key', '')
    verification_token = CONFIG['feishu'].get('verification_token', '')

    if not app_id or app_id == 'cli_xxxxxxxxxx':
        print("[WARN] Feishu app not configured")
        return None

    try:
        # Create config with verification
        sdk_config = Config.new_internal_config(
            app_id,
            app_secret,
            DOMAIN_FEISHU,
            lark.LogLevel.INFO
        )
        sdk_config.verification_token = verification_token
        sdk_config.encrypt_key = encrypt_key

        # Set event callback
        set_event_callback(MessageReceiveEvent, on_message_receive)

        print("[OK] Feishu SDK initialized")
        return sdk_config
    except Exception as e:
        print(f"[ERROR] Failed to initialize SDK: {e}")
        return None


def send_message_with_sdk(user_id: str, text: str):
    """Send message using SDK"""
    if not sdk_config:
        print(f"\n[Simulate sending to {user_id}]:")
        print("-" * 40)
        print(text[:500] + "..." if len(text) > 500 else text)
        print("-" * 40)
        return True

    try:
        # Split long message
        max_len = 2000
        parts = []
        if len(text) <= max_len:
            parts = [text]
        else:
            remaining = text
            while remaining:
                if len(remaining) <= max_len:
                    parts.append(remaining)
                    break
                split_idx = remaining.rfind('\n', 0, max_len)
                if split_idx == -1:
                    split_idx = max_len
                parts.append(remaining[:split_idx])
                remaining = remaining[split_idx:]

        success = True
        for i, part in enumerate(parts):
            send_text = part
            if len(parts) > 1:
                send_text = f"({i+1}/{len(parts)})\n{send_text}"

            # Build request
            req = SendMessageRequest.builder() \
                .receive_id_type("open_id") \
                .request_body(SendMessageRequestBody.builder()
                    .receive_id(user_id)
                    .msg_type("text")
                    .content(json.dumps({"text": send_text}))
                    .build()) \
                .build()

            # Send request
            resp = Service(sdk_config).v1.message.send(req)

            if not resp.success():
                print(f"[ERROR] Message {i+1} send failed: {resp.code}, {resp.msg}")
                success = False
            else:
                print(f"[OK] Message {i+1} sent")

            if len(parts) > 1:
                import time
                time.sleep(0.5)

        return success

    except Exception as e:
        print(f"[ERROR] Send message exception: {e}")
        return False


def on_message_receive(ctx, event: MessageReceiveEvent):
    """Handle message receive event"""
    print(f"\n{'='*60}")
    print(f"Received message event")
    print(f"{'='*60}")

    try:
        # Get sender info
        sender = event.event.sender
        sender_id = sender.sender_id.open_id

        # Get message content
        message = event.event.message
        content = message.content

        # Parse text
        try:
            content_dict = json.loads(content)
            text = content_dict.get('text', '').strip()
        except:
            text = content.strip()

        if not text:
            print("[WARN] Empty message")
            return

        print(f"From: {sender_id}")
        print(f"Text: {text[:100]}...")

        # Process with Claude Code
        response = bridge.send_query(sender_id, text)

        # Send reply
        print(f"\nReply length: {len(response)}")
        send_message_with_sdk(sender_id, response)

    except Exception as e:
        print(f"[ERROR] Handle event exception: {e}")
        import traceback
        traceback.print_exc()


@app.route('/webhook', methods=['POST'])
def webhook():
    """Handle Feishu webhook with SDK"""
    try:
        body = request.get_data()
        data = request.get_json(silent=True)

        print(f"\n[Webhook] Received:")
        if data:
            print(json.dumps(data, indent=2, ensure_ascii=False))

        # URL verification
        if data and 'challenge' in data:
            print("[Webhook] URL verification")
            return jsonify({"challenge": data['challenge']})

        # Use SDK to handle event
        if sdk_config:
            try:
                oapi_request = OapiRequest(
                    uri=request.path,
                    body=body,
                    header=OapiHeader(request.headers)
                )
                handle_event(sdk_config, oapi_request)
                return jsonify({"status": "ok"})
            except Exception as e:
                print(f"[ERROR] SDK handle event failed: {e}")
                return jsonify({"error": str(e)}), 500

        return jsonify({"status": "ok", "note": "SDK not initialized"})

    except Exception as e:
        print(f"[Webhook] Error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route('/health', methods=['GET'])
def health():
    """Health check"""
    return jsonify({
        "status": "ok",
        "service": "feishu-claude-bridge-sdk",
        "sdk_initialized": sdk_config is not None
    })


@app.route('/test', methods=['GET'])
def test():
    """Test endpoint"""
    query = request.args.get('q', 'Hello')
    user_id = request.args.get('user', 'test_user')

    response = bridge.send_query(user_id, query)

    return jsonify({
        "query": query,
        "user_id": user_id,
        "response": response
    })


def main():
    """Main function"""
    print("="*60)
    print("Feishu <-> Claude Code Bridge - Webhook with SDK")
    print("="*60)

    host = '0.0.0.0'
    port = 8000

    # Initialize SDK
    init_sdk()

    print(f"\nServer: http://{host}:{port}")
    print(f"Webhook: http://{host}:{port}/webhook")
    print(f"Health: http://{host}:{port}/health")
    print(f"Test: http://{host}:{port}/test?q=hello")

    if sdk_config:
        print(f"\n[OK] Feishu SDK initialized")
    else:
        print(f"\n[WARN] Feishu SDK not initialized")

    print("\n" + "="*60)
    print("Starting server...")
    print("="*60)

    app.run(host=host, port=port, debug=False)


if __name__ == '__main__':
    main()
