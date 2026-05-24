// Global variables
let socket = null;
let currentJobId = null;
let uploadedData = null;
let updateInterval = null;

// Initialize Socket.IO connection
function initializeSocket() {
    socket = io();
    
    socket.on('connect', () => {
        addLog('WebSocket connected successfully', 'success');
    });
    
    socket.on('progress_update', (data) => {
        if (data.job_id === currentJobId) {
            updateDashboard(data);
        }
    });
    
socket.on(
    "job_completed",
    (data) => {

        console.log(data);

        alert(
            "✅ Extraction Completed Successfully"
        );

const exportBtn =
    document.getElementById(
        "exportXlsxBtn"
    );

if (exportBtn) {

    exportBtn.style.display =
        "inline-flex";
}


        if (xlsxBtn) {

            xlsxBtn.style.display =
                "inline-flex";
        }

        if (csvBtn) {

            csvBtn.style.display =
                "inline-flex";
        }
    }
);
}

// File upload handling
document.getElementById('uploadArea').addEventListener('click', (e) => {
    if (e.target === document.getElementById('uploadArea') || 
        e.target.closest('.upload-content')) {
        document.getElementById('fileInput').click();
    }
});

document.getElementById('uploadArea').addEventListener('dragover', (e) => {
    e.preventDefault();
    document.getElementById('uploadArea').style.borderColor = '#00f3ff';
    document.getElementById('uploadArea').style.background = 'rgba(0, 243, 255, 0.05)';
});

document.getElementById('uploadArea').addEventListener('dragleave', (e) => {
    e.preventDefault();
    document.getElementById('uploadArea').style.borderColor = 'rgba(255, 255, 255, 0.1)';
    document.getElementById('uploadArea').style.background = 'rgba(255, 255, 255, 0.03)';
});

document.getElementById('uploadArea').addEventListener('drop', (e) => {
    e.preventDefault();
    const file = e.dataTransfer.files[0];
    if (file) {
        handleFileUpload(file);
    }
    document.getElementById('uploadArea').style.borderColor = 'rgba(255, 255, 255, 0.1)';
    document.getElementById('uploadArea').style.background = 'rgba(255, 255, 255, 0.03)';
});

document.getElementById('fileInput').addEventListener('change', (e) => {
    const file = e.target.files[0];
    if (file) {
        handleFileUpload(file);
    }
});

async function handleFileUpload(file) {
    const formData = new FormData();
    formData.append('file', file);
    
    addLog(`Uploading file: ${file.name}`, 'info');
    
    // Show loading
    Swal.fire({
        title: 'Uploading...',
        text: 'Please wait while we process your file',
        allowOutsideClick: false,
        didOpen: () => {
            Swal.showLoading();
        }
    });
    
    try {
        const response = await fetch('/api/upload', {
            method: 'POST',
            body: formData
        });
        
        const data = await response.json();
        
        if (data.success) {
            uploadedData = data;
            
            // Update file info display
            document.getElementById('fileName').textContent = data.filename;
            document.getElementById('asinCount').textContent = `${data.total_asins} ASINs found`;
            document.getElementById('fileInfo').style.display = 'flex';
            
            // Show options panel
            document.getElementById('optionsPanel').style.display = 'block';
            
            Swal.fire({
                title: 'Success!',
                text: `File uploaded successfully. ${data.total_asins} ASINs detected.`,
                icon: 'success',
                background: '#0a0e27',
                color: '#fff'
            });
            
            addLog(`File uploaded: ${data.total_asins} ASINs ready for extraction`, 'success');
            
            // Scroll to options panel
            document.getElementById('optionsPanel').scrollIntoView({ behavior: 'smooth' });
        } else {
            throw new Error(data.error);
        }
    } catch (error) {
        console.error('Upload error:', error);
        Swal.fire({
            title: 'Error!',
            text: error.message || 'Failed to upload file',
            icon: 'error',
            background: '#0a0e27',
            color: '#fff'
        });
        addLog(`Upload failed: ${error.message}`, 'error');
    }
}

// Toggle all fields
function toggleAllFields() {
    const checkboxes = document.querySelectorAll('.field-check');
    const allChecked = Array.from(checkboxes).every(cb => cb.checked);
    
    checkboxes.forEach(checkbox => {
        checkbox.checked = !allChecked;
    });
    
    addLog(`${!allChecked ? 'Selected' : 'Deselected'} all extraction fields`, 'info');
}

// Start scraping
async function startScraping() {
    if (!uploadedData) {
        Swal.fire('Error', 'Please upload a file first', 'error');
        return;
    }
    
    const selectedFields = Array.from(document.querySelectorAll('.field-check:checked'))
        .map(cb => cb.value);
    
    if (selectedFields.length === 0) {
        Swal.fire('Warning', 'Please select at least one field to extract', 'warning');
        return;
    }
    
    addLog(`Starting extraction with ${selectedFields.length} selected fields`, 'info');
    
    // Show loading
    Swal.fire({
        title: 'Starting Extraction...',
        text: 'Initializing scraping engine',
        allowOutsideClick: false,
        didOpen: () => {
            Swal.showLoading();
        }
    });
    
    try {
        const response = await fetch('/api/start-scraping', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                file_path: uploadedData.filename,
                asins: uploadedData.asins,
                selected_fields: selectedFields
            })
        });
        
        const data = await response.json();
        
        if (data.job_id) {
            currentJobId = data.job_id;
            
            // Show dashboard
            document.getElementById('dashboard').style.display = 'block';
            document.getElementById('totalCount').textContent = uploadedData.total_asins;
            
            // Start progress polling
            startProgressPolling();
            
            Swal.fire({
                title: 'Extraction Started!',
                text: 'Processing your ASINs. Monitor progress in the dashboard.',
                icon: 'success',
                background: '#0a0e27',
                color: '#fff'
            });
            
            addLog(`Extraction job started: ${currentJobId}`, 'success');
            
            // Scroll to dashboard
            document.getElementById('dashboard').scrollIntoView({ behavior: 'smooth' });
        } else {
            throw new Error('No job ID returned');
        }
    } catch (error) {
        console.error('Start scraping error:', error);
        Swal.fire({
            title: 'Error!',
            text: error.message || 'Failed to start extraction',
            icon: 'error',
            background: '#0a0e27',
            color: '#fff'
        });
        addLog(`Failed to start extraction: ${error.message}`, 'error');
    }
}

// Start progress polling
function startProgressPolling() {
    if (updateInterval) {
        clearInterval(updateInterval);
    }
    
    updateInterval = setInterval(async () => {
        if (!currentJobId) return;
        
        try {
            const response = await fetch(`/api/job-status/${currentJobId}`);
            const data = await response.json();
            
            updateDashboard(data);
            
            if (data.status === 'completed') {
                clearInterval(updateInterval);
                updateInterval = null;
            }
        } catch (error) {
            console.error('Error fetching status:', error);
        }
    }, 2000);
}

// Update dashboard with latest data
function updateDashboard(data) {
    // Update stats
    document.getElementById('completedCount').textContent = data.processed || 0;
    document.getElementById('availableCount').textContent = data.available || 0;
    document.getElementById('unavailableCount').textContent = data.unavailable || 0;
    document.getElementById('errorCount').textContent = data.failed || 0;
    document.getElementById('speedCount').textContent = data.speed ? data.speed.toFixed(2) : '0';
    document.getElementById('currentAsin').textContent = data.current_asin || 'Completed';
    
    // Update progress
    const percentage = data.progress_percentage || 0;
    document.getElementById('progressPercent').textContent = `${Math.round(percentage)}%`;
    document.getElementById('progressBar').style.width = `${percentage}%`;
    
    // Update progress ring
    const circumference = 213.628;
    const offset = circumference - (percentage / 100) * circumference;
    const progressRing = document.getElementById('progressRing');
    if (progressRing) {
        progressRing.style.strokeDashoffset = offset;
    }
    
    // Add log entry for significant events
    if (data.current_asin && data.current_asin !== 'Completed') {
        addLog(`Processing ASIN: ${data.current_asin} (${data.processed}/${data.total_asins})`, 'info');
    }
}

// Export data
async function exportData(format, filter) {
    if (!currentJobId) {
        Swal.fire('Error', 'No extraction job found', 'error');
        return;
    }
    
    addLog(`Preparing ${format.toUpperCase()} export with ${filter} filter...`, 'info');
    
    try {
        window.location.href = `/api/export/${currentJobId}?format=${format}&filter=${filter}`;
        addLog(`Export started: ${format.toUpperCase()} format`, 'success');
    } catch (error) {
        console.error('Export error:', error);
        addLog(`Export failed: ${error.message}`, 'error');
    }
}

// Add log entry
function addLog(message, type = 'info') {
    const logsContainer = document.getElementById('liveLogs');
    const logEntry = document.createElement('div');
    logEntry.className = 'log-entry';
    
    const timestamp = new Date().toLocaleTimeString();
    const icon = getLogIcon(type);
    
    logEntry.innerHTML = `[${timestamp}] ${icon} ${message}`;
    
    logsContainer.appendChild(logEntry);
    logsContainer.scrollTop = logsContainer.scrollHeight;
    
    // Limit log entries to 100
    while (logsContainer.children.length > 100) {
        logsContainer.removeChild(logsContainer.firstChild);
    }
}

function getLogIcon(type) {
    switch(type) {
        case 'success': return '✅';
        case 'error': return '❌';
        case 'warning': return '⚠️';
        default: return 'ℹ️';
    }
}

function clearLogs() {
    const logsContainer = document.getElementById('liveLogs');
    logsContainer.innerHTML = '<div class="log-entry">Logs cleared</div>';
    addLog('Log history cleared', 'info');
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    initializeSocket();
    addLog('Amazon ASIN Intelligence System initialized', 'success');
    addLog('Ready to process ASIN data', 'info');
});