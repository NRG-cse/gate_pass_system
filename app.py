# app.py - COMPLETELY FIXED APPROVAL_PENDING
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
    if init_db():
        print("✅ Database initialized successfully!")
    else:
        print("❌ Database initialization failed!")
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
            cursor.execute('SELECT COUNT(*) FROM users WHERE status = "pending"')
            pending_user_approvals = cursor.fetchone()[0]
            
            # Pending gate pass approvals for System Admin
            cursor.execute('SELECT COUNT(*) FROM gate_passes WHERE status = "pending_security"')
            pending_gatepass_approvals = cursor.fetchone()[0]
            
            pending_approvals = pending_user_approvals + pending_gatepass_approvals
            
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
            # Get department ID first
            cursor.execute('SELECT department_id FROM users WHERE id = %s', (session['user_id'],))
            user_dept = cursor.fetchone()
            
            if user_dept:
                department_id = user_dept[0]
                
                # Get department name
                cursor.execute('SELECT name FROM departments WHERE id = %s', (department_id,))
                dept_name_result = cursor.fetchone()
                dept_name = dept_name_result[0] if dept_name_result else ""
                
                cursor.execute('''SELECT COUNT(*) FROM gate_passes gp 
                               WHERE gp.department_id = %s''', (department_id,))
                total_passes = cursor.fetchone()[0]
                
                cursor.execute('''SELECT COUNT(*) FROM gate_passes gp 
                               WHERE gp.department_id = %s 
                               AND gp.status = "pending_dept"''', (department_id,))
                pending_passes = cursor.fetchone()[0]
                
                cursor.execute('''SELECT COUNT(*) FROM gate_passes gp 
                               WHERE gp.department_id = %s 
                               AND gp.material_type = 'returnable' 
                               AND gp.expected_return_date < NOW() 
                               AND gp.actual_return_date IS NULL 
                               AND gp.status = 'approved' ''', (department_id,))
                overdue_passes = cursor.fetchone()[0]
                
                # Pending user approvals for Department Head
                cursor.execute('''SELECT COUNT(*) FROM users u 
                               WHERE u.department_id = %s 
                               AND u.status = "pending"''', (department_id,))
                pending_user_approvals = cursor.fetchone()[0]
                
                pending_approvals = pending_user_approvals + pending_passes
            else:
                total_passes = pending_passes = overdue_passes = pending_approvals = 0
            
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
    """Show pending approvals for department heads and system admins"""
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    
    if session['role'] not in ['system_admin', 'department_head']:
        flash('Access denied! Only Department Heads and System Admins can view approvals.', 'error')
        return redirect(url_for('dashboard'))
    
    conn = get_db_connection()
    if conn is None:
        flash('Database connection failed!', 'error')
        return render_template('approval_pending.html', pending_users=[], pending_passes=[])
    
    cursor = conn.cursor()
    
    try:
        pending_users = []
        pending_passes = []
        
        # Get pending users based on role
        if session['role'] == 'system_admin':
            # System Admin can see ALL pending users
            cursor.execute('''
                SELECT u.*, d.name as department_name, dv.name as division_name
                FROM users u 
                LEFT JOIN departments d ON u.department_id = d.id 
                LEFT JOIN divisions dv ON u.division_id = dv.id 
                WHERE u.status = 'pending' 
                ORDER BY u.created_at DESC
            ''')
            pending_users = dict_fetchall(cursor)
            
            # System Admin can also see pending gate passes for security approval
            cursor.execute('''
                SELECT gp.*, u.name as creator_name, d.name as department_name, dv.name as division_name
                FROM gate_passes gp 
                JOIN users u ON gp.created_by = u.id 
                JOIN departments d ON gp.department_id = d.id 
                JOIN divisions dv ON gp.division_id = dv.id 
                WHERE gp.status = 'pending_security'
                ORDER BY gp.created_at DESC
            ''')
            pending_passes = dict_fetchall(cursor)
            
        elif session['role'] == 'department_head':
            # Department Head can only see users from their OWN department
            # First, get the department_id of the department head
            cursor.execute('SELECT department_id FROM users WHERE id = %s', (session['user_id'],))
            dept_result = cursor.fetchone()
            
            if dept_result:
                department_id = dept_result[0]
                
                # Get department name
                cursor.execute('SELECT name FROM departments WHERE id = %s', (department_id,))
                dept_name_result = cursor.fetchone()
                dept_name = dept_name_result[0] if dept_name_result else ""
                
                # Get pending users from this department
                cursor.execute('''
                    SELECT u.*, d.name as department_name, dv.name as division_name
                    FROM users u 
                    LEFT JOIN departments d ON u.department_id = d.id 
                    LEFT JOIN divisions dv ON u.division_id = dv.id 
                    WHERE u.status = 'pending' 
                    AND u.department_id = %s
                    ORDER BY u.created_at DESC
                ''', (department_id,))
                pending_users = dict_fetchall(cursor)
                
                # Department Head can see gate passes from their department
                cursor.execute('''
                    SELECT gp.*, u.name as creator_name, d.name as department_name, dv.name as division_name
                    FROM gate_passes gp 
                    JOIN users u ON gp.created_by = u.id 
                    JOIN departments d ON gp.department_id = d.id 
                    JOIN divisions dv ON gp.division_id = dv.id 
                    WHERE gp.status = 'pending_dept'
                    AND gp.department_id = %s
                    ORDER BY gp.created_at DESC
                ''', (department_id,))
                pending_passes = dict_fetchall(cursor)
        
        print(f"DEBUG: Found {len(pending_users)} pending users for {session['role']}")
        for user in pending_users:
            print(f"  - {user['username']} ({user['name']}) in {user.get('department_name', 'Unknown')}")
        
    except Exception as e:
        print(f"Approval pending error: {e}")
        import traceback
        traceback.print_exc()
        flash('Error loading pending approvals!', 'error')
    finally:
        cursor.close()
        conn.close()
    
    return render_template('approval_pending.html', 
                         pending_users=pending_users, 
                         pending_passes=pending_passes)

@app.route('/approve_user/<int:user_id>/<action>')
def approve_user(user_id, action):
    """Approve or reject user registration - FIXED VERSION"""
    if 'user_id' not in session or session['role'] not in ['system_admin', 'department_head']:
        return jsonify({'success': False, 'message': 'Access denied!'})
    
    if action not in ['approve', 'reject']:
        return jsonify({'success': False, 'message': 'Invalid action!'})
    
    conn = get_db_connection()
    if conn is None:
        return jsonify({'success': False, 'message': 'Database connection failed!'})
    
    cursor = conn.cursor()
    
    try:
        # Get user details
        cursor.execute('''
            SELECT u.*, d.name as department_name, d.id as dept_id
            FROM users u 
            LEFT JOIN departments d ON u.department_id = d.id 
            WHERE u.id = %s AND u.status = 'pending'
        ''', (user_id,))
        user = dict_fetchone(cursor)
        
        if not user:
            return jsonify({'success': False, 'message': 'User not found or already processed!'})
        
        # Check permissions for department head
        if session['role'] == 'department_head':
            # Get department head's department
            cursor.execute('SELECT department_id FROM users WHERE id = %s', (session['user_id'],))
            dept_head_dept = cursor.fetchone()
            
            if not dept_head_dept or dept_head_dept[0] != user['dept_id']:
                return jsonify({'success': False, 'message': 'You can only approve users from your department!'})
        
        # Update user status
        new_status = 'approved' if action == 'approve' else 'rejected'
        cursor.execute('''
            UPDATE users SET status = %s WHERE id = %s
        ''', (new_status, user_id))
        
        # Create notification for the user
        if action == 'approve':
            create_notification(
                user_id,
                f"🎉 Your account has been approved by {session['name']}! You can now login.",
                'status',
                None
            )
            
            # Also notify the other approver (if exists)
            if session['role'] == 'system_admin':
                # Notify department head that user was approved by admin
                cursor.execute('''
                    SELECT u.id FROM users u 
                    WHERE u.department_id = %s 
                    AND u.role = 'department_head' 
                    AND u.status = 'approved'
                    AND u.id != %s
                ''', (user['dept_id'], session['user_id']))
                dept_heads = dict_fetchall(cursor)
                for dept_head in dept_heads:
                    create_notification(
                        dept_head['id'],
                        f"✅ User {user['name']} from your department has been approved by System Administrator",
                        'status',
                        None
                    )
            else:
                # Notify system admin that user was approved by department head
                cursor.execute('SELECT id FROM users WHERE role = "system_admin" AND status = "approved"')
                admins = dict_fetchall(cursor)
                for admin in admins:
                    create_notification(
                        admin['id'],
                        f"✅ User {user['name']} has been approved by Department Head {session['name']}",
                        'status',
                        None
                    )
        else:
            create_notification(
                user_id,
                f"❌ Your account registration has been rejected by {session['name']}.",
                'status',
                None
            )
        
        conn.commit()
        
        message = f"User {user['name']} has been {action}d successfully!"
        return jsonify({'success': True, 'message': message})
        
    except Exception as e:
        conn.rollback()
        print(f"Error approving user: {e}")
        return jsonify({'success': False, 'message': f'Error processing user: {str(e)}'})
    finally:
        cursor.close()
        conn.close()

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