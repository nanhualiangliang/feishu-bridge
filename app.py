#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
飞书消息中转站 - 极简版
只接收和存储消息，不处理发送（发送由本地通过 Webhook 处理）
"""

from flask import Flask, request, jsonify
from collections import deque
import json
import time
import os

app = Flask(__name__)

# 内存队列（保存最近 50 条消息）
message_queue = deque(maxlen=50)

def extract_text(message):
    """提取消息文本"""
    content = message.get('content', '{}')
    msg_type = message.get('message_type', '')
    
    try:
        if isinstance(content, str):
            content = json.loads(content)
    except:
        pass
    
    if msg_type == 'text':
        return content.get('text', '')
    elif msg_type == 'post':
        texts = []
        for block in content.get('content', []):
            for elem in block:
                if elem.get('tag') == 'text':
                    texts.append(elem.get('text', ''))
        return ' '.join(texts)
    return str(content)

@app.route('/', methods=['GET', 'POST'])
def handler():
    if request.method == 'POST':
        try:
            data = request.get_json() or {}
            
            # Challenge 验证
            if data.get('type') == 'url_verification':
                return jsonify({'challenge': data.get('challenge')})
            
            # 检查是否是自定义消息（来自发送端）
            if 'id' in data and 'text' in data:
                msg_info = {
                    'id': data['id'],
                    'text': data['text'],
                    'sender': data.get('sender', 'system'),
                    'chat': data.get('chat', 'auto'),
                    'time': data.get('time', int(time.time()))
                }
                message_queue.append(msg_info)
                print(f"[存储自定义消息] {msg_info['text'][:30]}... (队列: {len(message_queue)})")
                return jsonify({'code': 0})
            
            # 处理飞书消息事件
            if data.get('header', {}).get('event_type') == 'im.message.receive_v1':
                event_data = data.get('event', {})
                message = event_data.get('message', {})
                
                msg_info = {
                    'id': message.get('message_id'),
                    'text': extract_text(message),
                    'sender': event_data.get('sender', {}).get('sender_id', {}).get('open_id', 'unknown')[-6:],
                    'chat': message.get('chat_id', 'unknown')[-6:],
                    'time': int(time.time())
                }
                
                if msg_info['id']:
                    message_queue.append(msg_info)
                    print(f"[存储飞书消息] {msg_info['text'][:30]}... (队列: {len(message_queue)})")
            
            return jsonify({'code': 0})
            
        except Exception as e:
            print(f"处理错误: {e}")
            return jsonify({'code': -1, 'msg': str(e)}), 500
    
    # GET 请求：本地客户端拉取消息
    return jsonify({
        'messages': list(message_queue),
        'count': len(message_queue)
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
