#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
飞书消息中转站 - Outgoing兼容版
同时支持：群机器人Outgoing + 应用事件订阅
"""

from flask import Flask, request, jsonify
from collections import deque
import json
import time
import os
import hmac
import hashlib

app = Flask(__name__)

message_queue = deque(maxlen=50)

# 飞书Outgoing配置的Token（用于验证，可选）
OUTGOING_TOKEN = os.environ.get('OUTGOING_TOKEN', '')

def verify_outgoing_token(data, signature):
    """验证Outgoing请求（可选安全验证）"""
    if not OUTGOING_TOKEN:
        return True
    timestamp = data.get('timestamp', '')
    expected = hmac.new(OUTGOING_TOKEN.encode(), f"{timestamp}{json.dumps(data)}".encode(), hashlib.sha256).hexdigest()
    return expected == signature

@app.route('/', methods=['GET', 'POST'])
def handler():
    if request.method == 'POST':
        try:
            data = request.get_json() or {}
            print(f"[收到请求] {json.dumps(data, ensure_ascii=False)[:300]}...")
            
            # ========== 1. Challenge 验证（两种模式都需要） ==========
            if data.get('type') == 'url_verification':
                return jsonify({'challenge': data.get('challenge')})
            
            # ========== 2. Outgoing Webhook 格式 ==========
            # 特征：有uuid字段，数据格式扁平
            if data.get('uuid') and data.get('event'):
                event = data.get('event', {})
                
                # Outgoing直接给出text内容，不需要解析JSON
                msg_info = {
                    'id': event.get('message_id'),
                    'text': event.get('text', event.get('content', '')),  # 兼容不同版本
                    'sender': event.get('open_id', 'unknown')[-6:],
                    'chat': event.get('open_chat_id', 'unknown')[-6:],
                    'time': int(time.time())
                }
                
                if msg_info['id']:
                    message_queue.append(msg_info)
                    print(f"[Outgoing存储] {msg_info['text'][:30]}... (队列: {len(message_queue)})")
                
                # Outgoing要求返回特定格式
                return jsonify({'code': 0})
            
            # ========== 3. 应用事件订阅格式（原有逻辑） ==========
            if data.get('header', {}).get('event_type') == 'im.message.receive_v1':
                event_data = data.get('event', {})
                message = event_data.get('message', {})
                
                # 原有提取逻辑
                content = message.get('content', '{}')
                try:
                    if isinstance(content, str):
                        content = json.loads(content)
                except:
                    pass
                
                text = ''
                msg_type = message.get('message_type', '')
                if msg_type == 'text':
                    text = content.get('text', '')
                
                msg_info = {
                    'id': message.get('message_id'),
                    'text': text,
                    'sender': event_data.get('sender', {}).get('sender_id', {}).get('open_id', 'unknown')[-6:],
                    'chat': message.get('chat_id', 'unknown')[-6:],
                    'time': int(time.time())
                }
                
                if msg_info['id']:
                    message_queue.append(msg_info)
                    print(f"[Event存储] {msg_info['text'][:30]}... (队列: {len(message_queue)})")
            
            return jsonify({'code': 0})
            
        except Exception as e:
            print(f"处理错误: {e}")
            import traceback
            print(traceback.format_exc())
            return jsonify({'code': -1, 'msg': str(e)}), 500
    
    # GET请求：本地客户端拉取（保持原有格式不变）
    return jsonify({
        'messages': list(message_queue),
        'count': len(message_queue)
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
