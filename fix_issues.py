# fix_issues.py
import MySQLdb

def fix_database_issues():
    print("🔧 Fixing database issues...")
    
    try:
        conn = MySQLdb.connect(
            host='localhost',
            user='root',
            passwd='',
            db='gate_pass_system'
        )
        cursor = conn.cursor()
        
        # 1. Add missing columns to gate_passes table
        print("Checking gate_passes table structure...")
        
        columns_to_add = [
            ('images', 'TEXT'),
            ('division_id', 'INT'),
            ('department_id', 'INT'),
            ('urgent', 'BOOLEAN DEFAULT FALSE'),
            ('status', 'VARCHAR(50) DEFAULT "pending_dept"')
        ]
        
        for column_name, column_type in columns_to_add:
            try:
                cursor.execute(f"SHOW COLUMNS FROM gate_passes LIKE '{column_name}'")
                if not cursor.fetchone():
                    cursor.execute(f"ALTER TABLE gate_passes ADD COLUMN {column_name} {column_type}")
                    print(f"✅ Added column: {column_name}")
            except Exception as e:
                print(f"⚠️ Error adding column {column_name}: {e}")
        
        # 2. Check for foreign key constraints
        print("\nChecking foreign key constraints...")
        cursor.execute("SHOW CREATE TABLE gate_passes")
        create_table_sql = cursor.fetchone()[1]
        
        if 'FOREIGN KEY' not in create_table_sql:
            print("⚠️ No foreign key constraints found. Adding...")
            try:
                cursor.execute('''
                    ALTER TABLE gate_passes 
                    ADD FOREIGN KEY (division_id) REFERENCES divisions(id),
                    ADD FOREIGN KEY (department_id) REFERENCES departments(id)
                ''')
                print("✅ Added foreign key constraints")
            except Exception as e:
                print(f"⚠️ Error adding foreign keys: {e}")
        
        # 3. Ensure at least one department exists
        cursor.execute("SELECT COUNT(*) FROM departments")
        if cursor.fetchone()[0] == 0:
            print("⚠️ No departments found. Creating default...")
            cursor.execute("SELECT id FROM divisions LIMIT 1")
            division_id = cursor.fetchone()[0]
            cursor.execute('''
                INSERT INTO departments (name, division_id, description, created_by)
                VALUES ('Default Department', %s, 'Default department for testing', 0)
            ''', (division_id,))
            print("✅ Created default department")
        
        conn.commit()
        print("\n✅ Database issues fixed successfully!")
        
    except Exception as e:
        print(f"❌ Error fixing database: {e}")
    
    finally:
        cursor.close()
        conn.close()

if __name__ == '__main__':
    fix_database_issues()