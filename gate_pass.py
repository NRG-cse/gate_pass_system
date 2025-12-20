# gate_pass.py - UPDATED FOR NEW SYSTEM
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from models import get_db_connection, dict_fetchall, dict_fetchone
from qr_utils import generate_qr_code, generate_gate_pass_qr_data
from notifications import create_notification
import MySQLdb
from datetime import datetime
import os
import json
import base64

gate_pass_bp = Blueprint('gate_pass', __name__)

def save_captured_images(images_data):
    saved_paths = []
    upload_folder = 'static/uploads'
    
    if not os.path.exists(upload_folder):
        os.makedirs(upload_folder)
    
    for i, image_data in enumerate(images_data):
        if image_data.startswith('data:image'):
            try:
                # Remove data:image/jpeg;base64, prefix
                header, encoded = image_data.split(',', 1)
                image_bytes = base64.b64decode(encoded)
                
                filename = f"material_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{i+1}.jpg"
                filepath = os.path.join(upload_folder, filename)
                
                with open(filepath, 'wb') as f:
                    f.write(image_bytes)
                
                saved_paths.append(filepath.replace('static/', ''))
            except Exception as e:
                print(f"Error saving image {i+1}: {e}")
                continue
        else:
            saved_paths.append(image_data)
    
    return json.dumps(saved_paths)

@gate_pass_bp.route('/create_gate_pass', methods=['GET', 'POST'])
def create_gate_pass():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    
    if session['role'] == 'security':
        flash('Security personnel cannot create gate passes!', 'error')
        return redirect(url_for('dashboard'))
    
    if session['role'] == 'store_manager':
        flash('Store managers cannot create gate passes!', 'error')
        return redirect(url_for('dashboard'))
    
    conn = get_db_connection()
    if conn is None:
        flash('Database connection failed!', 'error')
        return render_template('create_gate_pass.html', divisions=[], departments=[])
    
    cursor = conn.cursor()
    
    # Get divisions and departments for dropdown
    try:
        cursor.execute('SELECT * FROM divisions WHERE status = "active" ORDER BY name')
        divisions = dict_fetchall(cursor)
        
        cursor.execute('''
            SELECT d.*, dv.name as division_name 
            FROM departments d 
            JOIN divisions dv ON d.division_id = dv.id 
            WHERE d.status = "active" 
            ORDER BY dv.name, d.name
        ''')
        departments = dict_fetchall(cursor)
    except Exception as e:
        print(f"Error fetching divisions/departments: {e}")
        divisions = []
        departments = []
    
    if request.method == 'POST':
        # Get form data
        division_id = request.form.get('division_id')
        department_id = request.form.get('department_id')
        material_description = request.form.get('material_description')
        destination = request.form.get('destination')
        purpose = request.form.get('purpose')
        material_type = request.form.get('material_type')
        material_status = request.form.get('material_status')
        receiver_name = request.form.get('receiver_name')
        receiver_contact = request.form.get('receiver_contact')
        send_date = request.form.get('send_date')
        expected_return_date = request.form.get('expected_return_date') if material_type == 'returnable' else None
        
        # Validate required fields
        if not all([division_id, department_id, material_description, destination, purpose, material_type, material_status, receiver_name, receiver_contact, send_date]):
            flash('Please fill all required fields!', 'error')
            return render_template('create_gate_pass.html', divisions=divisions, departments=departments)
        
        # Get captured images - REQUIRED
        images_data = request.form.getlist('captured_images[]')
        if not images_data or len(images_data) < 4:
            flash('Minimum 4 photos required!', 'error')
            return render_template('create_gate_pass.html', divisions=divisions, departments=departments)
        
        images_json = save_captured_images(images_data) if images_data else '[]'
        
        try:
            # Generate pass number
            pass_number = f"GP{datetime.now().strftime('%Y%m%d%H%M%S')}"
            
            # Insert gate pass
            cursor.execute('''
                INSERT INTO gate_passes (
                    pass_number, created_by, division_id, department_id, material_description,
                    destination, purpose, material_type, material_status, expected_return_date,
                    receiver_name, receiver_contact, send_date, images, status
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'pending_dept')
            ''', (
                pass_number, session['user_id'], division_id, department_id, material_description,
                destination, purpose, material_type, material_status, expected_return_date,
                receiver_name, receiver_contact, send_date, images_json
            ))
            
            gate_pass_id = cursor.lastrowid
            
            # Generate QR codes
            qr_data_form = generate_gate_pass_qr_data(gate_pass_id, pass_number)
            qr_data_sticker = generate_gate_pass_qr_data(gate_pass_id, f"{pass_number}_STICKER")
            
            cursor.execute('''
                UPDATE gate_passes 
                SET qr_code_form = %s, qr_code_sticker = %s 
                WHERE id = %s
            ''', (qr_data_form, qr_data_sticker, gate_pass_id))
            
            # Get department head for notification
            cursor.execute('''
                SELECT u.id, u.name 
                FROM users u 
                JOIN departments d ON u.department_id = d.id 
                WHERE d.id = %s AND u.role = 'department_head' AND u.status = 'approved'
            ''', (department_id,))
            
            dept_heads = dict_fetchall(cursor)
            if dept_heads:
                for dept_head in dept_heads:
                    create_notification(
                        dept_head['id'],
                        f"New Gate Pass {pass_number} requires your approval",
                        'approval',
                        gate_pass_id
                    )
                flash('Gate Pass created successfully! Waiting for department head approval.', 'success')
            else:
                # If no department head, send to store directly
                cursor.execute('UPDATE gate_passes SET status = "pending_store" WHERE id = %s', (gate_pass_id,))
                
                # Notify store managers
                cursor.execute('SELECT id FROM users WHERE role = "store_manager" AND status = "approved"')
                store_managers = dict_fetchall(cursor)
                for store_manager in store_managers:
                    create_notification(
                        store_manager['id'],
                        f"New Gate Pass {pass_number} requires store approval (No department head found)",
                        'approval',
                        gate_pass_id
                    )
                flash('Gate Pass created successfully! Sent directly to store for approval.', 'success')
            
            conn.commit()
            return redirect(url_for('gate_pass.gate_pass_list'))
            
        except Exception as e:
            conn.rollback()
            flash(f'Error creating gate pass: {str(e)}', 'error')
            print(f"Gate pass creation error: {e}")
        finally:
            cursor.close()
            conn.close()
    
    cursor.close()
    conn.close()
    
    return render_template('create_gate_pass.html', divisions=divisions, departments=departments)

@gate_pass_bp.route('/gate_pass_list')
def gate_pass_list():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    
    conn = get_db_connection()
    if conn is None:
        flash('Database connection failed!', 'error')
        return render_template('gate_pass_list.html', gate_passes=[])
    
    cursor = conn.cursor()
    
    try:
        if session['role'] == 'system_admin':
            # System Admin can see all gate passes
            cursor.execute('''
                SELECT gp.*, u.name as creator_name, d.name as department_name, dv.name as division_name
                FROM gate_passes gp 
                JOIN users u ON gp.created_by = u.id 
                JOIN departments d ON gp.department_id = d.id 
                JOIN divisions dv ON gp.division_id = dv.id 
                ORDER BY gp.created_at DESC
            ''')
        
        elif session['role'] == 'store_manager':
            # Store Manager can see gate passes for their store
            store_location = 'store_1' if 'store1' in session['username'] else 'store_2'
            cursor.execute('''
                SELECT gp.*, u.name as creator_name, d.name as department_name, dv.name as division_name
                FROM gate_passes gp 
                JOIN users u ON gp.created_by = u.id 
                JOIN departments d ON gp.department_id = d.id 
                JOIN divisions dv ON gp.division_id = dv.id 
                WHERE gp.store_location = %s 
                ORDER BY gp.created_at DESC
            ''', (store_location,))
        
        elif session['role'] == 'department_head':
            # Department Head can see gate passes from their department
            cursor.execute('''
                SELECT gp.*, u.name as creator_name, d.name as department_name, dv.name as division_name
                FROM gate_passes gp 
                JOIN users u ON gp.created_by = u.id 
                JOIN departments d ON gp.department_id = d.id 
                JOIN divisions dv ON gp.division_id = dv.id 
                WHERE gp.department_id IN (
                    SELECT id FROM departments WHERE name = %s
                )
                ORDER BY gp.created_at DESC
            ''', (session['department'],))
        
        elif session['role'] == 'security':
            # Security can see gate passes pending security approval
            cursor.execute('''
                SELECT gp.*, u.name as creator_name, d.name as department_name, dv.name as division_name
                FROM gate_passes gp 
                JOIN users u ON gp.created_by = u.id 
                JOIN departments d ON gp.department_id = d.id 
                JOIN divisions dv ON gp.division_id = dv.id 
                WHERE gp.status = 'pending_security'
                ORDER BY gp.created_at DESC
            ''')
        
        else:
            # Regular user can only see their own gate passes
            cursor.execute('''
                SELECT gp.*, u.name as creator_name, d.name as department_name, dv.name as division_name
                FROM gate_passes gp 
                JOIN users u ON gp.created_by = u.id 
                JOIN departments d ON gp.department_id = d.id 
                JOIN divisions dv ON gp.division_id = dv.id 
                WHERE gp.created_by = %s 
                ORDER BY gp.created_at DESC
            ''', (session['user_id'],))
        
        gate_passes = dict_fetchall(cursor)
    except Exception as e:
        print(f"Gate pass list error: {e}")
        gate_passes = []
    finally:
        cursor.close()
        conn.close()
    
    return render_template('gate_pass_list.html', gate_passes=gate_passes)

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
        
        # Check permissions
        if session['role'] == 'department_head':
            cursor.execute('SELECT name FROM departments WHERE id = %s', (gate_pass['department_id'],))
            dept = cursor.fetchone()
            if not dept or dept[0] != session['department']:
                flash('Access denied! You can only view gate passes from your department.', 'error')
                return redirect(url_for('gate_pass.gate_pass_list'))
        
        elif session['role'] == 'store_manager':
            if gate_pass['store_location'] != ('store_1' if 'store1' in session['username'] else 'store_2'):
                flash('Access denied! You can only view gate passes from your store.', 'error')
                return redirect(url_for('gate_pass.gate_pass_list'))
        
        elif session['role'] not in ['system_admin', 'security']:
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
        
    except Exception as e:
        print(f"Gate pass detail error: {e}")
        flash('Error loading gate pass details!', 'error')
        return redirect(url_for('gate_pass.gate_pass_list'))
    finally:
        cursor.close()
        conn.close()
    
    return render_template('gate_pass_detail.html', gate_pass=gate_pass, now=datetime.now())

@gate_pass_bp.route('/approve_gate_pass/<int:gate_pass_id>/<action>')
def approve_gate_pass(gate_pass_id, action):
    if 'user_id' not in session or session['role'] not in ['department_head', 'store_manager', 'security']:
        return jsonify({'success': False, 'message': 'Access denied!'})
    
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
        
        current_time = datetime.now()
        message = ''
        
        # Department Head Approval
        if session['role'] == 'department_head' and gate_pass['status'] == 'pending_dept':
            # Check if gate pass belongs to department head's department
            cursor.execute('SELECT name FROM departments WHERE id = %s', (gate_pass['department_id'],))
            dept = cursor.fetchone()
            if not dept or dept[0] != session['department']:
                return jsonify({'success': False, 'message': 'You can only approve gate passes from your department!'})
            
            if action == 'approve':
                cursor.execute('''
                    UPDATE gate_passes 
                    SET department_approval = 'approved', 
                        department_approval_date = %s,
                        status = 'pending_store'
                    WHERE id = %s
                ''', (current_time, gate_pass_id))
                
                # Notify store managers
                cursor.execute('SELECT id FROM users WHERE role = "store_manager" AND status = "approved"')
                store_managers = dict_fetchall(cursor)
                for store_manager in store_managers:
                    create_notification(
                        store_manager['id'],
                        f"Gate Pass {gate_pass['pass_number']} requires store approval",
                        'approval',
                        gate_pass_id
                    )
                
                # Notify creator
                create_notification(
                    gate_pass['created_by'],
                    f"Gate Pass {gate_pass['pass_number']} approved by department head, waiting for store approval",
                    'status',
                    gate_pass_id
                )
                
                message = 'Gate Pass approved! Sent to store for approval.'
                
            elif action == 'reject':
                cursor.execute('''
                    UPDATE gate_passes 
                    SET department_approval = 'rejected', 
                        status = 'rejected'
                    WHERE id = %s
                ''', (gate_pass_id,))
                
                create_notification(
                    gate_pass['created_by'],
                    f"Gate Pass {gate_pass['pass_number']} was rejected by department head",
                    'status',
                    gate_pass_id
                )
                message = 'Gate Pass rejected!'
                
            elif action == 'inquiry':
                cursor.execute('''
                    UPDATE gate_passes 
                    SET department_approval = 'inquiry',
                        status = 'inquiry'
                    WHERE id = %s
                ''', (gate_pass_id,))
                
                # Notify store managers for inquiry
                cursor.execute('SELECT id FROM users WHERE role = "store_manager" AND status = "approved"')
                store_managers = dict_fetchall(cursor)
                for store_manager in store_managers:
                    create_notification(
                        store_manager['id'],
                        f"INQUIRY: Gate Pass {gate_pass['pass_number']} requires investigation",
                        'approval',
                        gate_pass_id
                    )
                
                # Notify creator
                create_notification(
                    gate_pass['created_by'],
                    f"Gate Pass {gate_pass['pass_number']} has been marked for inquiry. Store will investigate.",
                    'status',
                    gate_pass_id
                )
                
                message = 'Inquiry raised! Store will investigate.'
            else:
                return jsonify({'success': False, 'message': 'Invalid action!'})
        
        # Store Manager Approval
        elif session['role'] == 'store_manager' and gate_pass['status'] == 'pending_store':
            # Check store location
            store_location = 'store_1' if 'store1' in session['username'] else 'store_2'
            if gate_pass['store_location'] and gate_pass['store_location'] != store_location:
                return jsonify({'success': False, 'message': 'You can only approve gate passes from your store!'})
            
            if action == 'approve':
                # Assign store location if not already assigned
                if not gate_pass['store_location']:
                    store_location = 'store_1' if 'store1' in session['username'] else 'store_2'
                    cursor.execute('''
                        UPDATE gate_passes 
                        SET store_approval = 'approved', 
                            store_approval_date = %s,
                            store_location = %s,
                            status = 'pending_security'
                        WHERE id = %s
                    ''', (current_time, store_location, gate_pass_id))
                else:
                    cursor.execute('''
                        UPDATE gate_passes 
                        SET store_approval = 'approved', 
                            store_approval_date = %s,
                            status = 'pending_security'
                        WHERE id = %s
                    ''', (current_time, gate_pass_id))
                
                # Notify security
                cursor.execute('SELECT id FROM users WHERE role = "security" AND status = "approved"')
                security_users = dict_fetchall(cursor)
                for security_user in security_users:
                    create_notification(
                        security_user['id'],
                        f"Gate Pass {gate_pass['pass_number']} requires security approval",
                        'approval',
                        gate_pass_id
                    )
                
                # Notify creator
                create_notification(
                    gate_pass['created_by'],
                    f"Gate Pass {gate_pass['pass_number']} approved by store, waiting for security approval",
                    'status',
                    gate_pass_id
                )
                
                message = 'Gate Pass approved! Sent to security for final approval.'
                
            elif action == 'reject':
                cursor.execute('''
                    UPDATE gate_passes 
                    SET store_approval = 'rejected', 
                        status = 'rejected'
                    WHERE id = %s
                ''', (gate_pass_id,))
                
                create_notification(
                    gate_pass['created_by'],
                    f"Gate Pass {gate_pass['pass_number']} was rejected by store",
                    'status',
                    gate_pass_id
                )
                message = 'Gate Pass rejected!'
            else:
                return jsonify({'success': False, 'message': 'Invalid action!'})
        
        # Security Approval
        elif session['role'] == 'security' and gate_pass['status'] == 'pending_security':
            if action == 'approve':
                cursor.execute('''
                    UPDATE gate_passes 
                    SET security_approval = 'approved', 
                        security_approval_date = %s,
                        status = 'approved'
                    WHERE id = %s
                ''', (current_time, gate_pass_id))
                
                create_notification(
                    gate_pass['created_by'],
                    f"✅ Gate Pass {gate_pass['pass_number']} has been approved! You can now print and send the material.",
                    'status',
                    gate_pass_id
                )
                
                # Notify department users about approval
                cursor.execute('''
                    SELECT u.id FROM users u 
                    WHERE u.department_id = %s AND u.status = 'approved'
                ''', (gate_pass['department_id'],))
                
                dept_users = dict_fetchall(cursor)
                for user in dept_users:
                    if user['id'] != gate_pass['created_by']:
                        create_notification(
                            user['id'],
                            f"📦 Gate Pass {gate_pass['pass_number']} from your department has been approved",
                            'status',
                            gate_pass_id
                        )
                
                message = 'Gate Pass approved! Ready for printing.'
                
            elif action == 'reject':
                cursor.execute('''
                    UPDATE gate_passes 
                    SET security_approval = 'rejected', 
                        status = 'rejected'
                    WHERE id = %s
                ''', (gate_pass_id,))
                
                create_notification(
                    gate_pass['created_by'],
                    f"Gate Pass {gate_pass['pass_number']} was rejected by security",
                    'status',
                    gate_pass_id
                )
                message = 'Gate Pass rejected!'
            else:
                return jsonify({'success': False, 'message': 'Invalid action!'})
        
        # Store Manager can also handle inquiries
        elif session['role'] == 'store_manager' and gate_pass['status'] == 'inquiry':
            if action == 'approve':
                cursor.execute('''
                    UPDATE gate_passes 
                    SET department_approval = 'approved',
                        store_approval = 'approved', 
                        store_approval_date = %s,
                        status = 'pending_security'
                    WHERE id = %s
                ''', (current_time, gate_pass_id))
                
                create_notification(
                    gate_pass['created_by'],
                    f"Gate Pass {gate_pass['pass_number']} inquiry resolved and sent to security!",
                    'status',
                    gate_pass_id
                )
                message = 'Gate Pass approved after inquiry! Sent to security.'
                
            elif action == 'reject':
                cursor.execute('''
                    UPDATE gate_passes 
                    SET store_approval = 'rejected', 
                        status = 'rejected'
                    WHERE id = %s
                ''', (gate_pass_id,))
                
                create_notification(
                    gate_pass['created_by'],
                    f"Gate Pass {gate_pass['pass_number']} was rejected by store after inquiry",
                    'status',
                    gate_pass_id
                )
                message = 'Gate Pass rejected after inquiry!'
            else:
                return jsonify({'success': False, 'message': 'Invalid action!'})
        else:
            return jsonify({'success': False, 'message': 'Invalid approval state!'})
        
        conn.commit()
        return jsonify({'success': True, 'message': message})
        
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'message': f'Approval error: {str(e)}'})
    finally:
        cursor.close()
        conn.close()

@gate_pass_bp.route('/verify_qr_match', methods=['POST'])
def verify_qr_match():
    """QR verification for security at gate"""
    if 'user_id' not in session or session['role'] != 'security':
        return jsonify({'success': False, 'message': 'Access denied!'})
    
    form_qr = request.json.get('form_qr')
    sticker_qr = request.json.get('sticker_qr')
    gate_pass_id = request.json.get('gate_pass_id')
    
    from qr_utils import verify_qr_code
    
    conn = get_db_connection()
    if conn is None:
        return jsonify({'success': False, 'message': 'Database connection failed'})
    
    cursor = conn.cursor()
    
    try:
        # Get current session information
        cursor.execute("SELECT session_token FROM gate_passes WHERE id = %s", (gate_pass_id,))
        result = cursor.fetchone()
        current_session = result[0] if result else None
        
        form_valid, form_data = verify_qr_code(form_qr, current_session)
        sticker_valid, sticker_data = verify_qr_code(sticker_qr, current_session)
        
        if form_valid and sticker_valid:
            if (form_data.get('gate_pass_id') == str(gate_pass_id) and
                form_data.get('gate_pass_id') == sticker_data.get('gate_pass_id') and
                form_data.get('pass_number') in sticker_data.get('pass_number')):
                
                return jsonify({
                    'success': True, 
                    'message': '✅ QR codes matched successfully! Material verified.',
                    'return_eligible': True
                })
            else:
                return jsonify({
                    'success': False, 
                    'message': "❌ QR codes don't match - please verify physical items"
                })
        else:
            return jsonify({
                'success': False, 
                'message': 'Invalid or expired QR codes'
            })
            
    except Exception as e:
        return jsonify({'success': False, 'message': f'Verification error: {str(e)}'})
    finally:
        cursor.close()
        conn.close()

@gate_pass_bp.route('/create_store_request', methods=['POST'])
def create_store_request():
    """Security creates store request for sending materials"""
    if 'user_id' not in session or session['role'] != 'security':
        return jsonify({'success': False, 'message': 'Access denied!'})
    
    material_description = request.form['material_description']
    destination = request.form['destination']
    purpose = request.form['purpose']
    receiver_name = request.form['receiver_name']
    receiver_contact = request.form.get('receiver_contact')
    urgent = request.form.get('urgent', False)
    
    conn = get_db_connection()
    if conn is None:
        return jsonify({'success': False, 'message': 'Database connection failed!'})
    
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            INSERT INTO store_requests (
                security_user_id, material_description, destination, purpose,
                receiver_name, receiver_contact, urgent, status
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, 'pending')
        ''', (session['user_id'], material_description, destination, purpose,
              receiver_name, receiver_contact, urgent))
        
        conn.commit()
        
        # Notify System Administrator
        cursor.execute('SELECT id FROM users WHERE role = "system_admin" AND status = "approved"')
        admins = dict_fetchall(cursor)
        for admin in admins:
            create_notification(
                admin['id'],
                f"🛒 New Store Request from Security: {material_description}",
                'approval',
                None
            )
        
        return jsonify({'success': True, 'message': 'Store request submitted! Waiting for admin approval.'})
        
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'message': f'Error creating store request: {str(e)}'})
    finally:
        cursor.close()
        conn.close()