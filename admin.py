# admin.py - UPDATED WITH NEW USER MANAGEMENT SYSTEM
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from models import get_db_connection, dict_fetchall, dict_fetchone, hash_password
from notifications import create_notification
import MySQLdb
from datetime import datetime

admin_bp = Blueprint('admin', __name__)

@admin_bp.route('/divisions', methods=['GET', 'POST'])
def manage_divisions():
    if 'user_id' not in session or session['role'] != 'system_admin':
        flash('Access denied! Only System Admin can manage divisions.', 'error')
        return redirect(url_for('dashboard'))
    
    conn = get_db_connection()
    if conn is None:
        flash('Database connection failed!', 'error')
        return render_template('admin/divisions.html', divisions=[])
    
    cursor = conn.cursor()
    
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'create':
            division_name = request.form['name']
            description = request.form.get('description', '')
            
            try:
                cursor.execute('INSERT INTO divisions (name, description, created_by) VALUES (%s, %s, %s)',
                             (division_name, description, session['user_id']))
                conn.commit()
                flash('Division created successfully!', 'success')
            except MySQLdb.IntegrityError:
                conn.rollback()
                flash('Division already exists!', 'error')
            except Exception as e:
                conn.rollback()
                flash(f'Error creating division: {str(e)}', 'error')
        
        elif action == 'update':
            division_id = request.form['id']
            division_name = request.form['name']
            description = request.form.get('description', '')
            
            try:
                cursor.execute('''
                    UPDATE divisions 
                    SET name = %s, description = %s 
                    WHERE id = %s
                ''', (division_name, description, division_id))
                conn.commit()
                flash('Division updated successfully!', 'success')
            except MySQLdb.IntegrityError:
                conn.rollback()
                flash('Division name already exists!', 'error')
            except Exception as e:
                conn.rollback()
                flash(f'Error updating division: {str(e)}', 'error')
        
        elif action == 'delete':
            division_id = request.form['id']
            
            try:
                cursor.execute('SELECT COUNT(*) FROM departments WHERE division_id = %s', (division_id,))
                if cursor.fetchone()[0] > 0:
                    flash('Cannot delete division with existing departments!', 'error')
                else:
                    cursor.execute('DELETE FROM divisions WHERE id = %s', (division_id,))
                    conn.commit()
                    flash('Division deleted successfully!', 'success')
            except Exception as e:
                conn.rollback()
                flash(f'Error deleting division: {str(e)}', 'error')
        
        return redirect(url_for('admin.manage_divisions'))
    
    try:
        cursor.execute('SELECT * FROM divisions ORDER BY name')
        divisions = dict_fetchall(cursor)
    except Exception as e:
        print(f"Error fetching divisions: {e}")
        divisions = []
    finally:
        cursor.close()
        conn.close()
    
    return render_template('admin/divisions.html', divisions=divisions)

@admin_bp.route('/departments', methods=['GET', 'POST'])
def manage_departments():
    if 'user_id' not in session or session['role'] != 'system_admin':
        flash('Access denied! Only System Admin can manage departments.', 'error')
        return redirect(url_for('dashboard'))
    
    conn = get_db_connection()
    if conn is None:
        flash('Database connection failed!', 'error')
        return render_template('admin/departments.html', departments=[], divisions=[])
    
    cursor = conn.cursor()
    
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'create':
            division_id = request.form['division_id']
            dept_name = request.form['name']
            description = request.form.get('description', '')
            
            try:
                cursor.execute('''
                    INSERT INTO departments (name, division_id, description, created_by) 
                    VALUES (%s, %s, %s, %s)
                ''', (dept_name, division_id, description, session['user_id']))
                conn.commit()
                flash('Department created successfully!', 'success')
            except MySQLdb.IntegrityError:
                conn.rollback()
                flash('Department already exists in this division!', 'error')
            except Exception as e:
                conn.rollback()
                flash(f'Error creating department: {str(e)}', 'error')
        
        elif action == 'update':
            dept_id = request.form['id']
            division_id = request.form['division_id']
            dept_name = request.form['name']
            description = request.form.get('description', '')
            
            try:
                cursor.execute('''
                    UPDATE departments 
                    SET name = %s, division_id = %s, description = %s 
                    WHERE id = %s
                ''', (dept_name, division_id, description, dept_id))
                conn.commit()
                flash('Department updated successfully!', 'success')
            except MySQLdb.IntegrityError:
                conn.rollback()
                flash('Department name already exists in this division!', 'error')
            except Exception as e:
                conn.rollback()
                flash(f'Error updating department: {str(e)}', 'error')
        
        elif action == 'delete':
            dept_id = request.form['id']
            
            try:
                cursor.execute('SELECT COUNT(*) FROM users WHERE department_id = %s', (dept_id,))
                if cursor.fetchone()[0] > 0:
                    flash('Cannot delete department with existing users!', 'error')
                else:
                    cursor.execute('DELETE FROM departments WHERE id = %s', (dept_id,))
                    conn.commit()
                    flash('Department deleted successfully!', 'success')
            except Exception as e:
                conn.rollback()
                flash(f'Error deleting department: {str(e)}', 'error')
        
        return redirect(url_for('admin.manage_departments'))
    
    try:
        cursor.execute('SELECT d.*, dv.name as division_name FROM departments d JOIN divisions dv ON d.division_id = dv.id ORDER BY dv.name, d.name')
        departments = dict_fetchall(cursor)
        
        cursor.execute('SELECT * FROM divisions ORDER BY name')
        divisions = dict_fetchall(cursor)
    except Exception as e:
        print(f"Error fetching departments: {e}")
        departments = []
        divisions = []
    finally:
        cursor.close()
        conn.close()
    
    return render_template('admin/departments.html', departments=departments, divisions=divisions)

@admin_bp.route('/all_users')
def all_users():
    if 'user_id' not in session or session['role'] != 'system_admin':
        flash('Access denied! Only System Admin can view all users.', 'error')
        return redirect(url_for('dashboard'))
    
    conn = get_db_connection()
    if conn is None:
        flash('Database connection failed!', 'error')
        return render_template('admin/all_users.html', users=[], divisions=[], departments=[])
    
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            SELECT u.*, d.name as department_name, dv.name as division_name 
            FROM users u 
            LEFT JOIN departments d ON u.department_id = d.id 
            LEFT JOIN divisions dv ON u.division_id = dv.id 
            ORDER BY 
                CASE 
                    WHEN u.status = 'dual_pending' THEN 1
                    WHEN u.status = 'pending_admin' THEN 2
                    WHEN u.status = 'pending_dept' THEN 3
                    WHEN u.status = 'approved' THEN 4
                    ELSE 5
                END,
                u.name
        ''')
        users = dict_fetchall(cursor)
        
        cursor.execute('SELECT * FROM divisions ORDER BY name')
        divisions = dict_fetchall(cursor)
        
        cursor.execute('SELECT * FROM departments ORDER BY name')
        departments = dict_fetchall(cursor)
    except Exception as e:
        print(f"Error fetching users: {e}")
        users = []
        divisions = []
        departments = []
    finally:
        cursor.close()
        conn.close()
    
    return render_template('admin/all_users.html', users=users, divisions=divisions, departments=departments)

@admin_bp.route('/create_user', methods=['POST'])
def create_user():
    if 'user_id' not in session or session['role'] != 'system_admin':
        return jsonify({'success': False, 'message': 'Access denied!'})
    
    username = request.form['username']
    password = request.form['password']
    name = request.form['name']
    designation = request.form['designation']
    department_id = request.form['department_id']
    role = request.form['role']
    phone = request.form.get('phone')
    email = request.form.get('email')
    
    conn = get_db_connection()
    if conn is None:
        return jsonify({'success': False, 'message': 'Database connection failed!'})
    
    cursor = conn.cursor()
    
    try:
        # Get division_id from department
        cursor.execute('SELECT division_id FROM departments WHERE id = %s', (department_id,))
        division = cursor.fetchone()
        if not division:
            return jsonify({'success': False, 'message': 'Invalid department!'})
        
        division_id = division[0]
        
        # Check if username exists
        cursor.execute('SELECT id FROM users WHERE username = %s', (username,))
        if cursor.fetchone():
            return jsonify({'success': False, 'message': 'Username already exists!'})
        
        hashed_password = hash_password(password)
        
        # Auto-approve admin created users
        status = 'approved'
        approved_by_admin = True
        approved_by_dept_head = True
        
        cursor.execute('''
            INSERT INTO users (username, password, name, designation, division_id, department_id, 
                             phone, email, role, status, approved_by_admin, approved_by_dept_head, created_by)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ''', (username, hashed_password, name, designation, division_id, department_id, 
              phone, email, role, status, approved_by_admin, approved_by_dept_head, session['user_id']))
        
        user_id = cursor.lastrowid
        
        # If user is department head, notify them
        if role == 'department_head':
            create_notification(
                user_id,
                f"🎉 You have been assigned as Department Head by System Administrator",
                'status',
                None
            )
        
        conn.commit()
        return jsonify({'success': True, 'message': 'User created successfully!'})
        
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'message': f'Error creating user: {str(e)}'})
    finally:
        cursor.close()
        conn.close()

@admin_bp.route('/update_user/<int:user_id>', methods=['POST'])
def update_user(user_id):
    if 'user_id' not in session or session['role'] != 'system_admin':
        return jsonify({'success': False, 'message': 'Access denied!'})
    
    name = request.form['name']
    designation = request.form['designation']
    department_id = request.form['department_id']
    role = request.form['role']
    status = request.form['status']
    phone = request.form.get('phone')
    email = request.form.get('email')
    
    conn = get_db_connection()
    if conn is None:
        return jsonify({'success': False, 'message': 'Database connection failed!'})
    
    cursor = conn.cursor()
    
    try:
        # Get division_id from department
        cursor.execute('SELECT division_id FROM departments WHERE id = %s', (department_id,))
        division = cursor.fetchone()
        if not division:
            return jsonify({'success': False, 'message': 'Invalid department!'})
        
        division_id = division[0]
        
        # Get current user data
        cursor.execute('SELECT role, status FROM users WHERE id = %s', (user_id,))
        current_user = cursor.fetchone()
        
        cursor.execute('''
            UPDATE users 
            SET name = %s, designation = %s, division_id = %s, department_id = %s, 
                role = %s, status = %s, phone = %s, email = %s
            WHERE id = %s
        ''', (name, designation, division_id, department_id, role, status, phone, email, user_id))
        
        conn.commit()
        
        # Notify user if status changed to approved
        if status == 'approved' and current_user and current_user[1] != 'approved':
            create_notification(
                user_id,
                f"🎉 Your account has been approved by System Administrator!",
                'status',
                None
            )
        
        # If role changed to department head
        if role == 'department_head' and current_user and current_user[0] != 'department_head':
            create_notification(
                user_id,
                f"📢 You have been promoted to Department Head by System Administrator!",
                'status',
                None
            )
        
        return jsonify({'success': True, 'message': 'User updated successfully!'})
        
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'message': f'Error updating user: {str(e)}'})
    finally:
        cursor.close()
        conn.close()

@admin_bp.route('/delete_user/<int:user_id>', methods=['POST'])
def delete_user(user_id):
    if 'user_id' not in session or session['role'] != 'system_admin':
        return jsonify({'success': False, 'message': 'Access denied!'})
    
    conn = get_db_connection()
    if conn is None:
        return jsonify({'success': False, 'message': 'Database connection failed!'})
    
    cursor = conn.cursor()
    
    try:
        # Check if user has created gate passes
        cursor.execute('SELECT COUNT(*) FROM gate_passes WHERE created_by = %s', (user_id,))
        if cursor.fetchone()[0] > 0:
            return jsonify({'success': False, 'message': 'Cannot delete user with existing gate passes!'})
        
        cursor.execute('DELETE FROM users WHERE id = %s', (user_id,))
        conn.commit()
        
        return jsonify({'success': True, 'message': 'User deleted successfully!'})
        
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'message': f'Error deleting user: {str(e)}'})
    finally:
        cursor.close()
        conn.close()

@admin_bp.route('/approve_user/<int:user_id>/<action>', methods=['GET', 'POST'])
def approve_user(user_id, action):
    """Approve or reject user (can be called by Admin OR Department Head)"""
    if 'user_id' not in session or session['role'] not in ['system_admin', 'department_head']:
        return jsonify({'success': False, 'message': 'Access denied!'})
    
    conn = get_db_connection()
    if conn is None:
        return jsonify({'success': False, 'message': 'Database connection failed!'})
    
    cursor = conn.cursor()
    
    try:
        # Get user details
        cursor.execute('''
            SELECT u.*, d.name as department_name 
            FROM users u 
            LEFT JOIN departments d ON u.department_id = d.id 
            WHERE u.id = %s
        ''', (user_id,))
        user = dict_fetchone(cursor)
        
        if not user:
            return jsonify({'success': False, 'message': 'User not found!'})
        
        # Check permissions
        if session['role'] == 'department_head':
            # Department head can only approve users from their department
            if user['department_name'] != session['department']:
                return jsonify({'success': False, 'message': 'You can only approve users from your department!'})
        
        if action == 'approve':
            # Update approval based on who is approving
            if session['role'] == 'system_admin':
                cursor.execute('''
                    UPDATE users 
                    SET approved_by_admin = TRUE,
                        status = CASE 
                            WHEN approved_by_dept_head = TRUE THEN 'approved'
                            ELSE 'pending_dept'
                        END
                    WHERE id = %s
                ''', (user_id,))
                
                # Notify user
                create_notification(
                    user_id,
                    f"✅ Your account has been approved by System Administrator!" + 
                    (" Waiting for Department Head approval." if not user['approved_by_dept_head'] else ""),
                    'status',
                    None
                )
                
                message = 'User approved by Admin!' + (" Waiting for Department Head approval." if not user['approved_by_dept_head'] else "")
                
            elif session['role'] == 'department_head':
                cursor.execute('''
                    UPDATE users 
                    SET approved_by_dept_head = TRUE,
                        status = CASE 
                            WHEN approved_by_admin = TRUE THEN 'approved'
                            ELSE 'pending_admin'
                        END
                    WHERE id = %s
                ''', (user_id,))
                
                # Notify user
                create_notification(
                    user_id,
                    f"✅ Your account has been approved by Department Head!" + 
                    (" Waiting for Admin approval." if not user['approved_by_admin'] else ""),
                    'status',
                    None
                )
                
                message = 'User approved by Department Head!' + (" Waiting for Admin approval." if not user['approved_by_admin'] else "")
            
            # Check if both approvals are done
            cursor.execute('SELECT approved_by_admin, approved_by_dept_head FROM users WHERE id = %s', (user_id,))
            approvals = cursor.fetchone()
            
            if approvals[0] and approvals[1]:
                cursor.execute('''
                    UPDATE users 
                    SET status = 'approved' 
                    WHERE id = %s
                ''', (user_id,))
                
                create_notification(
                    user_id,
                    f"🎉 Congratulations! Your account has been fully approved. You can now login!",
                    'status',
                    None
                )
                
                message = 'User fully approved and can now login!'
        
        elif action == 'reject':
            if session['role'] == 'system_admin':
                cursor.execute('''
                    UPDATE users 
                    SET status = 'rejected', 
                        approved_by_admin = FALSE 
                    WHERE id = %s
                ''', (user_id,))
            elif session['role'] == 'department_head':
                cursor.execute('''
                    UPDATE users 
                    SET status = 'rejected', 
                        approved_by_dept_head = FALSE 
                    WHERE id = %s
                ''', (user_id,))
            
            create_notification(
                user_id,
                f"❌ Your account registration has been rejected by {session['role'].replace('_', ' ').title()}.",
                'status',
                None
            )
            
            message = f'User rejected by {session["role"].replace("_", " ").title()}!'
        
        else:
            return jsonify({'success': False, 'message': 'Invalid action!'})
        
        conn.commit()
        return jsonify({'success': True, 'message': message})
        
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'message': f'Error processing user: {str(e)}'})
    finally:
        cursor.close()
        conn.close()

@admin_bp.route('/all_gate_passes')
def all_gate_passes():
    if 'user_id' not in session or session['role'] != 'system_admin':
        flash('Access denied! Only System Admin can view all gate passes.', 'error')
        return redirect(url_for('dashboard'))
    
    conn = get_db_connection()
    if conn is None:
        flash('Database connection failed!', 'error')
        return render_template('admin/all_gate_passes.html', gate_passes=[])
    
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            SELECT gp.*, u.name as creator_name, d.name as department_name, dv.name as division_name
            FROM gate_passes gp 
            JOIN users u ON gp.created_by = u.id 
            JOIN departments d ON gp.department_id = d.id 
            JOIN divisions dv ON gp.division_id = dv.id 
            ORDER BY gp.created_at DESC
        ''')
        gate_passes = dict_fetchall(cursor)
    except Exception as e:
        print(f"Error fetching gate passes: {e}")
        gate_passes = []
    finally:
        cursor.close()
        conn.close()
    
    return render_template('admin/all_gate_passes.html', gate_passes=gate_passes)

@admin_bp.route('/approve_gate_pass/<int:gate_pass_id>', methods=['POST'])
def approve_gate_pass_admin(gate_pass_id):
    if 'user_id' not in session or session['role'] != 'system_admin':
        return jsonify({'success': False, 'message': 'Access denied!'})
    
    action = request.form.get('action')
    store_location = request.form.get('store_location', 'store_1')
    
    conn = get_db_connection()
    if conn is None:
        return jsonify({'success': False, 'message': 'Database connection failed!'})
    
    cursor = conn.cursor()
    
    try:
        if action == 'approve':
            cursor.execute('''
                UPDATE gate_passes 
                SET status = 'approved', security_approval = 'approved',
                    security_approval_date = %s, store_location = %s
                WHERE id = %s
            ''', (datetime.now(), store_location, gate_pass_id))
            
            cursor.execute('SELECT created_by, pass_number FROM gate_passes WHERE id = %s', (gate_pass_id,))
            result = cursor.fetchone()
            if result:
                create_notification(
                    result[0],
                    f"Gate Pass {result[1]} has been approved by System Administrator!",
                    'status',
                    gate_pass_id
                )
            
            message = 'Gate Pass approved!'
            
        elif action == 'reject':
            cursor.execute('''
                UPDATE gate_passes 
                SET status = 'rejected', security_approval = 'rejected'
                WHERE id = %s
            ''', (gate_pass_id,))
            
            cursor.execute('SELECT created_by, pass_number FROM gate_passes WHERE id = %s', (gate_pass_id,))
            result = cursor.fetchone()
            if result:
                create_notification(
                    result[0],
                    f"Gate Pass {result[1]} has been rejected by System Administrator",
                    'status',
                    gate_pass_id
                )
            
            message = 'Gate Pass rejected!'
        
        elif action == 'edit':
            material_description = request.form['material_description']
            destination = request.form['destination']
            purpose = request.form['purpose']
            receiver_name = request.form['receiver_name']
            
            cursor.execute('''
                UPDATE gate_passes 
                SET material_description = %s, destination = %s, 
                    purpose = %s, receiver_name = %s
                WHERE id = %s
            ''', (material_description, destination, purpose, receiver_name, gate_pass_id))
            
            message = 'Gate Pass updated successfully!'
        
        else:
            return jsonify({'success': False, 'message': 'Invalid action!'})
        
        conn.commit()
        return jsonify({'success': True, 'message': message})
        
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'message': f'Error processing gate pass: {str(e)}'})
    finally:
        cursor.close()
        conn.close()

@admin_bp.route('/delete_gate_pass/<int:gate_pass_id>', methods=['POST'])
def delete_gate_pass(gate_pass_id):
    if 'user_id' not in session or session['role'] != 'system_admin':
        return jsonify({'success': False, 'message': 'Access denied!'})
    
    conn = get_db_connection()
    if conn is None:
        return jsonify({'success': False, 'message': 'Database connection failed!'})
    
    cursor = conn.cursor()
    
    try:
        cursor.execute('DELETE FROM gate_passes WHERE id = %s', (gate_pass_id,))
        conn.commit()
        
        return jsonify({'success': True, 'message': 'Gate Pass deleted successfully!'})
        
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'message': f'Error deleting gate pass: {str(e)}'})
    finally:
        cursor.close()
        conn.close()

@admin_bp.route('/store_requests')
def store_requests():
    if 'user_id' not in session or session['role'] != 'system_admin':
        flash('Access denied! Only System Admin can view store requests.', 'error')
        return redirect(url_for('dashboard'))
    
    conn = get_db_connection()
    if conn is None:
        flash('Database connection failed!', 'error')
        return render_template('admin/store_requests.html', requests=[])
    
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            SELECT sr.*, u.name as security_name 
            FROM store_requests sr 
            JOIN users u ON sr.security_user_id = u.id 
            WHERE sr.status = 'pending'
            ORDER BY sr.created_at DESC
        ''')
        requests = dict_fetchall(cursor)
    except Exception as e:
        print(f"Error fetching store requests: {e}")
        requests = []
    finally:
        cursor.close()
        conn.close()
    
    return render_template('admin/store_requests.html', requests=requests)

@admin_bp.route('/process_store_request/<int:request_id>', methods=['POST'])
def process_store_request(request_id):
    if 'user_id' not in session or session['role'] != 'system_admin':
        return jsonify({'success': False, 'message': 'Access denied!'})
    
    action = request.form.get('action')
    
    conn = get_db_connection()
    if conn is None:
        return jsonify({'success': False, 'message': 'Database connection failed!'})
    
    cursor = conn.cursor()
    
    try:
        if action == 'approve':
            cursor.execute('''
                SELECT material_description, destination, purpose, receiver_name, receiver_contact, security_user_id 
                FROM store_requests WHERE id = %s
            ''', (request_id,))
            request_data = cursor.fetchone()
            
            if not request_data:
                return jsonify({'success': False, 'message': 'Request not found!'})
            
            pass_number = f"GP{datetime.now().strftime('%Y%m%d%H%M%S')}"
            
            cursor.execute('''
                INSERT INTO gate_passes (
                    pass_number, created_by, division_id, department_id,
                    material_description, destination, purpose, 
                    material_type, material_status, receiver_name, 
                    receiver_contact, send_date, images, status
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, 'non_returnable', 'new', %s, %s, %s, '[]', 'approved')
            ''', (
                pass_number, session['user_id'], 1, 1,
                request_data[0], request_data[1], request_data[2],
                request_data[3], request_data[4], datetime.now()
            ))
            
            gate_pass_id = cursor.lastrowid
            
            cursor.execute('''
                UPDATE store_requests 
                SET status = 'approved', admin_id = %s, gate_pass_id = %s
                WHERE id = %s
            ''', (session['user_id'], gate_pass_id, request_id))
            
            create_notification(
                request_data[5],
                f"✅ Your store request has been approved! Gate Pass #{pass_number} created.",
                'status',
                gate_pass_id
            )
            
            message = 'Store request approved and gate pass created!'
            
        elif action == 'reject':
            cursor.execute('''
                UPDATE store_requests 
                SET status = 'rejected', admin_id = %s
                WHERE id = %s
            ''', (session['user_id'], request_id))
            
            cursor.execute('SELECT security_user_id FROM store_requests WHERE id = %s', (request_id,))
            security_id = cursor.fetchone()[0]
            
            create_notification(
                security_id,
                f"❌ Your store request has been rejected by System Administrator.",
                'status',
                None
            )
            
            message = 'Store request rejected!'
        
        else:
            return jsonify({'success': False, 'message': 'Invalid action!'})
        
        conn.commit()
        return jsonify({'success': True, 'message': message})
        
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'message': f'Error processing request: {str(e)}'})
    finally:
        cursor.close()
        conn.close()