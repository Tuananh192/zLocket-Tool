
from flask import Flask, render_template, request, jsonify, session
import threading
import time
import sys
from io import StringIO
from main import zLocket, main as original_main
import os

app = Flask(__name__)
app.secret_key = os.urandom(24)

# Global variables to store output and tool state
output_buffer = StringIO()
tool_running = False
tool_thread = None

class WebOutput:
    def __init__(self):
        self.messages = []
    
    def write(self, text):
        if text.strip():
            self.messages.append(text.strip())
    
    def flush(self):
        pass
    
    def get_messages(self):
        return self.messages[-50:]  # Return last 50 messages

web_output = WebOutput()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/start_tool', methods=['POST'])
def start_tool():
    global tool_running, tool_thread
    
    if tool_running:
        return jsonify({'status': 'error', 'message': 'Tool is already running'})
    
    data = request.json
    target = data.get('target', '')
    custom_name = data.get('custom_name', 'zLocket Tool Pro')
    use_emoji = data.get('use_emoji', True)
    
    if not target:
        return jsonify({'status': 'error', 'message': 'Target is required'})
    
    # Redirect stdout to capture output
    sys.stdout = web_output
    
    def run_tool():
        global tool_running
        try:
            tool_running = True
            
            # Import các hàm cần thiết từ main.py
            from main import init_proxy, step1_create_account, zLocket
            
            # Tạo config instance trước khi sử dụng
            web_output.write("Initializing configuration...")
            import main
            main.config = zLocket()
            
            # Set configuration from web input
            url = target.strip()
            if not url.startswith(("http://", "https://")) and not url.startswith("locket."):
                url = f"https://locket.cam/{url}"
            if url.startswith("locket."):
                url = f"https://{url}"
            
            uid = main.config._extract_uid_locket(url)
            if uid:
                main.config.TARGET_FRIEND_UID = uid
                main.config.NAME_TOOL = custom_name
                main.config.USE_EMOJI = use_emoji
                
                web_output.write(f"Tool started with target UID: {uid}")
                web_output.write(f"Custom name: {custom_name}")
                web_output.write(f"Emoji enabled: {use_emoji}")
                
                # Khởi tạo proxy và spam
                web_output.write("Initializing proxy system...")
                proxy_queue, num_threads = init_proxy()
                
                # Giảm số thread để tránh quá tải
                num_threads = min(num_threads, 20)
                web_output.write(f"Starting {num_threads} spam threads...")
                
                stop_event = threading.Event()
                threads = []
                
                # Tạo và chạy các thread spam
                for i in range(num_threads):
                    if not tool_running:  # Kiểm tra nếu user đã stop
                        break
                    thread = threading.Thread(
                        target=step1_create_account,
                        args=(i, proxy_queue, stop_event)
                    )
                    threads.append(thread)
                    thread.daemon = True
                    thread.start()
                    
                    if i % 5 == 0:
                        web_output.write(f"Started {i+1}/{num_threads} threads...")
                
                web_output.write("All spam threads activated!")
                web_output.write("Spam is running... Click Stop to terminate.")
                
                # Chờ cho đến khi tool_running = False hoặc threads kết thúc
                while tool_running and any(t.is_alive() for t in threads):
                    time.sleep(1)
                
                # Dừng tất cả threads
                stop_event.set()
                web_output.write("Stopping all threads...")
                
                for thread in threads:
                    thread.join(timeout=2)
                
                web_output.write("All threads stopped.")
                
            else:
                web_output.write("Failed to extract UID from target")
                
        except Exception as e:
            web_output.write(f"Error: {str(e)}")
            import traceback
            web_output.write(f"Traceback: {traceback.format_exc()}")
        finally:
            tool_running = False
    
    tool_thread = threading.Thread(target=run_tool)
    tool_thread.start()
    
    return jsonify({'status': 'success', 'message': 'Tool started'})

@app.route('/stop_tool', methods=['POST'])
def stop_tool():
    global tool_running
    tool_running = False
    return jsonify({'status': 'success', 'message': 'Tool stopped'})

@app.route('/get_output')
def get_output():
    return jsonify({
        'messages': web_output.get_messages(),
        'running': tool_running
    })

@app.route('/status')
def status():
    return jsonify({'running': tool_running})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
