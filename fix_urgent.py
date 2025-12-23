# fix_urgent.py - Complete fix for gate pass creation
import MySQLdb
import hashlib
import os

def fix_urgent_issues():
    print("🚨 URGENT FIX - Gate Pass Creation Issues")
    print("="*60)
    
    try:
        # Database connection
        conn = MySQLdb.connect(
            host='localhost',
            user='root',
            passwd='',
            db='gate_pass_system'
        )
        cursor = conn.cursor()
        
        print("✅ Database connected successfully")
        
        # 1. Create gate_pass_approvals table if not exists
        print("\n1. Creating gate_pass_approvals table...")
        try:
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS gate_pass_approvals (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    gate_pass_id INT NOT NULL,
                    user_id INT NOT NULL,
                    approval_type ENUM('department', 'store', 'security', 'system_admin') NOT NULL,
                    status ENUM('approved', 'rejected', 'inquiry') NOT NULL,
                    comments TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (gate_pass_id) REFERENCES gate_passes(id),
                    FOREIGN KEY (user_id) REFERENCES users(id)
                )
            ''')
            print("  ✅ gate_pass_approvals table created")
        except Exception as e:
            print(f"  ⚠️ Error creating table: {e}")
        
        # 2. Check if test user exists
        print("\n2. Checking test user 'tanvir'...")
        cursor.execute("SELECT id, username, status FROM users WHERE username = 'tanvir'")
        tanvir = cursor.fetchone()
        
        if tanvir:
            user_id, username, status = tanvir
            print(f"  ✅ Found user: {username} (ID: {user_id}, Status: {status})")
            
            if status != 'approved':
                print(f"  ⚠️ User {username} is not approved! Status: {status}")
                print("  🔄 Updating to approved status...")
                cursor.execute("UPDATE users SET status = 'approved' WHERE username = 'tanvir'")
                print(f"  ✅ User {username} approved!")
        else:
            print("  ❌ User 'tanvir' not found!")
            print("  🔄 Creating test user...")
            
            # Get first department
            cursor.execute("SELECT id FROM departments LIMIT 1")
            dept_id = cursor.fetchone()[0]
            
            # Get division for department
            cursor.execute("SELECT division_id FROM departments WHERE id = %s", (dept_id,))
            div_id = cursor.fetchone()[0]
            
            # Create user
            password = hashlib.md5('tanvir123'.encode()).hexdigest()
            cursor.execute('''
                INSERT INTO users (username, password, name, designation, division_id, department_id, role, status)
                VALUES (%s, %s, %s, %s, %s, %s, %s, 'approved')
            ''', ('tanvir', password, 'Tanvir Ahmed', 'Executive', div_id, dept_id, 'user'))
            
            print("  ✅ Created test user: tanvir / tanvir123")
        
        # 3. Fix any existing gate passes without required data
        print("\n3. Fixing existing gate passes...")
        cursor.execute("SELECT id, images FROM gate_passes WHERE images IS NULL OR images = ''")
        broken_passes = cursor.fetchall()
        
        for pass_id, images in broken_passes:
            print(f"  ⚠️ Fixing gate pass ID {pass_id}")
            cursor.execute("UPDATE gate_passes SET images = '[]' WHERE id = %s", (pass_id,))
        
        # 4. Create uploads directory
        print("\n4. Creating uploads directory...")
        os.makedirs('static/uploads', exist_ok=True)
        print("  ✅ Created static/uploads directory")
        
        # 5. Verify all tables
        print("\n5. Verifying all tables...")
        cursor.execute("SHOW TABLES")
        tables = cursor.fetchall()
        for table in tables:
            table_name = table[0]
            cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
            count = cursor.fetchone()[0]
            print(f"  📊 {table_name}: {count} rows")
        
        conn.commit()
        cursor.close()
        conn.close()
        
        print("\n" + "="*60)
        print("✅ URGENT FIXES APPLIED SUCCESSFULLY!")
        print("="*60)
        print("\nTEST CREDENTIALS:")
        print("  System Admin: sysadmin / admin123")
        print("  Test User: tanvir / tanvir123")
        print("\nNEXT STEPS:")
        print("  1. Restart: python app.py")
        print("  2. Login as tanvir / tanvir123")
        print("  3. Try creating gate pass")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    fix_urgent_issues()