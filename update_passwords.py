# update_passwords.py
import MySQLdb
import hashlib

def hash_password(password):
    return hashlib.md5(password.encode('utf-8')).hexdigest()

def update_user_passwords():
    print("🔄 Updating user passwords to MD5 hashing...")
    
    try:
        conn = MySQLdb.connect(
            host='localhost',
            user='root',
            passwd='',
            db='gate_pass_system'
        )
        cursor = conn.cursor()
        
        # Get all users
        cursor.execute("SELECT id, username, password FROM users")
        users = cursor.fetchall()
        
        updated_count = 0
        for user in users:
            user_id, username, current_password = user
            
            # Check if password is already MD5 hashed (32 chars hex)
            if len(current_password) != 32 or not all(c in '0123456789abcdef' for c in current_password.lower()):
                # Password is not hashed, update it
                hashed_password = hash_password(current_password)
                cursor.execute("UPDATE users SET password = %s WHERE id = %s", (hashed_password, user_id))
                print(f"✅ Updated {username}: {current_password} -> {hashed_password}")
                updated_count += 1
            else:
                print(f"ℹ️  {username} password already MD5 hashed")
        
        conn.commit()
        cursor.close()
        conn.close()
        
        print(f"🎯 Updated {updated_count} user passwords successfully!")
        
    except Exception as e:
        print(f"❌ Error updating passwords: {e}")

if __name__ == '__main__':
    update_user_passwords()