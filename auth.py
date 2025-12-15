# auth.py - UPDATED WITH DUAL APPROVAL SYSTEM
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from models import get_db_connection, hash_password, check_password, dict_fetchone, dict_fetchall
from notifications import create_notification

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        conn = get_db_connection()
        if conn is None:
            flash('Database connection failed!', 'error')
            return render_template('login.html')
        
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                SELECT u.*, d.name as department_name, dv.name as division_name 
                FROM users u 
                LEFT JOIN departments d ON u.department_id = d.id 
                LEFT JOIN divisions dv ON u.division_id = dv.id 
                WHERE u.username = %s
            ''', (username,))
            user = dict_fetchone(cursor)
            
            if user and check_password(user['password'], password):
                # Check if user is approved (either by admin OR dept head)
                if user['status'] != 'approved':
                    if user['approved_by_admin'] or user['approved_by_dept_head']:
                        # Update status to approved if either approved
                        cursor.execute('''
                            UPDATE users 
                            SET status = 'approved' 
                            WHERE id = %s
                        ''', (user['id'],))
                        conn.commit()
                        user['status'] = 'approved'
                    else:
                        flash('Your account is pending approval from either Admin or Department Head!', 'error')
                        return render_template('login.html')
                
                session['user_id'] = user['id']
                session['username'] = user['username']
                session['name'] = user['name']
                session['role'] = user['role']
                session['department'] = user['department_name'] if user['department_name'] else ''
                session['division'] = user['division_name'] if user['division_name'] else ''
                session['designation'] = user['designation']
                
                flash(f'Welcome back, {user["name"]}!', 'success')
                return redirect(url_for('dashboard'))
            else:
                flash('Invalid username or password!', 'error')
                
        except Exception as e:
            flash(f'Login error: {str(e)}', 'error')
        finally:
            cursor.close()
            conn.close()
    
    return render_template('login.html')

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    conn = get_db_connection()
    if conn is None:
        flash('Database connection failed!', 'error')
        return render_template('register.html', divisions=[], departments=[])
    
    cursor = conn.cursor()
    
    # Get divisions and departments for dropdown
    try:
        cursor.execute('SELECT * FROM divisions WHERE status = "active" ORDER BY name')
        divisions = dict_fetchall(cursor)
        
        cursor.execute('''
            SELECT d.*, dv.name as division_name 
            FROM departments d 
            LEFT JOIN divisions dv ON d.division_id = dv.id 
            WHERE d.status = "active" 
            ORDER BY dv.name, d.name
        ''')
        departments = dict_fetchall(cursor)
        
    except Exception as e:
        print(f"Error fetching divisions/departments: {e}")
        divisions = []
        departments = []
    
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        name = request.form['name']
        designation = request.form['designation']
        division_id = request.form.get('division_id', '')
        department_id = request.form.get('department_id', '')
        phone = request.form.get('phone')
        email = request.form.get('email')
        role = 'user'  # Regular users only
        
        # Validation
        if not division_id or not department_id:
            flash('Please select both division and department!', 'error')
            return render_template('register.html', divisions=divisions, departments=departments)
        
        if password != confirm_password:
            flash('Passwords do not match!', 'error')
            return render_template('register.html', divisions=divisions, departments=departments)
        
        if len(password) < 6:
            flash('Password must be at least 6 characters long!', 'error')
            return render_template('register.html', divisions=divisions, departments=departments)
        
        try:
            # Check if username already exists
            cursor.execute('SELECT id FROM users WHERE username = %s', (username,))
            if cursor.fetchone():
                flash('Username already exists!', 'error')
                return render_template('register.html', divisions=divisions, departments=departments)
            
            # Check if selected department belongs to selected division
            cursor.execute('SELECT division_id FROM departments WHERE id = %s', (department_id,))
            dept_result = cursor.fetchone()
            if not dept_result or str(dept_result[0]) != division_id:
                flash('Invalid department for selected division!', 'error')
                return render_template('register.html', divisions=divisions, departments=departments)
            
            # Insert new user with DUAL PENDING status
            hashed_password = hash_password(password)
            cursor.execute('''
                INSERT INTO users (username, password, name, designation, division_id, department_id, phone, email, role, status)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'dual_pending')
            ''', (username, hashed_password, name, designation, division_id, department_id, phone, email, role))
            
            user_id = cursor.lastrowid
            
            # Get ALL System Administrators for notification
            cursor.execute('SELECT id, name FROM users WHERE role = "system_admin" AND status = "approved"')
            admins = dict_fetchall(cursor)
            
            # Get Department Head for the selected department
            cursor.execute('''
                SELECT u.id, u.name 
                FROM users u 
                WHERE u.department_id = %s AND u.role = 'department_head' AND u.status = 'approved'
            ''', (department_id,))
            
            dept_heads = dict_fetchall(cursor)
            
            # Notify ALL System Administrators
            for admin in admins:
                create_notification(
                    admin['id'],
                    f"📋 NEW USER REGISTRATION (Admin Approval): {name} ({username}) wants to join as {designation}. Please review in User Management.",
                    'approval',
                    user_id
                )
            
            # Notify Department Head (if exists)
            if dept_heads:
                for dept_head in dept_heads:
                    create_notification(
                        dept_head['id'],
                        f"📋 NEW USER REGISTRATION (Dept Head Approval): {name} ({username}) wants to join as {designation} in your department. Please review in Pending Approvals.",
                        'approval',
                        user_id
                    )
            else:
                # If no department head, user will be approved by admin only
                create_notification(
                    user_id,
                    f"📝 Your registration is pending Admin approval (No Department Head found in your department).",
                    'status',
                    None
                )
            
            conn.commit()
            flash('Registration successful! Your account is pending approval from either Admin or Department Head. You will be notified once approved.', 'success')
            return redirect(url_for('auth.login'))
            
        except Exception as e:
            conn.rollback()
            flash(f'Registration error: {str(e)}', 'error')
            print(f"Registration error: {e}")
        finally:
            cursor.close()
            conn.close()
    
    cursor.close()
    conn.close()
    
    return render_template('register.html', divisions=divisions, departments=departments)

@auth_bp.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out successfully!', 'success')
    return redirect(url_for('auth.login'))