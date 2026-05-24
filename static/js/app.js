// ============================================================
// AMAZON ASIN INTELLIGENCE & PRODUCT ANALYTICS PLATFORM
// ENTERPRISE-GRADE FRONTEND (app.js)
// VERSION: 4.0.0 - FULLY OPTIMIZED WITH REAL-TIME DASHBOARD
// ============================================================

// ============================================================
// GLOBAL CONFIGURATION
// ============================================================

const CONFIG = {
    SOCKET_RECONNECT_ATTEMPTS: 5,
    SOCKET_RECONNECT_DELAY: 2000,
    PROGRESS_POLL_INTERVAL: 1000, // 1 second for real-time updates
    LOGS_LIMIT: 500,
    MAX_ASIN_DISPLAY: 10,
    ANIMATION_DURATION: 300,
    RETRY_ATTEMPTS: 3,
    RETRY_DELAY: 1000,
    EXPORT_FORMATS: ['xlsx', 'csv', 'json'],
    THEME: 'dark',
    AUTO_REFRESH: true
};

// ============================================================
// GLOBAL STATE
// ============================================================

let socket = null;
let currentJobId = null;
let uploadedData = null;
let updateInterval = null;
let extractionStarted = false;
let reconnectAttempts = 0;
let logsLimit = CONFIG.LOGS_LIMIT;
let activeSubscriptions = new Set();
let currentFilters = {
    exportFormat: 'xlsx',
    exportFilter: 'all',
    showOnlyAvailable: false,
    searchAsin: ''
};
let dashboardCharts = {};
let notificationQueue = [];
let batchUpdateTimeout = null;
let pendingUpdates = {};

// ============================================================
// SAFE DOM HELPERS (IMPROVED)
// ============================================================

function getEl(id) {
    return document.getElementById(id);
}

function qs(selector) {
    return document.querySelector(selector);
}

function qsa(selector) {
    return document.querySelectorAll(selector);
}

function safeShow(id, display = 'flex') {
    const el = getEl(id);
    if (el) {
        el.style.display = display;
        el.classList.add('fade-in');
    }
}

function safeHide(id) {
    const el = getEl(id);
    if (el) {
        el.style.display = 'none';
        el.classList.remove('fade-in');
    }
}

function safeText(id, value) {
    const el = getEl(id);
    if (el) {
        el.textContent = value !== undefined && value !== null ? value : '0';
    }
}

function safeHTML(id, value) {
    const el = getEl(id);
    if (el) {
        el.innerHTML = value;
    }
}

function toggleVisibility(id, show) {
    if (show) {
        safeShow(id);
    } else {
        safeHide(id);
    }
}

// ============================================================
// ENHANCED LOGGING SYSTEM
// ============================================================

class EnhancedLogger {
    constructor() {
        this.logs = [];
        this.listeners = [];
        this.maxLogs = CONFIG.LOGS_LIMIT;
    }

    add(message, type = 'info', details = null) {
        const logEntry = {
            id: Date.now() + Math.random(),
            timestamp: new Date().toISOString(),
            formattedTime: new Date().toLocaleTimeString(),
            message: message,
            type: type,
            details: details
        };

        this.logs.unshift(logEntry);
        
        if (this.logs.length > this.maxLogs) {
            this.logs.pop();
        }

        this.renderToDOM(logEntry);
        this.notifyListeners(logEntry);
        
        // Also send to console
        const consoleMethod = type === 'error' ? 'error' : type === 'warning' ? 'warn' : 'log';
        console[consoleMethod](`[${logEntry.formattedTime}] ${message}`, details || '');
    }

    renderToDOM(logEntry) {
        const logsContainer = getEl('liveLogs');
        if (!logsContainer) return;

        const entry = document.createElement('div');
        entry.className = `log-entry ${logEntry.type} animate-slide-in`;
        entry.setAttribute('data-log-id', logEntry.id);
        
        const icon = this.getLogIcon(logEntry.type);
        entry.innerHTML = `
            <span class="log-icon">${icon}</span>
            <span class="log-time">[${logEntry.formattedTime}]</span>
            <span class="log-message">${this.escapeHtml(logEntry.message)}</span>
        `;

        logsContainer.appendChild(entry);
        
        // Auto-scroll
        entry.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        
        // Remove old logs if exceeded
        while (logsContainer.children.length > this.maxLogs) {
            logsContainer.removeChild(logsContainer.firstChild);
        }

        // Auto-remove success logs after 10 seconds
        if (logEntry.type === 'success') {
            setTimeout(() => {
                const logElement = logsContainer.querySelector(`[data-log-id="${logEntry.id}"]`);
                if (logElement) {
                    logElement.style.opacity = '0';
                    setTimeout(() => logElement.remove(), 300);
                }
            }, 10000);
        }
    }

    getLogIcon(type) {
        const icons = {
            success: '✅',
            error: '❌',
            warning: '⚠️',
            info: 'ℹ️',
            debug: '🔍'
        };
        return icons[type] || '📝';
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    notifyListeners(logEntry) {
        this.listeners.forEach(listener => listener(logEntry));
    }

    onLog(callback) {
        this.listeners.push(callback);
    }

    clear() {
        this.logs = [];
        const logsContainer = getEl('liveLogs');
        if (logsContainer) {
            logsContainer.innerHTML = '';
        }
        this.add('Logs cleared', 'info');
    }

    getRecent(limit = 50) {
        return this.logs.slice(0, limit);
    }
}

const logger = new EnhancedLogger();

// ============================================================
// ENHANCED SOCKET INITIALIZATION
// ============================================================

function initializeSocket() {
    try {
        socket = io({
            transports: ['websocket', 'polling'],
            reconnection: true,
            reconnectionAttempts: CONFIG.SOCKET_RECONNECT_ATTEMPTS,
            reconnectionDelay: CONFIG.SOCKET_RECONNECT_DELAY,
            timeout: 10000
        });

        socket.on('connect', () => {
            reconnectAttempts = 0;
            logger.add('WebSocket Connected - Real-time updates enabled', 'success');
            updateConnectionStatus(true);
            
            // Resubscribe to previous job if exists
            if (currentJobId) {
                subscribeToJob(currentJobId);
            }
        });

        socket.on('disconnect', () => {
            logger.add('WebSocket Disconnected - Reconnecting...', 'warning');
            updateConnectionStatus(false);
        });

        socket.on('connect_error', (error) => {
            reconnectAttempts++;
            logger.add(`Connection attempt ${reconnectAttempts} failed`, 'warning');
            if (reconnectAttempts >= CONFIG.SOCKET_RECONNECT_ATTEMPTS) {
                logger.add('Failed to connect to server. Please refresh the page.', 'error');
            }
        });

        socket.on('progress_update', (data) => {
            if (data.job_id === currentJobId) {
                handleProgressUpdate(data);
            }
        });

        socket.on('job_completed', (data) => {
            if (data.job_id === currentJobId) {
                handleJobCompletion(data);
            }
        });

        socket.on('job_error', (data) => {
            if (data.job_id === currentJobId) {
                handleJobError(data);
            }
        });

        socket.on('connected', (data) => {
            logger.add(data.message || 'Connected to server', 'success');
        });

        socket.on('subscribed', (data) => {
            logger.add(`Subscribed to job: ${data.job_id}`, 'info');
        });

    } catch (error) {
        console.error(error);
        logger.add('Socket initialization failed', 'error');
    }
}

function updateConnectionStatus(connected) {
    const statusDot = qs('.status-dot');
    const statusText = qs('.connection-status');
    
    if (statusDot) {
        statusDot.className = `status-dot ${connected ? 'connected' : 'disconnected'}`;
    }
    
    if (statusText) {
        statusText.textContent = connected ? 'Live' : 'Reconnecting';
    }
}

function subscribeToJob(jobId) {
    if (socket && socket.connected && jobId) {
        socket.emit('subscribe_job', { job_id: jobId });
        activeSubscriptions.add(jobId);
    }
}

// ============================================================
// ENHANCED FILE UPLOAD HANDLING
// ============================================================

function initializeUploadEvents() {
    const uploadArea = getEl('uploadArea');
    const fileInput = getEl('fileInput');
    const browseBtn = getEl('browseBtn');

    if (!uploadArea || !fileInput) {
        logger.add('Upload elements missing', 'warning');
        return;
    }

    const clickHandlers = [uploadArea];
    if (browseBtn) clickHandlers.push(browseBtn);
    
    clickHandlers.forEach(el => {
        if (el) {
            el.addEventListener('click', (e) => {
                e.stopPropagation();
                fileInput.click();
            });
        }
    });

    uploadArea.addEventListener('dragover', (e) => {
        e.preventDefault();
        uploadArea.classList.add('dragging');
    });

    uploadArea.addEventListener('dragleave', (e) => {
        e.preventDefault();
        uploadArea.classList.remove('dragging');
    });

    uploadArea.addEventListener('drop', (e) => {
        e.preventDefault();
        uploadArea.classList.remove('dragging');
        const file = e.dataTransfer.files[0];
        if (file) {
            handleFileUpload(file);
        }
    });

    fileInput.addEventListener('change', (e) => {
        const file = e.target.files[0];
        if (file) {
            handleFileUpload(file);
        }
    });
}

async function handleFileUpload(file) {
    if (!file) return;

    const maxSize = 200 * 1024 * 1024; // 200MB
    if (file.size > maxSize) {
        logger.add(`File too large: ${(file.size / 1024 / 1024).toFixed(2)}MB (max 200MB)`, 'error');
        showNotification('File too large', 'error');
        return;
    }

    logger.add(`Uploading ${file.name} (${(file.size / 1024 / 1024).toFixed(2)}MB)`, 'info');

    const formData = new FormData();
    formData.append('file', file);

    showLoadingOverlay('Uploading file...');

    try {
        const response = await fetchWithRetry('/api/upload', {
            method: 'POST',
            body: formData
        });

        const data = await response.json();

        if (!data.success) {
            throw new Error(data.error || 'Upload failed');
        }

        uploadedData = data;
        updateFileInfo(data);
        
        logger.add(`Successfully uploaded ${data.total_asins} ASINs from ${file.name}`, 'success');
        showNotification(`Loaded ${data.total_asins} ASINs`, 'success');
        
        // Display ASIN preview
        if (data.asins && data.asins.length > 0) {
            displayAsinPreview(data.asins);
        }

    } catch (error) {
        console.error(error);
        logger.add(`Upload failed: ${error.message}`, 'error');
        showNotification(`Upload failed: ${error.message}`, 'error');
    } finally {
        hideLoadingOverlay();
    }
}

function displayAsinPreview(asins) {
    const previewContainer = getEl('asinPreview');
    if (!previewContainer) return;

    const previewCount = Math.min(asins.length, CONFIG.MAX_ASIN_DISPLAY);
    const previewHtml = `
        <div class="asin-preview animate-fade-in">
            <div class="preview-header">
                <i class="fas fa-list-ul"></i>
                <span>ASIN Preview (First ${previewCount} of ${asins.length})</span>
            </div>
            <div class="preview-list">
                ${asins.slice(0, previewCount).map(asin => `
                    <div class="preview-item">
                        <code>${escapeHtml(asin)}</code>
                        <button class="copy-asin-btn" data-asin="${escapeHtml(asin)}">
                            <i class="fas fa-copy"></i>
                        </button>
                    </div>
                `).join('')}
            </div>
            ${asins.length > previewCount ? `
                <div class="preview-more">
                    +${asins.length - previewCount} more ASINs
                </div>
            ` : ''}
        </div>
    `;
    
    previewContainer.innerHTML = previewHtml;
    safeShow('asinPreviewSection', 'block');
    
    // Add copy functionality
    document.querySelectorAll('.copy-asin-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const asin = btn.getAttribute('data-asin');
            navigator.clipboard.writeText(asin);
            showNotification(`Copied ${asin} to clipboard`, 'success');
        });
    });
}

function updateFileInfo(data) {
    safeText('fileName', data.filename || '-');
    safeText('asinCount', `${data.total_asins?.toLocaleString() || 0} ASINs`);
    safeText('fileSize', data.file_size || 'N/A');
    
    safeShow('fileInfo', 'flex');
    safeShow('optionsPanel', 'block');
    
    // Animate the file info panel
    const fileInfo = getEl('fileInfo');
    if (fileInfo) {
        fileInfo.classList.add('animate-slide-in');
        setTimeout(() => fileInfo.classList.remove('animate-slide-in'), 500);
    }
    
    const optionsPanel = getEl('optionsPanel');
    if (optionsPanel && typeof optionsPanel.scrollIntoView === 'function') {
        optionsPanel.scrollIntoView({ behavior: 'smooth' });
    }
    
    // Enable start button
    const startBtn = getEl('startScrapingBtn');
    if (startBtn) {
        startBtn.disabled = false;
        startBtn.classList.add('pulse-animation');
        setTimeout(() => startBtn.classList.remove('pulse-animation'), 2000);
    }
}

// ============================================================
// FETCH WITH RETRY
// ============================================================

async function fetchWithRetry(url, options, retries = CONFIG.RETRY_ATTEMPTS) {
    for (let i = 0; i < retries; i++) {
        try {
            const response = await fetch(url, options);
            if (response.ok) return response;
            if (response.status === 429 && i < retries - 1) {
                await new Promise(resolve => setTimeout(resolve, CONFIG.RETRY_DELAY * Math.pow(2, i)));
                continue;
            }
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        } catch (error) {
            if (i === retries - 1) throw error;
            await new Promise(resolve => setTimeout(resolve, CONFIG.RETRY_DELAY * Math.pow(2, i)));
        }
    }
}

// ============================================================
// FIELD SELECTION MANAGEMENT
// ============================================================

function toggleAllFields() {
    const fields = qsa('.field-check');
    const allChecked = Array.from(fields).every(cb => cb.checked);
    
    fields.forEach(cb => {
        cb.checked = !allChecked;
        updateFieldCardStyle(cb);
    });
    
    logger.add(allChecked ? 'Deselected all fields' : 'Selected all fields', 'info');
    updateSelectedCount();
}

function updateFieldCardStyle(checkbox) {
    const card = checkbox.closest('.field-card');
    if (card) {
        if (checkbox.checked) {
            card.classList.add('selected');
        } else {
            card.classList.remove('selected');
        }
    }
}

function updateSelectedCount() {
    const selectedCount = getSelectedFields().length;
    const countSpan = getEl('selectedFieldsCount');
    if (countSpan) {
        countSpan.textContent = selectedCount;
        countSpan.classList.add('animate-pulse');
        setTimeout(() => countSpan.classList.remove('animate-pulse'), 300);
    }
}

function getSelectedFields() {
    return Array.from(qsa('.field-check:checked')).map(cb => cb.value);
}

function getAvailableFields() {
    return Array.from(qsa('.field-check')).map(cb => cb.value);
}

// ============================================================
// ENHANCED SCRAPING START
// ============================================================

async function startScraping() {
    if (!uploadedData) {
        showNotification('Please upload a file first', 'warning');
        return;
    }

    if (extractionStarted) {
        showNotification('Extraction already in progress', 'info');
        return;
    }

    const selectedFields = getSelectedFields();
    
    if (selectedFields.length === 0) {
        showNotification('Please select at least one field to extract', 'warning');
        return;
    }

    extractionStarted = true;
    hideExportButtons();
    resetDashboard();
    initializeDashboard();
    
    logger.add(`Starting extraction with ${selectedFields.length} selected fields`, 'info');
    showLoadingOverlay('Initializing extraction engine...');

    try {
        const response = await fetchWithRetry('/api/start-scraping', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                asins: uploadedData.asins,
                selected_fields: selectedFields,
                filename: uploadedData.filename
            })
        });

        const data = await response.json();

        if (!data.job_id) {
            throw new Error(data.error || 'Failed to start extraction');
        }

        currentJobId = data.job_id;
        subscribeToJob(currentJobId);
        startProgressPolling();
        
        logger.add(`Job started: ${currentJobId.substring(0, 8)}...`, 'success');
        showNotification('Extraction started successfully', 'success');
        
        // Update URL with job ID for sharing
        window.history.pushState({ jobId: currentJobId }, '', `?job=${currentJobId}`);

    } catch (error) {
        extractionStarted = false;
        logger.add(`Failed to start extraction: ${error.message}`, 'error');
        showNotification(`Failed to start: ${error.message}`, 'error');
    } finally {
        hideLoadingOverlay();
    }
}

// ============================================================
// ENHANCED DASHBOARD MANAGEMENT
// ============================================================

function initializeDashboard() {
    safeShow('dashboard', 'block');
    safeText('totalCount', uploadedData?.total_asins?.toLocaleString() || '0');
    
    // Initialize charts
    initializeCharts();
    
    const dashboard = getEl('dashboard');
    if (dashboard && typeof dashboard.scrollIntoView === 'function') {
        dashboard.scrollIntoView({ behavior: 'smooth' });
    }
}

function initializeCharts() {
    // Donut chart for availability
    const ctx = getEl('availabilityChart');
    if (ctx && !dashboardCharts.availability) {
        dashboardCharts.availability = new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: ['Available', 'Unavailable', 'Failed'],
                datasets: [{
                    data: [0, 0, 0],
                    backgroundColor: ['#10b981', '#ef4444', '#f59e0b'],
                    borderWidth: 0,
                    hoverOffset: 10
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { position: 'bottom', labels: { color: '#ffffff' } }
                }
            }
        });
    }
}

function updateCharts(available, unavailable, failed) {
    if (dashboardCharts.availability) {
        dashboardCharts.availability.data.datasets[0].data = [available, unavailable, failed];
        dashboardCharts.availability.update();
    }
}

function handleProgressUpdate(data) {
    // Batch updates for performance
    pendingUpdates = { ...pendingUpdates, ...data };
    
    if (batchUpdateTimeout) clearTimeout(batchUpdateTimeout);
    batchUpdateTimeout = setTimeout(() => {
        applyDashboardUpdates(pendingUpdates);
        pendingUpdates = {};
    }, 100);
}

function applyDashboardUpdates(data) {
    const processed = data.processed || 0;
    const total = data.total_asins || uploadedData?.total_asins || 1;
    const percentage = (processed / total) * 100;
    
    // Animate number changes
    animateNumber('completedCount', 0, processed);
    animateNumber('availableCount', 0, data.available || 0);
    animateNumber('unavailableCount', 0, data.unavailable || 0);
    animateNumber('errorCount', 0, data.failed || 0);
    
    safeText('currentAsin', data.current_asin || '-');
    safeText('progressPercent', `${Math.round(percentage)}%`);
    
    updateProgressBar(percentage);
    updateProgressRing(percentage);
    updateCharts(data.available || 0, data.unavailable || 0, data.failed || 0);
    
    // Update speed metrics
    if (data.processed && data.start_time) {
        const elapsed = (Date.now() - new Date(data.start_time).getTime()) / 1000;
        const speed = elapsed > 0 ? (data.processed / elapsed).toFixed(1) : 0;
        safeText('processingSpeed', `${speed} ASINs/sec`);
    }
}

function animateNumber(elementId, start, end) {
    const element = getEl(elementId);
    if (!element) return;
    
    const duration = 500;
    const startTime = performance.now();
    const startValue = start;
    const endValue = end;
    
    function update(currentTime) {
        const elapsed = currentTime - startTime;
        const progress = Math.min(elapsed / duration, 1);
        const value = Math.floor(startValue + (endValue - startValue) * progress);
        element.textContent = value.toLocaleString();
        
        if (progress < 1) {
            requestAnimationFrame(update);
        }
    }
    
    requestAnimationFrame(update);
}

function updateProgressBar(percentage) {
    const progressBar = getEl('progressBar');
    if (progressBar) {
        progressBar.style.width = `${percentage}%`;
        progressBar.setAttribute('aria-valuenow', percentage);
    }
}

function updateProgressRing(percentage) {
    const ring = getEl('progressRing');
    if (!ring) return;
    
    const radius = ring.r.baseVal.value;
    const circumference = 2 * Math.PI * radius;
    const offset = circumference - (percentage / 100) * circumference;
    
    ring.style.strokeDasharray = `${circumference} ${circumference}`;
    ring.style.strokeDashoffset = offset;
}

function handleJobCompletion(data) {
    extractionStarted = false;
    stopProgressPolling();
    showExportButtons();
    
    logger.add(`Extraction completed! Processed ${data.total_processed || 0} ASINs`, 'success');
    
    showNotification('Extraction completed successfully!', 'success');
    
    // Display completion summary
    displayCompletionSummary(data);
    
    // Play completion sound (optional)
    playCompletionSound();
}

function displayCompletionSummary(data) {
    const summaryHtml = `
        <div class="completion-summary animate-fade-in">
            <h4><i class="fas fa-chart-line"></i> Extraction Summary</h4>
            <div class="summary-stats">
                <div class="summary-stat">
                    <span class="stat-label">Total Processed</span>
                    <span class="stat-value">${(data.total_processed || 0).toLocaleString()}</span>
                </div>
                <div class="summary-stat success">
                    <span class="stat-label">Successful</span>
                    <span class="stat-value">${(data.total_successful || 0).toLocaleString()}</span>
                </div>
                <div class="summary-stat error">
                    <span class="stat-label">Failed</span>
                    <span class="stat-value">${(data.total_failed || 0).toLocaleString()}</span>
                </div>
                <div class="summary-stat info">
                    <span class="stat-label">Available</span>
                    <span class="stat-value">${(data.total_available || 0).toLocaleString()}</span>
                </div>
                <div class="summary-stat warning">
                    <span class="stat-label">Unavailable</span>
                    <span class="stat-value">${(data.total_unavailable || 0).toLocaleString()}</span>
                </div>
            </div>
            <button class="btn-primary" onclick="exportData('xlsx', 'all')">
                <i class="fas fa-download"></i> Download Results
            </button>
        </div>
    `;
    
    const summaryContainer = getEl('completionSummary');
    if (summaryContainer) {
        summaryContainer.innerHTML = summaryHtml;
        safeShow('completionSummary', 'block');
    }
}

function handleJobError(data) {
    extractionStarted = false;
    stopProgressPolling();
    
    logger.add(`Extraction error: ${data.error}`, 'error');
    showNotification(`Error: ${data.error}`, 'error');
}

function startProgressPolling() {
    stopProgressPolling();
    updateInterval = setInterval(async () => {
        if (!currentJobId) return;
        
        try {
            const response = await fetch(`/api/job/${currentJobId}`);
            if (!response.ok) return;
            
            const data = await response.json();
            handleProgressUpdate(data);
            
            if (data.status === 'completed') {
                handleJobCompletion(data);
                stopProgressPolling();
            } else if (data.status === 'cancelled') {
                extractionStarted = false;
                stopProgressPolling();
                logger.add('Job cancelled', 'warning');
            }
        } catch (error) {
            console.error('Progress polling error:', error);
        }
    }, CONFIG.PROGRESS_POLL_INTERVAL);
}

function stopProgressPolling() {
    if (updateInterval) {
        clearInterval(updateInterval);
        updateInterval = null;
    }
}

// ============================================================
// ENHANCED EXPORT FUNCTIONALITY
// ============================================================

function showExportButtons() {
    safeShow('exportXlsxBtn', 'inline-flex');
    safeShow('exportCsvBtn', 'inline-flex');
    safeShow('exportJsonBtn', 'inline-flex');
    safeShow('exportFilteredBtn', 'inline-flex');
}

function hideExportButtons() {
    safeHide('exportXlsxBtn');
    safeHide('exportCsvBtn');
    safeHide('exportJsonBtn');
    safeHide('exportFilteredBtn');
}

async function exportData(format = 'xlsx', filter = 'all') {
    if (!currentJobId) {
        showNotification('No completed extraction to export', 'warning');
        return;
    }

    showLoadingOverlay(`Preparing ${format.toUpperCase()} export...`);
    
    try {
        const exportUrl = `/api/export/${currentJobId}?format=${format}&filter=${filter}`;
        
        // Use fetch to download with progress
        const response = await fetch(exportUrl);
        if (!response.ok) throw new Error('Export failed');
        
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `amazon_export_${currentJobId.substring(0, 8)}_${new Date().toISOString().slice(0, 19)}.${format}`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        window.URL.revokeObjectURL(url);
        
        logger.add(`Export completed: ${format.toUpperCase()} format with ${filter} filter`, 'success');
        showNotification(`Export completed (${format.toUpperCase()})`, 'success');
        
    } catch (error) {
        logger.add(`Export failed: ${error.message}`, 'error');
        showNotification('Export failed', 'error');
    } finally {
        hideLoadingOverlay();
    }
}

async function exportFiltered() {
    const filterType = qs('input[name="filterType"]:checked')?.value || 'all';
    await exportData('xlsx', filterType);
}

// ============================================================
// JOB MANAGEMENT
// ============================================================

async function cancelJob() {
    if (!currentJobId || !extractionStarted) {
        showNotification('No active job to cancel', 'warning');
        return;
    }
    
    const confirmed = await showConfirmDialog('Cancel Extraction', 'Are you sure you want to cancel the ongoing extraction?');
    if (!confirmed) return;
    
    showLoadingOverlay('Cancelling job...');
    
    try {
        const response = await fetch(`/api/cancel-job/${currentJobId}`, { method: 'POST' });
        const data = await response.json();
        
        if (data.success) {
            extractionStarted = false;
            stopProgressPolling();
            logger.add('Job cancelled successfully', 'warning');
            showNotification('Job cancelled', 'info');
        } else {
            throw new Error(data.error);
        }
    } catch (error) {
        logger.add(`Failed to cancel job: ${error.message}`, 'error');
    } finally {
        hideLoadingOverlay();
    }
}

async function listJobs() {
    try {
        const response = await fetch('/api/jobs');
        const data = await response.json();
        
        if (data.jobs && data.jobs.length > 0) {
            displayJobHistory(data.jobs);
        }
    } catch (error) {
        logger.add(`Failed to load job history: ${error.message}`, 'error');
    }
}

function displayJobHistory(jobs) {
    const modal = createJobHistoryModal(jobs);
    document.body.appendChild(modal);
    safeShow('jobHistoryModal', 'block');
}

// ============================================================
// UI HELPERS & ANIMATIONS
// ============================================================

function showLoadingOverlay(message = 'Processing...') {
    let overlay = getEl('loadingOverlay');
    if (!overlay) {
        overlay = document.createElement('div');
        overlay.id = 'loadingOverlay';
        overlay.className = 'loading-overlay';
        overlay.innerHTML = `
            <div class="loading-content">
                <div class="spinner"></div>
                <p class="loading-message">${message}</p>
            </div>
        `;
        document.body.appendChild(overlay);
    }
    const messageEl = overlay.querySelector('.loading-message');
    if (messageEl) messageEl.textContent = message;
    overlay.classList.add('show');
}

function hideLoadingOverlay() {
    const overlay = getEl('loadingOverlay');
    if (overlay) {
        overlay.classList.remove('show');
        setTimeout(() => overlay.remove(), 300);
    }
}

function showNotification(message, type = 'info') {
    const notification = document.createElement('div');
    notification.className = `notification notification-${type} animate-slide-in`;
    notification.innerHTML = `
        <div class="notification-content">
            <i class="fas ${getNotificationIcon(type)}"></i>
            <span>${escapeHtml(message)}</span>
        </div>
        <button class="notification-close">&times;</button>
    `;
    
    document.body.appendChild(notification);
    
    const closeBtn = notification.querySelector('.notification-close');
    closeBtn.addEventListener('click', () => notification.remove());
    
    setTimeout(() => {
        if (notification.parentNode) {
            notification.classList.add('fade-out');
            setTimeout(() => notification.remove(), 300);
        }
    }, 5000);
}

function getNotificationIcon(type) {
    const icons = {
        success: 'fa-check-circle',
        error: 'fa-exclamation-circle',
        warning: 'fa-exclamation-triangle',
        info: 'fa-info-circle'
    };
    return icons[type] || 'fa-info-circle';
}

function showConfirmDialog(title, message) {
    return new Promise((resolve) => {
        const modal = document.createElement('div');
        modal.className = 'modal-overlay';
        modal.innerHTML = `
            <div class="modal-content animate-scale-in">
                <div class="modal-header">
                    <h3>${escapeHtml(title)}</h3>
                    <button class="modal-close">&times;</button>
                </div>
                <div class="modal-body">
                    <p>${escapeHtml(message)}</p>
                </div>
                <div class="modal-footer">
                    <button class="btn-secondary modal-cancel">Cancel</button>
                    <button class="btn-primary modal-confirm">Confirm</button>
                </div>
            </div>
        `;
        
        document.body.appendChild(modal);
        
        const closeModal = () => modal.remove();
        modal.querySelector('.modal-close').addEventListener('click', closeModal);
        modal.querySelector('.modal-cancel').addEventListener('click', () => {
            closeModal();
            resolve(false);
        });
        modal.querySelector('.modal-confirm').addEventListener('click', () => {
            closeModal();
            resolve(true);
        });
        
        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                closeModal();
                resolve(false);
            }
        });
    });
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function playCompletionSound() {
    // Optional: Add completion sound
    // const audio = new Audio('/static/sounds/complete.wav');
    // audio.play().catch(e => console.log('Audio play failed:', e));
}

function resetDashboard() {
    safeText('completedCount', '0');
    safeText('availableCount', '0');
    safeText('unavailableCount', '0');
    safeText('errorCount', '0');
    safeText('progressPercent', '0%');
    safeText('currentAsin', '-');
    safeText('processingSpeed', '0 ASINs/sec');
    
    updateProgressBar(0);
    updateProgressRing(0);
    
    if (dashboardCharts.availability) {
        dashboardCharts.availability.data.datasets[0].data = [0, 0, 0];
        dashboardCharts.availability.update();
    }
    
    safeHide('completionSummary');
}

function clearLogs() {
    logger.clear();
}

// ============================================================
// KEYBOARD SHORTCUTS
// ============================================================

function initializeKeyboardShortcuts() {
    document.addEventListener('keydown', (e) => {
        // Ctrl/Cmd + Enter: Start scraping
        if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
            e.preventDefault();
            startScraping();
        }
        // Ctrl/Cmd + E: Export
        if ((e.ctrlKey || e.metaKey) && e.key === 'e') {
            e.preventDefault();
            if (currentJobId) exportData('xlsx', 'all');
        }
        // Ctrl/Cmd + L: Clear logs
        if ((e.ctrlKey || e.metaKey) && e.key === 'l') {
            e.preventDefault();
            clearLogs();
        }
        // Escape: Cancel loading
        if (e.key === 'Escape') {
            if (extractionStarted) cancelJob();
        }
    });
}

// ============================================================
// THEME MANAGEMENT
// ============================================================

function initializeTheme() {
    const savedTheme = localStorage.getItem('theme') || CONFIG.THEME;
    document.body.setAttribute('data-theme', savedTheme);
    
    const themeToggle = getEl('themeToggle');
    if (themeToggle) {
        themeToggle.addEventListener('click', () => {
            const currentTheme = document.body.getAttribute('data-theme');
            const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
            document.body.setAttribute('data-theme', newTheme);
            localStorage.setItem('theme', newTheme);
            logger.add(`Theme switched to ${newTheme}`, 'info');
        });
    }
}

// ============================================================
// ANIMATIONS & TRANSITIONS
// ============================================================

function initializeAnimations() {
    const cards = qsa('.animated-card');
    cards.forEach((card, index) => {
        card.style.animationDelay = `${index * 0.1}s`;
        card.classList.add('fade-in-up');
    });
    
    // Add intersection observer for scroll animations
    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.classList.add('animate-visible');
            }
        });
    }, { threshold: 0.1 });
    
    qsa('.animate-on-scroll').forEach(el => observer.observe(el));
}

// ============================================================
// RESPONSIVE HANDLING
// ============================================================

function initializeResponsive() {
    const sidebar = qs('.sidebar');
    const toggleBtn = getEl('sidebarToggle');
    
    if (toggleBtn && sidebar) {
        toggleBtn.addEventListener('click', () => {
            sidebar.classList.toggle('collapsed');
            localStorage.setItem('sidebarCollapsed', sidebar.classList.contains('collapsed'));
        });
    }
    
    // Load saved state
    const savedState = localStorage.getItem('sidebarCollapsed');
    if (savedState === 'true' && sidebar) {
        sidebar.classList.add('collapsed');
    }
}

// ============================================================
// ERROR BOUNDARY
// ============================================================

window.addEventListener('error', (event) => {
    logger.add(`Global error: ${event.message}`, 'error');
});

window.addEventListener('unhandledrejection', (event) => {
    logger.add(`Unhandled rejection: ${event.reason}`, 'error');
});

// ============================================================
// PAGE INITIALIZATION
// ============================================================

document.addEventListener('DOMContentLoaded', () => {
    logger.add('Amazon ASIN Intelligence Platform v4.0.0', 'success');
    logger.add('Initializing application...', 'info');
    
    initializeSocket();
    initializeUploadEvents();
    initializeAnimations();
    initializeKeyboardShortcuts();
    initializeTheme();
    initializeResponsive();
    
    resetDashboard();
    
    // Check for job ID in URL
    const urlParams = new URLSearchParams(window.location.search);
    const jobIdFromUrl = urlParams.get('job');
    if (jobIdFromUrl) {
        currentJobId = jobIdFromUrl;
        subscribeToJob(currentJobId);
        startProgressPolling();
        logger.add(`Resuming monitoring for job: ${jobIdFromUrl.substring(0, 8)}...`, 'info');
    }
    
    logger.add('Application ready - Waiting for file upload', 'success');
    
    // Load available fields
    fetch('/api/available-fields')
        .then(res => res.json())
        .then(data => {
            if (data.fields) {
                logger.add(`Loaded ${data.fields.length} available extraction fields`, 'info');
            }
        })
        .catch(err => console.error('Failed to load fields:', err));
});

// ============================================================
// EXPORT GLOBALLY ACCESSIBLE FUNCTIONS
// ============================================================

window.startScraping = startScraping;
window.toggleAllFields = toggleAllFields;
window.exportData = exportData;
window.exportFiltered = exportFiltered;
window.cancelJob = cancelJob;
window.clearLogs = clearLogs;
window.listJobs = listJobs;
window.resetDashboard = resetDashboard;
window.getSelectedFields = getSelectedFields;