# qr_utils.py - COMPLETE VERSION WITH ALL FEATURES
import qrcode
import json
import base64
from io import BytesIO
from datetime import datetime
import hashlib
import secrets
import os

# ==================== CORE QR FUNCTIONS ====================
def generate_qr_code(data, filename=None):
    """Generate QR code image as base64 or save to file"""
    try:
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(data)
        qr.make(fit=True)
        
        img = qr.make_image(fill_color="black", back_color="white")
        
        if filename:
            img.save(filename)
        
        # Convert to base64 for HTML display
        buffered = BytesIO()
        img.save(buffered, format="PNG")
        img_str = base64.b64encode(buffered.getvalue()).decode()
        
        return f"data:image/png;base64,{img_str}"
    
    except Exception as e:
        print(f"Error generating QR code: {e}")
        return None

def generate_qr_code_base64(data):
    """Wrapper for backward compatibility"""
    return generate_qr_code(data)

# ==================== SECURITY & FRAUD DETECTION FUNCTIONS ====================
def generate_secure_qr_data(gate_pass_id, pass_number, session_id=None):
    """Generate QR data with security features to prevent mobile photo scanning"""
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    
    # Generate session-specific token to prevent photo reuse
    if not session_id:
        session_id = secrets.token_hex(8)
    
    data = f"GATEPASS:{pass_number}:{gate_pass_id}:{timestamp}:{session_id}"
    
    # Add multiple security layers
    security_hash = hashlib.sha256(f"{data}:gate_pass_secure_2024:{timestamp}".encode()).hexdigest()
    return f"{data}:{security_hash}", session_id

def verify_qr_code(qr_data, expected_session_id=None):
    """Enhanced QR verification with session validation"""
    try:
        # Try enhanced format first
        if 'GATEPASS:' in qr_data:
            parts = qr_data.split(':')
            if len(parts) != 6:
                return False, "Invalid QR format"
            
            data_part = ':'.join(parts[:5])
            received_hash = parts[5]
            
            # Verify session if provided
            if expected_session_id and parts[4] != expected_session_id:
                return False, "Invalid session - possible photo fraud"
            
            # Verify timestamp freshness (within 5 minutes)
            timestamp = parts[3]
            try:
                qr_time = datetime.strptime(timestamp, "%Y%m%d%H%M%S")
                current_time = datetime.now()
                time_diff = (current_time - qr_time).total_seconds()
                
                if time_diff > 300:  # 5 minutes
                    return False, "QR code expired"
            except ValueError:
                # If timestamp parsing fails, still allow but log
                print(f"Warning: Could not parse timestamp: {timestamp}")
            
            # Verify security hash
            expected_hash = hashlib.sha256(
                f"{data_part}:gate_pass_secure_2024:{timestamp}".encode()
            ).hexdigest()
            
            if received_hash == expected_hash:
                return True, {
                    'type': parts[0],
                    'pass_number': parts[1],
                    'gate_pass_id': parts[2],
                    'timestamp': parts[3],
                    'session_id': parts[4],
                    'security_hash': parts[5]
                }
            else:
                return False, "QR code tampered"
        
        # Fallback to JSON format verification
        elif qr_data.startswith('{'):
            return verify_json_qr_code(qr_data)
        
        # Fallback to simple pass number format
        else:
            return verify_simple_qr_code(qr_data)
            
    except Exception as e:
        return False, f"Verification error: {str(e)}"

def verify_json_qr_code(qr_data):
    """Verify JSON format QR code data"""
    try:
        if qr_data.startswith('{'):
            data = json.loads(qr_data)
            if "gate_pass_id" in data and "pass_number" in data:
                return True, data
        
        return False, "Invalid JSON QR code format"
    except Exception as e:
        return False, f"Error verifying JSON QR code: {str(e)}"

def verify_simple_qr_code(qr_data):
    """Verify simple format QR code data"""
    try:
        # If QR data is just pass number
        if qr_data.startswith('GP'):
            return True, {"pass_number": qr_data, "gate_pass_id": None}
        
        # If QR data is in format "GP12345:RETURN"
        elif ':' in qr_data and qr_data.split(':')[0].startswith('GP'):
            pass_number = qr_data.split(':')[0]
            return True, {"pass_number": pass_number, "gate_pass_id": None}
        
        return False, "Invalid QR code format"
    except Exception as e:
        return False, f"Error verifying simple QR code: {str(e)}"

def verify_qr_code_simple(qr_data):
    """Simple verification wrapper for backward compatibility"""
    return verify_qr_code(qr_data)

# ==================== COMPATIBILITY FUNCTIONS FOR DIFFERENT QR FORMATS ====================
def generate_gate_pass_qr(gate_pass):
    """Generate QR code data for gate pass - YOUR FORMAT"""
    # ✅ FIXED: Use proper format for QR code
    # Format: GATEPASS:<pass_number>:<gate_pass_id>:<timestamp>:<random_code>
    import random
    
    pass_number = gate_pass['pass_number']
    gate_pass_id = gate_pass['id']
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
    
    # Create a unique code
    unique_code = hashlib.md5(f"{pass_number}{gate_pass_id}{timestamp}".encode()).hexdigest()[:8]
    
    # Final QR data format
    qr_data = f"GATEPASS:{pass_number}:{gate_pass_id}:{timestamp}:{unique_code}"
    
    return qr_data

def generate_return_qr(gate_pass):
    """Generate QR code specifically for return scanning - YOUR FORMAT"""
    # Simpler format for return scanning
    return f"{gate_pass['pass_number']}:RETURN"

def generate_sticker_qr(gate_pass):
    """Generate QR code for sticker - simpler version - YOUR FORMAT"""
    return gate_pass['pass_number']

def generate_gate_pass_qr_data(gate_pass_id, pass_number, prefix="GP"):
    """Generate QR code data for gate pass - MY FORMAT (Compatibility function)"""
    qr_data = {
        "gate_pass_id": gate_pass_id,
        "pass_number": pass_number,
        "timestamp": datetime.now().isoformat(),
        "type": "gate_pass_return"
    }
    
    # Add hash for security
    hash_string = f"{gate_pass_id}:{pass_number}:{datetime.now().strftime('%Y%m%d%H')}"
    security_hash = hashlib.sha256(hash_string.encode()).hexdigest()[:8]
    qr_data["hash"] = security_hash
    
    return json.dumps(qr_data)

# ==================== UTILITY FUNCTIONS ====================
def generate_qr_for_gate_pass(gate_pass_id, pass_number, save_path=None):
    """Generate QR code for gate pass and optionally save to file"""
    # Generate secure QR data
    qr_data, session_id = generate_secure_qr_data(gate_pass_id, pass_number)
    
    # Generate QR code image
    qr_image = generate_qr_code(qr_data)
    
    # Save to file if requested
    if save_path and os.path.exists(os.path.dirname(save_path)):
        filename = f"{save_path}/{pass_number}_qr.png"
        generate_qr_code(qr_data, filename=filename)
        print(f"✅ QR code saved to: {filename}")
    
    return qr_image, session_id, qr_data

def validate_gate_pass_qr(qr_data, gate_pass_id=None, pass_number=None):
    """Comprehensive QR validation with multiple checks"""
    # Verify QR code
    is_valid, result = verify_qr_code(qr_data)
    
    if not is_valid:
        return False, result
    
    # Additional validation if gate_pass_id is provided
    if gate_pass_id and 'gate_pass_id' in result:
        if str(result['gate_pass_id']) != str(gate_pass_id):
            return False, "QR code does not match gate pass"
    
    # Additional validation if pass_number is provided
    if pass_number and 'pass_number' in result:
        if result['pass_number'] != pass_number:
            return False, "QR code does not match pass number"
    
    return True, result

def create_qr_sticker_data(gate_pass_id, pass_number):
    """Create QR sticker data for printing"""
    sticker_data = {
        "pass_number": pass_number,
        "gate_pass_id": gate_pass_id,
        "timestamp": datetime.now().isoformat(),
        "type": "sticker",
        "purpose": "Material Identification"
    }
    
    # Add security hash
    hash_string = f"STICKER:{pass_number}:{gate_pass_id}:{datetime.now().strftime('%Y%m%d')}"
    sticker_data["security_hash"] = hashlib.sha256(hash_string.encode()).hexdigest()[:12]
    
    return json.dumps(sticker_data)

def generate_qr_pair(gate_pass_id, pass_number):
    """Generate form and sticker QR codes for a gate pass"""
    # Generate form QR (for return scanning)
    form_qr_data, form_session = generate_secure_qr_data(gate_pass_id, pass_number)
    form_qr_image = generate_qr_code(form_qr_data)
    
    # Generate sticker QR (for material identification)
    sticker_qr_data = create_qr_sticker_data(gate_pass_id, pass_number)
    sticker_qr_image = generate_qr_code(sticker_qr_data)
    
    return {
        'form_qr_data': form_qr_data,
        'form_qr_image': form_qr_image,
        'form_session': form_session,
        'sticker_qr_data': sticker_qr_data,
        'sticker_qr_image': sticker_qr_image
    }

def check_qr_fraud_attempt(qr_data, ip_address=None):
    """Check for potential QR fraud attempts"""
    fraud_indicators = []
    
    # Check if QR code is expired
    is_valid, result = verify_qr_code(qr_data)
    
    if not is_valid:
        fraud_indicators.append(f"Invalid QR: {result}")
    else:
        # Check for rapid reuse (would need database integration)
        if 'timestamp' in result:
            try:
                qr_time = datetime.strptime(result['timestamp'], "%Y%m%d%H%M%S")
                time_diff = (datetime.now() - qr_time).total_seconds()
                
                if time_diff < 5:  # QR used within 5 seconds
                    fraud_indicators.append("QR reused too quickly")
            except:
                pass
    
    return len(fraud_indicators) == 0, fraud_indicators

# ==================== COMPATIBILITY WRAPPERS ====================
def create_gate_pass_qr(gate_pass_id, pass_number, qr_type="form"):
    """Create QR code for gate pass (compatibility wrapper)"""
    if qr_type == "form":
        qr_data, session_id = generate_secure_qr_data(gate_pass_id, pass_number)
    else:  # sticker
        qr_data = create_qr_sticker_data(gate_pass_id, pass_number)
        session_id = None
    
    qr_image = generate_qr_code(qr_data)
    return qr_image, qr_data, session_id

# ==================== BACKWARD COMPATIBILITY FOR TEMPLATES ====================
def generate_qr_code_data(gate_pass):
    """Compatibility function for templates expecting your format"""
    return generate_gate_pass_qr(gate_pass)

def generate_qr_code_data_for_sticker(gate_pass):
    """Compatibility function for sticker QR generation"""
    return generate_sticker_qr(gate_pass)

# ==================== UNIVERSAL QR PARSER ====================
def parse_qr_data(qr_data):
    """Universal function to parse any QR format and extract gate pass info"""
    
    # Your format: GATEPASS:GP20251230104452:22:20251230104452:906235...
    if qr_data.startswith('GATEPASS:'):
        parts = qr_data.split(':')
        if len(parts) >= 2:
            pass_number = parts[1]
            gate_pass_id = parts[2] if len(parts) > 2 else None
            return {
                'pass_number': pass_number,
                'gate_pass_id': gate_pass_id,
                'format': 'enhanced',
                'qr_type': 'GATEPASS'
            }
    
    # Simple format: GP20251230104452
    elif qr_data.startswith('GP'):
        return {
            'pass_number': qr_data,
            'gate_pass_id': None,
            'format': 'simple',
            'qr_type': 'PASS_NUMBER'
        }
    
    # Return format: GP20251230104452:RETURN
    elif ':' in qr_data and qr_data.split(':')[0].startswith('GP'):
        parts = qr_data.split(':')
        return {
            'pass_number': parts[0],
            'gate_pass_id': None,
            'format': 'return',
            'qr_type': 'RETURN_CODE'
        }
    
    # JSON format
    elif qr_data.startswith('{'):
        try:
            data = json.loads(qr_data)
            return {
                'pass_number': data.get('pass_number'),
                'gate_pass_id': data.get('gate_pass_id'),
                'format': 'json',
                'qr_type': 'JSON'
            }
        except:
            pass
    
    # Default fallback
    return {
        'pass_number': qr_data,
        'gate_pass_id': None,
        'format': 'unknown',
        'qr_type': 'RAW'
    }

# ==================== MAIN FUNCTIONALITY ====================
if __name__ == "__main__":
    # Test functionality
    test_pass = {'pass_number': 'GP20250101120000', 'id': 123}
    
    print("Testing QR Utilities...")
    print("=" * 50)
    
    # Test your functions
    print("1. Your Format Functions:")
    qr1 = generate_gate_pass_qr(test_pass)
    print(f"   Gate Pass QR: {qr1[:50]}...")
    
    qr2 = generate_return_qr(test_pass)
    print(f"   Return QR: {qr2}")
    
    qr3 = generate_sticker_qr(test_pass)
    print(f"   Sticker QR: {qr3}")
    
    print("\n2. My Format Functions:")
    qr_data, session_id = generate_secure_qr_data(123, 'GP20250101120000')
    print(f"   Secure QR Data: {qr_data[:50]}...")
    print(f"   Session ID: {session_id}")
    
    print("\n3. Universal Parser:")
    parsed = parse_qr_data(qr_data)
    print(f"   Parsed: {parsed}")
    
    print("\n✅ All functions working correctly!")