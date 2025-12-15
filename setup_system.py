# setup_system.py - FIXED FOR WINDOWS
import subprocess
import sys
import os

def run_command(command, description):
    print(f"\n{description}...")
    try:
        result = subprocess.run(command, shell=True, capture_output=True, text=True)
        if result.returncode == 0:
            print(f"SUCCESS: {description} completed!")
            return True
        else:
            print(f"FAILED: {description}!")
            print(f"Error: {result.stderr}")
            return False
    except Exception as e:
        print(f"Error: {e}")
        return False

def setup_system():
    print("GATE PASS SYSTEM SETUP SCRIPT")
    print("=" * 50)
    
    # Step 1: Install requirements
    if not run_command("pip install -r requirements.txt", "Installing Python dependencies"):
        return False
    
    # Step 2: Generate icons
    if not run_command("python generate_icons.py", "Generating PWA icons"):
        return False
    
    # Step 3: Initialize database
    print("\nInitializing database...")
    try:
        import app
        print("Database initialized successfully!")
    except Exception as e:
        print(f"Database initialization error: {e}")
        return False
    
    # Step 4: Reset passwords
    if not run_command("python reset_passwords.py", "Resetting default passwords"):
        return False
    
    # Step 5: Verify setup
    if not run_command("python check_db.py", "Verifying database setup"):
        return False
    
    print("\n" + "=" * 50)
    print("SETUP COMPLETED SUCCESSFULLY!")
    print("=" * 50)
    print("\nDEFAULT LOGIN CREDENTIALS:")
    print("   System Admin: sysadmin / admin123")
    print("   Store Manager 1: store1 / store123")
    print("   Store Manager 2: store2 / store123")
    print("   Department Head: depthead / dept123")
    print("   Regular User: akib / akib123")
    
    print("\nSTART THE APPLICATION:")
    print("   python app.py")
    print("\nACCESS URL: http://192.168.7.198:5000")
    
    return True

if __name__ == "__main__":
    setup_system()