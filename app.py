from flask import Flask, request, jsonify
from collections import deque
import json
import time
import os
import requests

app = Flask(__name__)
message_queue = deque(maxlen=100)

# 从环境变量读取飞书凭证
FEISHU_APP_ID = os.environ.get('FEISHU_APP_ID', '')
FEISHU_APP_SECRET = os.environ.get('FEISHU_APP_SECRET', '')

def get_feishu_token():
    """获取飞书 access_token"""
    if not FEISHU_APP_ID or not FEISHU_APP_SECRET:
        print("[警告] 未配置飞书凭证")
        return None
    try:
        url = "https://open.feishu.cn/open-apis/auth/v3/app_access_token/internal"
        resp = requests.post(url, json={
            "app_id": FEISHU_APP_ID,
            "app_secret": FEISHU_APP_SECRET
        }, timeout=10)
        data = resp.json()
        if data.get("code") == 0:
            return data.get("app_access_token")
        else:
            print(f"[获取Token失败] {data}")
    except Exception as e:
        print(f"获取token异常: {e}")
    return None

def send_feishu_message(chat_id, text):
    """发送消息到飞书群"""
    token = get_feishu_token()
    if not token:
        print("[发送失败] 无有效token")
        return False
    
    try:
        url = "https://open.feishu.cn/open-apis/im/v1/messages"
        headers = {"Authorization": f"Bearer {token}"}
        params = {"receive_id_type": "chat_id"}
        
        content = json.dumps({"text": text})
        data = {
            "receive_id": chat_id,  # 使用完整的chat_id
            "msg_type": "text",
            "content": content
        }
        
        print(f"[发送消息] chat_id: {chat_id[:15]}... 内容: {text[:20]}...")
        resp = requests.post(url, headers=headers, params=params, json=data, timeout=10)
        result = resp.json()
        print(f"[飞书响应] {result}")
        
        if result.get("code") == 0:
            return True
        else:
            print(f"[发送失败] 错误码: {result.get('code')}, 错误信息: {result.get('msg')}")
            return False
    except Exception as e:
        print(f"发送消息异常: {e}")
        return False

@app.route('/', methods=['GET', 'POST'])
def webhook():
    if request.method == 'POST':
        try:
            data = request.get_json() or {}
            
            # 飞书Challenge验证
            if data.get('type') == 'url_verification':
                print(f"[Challenge验证] {data.get('challenge')}")
                return jsonify({'challenge': data.get('challenge')})
            
            # 处理消息
            if data.get('header', {}).get('event_type') == 'im.message.receive_v1':
                event_data = data.get('event', {})
                message = event_data.get('message', {})
                
                # 提取消息内容
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
                
                # 修复：保存完整的chat_id和sender_id，不要截断！
                msg_info = {
                    'id': message.get('message_id'),
                    'text': text,
                    'sender': event_data.get('sender', {}).get('sender_id', {}).get('open_id', 'unknown'),  # 完整ID
                    'chat': message.get('chat_id', 'unknown'),  # 完整ID，不截断！
                    'chat_type': message.get('chat_type', ''),
                    'time': int(time.time())
                }
                
                message_queue.append(msg_info)
                print(f"[收到消息] 群:{msg_info['chat'][:15]}... 发送者:{msg_info['sender'][:10]}... 内容:{text[:30]}...")
            
            return jsonify({'code': 0})
        except Exception as e:
            print(f"处理错误: {e}")
            import traceback
            traceback.print_exc()
            return jsonify({'code': -1, 'msg': str(e)}), 500
    
    # GET请求返回队列
    return jsonify({'messages': list(message_queue)})

@app.route('/send', methods=['POST'])
def send_message():
    """接收本地程序请求，发送消息到飞书"""
    try:
        data = request.get_json() or {}
        chat_id = data.get('chat_id')
        text = data.get('text')
        
        print(f"[发送接口] 收到请求 chat_id:{chat_id[:20] if chat_id else 'None'}... text:{text[:20] if text else 'None'}...")
        
        if not chat_id or not text:
            return jsonify({'code': -1, 'msg': '缺少chat_id或text'}), 400
        
        if not FEISHU_APP_ID or not FEISHU_APP_SECRET:
            return jsonify({'code': -1, 'msg': '服务端未配置飞书凭证'}), 500
        
        success = send_feishu_message(chat_id, text)
        
        if success:
            return jsonify({'code': 0, 'msg': '发送成功'})
        else:
            return jsonify({'code': -1, 'msg': '发送失败，检查日志'}), 500
    except Exception as e:
        print(f"发送接口异常: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'code': -1, 'msg': str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
