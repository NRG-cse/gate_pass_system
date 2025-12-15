# app.py - UPDATED WITH NEW APPROVAL SYSTEM
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from models import get_db_connection, init_db, dict_fetchall, dict_fetchone
from notifications import start_notification_scheduler, create_notification
from auth import auth_bp
from gate_pass import gate_pass_bp
from admin import admin_bp
import MySQLdb
from datetime import datetime
from flask import send_from_directory
import os
import json

app = Flask(__name__)
app.secret_key = 'gate-pass-system-secret-key-2024'

# Register blueprints
app.register_blueprint(auth_bp, url_prefix='/auth')
app.register_blueprint(gate_pass_bp, url_prefix='/gate_pass')
app.register_blueprint(admin_bp, url_prefix='/admin')

@app.route('/manifest.json')
def manifest():
    return send_from_directory('static', 'manifest.json')

@app.route('/service-worker.js')
def service_worker():
    return send_from_directory('static', 'js/service-worker.js', mimetype='application/javascript')

@app.route('/favicon.ico')
def favicon():
    return send_from_directory('static', 'icons/icon-32x32.png')

@app.route('/offline')
def offline():
    return render_template('offline.html')

@app.route('/install-pwa')
def install_pwa():
    return render_template('install_pwa.html')

# Initialize database and start scheduler
with app.app_context():
    init_db()
    start_notification_scheduler()

@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('auth.login'))

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    
    conn = get_db_connection()
    if conn is None:
        flash('Database connection failed!', 'error')
        return render_template('dashboard.html', 
                             total_passes=0, 
                             pending_passes=0, 
                             overdue_passes=0, 
                             pending_approvals=0,
                             notifications=[])
    
    cursor = conn.cursor()
    
    try:
        # Get statistics based on role
        if session['role'] == 'system_admin':
            # System Admin - All statistics
            cursor.execute('SELECT COUNT(*) FROM gate_passes')
            total_passes = cursor.fetchone()[0]
            
            cursor.execute('SELECT COUNT(*) FROM gate_passes WHERE status IN ("pending_dept", "pending_store", "pending_security")')
            pending_passes = cursor.fetchone()[0]
            
            cursor.execute('''SELECT COUNT(*) FROM gate_passes 
                           WHERE material_type = 'returnable' 
                           AND expected_return_date < NOW() 
                           AND actual_return_date IS NULL 
                           AND status = 'approved' ''')
            overdue_passes = cursor.fetchone()[0]
            
            # Pending user approvals for System Admin
            cursor.execute('''SELECT COUNT(*) FROM users 
                           WHERE status IN ('dual_pending', 'pending_admin') 
                           AND (approved_by_admin = FALSE OR approved_by_admin IS NULL)''')
            pending_approvals = cursor.fetchone()[0]
            
        elif session['role'] == 'store_manager':
            # Store Manager - Statistics for their store
            cursor.execute('SELECT COUNT(*) FROM gate_passes WHERE store_location = %s', 
                         ('store_1' if 'store1' in session['username'] else 'store_2',))
            total_passes = cursor.fetchone()[0]
            
            cursor.execute('''SELECT COUNT(*) FROM gate_passes 
                           WHERE store_location = %s 
                           AND status = "pending_store"''', 
                         ('store_1' if 'store1' in session['username'] else 'store_2',))
            pending_passes = cursor.fetchone()[0]
            
            cursor.execute('''SELECT COUNT(*) FROM gate_passes 
                           WHERE store_location = %s 
                           AND material_type = 'returnable' 
                           AND expected_return_date < NOW() 
                           AND actual_return_date IS NULL 
                           AND status = 'approved' ''', 
                         ('store_1' if 'store1' in session['username'] else 'store_2',))
            overdue_passes = cursor.fetchone()[0]
            
            pending_approvals = pending_passes
            
        elif session['role'] == 'department_head':
            # Department Head - Only their department statistics
            cursor.execute('''SELECT COUNT(*) FROM gate_passes gp 
                           JOIN departments d ON gp.department_id = d.id 
                           WHERE d.name = %s''', 
                         (session['department'],))
            total_passes = cursor.fetchone()[0]
            
            cursor.execute('''SELECT COUNT(*) FROM gate_passes gp 
                           JOIN departments d ON gp.department_id = d.id 
                           WHERE d.name = %s 
                           AND gp.status = "pending_dept"''', 
                         (session['department'],))
            pending_passes = cursor.fetchone()[0]
            
            cursor.execute('''SELECT COUNT(*) FROM gate_passes gp 
                           JOIN departments d ON gp.department_id = d.id 
                           WHERE d.name = %s 
                           AND gp.material_type = 'returnable' 
                           AND gp.expected_return_date < NOW() 
                           AND gp.actual_return_date IS NULL 
                           AND gp.status = 'approved' ''', 
                         (session['department'],))
            overdue_passes = cursor.fetchone()[0]
            
            # Pending user approvals for Department Head
            cursor.execute('''SELECT COUNT(DISTINCT u.id) 
                           FROM users u 
                           JOIN departments d ON u.department_id = d.id 
                           WHERE d.name = %s 
                           AND u.status IN ('dual_pending', 'pending_dept') 
                           AND (u.approved_by_dept_head = FALSE OR u.approved_by_dept_head IS NULL)''', 
                         (session['department'],))
            pending_approvals = cursor.fetchone()[0]
            
        elif session['role'] == 'security':
            # Security - Statistics for security approvals
            cursor.execute('SELECT COUNT(*) FROM gate_passes WHERE status = "pending_security"')
            pending_passes = cursor.fetchone()[0]
            
            cursor.execute('''SELECT COUNT(*) FROM gate_passes 
                           WHERE material_type = 'returnable' 
                           AND expected_return_date < NOW() 
                           AND actual_return_date IS NULL 
                           AND status = 'approved' ''')
            overdue_passes = cursor.fetchone()[0]
            
            total_passes = 0
            pending_approvals = pending_passes
            
        else:
            # Regular user - Only their own passes
            cursor.execute('SELECT COUNT(*) FROM gate_passes WHERE created_by = %s', 
                         (session['user_id'],))
            total_passes = cursor.fetchone()[0]
            
            cursor.execute('''SELECT COUNT(*) FROM gate_passes 
                           WHERE created_by = %s 
                           AND status IN ("pending_dept", "pending_store", "pending_security")''', 
                         (session['user_id'],))
            pending_passes = cursor.fetchone()[0]
            
            cursor.execute('''SELECT COUNT(*) FROM gate_passes 
                           WHERE created_by = %s 
                           AND material_type = 'returnable' 
                           AND expected_return_date < NOW() 
                           AND actual_return_date IS NULL 
                           AND status = 'approved' ''', 
                         (session['user_id'],))
            overdue_passes = cursor.fetchone()[0]
            
            pending_approvals = 0
        
        # Get user notifications
        cursor.execute('''
            SELECT * FROM notifications 
            WHERE user_id = %s 
            ORDER BY created_at DESC 
            LIMIT 5
        ''', (session['user_id'],))
        notifications = dict_fetchall(cursor)
        
    except Exception as e:
        print(f"Dashboard error: {e}")
        total_passes = pending_passes = overdue_passes = pending_approvals = 0
        notifications = []
    finally:
        cursor.close()
        conn.close()
    
    return render_template('dashboard.html',
                         total_passes=total_passes,
                         pending_passes=pending_passes,
                         overdue_passes=overdue_passes,
                         pending_approvals=pending_approvals,
                         notifications=notifications)

@app.route('/approval_pending')
def approval_pending():
    """Show pending approvals for both Admin and Department Head"""
    if 'user_id' not in session or session['role'] not in ['system_admin', 'department_head']:
        flash('Access denied!', 'error')
        return redirect(url_for('dashboard'))
    
    conn = get_db_connection()
    if conn is None:
        flash('Database connection failed!', 'error')
        return render_template('approval_pending.html', pending_users=[], pending_passes=[])
    
    cursor = conn.cursor()
    
    try:
        # Get pending users based on role
        if session['role'] == 'system_admin':
            # Admin can see all pending users who need admin approval
            cursor.execute('''
                SELECT u.*, d.name as department, dv.name as division
                FROM users u 
                LEFT JOIN departments d ON u.department_id = d.id 
                LEFT JOIN divisions dv ON u.division_id = dv.id 
                WHERE u.status IN ('dual_pending', 'pending_admin') 
                AND (u.approved_by_admin = FALSE OR u.approved_by_admin IS NULL)
                ORDER BY u.created_at DESC
            ''')
            pending_users = dict_fetchall(cursor)
            
            # Admin can see all pending gate passes
            cursor.execute('''
                SELECT gp.*, u.name as creator_name 
                FROM gate_passes gp 
                JOIN users u ON gp.created_by = u.id 
                WHERE gp.status = 'pending_security'
                ORDER BY gp.created_at DESC
            ''')
            pending_passes = dict_fetchall(cursor)
            
        elif session['role'] == 'department_head':
            # Department Head can only see users from their department
            cursor.execute('''
                SELECT u.*, d.name as department, dv.name as division
                FROM users u 
                JOIN departments d ON u.department_id = d.id 
                LEFT JOIN divisions dv ON u.division_id = dv.id 
                WHERE d.name = %s 
                AND u.status IN ('dual_pending', 'pending_dept') 
                AND (u.approved_by_dept_head = FALSE OR u.approved_by_dept_head IS NULL)
                ORDER BY u.created_at DESC
            ''', (session['department'],))
            pending_users = dict_fetchall(cursor)
            
            # Department Head can see gate passes from their department
            cursor.execute('''
                SELECT gp.*, u.name as creator_name 
                FROM gate_passes gp 
                JOIN users u ON gp.created_by = u.id 
                JOIN departments d ON gp.department_id = d.id 
                WHERE d.name = %s AND gp.status = 'pending_dept'
                ORDER BY gp.created_at DESC
            ''', (session['department'],))
            pending_passes = dict_fetchall(cursor)
        
    except Exception as e:
        print(f"Approval pending error: {e}")
        pending_users = []
        pending_passes = []
    finally:
        cursor.close()
        conn.close()
    
    return render_template('approval_pending.html', 
                         pending_users=pending_users, 
                         pending_passes=pending_passes)

@app.route('/mark_returned/<int:gate_pass_id>', methods=['POST'])
def mark_returned(gate_pass_id):
    if 'user_id' not in session or session['role'] != 'security':
        return jsonify({'success': False, 'message': 'Access denied'})
    
    conn = get_db_connection()
    if conn is None:
        return jsonify({'success': False, 'message': 'Database connection failed'})
    
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            UPDATE gate_passes 
            SET actual_return_date = %s, status = 'returned' 
            WHERE id = %s AND material_type = 'returnable'
        ''', (datetime.now(), gate_pass_id))
        
        if cursor.rowcount > 0:
            conn.commit()
            
            # Notify creator
            cursor.execute('SELECT created_by, pass_number FROM gate_passes WHERE id = %s', (gate_pass_id,))
            result = cursor.fetchone()
            if result:
                create_notification(
                    result[0],
                    f"Your material with Gate Pass {result[1]} has been returned",
                    'status',
                    gate_pass_id
                )
            
            return jsonify({'success': True, 'message': 'Material marked as returned!'})
        else:
            return jsonify({'success': False, 'message': 'Gate pass not found or not returnable'})
            
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'message': str(e)})
    finally:
        cursor.close()
        conn.close()

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)