/* ============================================================
   Daily Task Observer - frontend logic

   Talks to the Flask backend with fetch(). All numbers shown on
   the dashboard and statistics pages come from the API/SQLite.
   ============================================================ */

// Base URL of the backend. Change it here if the backend runs on a
// different host or port (see README.md).
const API_BASE = "https://daily-task-observer-6.onrender.com/";

/* --------------------------- helpers --------------------------- */

const $ = (id) => document.getElementById(id);

function escapeHtml(value) {
    return String(value ?? "").replace(/[&<>"']/g, (ch) => ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#39;",
    })[ch]);
}

function pad2(number) {
    return String(number).padStart(2, "0");
}

function todayISO() {
    const now = new Date();
    return `${now.getFullYear()}-${pad2(now.getMonth() + 1)}-${pad2(now.getDate())}`;
}

function formatDate(iso) {
    const date = new Date(`${iso}T00:00:00`);
    if (Number.isNaN(date.getTime())) return iso;
    return date.toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" });
}

function formatDateParts(iso) {
    const date = new Date(`${iso}T00:00:00`);
    if (Number.isNaN(date.getTime())) return { d: iso, m: "", y: "" };
    return {
        d: pad2(date.getDate()),
        m: date.toLocaleDateString(undefined, { month: "short" }),
        y: String(date.getFullYear()),
    };
}

/** One fetch wrapper: sends JSON/FormData, parses responses, throws Errors with friendly messages. */
async function api(path, options = {}) {
    const config = { ...options };
    config.headers = { ...(options.headers || {}) };
    if (config.body && !(config.body instanceof FormData) && !config.headers["Content-Type"]) {
        config.headers["Content-Type"] = "application/json";
    }

    let response;
    try {
        response = await fetch(API_BASE + path, config);
    } catch (networkError) {
        throw new Error(`Cannot reach the backend at ${API_BASE}. Make sure it is running (python backend/app.py).`);
    }

    let data = null;
    try {
        data = await response.json();
    } catch (parseError) {
        // Non-JSON response (should not happen for API routes).
    }

    if (!response.ok) {
        throw new Error((data && data.error) || `Request failed (HTTP ${response.status}).`);
    }
    return data;
}

/* --------------------------- toasts ---------------------------- */

let toastTimer = null;

function toast(message, type = "success") {
    const el = $("toast");
    el.textContent = message;
    el.className = `toast ${type}`;
    el.hidden = false;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => {
        el.hidden = true;
    }, 3200);
}

function showFormMessage(el, message, type) {
    el.textContent = message;
    el.className = `form-message ${type}`;
    el.hidden = false;
}

function hideFormMessage(el) {
    el.hidden = true;
}

/* ------------------------ view switching ----------------------- */

const viewLoaders = {
    dashboard: () => {
        loadDashboard();
        loadTasks();
    },
    upload: prepareUploadView,
    history: loadHistory,
    calendar: loadCalendar,
    statistics: loadStatistics,
};

let currentView = "dashboard";

function showView(name) {
    currentView = name;
    document.querySelectorAll(".view").forEach((section) => {
        section.hidden = section.id !== `view-${name}`;
    });
    document.querySelectorAll(".nav-btn").forEach((button) => {
        button.classList.toggle("active", button.dataset.view === name);
    });
    (viewLoaders[name] || (() => {}))();
}

/* --------------------------- dashboard ------------------------- */

function statCard(label, value, hint) {
    return `
        <div class="stat">
            <div class="stat-label">${escapeHtml(label)}</div>
            <div class="stat-value">${escapeHtml(String(value))}</div>
            <div class="stat-hint">${escapeHtml(hint)}</div>
        </div>`;
}

function renderDashboard(data) {
    $("dashboardStats").innerHTML = [
        statCard("Total days tracked", data.total_days, "Unique days with an upload"),
        statCard("Current streak", `${data.current_streak} d`, "Consecutive days with progress"),
        statCard("Total files", data.total_files, "Progress files stored"),
        statCard(
            "Today's tasks",
            `${data.today.completed}/${data.today.total}`,
            `${data.today.percentage}% completed today`
        ),
    ].join("");

    // Recent progress list
    const list = $("recentList");
    const empty = $("recentEmpty");
    if (!data.recent.length) {
        list.innerHTML = "";
        empty.hidden = false;
    } else {
        empty.hidden = true;
        list.innerHTML = data.recent.map((item) => {
            const parts = formatDateParts(item.date);
            return `
                <li>
                    <button type="button" class="recent-item" data-open-id="${item.id}">
                        <span class="date-badge">
                            <span class="d">${escapeHtml(parts.d)}</span>
                            <span class="m">${escapeHtml(parts.m)}</span>
                        </span>
                        <span class="entry-body">
                            <h4>${escapeHtml(item.title)}</h4>
                            <span class="entry-meta">${escapeHtml(formatDate(item.date))}</span>
                            ${renderTags(item.tags)}
                        </span>
                    </button>
                </li>`;
        }).join("");
    }
}

async function loadDashboard() {
    try {
        const data = await api("/api/dashboard");
        renderDashboard(data);
    } catch (error) {
        $("dashboardStats").innerHTML = `<div class="card loading">${escapeHtml(error.message)}</div>`;
        toast(error.message, "error");
    }
}

/* ----------------------------- tasks --------------------------- */

async function loadTasks() {
    const taskDate = $("taskDate").value || todayISO();
    try {
        const data = await api(`/api/tasks?date=${encodeURIComponent(taskDate)}`);
        renderTasks(data);
    } catch (error) {
        toast(error.message, "error");
    }
}

function renderTasks(data) {
    const list = $("taskList");
    const empty = $("taskEmpty");
    const summary = $("taskSummary");

    const total = data.items.length;
    const completed = data.completed;
    const pending = data.pending;
    const percentage = total ? Math.round((completed * 100) / total) : 0;

    summary.hidden = total === 0;
    $("taskProgressBar").style.width = `${percentage}%`;
    $("taskSummaryText").textContent = `${completed} completed · ${pending} pending · ${percentage}% done`;

    if (!total) {
        list.innerHTML = "";
        empty.hidden = false;
        return;
    }
    empty.hidden = true;
    list.innerHTML = data.items.map((task) => {
        const done = task.status === "completed";
        return `
            <li class="task-item ${done ? "done" : ""}">
                <label>
                    <input type="checkbox" data-task-toggle="${task.id}" ${done ? "checked" : ""}>
                    <span class="task-title">${escapeHtml(task.title)}</span>
                </label>
                <span class="badge ${done ? "completed" : "pending"}">${done ? "Completed" : "Pending"}</span>
                <button type="button" class="icon-btn" data-task-delete="${task.id}"
                        title="Delete task" aria-label="Delete task">&times;</button>
            </li>`;
    }).join("");
}

/** Refresh the tasks card and the dashboard numbers that depend on tasks. */
function refreshTasks() {
    loadTasks();
    loadDashboard();
}

async function addTask(event) {
    event.preventDefault();
    const input = $("taskTitle");
    const title = input.value.trim();
    if (!title) {
        toast("Please enter a task title.", "error");
        return;
    }
    try {
        await api("/api/tasks", {
            method: "POST",
            body: JSON.stringify({ title, date: $("taskDate").value || todayISO() }),
        });
        input.value = "";
        refreshTasks();
    } catch (error) {
        toast(error.message, "error");
    }
}

async function toggleTask(checkbox) {
    const id = checkbox.dataset.taskToggle;
    checkbox.disabled = true;
    try {
        await api(`/api/tasks/${id}`, {
            method: "PUT",
            body: JSON.stringify({ status: checkbox.checked ? "completed" : "pending" }),
        });
        refreshTasks();
    } catch (error) {
        checkbox.checked = !checkbox.checked;
        toast(error.message, "error");
    } finally {
        checkbox.disabled = false;
    }
}

async function deleteTask(id) {
    if (!window.confirm("Delete this task? This cannot be undone.")) return;
    try {
        await api(`/api/tasks/${id}`, { method: "DELETE" });
        toast("Task deleted.");
        refreshTasks();
    } catch (error) {
        toast(error.message, "error");
    }
}

/* --------------------------- upload ---------------------------- */

function prepareUploadView() {
    if (!$("uploadDate").value) $("uploadDate").value = todayISO();
    hideFormMessage($("uploadMessage"));
}

async function uploadProgress(event) {
    event.preventDefault();
    const messageEl = $("uploadMessage");
    hideFormMessage(messageEl);

    const fileInput = $("uploadFile");
    const date = $("uploadDate").value;
    const title = $("uploadTitle").value.trim();

    // Quick checks before touching the network (the backend validates too).
    if (!fileInput.files.length) {
        showFormMessage(messageEl, "Please choose a .txt file.", "error");
        return;
    }
    if (!fileInput.files[0].name.toLowerCase().endsWith(".txt")) {
        showFormMessage(messageEl, "Only .txt files are allowed.", "error");
        return;
    }
    if (!date) {
        showFormMessage(messageEl, "Please select a date.", "error");
        return;
    }
    if (!title) {
        showFormMessage(messageEl, "Please enter a title.", "error");
        return;
    }

    const button = $("uploadBtn");
    button.disabled = true;
    button.textContent = "Saving…";

    try {
        // The form carries file + date + title + tags as multipart data.
        const formData = new FormData($("uploadForm"));
        await api("/api/progress", { method: "POST", body: formData });

        showFormMessage(messageEl, "Progress saved successfully.", "success");
        $("uploadForm").reset();
        $("uploadDate").value = todayISO();
        refreshAllData();
    } catch (error) {
        showFormMessage(messageEl, error.message, "error");
    } finally {
        button.disabled = false;
        button.textContent = "Save Progress";
    }
}

/* --------------------------- history --------------------------- */

const historyFilters = { search: "", tag: "", sort: "newest" };
let historySearchTimer = null;

function renderTags(tags) {
    const list = (tags || "").split(",").map((tag) => tag.trim()).filter(Boolean);
    if (!list.length) return "";
    return `<span class="tags">${list.map((tag) => `<span class="tag">${escapeHtml(tag)}</span>`).join("")}</span>`;
}

function historyItemHtml(item, { compact = false, showDelete = true } = {}) {
    const parts = formatDateParts(item.date);
    return `
        <li class="history-item">
            <span class="date-badge">
                <span class="d">${escapeHtml(parts.d)}</span>
                <span class="m">${escapeHtml(parts.m)}</span>
            </span>
            <span class="entry-body">
                <h4>${escapeHtml(item.title)}</h4>
                <span class="entry-meta">${escapeHtml(formatDate(item.date))} · uploaded ${escapeHtml(item.created_at || "")}</span>
                <span class="entry-meta file">File: ${escapeHtml(item.filename)}</span>
                ${renderTags(item.tags)}
                ${compact ? "" : `<span class="entry-preview">${escapeHtml(item.preview || "")}</span>`}
            </span>
            <span class="entry-actions">
                <button type="button" class="btn btn-secondary btn-sm" data-open-id="${item.id}">View</button>
                ${showDelete ? `<button type="button" class="btn btn-danger btn-sm" data-delete-id="${item.id}">Delete</button>` : ""}
            </span>
        </li>`;
}

function renderHistory(items) {
    const list = $("historyList");
    const empty = $("historyEmpty");
    if (!items.length) {
        list.innerHTML = "";
        empty.hidden = false;
        empty.textContent = historyFilters.search || historyFilters.tag
            ? "No progress entries match your search/filter."
            : "No progress entries yet.";
    } else {
        empty.hidden = true;
        list.innerHTML = items.map((item) => historyItemHtml(item)).join("");
    }
}

async function loadHistory() {
    const list = $("historyList");
    try {
        const query = new URLSearchParams({
            search: historyFilters.search,
            tag: historyFilters.tag,
            sort: historyFilters.sort,
        });
        const [data, tagData] = await Promise.all([
            api(`/api/progress?${query}`),
            api("/api/progress/tags"),
        ]);
        renderHistory(data.items);
        renderTagOptions(tagData.tags);
    } catch (error) {
        list.innerHTML = `<li class="empty">${escapeHtml(error.message)}</li>`;
        $("historyEmpty").hidden = true;
        toast(error.message, "error");
    }
}

function renderTagOptions(tags) {
    const select = $("historyTag");
    const current = select.value;
    select.innerHTML = `<option value="">All tags</option>` +
        tags.map((tag) => `<option value="${escapeHtml(tag)}">${escapeHtml(tag)}</option>`).join("");
    // Keep the user's selection if the tag still exists.
    select.value = tags.includes(current) ? current : "";
    historyFilters.tag = select.value;
}

async function deleteProgress(id, { fromModal = false } = {}) {
    if (!window.confirm("Delete this progress entry and its file? This cannot be undone.")) return false;
    try {
        await api(`/api/progress/${id}`, { method: "DELETE" });
        toast("Progress deleted.");
        if (fromModal) closeViewer();
        refreshAllData();
        return true;
    } catch (error) {
        toast(error.message, "error");
        return false;
    }
}

/* --------------------------- viewer ---------------------------- */

let viewerProgressId = null;

async function openViewer(id) {
    try {
        const item = await api(`/api/progress/${id}`);
        viewerProgressId = item.id;
        $("viewerDate").value = item.date;
        $("viewerTitle").value = item.title;
        $("viewerTags").value = item.tags;
        $("viewerContent").value = item.content;
        $("viewerMeta").textContent =
            `File: ${item.filename} · uploaded ${item.created_at} · last updated ${item.updated_at}`;
        hideFormMessage($("viewerMessage"));
        $("viewerModal").hidden = false;
    } catch (error) {
        toast(error.message, "error");
    }
}

function closeViewer() {
    $("viewerModal").hidden = true;
    viewerProgressId = null;
}

async function saveViewerChanges() {
    if (viewerProgressId === null) return;
    const messageEl = $("viewerMessage");
    hideFormMessage(messageEl);

    const button = $("viewerSave");
    button.disabled = true;
    button.textContent = "Saving…";

    try {
        await api(`/api/progress/${viewerProgressId}`, {
            method: "PUT",
            body: JSON.stringify({
                date: $("viewerDate").value,
                title: $("viewerTitle").value.trim(),
                tags: $("viewerTags").value,
                content: $("viewerContent").value,
            }),
        });
        toast("Progress updated.");
        closeViewer();
        refreshAllData();
    } catch (error) {
        showFormMessage(messageEl, error.message, "error");
    } finally {
        button.disabled = false;
        button.textContent = "Save Changes";
    }
}

/* --------------------------- calendar -------------------------- */

let calendarYear = new Date().getFullYear();
let calendarMonth = new Date().getMonth(); // 0-based
let calendarCounts = new Map();            // "YYYY-MM-DD" -> upload count
let selectedCalendarDate = null;

async function loadCalendar() {
    try {
        const data = await api("/api/calendar");
        calendarCounts = new Map(data.days.map((day) => [day.date, day.count]));
        renderCalendar();
        if (selectedCalendarDate) loadCalendarDay(selectedCalendarDate, false);
    } catch (error) {
        $("calDays").innerHTML = `<div class="loading">${escapeHtml(error.message)}</div>`;
        toast(error.message, "error");
    }
}

function renderCalendar() {
    $("calTitle").textContent = new Date(calendarYear, calendarMonth, 1)
        .toLocaleDateString(undefined, { month: "long", year: "numeric" });

    const firstWeekday = new Date(calendarYear, calendarMonth, 1).getDay(); // 0 = Sunday
    const daysInMonth = new Date(calendarYear, calendarMonth + 1, 0).getDate();
    const today = todayISO();

    let html = "";
    for (let i = 0; i < firstWeekday; i += 1) {
        html += `<span class="cal-cell blank"></span>`;
    }
    for (let day = 1; day <= daysInMonth; day += 1) {
        const iso = `${calendarYear}-${pad2(calendarMonth + 1)}-${pad2(day)}`;
        const count = calendarCounts.get(iso) || 0;
        const classes = ["cal-cell"];
        if (count) classes.push("has-progress");
        if (iso === today) classes.push("is-today");
        if (iso === selectedCalendarDate) classes.push("is-selected");
        html += `
            <button type="button" class="${classes.join(" ")}" data-cal-date="${iso}"
                    title="${count} upload(s) on ${iso}">
                <span>${day}</span>${count ? `<span class="dot"></span>` : ""}
            </button>`;
    }
    $("calDays").innerHTML = html;
}

async function loadCalendarDay(iso, render = true) {
    selectedCalendarDate = iso;
    if (render) renderCalendar();

    const parts = formatDateParts(iso);
    $("calDayTitle").textContent = `Progress on ${formatDate(iso)}`;
    $("calDayList").innerHTML = "";
    $("calDayEmpty").hidden = false;
    $("calDayEmpty").textContent = "Loading…";

    try {
        const data = await api(`/api/progress?date=${encodeURIComponent(iso)}&sort=newest`);
        $("calDayEmpty").hidden = data.items.length > 0;
        $("calDayEmpty").textContent = "No progress was uploaded on this day.";
        $("calDayList").innerHTML = data.items.map((item) => historyItemHtml(item, { compact: true })).join("");
    } catch (error) {
        $("calDayEmpty").hidden = false;
        $("calDayEmpty").textContent = error.message;
    }
}

function changeMonth(delta) {
    const next = new Date(calendarYear, calendarMonth + delta, 1);
    calendarYear = next.getFullYear();
    calendarMonth = next.getMonth();
    renderCalendar();
}

/* -------------------------- statistics ------------------------- */

async function loadStatistics() {
    const grid = $("statsGrid");
    try {
        const s = await api("/api/statistics");
        grid.innerHTML = [
            statCard("Current streak", `${s.current_streak} d`, "Consecutive days with progress"),
            statCard("Longest streak", `${s.longest_streak} d`, "Best run of consecutive days"),
            statCard("Total uploads", s.total_uploads, `${s.total_days} unique days tracked`),
            statCard("Weekly progress", `${s.weekly_days} d`, `${s.weekly_uploads} upload(s) since Monday`),
            statCard("Monthly progress", `${s.monthly_days} d`, `${s.monthly_uploads} upload(s) this month`),
            statCard("Task completion", `${s.completion_rate}%`, `${s.completed_tasks} of ${s.total_tasks} tasks done`),
            statCard("Tasks done this week", s.completed_this_week, "Since Monday"),
            statCard("Tasks done this month", s.completed_this_month, "Current month"),
        ].join("");
    } catch (error) {
        grid.innerHTML = `<div class="card loading">${escapeHtml(error.message)}</div>`;
        toast(error.message, "error");
    }
}

/* ------------------------ refresh all -------------------------- */

/** Reload every section after data changes so nothing shows stale numbers. */
function refreshAllData() {
    loadDashboard();
    loadTasks();
    if (currentView === "history" || $("historyList").children.length) loadHistory();
    loadCalendar();
    if (currentView === "statistics" || $("statsGrid").querySelector(".stat")) loadStatistics();
}

/* --------------------------- wiring ---------------------------- */

function init() {
    // Navigation
    document.querySelectorAll(".nav-btn").forEach((button) => {
        button.addEventListener("click", () => showView(button.dataset.view));
    });
    document.querySelectorAll("[data-goto]").forEach((button) => {
        button.addEventListener("click", () => showView(button.dataset.goto));
    });

    // Tasks
    $("taskForm").addEventListener("submit", addTask);
    $("taskDate").addEventListener("change", loadTasks);
    $("taskDate").value = todayISO();
    $("taskList").addEventListener("change", (event) => {
        const checkbox = event.target.closest("[data-task-toggle]");
        if (checkbox) toggleTask(checkbox);
    });
    $("taskList").addEventListener("click", (event) => {
        const button = event.target.closest("[data-task-delete]");
        if (button) deleteTask(button.dataset.taskDelete);
    });

    // Upload
    $("uploadForm").addEventListener("submit", uploadProgress);
    $("uploadDate").value = todayISO();

    // Opening entries from dashboard / history / calendar
    document.addEventListener("click", (event) => {
        const openButton = event.target.closest("[data-open-id]");
        if (openButton) {
            openViewer(openButton.dataset.openId);
            return;
        }
        const deleteButton = event.target.closest("[data-delete-id]");
        if (deleteButton) deleteProgress(deleteButton.dataset.deleteId);
    });

    // History controls
    $("historySearch").addEventListener("input", (event) => {
        clearTimeout(historySearchTimer);
        historySearchTimer = setTimeout(() => {
            historyFilters.search = event.target.value.trim();
            loadHistory();
        }, 300);
    });
    $("historyTag").addEventListener("change", (event) => {
        historyFilters.tag = event.target.value;
        loadHistory();
    });
    $("historySort").addEventListener("change", (event) => {
        historyFilters.sort = event.target.value;
        loadHistory();
    });
    $("historyRefresh").addEventListener("click", loadHistory);

    // Calendar
    $("calPrev").addEventListener("click", () => changeMonth(-1));
    $("calNext").addEventListener("click", () => changeMonth(1));
    $("calToday").addEventListener("click", () => {
        const now = new Date();
        calendarYear = now.getFullYear();
        calendarMonth = now.getMonth();
        renderCalendar();
        loadCalendarDay(todayISO());
    });
    $("calDays").addEventListener("click", (event) => {
        const cell = event.target.closest("[data-cal-date]");
        if (cell) loadCalendarDay(cell.dataset.calDate);
    });

    // Viewer modal
    $("viewerSave").addEventListener("click", saveViewerChanges);
    $("viewerDelete").addEventListener("click", () => {
        if (viewerProgressId !== null) deleteProgress(viewerProgressId, { fromModal: true });
    });
    $("viewerClose").addEventListener("click", closeViewer);
    $("viewerCancel").addEventListener("click", closeViewer);
    $("viewerModal").addEventListener("click", (event) => {
        if (event.target === $("viewerModal")) closeViewer();
    });
    document.addEventListener("keydown", (event) => {
        if (event.key === "Escape" && !$("viewerModal").hidden) closeViewer();
    });

    // First load
    showView("dashboard");
}

document.addEventListener("DOMContentLoaded", init);
