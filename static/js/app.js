// ======================================================
// AMAZON ASIN ANALYTICS - COMPLETE app.js
// ======================================================

// ---------------- GLOBAL VARIABLES ----------------

let socket = null;
let currentJobId = null;
let uploadedData = null;
let updateInterval = null;
let extractionStarted = false;

// ---------------- SAFE ELEMENT GETTER ----------------

function getEl(id) {
    return document.getElementById(id);
}

// ---------------- SOCKET INITIALIZATION ----------------

function initializeSocket() {

    socket = io();

    socket.on('connect', () => {

        console.log('Socket Connected');

        addLog(
            'WebSocket connected successfully',
            'success'
        );
    });

    socket.on('disconnect', () => {

        addLog(
            'WebSocket disconnected',
            'warning'
        );
    });

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

            console.log(data);

            extractionStarted = false;

            addLog(
                'Extraction completed successfully',
                'success'
            );

            Swal.fire({
                title: 'Completed',
                text: 'Extraction completed successfully',
                icon: 'success',
                background: '#0a0e27',
                color: '#ffffff'
            });

            showExportButtons();

            stopProgressPolling();
        }
    );

    socket.on(
        'job_error',
        (data) => {

            console.error(data);

            extractionStarted = false;

            addLog(
                `Extraction Error: ${data.error}`,
                'error'
            );

            Swal.fire({
                title: 'Error',
                text: data.error || 'Unknown error',
                icon: 'error',
                background: '#0a0e27',
                color: '#ffffff'
            });

            stopProgressPolling();
        }
    );
}

// ---------------- SHOW EXPORT BUTTONS ----------------

function showExportButtons() {

    const xlsxBtn =
        getEl('exportXlsxBtn');

    const csvBtn =
        getEl('exportCsvBtn');

    if (xlsxBtn) {

        xlsxBtn.style.display =
            'inline-flex';
    }

    if (csvBtn) {

        csvBtn.style.display =
            'inline-flex';
    }
}

// ---------------- HIDE EXPORT BUTTONS ----------------

function hideExportButtons() {

    const xlsxBtn =
        getEl('exportXlsxBtn');

    const csvBtn =
        getEl('exportCsvBtn');

    if (xlsxBtn) {

        xlsxBtn.style.display =
            'none';
    }

    if (csvBtn) {

        csvBtn.style.display =
            'none';
    }
}

// ---------------- FILE UPLOAD EVENTS ----------------

function initializeUploadEvents() {

    const uploadArea =
        getEl('uploadArea');

    const fileInput =
        getEl('fileInput');

    if (!uploadArea || !fileInput) {
        return;
    }

    uploadArea.addEventListener(
        'click',
        (e) => {

            if (
                e.target === uploadArea ||
                e.target.closest('.upload-content')
            ) {

                fileInput.click();
            }
        }
    );

    uploadArea.addEventListener(
        'dragover',
        (e) => {

            e.preventDefault();

            uploadArea.style.borderColor =
                '#00f3ff';

            uploadArea.style.background =
                'rgba(0,243,255,0.08)';
        }
    );

    uploadArea.addEventListener(
        'dragleave',
        (e) => {

            e.preventDefault();

            resetUploadArea();
        }
    );

    uploadArea.addEventListener(
        'drop',
        (e) => {

            e.preventDefault();

            resetUploadArea();

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

// ---------------- RESET UPLOAD UI ----------------

function resetUploadArea() {

    const uploadArea =
        getEl('uploadArea');

    if (!uploadArea) return;

    uploadArea.style.borderColor =
        'rgba(255,255,255,0.1)';

    uploadArea.style.background =
        'rgba(255,255,255,0.03)';
}

// ---------------- HANDLE FILE UPLOAD ----------------

async function handleFileUpload(file) {

    if (!file) return;

    const formData = new FormData();

    formData.append(
        'file',
        file
    );

    addLog(
        `Uploading file: ${file.name}`,
        'info'
    );

    Swal.fire({
        title: 'Uploading...',
        text: 'Processing uploaded file',
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
                `${data.total_asins} ASINs detected`,
            icon: 'success',
            background: '#0a0e27',
            color: '#ffffff'
        });

        addLog(
            `Upload successful: ${data.total_asins} ASINs`,
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
            `Upload failed: ${error.message}`,
            'error'
        );
    }
}

// ---------------- UPDATE FILE INFO ----------------

function updateFileInfo(data) {

    const fileInfo =
        getEl('fileInfo');

    const fileName =
        getEl('fileName');

    const asinCount =
        getEl('asinCount');

    const optionsPanel =
        getEl('optionsPanel');

    if (fileName) {

        fileName.textContent =
            data.filename;
    }

    if (asinCount) {

        asinCount.textContent =
            `${data.total_asins} ASINs`;
    }

    if (fileInfo) {

        fileInfo.style.display =
            'flex';
    }

    if (optionsPanel) {

        optionsPanel.style.display =
            'block';
    }
}

// ---------------- TOGGLE ALL FIELDS ----------------

function toggleAllFields() {

    const checkboxes =
        document.querySelectorAll(
            '.field-check'
        );

    const allChecked =
        Array.from(checkboxes)
        .every(cb => cb.checked);

    checkboxes.forEach(cb => {

        cb.checked = !allChecked;
    });

    addLog(
        !allChecked
            ? 'All fields selected'
            : 'All fields deselected',
        'info'
    );
}

// ---------------- START SCRAPING ----------------

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
            text: 'Extraction already in progress',
            icon: 'info',
            background: '#0a0e27',
            color: '#ffffff'
        });

        return;
    }

    const selectedFields =
        Array.from(
            document.querySelectorAll(
                '.field-check:checked'
            )
        ).map(
            cb => cb.value
        );

    if (
        selectedFields.length === 0
    ) {

        Swal.fire({
            title: 'No Fields Selected',
            text: 'Please select fields',
            icon: 'warning',
            background: '#0a0e27',
            color: '#ffffff'
        });

        return;
    }

    extractionStarted = true;

    hideExportButtons();

    addLog(
        `Starting extraction with ${selectedFields.length} fields`,
        'info'
    );

    Swal.fire({
        title: 'Starting...',
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

        if (!data.success) {

            throw new Error(
                data.error ||
                'Failed to start'
            );
        }

        currentJobId =
            data.job_id;

        initializeDashboard();

        startProgressPolling();

        Swal.fire({
            title: 'Extraction Started',
            text: 'Monitor progress below',
            icon: 'success',
            background: '#0a0e27',
            color: '#ffffff'
        });

        addLog(
            `Job started: ${currentJobId}`,
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
            `Start failed: ${error.message}`,
            'error'
        );
    }
}

// ---------------- INITIALIZE DASHBOARD ----------------

function initializeDashboard() {

    const dashboard =
        getEl('dashboard');

    const totalCount =
        getEl('totalCount');

    if (dashboard) {

        dashboard.style.display =
            'block';
    }

    if (totalCount) {

        totalCount.textContent =
            uploadedData.total_asins || 0;
    }

    dashboard.scrollIntoView({
        behavior: 'smooth'
    });
}

// ---------------- PROGRESS POLLING ----------------

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

// ---------------- STOP POLLING ----------------

function stopProgressPolling() {

    if (updateInterval) {

        clearInterval(
            updateInterval
        );

        updateInterval = null;
    }
}

// ---------------- UPDATE DASHBOARD ----------------

function updateDashboard(data) {

    updateText(
        'completedCount',
        data.processed || 0
    );

    updateText(
        'availableCount',
        data.available || 0
    );

    updateText(
        'unavailableCount',
        data.unavailable || 0
    );

    updateText(
        'errorCount',
        data.failed || 0
    );

    updateText(
        'currentAsin',
        data.current_asin || '-'
    );

    const percentage =
        data.progress_percentage || 0;

    updateText(
        'progressPercent',
        `${Math.round(percentage)}%`
    );

    const progressBar =
        getEl('progressBar');

    if (progressBar) {

        progressBar.style.width =
            `${percentage}%`;
    }

    updateProgressRing(
        percentage
    );

    if (
        data.current_asin
    ) {

        addLog(
            `Processing: ${data.current_asin}`,
            'info'
        );
    }
}

// ---------------- UPDATE TEXT ----------------

function updateText(id, value) {

    const el = getEl(id);

    if (el) {

        el.textContent = value;
    }
}

// ---------------- UPDATE RING ----------------

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

// ---------------- EXPORT ----------------

function exportData(
    format = 'xlsx',
    filter = 'all'
) {

    if (!currentJobId) {

        Swal.fire({
            title: 'No Job',
            text: 'No completed extraction',
            icon: 'warning',
            background: '#0a0e27',
            color: '#ffffff'
        });

        return;
    }

    addLog(
        `Exporting ${format.toUpperCase()}`,
        'success'
    );

    window.location.href =
        `/api/export/${currentJobId}?format=${format}&filter=${filter}`;
}

// ---------------- LOGGING ----------------

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

    const time =
        new Date()
        .toLocaleTimeString();

    entry.innerHTML =
        `[${time}] ${getLogIcon(type)} ${message}`;

    logs.appendChild(entry);

    logs.scrollTop =
        logs.scrollHeight;

    while (
        logs.children.length > 100
    ) {

        logs.removeChild(
            logs.firstChild
        );
    }
}

// ---------------- LOG ICON ----------------

function getLogIcon(type) {

    switch(type) {

        case 'success':
            return '✅';

        case 'error':
            return '❌';

        case 'warning':
            return '⚠️';

        default:
            return 'ℹ️';
    }
}

// ---------------- CLEAR LOGS ----------------

function clearLogs() {

    const logs =
        getEl('liveLogs');

    if (!logs) return;

    logs.innerHTML = '';

    addLog(
        'Logs cleared',
        'info'
    );
}

// ---------------- PAGE LOAD ----------------

document.addEventListener(
    'DOMContentLoaded',
    () => {

        initializeSocket();

        initializeUploadEvents();

        addLog(
            'Amazon ASIN Analytics Ready',
            'success'
        );

        addLog(
            'Waiting for file upload',
            'info'
        );
    }
);