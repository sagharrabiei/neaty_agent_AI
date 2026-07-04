document.addEventListener("DOMContentLoaded", () => {
    // UI Elements
    const btnShowConfig = document.getElementById("btn-show-config");
    const btnCloseConfig = document.getElementById("btn-close-config");
    const btnCancelConfig = document.getElementById("btn-cancel-config");
    const btnSaveConfig = document.getElementById("btn-save-config");
    const configModal = document.getElementById("config-modal");
    
    const inputSourceDir = document.getElementById("input-source-dir");
    const inputDestDir = document.getElementById("input-dest-dir");
    const btnScan = document.getElementById("btn-scan");
    const btnOrganize = document.getElementById("btn-organize");
    
    const scanSpinner = document.getElementById("scan-spinner");
    const organizeSpinner = document.getElementById("organize-spinner");
    
    const statusCard = document.getElementById("status-card");
    const statusTitle = document.getElementById("status-title");
    const statusDesc = document.getElementById("status-desc");
    
    // Tab Elements
    const tabBtnPreview = document.getElementById("tab-btn-preview");
    const tabBtnReport = document.getElementById("tab-btn-report");
    const tabPreviewContent = document.getElementById("tab-preview-content");
    const tabReportContent = document.getElementById("tab-report-content");
    
    const previewEmpty = document.getElementById("preview-empty");
    const previewContainer = document.getElementById("preview-container");
    const filesTableBody = document.getElementById("files-table-body");
    const badgeFileCount = document.getElementById("badge-file-count");
    const badgeSourcePath = document.getElementById("badge-source-path");
    
    const reportEmpty = document.getElementById("report-empty");
    const reportContainer = document.getElementById("report-container");
    const reportMdBody = document.getElementById("report-md-body");
    const btnViewFolder = document.getElementById("btn-view-folder");

    // Mode Selector Elements
    const modeBtnLocal = document.getElementById("mode-btn-local");
    const modeBtnCloud = document.getElementById("mode-btn-cloud");
    const localControls = document.getElementById("local-controls");
    const cloudControls = document.getElementById("cloud-controls");

    // Cloud Mode Elements
    const uploadZone = document.getElementById("upload-zone");
    const inputCloudFile = document.getElementById("input-cloud-file");
    const uploadProgressContainer = document.getElementById("upload-progress-container");
    const uploadProgressBar = document.getElementById("upload-progress-bar");
    const uploadStatusLbl = document.getElementById("upload-status-lbl");
    const uploadPercentLbl = document.getElementById("upload-percent-lbl");
    const btnCloudOrganize = document.getElementById("btn-cloud-organize");
    const cloudOrganizeSpinner = document.getElementById("cloud-organize-spinner");
    const btnDownloadZip = document.getElementById("btn-download-zip");

    let currentSourcePath = "";
    let currentDestPath = "";
    let cloudSession = null; // { session_id, source_dir, destination_dir }

    // Modal Subtabs
    const subtabBtnGcp = document.getElementById("subtab-btn-gcp");
    const subtabBtnApi = document.getElementById("subtab-btn-api");
    const subtabBtnProxy = document.getElementById("subtab-btn-proxy");
    const subtabGcpContent = document.getElementById("subtab-gcp-content");
    const subtabApiContent = document.getElementById("subtab-api-content");
    const subtabProxyContent = document.getElementById("subtab-proxy-content");

    // 1. ENVIRONMENT CONFIGURATION LOGIC
    // Load config from backend
    async function loadConfig() {
        try {
            const res = await fetch("/api/env");
            if (!res.ok) throw new Error("Failed to load environment variables.");
            const data = await res.json();
            
            document.getElementById("cfg-use-enterprise").value = data.GOOGLE_GENAI_USE_ENTERPRISE || "";
            document.getElementById("cfg-project-id").value = data.GOOGLE_CLOUD_PROJECT || "";
            document.getElementById("cfg-location").value = data.GOOGLE_CLOUD_LOCATION || "";
            document.getElementById("cfg-gemini-key").value = data.GEMINI_API_KEY || "";
            document.getElementById("cfg-google-key").value = data.GOOGLE_API_KEY || "";
            document.getElementById("cfg-http-proxy").value = data.HTTP_PROXY || "";
            document.getElementById("cfg-https-proxy").value = data.HTTPS_PROXY || "";
        } catch (err) {
            showStatus("Error Loading Config", err.message, "error");
        }
    }

    // Save config to backend
    async function saveConfig() {
        const config = {
            GEMINI_API_KEY: document.getElementById("cfg-gemini-key").value.trim(),
            GOOGLE_API_KEY: document.getElementById("cfg-google-key").value.trim(),
            GOOGLE_GENAI_USE_ENTERPRISE: document.getElementById("cfg-use-enterprise").value,
            GOOGLE_CLOUD_PROJECT: document.getElementById("cfg-project-id").value.trim(),
            GOOGLE_CLOUD_LOCATION: document.getElementById("cfg-location").value.trim(),
            HTTP_PROXY: document.getElementById("cfg-http-proxy").value.trim(),
            HTTPS_PROXY: document.getElementById("cfg-https-proxy").value.trim(),
        };

        btnSaveConfig.disabled = true;
        btnSaveConfig.textContent = "Saving...";

        try {
            const res = await fetch("/api/env", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(config)
            });

            if (!res.ok) throw new Error("Failed to save environment variables.");
            
            configModal.classList.add("hidden");
            showStatus("Configuration Saved", "Local environment updated successfully.", "success");
        } catch (err) {
            alert("Error saving configuration: " + err.message);
        } finally {
            btnSaveConfig.disabled = false;
            btnSaveConfig.textContent = "Save Settings";
        }
    }

    // Modal Events
    btnShowConfig.addEventListener("click", () => {
        loadConfig();
        configModal.classList.remove("hidden");
    });
    
    btnCloseConfig.addEventListener("click", () => configModal.classList.add("hidden"));
    btnCancelConfig.addEventListener("click", () => configModal.classList.add("hidden"));
    btnSaveConfig.addEventListener("click", saveConfig);

    // Subtab switching logic
    function setupSubtabs(btns, contents) {
        btns.forEach((btn, i) => {
            btn.addEventListener("click", () => {
                btns.forEach(b => b.classList.remove("active"));
                contents.forEach(c => c.classList.remove("active"));
                btn.classList.add("active");
                contents[i].classList.add("active");
            });
        });
    }

    setupSubtabs(
        [subtabBtnGcp, subtabBtnApi, subtabBtnProxy],
        [subtabGcpContent, subtabApiContent, subtabProxyContent]
    );

    // 2. SCANNING LOGIC
    btnScan.addEventListener("click", async () => {
        const sourceDir = inputSourceDir.value.trim();
        if (!sourceDir) {
            showStatus("Invalid Path", "Please provide a valid source directory path.", "error");
            return;
        }

        btnScan.disabled = true;
        scanSpinner.classList.remove("hidden");
        showStatus("Scanning Folder...", "Inspecting local directory files and snippets.", "working");

        try {
            const res = await fetch("/api/scan", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ source_dir: sourceDir })
            });

            if (!res.ok) {
                const errData = await res.json();
                throw new Error(errData.detail || "Scan request failed.");
            }

            const data = await res.json();
            currentSourcePath = data.source_dir;
            currentDestPath = data.destination_dir;

            // Render Preview Table
            renderFilesTable(data.files);
            badgeFileCount.textContent = `${data.files.length} File(s) Detected`;
            badgeSourcePath.textContent = data.source_dir;
            
            previewEmpty.classList.add("hidden");
            previewContainer.classList.remove("hidden");

            // Unlock tabs and organize button
            btnOrganize.classList.remove("disabled");
            btnOrganize.disabled = false;
            tabBtnPreview.click();

            showStatus("Scan Successful", `Discovered ${data.files.length} file(s) ready to organize.`, "success");
        } catch (err) {
            previewEmpty.classList.remove("hidden");
            previewContainer.classList.add("hidden");
            btnOrganize.classList.add("disabled");
            btnOrganize.disabled = true;
            showStatus("Scan Failed", err.message, "error");
        } finally {
            btnScan.disabled = false;
            scanSpinner.classList.add("hidden");
        }
    });

    function renderFilesTable(files) {
        filesTableBody.innerHTML = "";
        if (files.length === 0) {
            filesTableBody.innerHTML = `<tr><td colspan="4" style="text-align: center; color: var(--text-secondary);">No file(s) found inside this directory.</td></tr>`;
            return;
        }

        files.forEach(file => {
            const sizeKB = (file.size_bytes / 1024).toFixed(1);
            const row = document.createElement("tr");
            row.innerHTML = `
                <td title="${file.filepath}"><strong>${file.filename}</strong></td>
                <td><span class="summary-badge cyan-badge" style="font-size: 0.7rem; padding: 0.2rem 0.5rem;">${file.extension}</span></td>
                <td>${sizeKB} KB</td>
                <td>${escapeHtml(file.snippet)}</td>
            `;
            filesTableBody.appendChild(row);
        });
    }

    // 3. ORGANIZATION LOGIC
    btnOrganize.addEventListener("click", async () => {
        const sourceDir = inputSourceDir.value.trim();
        const destDir = inputDestDir.value.trim() || null;

        btnOrganize.disabled = true;
        btnScan.disabled = true;
        organizeSpinner.classList.remove("hidden");
        showStatus("Organizing Files...", "Running ADK Graph workflow. Querying Gemini categorizer model...", "working");

        try {
            const res = await fetch("/api/organize", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ source_dir: sourceDir, destination_dir: destDir })
            });

            if (!res.ok) {
                const errData = await res.json();
                throw errData.detail || { error: "Organization request failed." };
            }

            const data = await res.json();
            
            // Render Report
            renderReport(data.report);
            currentDestPath = data.destination_dir;

            reportEmpty.classList.add("hidden");
            reportContainer.classList.remove("hidden");

            // Ensure proper action buttons are shown/hidden for local mode
            btnViewFolder.classList.remove("hidden");
            btnDownloadZip.classList.add("hidden");
            
            // Enable Report Tab
            tabBtnReport.classList.remove("disabled");
            tabBtnReport.disabled = false;
            tabBtnReport.click();

            showStatus("Organization Success!", "Files structured safely. Check the Report tab!", "success");
        } catch (err) {
            let errMsg = "An unknown error occurred during execution.";
            let errTrace = "";

            if (typeof err === "string") errMsg = err;
            else if (err.error) {
                errMsg = err.error;
                errTrace = err.trace || "";
            }

            // Render detailed traceback into report area so user can inspect it
            renderErrorReport(errMsg, errTrace);
            reportEmpty.classList.add("hidden");
            reportContainer.classList.remove("hidden");
            tabBtnReport.classList.remove("disabled");
            tabBtnReport.disabled = false;
            tabBtnReport.click();

            showStatus("Workflow Run Failed", errMsg, "error");
        } finally {
            btnOrganize.disabled = false;
            btnScan.disabled = false;
            organizeSpinner.classList.add("hidden");
        }
    });

    // 3.5 MODE SWITCHING AND CLOUD INTEGRATION
    function switchMode(mode) {
        if (mode === "local") {
            modeBtnLocal.classList.add("active");
            modeBtnCloud.classList.remove("active");
            localControls.classList.add("active");
            cloudControls.classList.remove("active");
        } else {
            modeBtnLocal.classList.remove("active");
            modeBtnCloud.classList.add("active");
            localControls.classList.remove("active");
            cloudControls.classList.add("active");
        }
    }

    modeBtnLocal.addEventListener("click", () => switchMode("local"));
    modeBtnCloud.addEventListener("click", () => switchMode("cloud"));

    // Check if hosted on cloud or localhost
    const isLocal = window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1";
    if (!isLocal) {
        switchMode("cloud");
    } else {
        switchMode("local");
    }

    // Drag and drop event handling
    uploadZone.addEventListener("click", () => {
        inputCloudFile.click();
    });

    inputCloudFile.addEventListener("change", (e) => {
        if (e.target.files.length > 0) {
            handleZipUpload(e.target.files[0]);
        }
    });

    ["dragenter", "dragover"].forEach(eventName => {
        uploadZone.addEventListener(eventName, (e) => {
            e.preventDefault();
            e.stopPropagation();
            uploadZone.classList.add("dragover");
        }, false);
    });

    ["dragleave", "drop"].forEach(eventName => {
        uploadZone.addEventListener(eventName, (e) => {
            e.preventDefault();
            e.stopPropagation();
            uploadZone.classList.remove("dragover");
        }, false);
    });

    uploadZone.addEventListener("drop", (e) => {
        const dt = e.dataTransfer;
        const files = dt.files;
        if (files.length > 0) {
            const file = files[0];
            if (file.name.endsWith(".zip")) {
                handleZipUpload(file);
            } else {
                showStatus("Unsupported File", "Only .zip archives are supported.", "error");
            }
        }
    });

    function handleZipUpload(file) {
        if (!file.name.endsWith(".zip")) {
            showStatus("Unsupported File", "Please upload a valid .zip file.", "error");
            return;
        }

        // Show progress elements
        uploadProgressContainer.classList.remove("hidden");
        uploadProgressBar.style.width = "0%";
        uploadPercentLbl.textContent = "0%";
        uploadStatusLbl.textContent = "Uploading zip archive...";
        
        btnCloudOrganize.disabled = true;
        btnCloudOrganize.classList.add("disabled");

        const formData = new FormData();
        formData.append("file", file);

        const xhr = new XMLHttpRequest();
        xhr.open("POST", "/api/upload", true);

        // Upload progress listener
        xhr.upload.addEventListener("progress", (e) => {
            if (e.lengthComputable) {
                const percentComplete = Math.round((e.loaded / e.total) * 100);
                uploadProgressBar.style.width = percentComplete + "%";
                uploadPercentLbl.textContent = percentComplete + "%";
                if (percentComplete === 100) {
                    uploadStatusLbl.textContent = "Processing and scanning ZIP...";
                }
            }
        });

        // Request complete listener
        xhr.onload = function() {
            if (xhr.status === 200) {
                try {
                    const data = JSON.parse(xhr.responseText);
                    if (data.status === "success") {
                        cloudSession = {
                            session_id: data.session_id,
                            source_dir: data.source_dir,
                            destination_dir: data.destination_dir
                        };

                        currentSourcePath = data.source_dir;
                        currentDestPath = data.destination_dir;

                        // Render Preview Table
                        renderFilesTable(data.files);
                        badgeFileCount.textContent = `${data.files.length} File(s) Detected`;
                        badgeSourcePath.textContent = "Uploaded ZIP";

                        previewEmpty.classList.add("hidden");
                        previewContainer.classList.remove("hidden");

                        // Unlock organize button
                        btnCloudOrganize.classList.remove("disabled");
                        btnCloudOrganize.disabled = false;
                        
                        // Switch tab to preview
                        tabBtnPreview.click();

                        uploadStatusLbl.textContent = "Upload complete!";
                        showStatus("Upload Successful", `ZIP archive extracted and ${data.files.length} file(s) scanned.`, "success");
                    } else {
                        throw new Error(data.detail || "Processing failed.");
                    }
                } catch (err) {
                    uploadStatusLbl.textContent = "Processing failed.";
                    showStatus("Upload Processing Failed", err.message, "error");
                }
            } else {
                let errorMsg = "Upload failed.";
                try {
                    const errData = JSON.parse(xhr.responseText);
                    errorMsg = errData.detail || errorMsg;
                } catch(e) {}
                uploadStatusLbl.textContent = "Upload failed.";
                showStatus("Upload Failed", errorMsg, "error");
            }
        };

        xhr.onerror = function() {
            uploadStatusLbl.textContent = "Connection error.";
            showStatus("Network Error", "Unable to upload ZIP. Connection lost.", "error");
        };

        xhr.send(formData);
    }

    btnCloudOrganize.addEventListener("click", async () => {
        if (!cloudSession) {
            showStatus("No Session", "Please upload a ZIP file first.", "error");
            return;
        }

        btnCloudOrganize.disabled = true;
        cloudOrganizeSpinner.classList.remove("hidden");
        showStatus("Organizing Files...", "Running ADK Graph workflow inside cloud session...", "working");

        try {
            const res = await fetch("/api/organize", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    source_dir: cloudSession.source_dir,
                    destination_dir: cloudSession.destination_dir
                })
            });

            if (!res.ok) {
                const errData = await res.json();
                throw errData.detail || { error: "Organization request failed." };
            }

            const data = await res.json();

            // Render Report
            renderReport(data.report);

            reportEmpty.classList.add("hidden");
            reportContainer.classList.remove("hidden");

            // Setup buttons in report header
            btnViewFolder.classList.add("hidden");
            btnDownloadZip.classList.remove("hidden");

            // Attach download URL
            if (data.download_url) {
                cloudSession.download_url = data.download_url;
            } else {
                cloudSession.download_url = `/api/download/${cloudSession.session_id}`;
            }

            // Enable Report Tab
            tabBtnReport.classList.remove("disabled");
            tabBtnReport.disabled = false;
            tabBtnReport.click();

            showStatus("Organization Success!", "Download organized ZIP from the report view!", "success");
        } catch (err) {
            let errMsg = "An unknown error occurred during execution.";
            let errTrace = "";

            if (typeof err === "string") errMsg = err;
            else if (err.error) {
                errMsg = err.error;
                errTrace = err.trace || "";
            }

            // Render detailed error report inside the report container
            renderErrorReport(errMsg, errTrace);
            reportEmpty.classList.add("hidden");
            reportContainer.classList.remove("hidden");
            tabBtnReport.classList.remove("disabled");
            tabBtnReport.disabled = false;
            tabBtnReport.click();

            showStatus("Workflow Run Failed", errMsg, "error");
        } finally {
            btnCloudOrganize.disabled = false;
            cloudOrganizeSpinner.classList.add("hidden");
        }
    });

    btnDownloadZip.addEventListener("click", () => {
        if (cloudSession && cloudSession.download_url) {
            window.location.href = cloudSession.download_url;
        } else {
            showStatus("Download Error", "No download link found for this session.", "error");
        }
    });

    // Renders the successful Markdown Report as clean HTML
    function renderReport(mdText) {
        reportMdBody.innerHTML = parseMarkdown(mdText);
    }

    // Renders the detailed error traceback as a nice code blocks inside the Report area
    function renderErrorReport(msg, trace) {
        reportMdBody.innerHTML = `
            <div style="border-left: 4px solid var(--accent-red); background: rgba(239, 68, 68, 0.08); padding: 1rem; border-radius: 8px; margin-bottom: 1.5rem;">
                <h4 style="color: var(--accent-red); font-family: var(--font-header); margin-bottom: 0.5rem;">⚠️ Execution Error</h4>
                <p style="font-size: 0.875rem; color: var(--text-primary); font-weight: 600;">${msg}</p>
            </div>
            
            ${trace ? `
                <h4 style="font-family: var(--font-header); font-size: 0.95rem; margin-bottom: 0.5rem; color: var(--text-secondary);">Technical Stack Trace:</h4>
                <pre style="background: rgba(0,0,0,0.4); border: 1px solid var(--border-color); padding: 1rem; border-radius: 8px; overflow-x: auto; font-family: monospace; font-size: 0.8rem; line-height: 1.4; color: #f87171; white-space: pre-wrap;">${escapeHtml(trace)}</pre>
            ` : ""}
            
            <div style="margin-top: 1.5rem; font-size: 0.85rem; color: var(--text-secondary); line-height: 1.5;">
                <p>💡 <strong>Troubleshooting Advice:</strong></p>
                <ul style="margin-left: 1.25rem; margin-top: 0.5rem;">
                    <li>If you see a <strong>429 Credits Depleted</strong> error, check your AI Studio billing settings.</li>
                    <li>If you see a <strong>404 Model Not Found</strong> or a <strong>RemoteProtocolError (Connection Drops)</strong>, verify your local VPN proxy is running and configured correctly in Settings.</li>
                </ul>
            </div>
        `;
    }

    // Open Output folder on Click
    btnViewFolder.addEventListener("click", () => {
        if (currentDestPath) {
            // Note: Since this is localhost running on their machine, we can open explorer!
            // But we don't need a direct API unless we just alert them where it is or open it.
            // Since we don't have a direct shell API for opening directories in web frontend, 
            // we will let the user know where it is or copy it to clipboard.
            navigator.clipboard.writeText(currentDestPath);
            alert(`Destination Path copied to clipboard:\n${currentDestPath}\n\nYou can paste this into Windows Explorer to view your organized files!`);
        }
    });

    // 4. TAB NAVIGATION CONTROLS
    tabBtnPreview.addEventListener("click", () => {
        tabBtnPreview.classList.add("active");
        tabBtnReport.classList.remove("active");
        tabPreviewContent.classList.add("active");
        tabReportContent.classList.remove("active");
    });

    tabBtnReport.addEventListener("click", () => {
        if (tabBtnReport.disabled) return;
        tabBtnReport.classList.add("active");
        tabBtnPreview.classList.remove("active");
        tabReportContent.classList.add("active");
        tabPreviewContent.classList.remove("active");
    });

    // 5. HELPER UTILS
    function showStatus(title, desc, type) {
        statusCard.className = `status-box ${type}`;
        statusTitle.textContent = title;
        statusDesc.textContent = desc;
        statusCard.classList.remove("hidden");
    }

    function escapeHtml(text) {
        if (!text) return "";
        return text
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }

    // Lightweight self-contained markdown parser for report styling
    function parseMarkdown(md) {
        if (!md) return "";
        let html = md;

        // Escape HTML tags to protect integrity
        html = html.replace(/<(?!\/?(strong|em|h1|h2|h3|ul|li|p|table|thead|tbody|tr|th|td))/g, "&lt;");

        // Convert Headers
        html = html.replace(/^# (.*?)$/gm, "<h1>$1</h1>");
        html = html.replace(/^## (.*?)$/gm, "<h2>$1</h2>");
        html = html.replace(/^### (.*?)$/gm, "<h3>$1</h3>");

        // Convert Bold
        html = html.replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>");

        // Convert Lists
        html = html.replace(/^\- (.*?)$/gm, "<li>$1</li>");
        // Wrap <li> blocks inside <ul> tags
        html = html.replace(/(<li>.*?<\/li>)/gs, "<ul>$1</ul>");
        // De-duplicate redundant adjacent <ul> wraps
        html = html.replace(/<\/ul>\s*<ul>/g, "");

        // Convert Tables
        const lines = html.split("\n");
        let inTable = false;
        let tableHeader = null;
        let tableBody = [];
        let outputLines = [];

        for (let line of lines) {
            const isRow = line.trim().startsWith("|") && line.trim().endsWith("|");
            
            if (isRow) {
                const cells = line.split("|").slice(1, -1).map(c => c.trim());
                
                // Skip separator rows (| :--- | :--- |)
                if (cells.every(c => /^:?\-+:?$/.test(c))) {
                    continue;
                }

                if (!inTable) {
                    inTable = true;
                    tableHeader = cells;
                } else {
                    tableBody.push(cells);
                }
            } else {
                if (inTable) {
                    // Close the table and compile it
                    const tableHtml = renderTableHtml(tableHeader, tableBody);
                    outputLines.push(tableHtml);
                    inTable = false;
                    tableHeader = null;
                    tableBody = [];
                }
                outputLines.push(line);
            }
        }
        
        if (inTable) {
            const tableHtml = renderTableHtml(tableHeader, tableBody);
            outputLines.push(tableHtml);
        }

        html = outputLines.join("\n");

        // Wrap orphan lines as paragraphs
        html = html.split("\n").map(line => {
            const trimmed = line.trim();
            if (!trimmed) return "";
            if (trimmed.startsWith("<h") || trimmed.startsWith("<ul") || trimmed.startsWith("</ul") || trimmed.startsWith("<li") || trimmed.startsWith("<table") || trimmed.startsWith("<div") || trimmed.startsWith("</div")) {
                return line;
            }
            return `<p>${line}</p>`;
        }).join("\n");

        return html;
    }

    function renderTableHtml(header, bodyRows) {
        let headerCells = header.map(h => `<th>${h}</th>`).join("");
        let trs = bodyRows.map(row => {
            let tds = row.map(cell => `<td>${cell}</td>`).join("");
            return `<tr>${tds}</tr>`;
        }).join("");

        return `
            <table>
                <thead>
                    <tr>${headerCells}</tr>
                </thead>
                <tbody>
                    ${trs}
                </tbody>
            </table>
        `;
    }

    // Initial config load on boot
    loadConfig();
});
