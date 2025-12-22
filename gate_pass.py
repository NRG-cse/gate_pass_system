# gate_pass.py - COMPLETELY FIXED GATE PASS CREATION
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
    """Save base64 encoded images to filesystem"""
    saved_paths = []
    upload_folder = 'static/uploads'
    
    # Create upload folder if not exists
    if not os.path.exists(upload_folder):
        os.makedirs(upload_folder, exist_ok=True)
    
    for i, image_data in enumerate(images_data):
        if image_data and isinstance(image_data, str) and image_data.startswith('data:image'):
            try:
                # Remove data:image/jpeg;base64, prefix
                if ',' in image_data:
                    header, encoded = image_data.split(',', 1)
                else:
                    encoded = image_data
                
                # Skip if too short
                if len(encoded) < 100:
                    print(f"⚠️ Image {i+1}: Too short, skipping")
                    continue
                
                image_bytes = base64.b64decode(encoded)
                
                # Generate unique filename
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                filename = f"material_{timestamp}_{i+1}.jpg"
                filepath = os.path.join(upload_folder, filename)
                
                with open(filepath, 'wb') as f:
                    f.write(image_bytes)
                
                saved_paths.append(f"uploads/{filename}")
                print(f"✅ Image {i+1} saved: {filename}")
            except Exception as e:
                print(f"❌ Error saving image {i+1}: {e}")
                continue
        elif image_data:
            # If it's already a file path
            saved_paths.append(image_data)
    
    print(f"📁 Total images saved: {len(saved_paths)}")
    return json.dumps(saved_paths)

@gate_pass_bp.route('/create_gate_pass', methods=['GET', 'POST'])
def create_gate_pass():
    """Create new gate pass - SIMPLE AND WORKING VERSION"""
    
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    
    # Check if user can create gate pass
    if session['role'] in ['security', 'store_manager']:
        flash(f'{session["role"].replace("_", " ").title()} cannot create gate passes!', 'error')
        return redirect(url_for('dashboard'))
    
    conn = get_db_connection()
    if conn is None:
        flash('Database connection failed!', 'error')
        return render_template('create_gate_pass.html', divisions=[], departments=[])
    
    cursor = conn.cursor()
    
    # Get divisions and departments for dropdown
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
        print(f"Error fetching divisions/departments: {e}")
        divisions = []
        departments = []
    
    if request.method == 'POST':
        print("\n" + "="*80)
        print("🚀 FORM SUBMISSION RECEIVED - PROCESSING...")
        print("="*80)
        
        # Get form data using get() to avoid KeyError
        try:
            division_id = request.form.get('division_id', '').strip()
            department_id = request.form.get('department_id', '').strip()
            material_description = request.form.get('material_description', '').strip()
            destination = request.form.get('destination', '').strip()
            purpose = request.form.get('purpose', '').strip()
            material_type = request.form.get('material_type', '').strip()
            material_status = request.form.get('material_status', '').strip()
            receiver_name = request.form.get('receiver_name', '').strip()
            receiver_contact = request.form.get('receiver_contact', '').strip()
            send_date_str = request.form.get('send_date', '').strip()
            expected_return_date = request.form.get('expected_return_date', '').strip()
            vehicle_number = request.form.get('vehicle_number', '').strip()
            receiver_id = request.form.get('receiver_id', '').strip()
            delivery_address = request.form.get('delivery_address', '').strip()
            special_instructions = request.form.get('special_instructions', '').strip()
            urgent = request.form.get('urgent', 'false') == 'true'
            
            # Get captured images
            captured_images = request.form.getlist('captured_images[]')
            
            print(f"📊 Form Data Summary:")
            print(f"  Division ID: {division_id}")
            print(f"  Department ID: {department_id}")
            print(f"  Material: {material_description[:50]}...")
            print(f"  Destination: {destination}")
            print(f"  Receiver: {receiver_name}")
            print(f"  Photos: {len(captured_images)} received")
            
            # Validate required fields
            errors = []
            
            if not division_id:
                errors.append("Please select a Division")
            if not department_id:
                errors.append("Please select a Department")
            if not material_description:
                errors.append("Please enter Material Description")
            if not destination:
                errors.append("Please enter Destination")
            if not purpose:
                errors.append("Please enter Purpose")
            if not material_type:
                errors.append("Please select Material Type")
            if not material_status:
                errors.append("Please select Material Status")
            if not receiver_name:
                errors.append("Please enter Receiver Name")
            if not receiver_contact:
                errors.append("Please enter Receiver Contact")
            if not send_date_str:
                errors.append("Please select Send Date")
            
            # Validate photos
            valid_images = []
            for i, img in enumerate(captured_images):
                if img and img.strip() and img.startswith('data:image'):
                    valid_images.append(img.strip())
            
            if len(valid_images) < 4:
                errors.append(f"Minimum 4 photos required (you have {len(valid_images)})")
            
            if errors:
                for error in errors:
                    flash(f'❌ {error}', 'error')
                cursor.close()
                conn.close()
                return render_template('create_gate_pass.html', 
                                     divisions=divisions, 
                                     departments=departments,
                                     form_data=request.form)
            
            # Process dates
            send_date = None
            if send_date_str:
                try:
                    if 'T' in send_date_str:
                        send_date = datetime.strptime(send_date_str, '%Y-%m-%dT%H:%M')
                    else:
                        send_date = datetime.strptime(send_date_str, '%Y-%m-%d %H:%M:%S')
                except:
                    send_date = datetime.now()
            else:
                send_date = datetime.now()
            
            return_date = None
            if material_type == 'returnable' and expected_return_date:
                try:
                    if 'T' in expected_return_date:
                        return_date = datetime.strptime(expected_return_date, '%Y-%m-%dT%H:%M')
                    else:
                        return_date = datetime.strptime(expected_return_date, '%Y-%m-%d %H:%M:%S')
                except:
                    return_date = None
            
            # Save images
            images_json = save_captured_images(valid_images)
            
            # Generate pass number
            pass_number = f"GP{datetime.now().strftime('%Y%m%d%H%M%S')}"
            print(f"🔢 Generated Pass Number: {pass_number}")
            
            # Insert into database
            cursor.execute('''
                INSERT INTO gate_passes (
                    pass_number, created_by, division_id, department_id, 
                    material_description, destination, purpose, material_type, 
                    material_status, expected_return_date, receiver_name, 
                    receiver_contact, receiver_id, delivery_address, send_date,
                    vehicle_number, special_instructions, images, status, urgent
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'pending_dept', %s)
            ''', (
                pass_number, 
                session['user_id'], 
                division_id, 
                department_id, 
                material_description,
                destination, 
                purpose, 
                material_type, 
                material_status, 
                return_date,
                receiver_name, 
                receiver_contact, 
                receiver_id or None, 
                delivery_address, 
                send_date,
                vehicle_number, 
                special_instructions, 
                images_json, 
                urgent
            ))
            
            gate_pass_id = cursor.lastrowid
            print(f"✅ Gate Pass inserted! ID: {gate_pass_id}")
            
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
                WHERE u.department_id = %s 
                AND u.role = 'department_head' 
                AND u.status = 'approved'
                LIMIT 1
            ''', (department_id,))
            
            dept_head = cursor.fetchone()
            if dept_head:
                create_notification(
                    dept_head['id'],
                    f"📋 New Gate Pass {pass_number} requires your approval",
                    'approval',
                    gate_pass_id
                )
                flash_message = f'✅ Gate Pass {pass_number} created successfully! Waiting for department head approval.'
                print(f"📢 Notified department head")
            else:
                # If no department head, send to store
                cursor.execute('UPDATE gate_passes SET status = "pending_store" WHERE id = %s', (gate_pass_id,))
                
                # Notify store managers
                cursor.execute('SELECT id, name FROM users WHERE role = "store_manager" AND status = "approved"')
                store_managers = dict_fetchall(cursor)
                for manager in store_managers:
                    create_notification(
                        manager['id'],
                        f"🏪 New Gate Pass {pass_number} requires store approval",
                        'store_notification',
                        gate_pass_id
                    )
                flash_message = f'✅ Gate Pass {pass_number} created successfully! Sent to store for approval.'
                print(f"📢 Notified {len(store_managers)} store managers")
            
            # Notify creator
            create_notification(
                session['user_id'],
                f"✅ Your Gate Pass {pass_number} has been created successfully!",
                'status',
                gate_pass_id
            )
            
            conn.commit()
            print(f"🎉 SUCCESS! Gate Pass {pass_number} fully created!")
            
            flash(flash_message, 'success')
            
            cursor.close()
            conn.close()
            
            # Return success for AJAX
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({
                    'success': True,
                    'message': flash_message,
                    'redirect': url_for('gate_pass.gate_pass_list')
                })
            
            # Normal redirect
            return redirect(url_for('gate_pass.gate_pass_list'))
            
        except MySQLdb.Error as e:
            conn.rollback()
            error_msg = f'❌ Database Error: {str(e)}'
            print(f"❌ MYSQL ERROR: {e}")
            
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'success': False, 'message': error_msg})
            
            flash(error_msg, 'error')
            
        except Exception as e:
            conn.rollback()
            error_msg = f'❌ System Error: {str(e)}'
            print(f"❌ SYSTEM ERROR: {e}")
            import traceback
            traceback.print_exc()
            
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'success': False, 'message': error_msg})
            
            flash(error_msg, 'error')
        
        finally:
            cursor.close()
            conn.close()
        
        # Return to form with errors
        return render_template('create_gate_pass.html', 
                             divisions=divisions, 
                             departments=departments,
                             form_data=request.form)
    
    # GET request - show form
    print("📄 GET request - showing form")
    
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
        # For Store Managers - Show ALL gate passes AND their store requests
        if session['role'] == 'store_manager':
            store_location = 'store_1' if 'store1' in session['username'] else 'store_2'
            
            # Get ALL gate passes (for viewing only)
            cursor.execute('''
                SELECT gp.*, u.name as creator_name, d.name as department_name, dv.name as division_name
                FROM gate_passes gp 
                JOIN users u ON gp.created_by = u.id 
                JOIN departments d ON gp.department_id = d.id 
                JOIN divisions dv ON gp.division_id = dv.id 
                WHERE gp.status IN ('pending_store', 'approved', 'in_transit')
                ORDER BY gp.created_at DESC
            ''')
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
        
        # For Department Head - Only their department's gate passes
        elif session['role'] == 'department_head':
            # Get department head's department
            cursor.execute('SELECT department_id FROM users WHERE id = %s', (session['user_id'],))
            user_dept = cursor.fetchone()
            
            if user_dept:
                department_id = user_dept[0]
                cursor.execute('''
                    SELECT gp.*, u.name as creator_name, d.name as department_name, dv.name as division_name
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
            
            return render_template('gate_pass_list.html', gate_passes=gate_passes, store_requests=[])
        
        # For Security - Only security pending passes
        elif session['role'] == 'security':
            cursor.execute('''
                SELECT gp.*, u.name as creator_name, d.name as department_name, dv.name as division_name
                FROM gate_passes gp 
                JOIN users u ON gp.created_by = u.id 
                JOIN departments d ON gp.department_id = d.id 
                JOIN divisions dv ON gp.division_id = dv.id 
                WHERE gp.status = 'pending_security'
                ORDER BY gp.created_at DESC
            ''')
            gate_passes = dict_fetchall(cursor)
            
            return render_template('gate_pass_list.html', gate_passes=gate_passes, store_requests=[])
        
        # For System Admin - All gate passes
        elif session['role'] == 'system_admin':
            cursor.execute('''
                SELECT gp.*, u.name as creator_name, d.name as department_name, dv.name as division_name
                FROM gate_passes gp 
                JOIN users u ON gp.created_by = u.id 
                JOIN departments d ON gp.department_id = d.id 
                JOIN divisions dv ON gp.division_id = dv.id 
                ORDER BY gp.created_at DESC
            ''')
            gate_passes = dict_fetchall(cursor)
            
            return render_template('gate_pass_list.html', gate_passes=gate_passes, store_requests=[])
        
        # For Regular User - Only their own passes
        else:
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
            
            return render_template('gate_pass_list.html', gate_passes=gate_passes, store_requests=[])
        
    except Exception as e:
        print(f"Gate pass list error: {e}")
        gate_passes = []
        store_requests = []
    finally:
        cursor.close()
        conn.close()
    
    return render_template('gate_pass_list.html', gate_passes=gate_passes, store_requests=[])

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
        
        # Check permissions for store manager (can view all)
        if session['role'] == 'store_manager':
            # Store managers can view any gate pass
            pass
        
        # Check permissions for department head
        elif session['role'] == 'department_head':
            cursor.execute('SELECT department_id FROM users WHERE id = %s', (session['user_id'],))
            dept = cursor.fetchone()
            if not dept or dept[0] != gate_pass['department_id']:
                flash('Access denied! You can only view gate passes from your department.', 'error')
                return redirect(url_for('gate_pass.gate_pass_list'))
        
        # Check for regular users
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
        
        # Get approval history
        cursor.execute('''
            SELECT * FROM gate_pass_approvals 
            WHERE gate_pass_id = %s 
            ORDER BY created_at DESC
        ''', (gate_pass_id,))
        approvals = dict_fetchall(cursor)
        
    except Exception as e:
        print(f"Gate pass detail error: {e}")
        flash('Error loading gate pass details!', 'error')
        return redirect(url_for('gate_pass.gate_pass_list'))
    finally:
        cursor.close()
        conn.close()
    
    return render_template('gate_pass_detail.html', gate_pass=gate_pass, approvals=approvals, now=datetime.now())

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
            cursor.execute('''
                SELECT id FROM users 
                WHERE role IN ('system_admin') AND status = 'approved'
            ''')
            admins = dict_fetchall(cursor)
            
            for admin in admins:
                create_notification(
                    admin['id'],
                    f"🏪 Store Request from {session['name']} ({store_location}): {material_description}",
                    'approval',
                    request_id
                )
            
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
        create_notification(
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