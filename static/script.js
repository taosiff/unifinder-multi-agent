/**
 * static/script.js - UniFinder AI Client Controller
 * Multi-Agent Subgraphs • C-RAG • Persistent SqliteSaver Memory • Live Streaming • HITL
 */

// Global State (1-to-1 Chat Thread & Session ID)
let currentThreadId = localStorage.getItem("unifinder_thread_id") || `student_${Math.random().toString(36).substring(2, 9)}`;
let currentSessionId = currentThreadId;
let selectedDegree = "MSc";
let activeProvider = localStorage.getItem("unifinder_llm_provider") || "gemini";
let storedApiKey = localStorage.getItem("unifinder_api_key") || "";
let storedLangsmithKey = localStorage.getItem("unifinder_langsmith_key") || "";
let autoWipeEnabled = localStorage.getItem("unifinder_auto_wipe") === "true";

localStorage.setItem("unifinder_thread_id", currentThreadId);
localStorage.setItem("unifinder_session_id", currentSessionId);

// Initialize on DOM load
document.addEventListener("DOMContentLoaded", () => {
    checkSystemStatus();
    updateNavKeyStatus();
    checkLangsmithStatus();
    loadThreadsList();
    loadThreadMessages(currentThreadId);
    loadSessionDocs();
    loadMatrixTable();
    loadShortlist();
    loadOpportunities();
    recalculateROI();
    startLiveHubClock();
    const countryEl = document.getElementById("countryInput");
    if (countryEl) countryEl.addEventListener("change", updateLiveHubClock);
    const autoWipeEl = document.getElementById("autoWipeOnExit");
    if (autoWipeEl) autoWipeEl.checked = autoWipeEnabled;

    // Start sidebar collapsed on mobile/tablet, open on desktop
    const sidebar = document.getElementById("threadSidebar");
    if (sidebar && window.innerWidth <= 960) {
        sidebar.classList.add("collapsed");
    }
});

function autoResizeTextarea(el) {
    if (!el) return;
    el.style.height = "auto";
    el.style.height = Math.min(el.scrollHeight, 160) + "px";
}

function toggleAutoWipe(enabled) {
    autoWipeEnabled = !!enabled;
    localStorage.setItem("unifinder_auto_wipe", autoWipeEnabled ? "true" : "false");
    showToast(autoWipeEnabled ? "Auto-wipe on tab exit enabled." : "Auto-wipe on tab exit disabled.");
}

async function endAndWipeSession() {
    try {
        await fetch("/api/session/end", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ thread_id: currentThreadId, session_id: currentSessionId })
        });
    } catch (e) {
        console.error("Session wipe error:", e);
    }

    const feedback = document.getElementById("uploadFeedback");
    if (feedback) {
        feedback.textContent = "";
        feedback.classList.add("hidden");
    }
    createNewThread();
    loadShortlist();
    showToast("🧹 Session ended! Personal data, CVs & thread wiped from database.");
}

window.addEventListener("pagehide", () => {
    if (autoWipeEnabled && currentThreadId) {
        const payload = JSON.stringify({ thread_id: currentThreadId, session_id: currentSessionId });
        navigator.sendBeacon("/api/session/end", new Blob([payload], { type: "application/json" }));
    }
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

function toggleMobileProfile() {
    const card = document.getElementById("profileFilterCard");
    const arrow = document.getElementById("mobileProfileArrow");
    if (card) {
        const collapsed = card.classList.toggle("mobile-collapsed");
        if (arrow) arrow.textContent = collapsed ? "Show ▾" : "Hide ▴";
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
            <span class="thread-title-text" title="${t.title}">${t.title}</span>
            <button class="del-thread-btn" onclick="event.stopPropagation(); deleteThread('${t.thread_id}')" title="Delete conversation">✕</button>
        </div>
    `).join("");
}

function renderWelcomeChat() {
    const feed = document.getElementById("chatFeed");
    if (!feed) return;
    feed.innerHTML = `
        <div class="chat-welcome" id="chatWelcome">
            <div class="chat-welcome-icon">
                <svg class="ui-icon ui-icon-lg" viewBox="0 0 24 24"><path d="M22 10v6M2 10l10-5 10 5-10 5z"/><path d="M6 12v5c3 3 9 3 12 0v-5"/></svg>
            </div>
            <h3>Ask anything about your study abroad journey</h3>
            <p>Upload your CV on the left or type a question below. You can ask follow-up questions anytime — your session memory is saved automatically.</p>
            <div class="starter-chips-grid">
                <button class="starter-chip" onclick="sendStarterPrompt('Find tuition-free MSc AI & Computer Science in Germany with PR outlook')">Tuition-free MSc in Germany</button>
                <button class="starter-chip" onclick="sendStarterPrompt('Best MSc Data Science in Canada with 3-year PGWP and job market')">Data Science in Canada + PR</button>
                <button class="starter-chip" onclick="sendStarterPrompt('Compare living costs, scholarships & sponsored visas in UK vs Netherlands')">UK vs Netherlands Comparison</button>
            </div>
        </div>
    `;
}

function sendStarterPrompt(promptText) {
    const input = document.getElementById("userQuery");
    if (input) {
        input.value = promptText;
        runFinder();
    }
}

const HUB_TIMEZONES = {
    "Germany": { city: "Berlin", tz: "Europe/Berlin" },
    "United States": { city: "Boston", tz: "America/New_York" },
    "Canada": { city: "Toronto", tz: "America/Toronto" },
    "United Kingdom": { city: "London", tz: "Europe/London" },
    "Australia": { city: "Melbourne", tz: "Australia/Melbourne" },
    "Netherlands": { city: "Amsterdam", tz: "Europe/Amsterdam" },
    "Sweden": { city: "Stockholm", tz: "Europe/Stockholm" },
    "Singapore": { city: "Singapore", tz: "Asia/Singapore" },
    "France": { city: "Paris", tz: "Europe/Paris" }
};

function updateLiveHubClock() {
    const el = document.getElementById("liveHubClock");
    if (!el) return;
    const country = document.getElementById("countryInput")?.value || "";
    const hub = HUB_TIMEZONES[country] || { city: "Global", tz: "UTC" };
    try {
        const nowStr = new Intl.DateTimeFormat("en-US", {
            timeZone: hub.tz, hour: "2-digit", minute: "2-digit", hour12: false
        }).format(new Date());
        el.textContent = `${hub.city} ${nowStr}`;
    } catch {
        el.textContent = `${hub.city} Live`;
    }
}

function startLiveHubClock() {
    updateLiveHubClock();
    setInterval(updateLiveHubClock, 15000);
}

function appendChatMessage(role, content) {
    const feed = document.getElementById("chatFeed");
    if (!feed) return null;
    const welcome = document.getElementById("chatWelcome");
    if (welcome) welcome.remove();

    const row = document.createElement("div");
    row.className = `chat-msg-row ${role}`;

    if (role === "user") {
        const bubble = document.createElement("div");
        bubble.className = "chat-bubble-user";
        bubble.textContent = content;
        row.appendChild(bubble);
        feed.appendChild(row);
        feed.scrollTop = feed.scrollHeight;
        return bubble;
    } else {
        const bubble = document.createElement("div");
        bubble.className = "chat-bubble-assistant";
        const body = document.createElement("div");
        body.className = "markdown-body";
        body.innerHTML = (typeof marked !== "undefined" && content) ? marked.parse(content) : (content || `<span class="streaming-cursor"></span>`);
        bubble.appendChild(body);

        const actions = document.createElement("div");
        actions.className = "chat-bubble-actions";
        actions.innerHTML = `
            <button class="chat-mini-btn" onclick="copyBubbleText(this)">Copy</button>
            <button class="chat-mini-btn" onclick="printDossier()">Print / PDF</button>
        `;
        bubble.appendChild(actions);
        row.appendChild(bubble);
        feed.appendChild(row);
        feed.scrollTop = feed.scrollHeight;
        return body;
    }
}

function copyBubbleText(btn) {
    const bubble = btn.closest(".chat-bubble-assistant");
    const text = bubble?.querySelector(".markdown-body")?.innerText || "";
    navigator.clipboard.writeText(text).then(() => showToast("Copied to clipboard!"));
}

async function loadThreadMessages(threadId) {
    const threadDisplay = document.getElementById("threadDisplay");
    if (threadDisplay) threadDisplay.textContent = threadId;
    try {
        const res = await fetch(`/api/threads/${encodeURIComponent(threadId)}/messages`);
        const data = await res.json();
        const feed = document.getElementById("chatFeed");
        if (!feed) return;
        if (data.success && data.messages && data.messages.length > 0) {
            feed.innerHTML = "";
            data.messages.forEach(m => appendChatMessage(m.role, m.content));
        } else {
            renderWelcomeChat();
        }
    } catch (e) {
        console.error("Failed to load messages:", e);
    }
}

function handleChatKeydown(event) {
    if (event.key === "Enter" && !event.shiftKey) {
        event.preventDefault();
        runFinder();
    }
}

function createNewThread() {
    currentThreadId = `student_${Math.random().toString(36).substring(2, 9)}`;
    currentSessionId = currentThreadId;
    localStorage.setItem("unifinder_thread_id", currentThreadId);
    localStorage.setItem("unifinder_session_id", currentSessionId);

    const queryEl = document.getElementById("userQuery");
    if (queryEl) queryEl.value = "";
    document.getElementById("metricsBanner")?.classList.add("hidden");
    document.getElementById("hitlBanner")?.classList.add("hidden");
    document.getElementById("thinkingBubble")?.classList.add("hidden");
    const threadDisplay = document.getElementById("threadDisplay");
    if (threadDisplay) threadDisplay.textContent = currentThreadId;
    renderWelcomeChat();

    loadThreadsList();
    loadSessionDocs();
    showToast("Started new chat session!");
}

function switchThread(threadId, title) {
    currentThreadId = threadId;
    currentSessionId = threadId;
    localStorage.setItem("unifinder_thread_id", currentThreadId);
    localStorage.setItem("unifinder_session_id", currentSessionId);

    loadThreadsList();
    loadThreadMessages(threadId);
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

    const titleMap = {
        "counselor": "UniFinder Counselor",
        "opportunities": "Live Scholarships & Grants",
        "matrix": "Universities Explorer",
        "pr-visa": "PR & Post-Study Visas",
        "roi": "Career ROI Forecaster",
        "sop": "SOP Reviewer",
        "shortlist": "Saved Wishlist"
    };
    const titleEl = document.getElementById("activeViewTitle");
    if (titleEl && titleMap[tabName]) titleEl.textContent = titleMap[tabName];

    if (window.innerWidth <= 960) {
        const sidebar = document.getElementById("threadSidebar");
        const backdrop = document.getElementById("sidebarBackdrop");
        if (sidebar && !sidebar.classList.contains("collapsed")) {
            sidebar.classList.add("collapsed");
            if (backdrop) backdrop.classList.remove("active");
        }
    }
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
    const el = document.getElementById("budgetValue");
    if (!el) return;
    if (val === "" || val === null || val === undefined) {
        el.textContent = "Any";
    } else {
        el.textContent = `$${parseInt(val).toLocaleString()} USD`;
    }
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
        showError("Please enter your study goal, preferred universities, or follow-up question.");
        return;
    }

    const findBtn = document.getElementById("findBtn");
    const thinkingBubble = document.getElementById("thinkingBubble");
    const thinkingText = document.getElementById("thinkingText");

    findBtn.disabled = true;
    queryInput.value = "";
    appendChatMessage("user", query);

    if (thinkingBubble) {
        thinkingBubble.classList.remove("hidden");
        if (thinkingText) thinkingText.textContent = "Analyzing your profile & goals...";
    }

    const rawGpa = document.getElementById("gpaInput").value.trim();
    const rawIelts = document.getElementById("ieltsInput").value.trim();
    const rawBudget = document.getElementById("budgetInput").value.trim();

    const payload = {
        message: query,
        thread_id: currentThreadId,
        session_id: currentSessionId,
        degree_level: selectedDegree,
        subject: document.getElementById("subjectInput").value.trim() || "Computer Science",
        country: document.getElementById("countryInput").value,
        user_gpa: rawGpa ? parseFloat(rawGpa) : null,
        user_ielts: rawIelts ? parseFloat(rawIelts) : null,
        budget_usd: rawBudget ? parseInt(rawBudget) : null,
        api_key: storedApiKey || null,
        llm_provider: activeProvider
    };

    await executeStreamingSearch(payload);

    if (thinkingBubble) thinkingBubble.classList.add("hidden");
    findBtn.disabled = false;
    loadThreadsList();
}

async function executeStreamingSearch(payload) {
    const threadDisplay = document.getElementById("threadDisplay");
    const thinkingBubble = document.getElementById("thinkingBubble");
    const thinkingText = document.getElementById("thinkingText");
    const feed = document.getElementById("chatFeed");

    if (threadDisplay) threadDisplay.textContent = payload.thread_id;

    let assistantBody = null;
    let accumulatedMarkdown = "";

    try {
        const response = await fetch("/api/chat/stream", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });

        if (!response.ok) throw new Error("Connection failed.");

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";
        let receivedComplete = false;

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split("\n\n");
            buffer = lines.pop();

            for (const line of lines) {
                if (line.startsWith("data: ")) {
                    const eventData = JSON.parse(line.substring(6));

                    if (eventData.type === "phase") {
                        if (thinkingText) thinkingText.textContent = eventData.text;
                    } else if (eventData.type === "token") {
                        if (thinkingBubble) thinkingBubble.classList.add("hidden");
                        if (!assistantBody) {
                            assistantBody = appendChatMessage("assistant", "");
                        }
                        accumulatedMarkdown += eventData.content;
                        if (typeof marked !== "undefined") {
                            assistantBody.innerHTML = marked.parse(accumulatedMarkdown) + `<span class="streaming-cursor"></span>`;
                        } else {
                            assistantBody.innerText = accumulatedMarkdown;
                        }
                        if (feed) feed.scrollTop = feed.scrollHeight;
                    } else if (eventData.type === "error") {
                        if (thinkingBubble) thinkingBubble.classList.add("hidden");
                        showError("Agent error: " + (eventData.message || "Unexpected server error."));
                        return;
                    } else if (eventData.type === "complete") {
                        receivedComplete = true;
                        if (thinkingBubble) thinkingBubble.classList.add("hidden");
                        displayCompletedMetadata(eventData.data);
                        if (assistantBody && typeof marked !== "undefined") {
                            assistantBody.innerHTML = marked.parse(accumulatedMarkdown);
                        }
                    }
                }
            }
        }

        if (!receivedComplete && !accumulatedMarkdown) {
            if (thinkingBubble) thinkingBubble.classList.add("hidden");
            showError("Connection ended before results arrived. Please try again.");
        }
    } catch (e) {
        if (thinkingBubble) thinkingBubble.classList.add("hidden");
        showError("Chat error: " + e.message);
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
    const status = (document.getElementById("oppStatusFilter")?.value || "").toLowerCase();

    const filtered = cachedScholarships.filter(s => {
        const matchDest = !dest || s.destination.toLowerCase().includes(dest);
        const matchDeg = !deg || s.degree_levels.includes(deg);
        const matchFund = !fund || s.funding_type.toLowerCase().includes(fund);
        const matchStatus = !status || (s.record_status || "").toLowerCase().includes(status);
        return matchDest && matchDeg && matchFund && matchStatus;
    });

    renderOpportunities(filtered);
}

function renderOpportunities(opps) {
    const container = document.getElementById("oppsGrid");
    if (!opps || opps.length === 0) {
        container.innerHTML = `<div class="loading-cell">No scholarships match the selected filter.</div>`;
        return;
    }

    container.innerHTML = opps.map(o => {
        const recStatus = o.record_status || "Verified Open";
        const isVerified = recStatus.toLowerCase().includes("verified");
        const statusBadge = isVerified
            ? `<span class="opp-funding-tag" style="background:#D1FAE5; color:#065F46; border-color:#A7F3D0;">✅ Verified Open</span>`
            : `<span class="purple-pill">🆕 Newly Discovered</span>`;
        const sourceLine = o.source_name ? `<div class="opp-detail-row" style="font-size:0.75rem; color:var(--text-muted); margin-top:0.4rem;">🔗 Source: <strong>${o.source_name}</strong> (${o.attribution || "Original posting"})</div>` : "";

        return `
        <div class="opp-card">
            <div>
                <div class="opp-card-header">
                    <h4>${o.title}</h4>
                    <div style="display:flex; flex-direction:column; gap:0.35rem; align-items:flex-end;">
                        ${statusBadge}
                        <span class="opp-funding-tag">${o.funding_type}</span>
                    </div>
                </div>
                <div class="opp-detail-row"><strong>📍 Destination:</strong> ${o.destination}</div>
                <div class="opp-detail-row"><strong>🎓 Degrees:</strong> ${o.degree_levels.join(", ")}</div>
                <div class="opp-detail-row"><strong>💰 Coverage:</strong> ${o.coverage}</div>
                <div class="opp-detail-row"><strong>📅 Deadline:</strong> <span style="color:#C92A2A; font-weight:700;">${o.deadline}</span></div>
                <div class="opp-detail-row"><strong>📋 Eligibility:</strong> ${o.eligibility}</div>
                ${sourceLine}
            </div>
            <a href="${o.official_url}" target="_blank" rel="noopener" class="opp-apply-btn">
                View Original Posting ↗
            </a>
        </div>
        `;
    }).join("");
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

// ==========================================
// Univs.com Live Global Catalogue Search
// ==========================================
async function searchUnivsLive() {
    const query = document.getElementById("univsQueryInput")?.value || "Computer Science";
    const country = document.getElementById("univsCountryInput")?.value || "";
    const degree = document.getElementById("univsDegreeSelect")?.value || "MSc";
    const container = document.getElementById("univsResultsContainer");

    if (!container) return;
    container.innerHTML = `<div style="color:var(--text-muted); padding:0.5rem;">⏳ Searching Univs.com public catalogue...</div>`;

    try {
        const params = new URLSearchParams({ q: query, degree: degree });
        if (country.trim()) params.set("country", country.trim());

        const res = await fetch(`/api/univs/programs?${params.toString()}`);
        const data = await res.json();

        if (data.success && data.programs && data.programs.length > 0) {
            container.innerHTML = data.programs.map(p => `
                <div class="opp-card">
                    <div>
                        <div class="opp-card-header">
                            <h4>${p.program_name}</h4>
                            ${p.scholarship_available ? '<span class="opp-funding-tag">Scholarship Listed</span>' : '<span class="purple-pill">' + p.degree + '</span>'}
                        </div>
                        <div class="opp-detail-row">🏛️ <strong>${p.university_name}</strong></div>
                        <div class="opp-detail-row">📍 ${p.city ? p.city + ', ' : ''}${p.country}</div>
                        <div class="opp-detail-row">⏱️ Duration: ${p.duration}</div>
                    </div>
                    <a href="${p.url}" target="_blank" class="opp-apply-btn">View on Univs.com ↗</a>
                </div>
            `).join("");
        } else {
            container.innerHTML = `<div style="color:var(--text-muted); font-size:0.88rem;">No matching programs found on Univs.com for "${query}" (${degree}). Try broadening your search.</div>`;
        }
    } catch (e) {
        container.innerHTML = `<div class="alert-box error">Error fetching Univs.com catalogue: ${e.message}</div>`;
    }
}

// ==========================================
// Official University Website Scraper Subgraph
// ==========================================
async function scrapeOfficialUniversity() {
    const uniName = document.getElementById("scrapeUniName")?.value.trim() || "";
    const uniUrl = document.getElementById("scrapeUniUrl")?.value.trim() || "";
    const subject = document.getElementById("scrapeSubject")?.value.trim() || "Computer Science";
    const container = document.getElementById("scrapeResultsContainer");

    if (!container) return;
    if (!uniName && !uniUrl) {
        container.innerHTML = `<div class="alert-box error">Please enter a university name or official website URL.</div>`;
        return;
    }

    container.innerHTML = `<div style="color:var(--text-muted); padding:0.5rem;">⏳ Running Official Website Admissions Scraper Subgraph (crawling main site &amp; admissions subpages)...</div>`;

    try {
        const res = await fetch("/api/scrape-university", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                university_name: uniName,
                official_url: uniUrl,
                degree_level: selectedDegree || "MSc",
                subject: subject
            })
        });
        const payload = await res.json();
        if (!payload.success || !payload.data) {
            container.innerHTML = `<div class="alert-box error">Scrape failed: ${payload.error || "Unknown error"}</div>`;
            return;
        }

        const d = payload.data;
        const listItems = (arr) => (arr && arr.length ? arr.map(x => `<li>${x}</li>`).join("") : "<li>Not specified on scraped pages</li>");

        container.innerHTML = `
            <div class="opps-grid">
                <div class="opp-card">
                    <div>
                        <div class="opp-card-header">
                            <h4>${d.university_name || uniName}</h4>
                            <span class="opp-funding-tag">${(d.pages_scraped || []).length} Pages Scraped</span>
                        </div>
                        <div class="opp-detail-row">🌐 <a href="${d.official_url}" target="_blank">${d.official_url}</a></div>
                        <div class="opp-detail-row"><strong>💰 Tuition Extracted:</strong><ul style="margin:0.3rem 0 0 1.2rem;">${listItems(d.tuition)}</ul></div>
                        <div class="opp-detail-row"><strong>🗣️ IELTS / TOEFL Requirements:</strong><ul style="margin:0.3rem 0 0 1.2rem;">${listItems(d.english_requirements)}</ul></div>
                        <div class="opp-detail-row"><strong>📊 GPA Requirements:</strong><ul style="margin:0.3rem 0 0 1.2rem;">${listItems(d.gpa_requirements)}</ul></div>
                    </div>
                </div>
                <div class="opp-card">
                    <div>
                        <div class="opp-card-header">
                            <h4>Deadlines, Intakes &amp; Programs</h4>
                            <span class="purple-pill">Official Site Extract</span>
                        </div>
                        <div class="opp-detail-row"><strong>📅 Intakes:</strong><ul style="margin:0.3rem 0 0 1.2rem;">${listItems(d.intakes)}</ul></div>
                        <div class="opp-detail-row"><strong>⏰ Deadlines:</strong><ul style="margin:0.3rem 0 0 1.2rem;">${listItems(d.deadlines)}</ul></div>
                        <div class="opp-detail-row"><strong>🎓 Scraped Programs:</strong><ul style="margin:0.3rem 0 0 1.2rem;">${listItems(d.programs)}</ul></div>
                    </div>
                </div>
            </div>
        `;
    } catch (e) {
        container.innerHTML = `<div class="alert-box error">Error running scraper: ${e.message}</div>`;
    }
}
