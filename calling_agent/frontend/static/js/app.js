/**
 * AI Calling Agent - Frontend Application
 * Handles UI interactions and API communications
 */

// Configuration
const API_BASE_URL = window.location.origin;
const POLL_INTERVAL = 2000; // Poll every 2 seconds

// State
let currentCall = null;
let callTimer = null;
let callStartTime = null;
let pollInterval = null;

// DOM Elements
const elements = {
    serverStatus: document.getElementById('serverStatus'),
    callForm: document.getElementById('callForm'),
    callBtn: document.getElementById('callBtn'),
    phoneNumber: document.getElementById('phoneNumber'),
    greeting: document.getElementById('greeting'),
    systemPrompt: document.getElementById('systemPrompt'),
    activeCallCard: document.getElementById('activeCallCard'),
    activeCallNumber: document.getElementById('activeCallNumber'),
    activeCallStatus: document.getElementById('activeCallStatus'),
    callTimer: document.getElementById('callTimer'),
    endCallBtn: document.getElementById('endCallBtn'),
    transcriptCard: document.getElementById('transcriptCard'),
    transcriptContainer: document.getElementById('transcriptContainer'),
    callHistoryList: document.getElementById('callHistoryList'),
    refreshHistory: document.getElementById('refreshHistory'),
    toastContainer: document.getElementById('toastContainer'),
    modal: document.getElementById('callDetailsModal'),
    modalBody: document.getElementById('modalBody'),
    closeModal: document.getElementById('closeModal'),
    // Stats
    totalCalls: document.getElementById('totalCalls'),
    completedCalls: document.getElementById('completedCalls'),
    avgDuration: document.getElementById('avgDuration'),
    activeCalls: document.getElementById('activeCalls')
};

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    initializeApp();
});

async function initializeApp() {
    // Check server health
    await checkServerHealth();

    // Load initial data
    await loadStats();
    await loadCallHistory();

    // Setup event listeners
    setupEventListeners();

    // Start periodic updates
    setInterval(checkServerHealth, 30000);
    setInterval(loadStats, 10000);
}

// Server Health Check
async function checkServerHealth() {
    try {
        const response = await fetch(`${API_BASE_URL}/ready`);
        const data = await response.json();

        elements.serverStatus.classList.remove('error');

        if (data.status === 'ready') {
            elements.serverStatus.classList.add('connected');
            elements.serverStatus.querySelector('.status-text').textContent = 'Connected';
        } else {
            elements.serverStatus.classList.remove('connected');
            elements.serverStatus.querySelector('.status-text').textContent = 'Degraded';
        }
    } catch (error) {
        elements.serverStatus.classList.add('error');
        elements.serverStatus.classList.remove('connected');
        elements.serverStatus.querySelector('.status-text').textContent = 'Disconnected';
    }
}

// Event Listeners
function setupEventListeners() {
    // Call Form Submit
    elements.callForm.addEventListener('submit', handleCallSubmit);

    // End Call Button
    elements.endCallBtn.addEventListener('click', handleEndCall);

    // Refresh History
    elements.refreshHistory.addEventListener('click', () => {
        elements.refreshHistory.querySelector('i').classList.add('fa-spin');
        loadCallHistory().then(() => {
            setTimeout(() => {
                elements.refreshHistory.querySelector('i').classList.remove('fa-spin');
            }, 500);
        });
    });

    // Modal Close
    elements.closeModal.addEventListener('click', closeModal);
    elements.modal.querySelector('.modal-backdrop').addEventListener('click', closeModal);

    // Phone number formatting
    elements.phoneNumber.addEventListener('input', formatPhoneNumber);
}

// Phone Number Formatting
function formatPhoneNumber(e) {
    let value = e.target.value.replace(/[^\d+]/g, '');
    if (!value.startsWith('+')) {
        value = '+' + value;
    }
    e.target.value = value;
}

// Handle Call Submit
async function handleCallSubmit(e) {
    e.preventDefault();

    const phoneNumber = elements.phoneNumber.value.trim();
    const greeting = elements.greeting.value.trim();
    const systemPrompt = elements.systemPrompt.value.trim();

    if (!phoneNumber || !phoneNumber.startsWith('+')) {
        showToast('Please enter a valid phone number in E.164 format', 'error');
        return;
    }

    // Disable button and show loading
    elements.callBtn.disabled = true;
    elements.callBtn.innerHTML = '<span class="loading"></span> Initiating...';

    try {
        const response = await fetch(`${API_BASE_URL}/api/v1/calls/initiate`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                phone_number: phoneNumber,
                greeting_message: greeting || undefined,
                system_prompt: systemPrompt || undefined
            })
        });

        const data = await response.json();

        if (response.ok) {
            currentCall = data;
            showActiveCall(data);
            showToast('Call initiated successfully!', 'success');
            startCallTimer();
            startPolling();
        } else {
            showToast(data.detail || 'Failed to initiate call', 'error');
        }
    } catch (error) {
        showToast('Network error. Please check your connection.', 'error');
        console.error('Call error:', error);
    } finally {
        elements.callBtn.disabled = false;
        elements.callBtn.innerHTML = '<i class="fas fa-phone"></i> <span>Start Call</span>';
    }
}

// Show Active Call Card
function showActiveCall(call) {
    elements.activeCallCard.style.display = 'block';
    elements.activeCallNumber.textContent = call.phone_number;
    updateCallStatus(call.status);

    // Show transcript card
    elements.transcriptCard.style.display = 'block';
    elements.transcriptContainer.innerHTML = '';

    // Scroll to active call
    elements.activeCallCard.scrollIntoView({ behavior: 'smooth', block: 'center' });
}

// Update Call Status
function updateCallStatus(status) {
    const statusBadge = elements.activeCallStatus.querySelector('.status-badge');
    statusBadge.className = 'status-badge ' + status;
    statusBadge.textContent = status.replace('_', ' ');
}

// Start Call Timer
function startCallTimer() {
    callStartTime = Date.now();
    callTimer = setInterval(() => {
        const elapsed = Math.floor((Date.now() - callStartTime) / 1000);
        const minutes = Math.floor(elapsed / 60).toString().padStart(2, '0');
        const seconds = (elapsed % 60).toString().padStart(2, '0');
        elements.callTimer.textContent = `${minutes}:${seconds}`;
    }, 1000);
}

// Stop Call Timer
function stopCallTimer() {
    if (callTimer) {
        clearInterval(callTimer);
        callTimer = null;
    }
}

// Start Polling for Call Status
function startPolling() {
    if (pollInterval) clearInterval(pollInterval);

    pollInterval = setInterval(async () => {
        if (!currentCall) {
            stopPolling();
            return;
        }

        try {
            const response = await fetch(`${API_BASE_URL}/api/v1/calls/${currentCall.call_id}`);
            const data = await response.json();

            if (response.ok) {
                updateCallStatus(data.status);

                // Update transcript if available
                if (data.transcript && data.transcript.length > 0) {
                    updateTranscript(data.transcript);
                }

                // Check if call ended
                if (['completed', 'failed', 'no_answer', 'busy', 'cancelled'].includes(data.status)) {
                    handleCallEnded(data);
                }
            }
        } catch (error) {
            console.error('Polling error:', error);
        }
    }, POLL_INTERVAL);
}

// Stop Polling
function stopPolling() {
    if (pollInterval) {
        clearInterval(pollInterval);
        pollInterval = null;
    }
}

// Update Transcript
function updateTranscript(transcript) {
    const existingCount = elements.transcriptContainer.children.length;

    transcript.slice(existingCount).forEach(entry => {
        const messageDiv = document.createElement('div');
        messageDiv.className = `transcript-message ${entry.speaker}`;

        messageDiv.innerHTML = `
            <div class="transcript-avatar">
                <i class="fas ${entry.speaker === 'agent' ? 'fa-robot' : 'fa-user'}"></i>
            </div>
            <div class="transcript-bubble">
                ${escapeHtml(entry.text)}
            </div>
        `;

        elements.transcriptContainer.appendChild(messageDiv);
        elements.transcriptContainer.scrollTop = elements.transcriptContainer.scrollHeight;
    });
}

// Handle End Call
async function handleEndCall() {
    if (!currentCall) return;

    elements.endCallBtn.disabled = true;
    elements.endCallBtn.innerHTML = '<span class="loading"></span> Ending...';

    try {
        const response = await fetch(`${API_BASE_URL}/api/v1/calls/${currentCall.call_id}/end`, {
            method: 'POST'
        });

        if (response.ok) {
            handleCallEnded({ status: 'completed' });
            showToast('Call ended', 'info');
        } else {
            showToast('Failed to end call', 'error');
        }
    } catch (error) {
        showToast('Network error', 'error');
    } finally {
        elements.endCallBtn.disabled = false;
        elements.endCallBtn.innerHTML = '<i class="fas fa-phone-slash"></i> End Call';
    }
}

// Handle Call Ended
function handleCallEnded(call) {
    stopCallTimer();
    stopPolling();

    setTimeout(() => {
        elements.activeCallCard.style.display = 'none';
        elements.transcriptCard.style.display = 'none';
        currentCall = null;
        elements.callTimer.textContent = '00:00';

        // Refresh history and stats
        loadCallHistory();
        loadStats();
    }, 2000);
}

// Load Stats
async function loadStats() {
    try {
        const response = await fetch(`${API_BASE_URL}/stats`);
        const data = await response.json();

        elements.totalCalls.textContent = data.total_calls_processed;
        elements.completedCalls.textContent = data.completed_calls;
        elements.activeCalls.textContent = data.active_calls;

        // Format average duration
        const avgSeconds = Math.round(data.average_duration_seconds || 0);
        const minutes = Math.floor(avgSeconds / 60);
        const seconds = avgSeconds % 60;
        elements.avgDuration.textContent = `${minutes}:${seconds.toString().padStart(2, '0')}`;
    } catch (error) {
        console.error('Stats error:', error);
    }
}

// Load Call History
async function loadCallHistory() {
    try {
        const response = await fetch(`${API_BASE_URL}/api/v1/calls?limit=20`);
        const calls = await response.json();

        if (calls.length === 0) {
            elements.callHistoryList.innerHTML = `
                <div class="empty-state">
                    <i class="fas fa-phone-slash"></i>
                    <p>No calls yet</p>
                    <span>Start your first call above</span>
                </div>
            `;
            return;
        }

        elements.callHistoryList.innerHTML = calls.map(call => `
            <div class="call-history-item" onclick="showCallDetails('${call.call_id}')">
                <div class="call-avatar">
                    <i class="fas fa-user"></i>
                </div>
                <div class="call-info">
                    <span class="call-number">${call.phone_number}</span>
                    <div class="call-meta">
                        <span class="status-badge ${call.status}">${call.status}</span>
                        <span>${formatDate(call.created_at)}</span>
                        ${call.duration_seconds ? `<span>${formatDuration(call.duration_seconds)}</span>` : ''}
                    </div>
                </div>
            </div>
        `).join('');
    } catch (error) {
        console.error('History error:', error);
    }
}

// Show Call Details Modal
async function showCallDetails(callId) {
    try {
        const response = await fetch(`${API_BASE_URL}/api/v1/calls/${callId}`);
        const call = await response.json();

        elements.modalBody.innerHTML = `
            <div class="modal-call-details">
                <div class="detail-row">
                    <span class="detail-label">Call ID</span>
                    <span class="detail-value">${call.call_id}</span>
                </div>
                <div class="detail-row">
                    <span class="detail-label">Phone Number</span>
                    <span class="detail-value">${call.phone_number}</span>
                </div>
                <div class="detail-row">
                    <span class="detail-label">Status</span>
                    <span class="detail-value"><span class="status-badge ${call.status}">${call.status}</span></span>
                </div>
                <div class="detail-row">
                    <span class="detail-label">Direction</span>
                    <span class="detail-value">${call.direction}</span>
                </div>
                <div class="detail-row">
                    <span class="detail-label">Created</span>
                    <span class="detail-value">${formatDate(call.created_at)}</span>
                </div>
                ${call.duration_seconds ? `
                <div class="detail-row">
                    <span class="detail-label">Duration</span>
                    <span class="detail-value">${formatDuration(call.duration_seconds)}</span>
                </div>
                ` : ''}
                ${call.transcript && call.transcript.length > 0 ? `
                <div class="detail-section">
                    <h4>Transcript</h4>
                    <div class="modal-transcript">
                        ${call.transcript.map(t => `
                            <div class="transcript-entry ${t.speaker}">
                                <strong>${t.speaker}:</strong> ${escapeHtml(t.text)}
                            </div>
                        `).join('')}
                    </div>
                </div>
                ` : ''}
                ${call.summary ? `
                <div class="detail-section">
                    <h4>Summary</h4>
                    <p>${escapeHtml(call.summary.summary)}</p>
                </div>
                ` : ''}
            </div>
        `;

        elements.modal.classList.add('active');
    } catch (error) {
        showToast('Failed to load call details', 'error');
    }
}

// Close Modal
function closeModal() {
    elements.modal.classList.remove('active');
}

// Toast Notifications
function showToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;

    const icons = {
        success: 'fa-check',
        error: 'fa-exclamation',
        info: 'fa-info'
    };

    toast.innerHTML = `
        <div class="toast-icon">
            <i class="fas ${icons[type]}"></i>
        </div>
        <span>${escapeHtml(message)}</span>
    `;

    elements.toastContainer.appendChild(toast);

    // Auto remove after 5 seconds
    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateX(100px)';
        setTimeout(() => toast.remove(), 300);
    }, 5000);
}

// Utility Functions
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function formatDate(dateString) {
    const date = new Date(dateString);
    const now = new Date();
    const diff = now - date;

    if (diff < 60000) return 'Just now';
    if (diff < 3600000) return `${Math.floor(diff / 60000)}m ago`;
    if (diff < 86400000) return `${Math.floor(diff / 3600000)}h ago`;

    return date.toLocaleDateString('en-US', {
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
    });
}

function formatDuration(seconds) {
    const minutes = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${minutes}:${secs.toString().padStart(2, '0')}`;
}

// Make showCallDetails available globally
window.showCallDetails = showCallDetails;
