# reset_passwords_simple.py
import MySQLdb
import hashlib

def main():
    print("Setting up default users...")
    
    try:
        conn = MySQLdb.connect(
            host='localhost',
            user='root',
            passwd='',
            db='gate_pass_system'
        )
        
        cursor = conn.cursor()
        
        # Create system admin
        admin_pw = hashlib.md5('admin123'.encode()).hexdigest()
        
        cursor.execute("DELETE FROM users WHERE username = 'sysadmin'")
        cursor.execute("""
            INSERT INTO users (username, password, name, role, status) 
            VALUES ('sysadmin', %s, 'System Administrator', 'system_admin', 'approved')
        """, (admin_pw,))
        
        print("Created sysadmin / admin123")
        
        # Create store managers
        store_pw = hashlib.md5('store123'.encode()).hexdigest()
        
        cursor.execute("DELETE FROM users WHERE username IN ('store1', 'store2')")
        cursor.execute("""
            INSERT INTO users (username, password, name, role, status) 
            VALUES ('store1', %s, 'Store Manager 1', 'store_manager', 'approved')
        """, (store_pw,))
        
        cursor.execute("""
            INSERT INTO users (username, password, name, role, status) 
            VALUES ('store2', %s, 'Store Manager 2', 'store_manager', 'approved')
        """, (store_pw,))
        
        print("Created store1/store2 / store123")
        
        # Create department head
        dept_pw = hashlib.md5('dept123'.encode()).hexdigest()
        cursor.execute("DELETE FROM users WHERE username = 'depthead'")
        cursor.execute("""
            INSERT INTO users (username, password, name, role, status) 
            VALUES ('depthead', %s, 'Department Head', 'department_head', 'approved')
        """, (dept_pw,))
        
        print("Created depthead / dept123")
        
        conn.commit()
        cursor.close()
        conn.close()
        
        print("\nAll users created successfully!")
        print("\nLogin credentials:")
        print("- sysadmin / admin123")
        print("- store1 / store123")
        print("- store2 / store123") 
        print("- depthead / dept123")
        
    except Exception as e:
        print(f"Error: {e}")
        print("\nMake sure:")
        print("1. MySQL is running")
        print("2. Database 'gate_pass_system' exists")
        print("3. Run 'python app.py' first to create tables")

if __name__ == "__main__":
    main()