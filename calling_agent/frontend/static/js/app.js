/**
 * VoiceAI - Intelligent Calling Platform
 * Frontend Application
 */

// Configuration
const API_BASE_URL = window.location.origin;
const POLL_INTERVAL = 2000;
const REFRESH_INTERVAL = 15000;

// Application State
const state = {
    currentCall: null,
    callTimer: null,
    callStartTime: null,
    pollInterval: null,
    selectedConversation: null,
    conversations: [],
    dashboardData: null,
    currentSection: 'dashboard'
};

// DOM Elements Cache
const elements = {};

// Initialize Application
document.addEventListener('DOMContentLoaded', () => {
    cacheElements();
    initializeApp();
});

function cacheElements() {
    // Sidebar
    elements.sidebar = document.getElementById('sidebar');
    elements.menuToggle = document.getElementById('menuToggle');
    elements.navItems = document.querySelectorAll('.nav-item');
    elements.connectionStatus = document.getElementById('connectionStatus');
    elements.conversationCount = document.getElementById('conversationCount');

    // Top bar
    elements.pageTitle = document.getElementById('pageTitle');
    elements.quickCallBtn = document.getElementById('quickCallBtn');
    elements.activeCallsIndicator = document.getElementById('activeCallsIndicator');
    elements.activeCallCount = document.getElementById('activeCallCount');

    // Sections
    elements.sections = document.querySelectorAll('.content-section');

    // Dashboard
    elements.statTotalCalls = document.getElementById('statTotalCalls');
    elements.statCompleted = document.getElementById('statCompleted');
    elements.statAvgDuration = document.getElementById('statAvgDuration');
    elements.statSuccessRate = document.getElementById('statSuccessRate');
    elements.recentConversationsList = document.getElementById('recentConversationsList');
    elements.actionItemsList = document.getElementById('actionItemsList');
    elements.actionItemsBadge = document.getElementById('actionItemsBadge');
    elements.refreshConversations = document.getElementById('refreshConversations');

    // Sentiment
    elements.donutPositive = document.getElementById('donutPositive');
    elements.donutNeutral = document.getElementById('donutNeutral');
    elements.donutNegative = document.getElementById('donutNegative');
    elements.totalSentimentCalls = document.getElementById('totalSentimentCalls');
    elements.legendPositive = document.getElementById('legendPositive');
    elements.legendNeutral = document.getElementById('legendNeutral');
    elements.legendNegative = document.getElementById('legendNegative');

    // Call Form
    elements.callForm = document.getElementById('callForm');
    elements.phoneNumber = document.getElementById('phoneNumber');
    elements.greeting = document.getElementById('greeting');
    elements.systemPrompt = document.getElementById('systemPrompt');
    elements.initiateCallBtn = document.getElementById('initiateCallBtn');

    // Active Call
    elements.activeCallPanel = document.getElementById('activeCallPanel');
    elements.activePhoneNumber = document.getElementById('activePhoneNumber');
    elements.activeCallStatusBadge = document.getElementById('activeCallStatusBadge');
    elements.activeCallTimer = document.getElementById('activeCallTimer');
    elements.liveTranscript = document.getElementById('liveTranscript');
    elements.endCallBtn = document.getElementById('endCallBtn');

    // Conversations
    elements.searchConversations = document.getElementById('searchConversations');
    elements.filterButtons = document.querySelectorAll('.filter-btn');
    elements.allConversationsList = document.getElementById('allConversationsList');
    elements.conversationDetailPanel = document.getElementById('conversationDetailPanel');

    // Analytics
    elements.completedBar = document.getElementById('completedBar');
    elements.failedBar = document.getElementById('failedBar');
    elements.activeBar = document.getElementById('activeBar');
    elements.analyticsCompleted = document.getElementById('analyticsCompleted');
    elements.analyticsFailed = document.getElementById('analyticsFailed');
    elements.analyticsActive = document.getElementById('analyticsActive');
    elements.insightDuration = document.getElementById('insightDuration');
    elements.insightSuccessRate = document.getElementById('insightSuccessRate');
    elements.insightTotal = document.getElementById('insightTotal');
    elements.activityFeed = document.getElementById('activityFeed');

    // Modals
    elements.quickCallModal = document.getElementById('quickCallModal');
    elements.quickPhoneNumber = document.getElementById('quickPhoneNumber');
    elements.conversationModal = document.getElementById('conversationModal');
    elements.conversationModalBody = document.getElementById('conversationModalBody');

    // Toast
    elements.toastContainer = document.getElementById('toastContainer');
}

async function initializeApp() {
    // Check server connection
    await checkConnection();

    // Load initial data
    await Promise.all([
        loadDashboardData(),
        loadConversations()
    ]);

    // Setup event listeners
    setupEventListeners();

    // Start periodic updates
    setInterval(checkConnection, 30000);
    setInterval(() => {
        loadDashboardData();
        loadConversations();
    }, REFRESH_INTERVAL);
}

// Connection Check
async function checkConnection() {
    try {
        const response = await fetch(`${API_BASE_URL}/ready`);
        const data = await response.json();

        if (data.status === 'ready') {
            elements.connectionStatus.classList.add('connected');
            elements.connectionStatus.classList.remove('error');
            elements.connectionStatus.querySelector('.status-text').textContent = 'Connected';
        } else {
            elements.connectionStatus.classList.remove('connected');
            elements.connectionStatus.querySelector('.status-text').textContent = 'Degraded';
        }
    } catch (error) {
        elements.connectionStatus.classList.remove('connected');
        elements.connectionStatus.classList.add('error');
        elements.connectionStatus.querySelector('.status-text').textContent = 'Disconnected';
    }
}

// Event Listeners
function setupEventListeners() {
    // Sidebar navigation
    elements.navItems.forEach(item => {
        item.addEventListener('click', (e) => {
            e.preventDefault();
            const section = item.dataset.section;
            navigateToSection(section);
        });
    });

    // Menu toggle (mobile)
    elements.menuToggle?.addEventListener('click', () => {
        elements.sidebar.classList.toggle('open');
    });

    // Quick call button - navigate to new call section
    elements.quickCallBtn?.addEventListener('click', () => {
        navigateToSection('new-call');
        elements.phoneNumber?.focus();
    });

    // Close quick call modal
    document.getElementById('closeQuickCall')?.addEventListener('click', () => {
        elements.quickCallModal.classList.remove('active');
    });

    // Start quick call
    document.getElementById('startQuickCall')?.addEventListener('click', () => {
        const phone = elements.quickPhoneNumber.value.trim();
        if (phone) {
            elements.quickCallModal.classList.remove('active');
            elements.phoneNumber.value = phone;
            navigateToSection('new-call');
            setTimeout(() => handleCallSubmit(new Event('submit')), 100);
        }
    });

    // Call form
    elements.callForm?.addEventListener('submit', handleCallSubmit);

    // End call button
    elements.endCallBtn?.addEventListener('click', handleEndCall);

    // Phone number formatting
    elements.phoneNumber?.addEventListener('input', formatPhoneNumber);
    elements.quickPhoneNumber?.addEventListener('input', formatPhoneNumber);

    // Refresh conversations
    elements.refreshConversations?.addEventListener('click', async () => {
        const icon = elements.refreshConversations.querySelector('i');
        icon.classList.add('fa-spin');
        await Promise.all([loadDashboardData(), loadConversations()]);
        setTimeout(() => icon.classList.remove('fa-spin'), 500);
    });

    // Search conversations
    elements.searchConversations?.addEventListener('input', (e) => {
        filterConversations(e.target.value);
    });

    // Filter buttons
    elements.filterButtons?.forEach(btn => {
        btn.addEventListener('click', () => {
            elements.filterButtons.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            filterConversations(elements.searchConversations?.value || '', btn.dataset.filter);
        });
    });

    // Close conversation modal
    document.getElementById('closeConversationModal')?.addEventListener('click', () => {
        elements.conversationModal.classList.remove('active');
    });

    // Modal backdrop clicks
    document.querySelectorAll('.modal-backdrop').forEach(backdrop => {
        backdrop.addEventListener('click', () => {
            backdrop.closest('.modal').classList.remove('active');
        });
    });

    // Quick call on Enter
    elements.quickPhoneNumber?.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
            document.getElementById('startQuickCall').click();
        }
    });
}

// Navigation
function navigateToSection(section) {
    state.currentSection = section;

    // Update nav items
    elements.navItems.forEach(item => {
        item.classList.toggle('active', item.dataset.section === section);
    });

    // Update sections
    elements.sections.forEach(sec => {
        sec.classList.toggle('active', sec.id === `${section}-section`);
    });

    // Update page title
    const titles = {
        'dashboard': 'Dashboard',
        'new-call': 'New Call',
        'conversations': 'Conversations',
        'analytics': 'Analytics'
    };
    elements.pageTitle.textContent = titles[section] || 'Dashboard';

    // Close sidebar on mobile
    elements.sidebar.classList.remove('open');

    // Load section-specific data
    if (section === 'conversations') {
        renderAllConversations();
    } else if (section === 'analytics') {
        updateAnalytics();
    }
}

// Phone Number Formatting
function formatPhoneNumber(e) {
    let value = e.target.value.replace(/[^\d+]/g, '');
    if (value && !value.startsWith('+')) {
        value = '+' + value;
    }
    e.target.value = value;
}

// Load Dashboard Data
async function loadDashboardData() {
    try {
        const response = await fetch(`${API_BASE_URL}/api/v1/calls/dashboard/analytics`);

        if (!response.ok) {
            throw new Error('Failed to load dashboard data');
        }

        const data = await response.json();
        state.dashboardData = data;

        // Update UI components
        if (data.statistics) {
            updateStats(data.statistics);
        }

        if (data.sentiment_distribution) {
            updateSentimentChart(data.sentiment_distribution);
        }

        if (data.action_items) {
            updateActionItems(data.action_items);
        }

        if (data.recent_conversations) {
            renderRecentConversations(data.recent_conversations);
        }

        updateConversationCount(data.statistics?.total_calls || 0);
        updateActiveCallsIndicator(data.statistics?.active_calls || 0);

    } catch (error) {
        console.error('Failed to load dashboard data:', error);
        // Show empty state on error
        renderRecentConversations([]);
    }
}

// Load Conversations
async function loadConversations() {
    try {
        const response = await fetch(`${API_BASE_URL}/api/v1/calls/?limit=50`);

        if (!response.ok) {
            throw new Error('Failed to load conversations');
        }

        state.conversations = await response.json();
        updateConversationCount(state.conversations.length);

        // Update conversations panel if visible
        if (state.currentSection === 'conversations') {
            renderAllConversations();
        }
    } catch (error) {
        console.error('Failed to load conversations:', error);
        state.conversations = [];
    }
}

// Update Stats
function updateStats(stats) {
    if (!stats) return;

    elements.statTotalCalls.textContent = stats.total_calls || 0;
    elements.statCompleted.textContent = stats.completed_calls || 0;
    elements.statSuccessRate.textContent = `${(stats.success_rate || 0).toFixed(0)}%`;

    const avgSeconds = stats.average_duration_seconds || 0;
    const avgMinutes = Math.floor(avgSeconds / 60);
    const avgSecs = Math.round(avgSeconds % 60);
    elements.statAvgDuration.textContent = `${avgMinutes}:${avgSecs.toString().padStart(2, '0')}`;
}

// Update Sentiment Chart
function updateSentimentChart(sentiment) {
    if (!sentiment) {
        sentiment = { positive: 0, neutral: 0, negative: 0 };
    }

    const positive = sentiment.positive || 0;
    const neutral = sentiment.neutral || 0;
    const negative = sentiment.negative || 0;
    const total = positive + neutral + negative;

    elements.totalSentimentCalls.textContent = total;
    elements.legendPositive.textContent = positive;
    elements.legendNeutral.textContent = neutral;
    elements.legendNegative.textContent = negative;

    // Calculate circumference for donut chart (r=40, so 2*PI*40 = 251.2)
    const circumference = 251.2;

    if (total === 0) {
        // Show empty ring
        elements.donutPositive.setAttribute('stroke-dasharray', '0 251.2');
        elements.donutNeutral.setAttribute('stroke-dasharray', '0 251.2');
        elements.donutNegative.setAttribute('stroke-dasharray', '0 251.2');
        return;
    }

    const positiveLen = (positive / total) * circumference;
    const neutralLen = (neutral / total) * circumference;
    const negativeLen = (negative / total) * circumference;

    // Set the segments with proper offsets
    elements.donutPositive.setAttribute('stroke-dasharray', `${positiveLen} ${circumference}`);
    elements.donutPositive.setAttribute('stroke-dashoffset', '0');

    elements.donutNeutral.setAttribute('stroke-dasharray', `${neutralLen} ${circumference}`);
    elements.donutNeutral.setAttribute('stroke-dashoffset', `-${positiveLen}`);

    elements.donutNegative.setAttribute('stroke-dasharray', `${negativeLen} ${circumference}`);
    elements.donutNegative.setAttribute('stroke-dashoffset', `-${positiveLen + neutralLen}`);
}

// Update Action Items
function updateActionItems(items) {
    if (!items) items = [];

    elements.actionItemsBadge.textContent = items.length;

    if (items.length === 0) {
        elements.actionItemsList.innerHTML = `
            <div class="empty-state small">
                <i class="fas fa-clipboard-check"></i>
                <p>No action items yet</p>
            </div>
        `;
        return;
    }

    elements.actionItemsList.innerHTML = items.slice(0, 5).map(item => `
        <div class="action-item" onclick="viewConversation('${item.call_id}')">
            <div class="action-checkbox">
                <i class="far fa-circle"></i>
            </div>
            <div class="action-content">
                <p>${escapeHtml(item.item)}</p>
                <span class="action-meta">
                    <i class="fas fa-phone"></i> ${escapeHtml(item.phone_number)}
                    ${item.created_at ? ` &bull; ${formatRelativeTime(item.created_at)}` : ''}
                </span>
            </div>
        </div>
    `).join('');
}

// Render Recent Conversations
function renderRecentConversations(conversations) {
    if (!conversations || conversations.length === 0) {
        elements.recentConversationsList.innerHTML = `
            <div class="empty-state">
                <i class="fas fa-phone-slash"></i>
                <h4>No Calls Yet</h4>
                <p>Start making calls to see your history here</p>
                <button class="btn btn-primary" onclick="navigateToSection('new-call')">
                    <i class="fas fa-phone"></i> Make Your First Call
                </button>
            </div>
        `;
        return;
    }

    elements.recentConversationsList.innerHTML = conversations.map(conv => `
        <div class="conversation-row" onclick="viewConversation('${conv.call_id}')">
            <div class="conv-avatar">
                <i class="fas fa-user"></i>
            </div>
            <div class="conv-info">
                <div class="conv-header">
                    <span class="conv-phone">${escapeHtml(conv.phone_number)}</span>
                    <span class="conv-time">${formatRelativeTime(conv.created_at)}</span>
                </div>
                <div class="conv-meta">
                    <span class="status-pill ${conv.status}">${formatStatus(conv.status)}</span>
                    ${conv.duration_seconds ? `<span class="conv-duration"><i class="fas fa-clock"></i> ${formatDuration(conv.duration_seconds)}</span>` : ''}
                    ${conv.sentiment ? `<span class="sentiment-pill ${conv.sentiment.toLowerCase()}">${conv.sentiment}</span>` : ''}
                </div>
                ${conv.summary ? `<p class="conv-summary">${escapeHtml(truncate(conv.summary, 100))}</p>` : ''}
            </div>
            <div class="conv-arrow">
                <i class="fas fa-chevron-right"></i>
            </div>
        </div>
    `).join('');
}

// Render All Conversations (for Conversations section)
function renderAllConversations() {
    const conversations = state.conversations;

    if (!conversations || conversations.length === 0) {
        elements.allConversationsList.innerHTML = `
            <div class="empty-state">
                <i class="fas fa-phone-slash"></i>
                <p>No calls found</p>
            </div>
        `;
        return;
    }

    elements.allConversationsList.innerHTML = conversations.map(conv => `
        <div class="conversation-item ${state.selectedConversation === conv.call_id ? 'selected' : ''}"
             onclick="selectConversation('${conv.call_id}')">
            <div class="conv-item-avatar">
                <i class="fas fa-user"></i>
            </div>
            <div class="conv-item-info">
                <span class="conv-item-phone">${escapeHtml(conv.phone_number)}</span>
                <div class="conv-item-meta">
                    <span class="status-pill small ${conv.status}">${formatStatus(conv.status)}</span>
                    <span>${formatRelativeTime(conv.created_at)}</span>
                </div>
            </div>
        </div>
    `).join('');
}

// Filter Conversations
function filterConversations(searchTerm, statusFilter = 'all') {
    let filtered = state.conversations;

    if (searchTerm) {
        const term = searchTerm.toLowerCase();
        filtered = filtered.filter(c =>
            c.phone_number.includes(term) ||
            c.call_id.toLowerCase().includes(term)
        );
    }

    if (statusFilter !== 'all') {
        filtered = filtered.filter(c => c.status === statusFilter);
    }

    if (filtered.length === 0) {
        elements.allConversationsList.innerHTML = `
            <div class="empty-state small">
                <i class="fas fa-search"></i>
                <p>No matching calls</p>
            </div>
        `;
        return;
    }

    elements.allConversationsList.innerHTML = filtered.map(conv => `
        <div class="conversation-item ${state.selectedConversation === conv.call_id ? 'selected' : ''}"
             onclick="selectConversation('${conv.call_id}')">
            <div class="conv-item-avatar">
                <i class="fas fa-user"></i>
            </div>
            <div class="conv-item-info">
                <span class="conv-item-phone">${escapeHtml(conv.phone_number)}</span>
                <div class="conv-item-meta">
                    <span class="status-pill small ${conv.status}">${formatStatus(conv.status)}</span>
                    <span>${formatRelativeTime(conv.created_at)}</span>
                </div>
            </div>
        </div>
    `).join('');
}

// Select Conversation
async function selectConversation(callId) {
    state.selectedConversation = callId;
    renderAllConversations();
    await loadConversationDetail(callId);
}

// View Conversation (from dashboard)
async function viewConversation(callId) {
    state.selectedConversation = callId;
    await loadConversationDetail(callId, true);
}

// Load Conversation Detail
async function loadConversationDetail(callId, showModal = false) {
    try {
        const response = await fetch(`${API_BASE_URL}/api/v1/calls/${callId}`);

        if (!response.ok) {
            throw new Error('Failed to load call details');
        }

        const call = await response.json();
        const detailHtml = generateConversationDetail(call);

        if (showModal) {
            elements.conversationModalBody.innerHTML = detailHtml;
            elements.conversationModal.classList.add('active');
        } else {
            elements.conversationDetailPanel.innerHTML = detailHtml;
        }

    } catch (error) {
        console.error('Failed to load conversation:', error);
        showToast('Failed to load call details', 'error');
    }
}

// Generate Conversation Detail HTML
function generateConversationDetail(call) {
    return `
        <div class="detail-content">
            <!-- Header -->
            <div class="detail-header">
                <div class="detail-avatar">
                    <i class="fas fa-user"></i>
                </div>
                <div class="detail-info">
                    <h3>${escapeHtml(call.phone_number)}</h3>
                    <div class="detail-meta">
                        <span class="status-pill ${call.status}">${formatStatus(call.status)}</span>
                        <span><i class="fas fa-calendar"></i> ${formatDateTime(call.created_at)}</span>
                        ${call.duration_seconds ? `<span><i class="fas fa-clock"></i> ${formatDuration(call.duration_seconds)}</span>` : ''}
                    </div>
                </div>
                ${call.status === 'completed' && !call.summary ? `
                    <button class="btn btn-primary btn-sm" onclick="analyzeCall('${call.call_id}')">
                        <i class="fas fa-brain"></i> Analyze
                    </button>
                ` : ''}
            </div>

            ${call.summary ? `
            <!-- AI Analysis -->
            <div class="detail-section">
                <h4><i class="fas fa-brain"></i> AI Analysis</h4>
                <div class="analysis-card">
                    <div class="analysis-summary">
                        <p>${escapeHtml(call.summary.summary || '')}</p>
                    </div>
                    ${call.summary.sentiment ? `
                        <div class="analysis-sentiment">
                            <span class="label">Sentiment</span>
                            <span class="sentiment-pill large ${call.summary.sentiment.toLowerCase()}">${call.summary.sentiment}</span>
                        </div>
                    ` : ''}
                    ${call.summary.key_points && call.summary.key_points.length > 0 ? `
                        <div class="analysis-points">
                            <span class="label">Key Points</span>
                            <ul>
                                ${call.summary.key_points.map(p => `<li>${escapeHtml(p)}</li>`).join('')}
                            </ul>
                        </div>
                    ` : ''}
                    ${call.summary.action_items && call.summary.action_items.length > 0 ? `
                        <div class="analysis-actions">
                            <span class="label">Action Items</span>
                            <ul class="action-list">
                                ${call.summary.action_items.map(a => `
                                    <li><i class="fas fa-check-circle"></i> ${escapeHtml(a)}</li>
                                `).join('')}
                            </ul>
                        </div>
                    ` : ''}
                </div>
            </div>
            ` : ''}

            <!-- Transcript -->
            <div class="detail-section">
                <h4><i class="fas fa-comments"></i> Transcript</h4>
                ${call.transcript && call.transcript.length > 0 ? `
                    <div class="transcript-view">
                        ${call.transcript.map(t => `
                            <div class="transcript-msg ${t.speaker}">
                                <div class="msg-avatar">
                                    <i class="fas ${t.speaker === 'agent' ? 'fa-robot' : 'fa-user'}"></i>
                                </div>
                                <div class="msg-content">
                                    <span class="msg-speaker">${t.speaker === 'agent' ? 'AI' : 'Caller'}</span>
                                    <p>${escapeHtml(t.text)}</p>
                                </div>
                            </div>
                        `).join('')}
                    </div>
                ` : `
                    <div class="empty-state small">
                        <i class="fas fa-comment-slash"></i>
                        <p>No transcript available</p>
                    </div>
                `}
            </div>

            <!-- Call Info -->
            <div class="detail-section">
                <h4><i class="fas fa-info-circle"></i> Call Info</h4>
                <div class="info-grid">
                    <div class="info-item">
                        <span class="info-label">Call ID</span>
                        <span class="info-value">${call.call_id}</span>
                    </div>
                    <div class="info-item">
                        <span class="info-label">Direction</span>
                        <span class="info-value">${call.direction || 'Outbound'}</span>
                    </div>
                    <div class="info-item">
                        <span class="info-label">Status</span>
                        <span class="info-value">${formatStatus(call.status)}</span>
                    </div>
                    <div class="info-item">
                        <span class="info-label">Created</span>
                        <span class="info-value">${formatDateTime(call.created_at)}</span>
                    </div>
                </div>
            </div>
        </div>
    `;
}

// Analyze Call
async function analyzeCall(callId) {
    showToast('Analyzing call...', 'info');

    try {
        const response = await fetch(`${API_BASE_URL}/api/v1/calls/${callId}/analyze`, {
            method: 'POST'
        });

        const data = await response.json();

        if (data.success) {
            showToast('Analysis complete!', 'success');
            await loadConversationDetail(callId, true);
            await loadDashboardData();
        } else {
            showToast(data.error || 'Analysis failed', 'error');
        }
    } catch (error) {
        showToast('Failed to analyze call', 'error');
    }
}

// Handle Call Submit
async function handleCallSubmit(e) {
    e.preventDefault();

    const phoneNumber = elements.phoneNumber.value.trim();
    const greeting = elements.greeting?.value.trim();
    const systemPrompt = elements.systemPrompt?.value.trim();

    if (!phoneNumber || !phoneNumber.startsWith('+')) {
        showToast('Enter a valid phone number (E.164 format)', 'error');
        return;
    }

    elements.initiateCallBtn.disabled = true;
    elements.initiateCallBtn.innerHTML = '<span class="spinner-small"></span> Connecting...';

    try {
        const response = await fetch(`${API_BASE_URL}/api/v1/calls/initiate`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                phone_number: phoneNumber,
                greeting_message: greeting || undefined,
                system_prompt: systemPrompt || undefined
            })
        });

        const data = await response.json();

        if (response.ok) {
            state.currentCall = data;
            showActiveCall(data);
            showToast('Call initiated!', 'success');
            startCallTimer();
            startPolling();
        } else {
            showToast(data.detail || 'Failed to start call', 'error');
        }
    } catch (error) {
        showToast('Network error. Please try again.', 'error');
    } finally {
        elements.initiateCallBtn.disabled = false;
        elements.initiateCallBtn.innerHTML = '<i class="fas fa-phone"></i> Start Call';
    }
}

// Show Active Call
function showActiveCall(call) {
    elements.activeCallPanel.style.display = 'block';
    elements.activePhoneNumber.textContent = call.phone_number;
    updateCallStatus(call.status);
    elements.liveTranscript.innerHTML = `
        <div class="transcript-placeholder">
            <i class="fas fa-microphone-alt"></i>
            <p>Waiting for conversation...</p>
        </div>
    `;

    updateActiveCallsIndicator(1);
}

// Update Call Status
function updateCallStatus(status) {
    elements.activeCallStatusBadge.className = 'call-status-badge ' + status;
    elements.activeCallStatusBadge.textContent = formatStatus(status);
}

// Start Call Timer
function startCallTimer() {
    state.callStartTime = Date.now();
    state.callTimer = setInterval(() => {
        const elapsed = Math.floor((Date.now() - state.callStartTime) / 1000);
        const minutes = Math.floor(elapsed / 60).toString().padStart(2, '0');
        const seconds = (elapsed % 60).toString().padStart(2, '0');
        elements.activeCallTimer.textContent = `${minutes}:${seconds}`;
    }, 1000);
}

// Stop Call Timer
function stopCallTimer() {
    if (state.callTimer) {
        clearInterval(state.callTimer);
        state.callTimer = null;
    }
}

// Start Polling
function startPolling() {
    if (state.pollInterval) clearInterval(state.pollInterval);

    state.pollInterval = setInterval(async () => {
        if (!state.currentCall) {
            stopPolling();
            return;
        }

        try {
            const response = await fetch(`${API_BASE_URL}/api/v1/calls/${state.currentCall.call_id}`);
            const data = await response.json();

            if (response.ok) {
                updateCallStatus(data.status);
                updateLiveTranscript(data.transcript);

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
    if (state.pollInterval) {
        clearInterval(state.pollInterval);
        state.pollInterval = null;
    }
}

// Update Live Transcript
function updateLiveTranscript(transcript) {
    if (!transcript || transcript.length === 0) return;

    elements.liveTranscript.innerHTML = transcript.map(t => `
        <div class="live-msg ${t.speaker}">
            <div class="live-msg-avatar">
                <i class="fas ${t.speaker === 'agent' ? 'fa-robot' : 'fa-user'}"></i>
            </div>
            <div class="live-msg-text">${escapeHtml(t.text)}</div>
        </div>
    `).join('');

    elements.liveTranscript.scrollTop = elements.liveTranscript.scrollHeight;
}

// Handle End Call
async function handleEndCall() {
    if (!state.currentCall) return;

    elements.endCallBtn.disabled = true;
    elements.endCallBtn.innerHTML = '<span class="spinner-small"></span> Ending...';

    try {
        await fetch(`${API_BASE_URL}/api/v1/calls/${state.currentCall.call_id}/end`, {
            method: 'POST'
        });
        handleCallEnded({ status: 'completed' });
        showToast('Call ended', 'info');
    } catch (error) {
        showToast('Failed to end call', 'error');
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
        elements.activeCallPanel.style.display = 'none';
        state.currentCall = null;
        elements.activeCallTimer.textContent = '00:00';
        updateActiveCallsIndicator(0);

        // Refresh data
        loadDashboardData();
        loadConversations();
    }, 1500);
}

// Update Analytics
function updateAnalytics() {
    if (!state.dashboardData) return;

    const stats = state.dashboardData.statistics;
    if (!stats) return;

    const total = stats.total_calls || 1;

    // Update bars
    const completedPct = Math.round((stats.completed_calls / total) * 100);
    const failedPct = Math.round((stats.failed_calls / total) * 100);
    const activePct = Math.round((stats.active_calls / total) * 100);

    elements.completedBar.style.width = `${completedPct}%`;
    elements.failedBar.style.width = `${failedPct}%`;
    elements.activeBar.style.width = `${activePct}%`;

    // Update values
    elements.analyticsCompleted.textContent = stats.completed_calls || 0;
    elements.analyticsFailed.textContent = stats.failed_calls || 0;
    elements.analyticsActive.textContent = stats.active_calls || 0;

    // Update insights
    elements.insightDuration.textContent = `${Math.round(stats.average_duration_seconds || 0)} sec`;
    elements.insightSuccessRate.textContent = `${(stats.success_rate || 0).toFixed(0)}%`;
    elements.insightTotal.textContent = stats.total_calls || 0;

    // Update activity feed
    updateActivityFeed();
}

// Update Activity Feed
function updateActivityFeed() {
    const conversations = state.dashboardData?.recent_conversations || [];

    if (conversations.length === 0) {
        elements.activityFeed.innerHTML = `
            <div class="empty-state small">
                <i class="fas fa-rss"></i>
                <p>No recent activity</p>
            </div>
        `;
        return;
    }

    elements.activityFeed.innerHTML = conversations.slice(0, 5).map(conv => `
        <div class="activity-item" onclick="viewConversation('${conv.call_id}')">
            <div class="activity-icon ${conv.status}">
                <i class="fas ${conv.status === 'completed' ? 'fa-check' : 'fa-times'}"></i>
            </div>
            <div class="activity-info">
                <span class="activity-text">Call to ${escapeHtml(conv.phone_number)}</span>
                <span class="activity-time">${formatRelativeTime(conv.created_at)}</span>
            </div>
        </div>
    `).join('');
}

// Update Conversation Count
function updateConversationCount(count) {
    elements.conversationCount.textContent = count || 0;
}

// Update Active Calls Indicator
function updateActiveCallsIndicator(count) {
    if (count > 0) {
        elements.activeCallsIndicator.style.display = 'flex';
        elements.activeCallCount.textContent = count;
    } else {
        elements.activeCallsIndicator.style.display = 'none';
    }
}

// Toast Notifications
function showToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;

    const icons = { success: 'fa-check', error: 'fa-exclamation', info: 'fa-info' };

    toast.innerHTML = `
        <div class="toast-icon"><i class="fas ${icons[type]}"></i></div>
        <span>${escapeHtml(message)}</span>
        <button class="toast-close" onclick="this.parentElement.remove()">
            <i class="fas fa-times"></i>
        </button>
    `;

    elements.toastContainer.appendChild(toast);

    setTimeout(() => {
        toast.classList.add('fade-out');
        setTimeout(() => toast.remove(), 250);
    }, 4000);
}

// Utility Functions
function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function formatStatus(status) {
    if (!status) return '';
    return status.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
}

function formatRelativeTime(dateString) {
    if (!dateString) return '';
    const date = new Date(dateString);
    const now = new Date();
    const diff = now - date;

    if (diff < 60000) return 'Just now';
    if (diff < 3600000) return `${Math.floor(diff / 60000)}m ago`;
    if (diff < 86400000) return `${Math.floor(diff / 3600000)}h ago`;
    if (diff < 604800000) return `${Math.floor(diff / 86400000)}d ago`;

    return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}

function formatDateTime(dateString) {
    if (!dateString) return '';
    return new Date(dateString).toLocaleString('en-US', {
        month: 'short', day: 'numeric', year: 'numeric',
        hour: '2-digit', minute: '2-digit'
    });
}

function formatDuration(seconds) {
    if (!seconds) return '0:00';
    const mins = Math.floor(seconds / 60);
    const secs = Math.round(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
}

function truncate(text, length) {
    if (!text) return '';
    return text.length > length ? text.substring(0, length) + '...' : text;
}

// Global exports
window.navigateToSection = navigateToSection;
window.viewConversation = viewConversation;
window.selectConversation = selectConversation;
window.analyzeCall = analyzeCall;
