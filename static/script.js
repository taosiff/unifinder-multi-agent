/**
 * static/script.js - UniFinder AI Client Controller
 * Multi-Agent Subgraphs • C-RAG • Persistent SqliteSaver Memory • Live Streaming • HITL
 */

// Global State
let currentThreadId = localStorage.getItem("unifinder_thread_id") || `student_${Math.random().toString(36).substring(2, 9)}`;
let currentSessionId = localStorage.getItem("unifinder_session_id") || `session_${Math.random().toString(36).substring(2, 9)}`;
let selectedDegree = "MSc";
let activeProvider = localStorage.getItem("unifinder_llm_provider") || "gemini";
let storedApiKey = localStorage.getItem("unifinder_api_key") || "";
let storedLangsmithKey = localStorage.getItem("unifinder_langsmith_key") || "";

localStorage.setItem("unifinder_thread_id", currentThreadId);
localStorage.setItem("unifinder_session_id", currentSessionId);

// Initialize on DOM load
document.addEventListener("DOMContentLoaded", () => {
    checkSystemStatus();
    updateNavKeyStatus();
    checkLangsmithStatus();
    loadThreadsList();
    loadSessionDocs();
    loadMatrixTable();
    loadShortlist();
    loadOpportunities();
    recalculateROI();
});

// ==========================================
// Sidebar & Threads Management
// ==========================================
function toggleThreadSidebar() {
    const sidebar = document.getElementById("threadSidebar");
    const backdrop = document.getElementById("sidebarBackdrop");
    if (sidebar) {
        const isCollapsed = sidebar.classList.toggle("collapsed");
        if (backdrop) {
            backdrop.classList.toggle("active", !isCollapsed);
        }
    }
}

async function loadThreadsList() {
    try {
        const res = await fetch("/api/threads");
        const data = await res.json();
        if (data.success) {
            renderThreadsList(data.threads);
        }
    } catch (e) {
        console.error("Failed to load threads:", e);
    }
}

function renderThreadsList(threads) {
    const container = document.getElementById("threadsList");
    if (!threads || threads.length === 0) {
        container.innerHTML = `<div class="thread-empty">No conversations yet.</div>`;
        return;
    }

    container.innerHTML = threads.map(t => `
        <div class="thread-item ${t.thread_id === currentThreadId ? 'active' : ''}" onclick="switchThread('${t.thread_id}', '${escapeQuote(t.title)}')">
            <span class="thread-title-text" title="${t.title}">💬 ${t.title}</span>
            <button class="del-thread-btn" onclick="event.stopPropagation(); deleteThread('${t.thread_id}')" title="Delete conversation">✕</button>
        </div>
    `).join("");
}

function createNewThread() {
    currentThreadId = `student_${Math.random().toString(36).substring(2, 9)}`;
    currentSessionId = currentThreadId;
    localStorage.setItem("unifinder_thread_id", currentThreadId);
    localStorage.setItem("unifinder_session_id", currentSessionId);

    // Reset UI
    document.getElementById("userQuery").value = "";
    document.getElementById("dossierCard").classList.add("hidden");
    document.getElementById("metricsBanner").classList.add("hidden");
    document.getElementById("agentStepper").classList.add("hidden");
    document.getElementById("hitlBanner").classList.add("hidden");
    document.getElementById("dossierContent").innerHTML = "";

    loadThreadsList();
    loadSessionDocs();
    showToast("Started new counseling session!");
}

function switchThread(threadId, title) {
    currentThreadId = threadId;
    currentSessionId = threadId;
    localStorage.setItem("unifinder_thread_id", currentThreadId);
    localStorage.setItem("unifinder_session_id", currentSessionId);

    loadThreadsList();
    loadSessionDocs();
    showToast(`Switched to: ${title}`);
    if (window.innerWidth <= 1024) {
        toggleThreadSidebar();
    }
}

async function deleteThread(threadId) {
    try {
        const res = await fetch(`/api/threads/${threadId}`, { method: "DELETE" });
        const data = await res.json();
        if (data.success) {
            if (currentThreadId === threadId) {
                createNewThread();
            } else {
                loadThreadsList();
            }
        }
    } catch (e) {
        showToast("Error deleting thread.");
    }
}

// ==========================================
// C-RAG Document Upload
// ==========================================
async function handleFileUpload(files) {
    if (!files || files.length === 0) return;
    const file = files[0];

    const feedback = document.getElementById("uploadFeedback");
    feedback.textContent = `Indexing ${file.name} for C-RAG...`;
    feedback.className = "upload-feedback";
    feedback.classList.remove("hidden");

    const formData = new FormData();
    formData.append("file", file);
    formData.append("session_id", currentSessionId);

    try {
        const res = await fetch("/api/upload-doc", {
            method: "POST",
            body: formData
        });
        const data = await res.json();
        if (data.success) {
            feedback.innerHTML = `✅ <strong>${data.filename}</strong> indexed (${data.total_chunks} chunks).`;
            
            // Auto-populate hints
            if (data.profile_hints) {
                if (data.profile_hints.detected_gpa) {
                    const gpaVal = parseFloat(data.profile_hints.detected_gpa);
                    if (!isNaN(gpaVal)) {
                        document.getElementById("gpaInput").value = Math.min(4.0, gpaVal);
                        feedback.innerHTML += `<br>Detected GPA: ${data.profile_hints.detected_gpa} (applied).`;
                    }
                }
                if (data.profile_hints.detected_ielts) {
                    document.getElementById("ieltsInput").value = data.profile_hints.detected_ielts;
                    feedback.innerHTML += ` Detected IELTS: ${data.profile_hints.detected_ielts}.`;
                }
                if (data.profile_hints.detected_major) {
                    document.getElementById("subjectInput").value = data.profile_hints.detected_major;
                }
            }
            loadSessionDocs();
            showToast("Document indexed for C-RAG!");
        } else {
            feedback.className = "upload-feedback error";
            feedback.textContent = `Upload failed: ${data.error}`;
        }
    } catch (e) {
        feedback.className = "upload-feedback error";
        feedback.textContent = `Upload error: ${e.message}`;
    }
}

async function loadSessionDocs() {
    if (!currentSessionId || currentSessionId === "undefined" || currentSessionId === "null") {
        currentSessionId = `session_${Math.random().toString(36).substring(2, 9)}`;
        localStorage.setItem("unifinder_session_id", currentSessionId);
    }
    try {
        const res = await fetch(`/api/documents/${encodeURIComponent(currentSessionId)}`);
        const data = await res.json();
        const list = document.getElementById("docsList");
        if (data.success && data.documents && data.documents.length > 0) {
            list.innerHTML = data.documents.map(d => `
                <div class="doc-item">
                    <span>📄</span>
                    <span style="overflow:hidden; text-overflow:ellipsis; white-space:nowrap;">${d}</span>
                </div>
            `).join("");
        } else {
            list.innerHTML = `<div class="doc-empty">No documents uploaded yet.</div>`;
        }
    } catch (e) {
        console.error("Docs load error:", e);
    }
}

// ==========================================
// Tab Switching
// ==========================================
function switchTab(tabName) {
    document.querySelectorAll(".tab-btn").forEach(btn => btn.classList.remove("active"));
    document.querySelectorAll(".tab-content").forEach(content => content.classList.remove("active"));

    const targetBtn = Array.from(document.querySelectorAll(".tab-btn")).find(b => b.getAttribute("onclick")?.includes(tabName));
    if (targetBtn) targetBtn.classList.add("active");

    const targetContent = document.getElementById(`tab-${tabName}`);
    if (targetContent) targetContent.classList.add("active");
}

function selectDegree(degree) {
    selectedDegree = degree;
    document.querySelectorAll(".segment-btn").forEach(btn => {
        if (btn.textContent.trim().toUpperCase() === degree.toUpperCase()) {
            btn.classList.add("active");
        } else {
            btn.classList.remove("active");
        }
    });
}

function updateBudgetDisplay(val) {
    document.getElementById("budgetValue").textContent = `$${parseInt(val).toLocaleString()} USD`;
}

function setQuickScenario(deg, subj, country, gpa, ielts, budget, query) {
    selectDegree(deg);
    document.getElementById("subjectInput").value = subj;
    document.getElementById("countryInput").value = country;
    document.getElementById("gpaInput").value = gpa;
    document.getElementById("ieltsInput").value = ielts;
    document.getElementById("budgetInput").value = budget;
    updateBudgetDisplay(budget);
    document.getElementById("userQuery").value = query;

    document.getElementById("userQuery").scrollIntoView({ behavior: "smooth", block: "center" });
    document.getElementById("userQuery").focus();
}

// ==========================================
// Multi-Agent Execution Flow (with Live Streaming)
// ==========================================
async function runFinder() {
    hideError();

    const queryInput = document.getElementById("userQuery");
    const query = queryInput.value.trim();

    if (!query) {
        showError("Please enter your study goal, preferred universities, or budget questions.");
        return;
    }

    const findBtn = document.getElementById("findBtn");
    const btnText = findBtn.querySelector(".btn-text");
    const btnSpinner = findBtn.querySelector(".btn-spinner");
    const stepper = document.getElementById("agentStepper");
    const isStreaming = document.getElementById("streamToggle").checked;

    findBtn.disabled = true;
    btnText.textContent = "Multi-Agent System Working...";
    btnSpinner.classList.remove("hidden");
    stepper.classList.remove("hidden");

    const stepIds = ["step-guardrail", "step-crag", "step-discovery", "step-opps", "step-pr", "step-synthesis"];
    resetStepper(stepIds);

    const payload = {
        message: query,
        thread_id: currentThreadId,
        session_id: currentSessionId,
        degree_level: selectedDegree,
        subject: document.getElementById("subjectInput").value.trim() || "Computer Science",
        country: document.getElementById("countryInput").value,
        user_gpa: parseFloat(document.getElementById("gpaInput").value) || 3.4,
        user_ielts: parseFloat(document.getElementById("ieltsInput").value) || 6.5,
        budget_usd: parseInt(document.getElementById("budgetInput").value) || 25000,
        api_key: storedApiKey || null,
        llm_provider: activeProvider
    };

    if (isStreaming) {
        await executeStreamingSearch(payload, stepIds);
    } else {
        await executeStandardSearch(payload, stepIds);
    }

    findBtn.disabled = false;
    btnText.textContent = "🚀 Run Multi-Agent Search";
    btnSpinner.classList.add("hidden");
    loadThreadsList();
}

async function executeStreamingSearch(payload, stepIds) {
    const dossierCard = document.getElementById("dossierCard");
    const dossierContent = document.getElementById("dossierContent");
    const threadDisplay = document.getElementById("threadDisplay");

    dossierCard.classList.remove("hidden");
    dossierContent.innerHTML = `<span class="streaming-cursor"></span>`;
    threadDisplay.textContent = `Thread: ${payload.thread_id}`;

    let accumulatedMarkdown = "";
    let stepIdx = 0;

    try {
        const response = await fetch("/api/chat/stream", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });

        if (!response.ok) throw new Error("Stream connection failed.");

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split("\n\n");
            buffer = lines.pop(); // Retain remainder

            for (const line of lines) {
                if (line.startsWith("data: ")) {
                    const eventData = JSON.parse(line.substring(6));

                    if (eventData.type === "step") {
                        if (stepIdx < stepIds.length) {
                            if (stepIdx > 0) {
                                document.getElementById(stepIds[stepIdx - 1]).classList.remove("active");
                                document.getElementById(stepIds[stepIdx - 1]).classList.add("completed");
                            }
                            document.getElementById(stepIds[stepIdx]).classList.add("active");
                            stepIdx++;
                        }
                    } else if (eventData.type === "token") {
                        accumulatedMarkdown += eventData.content;
                        if (typeof marked !== "undefined") {
                            dossierContent.innerHTML = marked.parse(accumulatedMarkdown) + `<span class="streaming-cursor"></span>`;
                        } else {
                            dossierContent.innerText = accumulatedMarkdown;
                        }
                    } else if (eventData.type === "complete") {
                        stepIds.forEach(id => {
                            document.getElementById(id).classList.remove("active");
                            document.getElementById(id).classList.add("completed");
                        });
                        displayCompletedMetadata(eventData.data);
                        // Final clean render
                        if (typeof marked !== "undefined") {
                            dossierContent.innerHTML = marked.parse(accumulatedMarkdown);
                        }
                    }
                }
            }
        }
    } catch (e) {
        showError("Streaming error: " + e.message);
    }
}

async function executeStandardSearch(payload, stepIds) {
    let stepIndex = 0;
    const stepInterval = setInterval(() => {
        if (stepIndex < stepIds.length) {
            if (stepIndex > 0) {
                document.getElementById(stepIds[stepIndex - 1]).classList.remove("active");
                document.getElementById(stepIds[stepIndex - 1]).classList.add("completed");
            }
            document.getElementById(stepIds[stepIndex]).classList.add("active");
            stepIndex++;
        }
    }, 400);

    try {
        const res = await fetch("/api/find", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });
        const data = await res.json();
        clearInterval(stepInterval);

        stepIds.forEach(id => {
            document.getElementById(id).classList.remove("active");
            document.getElementById(id).classList.add("completed");
        });

        if (!res.ok || !data.success) {
            throw new Error(data.error || "Search failed.");
        }

        displayDossierResults(data);
    } catch (e) {
        clearInterval(stepInterval);
        showError(e.message);
    }
}

function resetStepper(stepIds) {
    stepIds.forEach(id => {
        const el = document.getElementById(id);
        el.classList.remove("active", "completed");
    });
}

function displayCompletedMetadata(data) {
    const metricsBanner = document.getElementById("metricsBanner");
    const cragBadge = document.getElementById("cragBadge");

    document.getElementById("metricUnisCount").textContent = data.discovered_universities?.length || 0;
    if (data.immigration_analysis) {
        document.getElementById("metricPswv").textContent = data.immigration_analysis.pswv_duration?.split("(")[0]?.trim() || "1-3 Yrs";
    }
    if (data.career_roi_analysis) {
        const startSalary = data.career_roi_analysis.projected_starting_salary_avg_usd;
        document.getElementById("metricStartingSalary").textContent = startSalary ? `$${(startSalary/1000).toFixed(0)}k/yr` : "$75k+";
        document.getElementById("metricPayback").textContent = `${data.career_roi_analysis.payback_period_years || 1.8} Yrs`;
    }

    metricsBanner.classList.remove("hidden");

    if (data.crag_grounding) {
        cragBadge.classList.remove("hidden");
    } else {
        cragBadge.classList.add("hidden");
    }

    // HITL Check
    handleHITLState(data);
}

function displayDossierResults(data) {
    displayCompletedMetadata(data);
    const dossierCard = document.getElementById("dossierCard");
    const dossierContent = document.getElementById("dossierContent");
    const threadDisplay = document.getElementById("threadDisplay");

    if (typeof marked !== "undefined") {
        dossierContent.innerHTML = marked.parse(data.dossier);
    } else {
        dossierContent.innerText = data.dossier;
    }

    threadDisplay.textContent = `Thread: ${data.thread_id}`;
    dossierCard.classList.remove("hidden");
    metricsBanner.scrollIntoView({ behavior: "smooth", block: "start" });
}

function handleHITLState(data) {
    const banner = document.getElementById("hitlBanner");
    const reasonText = document.getElementById("hitlReasonText");
    const btnContainer = document.getElementById("hitlActionButtons");

    if (data.hitl_required) {
        reasonText.textContent = data.hitl_reason || "Admissions counselor verification required.";
        btnContainer.innerHTML = (data.hitl_options || ["Confirm Strategy", "Revise Parameters"]).map(opt => `
            <button class="hitl-btn" onclick="resolveHITL('${escapeQuote(opt)}')">✓ ${opt}</button>
        `).join("");
        banner.classList.remove("hidden");
    } else {
        banner.classList.add("hidden");
    }
}

async function resolveHITL(decision) {
    try {
        const res = await fetch("/api/hitl-action", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ thread_id: currentThreadId, decision: decision })
        });
        const data = await res.json();
        if (data.success) {
            document.getElementById("hitlBanner").classList.add("hidden");
            showToast(`HITL Decision: ${decision} recorded!`);
        }
    } catch (e) {
        showToast("Error recording HITL decision.");
    }
}

// ==========================================
// Live Opportunities & Scholarships (Tab 2)
// ==========================================
let cachedScholarships = [];
let cachedNews = [];

async function loadOpportunities() {
    try {
        const res = await fetch("/api/opportunities");
        const data = await res.json();
        if (data.success) {
            cachedScholarships = data.scholarships;
            cachedNews = data.news;
            renderOpportunities(cachedScholarships);
            renderNews(cachedNews);
        }
    } catch (e) {
        console.error("Opportunities load error:", e);
    }
}

function filterOpportunities() {
    const dest = document.getElementById("oppCountryFilter").value.toLowerCase();
    const deg = document.getElementById("oppDegreeFilter").value;
    const fund = document.getElementById("oppFundingFilter").value.toLowerCase();

    const filtered = cachedScholarships.filter(s => {
        const matchDest = !dest || s.destination.toLowerCase().includes(dest);
        const matchDeg = !deg || s.degree_levels.includes(deg);
        const matchFund = !fund || s.funding_type.toLowerCase().includes(fund);
        return matchDest && matchDeg && matchFund;
    });

    renderOpportunities(filtered);
}

function renderOpportunities(opps) {
    const container = document.getElementById("oppsGrid");
    if (!opps || opps.length === 0) {
        container.innerHTML = `<div class="loading-cell">No scholarships match the selected filter.</div>`;
        return;
    }

    container.innerHTML = opps.map(o => `
        <div class="opp-card">
            <div>
                <div class="opp-card-header">
                    <h4>${o.title}</h4>
                    <span class="opp-funding-tag">${o.funding_type}</span>
                </div>
                <div class="opp-detail-row"><strong>📍 Destination:</strong> ${o.destination}</div>
                <div class="opp-detail-row"><strong>🎓 Degrees:</strong> ${o.degree_levels.join(", ")}</div>
                <div class="opp-detail-row"><strong>💰 Coverage:</strong> ${o.coverage}</div>
                <div class="opp-detail-row"><strong>📅 Deadline:</strong> <span style="color:#C92A2A; font-weight:700;">${o.deadline}</span></div>
                <div class="opp-detail-row"><strong>📋 Eligibility:</strong> ${o.eligibility}</div>
            </div>
            <a href="${o.official_url}" target="_blank" rel="noopener" class="opp-apply-btn">
                Visit Official Portal ↗
            </a>
        </div>
    `).join("");
}

function renderNews(news) {
    const container = document.getElementById("newsGrid");
    if (!news || news.length === 0) {
        container.innerHTML = `<div class="loading-cell">No recent bulletins.</div>`;
        return;
    }

    container.innerHTML = news.map(n => `
        <div class="news-card">
            <div class="news-card-title">${n.title}</div>
            <div class="news-card-meta">
                <span>📍 ${n.country}</span>
                <span>🏷️ ${n.category}</span>
                <span>🕒 ${n.date}</span>
            </div>
            <div class="news-card-summary">${n.summary}</div>
            <div style="margin-top:0.5rem; font-size:0.75rem; color:#2B8A3E; font-weight:600;">
                💡 Strategic Impact: ${n.impact}
            </div>
        </div>
    `).join("");
}

// ==========================================
// University Comparison Matrix (Tab 3)
// ==========================================
let cachedUniversities = [];

async function loadMatrixTable() {
    const tbody = document.getElementById("universityTableBody");
    tbody.innerHTML = `<tr><td colspan="9" class="loading-cell">Loading university matrix...</td></tr>`;

    try {
        const res = await fetch("/api/universities");
        const data = await res.json();
        if (data.success) {
            cachedUniversities = data.universities;
            renderMatrixRows(cachedUniversities);
        }
    } catch (e) {
        tbody.innerHTML = `<tr><td colspan="9" class="loading-cell">Failed to load universities: ${e.message}</td></tr>`;
    }
}

function filterMatrixTable() {
    const searchVal = document.getElementById("matrixSearch").value.toLowerCase().trim();
    const countryVal = document.getElementById("matrixCountryFilter").value;

    const filtered = cachedUniversities.filter(u => {
        const matchSearch = !searchVal || 
            u.name.toLowerCase().includes(searchVal) ||
            (u.subjects && u.subjects.some(s => s.toLowerCase().includes(searchVal)));
        const matchCountry = !countryVal || u.country.toLowerCase() === countryVal.toLowerCase();
        return matchSearch && matchCountry;
    });

    renderMatrixRows(filtered);
}

function renderMatrixRows(unis) {
    const tbody = document.getElementById("universityTableBody");
    if (!unis || unis.length === 0) {
        tbody.innerHTML = `<tr><td colspan="9" class="loading-cell">No universities match filter.</td></tr>`;
        return;
    }

    tbody.innerHTML = unis.map(u => {
        const degrees = Array.isArray(u.degree_levels) ? u.degree_levels.join(", ") : u.degree_levels;
        const prClass = u.pr_pathway_rating === "High" || u.pr_pathway_rating === "Very High" ? "tier-safety" : u.pr_pathway_rating === "Moderate" ? "tier-target" : "tier-reach";

        return `
            <tr>
                <td><strong>#${u.world_ranking || 'N/A'}</strong></td>
                <td>
                    <strong>${u.name}</strong><br>
                    <small style="color: #64748B;">📍 ${u.city}, ${u.country}</small>
                </td>
                <td><span style="font-weight:600;">${degrees}</span></td>
                <td><strong>$${(u.tuition_fee_annual_usd || 0).toLocaleString()}</strong> / yr</td>
                <td>$${(u.living_cost_annual_usd || 0).toLocaleString()} / yr</td>
                <td>${u.min_gpa || 3.0} / 4.0</td>
                <td>${u.post_study_work_permit_years || 2.0} Years</td>
                <td><span class="tier-badge ${prClass}">${u.pr_pathway_rating}</span></td>
                <td>
                    <button class="small-btn" onclick="saveToShortlistFromMatrix(${u.id}, '${escapeQuote(u.name)}', 'MSc Computer Science', '${u.degree_levels ? u.degree_levels[0] : 'MSc'}')">
                        ⭐ Save
                    </button>
                </td>
            </tr>
        `;
    }).join("");
}

function escapeQuote(str) {
    return (str || "").replace(/'/g, "\\'");
}

// ==========================================
// Interactive ROI Forecaster (Tab 5)
// ==========================================
function recalculateROI() {
    const country = document.getElementById("roiCountry").value;
    const subject = document.getElementById("roiSubject").value;
    const duration = parseFloat(document.getElementById("roiDuration").value);
    const annualTuition = parseInt(document.getElementById("roiTuition").value);
    const annualLiving = parseInt(document.getElementById("roiLiving").value);
    const scholarship = parseInt(document.getElementById("roiScholarship").value);

    document.getElementById("roiTuitionLabel").textContent = `$${annualTuition.toLocaleString()}`;
    document.getElementById("roiLivingLabel").textContent = `$${annualLiving.toLocaleString()}`;
    document.getElementById("roiScholarshipLabel").textContent = `$${scholarship.toLocaleString()}`;

    const benchmarks = {
        "United States": { "Computer Science": 115000, "Data Science": 110000, "Engineering": 88000, "Business": 85000, "Finance": 95000, "Humanities": 55000 },
        "Germany": { "Computer Science": 68000, "Data Science": 66000, "Engineering": 65000, "Business": 55000, "Finance": 62000, "Humanities": 42000 },
        "Canada": { "Computer Science": 72000, "Data Science": 70000, "Engineering": 62000, "Business": 54000, "Finance": 60000, "Humanities": 40000 },
        "United Kingdom": { "Computer Science": 58000, "Data Science": 56000, "Engineering": 48000, "Business": 46000, "Finance": 65000, "Humanities": 35000 },
        "Australia": { "Computer Science": 70000, "Data Science": 68000, "Engineering": 65000, "Business": 52000, "Finance": 62000, "Humanities": 42000 },
        "Netherlands": { "Computer Science": 62000, "Data Science": 60000, "Engineering": 58000, "Business": 50000, "Finance": 56000, "Humanities": 38000 }
    };

    const cData = benchmarks[country] || benchmarks["Germany"];
    const startingSalary = cData[subject] || 60000;

    const totalTuition = Math.max(0, (annualTuition * duration) - scholarship);
    const totalLiving = annualLiving * duration;
    const partTimeEarnings = 10000 * duration;
    const netInvestment = Math.max(0, (totalTuition + totalLiving) - partTimeEarnings);

    const annualSavings = Math.round(startingSalary * 0.32);
    const paybackYears = (netInvestment / Math.max(1000, annualSavings)).toFixed(1);
    const threeYearProfit = (annualSavings * 3) - netInvestment;

    document.getElementById("roiTotalCost").textContent = `$${netInvestment.toLocaleString()}`;
    document.getElementById("roiStartingSalary").textContent = `$${startingSalary.toLocaleString()} / yr`;
    document.getElementById("roiPaybackYears").textContent = `${paybackYears} Years`;
    document.getElementById("roiThreeYearProfit").textContent = `${threeYearProfit >= 0 ? '+' : ''}$${threeYearProfit.toLocaleString()}`;

    const badge = document.getElementById("roiRatingBadge");
    if (paybackYears <= 1.5) {
        badge.className = "rating-badge high";
        badge.textContent = "Exceptional ROI";
    } else if (paybackYears <= 3.0) {
        badge.className = "rating-badge moderate";
        badge.textContent = "Strong ROI";
    } else {
        badge.className = "rating-badge challenging";
        badge.textContent = "Moderate ROI";
    }

    let verdict = "";
    if (country === "Germany" || country === "Netherlands") {
        verdict = `With affordable tuition at top European universities and high tech demand, ${country} yields an exceptional payback time of ${paybackYears} years.`;
    } else if (country === "United States") {
        verdict = `US tuition is higher, but graduate tech starting salaries ($${startingSalary.toLocaleString()}) are the highest globally. Over 3 years, you achieve net savings of $${threeYearProfit.toLocaleString()}.`;
    } else {
        verdict = `${country} provides attractive work rights and steady graduate hiring in ${subject}, breaking even in ${paybackYears} years.`;
    }
    document.getElementById("roiVerdictText").textContent = verdict;
}

// ==========================================
// Statement of Purpose (SOP) Reviewer (Tab 6)
// ==========================================
async function reviewSOP() {
    const text = document.getElementById("sopText").value.trim();
    const targetUni = document.getElementById("sopTargetUni").value.trim();

    if (!text) {
        showToast("Please paste your Statement of Purpose text first.");
        return;
    }

    const btnText = document.getElementById("sopBtnText");
    const btnLoader = document.getElementById("sopBtnLoader");
    btnText.textContent = "Analyzing Admissions Impact...";
    btnLoader.classList.remove("hidden");

    try {
        const res = await fetch("/api/review-sop", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                sop_text: text,
                target_program: "Graduate Studies",
                target_university: targetUni
            })
        });

        const data = await res.json();
        if (data.success) {
            renderSOPFeedback(data.review);
        } else {
            showToast(data.error || "Failed to analyze SOP.");
        }
    } catch (e) {
        showToast("Error reviewing SOP: " + e.message);
    } finally {
        btnText.textContent = "🔍 Review My SOP";
        btnLoader.classList.add("hidden");
    }
}

function renderSOPFeedback(review) {
    document.getElementById("sopScoreVal").textContent = review.admissions_impact_score;
    document.getElementById("sopWordCountLabel").textContent = `Word count: ${review.word_count} words`;

    const ratingHeader = document.getElementById("sopRatingHeader");
    if (review.admissions_impact_score >= 80) {
        ratingHeader.textContent = "Competitive & Compelling";
        ratingHeader.style.color = "#2B8A3E";
    } else if (review.admissions_impact_score >= 65) {
        ratingHeader.textContent = "Promising, Needs Polish";
        ratingHeader.style.color = "#E67700";
    } else {
        ratingHeader.textContent = "Needs Technical Refinement";
        ratingHeader.style.color = "#C92A2A";
    }

    document.getElementById("sopStrengthsList").innerHTML = review.strengths.map(s => `<li>${s}</li>`).join("") || "<li>No major strengths detected.</li>";
    document.getElementById("sopCritiquesList").innerHTML = review.critiques.map(c => `<li>${c}</li>`).join("") || "<li>No major critical flags.</li>";
    document.getElementById("sopSuggestionsList").innerHTML = review.actionable_suggestions.map(s => `<li>${s}</li>`).join("");
}

// ==========================================
// Shortlist Wishlist (Tab 7)
// ==========================================
async function saveToShortlistFromMatrix(uniId, uniName, progName, deg) {
    try {
        const res = await fetch("/api/shortlist", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                session_id: currentSessionId,
                university_id: uniId,
                program_name: progName,
                degree_level: deg,
                notes: "Saved from University Matrix"
            })
        });
        const data = await res.json();
        if (data.success) {
            showToast(`⭐ Saved ${uniName} to wishlist!`);
            loadShortlist();
        }
    } catch (e) {
        showToast("Failed to save: " + e.message);
    }
}

async function loadShortlist() {
    try {
        const res = await fetch(`/api/shortlist/${currentSessionId}`);
        const data = await res.json();
        if (data.success) {
            renderShortlistTable(data.items);
        }
    } catch (e) {
        console.error("Shortlist load error:", e);
    }
}

function renderShortlistTable(items) {
    const tbody = document.getElementById("shortlistTableBody");
    const countEl = document.getElementById("shortlistCount");
    const totalLabel = document.getElementById("shortlistTotalLabel");

    countEl.textContent = items.length;
    totalLabel.textContent = `Saved Universities: ${items.length}`;

    if (!items || items.length === 0) {
        tbody.innerHTML = `<tr><td colspan="8" class="loading-cell">No universities saved to shortlist yet.</td></tr>`;
        return;
    }

    tbody.innerHTML = items.map(item => `
        <tr>
            <td>
                <strong>${item.university_name}</strong><br>
                <small style="color: #64748B;">📍 ${item.city}, ${item.country}</small>
            </td>
            <td>${item.country}</td>
            <td><strong>${item.degree_level}</strong></td>
            <td>${item.program_name}</td>
            <td>$${(item.tuition_usd || 0).toLocaleString()} / yr</td>
            <td><span class="rating-badge high">${item.pr_status || 'Standard'}</span></td>
            <td><small>${item.notes || 'No notes'}</small></td>
            <td>
                <button class="small-btn" style="border-color:#C92A2A; color:#C92A2A;" onclick="deleteShortlistItem(${item.id})">
                    🗑️ Remove
                </button>
            </td>
        </tr>
    `).join("");
}

async function deleteShortlistItem(id) {
    try {
        const res = await fetch(`/api/shortlist/${currentSessionId}/${id}`, { method: "DELETE" });
        const data = await res.json();
        if (data.success) {
            showToast("Item removed from wishlist.");
            loadShortlist();
        }
    } catch (e) {
        showToast("Error deleting item.");
    }
}

function exportShortlistJSON() {
    fetch(`/api/shortlist/${currentSessionId}`)
        .then(res => res.json())
        .then(data => {
            const blob = new Blob([JSON.stringify(data.items, null, 2)], { type: "application/json" });
            const url = URL.createObjectURL(blob);
            const a = document.createElement("a");
            a.href = url;
            a.download = `unifinder_wishlist_${new Date().toISOString().slice(0, 10)}.json`;
            a.click();
            URL.revokeObjectURL(url);
            showToast("Wishlist exported to JSON!");
        });
}

function printShortlist() {
    window.print();
}

// ==========================================
// API Key Setup Modal & LangSmith
// ==========================================
function openKeyModal() {
    document.getElementById("keyModal").classList.remove("hidden");
    document.getElementById("apiKeyInput").value = storedApiKey;
    document.getElementById("langsmithKeyInput").value = storedLangsmithKey;
}

function closeKeyModal() {
    document.getElementById("keyModal").classList.add("hidden");
    document.getElementById("keyTestResult").classList.add("hidden");
}

function selectProvider(prov) {
    activeProvider = prov;
    localStorage.setItem("unifinder_llm_provider", prov);

    const gemBtn = document.getElementById("provGeminiBtn");
    const groqBtn = document.getElementById("provGroqBtn");
    const gemGuide = document.getElementById("geminiGuide");
    const groqGuide = document.getElementById("groqGuide");

    if (prov === "gemini") {
        gemBtn.classList.add("active");
        groqBtn.classList.remove("active");
        gemGuide.classList.remove("hidden");
        groqGuide.classList.add("hidden");
        document.getElementById("apiKeyInput").placeholder = "Paste your Google Gemini API key (AIzaSy...)";
    } else {
        groqBtn.classList.add("active");
        gemBtn.classList.remove("active");
        groqGuide.classList.remove("hidden");
        gemGuide.classList.add("hidden");
        document.getElementById("apiKeyInput").placeholder = "Paste your Groq API key (gsk_...)";
    }
}

async function testKeyConnection() {
    const key = document.getElementById("apiKeyInput").value.trim();
    const resultBox = document.getElementById("keyTestResult");

    if (!key) {
        resultBox.className = "key-test-result error";
        resultBox.textContent = "Please enter an API key to test.";
        resultBox.classList.remove("hidden");
        return;
    }

    resultBox.className = "key-test-result";
    resultBox.textContent = "Connecting to " + (activeProvider === 'gemini' ? 'Google Gemini' : 'Groq') + "...";
    resultBox.classList.remove("hidden");

    try {
        const res = await fetch("/api/test-key", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ api_key: key, provider: activeProvider })
        });
        const data = await res.json();
        if (data.success) {
            resultBox.className = "key-test-result success";
            resultBox.textContent = `✅ Success! Connected to ${data.provider}. Key is active and ready.`;
        } else {
            resultBox.className = "key-test-result error";
            resultBox.textContent = `❌ Connection failed: ${data.error}`;
        }
    } catch (e) {
        resultBox.className = "key-test-result error";
        resultBox.textContent = `❌ Network Error: ${e.message}`;
    }
}

function saveApiKey() {
    const key = document.getElementById("apiKeyInput").value.trim();
    const lsKey = document.getElementById("langsmithKeyInput").value.trim();

    storedApiKey = key;
    storedLangsmithKey = lsKey;
    localStorage.setItem("unifinder_api_key", key);
    localStorage.setItem("unifinder_langsmith_key", lsKey);
    localStorage.setItem("unifinder_llm_provider", activeProvider);

    updateNavKeyStatus();
    checkLangsmithStatus();
    closeKeyModal();
    showToast("API keys saved! Ready for multi-agent reasoning.");
}

function updateNavKeyStatus() {
    const label = document.getElementById("navKeyLabel");
    if (storedApiKey) {
        label.textContent = activeProvider === "gemini" ? "Gemini Connected" : "Groq Connected";
    } else {
        label.textContent = "Set API Key (Free)";
    }
}

async function checkLangsmithStatus() {
    const tag = document.getElementById("langsmithTag");
    const label = document.getElementById("langsmithLabel");

    try {
        const res = await fetch("/api/langsmith-status");
        const data = await res.json();
        if (data.tracing_enabled || storedLangsmithKey) {
            tag.classList.add("active");
            label.textContent = "LangSmith Tracing ON";
        } else {
            tag.classList.remove("active");
            label.textContent = "LangSmith Ready";
        }
    } catch (e) {
        console.error("Langsmith status error:", e);
    }
}

async function checkSystemStatus() {
    try {
        const res = await fetch("/api/status");
        const data = await res.json();
        const statusText = document.getElementById("statusText");
        if (statusText) {
            statusText.textContent = `${data.checkpointer || 'PostgresSaver'} Ready`;
        }
        if (!storedApiKey && (data.has_google_key || data.has_groq_key)) {
            const label = document.getElementById("navKeyLabel");
            if (label) {
                label.textContent = data.has_google_key ? "Gemini Key (Active)" : "Groq Key (Active)";
            }
        }
    } catch (e) {
        console.error("Status check error:", e);
    }
}

// ==========================================
// Utilities
// ==========================================
function copyDossier() {
    const content = document.getElementById("dossierContent").innerText;
    navigator.clipboard.writeText(content).then(() => {
        showToast("📋 Dossier copied to clipboard!");
    });
}

function printDossier() {
    window.print();
}

function showError(msg) {
    const box = document.getElementById("errorBox");
    box.textContent = msg;
    box.classList.remove("hidden");
}

function hideError() {
    const box = document.getElementById("errorBox");
    box.textContent = "";
    box.classList.add("hidden");
}

function showToast(msg) {
    const toast = document.getElementById("toast");
    toast.textContent = msg;
    toast.classList.remove("hidden");
    setTimeout(() => {
        toast.classList.add("hidden");
    }, 3500);
}
