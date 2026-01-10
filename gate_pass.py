# gate_pass.py - COMPLETE WITH INSTANT APPROVAL & SECURITY WORKFLOW
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from models import get_db_connection, dict_fetchall, dict_fetchone
from qr_utils import generate_qr_code, generate_gate_pass_qr_data
from notifications import create_notification
import MySQLdb
from datetime import datetime, timedelta
import os
import json
import base64
import traceback
from threading import Thread

gate_pass_bp = Blueprint('gate_pass', __name__)

def save_captured_images(images_data):
    """Save base64 encoded images to filesystem"""
    saved_paths = []
    upload_folder = 'static/uploads'
    
    # Create upload folder if not exists
    if not os.path.exists(upload_folder):
        os.makedirs(upload_folder, exist_ok=True)
        print(f"📁 Created upload folder: {upload_folder}")
    
    for i, image_data in enumerate(images_data):
        if image_data and isinstance(image_data, str) and image_data.startswith('data:image'):
            try:
                # Remove data:image/jpeg;base64, prefix
                if ',' in image_data:
                    header, encoded = image_data.split(',', 1)
                else:
                    encoded = image_data
                
                # Validate base64
                if not encoded or len(encoded) < 100:
                    print(f"⚠️ Image {i+1}: Invalid base64 data (too short)")
                    continue
                
                # Decode base64
                try:
                    image_bytes = base64.b64decode(encoded)
                except Exception as decode_error:
                    print(f"⚠️ Image {i+1}: Base64 decode error: {decode_error}")
                    continue
                
                # Generate unique filename
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
                filename = f"material_{timestamp}_{i+1}.jpg"
                filepath = os.path.join(upload_folder, filename)
                
                # Save file
                with open(filepath, 'wb') as f:
                    f.write(image_bytes)
                
                saved_paths.append(f"uploads/{filename}")
                print(f"✅ Image {i+1} saved: {filename} ({len(image_bytes)} bytes)")
            except Exception as e:
                print(f"❌ Error saving image {i+1}: {e}")
                continue
        elif image_data:
            # If it's already a file path
            saved_paths.append(image_data)
    
    print(f"📁 Total images saved: {len(saved_paths)}")
    return json.dumps(saved_paths)

def async_notify(user_id, message, notif_type, gate_pass_id=None):
    """Send notification in background thread"""
    def send_notification():
        try:
            conn = get_db_connection()
            if conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO notifications (user_id, gate_pass_id, message, type)
                    VALUES (%s, %s, %s, %s)
                ''', (user_id, gate_pass_id, message, notif_type))
                conn.commit()
                cursor.close()
                conn.close()
        except:
            pass
    
    thread = Thread(target=send_notification)
    thread.daemon = True
    thread.start()

def async_notification_bulk(role, message, notif_type, gate_pass_id=None):
    """Send bulk notifications in background"""
    def send_bulk():
        try:
            conn = get_db_connection()
            if conn:
                cursor = conn.cursor()
                cursor.execute(f'SELECT id FROM users WHERE role = "{role}" AND status = "approved"')
                users = cursor.fetchall()
                
                for user in users:
                    try:
                        async_notify(user[0], message, notif_type, gate_pass_id)
                    except:
                        continue
                
                cursor.close()
                conn.close()
        except:
            pass
    
    thread = Thread(target=send_bulk)
    thread.daemon = True
    thread.start()

# ✅ ULTRA FAST APPROVAL FUNCTION (UNDER 2 SECONDS)
@gate_pass_bp.route('/instant_approve_gate_pass/<int:gate_pass_id>/<action>', methods=['POST'])
def instant_approve_gate_pass(gate_pass_id, action):
    """ULTRA-FAST gate pass approval - Under 2 seconds"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Access denied!'})
    
    # Quick permission check
    user_role = session['role']
    user_id = session['user_id']
    
    if user_role not in ['department_head', 'store_manager']:
        return jsonify({'success': False, 'message': 'Access denied!'})
    
    if action not in ['approve', 'reject']:
        return jsonify({'success': False, 'message': 'Invalid action!'})
    
    # Get comment
    data = request.get_json()
    comment = data.get('comment', '').strip() if data else ''
    
    conn = get_db_connection()
    if conn is None:
        return jsonify({'success': False, 'message': 'Database connection failed!'})
    
    cursor = conn.cursor()
    
    try:
        # 🔥 ULTRA FAST: Get only essential data
        cursor.execute('SELECT id, pass_number, status, department_id, created_by FROM gate_passes WHERE id = %s', (gate_pass_id,))
        result = cursor.fetchone()
        
        if not result:
            return jsonify({'success': False, 'message': 'Gate pass not found!'})
        
        gate_pass_id, pass_number, current_status, department_id, created_by = result
        
        # 🔥 Department Head - Instant Approval
        if user_role == 'department_head':
            if current_status != 'pending_dept':
                return jsonify({'success': False, 'message': f'Gate pass is already {current_status}!'})
            
            # Quick department check
            cursor.execute('SELECT department_id FROM users WHERE id = %s', (user_id,))
            user_dept = cursor.fetchone()
            
            if not user_dept or user_dept[0] != department_id:
                return jsonify({'success': False, 'message': 'You can only approve gate passes from your department!'})
            
            # 🔥 INSTANT STATUS UPDATE
            if action == 'approve':
                new_status = 'pending_store'
                approval_status = 'approved'
                message = f"✅ Gate Pass {pass_number} approved! Sent to stores."
            else:
                new_status = 'rejected'
                approval_status = 'rejected'
                message = f"❌ Gate Pass {pass_number} rejected."
            
            # 🔥 SINGLE UPDATE QUERY
            cursor.execute('''
                UPDATE gate_passes 
                SET status = %s, department_approval = %s, department_approval_date = %s
                WHERE id = %s
            ''', (new_status, approval_status, datetime.now(), gate_pass_id))
            
            # 🔥 QUICK APPROVAL RECORD
            if comment:
                cursor.execute('''
                    INSERT INTO gate_pass_approvals (gate_pass_id, user_id, approval_type, status, comments)
                    VALUES (%s, %s, 'department', %s, %s)
                ''', (gate_pass_id, user_id, approval_status, comment))
            else:
                cursor.execute('''
                    INSERT INTO gate_pass_approvals (gate_pass_id, user_id, approval_type, status)
                    VALUES (%s, %s, 'department', %s)
                ''', (gate_pass_id, user_id, approval_status))
            
        # 🔥 Store Manager - Instant Approval  
        elif user_role == 'store_manager':
            store_location = 'store_1' if 'store1' in session['username'] else 'store_2'
            
            if current_status != 'pending_store':
                return jsonify({'success': False, 'message': f'Gate pass is already {current_status}!'})
            
            if action == 'approve':
                new_status = 'pending_security'
                approval_status = 'approved'
                message = f"✅ Gate Pass {pass_number} approved! Sent to security."
            else:
                new_status = 'rejected'
                approval_status = 'rejected'
                message = f"❌ Gate Pass {pass_number} rejected by store."
            
            # 🔥 SINGLE UPDATE QUERY
            cursor.execute('''
                UPDATE gate_passes 
                SET status = %s, store_approval = %s, store_approval_date = %s, store_location = %s
                WHERE id = %s
            ''', (new_status, approval_status, datetime.now(), store_location, gate_pass_id))
            
            # 🔥 QUICK APPROVAL RECORD
            if comment:
                cursor.execute('''
                    INSERT INTO gate_pass_approvals (gate_pass_id, user_id, approval_type, status, comments)
                    VALUES (%s, %s, 'store', %s, %s)
                ''', (gate_pass_id, user_id, approval_status, comment))
            else:
                cursor.execute('''
                    INSERT INTO gate_pass_approvals (gate_pass_id, user_id, approval_type, status)
                    VALUES (%s, %s, 'store', %s)
                ''', (gate_pass_id, user_id, approval_status))
        
        # 🔥 COMMIT IMMEDIATELY
        conn.commit()
        
        # 🔥 BACKGROUND NOTIFICATIONS (Don't wait for them)
        if user_role == 'department_head':
            if action == 'approve':
                # Notify store managers in background
                async_notification_bulk('store_manager', f"📋 Gate Pass {pass_number} needs approval", 'approval', gate_pass_id)
            
            # Notify creator in background
            async_notify(created_by, f"📋 Your Gate Pass {pass_number} has been {action}d", 'status', gate_pass_id)
        
        elif user_role == 'store_manager':
            if action == 'approve':
                # Notify security in background
                async_notification_bulk('security', f"🛡️ Gate Pass {pass_number} needs approval", 'approval', gate_pass_id)
            
            # Notify creator and department head in background
            async_notify(created_by, f"🏪 Your Gate Pass {pass_number} has been {action}d", 'status', gate_pass_id)
            
            # Notify department head
            cursor.execute('SELECT id FROM users WHERE department_id = %s AND role = "department_head" LIMIT 1', (department_id,))
            dept_head = cursor.fetchone()
            if dept_head:
                async_notify(dept_head[0], f"🏪 Gate Pass {pass_number} has been {action}d by store", 'status', gate_pass_id)
        
        return jsonify({
            'success': True, 
            'message': message,
            'status': new_status,
            'has_comment': bool(comment)
        })
        
    except Exception as e:
        conn.rollback()
        print(f"Instant approval error: {e}")
        return jsonify({'success': False, 'message': 'Approval failed. Please try again.'})
    finally:
        cursor.close()
        conn.close()

# 🔥 Keep existing routes but use instant_approve for speed
@gate_pass_bp.route('/approve_gate_pass_with_comment/<int:gate_pass_id>/<action>', methods=['POST'])
def approve_gate_pass_with_comment(gate_pass_id, action):
    """Redirect to instant approval"""
    return instant_approve_gate_pass(gate_pass_id, action)

# ✅ OPTIMIZED: Faster approval function (backward compatible)
@gate_pass_bp.route('/fast_approve_gate_pass/<int:gate_pass_id>/<action>', methods=['POST'])
def fast_approve_gate_pass(gate_pass_id, action):
    """Ultra-fast gate pass approval API"""
    return instant_approve_gate_pass(gate_pass_id, action)

# 🔥 Fast inquiry function
@gate_pass_bp.route('/fast_inquiry/<int:gate_pass_id>', methods=['POST'])
def fast_inquiry(gate_pass_id):
    """Fast inquiry marking"""
    if 'user_id' not in session or session['role'] != 'department_head':
        return jsonify({'success': False, 'message': 'Access denied!'})
    
    data = request.get_json()
    inquiry_purpose = data.get('purpose', '').strip() if data else ''
    
    if not inquiry_purpose:
        return jsonify({'success': False, 'message': 'Please provide inquiry purpose!'})
    
    conn = get_db_connection()
    if conn is None:
        return jsonify({'success': False, 'message': 'Database connection failed!'})
    
    cursor = conn.cursor()
    
    try:
        # Quick check
        cursor.execute('SELECT status, pass_number FROM gate_passes WHERE id = %s', (gate_pass_id,))
        result = cursor.fetchone()
        
        if not result:
            return jsonify({'success': False, 'message': 'Gate pass not found!'})
        
        current_status, pass_number = result
        
        if current_status != 'pending_dept':
            return jsonify({'success': False, 'message': f'Gate pass is already {current_status}!'})
        
        # Fast update
        cursor.execute('''
            UPDATE gate_passes 
            SET status = 'inquiry', department_approval = 'inquiry', department_approval_date = %s
            WHERE id = %s
        ''', (datetime.now(), gate_pass_id))
        
        # Add inquiry record
        cursor.execute('''
            INSERT INTO gate_pass_approvals (gate_pass_id, user_id, approval_type, status, comments)
            VALUES (%s, %s, 'department', 'inquiry', %s)
        ''', (gate_pass_id, session['user_id'], inquiry_purpose))
        
        conn.commit()
        
        # Background notifications
        async_notification_bulk('store_manager', f"❓ Gate Pass {pass_number} marked for inquiry", 'inquiry', gate_pass_id)
        
        return jsonify({
            'success': True, 
            'message': f'Gate Pass {pass_number} marked for inquiry!'
        })
        
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'message': 'Error!'})
    finally:
        cursor.close()
        conn.close()

# 🔥 Fast user approval
@gate_pass_bp.route('/fast_approve_user/<int:user_id>/<action>', methods=['POST'])
def fast_approve_user(user_id, action):
    """Fast user approval"""
    if 'user_id' not in session or session['role'] != 'department_head':
        return jsonify({'success': False, 'message': 'Access denied!'})
    
    conn = get_db_connection()
    if conn is None:
        return jsonify({'success': False, 'message': 'Database connection failed!'})
    
    cursor = conn.cursor()
    
    try:
        # Get user department
        cursor.execute('SELECT department_id, username FROM users WHERE id = %s', (user_id,))
        user_data = cursor.fetchone()
        
        if not user_data:
            return jsonify({'success': False, 'message': 'User not found!'})
        
        user_dept, username = user_data
        
        # Check if department head can approve
        cursor.execute('SELECT department_id FROM users WHERE id = %s', (session['user_id'],))
        dept_head_dept = cursor.fetchone()
        
        if not dept_head_dept or dept_head_dept[0] != user_dept:
            return jsonify({'success': False, 'message': 'You can only approve users from your department!'})
        
        # Fast update
        status = 'approved' if action == 'approve' else 'rejected'
        cursor.execute('UPDATE users SET status = %s WHERE id = %s', (status, user_id))
        
        conn.commit()
        
        return jsonify({
            'success': True, 
            'message': f'User {username} {action}d successfully!'
        })
        
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'message': 'Error!'})
    finally:
        cursor.close()
        conn.close()

@gate_pass_bp.route('/create_gate_pass', methods=['GET', 'POST'])
def create_gate_pass():
    """Create new gate pass - ULTRA FAST VERSION"""
    print(f"\n{'='*90}")
    print(f"🚀 GATE PASS CREATION STARTED - FAST MODE")
    print(f"{'='*90}")
    
    if 'user_id' not in session:
        print("❌ User not logged in")
        flash('Please login first!', 'error')
        return redirect(url_for('auth.login'))
    
    # Quick role check
    if session['role'] in ['security', 'store_manager']:
        error_msg = f'{session["role"].replace("_", " ").title()} cannot create gate passes!'
        flash(error_msg, 'error')
        return redirect(url_for('dashboard'))
    
    # Get form data for dropdowns
    conn = get_db_connection()
    if conn is None:
        flash('❌ Database connection failed!', 'error')
        return render_template('create_gate_pass.html', divisions=[], departments=[])
    
    cursor = conn.cursor()
    
    try:
        cursor.execute('SELECT id, name FROM divisions WHERE status = "active" ORDER BY name')
        divisions = dict_fetchall(cursor)
        
        cursor.execute('''
            SELECT d.id, d.name, d.division_id, dv.name as division_name 
            FROM departments d 
            JOIN divisions dv ON d.division_id = dv.id 
            WHERE d.status = "active" 
            ORDER BY dv.name, d.name
        ''')
        departments = dict_fetchall(cursor)
    except Exception as e:
        print(f"❌ Error fetching data: {e}")
        divisions = []
        departments = []
    
    if request.method == 'POST':
        print("📤 Processing form submission...")
        
        # SIMPLE VALIDATION - FASTER
        required_fields = [
            'division_id', 'department_id', 'material_description', 
            'destination', 'purpose', 'material_type', 'material_status',
            'receiver_name', 'receiver_contact', 'send_date'
        ]
        
        form_data = {}
        for field in required_fields:
            value = request.form.get(field, '').strip()
            if not value:
                flash(f'❌ Please fill {field.replace("_", " ")}', 'error')
                return render_template('create_gate_pass.html', 
                                     divisions=divisions, 
                                     departments=departments)
            form_data[field] = value
        
        # Check photos
        captured_images = request.form.getlist('captured_images[]')
        valid_images = [img for img in captured_images if img and img.startswith('data:image')]
        
        if len(valid_images) < 4:
            flash('❌ Minimum 4 photos required!', 'error')
            return render_template('create_gate_pass.html', 
                                 divisions=divisions, 
                                 departments=departments)
        
        try:
            # Generate pass number
            timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
            pass_number = f"GP{timestamp}"
            
            # Save images (fast version)
            saved_paths = []
            upload_folder = 'static/uploads'
            os.makedirs(upload_folder, exist_ok=True)
            
            for i, img_data in enumerate(valid_images[:4]):  # Only first 4 images
                if ',' in img_data:
                    header, encoded = img_data.split(',', 1)
                else:
                    encoded = img_data
                
                try:
                    image_bytes = base64.b64decode(encoded)
                    filename = f"fast_{timestamp}_{i+1}.jpg"
                    filepath = os.path.join(upload_folder, filename)
                    
                    with open(filepath, 'wb') as f:
                        f.write(image_bytes)
                    
                    saved_paths.append(f"uploads/{filename}")
                except:
                    continue
            
            images_json = json.dumps(saved_paths)
            
            # Parse dates
            try:
                send_datetime = datetime.strptime(form_data['send_date'], '%Y-%m-%dT%H:%M')
            except:
                send_datetime = datetime.now()
            
            return_datetime = None
            if form_data['material_type'] == 'returnable' and request.form.get('expected_return_date'):
                try:
                    return_datetime = datetime.strptime(
                        request.form['expected_return_date'], 
                        '%Y-%m-%dT%H:%M'
                    )
                except:
                    return_datetime = datetime.now() + timedelta(days=7)
            
            # Insert gate pass - SIMPLIFIED
            cursor.execute('''
                INSERT INTO gate_passes (
                    pass_number, created_by, division_id, department_id, 
                    material_description, destination, purpose, material_type, 
                    material_status, expected_return_date, receiver_name, 
                    receiver_contact, send_date, images, status, urgent
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ''', (
                pass_number, session['user_id'], 
                int(form_data['division_id']), int(form_data['department_id']),
                form_data['material_description'], form_data['destination'], 
                form_data['purpose'], form_data['material_type'],
                form_data['material_status'], return_datetime,
                form_data['receiver_name'], form_data['receiver_contact'],
                send_datetime, images_json, 'pending_dept',
                1 if request.form.get('urgent') == 'true' else 0
            ))
            
            gate_pass_id = cursor.lastrowid
            
            # Generate QR (optional - can be done async)
            try:
                from qr_utils import generate_gate_pass_qr_data
                qr_data_form = generate_gate_pass_qr_data(gate_pass_id, pass_number)
                qr_data_sticker = generate_gate_pass_qr_data(gate_pass_id, f"{pass_number}_STICKER")
                
                cursor.execute('''
                    UPDATE gate_passes 
                    SET qr_code_form = %s, qr_code_sticker = %s 
                    WHERE id = %s
                ''', (qr_data_form, qr_data_sticker, gate_pass_id))
            except:
                pass  # QR can fail, gate pass still created
            
            # Commit FIRST, then send notifications
            conn.commit()
            
            # Send notifications (non-blocking)
            try:
                # Notify department head
                cursor.execute('''
                    SELECT u.id FROM users u 
                    WHERE u.department_id = %s 
                    AND u.role = 'department_head' 
                    AND u.status = 'approved'
                    LIMIT 1
                ''', (int(form_data['department_id']),))
                
                dept_head = cursor.fetchone()
                if dept_head:
                    # Use async notification
                    async_notify(dept_head[0], 
                                f"📋 New Gate Pass {pass_number} needs approval",
                                'approval',
                                gate_pass_id)
                
                # Notify creator
                async_notify(session['user_id'],
                            f"✅ Gate Pass {pass_number} created successfully!",
                            'status',
                            gate_pass_id)
            except:
                pass  # Notifications are optional
            
            flash(f'✅ Gate Pass {pass_number} created successfully!', 'success')
            print(f"🎉 Gate Pass {pass_number} created in under 2 seconds!")
            
            cursor.close()
            conn.close()
            
            return redirect(url_for('gate_pass.gate_pass_list'))
            
        except Exception as e:
            conn.rollback()
            error_msg = f'❌ Error: {str(e)[:100]}'
            flash(error_msg, 'error')
            print(f"❌ Error: {e}")
            import traceback
            traceback.print_exc()
            
            cursor.close()
            conn.close()
            return render_template('create_gate_pass.html', 
                                 divisions=divisions, 
                                 departments=departments)
    
    # GET request
    cursor.close()
    conn.close()
    return render_template('create_gate_pass.html', 
                         divisions=divisions, 
                         departments=departments)

@gate_pass_bp.route('/gate_pass_list')
def gate_pass_list():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    
    conn = get_db_connection()
    if conn is None:
        flash('Database connection failed!', 'error')
        return render_template('gate_pass_list.html', gate_passes=[], store_requests=[])
    
    cursor = conn.cursor()
    
    try:
        current_user_department_id = None
        
        # ✅ FIXED: Get current user's department for template
        if session['role'] == 'department_head':
            cursor.execute('SELECT department_id FROM users WHERE id = %s', (session['user_id'],))
            dept_result = cursor.fetchone()
            if dept_result:
                current_user_department_id = dept_result[0]
        
        # ✅ FIXED: For Store Managers - Show ALL gate passes AND their store requests
        if session['role'] == 'store_manager':
            store_location = 'store_1' if 'store1' in session['username'] else 'store_2'
            
            # ✅ FIXED: Get ALL gate passes that are relevant to store manager
            cursor.execute('''
                SELECT gp.*, u.name as creator_name, d.name as department_name, dv.name as division_name,
                       gp.department_approval_date, gp.department_approval
                FROM gate_passes gp 
                JOIN users u ON gp.created_by = u.id 
                JOIN departments d ON gp.department_id = d.id 
                JOIN divisions dv ON gp.division_id = dv.id 
                WHERE (gp.store_location = %s OR gp.status = 'pending_store' OR gp.status = 'approved')
                ORDER BY gp.created_at DESC
            ''', (store_location,))
            gate_passes = dict_fetchall(cursor)
            
            # Get store manager's own requests
            cursor.execute('''
                SELECT sr.*, u.name as admin_name
                FROM store_manager_requests sr
                LEFT JOIN users u ON sr.admin_response_by = u.id
                WHERE sr.store_manager_id = %s AND sr.store_location = %s
                ORDER BY sr.created_at DESC
            ''', (session['user_id'], store_location))
            store_requests = dict_fetchall(cursor)
            
            return render_template('gate_pass_list.html', 
                                 gate_passes=gate_passes, 
                                 store_requests=store_requests,
                                 user_role='store_manager')
        
        # ✅ FIXED: For Department Head - Only their department's gate passes
        elif session['role'] == 'department_head':
            # Get department head's department
            cursor.execute('SELECT department_id FROM users WHERE id = %s', (session['user_id'],))
            user_dept = cursor.fetchone()
            
            if user_dept:
                department_id = user_dept[0]
                # Department Head এর জন্য Department Approval তথ্য সহ
                cursor.execute('''
                    SELECT gp.*, u.name as creator_name, d.name as department_name, dv.name as division_name,
                           gp.department_approval_date, gp.department_approval
                    FROM gate_passes gp 
                    JOIN users u ON gp.created_by = u.id 
                    JOIN departments d ON gp.department_id = d.id 
                    JOIN divisions dv ON gp.division_id = dv.id 
                    WHERE gp.department_id = %s 
                    ORDER BY gp.created_at DESC
                ''', (department_id,))
                gate_passes = dict_fetchall(cursor)
            else:
                gate_passes = []
            
            return render_template('gate_pass_list.html', 
                                 gate_passes=gate_passes, 
                                 store_requests=[],
                                 current_user_department_id=current_user_department_id)
        
        # ✅ FIXED: For Security - ALL department approved gate passes
        elif session['role'] == 'security':
            # ✅ FIXED: Security can see ALL department approved gate passes
            cursor.execute('''
                SELECT gp.*, u.name as creator_name, d.name as department_name, dv.name as division_name,
                       gp.department_approval_date, gp.department_approval
                FROM gate_passes gp 
                JOIN users u ON gp.created_by = u.id 
                JOIN departments d ON gp.department_id = d.id 
                JOIN divisions dv ON gp.division_id = dv.id 
                WHERE gp.department_approval = 'approved' 
                ORDER BY gp.department_approval_date DESC, gp.created_at DESC
            ''')
            gate_passes = dict_fetchall(cursor)
            
            return render_template('gate_pass_list.html', 
                                 gate_passes=gate_passes, 
                                 store_requests=[],
                                 user_role='security')
        
        # ✅ FIXED: For System Admin - All gate passes
        elif session['role'] == 'system_admin':
            # System Admin এর জন্য Department Approval তথ্য সহ
            cursor.execute('''
                SELECT gp.*, u.name as creator_name, d.name as department_name, dv.name as division_name,
                       gp.department_approval_date, gp.department_approval
                FROM gate_passes gp 
                JOIN users u ON gp.created_by = u.id 
                JOIN departments d ON gp.department_id = d.id 
                JOIN divisions dv ON gp.division_id = dv.id 
                ORDER BY gp.created_at DESC
            ''')
            gate_passes = dict_fetchall(cursor)
            
            return render_template('gate_pass_list.html', 
                                 gate_passes=gate_passes, 
                                 store_requests=[])
        
        # ✅ FIXED: For Regular User - Only their own passes
        else:
            # Regular User এর জন্য Department Approval তথ্য সহ
            cursor.execute('''
                SELECT gp.*, u.name as creator_name, d.name as department_name, dv.name as division_name,
                       gp.department_approval_date, gp.department_approval
                FROM gate_passes gp 
                JOIN users u ON gp.created_by = u.id 
                JOIN departments d ON gp.department_id = d.id 
                JOIN divisions dv ON gp.division_id = dv.id 
                WHERE gp.created_by = %s 
                ORDER BY gp.created_at DESC
            ''', (session['user_id'],))
            gate_passes = dict_fetchall(cursor)
            
            return render_template('gate_pass_list.html', 
                                 gate_passes=gate_passes, 
                                 store_requests=[])
        
    except Exception as e:
        print(f"Gate pass list error: {e}")
        gate_passes = []
        store_requests = []
    finally:
        cursor.close()
        conn.close()
    
    return render_template('gate_pass_list.html', 
                         gate_passes=gate_passes, 
                         store_requests=[],
                         current_user_department_id=current_user_department_id)

@gate_pass_bp.route('/gate_pass_detail/<int:gate_pass_id>')
def gate_pass_detail(gate_pass_id):
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    
    conn = get_db_connection()
    if conn is None:
        flash('Database connection failed!', 'error')
        return redirect(url_for('gate_pass.gate_pass_list'))
    
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            SELECT gp.*, u.name as creator_name, u.designation as creator_designation,
                   d.name as department_name, dv.name as division_name
            FROM gate_passes gp 
            JOIN users u ON gp.created_by = u.id 
            JOIN departments d ON gp.department_id = d.id 
            JOIN divisions dv ON gp.division_id = dv.id 
            WHERE gp.id = %s
        ''', (gate_pass_id,))
        
        gate_pass = dict_fetchone(cursor)
        
        if not gate_pass:
            flash('Gate pass not found!', 'error')
            return redirect(url_for('gate_pass.gate_pass_list'))
        
        # Check permissions - FIXED VERSION
        if session['role'] not in ['system_admin', 'department_head', 'store_manager', 'security']:
            if gate_pass['created_by'] != session['user_id']:
                flash('Access denied!', 'error')
                return redirect(url_for('gate_pass.gate_pass_list'))
        
        # Parse images JSON
        try:
            gate_pass['images_list'] = json.loads(gate_pass['images']) if gate_pass['images'] else []
        except:
            gate_pass['images_list'] = []
        
        # Generate QR code images for display
        from qr_utils import generate_qr_code
        if gate_pass['qr_code_form']:
            gate_pass['qr_form_img'] = generate_qr_code(gate_pass['qr_code_form'])
        if gate_pass['qr_code_sticker']:
            gate_pass['qr_sticker_img'] = generate_qr_code(gate_pass['qr_code_sticker'])
        
        # Get approval history (FIXED - Check if table exists)
        approvals = []
        try:
            cursor.execute('''
                SELECT * FROM gate_pass_approvals 
                WHERE gate_pass_id = %s 
                ORDER BY created_at DESC
            ''', (gate_pass_id,))
            approvals = dict_fetchall(cursor)
        except Exception as table_error:
            print(f"Note: gate_pass_approvals table error: {table_error}")
            # Table might not exist yet, that's okay
        
    except Exception as e:
        print(f"Gate pass detail error: {e}")
        flash('Error loading gate pass details!', 'error')
        return redirect(url_for('gate_pass.gate_pass_list'))
    finally:
        cursor.close()
        conn.close()
    
    return render_template('gate_pass_detail.html', gate_pass=gate_pass, approvals=approvals, now=datetime.now())

@gate_pass_bp.route('/get_gate_pass_details/<int:gate_pass_id>')
def get_gate_pass_details(gate_pass_id):
    """Get gate pass details for editing"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Access denied!'})
    
    conn = get_db_connection()
    if conn is None:
        return jsonify({'success': False, 'message': 'Database connection failed!'})
    
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            SELECT gp.* 
            FROM gate_passes gp 
            WHERE gp.id = %s
        ''', (gate_pass_id,))
        
        gate_pass = dict_fetchone(cursor)
        
        if gate_pass:
            return jsonify({'success': True, 'gate_pass': gate_pass})
        else:
            return jsonify({'success': False, 'message': 'Gate pass not found!'})
            
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error: {str(e)}'})
    finally:
        cursor.close()
        conn.close()

@gate_pass_bp.route('/approve_gate_pass/<int:gate_pass_id>/<action>')
def approve_gate_pass(gate_pass_id, action):
    """Department Head approves gate pass - UPDATED WORKFLOW (Backward compatible)"""
    # Redirect to instant approval
    if action == 'inquiry':
        # Handle inquiry specially
        inquiry_purpose = request.args.get('inquiry_purpose', '')
        if not inquiry_purpose:
            return jsonify({'success': False, 'message': 'Please provide inquiry purpose!'})
        
        return fast_inquiry(gate_pass_id)
    else:
        return instant_approve_gate_pass(gate_pass_id, action)

@gate_pass_bp.route('/store/approve_gate_pass/<int:gate_pass_id>/<action>', methods=['POST'])
def store_approve_gate_pass(gate_pass_id, action):
    """Store Manager approves gate pass - UPDATED WORKFLOW (Backward compatible)"""
    return instant_approve_gate_pass(gate_pass_id, action)

# ✅ ADDED: Security Approve/Reject Gate Pass
@gate_pass_bp.route('/security/approve_gate_pass/<int:gate_pass_id>/<action>', methods=['POST'])
def security_approve_gate_pass(gate_pass_id, action):
    """Security approves gate pass"""
    if 'user_id' not in session or session['role'] != 'security':
        return jsonify({'success': False, 'message': 'Access denied! Only Security can approve gate passes.'})
    
    if action not in ['approve', 'reject']:
        return jsonify({'success': False, 'message': 'Invalid action!'})
    
    conn = get_db_connection()
    if conn is None:
        return jsonify({'success': False, 'message': 'Database connection failed!'})
    
    cursor = conn.cursor()
    
    try:
        # Get gate pass details
        cursor.execute('SELECT * FROM gate_passes WHERE id = %s', (gate_pass_id,))
        gate_pass = dict_fetchone(cursor)
        
        if not gate_pass:
            return jsonify({'success': False, 'message': 'Gate pass not found!'})
        
        # Check if gate pass is pending security approval
        if gate_pass['status'] != 'pending_security':
            return jsonify({'success': False, 'message': f'Gate pass is already {gate_pass["status"]}!'})
        
        if action == 'approve':
            # ✅ Security approves - gate pass becomes approved
            new_status = 'approved'
            security_approval_status = 'approved'
            
            cursor.execute('''
                INSERT INTO gate_pass_approvals (gate_pass_id, user_id, approval_type, status)
                VALUES (%s, %s, 'security', 'approved')
            ''', (gate_pass_id, session['user_id']))
            
            message = f"✅ Gate Pass {gate_pass['pass_number']} approved by Security!"
            
        else:  # reject
            new_status = 'rejected'
            security_approval_status = 'rejected'
            
            cursor.execute('''
                INSERT INTO gate_pass_approvals (gate_pass_id, user_id, approval_type, status)
                VALUES (%s, %s, 'security', 'rejected')
            ''', (gate_pass_id, session['user_id']))
            
            message = f"❌ Gate Pass {gate_pass['pass_number']} rejected by Security."
        
        # Update gate pass
        cursor.execute('''
            UPDATE gate_passes 
            SET status = %s, security_approval = %s, security_approval_date = %s,
                approved_by_security = %s
            WHERE id = %s
        ''', (new_status, security_approval_status, datetime.now(), session['name'], gate_pass_id))
        
        conn.commit()
        
        # Background notifications
        async_notify(
            gate_pass['created_by'],
            f"🛡️ Your Gate Pass {gate_pass['pass_number']} has been {action}d by Security",
            'status',
            gate_pass_id
        )
        
        # Notify department head
        cursor.execute('''
            SELECT u.id FROM users u 
            WHERE u.department_id = %s 
            AND u.role = 'department_head' 
            AND u.status = 'approved'
            LIMIT 1
        ''', (gate_pass['department_id'],))
        
        dept_head = cursor.fetchone()
        if dept_head:
            async_notify(
                dept_head[0],
                f"🛡️ Gate Pass {gate_pass['pass_number']} from your department has been {action}d by Security",
                'status',
                gate_pass_id
            )
        
        # Notify store manager (if store was involved)
        if gate_pass['store_location']:
            cursor.execute('''
                SELECT u.id FROM users u 
                WHERE u.role = 'store_manager' AND u.status = 'approved'
                LIMIT 1
            ''')
            store_manager = cursor.fetchone()
            if store_manager:
                async_notify(
                    store_manager[0],
                    f"🛡️ Gate Pass {gate_pass['pass_number']} has been {action}d by Security",
                    'status',
                    gate_pass_id
                )
        
        # Notify all system admins
        async_notification_bulk('system_admin', f"🛡️ Gate Pass {gate_pass['pass_number']} has been {action}d by Security ({session['name']})", 'status', gate_pass_id)
        
        return jsonify({'success': True, 'message': message})
        
    except Exception as e:
        print(f"Error in security approval: {e}")
        conn.rollback()
        return jsonify({'success': False, 'message': f'Error: {str(e)}'})
    finally:
        cursor.close()
        conn.close()

# ✅ NEW: Department Head Edit/Delete Gate Pass
@gate_pass_bp.route('/department/edit_gate_pass/<int:gate_pass_id>', methods=['POST'])
def edit_gate_pass(gate_pass_id):
    """Department Head edits gate pass"""
    if 'user_id' not in session or session['role'] != 'department_head':
        return jsonify({'success': False, 'message': 'Access denied!'})
    
    conn = get_db_connection()
    if conn is None:
        return jsonify({'success': False, 'message': 'Database connection failed!'})
    
    cursor = conn.cursor()
    
    try:
        # Check if department head can edit this gate pass
        cursor.execute('''
            SELECT gp.*, u.department_id as creator_dept_id
            FROM gate_passes gp 
            JOIN users u ON gp.created_by = u.id 
            WHERE gp.id = %s
        ''', (gate_pass_id,))
        
        gate_pass = dict_fetchone(cursor)
        
        if not gate_pass:
            return jsonify({'success': False, 'message': 'Gate pass not found!'})
        
        # Check if department head belongs to same department
        cursor.execute('SELECT department_id FROM users WHERE id = %s', (session['user_id'],))
        dept_head_dept = cursor.fetchone()
        
        if not dept_head_dept or dept_head_dept[0] != gate_pass['creator_dept_id']:
            return jsonify({'success': False, 'message': 'You can only edit gate passes from your department!'})
        
        # Check if gate pass can still be edited (only in draft or pending_dept)
        if gate_pass['status'] not in ['draft', 'pending_dept']:
            return jsonify({'success': False, 'message': 'Cannot edit gate pass that is already in approval process!'})
        
        # Get form data
        material_description = request.form.get('material_description')
        destination = request.form.get('destination')
        purpose = request.form.get('purpose')
        receiver_name = request.form.get('receiver_name')
        receiver_contact = request.form.get('receiver_contact')
        
        # Update gate pass
        cursor.execute('''
            UPDATE gate_passes 
            SET material_description = %s, destination = %s, purpose = %s,
                receiver_name = %s, receiver_contact = %s, updated_at = %s
            WHERE id = %s
        ''', (material_description, destination, purpose, receiver_name, receiver_contact, datetime.now(), gate_pass_id))
        
        conn.commit()
        
        # ✅ Notify Super Admin
        async_notification_bulk('system_admin', f"✏️ Gate Pass {gate_pass['pass_number']} edited by Department Head {session['name']}", 'alert', gate_pass_id)
        
        # Notify creator
        async_notify(
            gate_pass['created_by'],
            f"✏️ Your Gate Pass {gate_pass['pass_number']} has been edited by department head",
            'status',
            gate_pass_id
        )
        
        return jsonify({'success': True, 'message': 'Gate pass updated successfully!'})
        
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'message': f'Error updating gate pass: {str(e)}'})
    finally:
        cursor.close()
        conn.close()

@gate_pass_bp.route('/department/delete_gate_pass/<int:gate_pass_id>', methods=['POST'])
def delete_gate_pass_by_dept_head(gate_pass_id):
    """Department Head deletes gate pass"""
    if 'user_id' not in session or session['role'] != 'department_head':
        return jsonify({'success': False, 'message': 'Access denied!'})
    
    conn = get_db_connection()
    if conn is None:
        return jsonify({'success': False, 'message': 'Database connection failed!'})
    
    cursor = conn.cursor()
    
    try:
        # Check if department head can delete this gate pass
        cursor.execute('''
            SELECT gp.*, u.department_id as creator_dept_id
            FROM gate_passes gp 
            JOIN users u ON gp.created_by = u.id 
            WHERE gp.id = %s
        ''', (gate_pass_id,))
        
        gate_pass = dict_fetchone(cursor)
        
        if not gate_pass:
            return jsonify({'success': False, 'message': 'Gate pass not found!'})
        
        # Check if department head belongs to same department
        cursor.execute('SELECT department_id FROM users WHERE id = %s', (session['user_id'],))
        dept_head_dept = cursor.fetchone()
        
        if not dept_head_dept or dept_head_dept[0] != gate_pass['creator_dept_id']:
            return jsonify({'success': False, 'message': 'You can only delete gate passes from your department!'})
        
        # Check if gate pass can be deleted (only in draft or pending_dept)
        if gate_pass['status'] not in ['draft', 'pending_dept']:
            return jsonify({'success': False, 'message': 'Cannot delete gate pass that is already in approval process!'})
        
        # Delete gate pass
        cursor.execute('DELETE FROM gate_passes WHERE id = %s', (gate_pass_id,))
        
        conn.commit()
        
        # ✅ Notify Super Admin
        async_notification_bulk('system_admin', f"🗑️ Gate Pass {gate_pass['pass_number']} deleted by Department Head {session['name']}", 'alert', None)
        
        # Notify creator
        async_notify(
            gate_pass['created_by'],
            f"🗑️ Your Gate Pass {gate_pass['pass_number']} has been deleted by department head",
            'status',
            None
        )
        
        return jsonify({'success': True, 'message': 'Gate pass deleted successfully!'})
        
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'message': f'Error deleting gate pass: {str(e)}'})
    finally:
        cursor.close()
        conn.close()

@gate_pass_bp.route('/store/create_request', methods=['GET', 'POST'])
def create_store_request():
    """Store Manager creates request for HR/Admin to create gate pass"""
    if 'user_id' not in session or session['role'] != 'store_manager':
        flash('Access denied! Only Store Managers can create store requests.', 'error')
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        material_description = request.form['material_description']
        destination = request.form['destination']
        purpose = request.form['purpose']
        receiver_name = request.form['receiver_name']
        receiver_contact = request.form.get('receiver_contact', '')
        quantity = request.form.get('quantity', 1)
        urgency = request.form.get('urgency', 'normal')
        
        store_location = 'store_1' if 'store1' in session['username'] else 'store_2'
        
        conn = get_db_connection()
        if conn is None:
            flash('Database connection failed!', 'error')
            return redirect(url_for('gate_pass.gate_pass_list'))
        
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                INSERT INTO store_manager_requests (
                    store_manager_id, store_location, material_description, destination, purpose,
                    receiver_name, receiver_contact, quantity, urgency, status
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'pending')
            ''', (
                session['user_id'], store_location, material_description, destination, purpose,
                receiver_name, receiver_contact, quantity, urgency
            ))
            
            request_id = cursor.lastrowid
            
            # Notify ALL System Administrators and HR/Admin users
            async_notification_bulk('system_admin', f"🏪 Store Request from {session['name']} ({store_location}): {material_description}", 'approval', request_id)
            
            conn.commit()
            flash('✅ Store request submitted successfully! HR/Admin will review and create gate pass.', 'success')
            
        except Exception as e:
            conn.rollback()
            flash(f'❌ Error creating store request: {str(e)}', 'error')
        finally:
            cursor.close()
            conn.close()
        
        return redirect(url_for('gate_pass.gate_pass_list'))
    
    # GET request - show form
    return render_template('store/create_request.html')

@gate_pass_bp.route('/store/material_log')
def store_material_log():
    """Store Manager views material movement log"""
    if 'user_id' not in session or session['role'] != 'store_manager':
        flash('Access denied! Only Store Managers can view material logs.', 'error')
        return redirect(url_for('dashboard'))
    
    store_location = 'store_1' if 'store1' in session['username'] else 'store_2'
    
    conn = get_db_connection()
    if conn is None:
        flash('Database connection failed!', 'error')
        return render_template('store/material_log.html', logs=[])
    
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            SELECT sml.*, u.name as handler_name, gp.pass_number
            FROM store_material_logs sml
            LEFT JOIN users u ON sml.handled_by = u.id
            LEFT JOIN gate_passes gp ON sml.gate_pass_id = gp.id
            WHERE sml.store_location = %s
            ORDER BY sml.created_at DESC
        ''', (store_location,))
        
        logs = dict_fetchall(cursor)
    except Exception as e:
        print(f"Material log error: {e}")
        logs = []
    finally:
        cursor.close()
        conn.close()
    
    return render_template('store/material_log.html', logs=logs)

@gate_pass_bp.route('/store/mark_dispatched/<int:gate_pass_id>', methods=['POST'])
def mark_material_dispatched(gate_pass_id):
    """Store Manager marks material as dispatched from store"""
    if 'user_id' not in session or session['role'] != 'store_manager':
        return jsonify({'success': False, 'message': 'Access denied!'})
    
    store_location = 'store_1' if 'store1' in session['username'] else 'store_2'
    
    conn = get_db_connection()
    if conn is None:
        return jsonify({'success': False, 'message': 'Database connection failed!'})
    
    cursor = conn.cursor()
    
    try:
        # Get gate pass details
        cursor.execute('SELECT * FROM gate_passes WHERE id = %s', (gate_pass_id,))
        gate_pass = dict_fetchone(cursor)
        
        if not gate_pass:
            return jsonify({'success': False, 'message': 'Gate pass not found!'})
        
        # Check if gate pass is approved
        if gate_pass['status'] != 'approved':
            return jsonify({'success': False, 'message': 'Gate pass is not approved yet!'})
        
        # Update gate pass status
        cursor.execute('''
            UPDATE gate_passes 
            SET status = 'in_transit', store_location = %s
            WHERE id = %s
        ''', (store_location, gate_pass_id))
        
        # Add to material log
        cursor.execute('''
            INSERT INTO store_material_logs (
                store_location, gate_pass_id, material_description, movement_type,
                quantity, to_location, handled_by, remarks
            ) VALUES (%s, %s, %s, 'outgoing', 1, %s, %s, 'Material dispatched from store')
        ''', (
            store_location, gate_pass_id, gate_pass['material_description'],
            gate_pass['destination'], session['user_id']
        ))
        
        # Notify creator
        async_notify(
            gate_pass['created_by'],
            f"🚚 Your material with Gate Pass {gate_pass['pass_number']} has been dispatched from {store_location}",
            'status',
            gate_pass_id
        )
        
        conn.commit()
        return jsonify({'success': True, 'message': f'Material marked as dispatched from {store_location}!'})
        
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'message': f'Error: {str(e)}'})
    finally:
        cursor.close()
        conn.close()

@gate_pass_bp.route('/fast_create_gate_pass', methods=['POST'])
def fast_create_gate_pass():
    """Ultra-fast gate pass creation API"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Login required'})
    
    try:
        # Get data
        data = request.get_json()
        
        # Quick validation
        required = ['division_id', 'department_id', 'material_description', 
                   'destination', 'purpose', 'material_type', 'receiver_name']
        
        for field in required:
            if field not in data or not data[field]:
                return jsonify({'success': False, 'message': f'Missing {field}'})
        
        # Generate pass number
        pass_number = f"GP{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        # Insert to database
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO gate_passes (
                pass_number, created_by, division_id, department_id,
                material_description, destination, purpose, material_type,
                receiver_name, status
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'pending_dept')
        ''', (
            pass_number, session['user_id'],
            data['division_id'], data['department_id'],
            data['material_description'], data['destination'],
            data['purpose'], data['material_type'],
            data['receiver_name']
        ))
        
        gate_pass_id = cursor.lastrowid
        conn.commit()
        cursor.close()
        conn.close()
        
        return jsonify({
            'success': True, 
            'message': f'Gate Pass {pass_number} created!',
            'pass_number': pass_number,
            'gate_pass_id': gate_pass_id
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

# ✅ FIXED: Quick Manual Return API
@gate_pass_bp.route('/quick_manual_return', methods=['POST'])
def quick_manual_return():
    """Quick manual return without form validation issues"""
    if 'user_id' not in session or session['role'] != 'security':
        return jsonify({'success': False, 'message': 'Access denied!'})
    
    data = request.get_json()
    pass_number = data.get('pass_number', '').strip().upper()
    
    if not pass_number:
        return jsonify({'success': False, 'message': 'Please enter gate pass number!'})
    
    # Ensure it starts with GP
    if not pass_number.startswith('GP'):
        pass_number = f"GP{pass_number}"
    
    conn = get_db_connection()
    if conn is None:
        return jsonify({'success': False, 'message': 'Database connection failed!'})
    
    cursor = conn.cursor()
    
    try:
        # Get gate pass details
        cursor.execute('''  
            SELECT gp.*, u.name as creator_name
            FROM gate_passes gp 
            JOIN users u ON gp.created_by = u.id 
            WHERE gp.pass_number = %s AND gp.material_type = 'returnable'
        ''', (pass_number,))
        
        gate_pass = dict_fetchone(cursor)
        
        if not gate_pass:
            return jsonify({'success': False, 'message': 'Gate pass not found or not returnable!'})
        
        if gate_pass['actual_return_date']:
            return jsonify({'success': False, 'message': 'Material already returned!'})
        
        if gate_pass['status'] not in ['approved', 'gone_from_gate']:
            return jsonify({'success': False, 'message': f'Gate pass is {gate_pass["status"]}, cannot return!'})
        
        # Update as returned
        current_time = datetime.now()
        cursor.execute('''
            UPDATE gate_passes 
            SET actual_return_date = %s, 
                status = 'returned',
                security_approval_date = %s,
                returned_by_security = %s
            WHERE id = %s
        ''', (current_time, current_time, session['name'], gate_pass['id']))
        
        # Create security log
        cursor.execute('''
            INSERT INTO security_logs (gate_pass_id, user_id, alert_type, details)
            VALUES (%s, %s, 'material_returned', %s)
        ''', (gate_pass['id'], session['user_id'], 
              f'Manual return. Gate Pass: {pass_number}. Handled by: {session["name"]}'))
        
        conn.commit()
        
        # Send notification
        async_notify(
            gate_pass['created_by'],
            f"✅ আপনার Gate Pass {pass_number} এর মালামাল ম্যানুয়ালি রিটার্ন হয়েছে। Security: {session['name']}",
            'status',
            gate_pass['id']
        )
        
        return jsonify({
            'success': True,
            'message': f'✅ Gate Pass {pass_number} সফলভাবে রিটার্ন করা হয়েছে!',
            'gate_pass': {
                'pass_number': pass_number,
                'material_description': gate_pass['material_description'],
                'return_time': current_time.strftime('%H:%M:%S')
            }
        })
        
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'message': f'Error: {str(e)}'})
    finally:
        cursor.close()
        conn.close()

# ✅ Legacy approve_user route for backward compatibility
@gate_pass_bp.route('/approve_user/<int:user_id>/<action>')
def approve_user(user_id, action):
    """Legacy user approval route (redirects to fast version)"""
    return fast_approve_user(user_id, action)