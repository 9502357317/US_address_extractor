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

    // Address Registry
    const registryCount = document.getElementById("registry-count");
    const registryTableBody = document.getElementById("registry-table-body");
    const prevAddressesBtn = document.getElementById("prev-addresses-btn");
    const nextAddressesBtn = document.getElementById("next-addresses-btn");
    const downloadRegistryCsvBtn = document.getElementById("download-registry-csv-btn");
    const addressDetail = document.getElementById("address-detail");
    const addressSearchInput = document.getElementById("address-search-input");
    const cityFilterSelect = document.getElementById("city-filter-select");
    const stateFilterSelect = document.getElementById("state-filter-select");
    const zipFilterSelect = document.getElementById("zip-filter-select");
    const applyAddressFiltersBtn = document.getElementById("apply-address-filters-btn");
    const clearAddressFiltersBtn = document.getElementById("clear-address-filters-btn");

    // Review Queue & Modal Elements
    const reviewSection = document.getElementById("review-section");
    const reviewCount = document.getElementById("review-count");
    const reviewList = document.getElementById("review-list");
    const editAddressModal = document.getElementById("edit-address-modal");
    const editAddressForm = document.getElementById("edit-address-form");
    const editAddressIdInput = document.getElementById("edit-address-id");
    const editStreetInput = document.getElementById("edit-street");
    const editCityInput = document.getElementById("edit-city");
    const editStateInput = document.getElementById("edit-state");
    const editZipInput = document.getElementById("edit-zip");
    const closeEditModalBtn = document.getElementById("close-edit-modal-btn");
    const cancelEditBtn = document.getElementById("cancel-edit-btn");

    let currentFile = null;
    let currentResults = null;
    let addressLimit = 20;
    let addressOffset = 0;
    let addressTotal = 0;
    let addressSearch = "";
    let addressCity = "";
    let addressState = "";
    let addressZip = "";

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
                await loadFilterOptions();
                await loadAddresses();
                await loadDuplicates();
            } else {
                // Backend error response format: {success: false, error: "..."}
                let msg = data.error || "An unexpected error occurred. Please try again.";
                if (response.status === 409 && data.existing_document_id) {
                    const uploadedAt = data.uploaded_at
                        ? new Date(data.uploaded_at).toLocaleString()
                        : "an earlier upload";
                    msg = `${msg} Existing document #${data.existing_document_id} was uploaded at ${uploadedAt}.`;
                }
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

    async function loadFilterOptions() {
        try {
            const response = await fetch("/addresses/filter-options");
            if (!response.ok) return;
            const data = await response.json();

            // Populate City select
            const currentCity = cityFilterSelect.value;
            cityFilterSelect.innerHTML = '<option value="">All cities</option>';
            (data.cities || []).forEach(city => {
                const option = document.createElement("option");
                option.value = city;
                option.textContent = city;
                cityFilterSelect.appendChild(option);
            });
            cityFilterSelect.value = currentCity;

            // Populate State select
            const currentState = stateFilterSelect.value;
            stateFilterSelect.innerHTML = '<option value="">All states</option>';
            (data.states || []).forEach(state => {
                const option = document.createElement("option");
                option.value = state;
                option.textContent = state;
                stateFilterSelect.appendChild(option);
            });
            stateFilterSelect.value = currentState;

            // Populate Zip select
            const currentZip = zipFilterSelect.value;
            zipFilterSelect.innerHTML = '<option value="">All ZIPs</option>';
            (data.zips || []).forEach(zip => {
                const option = document.createElement("option");
                option.value = zip;
                option.textContent = zip;
                zipFilterSelect.appendChild(option);
            });
            zipFilterSelect.value = currentZip;
        } catch (err) {
            console.error("Error loading filter options:", err);
        }
    }

    async function loadAddresses() {
        const params = new URLSearchParams({
            limit: addressLimit,
            offset: addressOffset
        });

        if (addressSearch) params.set("search", addressSearch);
        if (addressCity) params.set("city", addressCity);
        if (addressState) params.set("state", addressState);
        if (addressZip) params.set("zip", addressZip);

        try {
            const response = await fetch(`/addresses?${params.toString()}`);
            const data = await response.json();

            if (!response.ok) {
                showError(data.detail || "Could not load addresses.");
                return;
            }

            addressTotal = data.total || 0;
            registryCount.textContent = `${addressTotal} address${addressTotal === 1 ? "" : "es"}`;
            registryTableBody.innerHTML = "";

            (data.items || []).forEach((address) => {
                const tr = document.createElement("tr");
                tr.classList.add("table-row-animated");
                tr.innerHTML = `
                    <td>${address.id}</td>
                    <td class="address-cell">${address.normalized || "-"}</td>
                    <td>${address.city || "-"}</td>
                    <td>${address.state || "-"}</td>
                    <td>${address.zip || "-"}</td>
                    <td>${address.review_status || "-"}</td>
                    <td class="table-actions">
                        <button type="button" class="btn btn-export view-address-btn" data-id="${address.id}">
                            View
                        </button>
                        <button type="button" class="btn btn-export delete-address-btn" data-id="${address.id}">
                            Delete
                        </button>
                    </td>
                `;
                registryTableBody.appendChild(tr);
            });

            prevAddressesBtn.disabled = addressOffset === 0;
            nextAddressesBtn.disabled = addressOffset + addressLimit >= addressTotal;
        } catch (err) {
            showError("Unable to load address registry.");
        }
    }

    async function loadAddressDetail(addressId) {
        try {
            const response = await fetch(`/addresses/${addressId}`);
            const address = await response.json();

            if (!response.ok) {
                showError(address.detail || "Could not load address details.");
                return;
            }

            const documents = address.documents || [];
            addressDetail.innerHTML = `
                <h3>Address #${address.id}</h3>
                <p><strong>Normalized:</strong> ${address.normalized || "-"}</p>
                <p><strong>Raw:</strong> ${address.raw_text || "-"}</p>
                <p><strong>Documents:</strong></p>
                <ul>
                    ${documents.map((doc) => `
                        <li>#${doc.id} - ${doc.filename} (${doc.status})</li>
                    `).join("")}
                </ul>
            `;
            addressDetail.classList.remove("hidden");
        } catch (err) {
            showError("Unable to load address details.");
        }
    }

    async function deleteAddress(addressId) {
        const confirmed = confirm("Soft-delete this address?");
        if (!confirmed) return;

        try {
            const response = await fetch(`/addresses/${addressId}`, {
                method: "DELETE"
            });
            const data = await response.json();

            if (!response.ok) {
                showError(data.detail || "Could not delete address.");
                return;
            }

            addressDetail.classList.add("hidden");
            await loadFilterOptions();
            await loadAddresses();
            await loadDuplicates();
        } catch (err) {
            showError("Unable to delete address.");
        }
    }

    function applyAddressFilters() {
        addressSearch = addressSearchInput.value.trim();
        addressCity = cityFilterSelect.value.trim();
        addressState = stateFilterSelect.value.trim();
        addressZip = zipFilterSelect.value.trim();
        addressOffset = 0;
        return loadAddresses();
    }

    registryTableBody.addEventListener("click", async (event) => {
        const viewButton = event.target.closest(".view-address-btn");
        const deleteButton = event.target.closest(".delete-address-btn");

        if (viewButton) {
            await loadAddressDetail(viewButton.dataset.id);
        }

        if (deleteButton) {
            await deleteAddress(deleteButton.dataset.id);
        }
    });

    prevAddressesBtn.addEventListener("click", async () => {
        addressOffset = Math.max(0, addressOffset - addressLimit);
        await loadAddresses();
    });

    nextAddressesBtn.addEventListener("click", async () => {
        addressOffset += addressLimit;
        await loadAddresses();
    });

    applyAddressFiltersBtn.addEventListener("click", applyAddressFilters);

    downloadRegistryCsvBtn.addEventListener("click", () => {
        const params = new URLSearchParams({
            format: "csv"
        });

        if (addressSearch) params.set("search", addressSearch);
        if (addressCity) params.set("city", addressCity);
        if (addressState) params.set("state", addressState);
        if (addressZip) params.set("zip", addressZip);

        window.location.href = `/export?${params.toString()}`;
    });

    clearAddressFiltersBtn.addEventListener("click", async () => {
        addressSearchInput.value = "";
        cityFilterSelect.value = "";
        stateFilterSelect.value = "";
        zipFilterSelect.value = "";
        addressSearch = "";
        addressCity = "";
        addressState = "";
        addressZip = "";
        addressOffset = 0;
        await loadFilterOptions();
        await loadAddresses();
    });

    [addressSearchInput].forEach((input) => {
        input.addEventListener("keydown", async (event) => {
            if (event.key === "Enter") {
                await applyAddressFilters();
            }
        });
    });

    [cityFilterSelect, stateFilterSelect, zipFilterSelect].forEach((select) => {
        select.addEventListener("change", applyAddressFilters);
    });

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

    async function loadDuplicates() {
        try {
            const response = await fetch("/duplicates");
            const data = await response.json();
            if (!response.ok) {
                console.error("Failed to load duplicates:", data);
                return;
            }

            const count = data.length || 0;
            reviewCount.textContent = `${count} candidate${count === 1 ? "" : "s"} pending`;

            if (count === 0) {
                reviewSection.classList.add("hidden");
                reviewList.innerHTML = "";
                return;
            }

            reviewList.innerHTML = "";
            data.forEach((cand) => {
                const card = document.createElement("div");
                card.className = "review-card";
                card.innerHTML = `
                    <div class="review-card-header">
                        <span>Candidate Pair #${cand.id}</span>
                        <span class="similarity-badge">${cand.score.toFixed(1)}% Match</span>
                    </div>
                    <div class="review-card-body">
                        <!-- Address A -->
                        <div class="address-comparison-box" id="cand-${cand.id}-a">
                            <h4>Address A (ID: ${cand.address_a.id}) <button type="button" class="btn btn-secondary btn-sm fix-addr-btn" data-id="${cand.address_a.id}" data-street="${cand.address_a.street || ""}" data-city="${cand.address_a.city || ""}" data-state="${cand.address_a.state || ""}" data-zip="${cand.address_a.zip || ""}">Fix</button></h4>
                            <div class="address-field-grid">
                                <div class="address-field-label">Raw:</div>
                                <div class="address-field-value">${cand.address_a.raw_text}</div>
                                <div class="address-field-label">Normalized:</div>
                                <div class="address-field-value">${cand.address_a.normalized || "-"}</div>
                                <div class="address-field-label">Street:</div>
                                <div class="address-field-value">${cand.address_a.street || "-"}</div>
                                <div class="address-field-label">City:</div>
                                <div class="address-field-value">${cand.address_a.city || "-"}</div>
                                <div class="address-field-label">State:</div>
                                <div class="address-field-value">${cand.address_a.state || "-"}</div>
                                <div class="address-field-label">ZIP:</div>
                                <div class="address-field-value">${cand.address_a.zip || "-"}</div>
                            </div>
                        </div>
                        <!-- Address B -->
                        <div class="address-comparison-box" id="cand-${cand.id}-b">
                            <h4>Address B (ID: ${cand.address_b.id}) <button type="button" class="btn btn-secondary btn-sm fix-addr-btn" data-id="${cand.address_b.id}" data-street="${cand.address_b.street || ""}" data-city="${cand.address_b.city || ""}" data-state="${cand.address_b.state || ""}" data-zip="${cand.address_b.zip || ""}">Fix</button></h4>
                            <div class="address-field-grid">
                                <div class="address-field-label">Raw:</div>
                                <div class="address-field-value">${cand.address_b.raw_text}</div>
                                <div class="address-field-label">Normalized:</div>
                                <div class="address-field-value">${cand.address_b.normalized || "-"}</div>
                                <div class="address-field-label">Street:</div>
                                <div class="address-field-value">${cand.address_b.street || "-"}</div>
                                <div class="address-field-label">City:</div>
                                <div class="address-field-value">${cand.address_b.city || "-"}</div>
                                <div class="address-field-label">State:</div>
                                <div class="address-field-value">${cand.address_b.state || "-"}</div>
                                <div class="address-field-label">ZIP:</div>
                                <div class="address-field-value">${cand.address_b.zip || "-"}</div>
                            </div>
                        </div>
                    </div>
                    <div class="review-card-actions">
                        <button type="button" class="btn btn-secondary not-duplicate-btn" data-id="${cand.id}">Not a Duplicate</button>
                        <button type="button" class="btn btn-secondary merge-btn" data-id="${cand.id}" data-winner="${cand.address_a.id}">Merge (Keep A)</button>
                        <button type="button" class="btn btn-primary merge-btn" data-id="${cand.id}" data-winner="${cand.address_b.id}">Merge (Keep B)</button>
                    </div>
                `;
                reviewList.appendChild(card);
            });

            // Re-initialize icons in review queue
            lucide.createIcons();
            reviewSection.classList.remove("hidden");
        } catch (err) {
            console.error("Error loading duplicates:", err);
        }
    }

    // Handle Review Actions (Fix, Not Duplicate, Merge)
    reviewList.addEventListener("click", (e) => {
        const fixBtn = e.target.closest(".fix-addr-btn");
        if (fixBtn) {
            editAddressIdInput.value = fixBtn.dataset.id;
            editStreetInput.value = fixBtn.dataset.street;
            editCityInput.value = fixBtn.dataset.city;
            editStateInput.value = fixBtn.dataset.state;
            editZipInput.value = fixBtn.dataset.zip;
            editAddressModal.classList.remove("hidden");
            return;
        }

        const notDupBtn = e.target.closest(".not-duplicate-btn");
        if (notDupBtn) {
            resolveDuplicate(notDupBtn.dataset.id, "not_duplicate");
            return;
        }

        const mergeBtn = e.target.closest(".merge-btn");
        if (mergeBtn) {
            resolveDuplicate(mergeBtn.dataset.id, "merge", mergeBtn.dataset.winner);
            return;
        }
    });

    async function resolveDuplicate(candidateId, action, winnerId = null) {
        const body = { action };
        if (winnerId) {
            body.winning_address_id = parseInt(winnerId, 10);
        }

        try {
            const response = await fetch(`/duplicates/${candidateId}/resolve`, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify(body)
            });
            const data = await response.json();
            if (!response.ok) {
                showError(data.detail || "Failed to resolve candidate.");
                return;
            }

            await loadDuplicates();
            await loadFilterOptions();
            await loadAddresses();
        } catch (err) {
            showError("Unable to resolve duplicate candidate.");
        }
    }

    // Modal Control
    const hideModal = () => {
        editAddressModal.classList.add("hidden");
        editAddressForm.reset();
    };
    closeEditModalBtn.addEventListener("click", hideModal);
    cancelEditBtn.addEventListener("click", hideModal);

    // Edit address submission
    editAddressForm.addEventListener("submit", async (e) => {
        e.preventDefault();
        const id = editAddressIdInput.value;
        const body = {
            street: editStreetInput.value.trim(),
            city: editCityInput.value.trim(),
            state: editStateInput.value.trim(),
            zip: editZipInput.value.trim()
        };

        try {
            const response = await fetch(`/addresses/${id}`, {
                method: "PATCH",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify(body)
            });
            const data = await response.json();
            if (!response.ok) {
                showError(data.detail || "Failed to save address changes.");
                return;
            }

            hideModal();
            await loadDuplicates();
            await loadFilterOptions();
            await loadAddresses();
        } catch (err) {
            showError("Unable to edit address.");
        }
    });

    async function init() {
        await loadFilterOptions();
        await loadAddresses();
        await loadDuplicates();
    }
    init();
});
