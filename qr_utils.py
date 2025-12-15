# qr_utils.py - Enhanced with fraud detection
import qrcode
import os
from io import BytesIO
import base64
from datetime import datetime
import hashlib
import secrets

def generate_qr_code(data, filename=None):
    try:
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=8,
            border=2,
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
        qr_time = datetime.strptime(timestamp, "%Y%m%d%H%M%S")
        current_time = datetime.now()
        time_diff = (current_time - qr_time).total_seconds()
        
        if time_diff > 300:  # 5 minutes
            return False, "QR code expired"
        
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
                'session_id': parts[4]
            }
        else:
            return False, "QR code tampered"
            
    except Exception as e:
        return False, f"Verification error: {str(e)}"

def generate_gate_pass_qr_data(gate_pass_id, pass_number):
    """Compatibility function for existing code"""
    qr_data, session_id = generate_secure_qr_data(gate_pass_id, pass_number)
    return qr_data