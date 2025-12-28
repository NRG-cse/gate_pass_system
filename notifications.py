# notifications.py - COMPLETE VERSION WITH OVERDUE ALARM SCHEDULER
import MySQLdb
from config import config
from datetime import datetime, timedelta
import time
import threading
from models import get_db_connection, dict_fetchall

def create_notification(user_id, message, notification_type, gate_pass_id=None):
    """Create notification with better error handling"""
    conn = get_db_connection()
    if conn is None:
        print("Failed to get database connection for notification")
        return
    
    cursor = conn.cursor()
    
    try:
        # Use simple INSERT without transactions to avoid locks
        cursor.execute('''
            INSERT INTO notifications (user_id, gate_pass_id, message, type, created_at)
            VALUES (%s, %s, %s, %s, NOW())
        ''', (user_id, gate_pass_id, message, notification_type))
        
        conn.commit()
        print(f"✅ Notification created for user {user_id}: {message[:50]}...")
        
    except MySQLdb.OperationalError as oe:
        if 'Lock wait timeout' in str(oe):
            print(f"⚠️ Lock timeout when creating notification, retrying...")
            try:
                # Try with a new connection
                cursor.close()
                conn.close()
                
                conn2 = get_db_connection()
                cursor2 = conn2.cursor()
                cursor2.execute('''
                    INSERT INTO notifications (user_id, gate_pass_id, message, type, created_at)
                    VALUES (%s, %s, %s, %s, NOW())
                ''', (user_id, gate_pass_id, message, notification_type))
                conn2.commit()
                cursor2.close()
                conn2.close()
                print(f"✅ Notification created on retry for user {user_id}")
            except Exception as e2:
                print(f"❌ Failed to create notification even on retry: {e2}")
        else:
            print(f"❌ MySQL error creating notification: {oe}")
    except Exception as e:
        print(f"❌ Error creating notification: {e}")
    finally:
        try:
            cursor.close()
            conn.close()
        except:
            pass

def get_user_notifications(user_id, limit=10):
    conn = get_db_connection()
    if conn is None:
        return []
    
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            SELECT * FROM notifications 
            WHERE user_id = %s 
            ORDER BY created_at DESC
            LIMIT %s
        ''', (user_id, limit))
        
        notifications = dict_fetchall(cursor)
    except Exception as e:
        print(f"Error getting notifications: {e}")
        notifications = []
    finally:
        cursor.close()
        conn.close()
    
    return notifications

def mark_notification_read(notification_id):
    conn = get_db_connection()
    if conn is None:
        return
    
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            UPDATE notifications SET is_read = TRUE WHERE id = %s
        ''', (notification_id,))
        
        conn.commit()
    except Exception as e:
        print(f"Error marking notification read: {e}")
        conn.rollback()
    finally:
        cursor.close()
        conn.close()

def check_overdue_gate_passes():
    """Check for overdue gate passes and send notifications"""
    conn = get_db_connection()
    if conn is None:
        return
    
    cursor = conn.cursor()
    
    try:
        # Find gate passes that are overdue
        cursor.execute('''
            SELECT gp.*, u.name as creator_name, u.id as creator_id,
                   u.department_id as creator_dept_id,
                   TIMESTAMPDIFF(DAY, gp.expected_return_date, NOW()) as overdue_days,
                   d.name as department_name,
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
            WHERE gp.material_type = 'returnable' 
            AND gp.expected_return_date < NOW() 
            AND gp.actual_return_date IS NULL
            AND gp.status = 'approved'
            AND (gp.last_overdue_notification IS NULL OR gp.last_overdue_notification < DATE_SUB(NOW(), INTERVAL 24 HOUR))
        ''')
        
        overdue_passes = dict_fetchall(cursor)
        
        for gate_pass in overdue_passes:
            overdue_days = gate_pass['overdue_days'] or 0
            
            # Determine severity
            if overdue_days == 1:
                # First day overdue - gentle reminder
                message = f"⏰ REMINDER: Gate Pass {gate_pass['pass_number']} is 1 day overdue!"
                notif_type = 'reminder'
                
            elif overdue_days <= 3:
                # 2-3 days - warning
                message = f"⚠️ WARNING: Gate Pass {gate_pass['pass_number']} is {overdue_days} days overdue!"
                notif_type = 'warning'
                
            elif overdue_days <= 7:
                # 4-7 days - urgent
                message = f"🚨 URGENT: Gate Pass {gate_pass['pass_number']} is {overdue_days} days overdue!"
                notif_type = 'alert'
                
            else:
                # More than 7 days - critical
                message = f"🔥 CRITICAL: Gate Pass {gate_pass['pass_number']} is {overdue_days} days overdue!"
                notif_type = 'critical'
            
            # 1. Notify CREATOR
            create_notification(
                gate_pass['creator_id'], 
                message, 
                notif_type, 
                gate_pass['id']
            )
            
            # 2. Notify DEPARTMENT HEAD
            if gate_pass['dept_head_id']:
                create_notification(
                    gate_pass['dept_head_id'],
                    f"{message} Created by: {gate_pass['creator_name']}",
                    notif_type,
                    gate_pass['id']
                )
            
            # 3. Notify STORE MANAGER (if store was involved)
            if gate_pass['store_manager_id']:
                create_notification(
                    gate_pass['store_manager_id'],
                    f"🏪 Store Alert: Material from Gate Pass {gate_pass['pass_number']} is {overdue_days} day(s) overdue",
                    'store_alert',
                    gate_pass['id']
                )
            
            # 4. Notify ALL SYSTEM ADMINS for critical overdue (>7 days)
            if overdue_days > 7:
                cursor.execute('SELECT id FROM users WHERE role = "system_admin" AND status = "approved"')
                admins = dict_fetchall(cursor)
                for admin in admins:
                    create_notification(
                        admin['id'],
                        f"🔥 CRITICAL OVERDUE: Gate Pass {gate_pass['pass_number']} is {overdue_days} days overdue! Department: {gate_pass['department_name']}",
                        'critical',
                        gate_pass['id']
                    )
            
            # 5. Update last notification time
            cursor.execute('''
                UPDATE gate_passes 
                SET last_overdue_notification = NOW() 
                WHERE id = %s
            ''', (gate_pass['id'],))
        
        conn.commit()
        
    except Exception as e:
        print(f"Error checking overdue gate passes: {e}")
        conn.rollback()
    finally:
        cursor.close()
        conn.close()

def check_store_overdue_passes():
    """Check for overdue passes related to stores"""
    conn = get_db_connection()
    if conn is None:
        return
    
    cursor = conn.cursor()
    
    try:
        # Find store-related overdue passes
        cursor.execute('''
            SELECT gp.*, u.name as creator_name, 
                   d.name as department_name, gp.store_location,
                   TIMESTAMPDIFF(DAY, gp.expected_return_date, NOW()) as overdue_days
            FROM gate_passes gp
            JOIN users u ON gp.created_by = u.id
            JOIN departments d ON gp.department_id = d.id
            WHERE gp.material_type = 'returnable' 
            AND gp.expected_return_date < NOW() 
            AND gp.actual_return_date IS NULL
            AND gp.status = 'approved'
            AND gp.store_location IS NOT NULL
            AND (gp.last_store_notification IS NULL OR gp.last_store_notification < DATE_SUB(NOW(), INTERVAL 12 HOUR))
        ''')
        
        store_overdue_passes = dict_fetchall(cursor)
        
        for gate_pass in store_overdue_passes:
            store_location = gate_pass['store_location']
            overdue_days = gate_pass['overdue_days'] or 0
            
            # Notify store managers
            if store_location == 'store_1':
                store_username = 'store1'
            else:
                store_username = 'store2'
            
            cursor.execute('''
                SELECT id FROM users 
                WHERE username = %s 
                AND role = 'store_manager' 
                AND status = 'approved'
            ''', (store_username,))
            
            store_managers = dict_fetchall(cursor)
            for store_manager in store_managers:
                create_notification(
                    store_manager['id'],
                    f"🏪 Store Alert: Material from Gate Pass {gate_pass['pass_number']} is {overdue_days} day(s) overdue",
                    'store_alert',
                    gate_pass['id']
                )
            
            # Update last store notification time
            cursor.execute('''
                UPDATE gate_passes 
                SET last_store_notification = NOW() 
                WHERE id = %s
            ''', (gate_pass['id'],))
        
        conn.commit()
        
    except Exception as e:
        print(f"Error checking store overdue passes: {e}")
        conn.rollback()
    finally:
        cursor.close()
        conn.close()

def start_notification_scheduler():
    """Start scheduler for regular notification checking (every 3 hours)"""
    def scheduler():
        while True:
            try:
                check_overdue_gate_passes()
                time.sleep(10800)  # 3 hours in seconds
            except Exception as e:
                print(f"Error in notification scheduler: {e}")
                time.sleep(300)  # Wait 5 minutes before retrying
    
    thread = threading.Thread(target=scheduler, daemon=True)
    thread.start()
    print("✅ Notification scheduler started!")

def start_overdue_alarm_scheduler():
    """Start scheduler for continuous overdue checking (every 30 seconds)"""
    def alarm_scheduler():
        while True:
            try:
                # Check every 30 seconds for immediate alerts
                check_overdue_gate_passes()
                check_store_overdue_passes()
                time.sleep(30)
            except Exception as e:
                print(f"Alarm scheduler error: {e}")
                time.sleep(60)  # Wait 1 minute before retrying
    
    # Start in separate thread
    thread = threading.Thread(target=alarm_scheduler, daemon=True)
    thread.start()
    print("✅ Overdue alarm scheduler started!")