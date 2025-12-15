# setup_windows.py - Simple Windows Setup
import subprocess
import sys
import os

def run_cmd(cmd, desc):
    print(f"\n>>> {desc}")
    print(f"Command: {cmd}")
    
    try:
        # Use proper encoding for Windows
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, encoding='utf-8')
        
        if result.returncode == 0:
            print(f"SUCCESS: {desc}")
            if result.stdout:
                print(f"Output: {result.stdout[:500]}")  # Limit output
            return True
        else:
            print(f"FAILED: {desc}")
            print(f"Error: {result.stderr}")
            return False
    except Exception as e:
        print(f"Exception: {e}")
        return False

def main():
    print("GATE PASS SYSTEM WINDOWS SETUP")
    print("=" * 60)
    
    # 1. Check Python version
    print("\n1. Checking Python version...")
    run_cmd("python --version", "Python version")
    
    # 2. Install requirements
    if not run_cmd("pip install -r requirements.txt", "Install dependencies"):
        print("\nTrying alternative pip command...")
        run_cmd("python -m pip install -r requirements.txt", "Install using python -m pip")
    
    # 3. Create icons directory
    print("\n3. Creating directories...")
    os.makedirs("static/icons", exist_ok=True)
    print("Created static/icons directory")
    
    # 4. Create simple icons (without Unicode)
    print("\n4. Creating simple icons...")
    try:
        from PIL import Image, ImageDraw
        
        sizes = [32, 72, 96, 128, 144, 152, 192, 512]
        
        for size in sizes:
            img = Image.new('RGB', (size, size), color=(52, 152, 219))
            draw = ImageDraw.Draw(img)
            
            # Try to use font, fallback to default
            try:
                font_size = size // 3
                font = ImageFont.truetype("arial.ttf", font_size)
            except:
                from PIL import ImageFont
                font = ImageFont.load_default()
            
            text = "GP"
            # Calculate text position
            text_width = draw.textlength(text, font=font)
            text_height = font_size
            position = ((size - text_width) // 2, (size - text_height) // 2)
            
            draw.text(position, text, fill=(255, 255, 255), font=font)
            img.save(f'static/icons/icon-{size}x{size}.png')
            print(f"Created icon-{size}x{size}.png")
        
        print("All icons created successfully!")
    except Exception as e:
        print(f"Warning: Could not create icons: {e}")
        print("Creating placeholder icons...")
        # Create simple colored squares as fallback
        for size in [32, 72, 96, 128, 144, 152, 192, 512]:
            with open(f'static/icons/icon-{size}x{size}.png', 'wb') as f:
                # Create a simple 1x1 blue pixel (base64 encoded)
                f.write(b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x00\r\xb4\xd0q\x00\x00\x00\x00IEND\xaeB`\x82')
        print("Created placeholder icons")
    
    # 5. Initialize database
    print("\n5. Initializing database...")
    try:
        # Create a simple database init script
        init_script = """
import MySQLdb

conn = MySQLdb.connect(
    host='localhost',
    user='root',
    passwd='',
    db='gate_pass_system'
)

cursor = conn.cursor()

# Create tables if they don't exist
tables = [
    \"\"\"CREATE TABLE IF NOT EXISTS users (
        id INT AUTO_INCREMENT PRIMARY KEY,
        username VARCHAR(80) UNIQUE NOT NULL,
        password VARCHAR(120) NOT NULL,
        name VARCHAR(100) NOT NULL,
        role VARCHAR(50) NOT NULL,
        status VARCHAR(20) DEFAULT 'pending'
    )\"\"\",
    
    \"\"\"CREATE TABLE IF NOT EXISTS gate_passes (
        id INT AUTO_INCREMENT PRIMARY KEY,
        pass_number VARCHAR(50) UNIQUE NOT NULL,
        created_by INT,
        status VARCHAR(50),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )\"\"\"
]

for table_sql in tables:
    try:
        cursor.execute(table_sql)
        print(f"Created table")
    except Exception as e:
        print(f"Error creating table: {e}")

conn.commit()
cursor.close()
conn.close()
print("Database initialized!")
"""
        
        with open("init_db_temp.py", "w") as f:
            f.write(init_script)
        
        run_cmd("python init_db_temp.py", "Initialize database tables")
        
        # Clean up
        if os.path.exists("init_db_temp.py"):
            os.remove("init_db_temp.py")
            
    except Exception as e:
        print(f"Database init error: {e}")
    
    # 6. Create default users
    print("\n6. Creating default users...")
    try:
        import hashlib
        import MySQLdb
        
        def hash_pw(pw):
            return hashlib.md5(pw.encode()).hexdigest()
        
        conn = MySQLdb.connect(
            host='localhost',
            user='root',
            passwd='',
            db='gate_pass_system'
        )
        cursor = conn.cursor()
        
        # Create sysadmin if not exists
        cursor.execute("SELECT COUNT(*) FROM users WHERE username = 'sysadmin'")
        if cursor.fetchone()[0] == 0:
            cursor.execute(
                "INSERT INTO users (username, password, name, role, status) VALUES (%s, %s, %s, %s, %s)",
                ('sysadmin', hash_pw('admin123'), 'System Admin', 'system_admin', 'approved')
            )
            print("Created sysadmin user")
        
        conn.commit()
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"User creation error: {e}")
    
    print("\n" + "=" * 60)
    print("SETUP COMPLETED!")
    print("=" * 60)
    print("\nNext steps:")
    print("1. Run: python app.py")
    print("2. Open: http://192.168.7.198:5000")
    print("3. Login with: sysadmin / admin123")
    print("\nIf you have issues, check:")
    print("- MySQL is running (XAMPP -> Start MySQL)")
    print("- Database 'gate_pass_system' exists")
    print("- Python packages are installed")

if __name__ == "__main__":
    main()