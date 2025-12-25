# notifications.py
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
    conn = get_db_connection()
    if conn is None:
        return
    
    cursor = conn.cursor()
    
    try:
        # Find gate passes that are overdue
        cursor.execute('''
            SELECT gp.*, u.name as creator_name, u.id as creator_id
            FROM gate_passes gp
            JOIN users u ON gp.created_by = u.id
            WHERE gp.material_type = 'returnable' 
            AND gp.expected_return_date < NOW() 
            AND gp.actual_return_date IS NULL
            AND gp.status = 'approved'
        ''')
        
        overdue_passes = dict_fetchall(cursor)
        
        for gate_pass in overdue_passes:
            # Notify creator
            return_date = gate_pass['expected_return_date']
            if isinstance(return_date, datetime):
                return_date_str = return_date.strftime('%Y-%m-%d %H:%M')
            else:
                return_date_str = str(return_date)
                
            message = f"Gate Pass {gate_pass['pass_number']} is overdue! Expected return: {return_date_str}"
            create_notification(
                gate_pass['creator_id'], 
                message, 
                'alert', 
                gate_pass['id']
            )
            
            # Notify HR/Admin users
            cursor.execute('''
                SELECT id FROM users WHERE role IN ('hr_admin', 'department_head') AND status = 'approved'
            ''')
            admin_users = dict_fetchall(cursor)
            
            for admin in admin_users:
                create_notification(
                    admin['id'],
                    f"OVERDUE: Gate Pass {gate_pass['pass_number']} created by {gate_pass['creator_name']}",
                    'alert',
                    gate_pass['id']
                )
    
    except Exception as e:
        print(f"Error checking overdue gate passes: {e}")
    finally:
        cursor.close()
        conn.close()

def start_notification_scheduler():
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