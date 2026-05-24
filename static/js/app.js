// ============================================================
// AMAZON ASIN ANALYTICS - ENTERPRISE FRONTEND
// COMPLETE FINAL app.js
// Paste & Run Version
// ============================================================

// ============================================================
// GLOBAL VARIABLES
// ============================================================

let socket = null;
let currentJobId = null;
let uploadedData = null;
let updateInterval = null;
let extractionStarted = false;
let reconnectAttempts = 0;
let logsLimit = 200;

// ============================================================
// SAFE DOM HELPERS
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

function safeShow(id, display = 'block') {

    const el = getEl(id);

    if (el) {
        el.style.display = display;
    }
}

function safeHide(id) {

    const el = getEl(id);

    if (el) {
        el.style.display = 'none';
    }
}

function safeText(id, value) {

    const el = getEl(id);

    if (el) {
        el.textContent = value;
    }
}

function safeHTML(id, value) {

    const el = getEl(id);

    if (el) {
        el.innerHTML = value;
    }
}

// ============================================================
// SOCKET INITIALIZATION
// ============================================================

function initializeSocket() {

    try {

        socket = io();

        socket.on(
            'connect',
            () => {

                reconnectAttempts = 0;

                addLog(
                    'WebSocket Connected',
                    'success'
                );
            }
        );

        socket.on(
            'disconnect',
            () => {

                addLog(
                    'WebSocket Disconnected',
                    'warning'
                );
            }
        );

        socket.on(
            'connect_error',
            () => {

                reconnectAttempts++;

                addLog(
                    `Socket reconnect attempt ${reconnectAttempts}`,
                    'warning'
                );
            }
        );

        socket.on(
            'progress_update',
            (data) => {

                if (
                    data.job_id === currentJobId
                ) {

                    updateDashboard(data);
                }
            }
        );

        socket.on(
            'job_completed',
            (data) => {

                extractionStarted = false;

                stopProgressPolling();

                updateDashboard(data);

                showExportButtons();

                addLog(
                    'Extraction Completed',
                    'success'
                );

                Swal.fire({
                    title: 'Completed',
                    text: 'Extraction completed successfully',
                    icon: 'success',
                    background: '#0a0e27',
                    color: '#ffffff'
                });
            }
        );

        socket.on(
            'job_error',
            (data) => {

                extractionStarted = false;

                stopProgressPolling();

                addLog(
                    `Error: ${data.error}`,
                    'error'
                );

                Swal.fire({
                    title: 'Error',
                    text: data.error || 'Unknown Error',
                    icon: 'error',
                    background: '#0a0e27',
                    color: '#ffffff'
                });
            }
        );

    } catch (error) {

        console.error(error);

        addLog(
            'Socket initialization failed',
            'error'
        );
    }
}

// ============================================================
// FILE UPLOAD EVENTS
// ============================================================

function initializeUploadEvents() {

    const uploadArea =
        getEl('uploadArea');

    const fileInput =
        getEl('fileInput');

    if (!uploadArea || !fileInput) {

        addLog(
            'Upload elements missing',
            'warning'
        );

        return;
    }

    uploadArea.addEventListener(
        'click',
        () => {

            fileInput.click();
        }
    );

    uploadArea.addEventListener(
        'dragover',
        (e) => {

            e.preventDefault();

            uploadArea.classList.add(
                'dragging'
            );
        }
    );

    uploadArea.addEventListener(
        'dragleave',
        (e) => {

            e.preventDefault();

            uploadArea.classList.remove(
                'dragging'
            );
        }
    );

    uploadArea.addEventListener(
        'drop',
        (e) => {

            e.preventDefault();

            uploadArea.classList.remove(
                'dragging'
            );

            const file =
                e.dataTransfer.files[0];

            if (file) {

                handleFileUpload(file);
            }
        }
    );

    fileInput.addEventListener(
        'change',
        (e) => {

            const file =
                e.target.files[0];

            if (file) {

                handleFileUpload(file);
            }
        }
    );
}

// ============================================================
// HANDLE FILE UPLOAD
// ============================================================

async function handleFileUpload(file) {

    if (!file) return;

    addLog(
        `Uploading ${file.name}`,
        'info'
    );

    const formData =
        new FormData();

    formData.append(
        'file',
        file
    );

    Swal.fire({
        title: 'Uploading',
        text: 'Please wait...',
        allowOutsideClick: false,
        background: '#0a0e27',
        color: '#ffffff',
        didOpen: () => {

            Swal.showLoading();
        }
    });

    try {

        const response =
            await fetch(
                '/api/upload',
                {
                    method: 'POST',
                    body: formData
                }
            );

        const data =
            await response.json();

        if (!data.success) {

            throw new Error(
                data.error ||
                'Upload failed'
            );
        }

        uploadedData = data;

        updateFileInfo(data);

        Swal.fire({
            title: 'Success',
            text:
                `${data.total_asins} ASINs Found`,
            icon: 'success',
            background: '#0a0e27',
            color: '#ffffff'
        });

        addLog(
            `${data.total_asins} ASINs detected`,
            'success'
        );

    } catch (error) {

        console.error(error);

        Swal.fire({
            title: 'Upload Failed',
            text: error.message,
            icon: 'error',
            background: '#0a0e27',
            color: '#ffffff'
        });

        addLog(
            error.message,
            'error'
        );
    }
}

// ============================================================
// UPDATE FILE INFO
// ============================================================

function updateFileInfo(data) {

    safeText(
        'fileName',
        data.filename || '-'
    );

    safeText(
        'asinCount',
        `${data.total_asins || 0} ASINs`
    );

    safeShow(
        'fileInfo',
        'flex'
    );

    safeShow(
        'optionsPanel',
        'block'
    );

    const optionsPanel =
        getEl('optionsPanel');

    if (
        optionsPanel &&
        typeof optionsPanel.scrollIntoView ===
        'function'
    ) {

        optionsPanel.scrollIntoView({
            behavior: 'smooth'
        });
    }
}

// ============================================================
// TOGGLE ALL FIELDS
// ============================================================

function toggleAllFields() {

    const fields =
        qsa('.field-check');

    const allChecked =
        Array.from(fields)
        .every(cb => cb.checked);

    fields.forEach(cb => {

        cb.checked = !allChecked;
    });

    addLog(
        allChecked
            ? 'Deselected all fields'
            : 'Selected all fields',
        'info'
    );
}

// ============================================================
// GET SELECTED FIELDS
// ============================================================

function getSelectedFields() {

    return Array.from(
        qsa('.field-check:checked')
    ).map(
        cb => cb.value
    );
}

// ============================================================
// START SCRAPING
// ============================================================

async function startScraping() {

    if (!uploadedData) {

        Swal.fire({
            title: 'Upload Required',
            text: 'Please upload a file first',
            icon: 'warning',
            background: '#0a0e27',
            color: '#ffffff'
        });

        return;
    }

    if (extractionStarted) {

        Swal.fire({
            title: 'Already Running',
            text: 'Extraction already running',
            icon: 'info',
            background: '#0a0e27',
            color: '#ffffff'
        });

        return;
    }

    const selectedFields =
        getSelectedFields();

    if (
        selectedFields.length === 0
    ) {

        Swal.fire({
            title: 'Select Fields',
            text: 'Please select at least one field',
            icon: 'warning',
            background: '#0a0e27',
            color: '#ffffff'
        });

        return;
    }

    extractionStarted = true;

    hideExportButtons();

    initializeDashboard();

    addLog(
        'Starting extraction...',
        'info'
    );

    Swal.fire({
        title: 'Starting',
        text: 'Initializing extraction engine',
        allowOutsideClick: false,
        background: '#0a0e27',
        color: '#ffffff',
        didOpen: () => {

            Swal.showLoading();
        }
    });

    try {

        const response =
            await fetch(
                '/api/start-scraping',
                {
                    method: 'POST',
                    headers: {
                        'Content-Type':
                            'application/json'
                    },
                    body: JSON.stringify({
                        asins:
                            uploadedData.asins,
                        selected_fields:
                            selectedFields
                    })
                }
            );

        const data =
            await response.json();

        if (!data.job_id) {

            throw new Error(
                data.error ||
                'Failed to start extraction'
            );
        }

        currentJobId =
            data.job_id;

        startProgressPolling();

        Swal.fire({
            title: 'Started',
            text: 'Extraction started successfully',
            icon: 'success',
            background: '#0a0e27',
            color: '#ffffff'
        });

        addLog(
            `Job Started (${currentJobId})`,
            'success'
        );

    } catch (error) {

        extractionStarted = false;

        console.error(error);

        Swal.fire({
            title: 'Failed',
            text: error.message,
            icon: 'error',
            background: '#0a0e27',
            color: '#ffffff'
        });

        addLog(
            error.message,
            'error'
        );
    }
}

// ============================================================
// DASHBOARD INIT
// ============================================================

function initializeDashboard() {

    safeShow(
        'dashboard',
        'block'
    );

    safeText(
        'totalCount',
        uploadedData?.total_asins || 0
    );

    const dashboard =
        getEl('dashboard');

    if (
        dashboard &&
        typeof dashboard.scrollIntoView ===
        'function'
    ) {

        dashboard.scrollIntoView({
            behavior: 'smooth'
        });
    }
}

// ============================================================
// PROGRESS POLLING
// ============================================================

function startProgressPolling() {

    stopProgressPolling();

    updateInterval =
        setInterval(
            async () => {

                if (!currentJobId) {
                    return;
                }

                try {

                    const response =
                        await fetch(
                            `/api/job-status/${currentJobId}`
                        );

                    const data =
                        await response.json();

                    updateDashboard(data);

                    if (
                        data.status ===
                        'completed'
                    ) {

                        extractionStarted = false;

                        stopProgressPolling();

                        showExportButtons();
                    }

                } catch (error) {

                    console.error(error);
                }

            },
            2000
        );
}

function stopProgressPolling() {

    if (updateInterval) {

        clearInterval(
            updateInterval
        );

        updateInterval = null;
    }
}

// ============================================================
// UPDATE DASHBOARD
// ============================================================

function updateDashboard(data) {

    safeText(
        'completedCount',
        data.processed || 0
    );

    safeText(
        'availableCount',
        data.available || 0
    );

    safeText(
        'unavailableCount',
        data.unavailable || 0
    );

    safeText(
        'errorCount',
        data.failed || 0
    );

    safeText(
        'currentAsin',
        data.current_asin || '-'
    );

    const percentage =
        data.progress_percentage || 0;

    safeText(
        'progressPercent',
        `${Math.round(percentage)}%`
    );

    updateProgressBar(
        percentage
    );

    updateProgressRing(
        percentage
    );
}

// ============================================================
// UPDATE PROGRESS BAR
// ============================================================

function updateProgressBar(
    percentage
) {

    const progressBar =
        getEl('progressBar');

    if (progressBar) {

        progressBar.style.width =
            `${percentage}%`;
    }
}

// ============================================================
// UPDATE PROGRESS RING
// ============================================================

function updateProgressRing(
    percentage
) {

    const ring =
        getEl('progressRing');

    if (!ring) return;

    const circumference =
        213.628;

    const offset =
        circumference -
        (
            percentage / 100
        ) * circumference;

    ring.style.strokeDashoffset =
        offset;
}

// ============================================================
// EXPORT BUTTONS
// ============================================================

function showExportButtons() {

    safeShow(
        'exportXlsxBtn',
        'inline-flex'
    );

    safeShow(
        'exportCsvBtn',
        'inline-flex'
    );
}

function hideExportButtons() {

    safeHide(
        'exportXlsxBtn'
    );

    safeHide(
        'exportCsvBtn'
    );
}

// ============================================================
// EXPORT DATA
// ============================================================

function exportData(
    format = 'xlsx',
    filter = 'all'
) {

    if (!currentJobId) {

        Swal.fire({
            title: 'No Data',
            text: 'No completed extraction',
            icon: 'warning',
            background: '#0a0e27',
            color: '#ffffff'
        });

        return;
    }

    try {

        const exportUrl =
            `/api/export/${currentJobId}?format=${format}&filter=${filter}`;

        window.open(
            exportUrl,
            '_blank'
        );

        addLog(
            `Exporting ${format.toUpperCase()}`,
            'success'
        );

    } catch (error) {

        console.error(error);

        addLog(
            'Export Failed',
            'error'
        );
    }
}

// ============================================================
// LOGGING
// ============================================================

function addLog(
    message,
    type = 'info'
) {

    const logs =
        getEl('liveLogs');

    if (!logs) return;

    const entry =
        document.createElement('div');

    entry.className =
        `log-entry ${type}`;

    const timestamp =
        new Date()
        .toLocaleTimeString();

    entry.innerHTML =
        `[${timestamp}] ${message}`;

    logs.appendChild(entry);

    logs.scrollTop =
        logs.scrollHeight;

    while (
        logs.children.length > logsLimit
    ) {

        logs.removeChild(
            logs.firstChild
        );
    }
}

// ============================================================
// CLEAR LOGS
// ============================================================

function clearLogs() {

    const logs =
        getEl('liveLogs');

    if (!logs) return;

    logs.innerHTML = '';

    addLog(
        'Logs Cleared',
        'info'
    );
}

// ============================================================
// RESET DASHBOARD
// ============================================================

function resetDashboard() {

    safeText(
        'completedCount',
        '0'
    );

    safeText(
        'availableCount',
        '0'
    );

    safeText(
        'unavailableCount',
        '0'
    );

    safeText(
        'errorCount',
        '0'
    );

    safeText(
        'progressPercent',
        '0%'
    );

    safeText(
        'currentAsin',
        '-'
    );

    updateProgressBar(0);

    updateProgressRing(0);
}

// ============================================================
// THEME ANIMATIONS
// ============================================================

function initializeAnimations() {

    const cards =
        qsa('.animated-card');

    cards.forEach((card, index) => {

        card.style.animationDelay =
            `${index * 0.1}s`;
    });
}

// ============================================================
// BUTTON LOADING
// ============================================================

function setButtonLoading(
    id,
    loading = true
) {

    const btn = getEl(id);

    if (!btn) return;

    if (loading) {

        btn.disabled = true;

        btn.dataset.originalText =
            btn.innerHTML;

        btn.innerHTML =
            '<i class="fas fa-spinner fa-spin"></i> Loading';

    } else {

        btn.disabled = false;

        if (
            btn.dataset.originalText
        ) {

            btn.innerHTML =
                btn.dataset.originalText;
        }
    }
}

// ============================================================
// PAGE INIT
// ============================================================

document.addEventListener(
    'DOMContentLoaded',
    function () {

        initializeSocket();

        initializeUploadEvents();

        initializeAnimations();

        resetDashboard();

        addLog(
            'Amazon ASIN Analytics Ready',
            'success'
        );

        addLog(
            'Waiting for upload...',
            'info'
        );
    }
);