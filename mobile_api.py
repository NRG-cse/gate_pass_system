# mobile_api.py
from flask import Flask, jsonify, request
from flask_cors import CORS
import MySQLdb
from models import get_db_connection, hash_password, check_password

app = Flask(__name__)
CORS(app)  # Enable CORS for mobile apps

@app.route('/mobile/login', methods=['POST'])
def mobile_login():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    
    conn = get_db_connection()
    if conn is None:
        return jsonify({'success': False, 'message': 'Database connection failed'})
    
    cursor = conn.cursor()
    
    try:
        cursor.execute('SELECT * FROM users WHERE username = %s', (username,))
        user = cursor.fetchone()
        
        if user and check_password(user[2], password):  # user[2] is password field
            if user[9] != 'approved':  # user[9] is status field
                return jsonify({'success': False, 'message': 'Account pending approval'})
            
            return jsonify({
                'success': True,
                'user': {
                    'id': user[0],
                    'username': user[1],
                    'name': user[3],
                    'role': user[8],
                    'department': user[5]
                }
            })
        else:
            return jsonify({'success': False, 'message': 'Invalid credentials'})
            
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})
    finally:
        cursor.close()
        conn.close()

@app.route('/mobile/gate_passes', methods=['GET'])
def mobile_gate_passes():
    user_id = request.args.get('user_id')
    
    conn = get_db_connection()
    if conn is None:
        return jsonify({'success': False, 'message': 'Database connection failed'})
    
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            SELECT gp.*, u.name as creator_name 
            FROM gate_passes gp 
            JOIN users u ON gp.created_by = u.id 
            WHERE gp.created_by = %s 
            ORDER BY gp.created_at DESC
        ''', (user_id,))
        
        passes = []
        for row in cursor.fetchall():
            passes.append({
                'id': row[0],
                'pass_number': row[1],
                'division_department': row[3],
                'material_description': row[4],
                'destination': row[5],
                'status': row[16],
                'created_at': row[25].strftime('%Y-%m-%d %H:%M')
            })
        
        return jsonify({'success': True, 'gate_passes': passes})
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})
    finally:
        cursor.close()
        conn.close()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)