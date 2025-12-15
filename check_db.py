# check_db.py - FIXED FOR WINDOWS
import MySQLdb
import hashlib

def hash_password(password):
    return hashlib.md5(password.encode('utf-8')).hexdigest()

def check_password(hashed_password, user_password):
    """Check password - compatible with both MD5 and existing hashes"""
    if hashlib.md5(user_password.encode('utf-8')).hexdigest() == hashed_password:
        return True
    if user_password == hashed_password:
        return True
    return False

def test_database():
    print("Checking database setup...")
    
    try:
        conn = MySQLdb.connect(
            host='localhost',
            user='root',
            passwd='',
            db='gate_pass_system'
        )
        print("Database connection successful!")
        
        cursor = conn.cursor()
        
        # Check tables
        cursor.execute("SHOW TABLES")
        tables = cursor.fetchall()
        table_names = [table[0] for table in tables]
        
        print(f"Found tables: {table_names}")
        
        required_tables = ['users', 'gate_passes', 'notifications']
        for table in required_tables:
            if table in table_names:
                print(f"SUCCESS: {table} table exists")
            else:
                print(f"ERROR: {table} table missing")
        
        if 'users' in table_names:
            print("Checking users...")
            
            # Check users
            cursor.execute("SELECT username, password, role, status FROM users")
            users = cursor.fetchall()
            print(f"Total users: {len(users)}")
            
            for user in users:
                username, password, role, status = user
                password_type = "MD5" if len(password) == 32 and all(c in '0123456789abcdef' for c in password.lower()) else "OTHER"
                print(f"   {username} - {role} - {status} - Password: {password_type} ({password})")
            
            # Test admin login
            print("\nTesting logins...")
            test_users = [
                ('admin', 'admin123'),
                ('depthead', 'dept123'),
                ('akib', 'akib123')
            ]
            
            for username, test_password in test_users:
                cursor.execute("SELECT password FROM users WHERE username = %s", (username,))
                result = cursor.fetchone()
                if result:
                    stored_hash = result[0]
                    if check_password(stored_hash, test_password):
                        print(f"SUCCESS: {username} login: PASSED")
                    else:
                        print(f"FAILED: {username} login: FAILED")
                        print(f"   Expected MD5: {hash_password(test_password)}")
                        print(f"   Stored hash: {stored_hash}")
                else:
                    print(f"WARNING: {username} not found in database")
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"Database error: {e}")

if __name__ == '__main__':
    test_database()