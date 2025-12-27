# models.py - COMPLETELY FIXED WITH PROPER INITIALIZATION INCLUDING SECURITY
import MySQLdb
from config import config
import hashlib

def get_db_connection():
    try:
        conn = MySQLdb.connect(
            host=config['default'].MYSQL_HOST,
            user=config['default'].MYSQL_USER,
            passwd=config['default'].MYSQL_PASSWORD,
            db=config['default'].MYSQL_DB
        )
        return conn
    except MySQLdb.Error as e:
        print(f"Database connection error: {e}")
        return None

def hash_password(password):
    """Hash password using MD5"""
    return hashlib.md5(password.encode('utf-8')).hexdigest()

def check_password(hashed_password, user_password):
    """Check password - compatible with both MD5 and existing hashes"""
    if hashlib.md5(user_password.encode('utf-8')).hexdigest() == hashed_password:
        return True
    if user_password == hashed_password:
        return True
    return False

def dict_fetchall(cursor):
    """Convert cursor results to list of dictionaries"""
    columns = [col[0] for col in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]

def dict_fetchone(cursor):
    """Convert single cursor result to dictionary"""
    columns = [col[0] for col in cursor.description]
    row = cursor.fetchone()
    if row is None:
        return None
    return dict(zip(columns, row))

def init_db():
    conn = get_db_connection()
    if conn is None:
        print("❌ Database connection failed! Please check MySQL setup.")
        return False
    
    cursor = conn.cursor()
    
    try:
        # Divisions table (NEW)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS divisions (
                id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(100) UNIQUE NOT NULL,
                description TEXT,
                status ENUM('active', 'inactive') DEFAULT 'active',
                created_by INT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            )
        ''')
        
        # Departments table (NEW - Now linked to divisions)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS departments (
                id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(100) NOT NULL,
                division_id INT NOT NULL,
                description TEXT,
                status ENUM('active', 'inactive') DEFAULT 'active',
                created_by INT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                FOREIGN KEY (division_id) REFERENCES divisions(id),
                UNIQUE KEY unique_dept_in_division (division_id, name)
            )
        ''')
        
        # Users table - UPDATED with division_id
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INT AUTO_INCREMENT PRIMARY KEY,
                username VARCHAR(80) UNIQUE NOT NULL,
                password VARCHAR(120) NOT NULL,
                name VARCHAR(100) NOT NULL,
                designation VARCHAR(100) NOT NULL,
                division_id INT,
                department_id INT NOT NULL,
                phone VARCHAR(15),
                email VARCHAR(120),
                role ENUM('system_admin', 'security', 'department_head', 'store_manager', 'user') DEFAULT 'user',
                status ENUM('pending', 'approved', 'rejected', 'inactive') DEFAULT 'pending',
                created_by INT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                FOREIGN KEY (division_id) REFERENCES divisions(id),
                FOREIGN KEY (department_id) REFERENCES departments(id)
            )
        ''')
        
        # Gate passes table - UPDATED with store information
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS gate_passes (
                id INT AUTO_INCREMENT PRIMARY KEY,
                pass_number VARCHAR(50) UNIQUE NOT NULL,
                created_by INT NOT NULL,
                division_id INT NOT NULL,
                department_id INT NOT NULL,
                material_description TEXT NOT NULL,
                destination VARCHAR(200) NOT NULL,
                purpose TEXT NOT NULL,
                material_type ENUM('returnable', 'non_returnable') NOT NULL,
                material_status ENUM('damaged', 'repair', 'new', 'other') NOT NULL,
                expected_return_date DATETIME NULL,
                receiver_name VARCHAR(100) NOT NULL,
                receiver_contact VARCHAR(15),
                send_date DATETIME NOT NULL,
                images TEXT NOT NULL,  -- REQUIRED: No gate pass without images
                qr_code_form VARCHAR(500),
                qr_code_sticker VARCHAR(500),
                status ENUM('draft', 'pending_dept', 'pending_store', 'pending_security', 'ready_for_dispatch', 'approved', 'rejected', 'inquiry', 'in_transit', 'returned', 'overdue') DEFAULT 'draft',
                department_approval ENUM('pending', 'approved', 'rejected', 'inquiry') DEFAULT 'pending',
                store_approval ENUM('pending', 'approved', 'rejected') DEFAULT 'pending',
                security_approval ENUM('pending', 'approved', 'rejected') DEFAULT 'pending',
                store_location ENUM('store_1', 'store_2') NULL,
                department_approval_date DATETIME NULL,
                store_approval_date DATETIME NULL,
                security_approval_date DATETIME NULL,
                actual_return_date DATETIME NULL,
                urgent BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                session_token VARCHAR(32),
                FOREIGN KEY (created_by) REFERENCES users(id),
                FOREIGN KEY (division_id) REFERENCES divisions(id),
                FOREIGN KEY (department_id) REFERENCES departments(id)
            )
        ''')
        
        # Gate pass approvals table (NEW) - Important for approval history
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
        
        # Notifications table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS notifications (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT NOT NULL,
                gate_pass_id INT,
                message TEXT NOT NULL,
                type ENUM('approval', 'reminder', 'status', 'alert', 'return_overdue') NOT NULL,
                is_read BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id),
                FOREIGN KEY (gate_pass_id) REFERENCES gate_passes(id)
            )
        ''')
        
        # Security logs table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS security_logs (
                id INT AUTO_INCREMENT PRIMARY KEY,
                gate_pass_id INT,
                user_id INT,
                alert_type VARCHAR(50) NOT NULL,
                details TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (gate_pass_id) REFERENCES gate_passes(id),
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        ''')
        
        # Store requests table (NEW) - Security to Admin requests
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS store_requests (
                id INT AUTO_INCREMENT PRIMARY KEY,
                security_user_id INT NOT NULL,
                material_description TEXT NOT NULL,
                destination VARCHAR(200) NOT NULL,
                purpose TEXT NOT NULL,
                receiver_name VARCHAR(100) NOT NULL,
                receiver_contact VARCHAR(15),
                urgent BOOLEAN DEFAULT FALSE,
                status ENUM('pending', 'approved', 'rejected', 'processed') DEFAULT 'pending',
                admin_id INT,
                gate_pass_id INT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                FOREIGN KEY (security_user_id) REFERENCES users(id),
                FOREIGN KEY (admin_id) REFERENCES users(id),
                FOREIGN KEY (gate_pass_id) REFERENCES gate_passes(id)
            )
        ''')

        # Store Requests Table (For store managers to request gate passes)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS store_manager_requests (
                id INT AUTO_INCREMENT PRIMARY KEY,
                store_manager_id INT NOT NULL,
                store_location ENUM('store_1', 'store_2') NOT NULL,
                material_description TEXT NOT NULL,
                destination VARCHAR(200) NOT NULL,
                purpose TEXT NOT NULL,
                receiver_name VARCHAR(100) NOT NULL,
                receiver_contact VARCHAR(15),
                quantity INT DEFAULT 1,
                urgency ENUM('normal', 'urgent', 'emergency') DEFAULT 'normal',
                status ENUM('pending', 'approved', 'rejected', 'processing') DEFAULT 'pending',
                admin_response TEXT,
                admin_response_by INT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                FOREIGN KEY (store_manager_id) REFERENCES users(id),
                FOREIGN KEY (admin_response_by) REFERENCES users(id)
            )
        ''')

        # Store Material Movement Log Table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS store_material_logs (
                id INT AUTO_INCREMENT PRIMARY KEY,
                store_location ENUM('store_1', 'store_2') NOT NULL,
                gate_pass_id INT,
                material_description TEXT NOT NULL,
                movement_type ENUM('incoming', 'outgoing', 'transfer') NOT NULL,
                quantity INT DEFAULT 1,
                from_location VARCHAR(100),
                to_location VARCHAR(100),
                handled_by INT NOT NULL,
                remarks TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (gate_pass_id) REFERENCES gate_passes(id),
                FOREIGN KEY (handled_by) REFERENCES users(id)
            )
        ''')
        
        # Add missing columns if they don't exist
        try:
            cursor.execute("SHOW COLUMNS FROM gate_passes LIKE 'store_location'")
            if not cursor.fetchone():
                cursor.execute('ALTER TABLE gate_passes ADD COLUMN store_location ENUM("store_1", "store_2") NULL')
        except:
            pass
        
        # Add missing column for store_manager_requests if not exists
        try:
            cursor.execute("SHOW COLUMNS FROM store_manager_requests LIKE 'admin_response_by'")
            if not cursor.fetchone():
                cursor.execute('ALTER TABLE store_manager_requests ADD COLUMN admin_response_by INT NULL')
                cursor.execute('ALTER TABLE store_manager_requests ADD FOREIGN KEY (admin_response_by) REFERENCES users(id)')
                print("✅ Added admin_response_by column to store_manager_requests")
        except Exception as e:
            print(f"⚠️ Could not add admin_response_by column: {e}")
        
        # ✅ ADDED: Create default divisions including Security Division
        cursor.execute("SELECT COUNT(*) FROM divisions")
        if cursor.fetchone()[0] == 0:
            print("Creating default divisions...")
            divisions = [
                ('Administration', 'Administration Division'),
                ('Yarn Dyeing', 'Yarn Dyeing Division'),
                ('Fabric Dyeing', 'Fabric Dyeing Division'),
                ('Spinning', 'Spinning Division'),
                ('Store', 'Store Division'),
                ('Security', 'Security Division')  # ✅ ADDED SECURITY DIVISION
            ]
            
            for div_name, div_desc in divisions:
                try:
                    cursor.execute('INSERT INTO divisions (name, description, created_by) VALUES (%s, %s, 0)', (div_name, div_desc))
                except:
                    pass
            
            print("✅ Created default divisions including Security")
        
        # ✅ ADDED: Create default departments including Security Departments
        cursor.execute("SELECT COUNT(*) FROM departments")
        if cursor.fetchone()[0] == 0:
            print("Creating default departments...")
            # Get division IDs
            cursor.execute("SELECT id, name FROM divisions")
            divisions_data = []
            for row in cursor.fetchall():
                divisions_data.append({'id': row[0], 'name': row[1]})
            
            division_map = {div['name']: div['id'] for div in divisions_data}
            
            # Create departments with proper division mapping
            departments = [
                ('Admin', 'Administration', 'Administration Office'),
                ('Accounts', 'Administration', 'Accounts Department'),
                ('HR', 'Administration', 'Human Resources'),
                ('IT', 'Administration', 'Information Technology'),
                ('Production', 'Yarn Dyeing', 'Production Department'),
                ('Maintenance', 'Yarn Dyeing', 'Maintenance Department'),
                ('Production', 'Fabric Dyeing', 'Production Department'),
                ('Maintenance', 'Fabric Dyeing', 'Maintenance Department'),
                ('Production', 'Spinning', 'Production Department'),
                ('Maintenance', 'Spinning', 'Maintenance Department'),
                ('Store 1', 'Store', 'Main Store'),
                ('Store 2', 'Store', 'Secondary Store'),
                ('Main Gate Security', 'Security', 'Main Gate Security Team'),  # ✅ ADDED SECURITY DEPARTMENTS
                ('Factory Security', 'Security', 'Factory Security Team')
            ]
            
            for dept_name, div_name, dept_desc in departments:
                if div_name in division_map:
                    try:
                        cursor.execute('''
                            INSERT INTO departments (name, division_id, description, created_by) 
                            VALUES (%s, %s, %s, 0)
                        ''', (dept_name, division_map[div_name], dept_desc))
                    except:
                        pass
            
            print("✅ Created default departments including Security")
        
        # ✅ ADDED: Create default System Administrator with proper department mapping
        cursor.execute("SELECT COUNT(*) FROM users WHERE username = 'sysadmin'")
        if cursor.fetchone()[0] == 0:
            print("Creating System Administrator...")
            # Get first department ID for Admin division
            cursor.execute('''
                SELECT d.id FROM departments d 
                JOIN divisions dv ON d.division_id = dv.id 
                WHERE dv.name = 'Administration' 
                LIMIT 1
            ''')
            admin_dept = cursor.fetchone()
            
            if admin_dept:
                admin_dept_id = admin_dept[0]
                # Get division ID for the department
                cursor.execute('SELECT division_id FROM departments WHERE id = %s', (admin_dept_id,))
                division_result = cursor.fetchone()
                
                if division_result:
                    admin_password = hash_password('admin123')
                    cursor.execute('''
                        INSERT INTO users (username, password, name, designation, division_id, department_id, role, status) 
                        VALUES ('sysadmin', %s, 'System Administrator', 'Super Admin', %s, %s, 'system_admin', 'approved')
                    ''', (admin_password, division_result[0], admin_dept_id))
                    print("✅ Created System Administrator: sysadmin / admin123")
        
        # ✅ ADDED: Create default Store Managers
        cursor.execute("SELECT COUNT(*) FROM users WHERE username IN ('store1', 'store2')")
        if cursor.fetchone()[0] == 0:
            print("Creating Store Managers...")
            # Get store departments
            cursor.execute("SELECT id FROM departments WHERE name LIKE '%Store%' ORDER BY name")
            store_depts = cursor.fetchall()
            
            if len(store_depts) >= 2:
                store_password = hash_password('store123')
                # Store Manager 1
                cursor.execute('SELECT division_id FROM departments WHERE id = %s', (store_depts[0][0],))
                div1 = cursor.fetchone()
                if div1:
                    cursor.execute('''
                        INSERT INTO users (username, password, name, designation, division_id, department_id, role, status) 
                        VALUES ('store1', %s, 'Store Manager 1', 'Store Manager', %s, %s, 'store_manager', 'approved')
                    ''', (store_password, div1[0], store_depts[0][0]))
                
                # Store Manager 2
                cursor.execute('SELECT division_id FROM departments WHERE id = %s', (store_depts[1][0],))
                div2 = cursor.fetchone()
                if div2:
                    cursor.execute('''
                        INSERT INTO users (username, password, name, designation, division_id, department_id, role, status) 
                        VALUES ('store2', %s, 'Store Manager 2', 'Store Manager', %s, %s, 'store_manager', 'approved')
                    ''', (store_password, div2[0], store_depts[1][0]))
                
                print("✅ Created Store Managers: store1/store2 / store123")
        
        # ✅ ADDED: Create default Department Head
        cursor.execute("SELECT COUNT(*) FROM users WHERE username = 'depthead'")
        if cursor.fetchone()[0] == 0:
            print("Creating Department Head...")
            # Get first non-store department
            cursor.execute("SELECT id FROM departments WHERE name NOT LIKE '%Store%' LIMIT 1")
            dept = cursor.fetchone()
            
            if dept:
                dept_id = dept[0]
                cursor.execute('SELECT division_id FROM departments WHERE id = %s', (dept_id,))
                div = cursor.fetchone()
                
                if div:
                    dept_password = hash_password('dept123')
                    cursor.execute('''
                        INSERT INTO users (username, password, name, designation, division_id, department_id, role, status) 
                        VALUES ('depthead', %s, 'Department Head', 'Department Manager', %s, %s, 'department_head', 'approved')
                    ''', (dept_password, div[0], dept_id))
                    print("✅ Created Department Head: depthead / dept123")
        
        # ✅ ADDED: Create default Security Users
        cursor.execute("SELECT COUNT(*) FROM users WHERE username IN ('security1', 'security2')")
        if cursor.fetchone()[0] == 0:
            print("Creating Security Users...")
            # Get security departments
            cursor.execute("SELECT id FROM departments WHERE name LIKE '%Security%' ORDER BY name")
            security_depts = cursor.fetchall()
            
            if len(security_depts) >= 2:
                security_password = hash_password('security123')
                
                # Security User 1 (Main Gate)
                cursor.execute('SELECT division_id FROM departments WHERE id = %s', (security_depts[0][0],))
                div1 = cursor.fetchone()
                if div1:
                    cursor.execute('''
                        INSERT INTO users (username, password, name, designation, division_id, department_id, role, status) 
                        VALUES ('security1', %s, 'Security Officer 1', 'Security', %s, %s, 'security', 'approved')
                    ''', (security_password, div1[0], security_depts[0][0]))
                
                # Security User 2 (Factory Security)
                cursor.execute('SELECT division_id FROM departments WHERE id = %s', (security_depts[1][0],))
                div2 = cursor.fetchone()
                if div2:
                    cursor.execute('''
                        INSERT INTO users (username, password, name, designation, division_id, department_id, role, status) 
                        VALUES ('security2', %s, 'Security Officer 2', 'Security', %s, %s, 'security', 'approved')
                    ''', (security_password, div2[0], security_depts[1][0]))
                
                print("✅ Created Security Users: security1/security2 / security123")
        
        # ✅ ADDED: Create test regular user
        cursor.execute("SELECT COUNT(*) FROM users WHERE username = 'akib'")
        if cursor.fetchone()[0] == 0:
            print("Creating test user...")
            # Get any department for test user
            cursor.execute("SELECT id FROM departments LIMIT 1")
            test_dept = cursor.fetchone()
            
            if test_dept:
                cursor.execute('SELECT division_id FROM departments WHERE id = %s', (test_dept[0],))
                test_div = cursor.fetchone()
                
                if test_div:
                    test_password = hash_password('akib123')
                    cursor.execute('''
                        INSERT INTO users (username, password, name, designation, division_id, department_id, role, status) 
                        VALUES ('akib', %s, 'Akib Rahman', 'Executive', %s, %s, 'user', 'approved')
                    ''', (test_password, test_div[0], test_dept[0]))
                    print("✅ Created test user: akib / akib123")
        
        # ✅ ADDED: Verify gate_passes table structure
        try:
            print("\n" + "="*60)
            print("🔍 VERIFYING GATE_PASSES TABLE STRUCTURE")
            print("="*60)
            
            cursor.execute("SHOW COLUMNS FROM gate_passes")
            columns = [col[0] for col in cursor.fetchall()]
            print(f"📊 gate_passes table has {len(columns)} columns")
            
            # Check for required columns
            required_columns = ['pass_number', 'created_by', 'division_id', 'department_id', 
                              'material_description', 'images', 'status', 'urgent']
            missing_columns = [col for col in required_columns if col not in columns]
            
            if missing_columns:
                print(f"⚠️ Missing columns in gate_passes: {missing_columns}")
                print("🛠️ Attempting to add missing columns...")
                
                for column in missing_columns:
                    try:
                        if column == 'images':
                            cursor.execute('ALTER TABLE gate_passes ADD COLUMN images TEXT NOT NULL')
                            print(f"✅ Added column: images (TEXT NOT NULL)")
                        elif column == 'status':
                            cursor.execute('ALTER TABLE gate_passes ADD COLUMN status VARCHAR(50) DEFAULT "pending_dept"')
                            print(f"✅ Added column: status (VARCHAR(50) DEFAULT 'pending_dept')")
                        elif column == 'urgent':
                            cursor.execute('ALTER TABLE gate_passes ADD COLUMN urgent BOOLEAN DEFAULT FALSE')
                            print(f"✅ Added column: urgent (BOOLEAN DEFAULT FALSE)")
                        elif column == 'division_id':
                            cursor.execute('ALTER TABLE gate_passes ADD COLUMN division_id INT NOT NULL')
                            print(f"✅ Added column: division_id (INT NOT NULL)")
                        elif column == 'department_id':
                            cursor.execute('ALTER TABLE gate_passes ADD COLUMN department_id INT NOT NULL')
                            print(f"✅ Added column: department_id (INT NOT NULL)")
                        else:
                            cursor.execute(f'ALTER TABLE gate_passes ADD COLUMN {column} VARCHAR(255)')
                            print(f"✅ Added column: {column} (VARCHAR(255))")
                    except Exception as col_error:
                        print(f"⚠️ Could not add column {column}: {col_error}")
                
                conn.commit()
                print("✅ Missing columns added successfully!")
            else:
                print("✅ All required columns are present in gate_passes table")
            
            # Also check for the correct ENUM values
            try:
                cursor.execute("SHOW COLUMNS FROM gate_passes LIKE 'status'")
                status_col = cursor.fetchone()
                if status_col:
                    print(f"📊 Status column type: {status_col[1]}")
            except:
                pass
                
        except Exception as table_error:
            print(f"⚠️ Table verification error: {table_error}")
            import traceback
            traceback.print_exc()
        
        # ✅ ADDED: Final verification of all tables
        print("\n" + "="*60)
        print("📋 FINAL TABLE VERIFICATION")
        print("="*60)
        
        cursor.execute("SHOW TABLES")
        tables = cursor.fetchall()
        print(f"📊 Total tables in database: {len(tables)}")
        
        for table in tables:
            table_name = table[0]
            cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
            count = cursor.fetchone()[0]
            print(f"  📈 {table_name}: {count} rows")
        
        # ✅ ADDED: Print all default users for verification
        print("\n" + "="*60)
        print("👥 DEFAULT USERS VERIFICATION")
        print("="*60)
        
        cursor.execute("SELECT username, name, role, status FROM users ORDER BY role, username")
        users = cursor.fetchall()
        for user in users:
            print(f"  👤 {user[0]} - {user[1]} ({user[2]}) - {user[3]}")
        
        conn.commit()
        print("\n" + "="*60)
        print("✅ Database initialized successfully with ALL default users!")
        print("="*60)
        print("\n📋 DEFAULT LOGIN CREDENTIALS:")
        print("   System Admin: sysadmin / admin123")
        print("   Store Manager 1: store1 / store123")
        print("   Store Manager 2: store2 / store123")
        print("   Department Head: depthead / dept123")
        print("   Security Officer 1: security1 / security123")
        print("   Security Officer 2: security2 / security123")
        print("   Regular User: akib / akib123")
        print("="*60)
        return True
        
    except Exception as e:
        print(f"❌ Database initialization error: {e}")
        import traceback
        traceback.print_exc()
        conn.rollback()
        return False
    finally:
        cursor.close()
        conn.close()