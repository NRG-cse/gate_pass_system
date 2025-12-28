# app.py - COMPLETE VERSION WITH OVERDUE RETURNS FEATURE
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from models import get_db_connection, init_db, dict_fetchall, dict_fetchone
from notifications import start_notification_scheduler, start_overdue_alarm_scheduler, create_notification
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

# Create upload folder if not exists
if not os.path.exists('static/uploads'):
    os.makedirs('static/uploads')
    print("✅ Created upload folder: static/uploads")

# Initialize database and start scheduler
with app.app_context():
    if init_db():
        print("✅ Database initialized successfully!")
    else:
        print("❌ Database initialization failed!")
    start_notification_scheduler()
    start_overdue_alarm_scheduler()  # ✅ THIS LINE WAS ADDED

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
                             notifications=[],
                             recent_passes=[],
                             unread_notifications=0,
                             approved_today=0,
                             now=datetime.now())
    
    cursor = conn.cursor()
    
    try:
        # Get statistics based on role
        if session['role'] == 'system_admin':
            # System Admin - All statistics (NO PENDING APPROVALS)
            cursor.execute('SELECT COUNT(*) FROM gate_passes')
            total_passes = cursor.fetchone()[0]
            
            # System Admin doesn't need pending approvals count
            pending_passes = 0
            
            cursor.execute('''SELECT COUNT(*) FROM gate_passes 
                           WHERE material_type = 'returnable' 
                           AND expected_return_date < NOW() 
                           AND actual_return_date IS NULL 
                           AND status = 'approved' ''')
            overdue_passes = cursor.fetchone()[0]
            
            # System Admin doesn't have pending approvals
            pending_approvals = 0
            
            # Approved today
            cursor.execute('''SELECT COUNT(*) FROM gate_passes 
                           WHERE DATE(created_at) = CURDATE() 
                           AND status = 'approved' ''')
            approved_today = cursor.fetchone()[0]
            
            # ✅ FIXED: Recent passes for admin (all)
            cursor.execute('''
                SELECT gp.*, u.name as creator_name, d.name as department_name, dv.name as division_name
                FROM gate_passes gp 
                JOIN users u ON gp.created_by = u.id 
                JOIN departments d ON gp.department_id = d.id 
                JOIN divisions dv ON gp.division_id = dv.id 
                ORDER BY gp.created_at DESC 
                LIMIT 5
            ''')
            recent_passes = dict_fetchall(cursor)
            
            # ✅ ADDED: Get pending users count for System Admin badge in sidebar
            cursor.execute('''SELECT COUNT(*) FROM users WHERE status = "pending"''')
            pending_users_count = cursor.fetchone()[0]
            
            # Add to session for sidebar badge
            session['pending_users_count'] = pending_users_count
            
        elif session['role'] == 'store_manager':
            # Store Manager - Statistics for store approvals
            store_location = 'store_1' if 'store1' in session['username'] else 'store_2'
            
            # ✅ FIXED: Total passes for store manager's store location
            cursor.execute('''SELECT COUNT(*) FROM gate_passes 
                           WHERE store_location = %s OR status = 'pending_store' ''', (store_location,))
            total_passes = cursor.fetchone()[0]
            
            # Pending store approvals
            cursor.execute('''SELECT COUNT(*) FROM gate_passes 
                           WHERE status = 'pending_store' ''')
            pending_passes = cursor.fetchone()[0]
            
            cursor.execute('''SELECT COUNT(*) FROM gate_passes 
                           WHERE material_type = 'returnable' 
                           AND expected_return_date < NOW() 
                           AND actual_return_date IS NULL 
                           AND status = 'approved' 
                           AND store_location = %s''', (store_location,))
            overdue_passes = cursor.fetchone()[0]
            
            # Store managers don't have user approvals
            pending_user_approvals = 0
            
            # Pending approvals = pending store approvals
            pending_approvals = pending_passes
            
            # Approved today for this store
            cursor.execute('''SELECT COUNT(*) FROM gate_passes 
                           WHERE DATE(created_at) = CURDATE() 
                           AND status = 'approved' 
                           AND store_location = %s''', (store_location,))
            approved_today = cursor.fetchone()[0]
            
            # ✅ FIXED: Recent passes for store manager (ALL gate passes, not just pending/approved)
            cursor.execute('''
                SELECT gp.*, u.name as creator_name, d.name as department_name, dv.name as division_name
                FROM gate_passes gp 
                JOIN users u ON gp.created_by = u.id 
                JOIN departments d ON gp.department_id = d.id 
                JOIN divisions dv ON gp.division_id = dv.id 
                WHERE (gp.store_location = %s OR gp.status = 'pending_store')
                ORDER BY gp.created_at DESC 
                LIMIT 5
            ''', (store_location,))
            recent_passes = dict_fetchall(cursor)
            
        elif session['role'] == 'department_head':
            # Department Head - Statistics for their department
            # Get department ID first
            cursor.execute('SELECT department_id FROM users WHERE id = %s', (session['user_id'],))
            user_dept = cursor.fetchone()
            
            if user_dept:
                department_id = user_dept[0]
                
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
                
                # Approved today for this department
                cursor.execute('''SELECT COUNT(*) FROM gate_passes 
                               WHERE department_id = %s 
                               AND DATE(created_at) = CURDATE() 
                               AND status = 'approved' ''', (department_id,))
                approved_today = cursor.fetchone()[0]
                
                # ✅ FIXED: Recent passes for department (ALL passes from department)
                cursor.execute('''
                    SELECT gp.*, u.name as creator_name, d.name as department_name, dv.name as division_name
                    FROM gate_passes gp 
                    JOIN users u ON gp.created_by = u.id 
                    JOIN departments d ON gp.department_id = d.id 
                    JOIN divisions dv ON gp.division_id = dv.id 
                    WHERE gp.department_id = %s
                    ORDER BY gp.created_at DESC 
                    LIMIT 5
                ''', (department_id,))
                recent_passes = dict_fetchall(cursor)
            else:
                total_passes = pending_passes = overdue_passes = pending_approvals = approved_today = 0
                recent_passes = []
            
        elif session['role'] == 'security':
            # Security - Statistics for security view
            # ✅ FIXED: Security can see ALL gate passes (not just approved)
            cursor.execute('''SELECT COUNT(*) FROM gate_passes 
                           WHERE department_approval = 'approved' ''')
            total_passes = cursor.fetchone()[0]
            
            # Pending security approvals (just for info)
            cursor.execute('''SELECT COUNT(*) FROM gate_passes 
                           WHERE status = 'pending_security' ''')
            pending_passes = cursor.fetchone()[0]
            
            cursor.execute('''SELECT COUNT(*) FROM gate_passes 
                           WHERE material_type = 'returnable' 
                           AND expected_return_date < NOW() 
                           AND actual_return_date IS NULL 
                           AND status = 'approved' ''')
            overdue_passes = cursor.fetchone()[0]
            
            # Security doesn't approve users
            pending_user_approvals = 0
            
            # Security doesn't need to approve gate passes (view only)
            pending_approvals = 0
            
            # Approved today
            cursor.execute('''SELECT COUNT(*) FROM gate_passes 
                           WHERE DATE(created_at) = CURDATE() 
                           AND status = 'approved' ''')
            approved_today = cursor.fetchone()[0]
            
            # ✅ FIXED: Recent passes for security (ALL department approved gate passes)
            cursor.execute('''
                SELECT gp.*, u.name as creator_name, d.name as department_name, dv.name as division_name
                FROM gate_passes gp 
                JOIN users u ON gp.created_by = u.id 
                JOIN departments d ON gp.department_id = d.id 
                JOIN divisions dv ON gp.division_id = dv.id 
                WHERE gp.department_approval = 'approved'
                ORDER BY gp.created_at DESC 
                LIMIT 5
            ''')
            recent_passes = dict_fetchall(cursor)
            
        else:
            # Regular user - Only their own passes
            cursor.execute('SELECT COUNT(*) FROM gate_passes WHERE created_by = %s', (session['user_id'],))
            total_passes = cursor.fetchone()[0]
            
            cursor.execute('''SELECT COUNT(*) FROM gate_passes 
                           WHERE created_by = %s 
                           AND status IN ("pending_dept", "pending_store", "pending_security")''', (session['user_id'],))
            pending_passes = cursor.fetchone()[0]
            
            cursor.execute('''SELECT COUNT(*) FROM gate_passes 
                           WHERE created_by = %s 
                           AND material_type = 'returnable' 
                           AND expected_return_date < NOW() 
                           AND actual_return_date IS NULL 
                           AND status = 'approved' ''', (session['user_id'],))
            overdue_passes = cursor.fetchone()[0]
            
            pending_approvals = 0
            
            # Approved today for this user
            cursor.execute('''SELECT COUNT(*) FROM gate_passes 
                           WHERE created_by = %s 
                           AND DATE(created_at) = CURDATE() 
                           AND status = 'approved' ''', (session['user_id'],))
            approved_today = cursor.fetchone()[0]
            
            # ✅ FIXED: Recent passes for user (their own passes)
            cursor.execute('''
                SELECT gp.*, u.name as creator_name, d.name as department_name, dv.name as division_name
                FROM gate_passes gp 
                JOIN users u ON gp.created_by = u.id 
                JOIN departments d ON gp.department_id = d.id 
                JOIN divisions dv ON gp.division_id = dv.id 
                WHERE gp.created_by = %s
                ORDER BY gp.created_at DESC 
                LIMIT 5
            ''', (session['user_id'],))
            recent_passes = dict_fetchall(cursor)
        
        # Get user notifications
        cursor.execute(''' 
            SELECT * FROM notifications 
            WHERE user_id = %s 
            ORDER BY created_at DESC 
            LIMIT 5
        ''', (session['user_id'],))
        notifications = dict_fetchall(cursor)
        
        # Get unread notification count
        cursor.execute(''' 
            SELECT COUNT(*) FROM notifications 
            WHERE user_id = %s AND is_read = FALSE
        ''', (session['user_id'],))
        unread_notifications = cursor.fetchone()[0]
        
        # ✅ ADDED: Get overdue count for sidebar badge
        cursor.execute('''
            SELECT COUNT(*) FROM gate_passes 
            WHERE material_type = 'returnable' 
            AND expected_return_date < NOW() 
            AND actual_return_date IS NULL 
            AND status = 'approved'
            AND (
                (created_by = %s) OR
                (department_id = %s AND %s IN ('department_head', 'system_admin', 'security')) OR
                (%s = 'store_manager' AND store_location = %s) OR
                (%s = 'system_admin') OR
                (%s = 'security')
            )
        ''', (session['user_id'], 
              session.get('department_id', 0), session['role'],
              session['role'], 'store_1' if 'store1' in session.get('username', '') else 'store_2',
              session['role'], session['role']))

        overdue_count = cursor.fetchone()[0] or 0
        session['overdue_count'] = overdue_count
        
    except Exception as e:
        print(f"Dashboard error: {e}")
        total_passes = pending_passes = overdue_passes = pending_approvals = 0
        approved_today = 0
        notifications = []
        recent_passes = []
        unread_notifications = 0
        session['overdue_count'] = 0
    finally:
        cursor.close()
        conn.close()
    
    return render_template('dashboard.html',
                         total_passes=total_passes,
                         pending_passes=pending_passes,
                         overdue_passes=overdue_passes,
                         pending_approvals=pending_approvals,
                         approved_today=approved_today,
                         notifications=notifications,
                         recent_passes=recent_passes,
                         unread_notifications=unread_notifications,
                         now=datetime.now())

@app.route('/approval_pending')
def approval_pending():
    """Show pending approvals for department heads and store managers ONLY"""
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    
    # ✅ UPDATED: System Admin should be redirected to admin user approvals
    if session['role'] == 'system_admin':
        flash('System Administrator: Use Admin Panel → User Approvals for user approvals.', 'info')
        return redirect(url_for('admin.user_approvals'))
    
    if session['role'] not in ['department_head', 'store_manager']:
        flash('Access denied! Only Department Heads and Store Managers can view approvals.', 'error')
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
        if session['role'] == 'department_head':
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
                
                # Department Head can see gate passes from their department that are pending
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
                
        elif session['role'] == 'store_manager':
            # Store Manager can see gate passes pending store approval
            store_location = 'store_1' if 'store1' in session['username'] else 'store_2'
            
            cursor.execute('''
                SELECT gp.*, u.name as creator_name, d.name as department_name, dv.name as division_name
                FROM gate_passes gp 
                JOIN users u ON gp.created_by = u.id 
                JOIN departments d ON gp.department_id = d.id 
                JOIN divisions dv ON gp.division_id = dv.id 
                WHERE gp.status = 'pending_store'
                ORDER BY gp.created_at DESC
            ''')
            pending_passes = dict_fetchall(cursor)
            
            # Store managers don't approve users
            pending_users = []
        
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
                         pending_passes=pending_passes,
                         now=datetime.now())

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
            WHERE u.id = %s
        ''', (user_id,))
        user = dict_fetchone(cursor)
        
        if not user:
            return jsonify({'success': False, 'message': 'User not found!'})
        
        # Check if already approved/rejected
        if user['status'] != 'pending':
            return jsonify({'success': False, 'message': f'User already {user["status"]}!'})
        
        # Check permissions for department head
        if session['role'] == 'department_head':
            cursor.execute('SELECT department_id FROM users WHERE id = %s', (session['user_id'],))
            dept_head_dept = cursor.fetchone()
            
            if not dept_head_dept or dept_head_dept[0] != user['dept_id']:
                return jsonify({'success': False, 'message': 'You can only approve users from your department!'})
        
        # Update user status
        new_status = 'approved' if action == 'approve' else 'rejected'
        cursor.execute('UPDATE users SET status = %s WHERE id = %s', (new_status, user_id))
        
        conn.commit()
        
        # Create notification for the user
        try:
            if action == 'approve':
                create_notification(
                    user_id,
                    f"🎉 Your account has been approved by {session['name']}! You can now login.",
                    'status',
                    None
                )
                
                # Also notify the other approver
                if session['role'] == 'system_admin':
                    conn2 = get_db_connection()
                    cursor2 = conn2.cursor()
                    cursor2.execute('''
                        SELECT u.id FROM users u 
                        WHERE u.department_id = %s 
                        AND u.role = 'department_head' 
                        AND u.status = 'approved'
                        AND u.id != %s
                    ''', (user['dept_id'], session['user_id']))
                    dept_heads = dict_fetchall(cursor2)
                    for dept_head in dept_heads:
                        create_notification(
                            dept_head['id'],
                            f"✅ User {user['name']} from your department has been approved by System Administrator",
                            'status',
                            None
                        )
                    cursor2.close()
                    conn2.close()
                else:
                    conn2 = get_db_connection()
                    cursor2 = conn2.cursor()
                    cursor2.execute('SELECT id FROM users WHERE role = "system_admin" AND status = "approved"')
                    admins = dict_fetchall(cursor2)
                    for admin in admins:
                        create_notification(
                            admin['id'],
                            f"✅ User {user['name']} has been approved by Department Head {session['name']}",
                            'status',
                            None
                        )
                    cursor2.close()
                    conn2.close()
            else:
                create_notification(
                    user_id,
                    f"❌ Your account registration has been rejected by {session['name']}.",
                    'status',
                    None
                )
        except Exception as notify_error:
            print(f"Notification error (non-critical): {notify_error}")
        
        message = f"User {user['name']} has been {action}d successfully!"
        return jsonify({'success': True, 'message': message})
        
    except MySQLdb.OperationalError as oe:
        print(f"MySQL error: {oe}")
        conn.rollback()
        return jsonify({'success': False, 'message': f'Database error: {str(oe)}'})
    except Exception as e:
        print(f"Error approving user: {e}")
        conn.rollback()
        return jsonify({'success': False, 'message': f'Error processing user: {str(e)}'})
    finally:
        cursor.close()
        conn.close()

def notify_gate_pass_printed(gate_pass_id, printed_by_user_id, printed_by_name):
    """Send notifications to all parties when security prints a gate pass"""
    conn = get_db_connection()
    if conn is None:
        return False
    
    cursor = conn.cursor()
    
    try:
        # Get gate pass details
        cursor.execute('''
            SELECT gp.*, u.id as creator_id, u.name as creator_name,
                   d.name as department_name, d.id as department_id,
                   dh.id as dept_head_id, dh.name as dept_head_name,
                   sm.id as store_manager_id, sm.name as store_manager_name
            FROM gate_passes gp 
            JOIN users u ON gp.created_by = u.id 
            JOIN departments d ON gp.department_id = d.id 
            LEFT JOIN users dh ON d.id = dh.department_id AND dh.role = 'department_head' AND dh.status = 'approved'
            LEFT JOIN users sm ON gp.store_location = CASE 
                WHEN sm.username = 'store1' THEN 'store_1'
                WHEN sm.username = 'store2' THEN 'store_2'
                ELSE NULL 
            END AND sm.role = 'store_manager' AND sm.status = 'approved'
            WHERE gp.id = %s
        ''', (gate_pass_id,))
        
        gate_pass = dict_fetchone(cursor)
        
        if not gate_pass:
            return False
        
        pass_number = gate_pass['pass_number']
        
        # Send notifications to all parties
        
        # 1. Notify CREATOR (user who created the gate pass)
        create_notification(
            gate_pass['creator_id'],
            f"🖨️ Gate Pass {pass_number} has been printed and material has left the gate by Security ({printed_by_name})",
            'status',
            gate_pass_id
        )
        
        # 2. Notify DEPARTMENT HEAD (if exists)
        if gate_pass['dept_head_id']:
            create_notification(
                gate_pass['dept_head_id'],
                f"🖨️ Gate Pass {pass_number} from your department has left the gate",
                'status',
                gate_pass_id
            )
        
        # 3. Notify STORE MANAGER (if store was involved)
        if gate_pass['store_manager_id']:
            create_notification(
                gate_pass['store_manager_id'],
                f"🖨️ Gate Pass {pass_number} has left the gate",
                'status',
                gate_pass_id
            )
        
        # 4. Notify ALL SYSTEM ADMINS
        cursor.execute('SELECT id FROM users WHERE role = "system_admin" AND status = "approved"')
        admins = dict_fetchall(cursor)
        for admin in admins:
            create_notification(
                admin['id'],
                f"🖨️ Gate Pass {pass_number} has left the gate (Printed by Security: {printed_by_name})",
                'alert',
                gate_pass_id
            )
        
        # 5. Log the printing event in security logs
        cursor.execute('''
            INSERT INTO security_logs (gate_pass_id, user_id, alert_type, details)
            VALUES (%s, %s, 'dispatched_from_gate', %s)
        ''', (gate_pass_id, printed_by_user_id, 
              f'Gate pass printed and material left the gate. Dispatched by: {printed_by_name}'))
        
        conn.commit()
        return True
        
    except Exception as e:
        print(f"Error sending print notifications: {e}")
        conn.rollback()
        return False
    finally:
        cursor.close()
        conn.close()

# ✅ ADDED: Security QR Scan and Return Marking
@app.route('/security/scan_qr', methods=['POST'])
def security_scan_qr():
    """Security scans QR code to mark material as returned"""
    if 'user_id' not in session or session['role'] != 'security':
        return jsonify({'success': False, 'message': 'Access denied! Only Security can scan QR codes.'})
    
    data = request.get_json()
    qr_data = data.get('qr_data')
    
    if not qr_data:
        return jsonify({'success': False, 'message': 'No QR data provided!'})
    
    # Verify QR code
    from qr_utils import verify_qr_code
    is_valid, result = verify_qr_code(qr_data)
    
    if not is_valid:
        return jsonify({'success': False, 'message': result})
    
    gate_pass_id = result['gate_pass_id']
    pass_number = result['pass_number']
    
    conn = get_db_connection()
    if conn is None:
        return jsonify({'success': False, 'message': 'Database connection failed!'})
    
    cursor = conn.cursor()
    
    try:
        # Get gate pass details
        cursor.execute('''
            SELECT gp.*, u.name as creator_name, u.id as creator_id, 
                   u.department_id as creator_dept_id, d.name as department_name,
                   dh.id as dept_head_id, dh.name as dept_head_name
            FROM gate_passes gp 
            JOIN users u ON gp.created_by = u.id 
            JOIN departments d ON u.department_id = d.id
            LEFT JOIN users dh ON d.id = dh.department_id AND dh.role = 'department_head' AND dh.status = 'approved'
            WHERE gp.id = %s AND gp.material_type = 'returnable'
        ''', (gate_pass_id,))
        
        gate_pass = dict_fetchone(cursor)
        
        if not gate_pass:
            return jsonify({'success': False, 'message': 'Gate pass not found or not returnable!'})
        
        # Check if already returned
        if gate_pass['actual_return_date']:
            return jsonify({'success': False, 'message': 'Material already returned!'})
        
        # Update as returned
        cursor.execute('''
            UPDATE gate_passes 
            SET actual_return_date = %s, status = 'returned',
                security_approval_date = %s
            WHERE id = %s
        ''', (datetime.now(), datetime.now(), gate_pass_id))
        
        # Create security log
        cursor.execute('''
            INSERT INTO security_logs (gate_pass_id, user_id, alert_type, details)
            VALUES (%s, %s, 'material_returned', %s)
        ''', (gate_pass_id, session['user_id'], 
              f'Material returned via QR scan. Scanned by: {session["name"]}'))
        
        conn.commit()
        
        # Send notifications to all parties
        notifications_sent = []
        
        # 1. Notify Creator
        create_notification(
            gate_pass['creator_id'],
            f"✅ Your material with Gate Pass {pass_number} has been returned and verified by Security.",
            'status',
            gate_pass_id
        )
        notifications_sent.append('Creator')
        
        # 2. Notify Department Head (if exists)
        if gate_pass['dept_head_id']:
            create_notification(
                gate_pass['dept_head_id'],
                f"📦 Material from your department (Gate Pass {pass_number}) has been returned.",
                'status',
                gate_pass_id
            )
            notifications_sent.append('Department Head')
        
        # 3. Notify all Super Admins
        cursor.execute('SELECT id FROM users WHERE role = "system_admin" AND status = "approved"')
        admins = dict_fetchall(cursor)
        for admin in admins:
            create_notification(
                admin['id'],
                f"🔄 Material Return: Gate Pass {pass_number} from {gate_pass['department_name']} has been returned.",
                'status',
                gate_pass_id
            )
        notifications_sent.append('Super Admin')
        
        # 4. Notify Store Manager (if store was involved)
        if gate_pass['store_location']:
            cursor.execute('''
                SELECT u.id FROM users u 
                WHERE u.role = 'store_manager' AND u.status = 'approved'
                LIMIT 1
            ''')
            store_manager = cursor.fetchone()
            if store_manager:
                create_notification(
                    store_manager[0],
                    f"📦 Material with Gate Pass {pass_number} has been returned.",
                    'status',
                    gate_pass_id
                )
                notifications_sent.append('Store Manager')
        
        cursor.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': f'✅ Material marked as returned! Notifications sent to: {", ".join(notifications_sent)}',
            'gate_pass': {
                'pass_number': pass_number,
                'material_description': gate_pass['material_description'],
                'department': gate_pass['department_name'],
                'return_time': datetime.now().strftime('%Y-%m-d %H:%M:%S')
            }
        })
        
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'message': f'Error processing return: {str(e)}'})
    finally:
        cursor.close()
        conn.close()

@app.route('/security/print_gate_pass/<int:gate_pass_id>')
def security_print_gate_pass(gate_pass_id):
    """Security prints gate pass copy"""
    if 'user_id' not in session or session['role'] != 'security':
        flash('Access denied! Only Security can print gate passes.', 'error')
        return redirect(url_for('dashboard'))
    
    conn = get_db_connection()
    if conn is None:
        flash('Database connection failed!', 'error')
        return redirect(url_for('gate_pass.gate_pass_list'))
    
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            SELECT gp.*, u.name as creator_name, u.designation as creator_designation,
                   d.name as department_name, dv.name as division_name,
                   dh.name as dept_head_name, dh.designation as dept_head_designation
            FROM gate_passes gp 
            JOIN users u ON gp.created_by = u.id 
            JOIN departments d ON gp.department_id = d.id 
            JOIN divisions dv ON gp.division_id = dv.id 
            LEFT JOIN users dh ON d.id = dh.department_id AND dh.role = 'department_head' AND dh.status = 'approved'
            WHERE gp.id = %s AND gp.department_approval = 'approved'
        ''', (gate_pass_id,))
        
        gate_pass = dict_fetchone(cursor)
        
        if not gate_pass:
            flash('Gate pass not found or not approved by department!', 'error')
            return redirect(url_for('gate_pass.gate_pass_list'))
        
        # Parse images JSON
        try:
            gate_pass['images_list'] = json.loads(gate_pass['images']) if gate_pass['images'] else []
        except:
            gate_pass['images_list'] = []
        
        # Generate QR codes
        from qr_utils import generate_qr_code
        if gate_pass['qr_code_form']:
            gate_pass['qr_form_img'] = generate_qr_code(gate_pass['qr_code_form'])
        
        if gate_pass['qr_code_sticker']:
            gate_pass['qr_sticker_img'] = generate_qr_code(gate_pass['qr_code_sticker'])
        
        # ✅ CRITICAL UPDATE: Update gate pass status to 'gone_from_gate' when security prints
        cursor.execute('''
            UPDATE gate_passes 
            SET status = 'gone_from_gate',
                security_approval = 'approved',
                security_approval_date = %s,
                approved_by_security = %s,
                gate_exit_time = %s
            WHERE id = %s
        ''', (datetime.now(), session['name'], datetime.now(), gate_pass_id))
        
        conn.commit()
        
        # ✅ Now send notifications to all parties
        notify_gate_pass_printed(gate_pass_id, session['user_id'], session['name'])
        
    except Exception as e:
        print(f"Print error: {e}")
        flash('Error loading gate pass for printing!', 'error')
        return redirect(url_for('gate_pass.gate_pass_list'))
    finally:
        cursor.close()
        conn.close()
    
    # Use the new template
    return render_template('security/print_gate_pass.html', 
                         gate_pass=gate_pass, 
                         now=datetime.now(),
                         security_name=session['name'])

# ✅ ADDED: Security QR Scan Page
@app.route('/security/scan')
def security_scan_page():
    """Security QR scan page"""
    if 'user_id' not in session or session['role'] != 'security':
        flash('Access denied! Only Security can access QR scanner.', 'error')
        return redirect(url_for('dashboard'))
    
    return render_template('security/scan_qr.html')

# ✅ ADDED: Today's Returns API for Security
@app.route('/security/today_returns')
def security_today_returns():
    """Get today's material returns for security"""
    if 'user_id' not in session or session['role'] != 'security':
        return jsonify({'success': False, 'message': 'Access denied!'})
    
    conn = get_db_connection()
    if conn is None:
        return jsonify({'success': False, 'message': 'Database connection failed!'})
    
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            SELECT gp.pass_number, gp.material_description, 
                   d.name as department, gp.actual_return_date,
                   DATE_FORMAT(gp.actual_return_date, '%H:%i') as return_time
            FROM gate_passes gp
            JOIN departments d ON gp.department_id = d.id
            WHERE DATE(gp.actual_return_date) = CURDATE()
            AND gp.actual_return_date IS NOT NULL
            ORDER BY gp.actual_return_date DESC
            LIMIT 10
        ''')
        
        returns = []
        for row in cursor.fetchall():
            returns.append({
                'pass_number': row[0],
                'material': row[1][:50] + ('...' if len(row[1]) > 50 else ''),
                'department': row[2],
                'return_time': row[4]
            })
        
        return jsonify({'success': True, 'returns': returns})
        
    except Exception as e:
        print(f"Error loading today's returns: {e}")
        return jsonify({'success': False, 'message': str(e)})
    finally:
        cursor.close()
        conn.close()

# ✅ ADDED: Mark Returned (Legacy route for backward compatibility)
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

# ✅ ADDED: Overdue Returns Page
@app.route('/overdue_returns')
def overdue_returns():
    """View all overdue returnable gate passes"""
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    
    conn = get_db_connection()
    if conn is None:
        flash('Database connection failed!', 'error')
        return render_template('overdue_returns.html', overdue_passes=[], now=datetime.now())
    
    cursor = conn.cursor()
    
    try:
        base_query = '''
            SELECT gp.*, u.name as creator_name, u.id as creator_id,
                   d.name as department_name, dv.name as division_name,
                   u.department_id as creator_dept_id,
                   TIMESTAMPDIFF(HOUR, gp.expected_return_date, NOW()) as overdue_hours,
                   TIMESTAMPDIFF(DAY, gp.expected_return_date, NOW()) as overdue_days
            FROM gate_passes gp
            JOIN users u ON gp.created_by = u.id
            JOIN departments d ON gp.department_id = d.id
            JOIN divisions dv ON gp.division_id = dv.id
            WHERE gp.material_type = 'returnable' 
            AND gp.expected_return_date < NOW() 
            AND gp.actual_return_date IS NULL
            AND gp.status = 'approved'
        '''
        
        if session['role'] == 'system_admin':
            # System Admin sees ALL overdue returns
            cursor.execute(f"{base_query} ORDER BY gp.expected_return_date ASC")
            overdue_passes = dict_fetchall(cursor)
            
        elif session['role'] == 'store_manager':
            # Store Managers see overdue passes from their store
            store_location = 'store_1' if 'store1' in session['username'] else 'store_2'
            cursor.execute(f'''
                {base_query} AND gp.store_location = %s 
                ORDER BY gp.expected_return_date ASC
            ''', (store_location,))
            overdue_passes = dict_fetchall(cursor)
            
        elif session['role'] == 'security':
            # Security sees ALL overdue returns (similar to system admin)
            cursor.execute(f"{base_query} ORDER BY gp.expected_return_date ASC")
            overdue_passes = dict_fetchall(cursor)
            
        elif session['role'] == 'department_head':
            # Department Head sees overdue passes from their department
            cursor.execute('SELECT department_id FROM users WHERE id = %s', (session['user_id'],))
            dept_result = cursor.fetchone()
            
            if dept_result:
                department_id = dept_result[0]
                cursor.execute(f'''
                    {base_query} AND gp.department_id = %s 
                    ORDER BY gp.expected_return_date ASC
                ''', (department_id,))
                overdue_passes = dict_fetchall(cursor)
            else:
                overdue_passes = []
                
        else:
            # Regular user sees only their own overdue passes
            cursor.execute(f'''
                {base_query} AND gp.created_by = %s 
                ORDER BY gp.expected_return_date ASC
            ''', (session['user_id'],))
            overdue_passes = dict_fetchall(cursor)
        
        # Get statistics
        cursor.execute('''
            SELECT COUNT(*) as total_overdue,
                   COUNT(CASE WHEN TIMESTAMPDIFF(DAY, expected_return_date, NOW()) > 7 THEN 1 END) as critical_overdue,
                   COUNT(CASE WHEN TIMESTAMPDIFF(DAY, expected_return_date, NOW()) BETWEEN 1 AND 7 THEN 1 END) as high_overdue
            FROM gate_passes
            WHERE material_type = 'returnable' 
            AND expected_return_date < NOW() 
            AND actual_return_date IS NULL
            AND status = 'approved'
        ''')
        stats = dict_fetchone(cursor)
        
    except Exception as e:
        print(f"Overdue returns error: {e}")
        import traceback
        traceback.print_exc()
        overdue_passes = []
        stats = {'total_overdue': 0, 'critical_overdue': 0, 'high_overdue': 0}
    finally:
        cursor.close()
        conn.close()
    
    return render_template('overdue_returns.html', 
                         overdue_passes=overdue_passes,
                         stats=stats,
                         now=datetime.now())

@app.route('/api/check_overdue_alarm')
def check_overdue_alarm():
    """Check if user has overdue materials for alarm"""
    if 'user_id' not in session:
        return jsonify({'has_overdue': False, 'overdue_count': 0})
    
    conn = get_db_connection()
    if conn is None:
        return jsonify({'has_overdue': False, 'overdue_count': 0})
    
    cursor = conn.cursor()
    
    try:
        base_query = '''
            SELECT COUNT(*) as overdue_count
            FROM gate_passes gp
            WHERE gp.material_type = 'returnable' 
            AND gp.expected_return_date < NOW() 
            AND gp.actual_return_date IS NULL
            AND gp.status = 'approved'
        '''
        
        if session['role'] == 'system_admin':
            # System Admin - all overdue
            cursor.execute(base_query)
            
        elif session['role'] == 'store_manager':
            # Store Manager - their store's overdue
            store_location = 'store_1' if 'store1' in session['username'] else 'store_2'
            cursor.execute(f"{base_query} AND gp.store_location = %s", (store_location,))
            
        elif session['role'] == 'security':
            # Security - all overdue
            cursor.execute(base_query)
            
        elif session['role'] == 'department_head':
            # Department Head - their department's overdue
            cursor.execute('SELECT department_id FROM users WHERE id = %s', (session['user_id'],))
            dept_result = cursor.fetchone()
            
            if dept_result:
                department_id = dept_result[0]
                cursor.execute(f"{base_query} AND gp.department_id = %s", (department_id,))
            else:
                return jsonify({'has_overdue': False, 'overdue_count': 0})
                
        else:
            # Regular user - their own overdue
            cursor.execute(f"{base_query} AND gp.created_by = %s", (session['user_id'],))
        
        result = cursor.fetchone()
        overdue_count = result[0] if result else 0
        
        return jsonify({
            'has_overdue': overdue_count > 0,
            'overdue_count': overdue_count
        })
        
    except Exception as e:
        print(f"Alarm check error: {e}")
        return jsonify({'has_overdue': False, 'overdue_count': 0})
    finally:
        cursor.close()
        conn.close()

@app.route('/api/send_overdue_reminder/<int:gate_pass_id>', methods=['POST'])
def send_overdue_reminder(gate_pass_id):
    """Send reminder notification for overdue material"""
    if 'user_id' not in session or session['role'] not in ['system_admin', 'department_head']:
        return jsonify({'success': False, 'message': 'Access denied!'})
    
    conn = get_db_connection()
    if conn is None:
        return jsonify({'success': False, 'message': 'Database connection failed!'})
    
    cursor = conn.cursor()
    
    try:
        # Get gate pass details
        cursor.execute('''
            SELECT gp.*, u.id as creator_id, u.name as creator_name,
                   d.name as department_name, TIMESTAMPDIFF(DAY, gp.expected_return_date, NOW()) as overdue_days
            FROM gate_passes gp
            JOIN users u ON gp.created_by = u.id
            JOIN departments d ON gp.department_id = d.id
            WHERE gp.id = %s AND gp.material_type = 'returnable' 
            AND gp.expected_return_date < NOW() 
            AND gp.actual_return_date IS NULL
            AND gp.status = 'approved'
        ''', (gate_pass_id,))
        
        gate_pass = dict_fetchone(cursor)
        
        if not gate_pass:
            return jsonify({'success': False, 'message': 'Gate pass not found or not overdue!'})
        
        # Check permissions
        if session['role'] == 'department_head':
            cursor.execute('SELECT department_id FROM users WHERE id = %s', (session['user_id'],))
            dept_head_dept = cursor.fetchone()
            
            if not dept_head_dept or dept_head_dept[0] != gate_pass['department_id']:
                return jsonify({'success': False, 'message': 'You can only send reminders for your department!'})
        
        # Send reminder to creator
        overdue_days = gate_pass['overdue_days'] or 0
        reminder_message = f"⏰ REMINDER: Your material with Gate Pass {gate_pass['pass_number']} is {overdue_days} day(s) overdue! Please return immediately."
        
        create_notification(
            gate_pass['creator_id'],
            reminder_message,
            'alert',
            gate_pass_id
        )
        
        # Also notify department head (if not the one sending)
        if session['role'] == 'system_admin':
            cursor.execute('''
                SELECT u.id FROM users u 
                WHERE u.department_id = %s 
                AND u.role = 'department_head' 
                AND u.status = 'approved'
                LIMIT 1
            ''', (gate_pass['department_id'],))
            
            dept_head = cursor.fetchone()
            if dept_head and dept_head[0] != session['user_id']:
                create_notification(
                    dept_head[0],
                    f"⏰ Reminder sent to {gate_pass['creator_name']} for overdue Gate Pass {gate_pass['pass_number']}",
                    'info',
                    gate_pass_id
                )
        
        # Log the reminder
        cursor.execute('''
            INSERT INTO overdue_reminders (gate_pass_id, reminded_by, reminder_date, remarks)
            VALUES (%s, %s, %s, %s)
        ''', (gate_pass_id, session['user_id'], datetime.now(), 
              f"Manual reminder sent by {session['name']}"))
        
        conn.commit()
        
        return jsonify({
            'success': True, 
            'message': f'Reminder sent to {gate_pass["creator_name"]}!'
        })
        
    except Exception as e:
        conn.rollback()
        print(f"Reminder error: {e}")
        return jsonify({'success': False, 'message': f'Error: {str(e)}'})
    finally:
        cursor.close()
        conn.close()

@app.route('/api/mark_force_returned/<int:gate_pass_id>', methods=['POST'])
def mark_force_returned(gate_pass_id):
    """System Admin marks overdue material as force returned"""
    if 'user_id' not in session or session['role'] != 'system_admin':
        return jsonify({'success': False, 'message': 'Access denied!'})
    
    data = request.get_json()
    remarks = data.get('remarks', '').strip()
    notify_all = data.get('notify_all', True)
    
    if not remarks:
        return jsonify({'success': False, 'message': 'Remarks required for force return!'})
    
    conn = get_db_connection()
    if conn is None:
        return jsonify({'success': False, 'message': 'Database connection failed!'})
    
    cursor = conn.cursor()
    
    try:
        # Get gate pass details
        cursor.execute('''
            SELECT gp.*, u.id as creator_id, u.name as creator_name,
                   d.name as department_name, u.department_id,
                   dh.id as dept_head_id, dh.name as dept_head_name
            FROM gate_passes gp
            JOIN users u ON gp.created_by = u.id
            JOIN departments d ON gp.department_id = d.id
            LEFT JOIN users dh ON d.id = dh.department_id AND dh.role = 'department_head' AND dh.status = 'approved'
            WHERE gp.id = %s AND gp.material_type = 'returnable' 
            AND gp.actual_return_date IS NULL
        ''', (gate_pass_id,))
        
        gate_pass = dict_fetchone(cursor)
        
        if not gate_pass:
            return jsonify({'success': False, 'message': 'Gate pass not found!'})
        
        # Mark as force returned
        cursor.execute('''
            UPDATE gate_passes 
            SET actual_return_date = %s, 
                status = 'force_returned',
                force_return_remarks = %s,
                force_returned_by = %s
            WHERE id = %s
        ''', (datetime.now(), remarks, session['user_id'], gate_pass_id))
        
        # Log the force return
        cursor.execute('''
            INSERT INTO force_return_logs (gate_pass_id, returned_by, return_date, remarks)
            VALUES (%s, %s, %s, %s)
        ''', (gate_pass_id, session['user_id'], datetime.now(), remarks))
        
        conn.commit()
        
        # Send notifications if requested
        if notify_all:
            # Notify creator
            create_notification(
                gate_pass['creator_id'],
                f"⚠️ Your material with Gate Pass {gate_pass['pass_number']} has been marked as force returned by System Admin. Remarks: {remarks}",
                'alert',
                gate_pass_id
            )
            
            # Notify department head
            if gate_pass['dept_head_id']:
                create_notification(
                    gate_pass['dept_head_id'],
                    f"⚠️ Material from your department (Gate Pass {gate_pass['pass_number']}) has been marked force returned by System Admin.",
                    'alert',
                    gate_pass_id
                )
            
            # Notify all system admins (except current)
            cursor.execute('''
                SELECT id FROM users 
                WHERE role = "system_admin" 
                AND status = "approved"
                AND id != %s
            ''', (session['user_id'],))
            
            other_admins = dict_fetchall(cursor)
            for admin in other_admins:
                create_notification(
                    admin['id'],
                    f"⚠️ Gate Pass {gate_pass['pass_number']} force returned by {session['name']}",
                    'info',
                    gate_pass_id
                )
        
        return jsonify({
            'success': True, 
            'message': f'Gate Pass {gate_pass["pass_number"]} marked as force returned!'
        })
        
    except Exception as e:
        conn.rollback()
        print(f"Force return error: {e}")
        return jsonify({'success': False, 'message': f'Error: {str(e)}'})
    finally:
        cursor.close()
        conn.close()

@app.route('/check_notifications')
def check_notifications():
    if 'user_id' not in session:
        return jsonify({'new_notifications': 0})
    
    conn = get_db_connection()
    if conn is None:
        return jsonify({'new_notifications': 0})
    
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            SELECT COUNT(*) FROM notifications 
            WHERE user_id = %s AND is_read = FALSE
        ''', (session['user_id'],))
        
        count = cursor.fetchone()[0]
        return jsonify({'new_notifications': count})
        
    except Exception as e:
        print(f"Notification check error: {e}")
        return jsonify({'new_notifications': 0})
    finally:
        cursor.close()
        conn.close()

@app.route('/mark_notification_read/<int:notification_id>', methods=['POST'])
def mark_notification_read(notification_id):
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    
    conn = get_db_connection()
    if conn is None:
        flash('Database connection failed!', 'error')
        return redirect(url_for('dashboard'))
    
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            UPDATE notifications SET is_read = TRUE 
            WHERE id = %s AND user_id = %s
        ''', (notification_id, session['user_id']))
        
        conn.commit()
        flash('Notification marked as read!', 'success')
    except Exception as e:
        conn.rollback()
        flash(f'Error marking notification: {str(e)}', 'error')
    finally:
        cursor.close()
        conn.close()
    
    return redirect(url_for('dashboard'))

@app.route('/mark_all_notifications_read', methods=['POST'])
def mark_all_notifications_read():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    
    conn = get_db_connection()
    if conn is None:
        flash('Database connection failed!', 'error')
        return redirect(url_for('dashboard'))
    
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            UPDATE notifications SET is_read = TRUE 
            WHERE user_id = %s AND is_read = FALSE
        ''', (session['user_id'],))
        
        conn.commit()
        flash('All notifications marked as read!', 'success')
    except Exception as e:
        conn.rollback()
        flash(f'Error marking notifications: {str(e)}', 'error')
    finally:
        cursor.close()
        conn.close()
    
    return redirect(url_for('dashboard'))

@app.route('/upload_photo', methods=['POST'])
def upload_photo():
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Not authenticated'})
    
    try:
        if 'photo' not in request.files:
            return jsonify({'success': False, 'message': 'No photo uploaded'})
        
        photo = request.files['photo']
        if photo.filename == '':
            return jsonify({'success': False, 'message': 'No selected file'})
        
        # Save the photo
        upload_folder = 'static/uploads'
        if not os.path.exists(upload_folder):
            os.makedirs(upload_folder)
        
        filename = f"upload_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{session['user_id']}.jpg"
        filepath = os.path.join(upload_folder, filename)
        photo.save(filepath)
        
        return jsonify({
            'success': True, 
            'message': 'Photo uploaded successfully',
            'filepath': filepath.replace('static/', '')
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/check_camera_support')
def check_camera_support():
    """Check if browser supports camera API"""
    return jsonify({
        'supports_getUserMedia': True,
        'message': 'Camera support check complete'
    })

# Create necessary directories at startup
def setup_directories():
    directories = ['static/uploads', 'static/icons', 'static/js', 'static/css']
    for directory in directories:
        if not os.path.exists(directory):
            os.makedirs(directory, exist_ok=True)
            print(f"✅ Created directory: {directory}")

# Call this at the beginning of your main app
setup_directories()

@app.route('/check_photo_count', methods=['POST'])
def check_photo_count():
    """Check if photos are being sent correctly"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Not logged in'})
    
    try:
        captured_images = request.form.getlist('captured_images[]')
        return jsonify({
            'success': True,
            'photo_count': len(captured_images),
            'message': f'Received {len(captured_images)} photos'
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/notify_gate_pass_printing', methods=['POST'])
def api_notify_gate_pass_printing():
    """API endpoint to notify that gate pass is being printed"""
    if 'user_id' not in session or session['role'] != 'security':
        return jsonify({'success': False, 'message': 'Access denied!'})
    
    data = request.get_json()
    gate_pass_id = data.get('gate_pass_id')
    printed_by = data.get('printed_by')
    printed_by_name = data.get('printed_by_name')
    
    if not gate_pass_id:
        return jsonify({'success': False, 'message': 'Gate pass ID required!'})
    
    # Log the printing start
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor()
        try:
            cursor.execute('''
                INSERT INTO security_logs (gate_pass_id, user_id, alert_type, details)
                VALUES (%s, %s, 'printing_started', %s)
            ''', (gate_pass_id, printed_by, 
                  f'Printing started by security: {printed_by_name}'))
            conn.commit()
        except Exception as e:
            print(f"Error logging print start: {e}")
        finally:
            cursor.close()
            conn.close()
    
    return jsonify({'success': True, 'message': 'Print notification logged'})

@app.route('/api/notify_gate_pass_print_complete', methods=['POST'])
def api_notify_gate_pass_print_complete():
    """API endpoint to notify that gate pass printing is complete"""
    if 'user_id' not in session or session['role'] != 'security':
        return jsonify({'success': False, 'message': 'Access denied!'})
    
    data = request.get_json()
    gate_pass_id = data.get('gate_pass_id')
    printed_by = data.get('printed_by')
    
    if not gate_pass_id:
        return jsonify({'success': False, 'message': 'Gate pass ID required!'})
    
    # Log the printing completion
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor()
        try:
            cursor.execute('''
                INSERT INTO security_logs (gate_pass_id, user_id, alert_type, details)
                VALUES (%s, %s, 'printing_complete', 'Gate pass printed successfully')
            ''', (gate_pass_id, printed_by))
            conn.commit()
        except Exception as e:
            print(f"Error logging print completion: {e}")
        finally:
            cursor.close()
            conn.close()
    
    return jsonify({'success': True, 'message': 'Print completion logged'})

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)