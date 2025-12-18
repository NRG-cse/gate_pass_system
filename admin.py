# admin.py - UPDATED WITH SUPER ADMIN ROLE ASSIGNMENT
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
        return render_template('admin/divisions.html', divisions=[], total_departments=0, total_users=0)
    
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
            status = request.form.get('status', 'active')
            
            try:
                cursor.execute('''
                    UPDATE divisions 
                    SET name = %s, description = %s, status = %s 
                    WHERE id = %s
                ''', (division_name, description, status, division_id))
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
                # Check if division has departments
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
        # Get divisions with department count
        cursor.execute('''
            SELECT d.*, 
                   (SELECT COUNT(*) FROM departments WHERE division_id = d.id) as department_count
            FROM divisions d 
            ORDER BY d.name
        ''')
        divisions = dict_fetchall(cursor)
        
        # Get total departments count
        cursor.execute('SELECT COUNT(*) FROM departments')
        total_departments = cursor.fetchone()[0]
        
        # Get total users count
        cursor.execute('SELECT COUNT(*) FROM users')
        total_users = cursor.fetchone()[0]
        
    except Exception as e:
        print(f"Error fetching divisions: {e}")
        divisions = []
        total_departments = 0
        total_users = 0
    finally:
        cursor.close()
        conn.close()
    
    return render_template('admin/divisions.html', 
                         divisions=divisions, 
                         total_departments=total_departments,
                         total_users=total_users)

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
                # Check if department has users
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
    
    return render_template('admin/departments.html', 
                         departments=departments, 
                         divisions=divisions,
                         now=datetime.now())

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
            ORDER BY u.role, u.name
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

# Add this route to your admin.py file

@admin_bp.route('/get_user/<int:user_id>')
def get_user(user_id):
    """Get user details for editing (AJAX endpoint)"""
    if 'user_id' not in session or session['role'] != 'system_admin':
        return jsonify({'success': False, 'message': 'Access denied!'})
    
    conn = get_db_connection()
    if conn is None:
        return jsonify({'success': False, 'message': 'Database connection failed!'})
    
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            SELECT u.*, d.name as department_name, dv.name as division_name
            FROM users u 
            LEFT JOIN departments d ON u.department_id = d.id 
            LEFT JOIN divisions dv ON u.division_id = dv.id 
            WHERE u.id = %s
        ''', (user_id,))
        user = dict_fetchone(cursor)
        
        if user:
            return jsonify({'success': True, 'user': user})
        else:
            return jsonify({'success': False, 'message': 'User not found!'})
            
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error fetching user: {str(e)}'})


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
    
    # NEW: Allow Super Admin to assign any role including department_head
    allowed_roles = ['user', 'department_head', 'store_manager', 'security', 'system_admin']
    if role not in allowed_roles:
        return jsonify({'success': False, 'message': 'Invalid role selected!'})
    
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
        
        # If role is system_admin, status is approved immediately
        # For other roles, status depends on if department_head exists
        status = 'approved' if role == 'system_admin' else 'pending'
        
        cursor.execute('''
            INSERT INTO users (username, password, name, designation, division_id, department_id, 
                             phone, email, role, status, created_by)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ''', (username, hashed_password, name, designation, division_id, department_id, 
              phone, email, role, status, session['user_id']))
        
        user_id = cursor.lastrowid
        
        # NEW: Send notification to both Super Admin and Department Head (if applicable)
        if role != 'system_admin':
            # Notify Super Admin about new user
            cursor.execute('SELECT id FROM users WHERE role = "system_admin" AND status = "approved"')
            admins = dict_fetchall(cursor)
            for admin in admins:
                create_notification(
                    admin['id'],
                    f"👤 NEW USER CREATED: {name} ({username}) as {role.replace('_', ' ').title()}",
                    'approval',
                    user_id
                )
            
            # If role is department_head, also notify existing department heads
            if role == 'department_head':
                cursor.execute('''
                    SELECT u.id FROM users u 
                    WHERE u.department_id = %s AND u.role = "department_head" AND u.status = "approved"
                ''', (department_id,))
                existing_dept_heads = dict_fetchall(cursor)
                for dept_head in existing_dept_heads:
                    create_notification(
                        dept_head['id'],
                        f"🎖️ NEW DEPARTMENT HEAD: {name} assigned as Department Head for your department",
                        'status',
                        user_id
                    )
        
        conn.commit()
        
        return jsonify({'success': True, 'message': f'User created successfully! Status: {status}'})
        
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
    
    # NEW: Allow Super Admin to assign any role
    allowed_roles = ['user', 'department_head', 'store_manager', 'security', 'system_admin']
    if role not in allowed_roles:
        return jsonify({'success': False, 'message': 'Invalid role selected!'})
    
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
        
        # Get current user role to check if it's changing
        cursor.execute('SELECT role FROM users WHERE id = %s', (user_id,))
        current_role = cursor.fetchone()[0]
        
        cursor.execute('''
            UPDATE users 
            SET name = %s, designation = %s, division_id = %s, department_id = %s, 
                role = %s, status = %s, phone = %s, email = %s
            WHERE id = %s
        ''', (name, designation, division_id, department_id, role, status, phone, email, user_id))
        
        conn.commit()
        
        # Notify user if status changed
        if status == 'approved':
            create_notification(
                user_id,
                f"🎉 Your account has been approved by System Administrator!",
                'status',
                None
            )
        
        # If role changed to department_head, notify department
        if current_role != role and role == 'department_head':
            cursor.execute('''
                SELECT u.id FROM users u 
                WHERE u.department_id = %s AND u.id != %s AND u.status = "approved"
            ''', (department_id, user_id))
            dept_users = dict_fetchall(cursor)
            for user in dept_users:
                create_notification(
                    user['id'],
                    f"🎖️ {name} has been assigned as your new Department Head",
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
            
            # Notify creator
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
            
            # Notify creator
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
            # Get request details
            cursor.execute('''
                SELECT material_description, destination, purpose, receiver_name, receiver_contact, security_user_id 
                FROM store_requests WHERE id = %s
            ''', (request_id,))
            request_data = cursor.fetchone()
            
            if not request_data:
                return jsonify({'success': False, 'message': 'Request not found!'})
            
            # Create gate pass for security
            pass_number = f"GP{datetime.now().strftime('%Y%m%d%H%M%S')}"
            
            cursor.execute('''
                INSERT INTO gate_passes (
                    pass_number, created_by, division_id, department_id,
                    material_description, destination, purpose, 
                    material_type, material_status, receiver_name, 
                    receiver_contact, send_date, images, status
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, 'non_returnable', 'new', %s, %s, %s, '[]', 'approved')
            ''', (
                pass_number, session['user_id'], 1, 1,  # Using default division/department
                request_data[0], request_data[1], request_data[2],
                request_data[3], request_data[4], datetime.now()
            ))
            
            gate_pass_id = cursor.lastrowid
            
            # Update request status
            cursor.execute('''
                UPDATE store_requests 
                SET status = 'approved', admin_id = %s, gate_pass_id = %s
                WHERE id = %s
            ''', (session['user_id'], gate_pass_id, request_id))
            
            # Notify security user
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
            
            # Notify security user
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

@admin_bp.route('/toggle_division_status/<int:division_id>', methods=['POST'])
def toggle_division_status(division_id):
    if 'user_id' not in session or session['role'] != 'system_admin':
        return jsonify({'success': False, 'message': 'Access denied!'})
    
    data = request.get_json()
    new_status = data.get('status')
    
    conn = get_db_connection()
    if conn is None:
        return jsonify({'success': False, 'message': 'Database connection failed!'})
    
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            UPDATE divisions SET status = %s WHERE id = %s
        ''', (new_status, division_id))
        
        conn.commit()
        return jsonify({'success': True, 'message': f'Division status updated to {new_status}!'})
        
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'message': f'Error updating status: {str(e)}'})
    finally:
        cursor.close()
        conn.close()

@admin_bp.route('/delete_division/<int:division_id>', methods=['POST'])
def delete_division_ajax(division_id):
    if 'user_id' not in session or session['role'] != 'system_admin':
        return jsonify({'success': False, 'message': 'Access denied!'})
    
    conn = get_db_connection()
    if conn is None:
        return jsonify({'success': False, 'message': 'Database connection failed!'})
    
    cursor = conn.cursor()
    
    try:
        # Check if division has departments
        cursor.execute('SELECT COUNT(*) FROM departments WHERE division_id = %s', (division_id,))
        if cursor.fetchone()[0] > 0:
            return jsonify({'success': False, 'message': 'Cannot delete division with existing departments!'})
        
        cursor.execute('DELETE FROM divisions WHERE id = %s', (division_id,))
        conn.commit()
        
        return jsonify({'success': True, 'message': 'Division deleted successfully!'})
        
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'message': f'Error deleting division: {str(e)}'})
    finally:
        cursor.close()
        conn.close()