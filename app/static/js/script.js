document.addEventListener("DOMContentLoaded", () => {
    // DOM Elements
    const uploadForm = document.getElementById("upload-form");
    const fileInput = document.getElementById("file-input");
    const dropZone = document.getElementById("drop-zone");
    const browseBtn = document.getElementById("browse-btn");
    const submitBtn = document.getElementById("submit-btn");
    
    // File Selected State
    const dropZoneContent = document.querySelector(".drop-zone-content");
    const fileSelectedState = document.getElementById("file-selected-state");
    const selectedFileName = document.getElementById("selected-file-name");
    const selectedFileSize = document.getElementById("selected-file-size");
    const removeFileBtn = document.getElementById("remove-file-btn");

    // Alerts
    const errorBanner = document.getElementById("error-banner");
    const errorMessage = document.getElementById("error-message");
    const closeErrorBtn = document.getElementById("close-error");

    // Loading / Results
    const loadingIndicator = document.getElementById("loading-indicator");
    const resultsSection = document.getElementById("results-section");
    const resultsCount = document.getElementById("results-count");
    const downloadJsonBtn = document.getElementById("download-json-btn");
    const exportCsvBtn = document.getElementById("export-csv-btn");
    const tableBody = document.getElementById("table-body");

    let currentFile = null;
    let currentResults = null;

    // Helper to format bytes
    function formatBytes(bytes, decimals = 2) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const dm = decimals < 0 ? 0 : decimals;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + ' ' + sizes[i];
    }

    // Hide error banner helper
    function hideError() {
        errorBanner.classList.add("hidden");
        errorMessage.textContent = "";
    }

    // Show error banner helper
    function showError(message) {
        errorMessage.textContent = message;
        errorBanner.classList.remove("hidden");
        errorBanner.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }

    // Close error button listener
    closeErrorBtn.addEventListener("click", hideError);

    // Click on drop zone triggers file input
    browseBtn.addEventListener("click", (e) => {
        e.stopPropagation();
        fileInput.click();
    });

    dropZone.addEventListener("click", () => {
        if (!currentFile) {
            fileInput.click();
        }
    });

    // File Input change event
    fileInput.addEventListener("change", () => {
        if (fileInput.files.length > 0) {
            handleFileSelection(fileInput.files[0]);
        }
    });

    // Drag & Drop event listeners
    ['dragenter', 'dragover'].forEach(eventName => {
        dropZone.addEventListener(eventName, (e) => {
            e.preventDefault();
            e.stopPropagation();
            dropZone.classList.add("dragover");
        }, false);
    });

    ['dragleave', 'drop'].forEach(eventName => {
        dropZone.addEventListener(eventName, (e) => {
            e.preventDefault();
            e.stopPropagation();
            dropZone.classList.remove("dragover");
        }, false);
    });

    dropZone.addEventListener("drop", (e) => {
        const dt = e.dataTransfer;
        const files = dt.files;
        if (files.length > 0) {
            handleFileSelection(files[0]);
        }
    }, false);

    // Handle File Selection
    function handleFileSelection(file) {
        hideError();
        resultsSection.classList.add("hidden");
        
        // Client side simple checks (type validation will be reinforced by backend)
        const name = file.name;
        const ext = name.split('.').pop().toLowerCase();
        if (ext !== 'pdf' && ext !== 'txt') {
            showError("Only PDF and TXT files are allowed.");
            clearFile();
            return;
        }

        currentFile = file;
        selectedFileName.textContent = file.name;
        selectedFileSize.textContent = formatBytes(file.size);
        
        // Toggle view states
        dropZoneContent.classList.add("hidden");
        fileSelectedState.classList.remove("hidden");
        submitBtn.disabled = false;
    }

    // Clear Selected File
    function clearFile() {
        currentFile = null;
        fileInput.value = "";
        fileSelectedState.classList.add("hidden");
        dropZoneContent.classList.remove("hidden");
        submitBtn.disabled = true;
    }

    removeFileBtn.addEventListener("click", (e) => {
        e.stopPropagation();
        clearFile();
    });

    // Form submission
    uploadForm.addEventListener("submit", async (e) => {
        e.preventDefault();
        if (!currentFile) return;

        hideError();
        resultsSection.classList.add("hidden");
        loadingIndicator.classList.remove("hidden");
        submitBtn.disabled = true;
        removeFileBtn.disabled = true;

        const formData = new FormData();
        formData.append("file", currentFile);

        try {
            const response = await fetch("/extract", {
                method: "POST",
                body: formData
            });

            const data = await response.json();

            if (response.ok && data.success) {
                // Success path
                currentResults = data;
                displayResults(data);
            } else {
                // Backend error response format: {success: false, error: "..."}
                const msg = data.error || "An unexpected error occurred. Please try again.";
                showError(msg);
            }
        } catch (err) {
            showError("Unable to connect to API. Please try again later.");
        } finally {
            loadingIndicator.classList.add("hidden");
            submitBtn.disabled = false;
            removeFileBtn.disabled = false;
        }
    });

    // Display Results in table
    function displayResults(data) {
        tableBody.innerHTML = "";
        const addresses = data.addresses || [];
        
        resultsCount.textContent = `${data.count} address${data.count === 1 ? '' : 'es'} found`;
        
        addresses.forEach((addr, idx) => {
            const tr = document.createElement("tr");
            tr.classList.add("table-row-animated");
            tr.style.animationDelay = `${idx * 0.02}s`;
            
            // Build Street string from parts
            const comp = addr.components || {};
            const streetParts = [];
            if (comp.primary_number) streetParts.push(comp.primary_number);
            if (comp.street_name) streetParts.push(comp.street_name);
            if (comp.street_suffix) streetParts.push(comp.street_suffix);
            const streetString = streetParts.join(" ") || "-";

            tr.innerHTML = `
                <td class="row-num">${idx + 1}</td>
                <td class="address-cell">${addr.input_text || "-"}</td>
                <td>${streetString}</td>
                <td>${comp.city_name || "-"}</td>
                <td>${comp.state_abbreviation || "-"}</td>
                <td>${comp.zipcode || "-"}</td>
            `;
            tableBody.appendChild(tr);
        });

        resultsSection.classList.remove("hidden");
        resultsSection.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }

    // Download raw JSON response
    downloadJsonBtn.addEventListener("click", () => {
        if (!currentResults) return;
        
        const jsonStr = JSON.stringify(currentResults, null, 2);
        const blob = new Blob([jsonStr], { type: "application/json" });
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `extracted_addresses_${Date.now()}.json`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    });

    // Export table data to CSV
    exportCsvBtn.addEventListener("click", () => {
        if (!currentResults || !currentResults.addresses) return;
        
        const headers = ["Index", "Full Address", "Street", "City", "State", "Zip"];
        const rows = [headers];
        
        currentResults.addresses.forEach((addr, idx) => {
            const comp = addr.components || {};
            const streetParts = [];
            if (comp.primary_number) streetParts.push(comp.primary_number);
            if (comp.street_name) streetParts.push(comp.street_name);
            if (comp.street_suffix) streetParts.push(comp.street_suffix);
            const streetString = streetParts.join(" ") || "";
            
            const escapeCSV = (val) => {
                if (val === null || val === undefined) return '""';
                const str = String(val).replace(/"/g, '""');
                return `"${str}"`;
            };
            
            rows.push([
                idx + 1,
                escapeCSV(addr.input_text),
                escapeCSV(streetString),
                escapeCSV(comp.city_name),
                escapeCSV(comp.state_abbreviation),
                escapeCSV(comp.zipcode)
            ]);
        });
        
        const csvContent = rows.map(r => r.join(",")).join("\n");
        const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" });
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `extracted_addresses_${Date.now()}.csv`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    });
});
