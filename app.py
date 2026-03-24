from flask import Flask, request, jsonify
from collections import deque
import json
import time
import os

app = Flask(__name__)
message_queue = deque(maxlen=100)

@app.route('/', methods=['GET', 'POST'])
def webhook():
    if request.method == 'POST':
        try:
            data = request.get_json() or {}
            
            if data.get('type') == 'url_verification':
                return jsonify({'challenge': data.get('challenge')})
            
            if data.get('header', {}).get('event_type') == 'im.message.receive_v1':
                event_data = data.get('event', {})
                message = event_data.get('message', {})
                
                content = message.get('content', '{}')
                try:
                    content = json.loads(content) if isinstance(content, str) else content
                except:
                    pass
                
                msg_type = message.get('message_type', '')
                if msg_type == 'text':
                    text = content.get('text', '')
                elif msg_type == 'post':
                    texts = []
                    for block in content.get('content', []):
                        for elem in block:
                            if elem.get('tag') == 'text':
                                texts.append(elem.get('text', ''))
                    text = ' '.join(texts)
                else:
                    text = str(content)
                
                message_queue.append({
                    'id': message.get('message_id'),
                    'text': text,
                    'sender': event_data.get('sender', {}).get('sender_id', {}).get('open_id', 'unknown')[-6:],
                    'chat': message.get('chat_id', 'unknown')[-6:],
                    'time': int(time.time())
                })
            
            return jsonify({'code': 0})
        except Exception as e:
            return jsonify({'code': -1, 'msg': str(e)}), 500
    
    return jsonify({'messages': list(message_queue)})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
