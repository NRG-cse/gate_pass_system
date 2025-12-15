# models.py - FIXED DEFAULT DATA ISSUE
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
                status ENUM('draft', 'pending_dept', 'pending_store', 'pending_security', 'approved', 'rejected', 'inquiry', 'in_transit', 'returned', 'overdue') DEFAULT 'draft',
                department_approval ENUM('pending', 'approved', 'rejected', 'inquiry') DEFAULT 'pending',
                store_approval ENUM('pending', 'approved', 'rejected') DEFAULT 'pending',
                security_approval ENUM('pending', 'approved', 'rejected') DEFAULT 'pending',
                store_location ENUM('store_1', 'store_2') NULL,
                department_approval_date DATETIME NULL,
                store_approval_date DATETIME NULL,
                security_approval_date DATETIME NULL,
                actual_return_date DATETIME NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                session_token VARCHAR(32),
                FOREIGN KEY (created_by) REFERENCES users(id),
                FOREIGN KEY (division_id) REFERENCES divisions(id),
                FOREIGN KEY (department_id) REFERENCES departments(id)
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
        
        # Add missing columns if they don't exist
        try:
            cursor.execute("SHOW COLUMNS FROM gate_passes LIKE 'store_location'")
            if not cursor.fetchone():
                cursor.execute('ALTER TABLE gate_passes ADD COLUMN store_location ENUM("store_1", "store_2") NULL')
        except:
            pass
        
        # Create default divisions and departments FIRST
        cursor.execute("SELECT COUNT(*) FROM divisions")
        if cursor.fetchone()[0] == 0:
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
            
            print("✅ Created default divisions")
        
        # Create default departments for each division
        cursor.execute("SELECT COUNT(*) FROM departments")
        if cursor.fetchone()[0] == 0:
            # Get division IDs
            cursor.execute("SELECT id, name FROM divisions")
            divisions_data = dict_fetchall(cursor)
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
            
            print("✅ Created default departments")
        
        # Create default System Administrator - FIXED department_id issue
        cursor.execute("SELECT COUNT(*) FROM users WHERE username = 'sysadmin'")
        if cursor.fetchone()[0] == 0:
            # Get a valid department ID
            cursor.execute("SELECT id FROM departments LIMIT 1")
            dept_result = cursor.fetchone()
            if dept_result:
                admin_password = hash_password('admin123')
                cursor.execute('''
                    INSERT INTO users (username, password, name, designation, department_id, role, status) 
                    VALUES ('sysadmin', %s, 'System Administrator', 'Super Admin', %s, 'system_admin', 'approved')
                ''', (admin_password, dept_result[0]))
                print("✅ Created System Administrator: sysadmin / admin123")
        
        # Create default Store Managers - FIXED department_id issue
        cursor.execute("SELECT COUNT(*) FROM users WHERE username IN ('store1', 'store2')")
        if cursor.fetchone()[0] == 0:
            # Get store department IDs
            cursor.execute("SELECT id FROM departments WHERE name LIKE '%Store%' LIMIT 2")
            store_depts = cursor.fetchall()
            
            if len(store_depts) >= 2:
                store_password = hash_password('store123')
                cursor.execute('''
                    INSERT INTO users (username, password, name, designation, department_id, role, status) 
                    VALUES ('store1', %s, 'Store Manager 1', 'Store Manager', %s, 'store_manager', 'approved')
                ''', (store_password, store_depts[0][0]))
                
                cursor.execute('''
                    INSERT INTO users (username, password, name, designation, department_id, role, status) 
                    VALUES ('store2', %s, 'Store Manager 2', 'Store Manager', %s, 'store_manager', 'approved')
                ''', (store_password, store_depts[1][0]))
                print("✅ Created Store Managers: store1/store2 / store123")
        
        conn.commit()
        print("✅ Database initialized successfully with new structure!")
        return True
        
    except Exception as e:
        print(f"❌ Database initialization error: {e}")
        conn.rollback()
        return False
    finally:
        cursor.close()
        conn.close()