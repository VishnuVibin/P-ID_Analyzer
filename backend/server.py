import os
import uuid
import sqlite3
import cv2
from flask import Flask, request, jsonify, send_file, send_from_directory
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from detector import PIDDetector

REACT_DIST_FOLDER = os.path.join(os.path.dirname(__file__), 'frontend', 'dist')
app = Flask(__name__, static_folder=REACT_DIST_FOLDER, static_url_path='/')

@app.route('/')
def serve_index():
    if os.path.exists(os.path.join(app.static_folder, 'index.html')):
        return send_file(os.path.join(app.static_folder, 'index.html'))
    return "Backend is running. React frontend build not found.", 200

# Configure folders
UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'uploads')
STATIC_OUTPUT_FOLDER = os.path.join(os.path.dirname(__file__), 'static', 'output')
DATABASE_FILE = os.path.join(os.path.dirname(__file__), 'users.db')

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(STATIC_OUTPUT_FOLDER, exist_ok=True)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['STATIC_OUTPUT_FOLDER'] = STATIC_OUTPUT_FOLDER

# Initialize SQLite database
def init_db():
    try:
        conn = sqlite3.connect(DATABASE_FILE)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL
            )
        ''')
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Error initializing SQLite database: {e}")

init_db()

# Global variable to cache the latest results for Excel download
latest_data = {
    'symbols': [],
    'connections': []
}

detector = PIDDetector()

@app.after_request
def add_cors_headers(response):
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type,Authorization'
    response.headers['Access-Control-Allow-Methods'] = 'GET,PUT,POST,DELETE,OPTIONS'
    return response

@app.route('/api/register', methods=['POST', 'OPTIONS'])
def register():
    if request.method == 'OPTIONS':
        return jsonify({'message': 'OK'}), 200
    data = request.get_json()
    if not data or 'username' not in data or 'password' not in data:
        return jsonify({'error': 'Please provide username and password'}), 400
    
    username = data['username'].strip()
    password = data['password']
    
    if not username or not password:
        return jsonify({'error': 'Username and password cannot be empty'}), 400
    
    conn = None
    try:
        conn = sqlite3.connect(DATABASE_FILE)
        cursor = conn.cursor()
        
        # Check if username exists
        cursor.execute("SELECT id FROM users WHERE username = ?", (username,))
        if cursor.fetchone():
            return jsonify({'error': 'Username already exists'}), 400
        
        # Hash password and insert
        hashed_pw = generate_password_hash(password)
        cursor.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, hashed_pw))
        conn.commit()
        return jsonify({'message': 'Registration successful'}), 200
    except Exception as e:
        return jsonify({'error': f"Database error: {str(e)}"}), 500
    finally:
        if conn:
            conn.close()

@app.route('/api/login', methods=['POST', 'OPTIONS'])
def login():
    if request.method == 'OPTIONS':
        return jsonify({'message': 'OK'}), 200
    data = request.get_json()
    if not data or 'username' not in data or 'password' not in data:
        return jsonify({'error': 'Please provide username and password'}), 400
    
    username = data['username'].strip()
    password = data['password']
    
    conn = None
    try:
        conn = sqlite3.connect(DATABASE_FILE)
        cursor = conn.cursor()
        cursor.execute("SELECT password FROM users WHERE username = ?", (username,))
        row = cursor.fetchone()
        if not row:
            return jsonify({'error': 'Invalid username or password'}), 401
        
        hashed_pw = row[0]
        if not check_password_hash(hashed_pw, password):
            return jsonify({'error': 'Invalid username or password'}), 401
        
        return jsonify({'message': 'Login successful', 'username': username}), 200
    except Exception as e:
        return jsonify({'error': f"Database error: {str(e)}"}), 500
    finally:
        if conn:
            conn.close()

@app.route('/api/process', methods=['POST', 'OPTIONS'])
def process_file():
    if request.method == 'OPTIONS':
        return jsonify({'message': 'OK'}), 200
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400

    filename = secure_filename(file.filename)
    unique_id = str(uuid.uuid4())
    file_ext = os.path.splitext(filename)[1].lower()
    saved_filename = f"{unique_id}{file_ext}"
    input_path = os.path.join(app.config['UPLOAD_FOLDER'], saved_filename)
    file.save(input_path)

    try:
        # 1. Extract image and text depending on file type
        if file_ext == '.pdf':
            img, text_blocks = detector.parse_pdf(input_path)
        elif file_ext in ['.png', '.jpg', '.jpeg']:
            img = cv2.imread(input_path)
            if img is None:
                return jsonify({'error': 'Failed to read image file'}), 400
            text_blocks = detector.ocr_image(img)
        else:
            return jsonify({'error': 'Unsupported file type. Please upload a PDF or image.'}), 400

        H, W, _ = img.shape

        # 2. Detect symbols
        symbols, grouped_text = detector.detect_symbols(img, text_blocks)

        # 3. Trace connections
        connections = detector.trace_connections(img, symbols, text_blocks)

        # 4. Save processed image as output reference
        output_filename = f"{unique_id}_processed.png"
        output_path = os.path.join(app.config['STATIC_OUTPUT_FOLDER'], output_filename)
        cv2.imwrite(output_path, img)

        # 5. Generate and save Excel sheet
        excel_filename = f"{unique_id}_inventory.xlsx"
        excel_path = os.path.join(app.config['STATIC_OUTPUT_FOLDER'], excel_filename)
        detector.generate_excel(symbols, connections, excel_path)

        # 6. Cache data in global dict for download endpoint
        global latest_data
        latest_data['symbols'] = symbols
        latest_data['connections'] = connections
        latest_data['excel_path'] = excel_path

        # 7. Format payload for React frontend
        response_data = {
            'image_url': f'/static/output/{output_filename}',
            'width': W,
            'height': H,
            'symbols': symbols,
            'connections': connections,
            'text_blocks': grouped_text,
            'excel_filename': excel_filename
        }
        return jsonify(response_data)

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': f"Error during processing: {str(e)}"}), 500
    finally:
        # Clean up raw upload to save space
        if os.path.exists(input_path):
            os.remove(input_path)

@app.route('/static/output/<filename>', methods=['GET'])
def serve_output_image(filename):
    return send_file(os.path.join(app.config['STATIC_OUTPUT_FOLDER'], filename))

@app.route('/api/download_excel', methods=['GET'])
def download_excel():
    excel_path = latest_data.get('excel_path')
    if excel_path and os.path.exists(excel_path):
        return send_file(
            excel_path,
            as_attachment=True,
            download_name="PID_Component_Inventory.xlsx",
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    else:
        return jsonify({'error': 'No inventory generated yet. Please process a P&ID diagram first.'}), 404

@app.route('/api/health', methods=['GET'])
def health_check():
    health = {
        'status': 'healthy',
        'database': 'ready',
        'database_path': DATABASE_FILE,
        'frontend_dist_path': REACT_DIST_FOLDER,
        'frontend_dist_exists': os.path.exists(REACT_DIST_FOLDER)
    }
    
    conn = None
    try:
        conn = sqlite3.connect(DATABASE_FILE)
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        cursor.fetchone()
    except Exception as e:
        health['status'] = 'unhealthy'
        health['database'] = f"error: {str(e)}"
    finally:
        if conn:
            conn.close()
            
    return jsonify(health), 200

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
