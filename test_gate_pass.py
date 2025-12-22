# test_gate_pass.py - Debug script
import MySQLdb
import json
from datetime import datetime

def test_database():
    print("🧪 Testing Database Connection and Tables...")
    
    try:
        conn = MySQLdb.connect(
            host='localhost',
            user='root',
            passwd='',
            db='gate_pass_system'
        )
        print("✅ Database connection successful")
        
        cursor = conn.cursor()
        
        # Check gate_passes table structure
        print("\n📊 Checking gate_passes table structure...")
        cursor.execute("DESCRIBE gate_passes")
        columns = cursor.fetchall()
        print(f"✅ gate_passes has {len(columns)} columns:")
        for col in columns:
            print(f"  - {col[0]} ({col[1]})")
        
        # Check if table is empty
        cursor.execute("SELECT COUNT(*) FROM gate_passes")
        count = cursor.fetchone()[0]
        print(f"\n📊 Total gate passes in database: {count}")
        
        if count > 0:
            cursor.execute("SELECT pass_number, status, created_at FROM gate_passes ORDER BY id DESC LIMIT 5")
            recent = cursor.fetchall()
            print(f"\n📋 Recent gate passes:")
            for gp in recent:
                print(f"  - {gp[0]} ({gp[1]}) at {gp[2]}")
        
        # Check users
        print("\n👥 Checking users...")
        cursor.execute("SELECT username, role, department_id FROM users WHERE status = 'approved'")
        users = cursor.fetchall()
        print(f"✅ Total approved users: {len(users)}")
        for user in users:
            print(f"  - {user[0]} ({user[1]}) - Dept: {user[2]}")
        
        # Check divisions and departments
        print("\n🏢 Checking divisions and departments...")
        cursor.execute("SELECT id, name FROM divisions WHERE status = 'active'")
        divisions = cursor.fetchall()
        print(f"✅ Active divisions: {len(divisions)}")
        for div in divisions:
            print(f"  - {div[0]}: {div[1]}")
        
        cursor.execute("SELECT id, name, division_id FROM departments WHERE status = 'active'")
        depts = cursor.fetchall()
        print(f"✅ Active departments: {len(depts)}")
        for dept in depts:
            print(f"  - {dept[0]}: {dept[1]} (Division: {dept[2]})")
        
        cursor.close()
        conn.close()
        
        print("\n🎯 Test completed successfully!")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

def test_form_submission():
    print("\n🧪 Simulating form submission...")
    
    # Simulate form data
    form_data = {
        'division_id': '1',
        'department_id': '1', 
        'material_description': 'Test Material from Debug',
        'destination': 'Test Destination',
        'purpose': 'Testing',
        'material_type': 'non_returnable',
        'material_status': 'new',
        'receiver_name': 'Test Receiver',
        'receiver_contact': '0123456789',
        'send_date': datetime.now().strftime('%Y-%m-%dT%H:%M'),
        'vehicle_number': 'ABC-123',
        'receiver_id': 'TEST001',
        'delivery_address': 'Test Address',
        'special_instructions': 'Test instructions',
        'urgent': 'false'
    }
    
    print("📋 Simulated form data:")
    for key, value in form_data.items():
        print(f"  {key}: {value}")
    
    print("\n✅ Form simulation complete")

if __name__ == '__main__':
    print("🔧 GATE PASS SYSTEM DEBUG TOOL")
    print("="*50)
    test_database()
    test_form_submission()