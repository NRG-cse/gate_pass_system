# fix_registration.py - Run this once to fix registration issues
import MySQLdb
import hashlib

def hash_password(password):
    return hashlib.md5(password.encode('utf-8')).hexdigest()

def fix_database():
    print("🔧 Fixing database for registration issues...")
    
    try:
        conn = MySQLdb.connect(
            host='localhost',
            user='root',
            passwd='',
            db='gate_pass_system'
        )
        cursor = conn.cursor()
        
        # 1. Check if divisions exist
        cursor.execute("SELECT COUNT(*) FROM divisions")
        division_count = cursor.fetchone()[0]
        
        if division_count == 0:
            print("Creating default divisions...")
            # Create default divisions
            divisions = [
                ('Administration', 'Administration Division'),
                ('Yarn Dyeing', 'Yarn Dyeing Division'),
                ('Fabric Dyeing', 'Fabric Dyeing Division'),
                ('Spinning', 'Spinning Division'),
                ('Store', 'Store Division')
            ]
            
            for div_name, div_desc in divisions:
                cursor.execute('''
                    INSERT INTO divisions (name, description, created_by) 
                    VALUES (%s, %s, 0)
                ''', (div_name, div_desc))
            print("✅ Created 5 default divisions")
        
        # 2. Check if departments exist
        cursor.execute("SELECT COUNT(*) FROM departments")
        department_count = cursor.fetchone()[0]
        
        if department_count == 0:
            print("Creating default departments...")
            # Get division IDs
            cursor.execute("SELECT id, name FROM divisions")
            divisions_data = []
            for row in cursor.fetchall():
                divisions_data.append({'id': row[0], 'name': row[1]})
            
            division_map = {div['name']: div['id'] for div in divisions_data}
            
            # Create departments
            departments = [
                ('Admin', division_map.get('Administration'), 'Administration Office'),
                ('Accounts', division_map.get('Administration'), 'Accounts Department'),
                ('Production', division_map.get('Yarn Dyeing'), 'Production Department'),
                ('Maintenance', division_map.get('Yarn Dyeing'), 'Maintenance Department'),
                ('Production', division_map.get('Fabric Dyeing'), 'Production Department'),
                ('Maintenance', division_map.get('Fabric Dyeing'), 'Maintenace Development'),
                ('Production', division_map.get('Spinning'), 'Production Department'),
                ('Maintenance', division_map.get('Spinning'), 'Maintenance Department'),
                ('Store 1', division_map.get('Store'), 'Main Store'),
                ('Store 2', division_map.get('Store'), 'Secondary Store')
            ]
            
            for dept_name, div_id, dept_desc in departments:
                if div_id:  # Only create if division exists
                    cursor.execute('''
                        INSERT INTO departments (name, division_id, description, created_by) 
                        VALUES (%s, %s, %s, 0)
                    ''', (dept_name, div_id, dept_desc))
            print("✅ Created 10 default departments")
        
        # 3. Fix existing users with department_id = 0
        cursor.execute("SELECT id, username FROM users WHERE department_id = 0 OR department_id IS NULL")
        users_to_fix = cursor.fetchall()
        
        if users_to_fix:
            print(f"Fixing {len(users_to_fix)} users with invalid department...")
            # Get a valid department ID
            cursor.execute("SELECT id FROM departments LIMIT 1")
            valid_dept = cursor.fetchone()
            
            if valid_dept:
                valid_dept_id = valid_dept[0]
                for user_id, username in users_to_fix:
                    cursor.execute('''
                        UPDATE users SET department_id = %s WHERE id = %s
                    ''', (valid_dept_id, user_id))
                    print(f"  Fixed user: {username} -> department_id: {valid_dept_id}")
        
        conn.commit()
        cursor.close()
        conn.close()
        
        print("🎯 Database fixed successfully!")
        print("\nNext steps:")
        print("1. Restart the application: python app.py")
        print("2. Super Admin can now create divisions/departments")
        print("3. Registration form will show existing divisions/departments")
        
    except Exception as e:
        print(f"❌ Error fixing database: {e}")

if __name__ == '__main__':
    fix_database()