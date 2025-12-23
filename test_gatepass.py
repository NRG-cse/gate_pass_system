# test_gatepass.py
import MySQLdb
from datetime import datetime

def test_gatepass_creation():
    print("🧪 Testing Gate Pass Creation...")
    
    try:
        conn = MySQLdb.connect(
            host='localhost',
            user='root',
            passwd='',
            db='gate_pass_system'
        )
        cursor = conn.cursor()
        
        # Test 1: Check users
        cursor.execute("SELECT id, username, role FROM users WHERE status = 'approved'")
        users = cursor.fetchall()
        print(f"✅ Approved users: {len(users)}")
        for user in users:
            print(f"   - {user[1]} ({user[2]})")
        
        # Test 2: Check divisions and departments
        cursor.execute("SELECT id, name FROM divisions WHERE status = 'active'")
        divisions = cursor.fetchall()
        print(f"✅ Active divisions: {len(divisions)}")
        
        cursor.execute("SELECT id, name, division_id FROM departments WHERE status = 'active'")
        departments = cursor.fetchall()
        print(f"✅ Active departments: {len(departments)}")
        
        # Test 3: Try to create a test gate pass
        print("\n🚀 Testing gate pass creation...")
        test_user = users[0][0] if users else 1
        
        cursor.execute("""
            INSERT INTO gate_passes (
                pass_number, created_by, division_id, department_id,
                material_description, destination, purpose, material_type,
                material_status, receiver_name, receiver_contact, send_date,
                images, status
            ) VALUES (
                'TEST-001', %s, %s, %s, 'Test Material', 'Test Destination',
                'Testing', 'non_returnable', 'new', 'Test Receiver', '0123456789',
                %s, '[]', 'pending_dept'
            )
        """, (test_user, divisions[0][0] if divisions else 1, 
              departments[0][0] if departments else 1, datetime.now()))
        
        conn.commit()
        print("✅ Test gate pass created successfully!")
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    test_gatepass_creation()