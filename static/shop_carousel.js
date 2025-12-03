/**
 * UPlanet Vitrine - Cover Flow JavaScript
 * Handles gesture-based navigation and carousel animation
 * 
 * Features:
 * - iPod Cover Flow 3D carousel
 * - Gesture detection polling from Python API
 * - Mouse/touch fallback navigation
 * - Thumbs-up photo capture with QR display
 * 
 * @author CopyLaRadio - UPlanet
 */

// === Configuration ===
const CONFIG = {
    API_BASE: '',  // Same origin
    POLL_INTERVAL: 50,  // ms - Gesture polling frequency
    EVENTS_REFRESH: 30000,  // ms - Nostr events refresh
    QR_DISPLAY_TIME: 10,  // seconds
    THUMBS_UP_HOLD: 1.5,  // seconds
    OPEN_HAND_HOLD: 1.0,  // seconds - Hold to show detail
    ANIMATION_DURATION: 500,  // ms
    MAX_VISIBLE_CARDS: 5,  // Cards visible at once
};

// === State ===
const state = {
    events: [],
    currentIndex: 0,
    loading: true,
    gesturePolling: null,
    eventsPolling: null,
    showDetail: false,
    showQR: false,
    qrCountdown: 0,
    qrInterval: null,
    thumbsUpProgress: 0,
    lastAction: 'idle',
    mouseEnabled: true,
    lightMode: false,
    timeUntilDark: 0,
    // WebSocket
    socket: null,
    useWebSocket: false,
};

// === DOM Elements ===
const DOM = {
    carouselTrack: null,
    navZoneLeft: null,
    navZoneRight: null,
    centerHint: null,
    detailPanel: null,
    qrOverlay: null,
    captureProgress: null,
    navDots: null,
    gestureStatus: null,
    messageCount: null,
    pipGestureIcon: null,
    pipGestureName: null,
};

// === Initialize ===
document.addEventListener('DOMContentLoaded', () => {
    initDOM();
    initMatrixBackground();
    loadEvents();
    startGesturePolling();
    initMouseNavigation();
    initKeyboardNavigation();
});

function initDOM() {
    DOM.carouselTrack = document.getElementById('carousel-track');
    DOM.navZoneLeft = document.getElementById('nav-zone-left');
    DOM.navZoneRight = document.getElementById('nav-zone-right');
    DOM.centerHint = document.getElementById('center-hint');
    DOM.detailPanel = document.getElementById('detail-panel');
    DOM.qrOverlay = document.getElementById('qr-overlay');
    DOM.captureProgress = document.getElementById('capture-progress');
    DOM.navDots = document.getElementById('nav-dots');
    DOM.gestureStatus = document.getElementById('gesture-status');
    DOM.messageCount = document.getElementById('message-count');
    DOM.pipGestureIcon = document.getElementById('pip-gesture-icon');
    DOM.pipGestureName = document.getElementById('pip-gesture-name');
    
    // Detail panel close button
    document.getElementById('detail-close')?.addEventListener('click', hideDetail);
    
    // Click outside to close
    DOM.detailPanel?.addEventListener('click', (e) => {
        if (e.target === DOM.detailPanel) hideDetail();
    });
    
    DOM.qrOverlay?.addEventListener('click', hideQR);
}

// === Matrix Background Effect ===
function initMatrixBackground() {
    const canvas = document.getElementById('matrix-bg');
    if (!canvas) return;
    
    const ctx = canvas.getContext('2d');
    
    function resize() {
        canvas.width = window.innerWidth;
        canvas.height = window.innerHeight;
    }
    resize();
    window.addEventListener('resize', resize);
    
    const chars = 'ア゙ウカキクケコサシスセソタチツテトナニヌネノハヒフヘホマミムメモヤユヨラリルレロワヲン0123456789';
    const fontSize = 14;
    const columns = Math.floor(canvas.width / fontSize);
    const drops = new Array(columns).fill(1);
    
    function draw() {
        ctx.fillStyle = 'rgba(10, 10, 15, 0.05)';
        ctx.fillRect(0, 0, canvas.width, canvas.height);
        
        ctx.fillStyle = '#00d4ff';
        ctx.font = `${fontSize}px monospace`;
        
        for (let i = 0; i < drops.length; i++) {
            const text = chars[Math.floor(Math.random() * chars.length)];
            ctx.fillText(text, i * fontSize, drops[i] * fontSize);
            
            if (drops[i] * fontSize > canvas.height && Math.random() > 0.975) {
                drops[i] = 0;
            }
            drops[i]++;
        }
        
        requestAnimationFrame(draw);
    }
    
    draw();
}

// === Events Loading ===
async function loadEvents() {
    try {
        const response = await fetch(`${CONFIG.API_BASE}/api/events`);
        const data = await response.json();
        
        state.events = data.events || [];
        state.loading = data.loading;
        
        updateMessageCount(state.events.length);
        renderCarousel();
        renderNavDots();
        
        // Center on latest message
        if (state.events.length > 0 && state.currentIndex === 0) {
            navigateTo(0);
        }
    } catch (error) {
        console.error('[Events] Load error:', error);
        showDemoEvents();
    }
    
    // Schedule refresh
    setTimeout(loadEvents, CONFIG.EVENTS_REFRESH);
}

function showDemoEvents() {
    state.events = [
        { id: 'demo1', pubkey: 'copylaradio', content: 'Welcome to UPlanet! 🌍', images: [], created_at: Date.now() / 1000 },
        { id: 'demo2', pubkey: 'system', content: 'Gesture-controlled Nostr viewer', images: [], created_at: Date.now() / 1000 - 3600 },
    ];
    renderCarousel();
    renderNavDots();
}

function updateMessageCount(count) {
    if (DOM.messageCount) {
        DOM.messageCount.querySelector('.status-text').textContent = `${count} messages`;
    }
}

// === Carousel Rendering ===
function renderCarousel() {
    if (!DOM.carouselTrack) return;
    
    DOM.carouselTrack.innerHTML = '';
    
    state.events.forEach((event, index) => {
        const card = createCard(event, index);
        DOM.carouselTrack.appendChild(card);
    });
    
    updateCarouselPositions();
}

function createCard(event, index) {
    const card = document.createElement('div');
    card.className = 'carousel-card';
    card.dataset.index = index;
    
    // Get profile data
    const profile = event.profile || {};
    const displayName = profile.display_name || profile.name || `@${event.pubkey?.substring(0, 8) || 'anon'}`;
    const authorShort = event.pubkey ? event.pubkey.substring(0, 8) : 'anon';
    
    // Header image: content image first, then profile banner, then placeholder
    let headerImageHtml;
    if (event.images && event.images.length > 0) {
        // Use first image from content (with fallback on error)
        headerImageHtml = `<img class="card-image" src="${escapeHtml(event.images[0])}" alt="Media" loading="lazy" onerror="this.style.display='none';this.nextElementSibling.style.display='flex'"><div class="card-image-placeholder" style="display:none">📝</div>`;
    } else if (profile.banner) {
        // Fallback to profile banner (with fallback on error)
        headerImageHtml = `<img class="card-image card-banner" src="${escapeHtml(profile.banner)}" alt="Banner" loading="lazy" onerror="this.style.display='none';this.nextElementSibling.style.display='flex'"><div class="card-image-placeholder" style="display:none">📝</div>`;
    } else {
        // No image available
        headerImageHtml = `<div class="card-image-placeholder">📝</div>`;
    }
    const imageHtml = headerImageHtml;
    
    // Avatar - use profile picture or fallback
    const avatarHtml = profile.picture
        ? `<img class="card-avatar-img" src="${escapeHtml(profile.picture)}" alt="${escapeHtml(displayName)}" onerror="this.style.display='none';this.nextElementSibling.style.display='flex'">`
        : '';
    const avatarFallback = `<div class="card-avatar-fallback" ${profile.picture ? 'style="display:none"' : ''}>${authorShort.substring(0, 2).toUpperCase()}</div>`;
    
    // Format time
    const timeAgo = formatTimeAgo(event.created_at);
    
    card.innerHTML = `
        <div class="card-image-container">
            ${imageHtml}
        </div>
        <div class="card-content">
            <div class="card-header">
                <div class="card-avatar">
                    ${avatarHtml}
                    ${avatarFallback}
                </div>
                <span class="card-author" title="${escapeHtml(event.pubkey || '')}">${escapeHtml(displayName)}</span>
                <span class="card-time">${timeAgo}</span>
            </div>
            <p class="card-text">${escapeHtml(event.content)}</p>
            <span class="card-index">#${index + 1}</span>
        </div>
    `;
    
    // Click to show detail
    card.addEventListener('click', () => {
        if (index === state.currentIndex) {
            showDetail(event);
        } else {
            navigateTo(index);
        }
    });
    
    return card;
}

function updateCarouselPositions() {
    const cards = DOM.carouselTrack?.querySelectorAll('.carousel-card');
    if (!cards) return;
    
    cards.forEach((card, index) => {
        const offset = index - state.currentIndex;
        const absOffset = Math.abs(offset);
        
        // Only show nearby cards for performance
        if (absOffset > Math.floor(CONFIG.MAX_VISIBLE_CARDS / 2) + 1) {
            card.style.opacity = '0';
            card.style.pointerEvents = 'none';
            return;
        }
        
        // Calculate transform
        const translateX = offset * 350; // Base spacing
        const translateZ = -absOffset * 100; // Depth
        const rotateY = offset * -30; // Rotation
        const scale = 1 - absOffset * 0.15; // Scale
        const opacity = 1 - absOffset * 0.25; // Fade
        
        card.style.transform = `
            translateX(${translateX}px)
            translateZ(${translateZ}px)
            rotateY(${rotateY}deg)
            scale(${Math.max(0.5, scale)})
        `;
        card.style.opacity = Math.max(0.2, opacity);
        card.style.zIndex = CONFIG.MAX_VISIBLE_CARDS - absOffset;
        card.style.pointerEvents = 'auto';
        
        // Active state
        if (index === state.currentIndex) {
            card.classList.add('active');
        } else {
            card.classList.remove('active');
        }
    });
}

// === Navigation Dots ===
function renderNavDots() {
    if (!DOM.navDots) return;
    
    DOM.navDots.innerHTML = '';
    
    // Limit dots for many messages
    const maxDots = 15;
    const step = state.events.length > maxDots ? Math.ceil(state.events.length / maxDots) : 1;
    
    for (let i = 0; i < state.events.length; i += step) {
        const dot = document.createElement('div');
        dot.className = 'nav-dot';
        if (Math.abs(i - state.currentIndex) < step) {
            dot.classList.add('active');
        }
        dot.addEventListener('click', () => navigateTo(i));
        DOM.navDots.appendChild(dot);
    }
}

function updateNavDots() {
    const dots = DOM.navDots?.querySelectorAll('.nav-dot');
    if (!dots) return;
    
    const maxDots = 15;
    const step = state.events.length > maxDots ? Math.ceil(state.events.length / maxDots) : 1;
    
    dots.forEach((dot, i) => {
        const dotIndex = i * step;
        if (Math.abs(dotIndex - state.currentIndex) < step) {
            dot.classList.add('active');
        } else {
            dot.classList.remove('active');
        }
    });
}

// === Navigation ===
function navigateTo(index) {
    const maxIndex = state.events.length - 1;
    state.currentIndex = Math.max(0, Math.min(index, maxIndex));
    
    updateCarouselPositions();
    updateNavDots();
    
    // Sync with server
    fetch(`${CONFIG.API_BASE}/api/set_index`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ index: state.currentIndex })
    }).catch(e => console.warn('[Nav] Sync error:', e));
}

function navigateLeft() {
    if (state.currentIndex > 0) {
        navigateTo(state.currentIndex - 1);
    }
}

function navigateRight() {
    if (state.currentIndex < state.events.length - 1) {
        navigateTo(state.currentIndex + 1);
    }
}

// === Gesture Polling ===
function startGesturePolling() {
    // Try WebSocket first (more efficient)
    if (typeof io !== 'undefined') {
        try {
            console.log('[WS] Attempting WebSocket connection...');
            state.socket = io(CONFIG.API_BASE || window.location.origin, {
                transports: ['websocket', 'polling'],
                reconnection: true,
                reconnectionDelay: 1000,
                reconnectionAttempts: 5
            });
            
            state.socket.on('connect', () => {
                console.log('[WS] Connected! Using WebSocket for gestures');
                state.useWebSocket = true;
                if (DOM.gestureStatus) {
                    DOM.gestureStatus.querySelector('.status-text').textContent = 'WS Connected';
                }
            });
            
            state.socket.on('gesture', (gesture) => {
                handleGesture(gesture);
            });
            
            state.socket.on('disconnect', () => {
                console.log('[WS] Disconnected, falling back to polling');
                state.useWebSocket = false;
                startPollingFallback();
            });
            
            state.socket.on('connect_error', (error) => {
                console.log('[WS] Connection error, using polling fallback', error.message);
                state.useWebSocket = false;
                if (state.socket) {
                    state.socket.disconnect();
                    state.socket = null;
                }
                startPollingFallback();
            });
            
            return; // WebSocket will handle updates
        } catch (e) {
            console.log('[WS] WebSocket init failed, using polling', e);
        }
    } else {
        console.log('[WS] Socket.IO not available, using polling');
    }
    
    // Fallback to HTTP polling
    startPollingFallback();
}

function startPollingFallback() {
    if (state.useWebSocket) return; // Don't poll if WebSocket is active
    
    async function poll() {
        if (state.useWebSocket) return; // Stop if WebSocket reconnected
        
        try {
            const response = await fetch(`${CONFIG.API_BASE}/api/gesture`);
            const gesture = await response.json();
            
            handleGesture(gesture);
        } catch (error) {
            // Fallback to mouse-only mode
            if (DOM.gestureStatus) {
                DOM.gestureStatus.querySelector('.status-text').textContent = 'Mouse mode';
            }
        }
        
        if (!state.useWebSocket) {
            state.gesturePolling = setTimeout(poll, CONFIG.POLL_INTERVAL);
        }
    }
    
    poll();
}

function handleGesture(gesture) {
    // Update status display
    updateGestureStatus(gesture);
    
    // Handle light/dark mode
    updateThemeMode(gesture.light_mode, gesture.time_until_dark);
    
    // Handle actions
    if (gesture.action !== state.lastAction) {
        state.lastAction = gesture.action;
        
        switch (gesture.action) {
            case 'nav_left':
                // Inverted: nav_left action → navigate RIGHT
                if (!state.showDetail && !state.showQR) {
                    navigateRight();
                    flashNavZone('right');
                }
                break;
            case 'nav_right':
                // Inverted: nav_right action → navigate LEFT
                if (!state.showDetail && !state.showQR) {
                    navigateLeft();
                    flashNavZone('left');
                }
                break;
            case 'detail':
                if (!state.showQR && state.events[state.currentIndex]) {
                    showDetail(state.events[state.currentIndex]);
                }
                break;
            case 'detail_close':
                // Hand disappeared or fist made - close detail
                hideDetail();
                break;
            case 'capture':
                if (!state.showQR) {
                    capturePhoto();
                }
                break;
        }
    }
    
    // Also close detail if fist detected while detail is open
    if (gesture.is_fist && state.showDetail) {
        hideDetail();
    }
    
    // Skip visual updates if showing QR
    if (state.showQR) return;
    
    // Update navigation zone visuals (inverted to match hand position)
    if (gesture.hand_detected && !state.showDetail) {
        if (gesture.hand_x < 0.25) {
            // Hand on left → will navigate RIGHT
            DOM.navZoneRight?.classList.add('active');
            DOM.navZoneLeft?.classList.remove('active');
        } else if (gesture.hand_x > 0.75) {
            // Hand on right → will navigate LEFT
            DOM.navZoneLeft?.classList.add('active');
            DOM.navZoneRight?.classList.remove('active');
        } else {
            DOM.navZoneLeft?.classList.remove('active');
            DOM.navZoneRight?.classList.remove('active');
        }
        
        // Show center hint when hand in center and not open
        if (gesture.hand_x > 0.35 && gesture.hand_x < 0.65 && !gesture.is_open_hand && !state.showDetail) {
            DOM.centerHint?.classList.add('visible');
        } else {
            DOM.centerHint?.classList.remove('visible');
        }
    } else {
        DOM.navZoneLeft?.classList.remove('active');
        DOM.navZoneRight?.classList.remove('active');
        DOM.centerHint?.classList.remove('visible');
    }
    
    // Open hand progress (for detail view)
    if (gesture.is_open_hand && !state.showDetail && gesture.open_hand_progress > 0) {
        showOpenHandProgress(gesture.open_hand_progress);
    } else {
        hideOpenHandProgress();
    }
    
    // Thumbs up progress
    if (gesture.is_thumbs_up && gesture.thumbs_up_progress > 0) {
        showCaptureProgress(gesture.thumbs_up_progress);
    } else {
        hideCaptureProgress();
    }
}

// === Theme Mode ===
function updateThemeMode(lightMode, timeUntilDark) {
    if (lightMode !== state.lightMode) {
        state.lightMode = lightMode;
        document.body.classList.toggle('light-mode', lightMode);
        console.log(`[Theme] Switched to ${lightMode ? 'LIGHT' : 'DARK'} mode`);
    }
    
    state.timeUntilDark = timeUntilDark;
    
    // Update countdown display if exists
    const countdownEl = document.getElementById('dark-mode-countdown');
    if (countdownEl) {
        if (timeUntilDark > 0 && !state.showDetail) {
            countdownEl.textContent = `Dark mode in ${Math.ceil(timeUntilDark)}s`;
            countdownEl.style.display = 'block';
        } else {
            countdownEl.style.display = 'none';
        }
    }
}

function updateGestureStatus(gesture) {
    if (DOM.gestureStatus) {
        let icon = '❌';
        let text = 'No hand';
        
        if (gesture.hand_detected) {
            switch (gesture.gesture_name) {
                case 'thumbs_up':
                    icon = '👍';
                    text = gesture.thumbs_up_progress > 0 
                        ? `Thumbs up ${Math.round(gesture.thumbs_up_progress * 100)}%` 
                        : 'Thumbs up';
                    break;
                case 'open_hand':
                    icon = '✋';
                    text = gesture.open_hand_progress > 0 
                        ? `Hold ${Math.round(gesture.open_hand_progress * 100)}%` 
                        : 'Open hand';
                    break;
                case 'swiping':
                    icon = '👋';
                    text = gesture.hand_x < 0.25 ? '→ Swipe RIGHT' : 
                           gesture.hand_x > 0.75 ? '← Swipe LEFT' : 'Swiping...';
                    break;
                case 'fist':
                    icon = '✊';
                    text = 'Fist (close)';
                    break;
                case 'pointing':
                    icon = '☝️';
                    text = `X: ${Math.round(gesture.hand_x * 100)}%`;
                    break;
                default:
                    icon = '🖐️';
                    text = gesture.gesture_name;
            }
        }
        
        DOM.gestureStatus.querySelector('.status-icon').textContent = icon;
        DOM.gestureStatus.querySelector('.status-text').textContent = text;
    }
    
    if (DOM.pipGestureIcon && DOM.pipGestureName) {
        const icon = gesture.hand_detected 
            ? (gesture.gesture_name === 'thumbs_up' ? '👍' : 
               gesture.gesture_name === 'fist' ? '✊' :
               gesture.gesture_name === 'swiping' ? '👋' :
               gesture.gesture_name === 'open_hand' ? '✋' : '☝️')
            : '❌';
        DOM.pipGestureIcon.textContent = icon;
        DOM.pipGestureName.textContent = gesture.gesture_name || 'none';
    }
}

function flashNavZone(side) {
    const zone = side === 'left' ? DOM.navZoneLeft : DOM.navZoneRight;
    zone?.classList.add('active');
    setTimeout(() => zone?.classList.remove('active'), 300);
}

// === Detail Panel ===
function showDetail(event) {
    if (!DOM.detailPanel || !event) return;
    
    state.showDetail = true;
    
    // Get profile data
    const profile = event.profile || {};
    const displayName = profile.display_name || profile.name || `@${event.pubkey?.substring(0, 8) || 'anon'}`;
    const pubkeyShort = event.pubkey ? event.pubkey.substring(0, 16) + '...' : 'Unknown';
    
    // Banner - display content image first, then profile banner
    const bannerEl = document.getElementById('detail-banner');
    if (bannerEl) {
        let bannerUrl = null;
        
        if (event.images && event.images.length > 0) {
            // Use first image from content
            bannerUrl = event.images[0];
        } else if (profile.banner) {
            // Fallback to profile banner
            bannerUrl = profile.banner;
        }
        
        if (bannerUrl) {
            // Preload image to check if it loads correctly
            const img = new Image();
            img.onload = () => {
                bannerEl.style.backgroundImage = `url(${bannerUrl})`;
                bannerEl.style.display = 'block';
            };
            img.onerror = () => {
                bannerEl.style.backgroundImage = '';
                bannerEl.style.display = 'none';
            };
            img.src = bannerUrl;
        } else {
            bannerEl.style.backgroundImage = '';
            bannerEl.style.display = 'none';
        }
    }
    
    // Set author info
    document.getElementById('detail-name').textContent = displayName;
    document.getElementById('detail-pubkey').textContent = pubkeyShort;
    document.getElementById('detail-time').textContent = formatTimeAgo(event.created_at);
    document.getElementById('detail-text').textContent = event.content;
    
    // Avatar - use profile picture if available
    const avatar = document.getElementById('detail-avatar');
    if (profile.picture) {
        avatar.src = profile.picture;
        avatar.style.background = 'transparent';
        avatar.onerror = () => {
            avatar.src = '';
            avatar.style.background = 'linear-gradient(135deg, #00d4ff 0%, #b366ff 100%)';
        };
    } else {
        avatar.src = '';
        avatar.style.background = 'linear-gradient(135deg, #00d4ff 0%, #b366ff 100%)';
    }
    avatar.alt = displayName.substring(0, 2).toUpperCase();
    
    // About section
    const aboutEl = document.getElementById('detail-about');
    if (aboutEl && profile.about) {
        aboutEl.textContent = profile.about;
        aboutEl.style.display = 'block';
    } else if (aboutEl) {
        aboutEl.style.display = 'none';
    }
    
    // NIP-05 verification
    const nip05El = document.getElementById('detail-nip05');
    if (nip05El && profile.nip05) {
        nip05El.textContent = `✓ ${profile.nip05}`;
        nip05El.style.display = 'inline-block';
    } else if (nip05El) {
        nip05El.style.display = 'none';
    }
    
    // Images
    const imagesContainer = document.getElementById('detail-images');
    imagesContainer.innerHTML = '';
    
    if (event.images && event.images.length > 0) {
        event.images.forEach(url => {
            const img = document.createElement('img');
            img.src = url;
            img.alt = 'Media';
            img.loading = 'lazy';
            img.onclick = () => window.open(url, '_blank');
            imagesContainer.appendChild(img);
        });
    }
    
    // External links
    document.getElementById('detail-profile-btn').href = 
        `https://ipfs.copylaradio.com/ipns/copylaradio.com/nostr_profile_viewer.html?hex=${event.pubkey || ''}`;
    document.getElementById('detail-external-btn').href = 
        `https://njump.me/${event.id || ''}`;
    
    DOM.detailPanel.classList.add('visible');
    console.log('[Detail] Opened for', displayName);
}

function hideDetail() {
    if (!state.showDetail) return;
    state.showDetail = false;
    DOM.detailPanel?.classList.remove('visible');
    console.log('[Detail] Closed');
}

// === Photo Capture ===
async function capturePhoto() {
    if (state.showQR) return;
    
    // Show capturing indicator
    const captureStatus = document.getElementById('capture-status');
    if (captureStatus) {
        captureStatus.textContent = '📤 Uploading to IPFS...';
        captureStatus.classList.add('visible');
    }
    
    try {
        const response = await fetch(`${CONFIG.API_BASE}/api/capture`, {
            method: 'POST'
        });
        const data = await response.json();
        
        if (data.success) {
            console.log('[Capture] Success!', data);
            
            // Log IPFS info
            if (data.ipfs_url) {
                console.log('[Capture] IPFS URL:', data.ipfs_url);
                console.log('[Capture] IPFS CID:', data.ipfs_cid);
            }
            
            // Show QR with IPFS info
            showQR(data.qr_code, data.ipfs_url, data.ipfs_cid);
        } else {
            console.error('[Capture] Failed:', data.error);
            if (captureStatus) {
                captureStatus.textContent = '❌ Capture failed';
                setTimeout(() => captureStatus.classList.remove('visible'), 2000);
            }
        }
    } catch (error) {
        console.error('[Capture] Error:', error);
        if (captureStatus) {
            captureStatus.textContent = '❌ Network error';
            setTimeout(() => captureStatus.classList.remove('visible'), 2000);
        }
    }
}

function showCaptureProgress(progress) {
    if (!DOM.captureProgress) return;
    
    const circle = document.getElementById('capture-ring-fill');
    if (circle) {
        const circumference = 2 * Math.PI * 45; // r=45
        circle.style.strokeDashoffset = circumference * (1 - progress);
    }
    
    if (progress > 0) {
        DOM.captureProgress.classList.add('visible');
    }
}

function hideCaptureProgress() {
    DOM.captureProgress?.classList.remove('visible');
    
    const circle = document.getElementById('capture-ring-fill');
    if (circle) {
        circle.style.strokeDashoffset = 283;
    }
}

// === Open Hand Progress ===
function showOpenHandProgress(progress) {
    // Reuse capture progress UI but with different styling
    const progressEl = document.getElementById('open-hand-progress');
    if (!progressEl) return;
    
    const circle = document.getElementById('open-hand-ring-fill');
    if (circle) {
        const circumference = 2 * Math.PI * 45; // r=45
        circle.style.strokeDashoffset = circumference * (1 - progress);
    }
    
    if (progress > 0) {
        progressEl.classList.add('visible');
    }
}

function hideOpenHandProgress() {
    const progressEl = document.getElementById('open-hand-progress');
    progressEl?.classList.remove('visible');
    
    const circle = document.getElementById('open-hand-ring-fill');
    if (circle) {
        circle.style.strokeDashoffset = 283;
    }
}

// === QR Code Display ===
function showQR(qrData, ipfsUrl = null, ipfsCid = null) {
    if (!DOM.qrOverlay) return;
    
    state.showQR = true;
    state.qrCountdown = CONFIG.QR_DISPLAY_TIME;
    
    // Hide capture status
    const captureStatus = document.getElementById('capture-status');
    if (captureStatus) {
        captureStatus.classList.remove('visible');
    }
    
    // Set QR image
    const qrImg = document.getElementById('qr-image');
    if (qrImg && qrData) {
        qrImg.src = `data:image/png;base64,${qrData}`;
    }
    
    // Show IPFS info if available
    const ipfsInfoEl = document.getElementById('qr-ipfs-info');
    if (ipfsInfoEl) {
        if (ipfsUrl) {
            ipfsInfoEl.innerHTML = `
                <div class="ipfs-success">✅ Photo on IPFS!</div>
                <a href="${ipfsUrl}" target="_blank" class="ipfs-link">${ipfsCid ? ipfsCid.substring(0, 16) + '...' : 'View'}</a>
            `;
            ipfsInfoEl.style.display = 'block';
        } else {
            ipfsInfoEl.innerHTML = '<div class="ipfs-pending">⏳ IPFS upload pending...</div>';
            ipfsInfoEl.style.display = 'block';
        }
    }
    
    // Update countdown
    const countdownEl = document.getElementById('qr-countdown');
    if (countdownEl) {
        countdownEl.textContent = state.qrCountdown;
    }
    
    DOM.qrOverlay.classList.add('visible');
    
    // Start countdown
    if (state.qrInterval) clearInterval(state.qrInterval);
    
    state.qrInterval = setInterval(() => {
        state.qrCountdown--;
        if (countdownEl) {
            countdownEl.textContent = state.qrCountdown;
        }
        
        if (state.qrCountdown <= 0) {
            hideQR();
        }
    }, 1000);
}

function hideQR() {
    state.showQR = false;
    DOM.qrOverlay?.classList.remove('visible');
    
    if (state.qrInterval) {
        clearInterval(state.qrInterval);
        state.qrInterval = null;
    }
}

// === Mouse Navigation ===
function initMouseNavigation() {
    // Click navigation zones
    DOM.navZoneLeft?.addEventListener('click', () => {
        navigateLeft();
        flashNavZone('left');
    });
    
    DOM.navZoneRight?.addEventListener('click', () => {
        navigateRight();
        flashNavZone('right');
    });
    
    // Mouse wheel
    document.addEventListener('wheel', (e) => {
        if (state.showDetail || state.showQR) return;
        
        if (e.deltaY > 0 || e.deltaX > 0) {
            navigateRight();
        } else {
            navigateLeft();
        }
    }, { passive: true });
    
    // Touch swipe
    let touchStartX = 0;
    let touchStartY = 0;
    
    document.addEventListener('touchstart', (e) => {
        touchStartX = e.touches[0].clientX;
        touchStartY = e.touches[0].clientY;
    }, { passive: true });
    
    document.addEventListener('touchend', (e) => {
        if (state.showDetail || state.showQR) return;
        
        const touchEndX = e.changedTouches[0].clientX;
        const touchEndY = e.changedTouches[0].clientY;
        const diffX = touchEndX - touchStartX;
        const diffY = touchEndY - touchStartY;
        
        // Horizontal swipe
        if (Math.abs(diffX) > Math.abs(diffY) && Math.abs(diffX) > 50) {
            if (diffX > 0) {
                navigateLeft();
            } else {
                navigateRight();
            }
        }
    }, { passive: true });
}

// === Keyboard Navigation ===
function initKeyboardNavigation() {
    document.addEventListener('keydown', (e) => {
        if (state.showQR) {
            if (e.key === 'Escape') hideQR();
            return;
        }
        
        if (state.showDetail) {
            if (e.key === 'Escape') hideDetail();
            return;
        }
        
        switch (e.key) {
            case 'ArrowLeft':
            case 'a':
                navigateLeft();
                flashNavZone('left');
                break;
            case 'ArrowRight':
            case 'd':
                navigateRight();
                flashNavZone('right');
                break;
            case 'Enter':
            case ' ':
                if (state.events[state.currentIndex]) {
                    showDetail(state.events[state.currentIndex]);
                }
                e.preventDefault();
                break;
            case 'Home':
                navigateTo(0);
                break;
            case 'End':
                navigateTo(state.events.length - 1);
                break;
        }
    });
}

// === Utilities ===
function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function formatTimeAgo(timestamp) {
    if (!timestamp) return 'Unknown';
    
    const now = Math.floor(Date.now() / 1000);
    const diff = now - timestamp;
    
    if (diff < 60) return 'just now';
    if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
    if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
    if (diff < 604800) return `${Math.floor(diff / 86400)}d ago`;
    
    const date = new Date(timestamp * 1000);
    return date.toLocaleDateString();
}

// === Export for debugging ===
window.VitrineApp = {
    state,
    navigateTo,
    navigateLeft,
    navigateRight,
    showDetail,
    hideDetail,
    capturePhoto,
    loadEvents,
};

