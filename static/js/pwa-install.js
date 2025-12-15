// static/js/pwa-install.js
let deferredPrompt;

window.addEventListener('beforeinstallprompt', (e) => {
    e.preventDefault();
    deferredPrompt = e;
    showInstallPromotion();
});

function showInstallPromotion() {
    const installBtn = document.createElement('div');
    installBtn.className = 'pwa-install-banner';
    installBtn.innerHTML = `
        <div class="install-banner-content">
            <i class="fas fa-mobile-alt"></i>
            <div>
                <strong>Install Gate Pass App</strong>
                <small>Add to home screen for quick access</small>
            </div>
            <button onclick="installPWA()" class="btn btn-primary btn-sm">
                <i class="fas fa-plus"></i> Install
            </button>
            <button onclick="hideInstallBanner()" class="btn btn-outline-secondary btn-sm">
                <i class="fas fa-times"></i>
            </button>
        </div>
    `;
    document.body.appendChild(installBtn);
}

async function installPWA() {
    if (!deferredPrompt) return;
    
    deferredPrompt.prompt();
    const { outcome } = await deferredPrompt.userChoice;
    
    if (outcome === 'accepted') {
        console.log('User accepted PWA installation');
        showToast('App installed successfully!', 'success');
    } else {
        console.log('User declined PWA installation');
        showToast('Installation cancelled', 'warning');
    }
    
    deferredPrompt = null;
    hideInstallBanner();
}

function hideInstallBanner() {
    const banner = document.querySelector('.pwa-install-banner');
    if (banner) banner.remove();
}

// Check if app is running in standalone mode
if (window.matchMedia('(display-mode: standalone)').matches || 
    window.navigator.standalone === true) {
    console.log('App is running in standalone mode');
    document.body.classList.add('standalone-mode');
}

// CSS for install banner
const style = document.createElement('style');
style.textContent = `
.pwa-install-banner {
    position: fixed;
    bottom: 20px;
    left: 20px;
    right: 20px;
    background: white;
    border-radius: 10px;
    box-shadow: 0 10px 30px rgba(0,0,0,0.2);
    z-index: 9999;
    padding: 15px;
    animation: slideUp 0.3s ease-out;
}

.install-banner-content {
    display: flex;
    align-items: center;
    gap: 15px;
}

.install-banner-content i {
    font-size: 24px;
    color: #3498db;
}

.install-banner-content div {
    flex: 1;
}

@keyframes slideUp {
    from { transform: translateY(100px); opacity: 0; }
    to { transform: translateY(0); opacity: 1; }
}
`;
document.head.appendChild(style);