// script.js
document.addEventListener('DOMContentLoaded', function() {
    // Material type change handler
    const materialType = document.getElementById('materialType');
    const returnDateField = document.getElementById('returnDateField');
    
    if (materialType && returnDateField) {
        materialType.addEventListener('change', function() {
            if (this.value === 'returnable') {
                returnDateField.style.display = 'block';
                const returnDateInput = document.getElementById('expectedReturnDate');
                if (returnDateInput) returnDateInput.required = true;
            } else {
                returnDateField.style.display = 'none';
                const returnDateInput = document.getElementById('expectedReturnDate');
                if (returnDateInput) returnDateInput.required = false;
            }
        });
        
        // Trigger change on page load
        materialType.dispatchEvent(new Event('change'));
    }
    
    // Auto-dismiss alerts
    const alerts = document.querySelectorAll('.alert');
    alerts.forEach(alert => {
        setTimeout(() => {
            if (alert.classList.contains('show')) {
                const bsAlert = new bootstrap.Alert(alert);
                bsAlert.close();
            }
        }, 5000);
    });
    
    // Print functionality
    const printButtons = document.querySelectorAll('.print-btn');
    printButtons.forEach(btn => {
        btn.addEventListener('click', function() {
            window.print();
        });
    });
    
    // Form validation
    const forms = document.querySelectorAll('form');
    forms.forEach(form => {
        form.addEventListener('submit', function(e) {
            const submitBtn = this.querySelector('button[type="submit"]');
            if (submitBtn) {
                submitBtn.disabled = true;
                submitBtn.innerHTML = '<span class="loading-spinner"></span> Processing...';
            }
        });
    });
});

// QR Code matching functionality
function verifyQRMatch() {
    const formQR = document.getElementById('formQR');
    const stickerQR = document.getElementById('stickerQR');
    
    if (!formQR || !stickerQR || !formQR.value || !stickerQR.value) {
        alert('Please scan both QR codes!');
        return;
    }
    
    const verifyBtn = document.getElementById('verifyBtn');
    const originalText = verifyBtn.innerHTML;
    
    verifyBtn.disabled = true;
    verifyBtn.innerHTML = '<span class="loading-spinner"></span> Verifying...';
    
    fetch('/verify_qr_match', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            form_qr: formQR.value,
            sticker_qr: stickerQR.value
        })
    })
    .then(response => response.json())
    .then(data => {
        const resultDiv = document.getElementById('matchResult');
        if (data.success) {
            resultDiv.innerHTML = '<div class="alert alert-success"><strong>MATCH</strong> - QR codes verified successfully!</div>';
        } else {
            resultDiv.innerHTML = `<div class="alert alert-danger"><strong>DON'T MATCH</strong> - ${data.message}</div>`;
        }
    })
    .catch(error => {
        console.error('Error:', error);
        alert('Error verifying QR codes!');
    })
    .finally(() => {
        verifyBtn.disabled = false;
        verifyBtn.innerHTML = originalText;
    });
}

// Mark as returned functionality
function markAsReturned(gatePassId) {
    if (confirm('Are you sure you want to mark this material as returned?')) {
        fetch('/mark_returned/' + gatePassId, {
            method: 'POST'
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                alert('Material marked as returned successfully!');
                location.reload();
            } else {
                alert('Error: ' + data.message);
            }
        })
        .catch(error => {
            console.error('Error:', error);
            alert('Error marking material as returned!');
        });
    }
}

// Camera functionality
function initializeCamera() {
    let stream = null;
    let photoCount = 0;
    const maxPhotos = 4;
    let captureInterval = null;

    const startCameraBtn = document.getElementById('startCamera');
    const stopCameraBtn = document.getElementById('stopCamera');
    const cameraSection = document.getElementById('cameraSection');
    const capturedPhotos = document.getElementById('capturedPhotos');

    if (startCameraBtn) {
        startCameraBtn.addEventListener('click', startCamera);
    }
    if (stopCameraBtn) {
        stopCameraBtn.addEventListener('click', stopCamera);
    }

    async function startCamera() {
        try {
            stream = await navigator.mediaDevices.getUserMedia({ 
                video: { 
                    facingMode: 'environment',
                    width: { ideal: 1280 },
                    height: { ideal: 720 }
                } 
            });
            
            const video = document.getElementById('video');
            video.srcObject = stream;
            
            cameraSection.style.display = 'block';
            startCameraBtn.style.display = 'none';
            stopCameraBtn.style.display = 'inline-block';
            
            // Start automatic photo capture
            photoCount = 0;
            capturedPhotos.innerHTML = '';
            captureInterval = setInterval(capturePhoto, 3000);
            
        } catch (err) {
            console.error('Error accessing camera:', err);
            alert('Error accessing camera: ' + err.message);
        }
    }

    function stopCamera() {
        if (stream) {
            stream.getTracks().forEach(track => track.stop());
        }
        if (captureInterval) {
            clearInterval(captureInterval);
        }
        
        cameraSection.style.display = 'none';
        startCameraBtn.style.display = 'inline-block';
        stopCameraBtn.style.display = 'none';
    }

    function capturePhoto() {
        if (photoCount >= maxPhotos) {
            clearInterval(captureInterval);
            stopCameraBtn.style.display = 'none';
            return;
        }
        
        const video = document.getElementById('video');
        const canvas = document.getElementById('canvas');
        const context = canvas.getContext('2d');
        
        // Set canvas size to match video
        canvas.width = video.videoWidth;
        canvas.height = video.videoHeight;
        
        // Draw video frame to canvas
        context.drawImage(video, 0, 0, canvas.width, canvas.height);
        
        // Convert to data URL
        const photoData = canvas.toDataURL('image/jpeg');
        
        // Display captured photo
        displayCapturedPhoto(photoData, photoCount + 1);
        
        // Store in hidden input
        addPhotoToForm(photoData);
        
        photoCount++;
        
        if (photoCount >= maxPhotos) {
            clearInterval(captureInterval);
            stopCameraBtn.style.display = 'none';
            
            // Show completion message
            capturedPhotos.innerHTML += `
                <div class="col-12">
                    <div class="alert alert-success text-center">
                        <i class="fas fa-check-circle"></i> 
                        Successfully captured ${maxPhotos} photos!
                    </div>
                </div>
            `;
        }
    }

    function displayCapturedPhoto(photoData, number) {
        const photoCol = document.createElement('div');
        photoCol.className = 'col-md-3 col-6 mb-3';
        photoCol.innerHTML = `
            <div class="text-center">
                <img src="${photoData}" class="captured-photo" alt="Photo ${number}">
                <div class="small text-muted">Photo ${number}</div>
            </div>
        `;
        
        capturedPhotos.appendChild(photoCol);
    }

    function addPhotoToForm(photoData) {
        const input = document.createElement('input');
        input.type = 'hidden';
        input.name = 'captured_images[]';
        input.value = photoData;
        
        document.getElementById('gatePassForm').appendChild(input);
    }
}

// Initialize camera when page loads
if (document.getElementById('startCamera')) {
    initializeCamera();
}

// Auto-refresh notifications every 30 seconds
setInterval(() => {
    // You can implement notification refresh here if needed
}, 30000);


// script.js - Add mobile camera simulation
// ... existing code ...

// Mobile Camera QR Simulation
function simulateMobileQRCamera() {
    const scenarios = [
        {
            name: "Correct Scan",
            description: "Perfect mobile camera scan",
            success: true
        },
        {
            name: "Blurry Image", 
            description: "Camera focus issue - wrong QR detected",
            success: false
        },
        {
            name: "Low Light",
            description: "Poor lighting - QR code misread",
            success: false
        },
        {
            name: "Reflection",
            description: "Screen reflection causes scan error",
            success: false
        },
        {
            name: "Fake QR",
            description: "Scanned fake QR code from different source",
            success: false
        }
    ];
    
    const randomScenario = scenarios[Math.floor(Math.random() * scenarios.length)];
    
    return {
        scenario: randomScenario,
        timestamp: new Date().toISOString(),
        isMobileScan: true
    };
}

// Enhanced QR verification with mobile simulation
function verifyQRMatchWithMobileCheck(formQR, stickerQR) {
    // Simulate mobile camera behavior
    const mobileScanResult = simulateMobileQRCamera();
    
    if (!mobileScanResult.scenario.success) {
        return {
            success: false,
            message: `MOBILE CAMERA ERROR: ${mobileScanResult.scenario.description}`,
            scenario: mobileScanResult.scenario.name,
            isMobileError: true
        };
    }
    
    // Continue with normal verification if mobile scan was successful
    return verifyQRMatch(formQR, stickerQR);
}
