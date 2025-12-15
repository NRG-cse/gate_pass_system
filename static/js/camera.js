// camera.js - UPDATED VERSION
let stream = null;
let photoCount = 0;
const maxPhotos = 4;
let captureInterval = null;

document.addEventListener('DOMContentLoaded', function() {
    const startCameraBtn = document.getElementById('startCamera');
    const stopCameraBtn = document.getElementById('stopCamera');
    
    if (startCameraBtn) {
        startCameraBtn.addEventListener('click', startCamera);
    }
    if (stopCameraBtn) {
        stopCameraBtn.addEventListener('click', stopCamera);
    }
});

async function startCamera() {
    try {
        // Check if browser supports camera
        if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
            throw new Error('Camera API not supported in this browser');
        }

        // Get camera stream
        stream = await navigator.mediaDevices.getUserMedia({ 
            video: { 
                facingMode: 'environment',
                width: { ideal: 1280 },
                height: { ideal: 720 }
            } 
        });
        
        const video = document.getElementById('video');
        if (!video) {
            throw new Error('Video element not found');
        }
        
        video.srcObject = stream;
        
        document.getElementById('cameraSection').style.display = 'block';
        document.getElementById('startCamera').style.display = 'none';
        document.getElementById('stopCamera').style.display = 'inline-block';
        
        // Start automatic photo capture
        photoCount = 0;
        document.getElementById('capturedPhotos').innerHTML = '';
        captureInterval = setInterval(capturePhoto, 3000); // 3 seconds interval
        
    } catch (err) {
        console.error('Error accessing camera:', err);
        alert('Error accessing camera: ' + err.message + '\n\nPlease ensure:\n1. You are using HTTPS or localhost\n2. Camera permissions are allowed\n3. Your device has a camera');
        
        // Fallback: Show file upload option
        showFileUploadFallback();
    }
}

function stopCamera() {
    if (stream) {
        stream.getTracks().forEach(track => track.stop());
        stream = null;
    }
    if (captureInterval) {
        clearInterval(captureInterval);
        captureInterval = null;
    }
    
    document.getElementById('cameraSection').style.display = 'none';
    document.getElementById('startCamera').style.display = 'inline-block';
    document.getElementById('stopCamera').style.display = 'none';
}

function capturePhoto() {
    if (photoCount >= maxPhotos) {
        stopCamera();
        return;
    }
    
    const video = document.getElementById('video');
    const canvas = document.getElementById('canvas');
    
    if (!video || !canvas) {
        console.error('Video or canvas element not found');
        return;
    }
    
    const context = canvas.getContext('2d');
    
    // Set canvas size to match video
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    
    // Draw video frame to canvas
    context.drawImage(video, 0, 0, canvas.width, canvas.height);
    
    // Convert to data URL
    const photoData = canvas.toDataURL('image/jpeg', 0.8);
    
    // Display captured photo
    displayCapturedPhoto(photoData, photoCount + 1);
    
    // Store in hidden input
    addPhotoToForm(photoData);
    
    photoCount++;
    
    if (photoCount >= maxPhotos) {
        stopCamera();
        
        // Show completion message
        const photoContainer = document.getElementById('capturedPhotos');
        photoContainer.innerHTML += `
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
    const photoContainer = document.getElementById('capturedPhotos');
    
    const photoCol = document.createElement('div');
    photoCol.className = 'col-md-3 col-6 mb-3';
    photoCol.innerHTML = `
        <div class="text-center">
            <img src="${photoData}" class="captured-photo" alt="Photo ${number}">
            <div class="small text-muted">Photo ${number}</div>
        </div>
    `;
    
    photoContainer.appendChild(photoCol);
}

function addPhotoToForm(photoData) {
    let form = document.getElementById('gatePassForm');
    if (!form) {
        console.error('Gate pass form not found');
        return;
    }
    
    const input = document.createElement('input');
    input.type = 'hidden';
    input.name = 'captured_images[]';
    input.value = photoData;
    
    form.appendChild(input);
}

// Fallback function for file upload
function showFileUploadFallback() {
    const cameraSection = document.getElementById('cameraSection');
    if (!cameraSection) return;
    
    cameraSection.innerHTML = `
        <div class="alert alert-warning">
            <i class="fas fa-exclamation-triangle"></i>
            <strong>Camera not available!</strong> Please upload photos manually.
        </div>
        <div class="mb-3">
            <label class="form-label">Upload Material Photos (Max 4)</label>
            <input type="file" class="form-control" id="fileUpload" accept="image/*" multiple 
                   onchange="handleFileUpload(this)" max="4">
            <div class="form-text">Select up to 4 photos of the material</div>
        </div>
        <div class="row" id="uploadedPhotos"></div>
    `;
    cameraSection.style.display = 'block';
}

function handleFileUpload(input) {
    const files = input.files;
    const uploadedPhotos = document.getElementById('uploadedPhotos');
    const form = document.getElementById('gatePassForm');
    
    // Clear existing photos
    uploadedPhotos.innerHTML = '';
    
    // Remove existing file inputs
    const existingFileInputs = form.querySelectorAll('input[name="uploaded_images[]"]');
    existingFileInputs.forEach(input => input.remove());
    
    for (let i = 0; i < Math.min(files.length, 4); i++) {
        const file = files[i];
        const reader = new FileReader();
        
        reader.onload = function(e) {
            // Display photo
            const photoCol = document.createElement('div');
            photoCol.className = 'col-md-3 col-6 mb-3';
            photoCol.innerHTML = `
                <div class="text-center">
                    <img src="${e.target.result}" class="captured-photo" alt="Uploaded Photo ${i + 1}">
                    <div class="small text-muted">Photo ${i + 1}</div>
                </div>
            `;
            uploadedPhotos.appendChild(photoCol);
            
            // Create hidden input for base64 data
            const hiddenInput = document.createElement('input');
            hiddenInput.type = 'hidden';
            hiddenInput.name = 'captured_images[]';
            hiddenInput.value = e.target.result;
            form.appendChild(hiddenInput);
        };
        
        reader.readAsDataURL(file);
    }
}