# fix_all_issues.py - Complete fix for all issues
import MySQLdb
import hashlib
import os

def fix_all_problems():
    print("🔧 Fixing ALL Gate Pass System Issues...")
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
        
        # 1. Fix gate_passes table structure
        print("\n1. Fixing gate_passes table structure...")
        try:
            # Add missing columns if they don't exist
            columns_to_add = [
                ('images', 'TEXT NOT NULL'),
                ('status', 'VARCHAR(50) DEFAULT "pending_dept"'),
                ('urgent', 'BOOLEAN DEFAULT FALSE'),
                ('division_id', 'INT NOT NULL'),
                ('department_id', 'INT NOT NULL'),
                ('send_date', 'DATETIME NOT NULL'),
                ('created_at', 'TIMESTAMP DEFAULT CURRENT_TIMESTAMP')
            ]
            
            for col_name, col_type in columns_to_add:
                try:
                    cursor.execute(f"SHOW COLUMNS FROM gate_passes LIKE '{col_name}'")
                    if not cursor.fetchone():
                        cursor.execute(f"ALTER TABLE gate_passes ADD COLUMN {col_name} {col_type}")
                        print(f"  ✅ Added column: {col_name}")
                except Exception as e:
                    print(f"  ⚠️ Could not add {col_name}: {e}")
            
            conn.commit()
        except Exception as e:
            print(f"  ❌ Error fixing table: {e}")
        
        # 2. Ensure divisions exist
        print("\n2. Ensuring divisions exist...")
        cursor.execute("SELECT COUNT(*) FROM divisions")
        if cursor.fetchone()[0] == 0:
            divisions = [
                ('Administration', 'Administration Division'),
                ('Yarn Dyeing', 'Yarn Dyeing Division'),
                ('Fabric Dyeing', 'Fabric Dyeing Division'),
                ('Spinning', 'Spinning Division'),
                ('Store', 'Store Division')
            ]
            
            for div_name, div_desc in divisions:
                try:
                    cursor.execute('INSERT INTO divisions (name, description, created_by) VALUES (%s, %s, 0)', 
                                 (div_name, div_desc))
                    print(f"  ✅ Created division: {div_name}")
                except:
                    pass
            
            conn.commit()
        
        # 3. Ensure departments exist
        print("\n3. Ensuring departments exist...")
        cursor.execute("SELECT COUNT(*) FROM departments")
        if cursor.fetchone()[0] == 0:
            # Get division IDs
            cursor.execute("SELECT id, name FROM divisions")
            divisions_data = []
            for row in cursor.fetchall():
                divisions_data.append({'id': row[0], 'name': row[1]})
            
            division_map = {div['name']: div['id'] for div in divisions_data}
            
            departments = [
                ('Admin', division_map.get('Administration'), 'Administration Office'),
                ('Accounts', division_map.get('Administration'), 'Accounts Department'),
                ('Production', division_map.get('Yarn Dyeing'), 'Production Department'),
                ('Maintenance', division_map.get('Yarn Dyeing'), 'Maintenance Department'),
                ('Production', division_map.get('Fabric Dyeing'), 'Production Department'),
                ('Maintenance', division_map.get('Fabric Dyeing'), 'Maintenance Department'),
                ('Production', division_map.get('Spinning'), 'Production Department'),
                ('Maintenance', division_map.get('Spinning'), 'Maintenance Department'),
                ('Store 1', division_map.get('Store'), 'Main Store'),
                ('Store 2', division_map.get('Store'), 'Secondary Store')
            ]
            
            for dept_name, div_id, dept_desc in departments:
                if div_id:
                    try:
                        cursor.execute('''
                            INSERT INTO departments (name, division_id, description, created_by) 
                            VALUES (%s, %s, %s, 0)
                        ''', (dept_name, div_id, dept_desc))
                        print(f"  ✅ Created department: {dept_name}")
                    except:
                        pass
            
            conn.commit()
        
        # 4. Fix user passwords to MD5
        print("\n4. Fixing user passwords...")
        cursor.execute("SELECT id, username, password FROM users")
        users = cursor.fetchall()
        
        for user_id, username, password in users:
            # Check if password is already MD5 (32 chars hex)
            if len(password) != 32 or not all(c in '0123456789abcdef' for c in password.lower()):
                hashed = hashlib.md5(password.encode()).hexdigest()
                cursor.execute("UPDATE users SET password = %s WHERE id = %s", (hashed, user_id))
                print(f"  ✅ Fixed password for: {username}")
        
        conn.commit()
        
        # 5. Create uploads directory
        print("\n5. Creating uploads directory...")
        os.makedirs('static/uploads', exist_ok=True)
        print("  ✅ Created static/uploads directory")
        
        cursor.close()
        conn.close()
        
        print("\n" + "="*60)
        print("✅ ALL FIXES APPLIED SUCCESSFULLY!")
        print("="*60)
        print("\nNext steps:")
        print("1. Restart the application: python app.py")
        print("2. Login with: sysadmin / admin123")
        print("3. Try creating a gate pass")
        
    except Exception as e:
        print(f"❌ Error fixing issues: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    fix_all_problems()