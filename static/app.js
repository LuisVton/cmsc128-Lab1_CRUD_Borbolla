let tasks = [];
let editingId = null;
let calendarDate = new Date();

const $ = (id) => document.getElementById(id);

async function loadTasks() {
    const response = await fetch("/api/tasks");
    tasks = await response.json();
    renderTasks();
    updateStats();
}

function formatDate(value) {
    const date = new Date(value);
    return date.toLocaleString([], { dateStyle: "medium", timeStyle: "short" });
}

function priorityClass(priority) {
    return priority.toLowerCase();
}

function renderTasks() {
    const search = $("searchInput").value.toLowerCase().trim();
    const tag = $("tagFilter").value;
    const priority = $("priorityFilter").value;
    const sort = $("sortSelect").value;

    let visible = tasks.filter(t =>
        t.title.toLowerCase().includes(search) &&
        (!tag || t.tag === tag) &&
        (!priority || t.priority === priority)
    );

    if (sort === "priority") {
        const order = { High: 1, Med: 2, Low: 3 };
        visible.sort((a,b) => order[a.priority] - order[b.priority]);
    } else if (sort === "tag") {
        visible.sort((a,b) => a.tag.localeCompare(b.tag));
    } else if (sort === "created_at") {
        visible.sort((a,b) => b.created_at.localeCompare(a.created_at));
    } else {
        visible.sort((a,b) => a.due_date.localeCompare(b.due_date));
    }

    $("taskList").innerHTML = visible.map(t => `
        <article class="task ${t.completed ? "done" : ""}">
            <button class="check ${t.completed ? "done" : ""}" onclick="toggleTask(${t.id})">
                ${t.completed ? "✓" : ""}
            </button>
            <div>
                <div class="task-title">${escapeHtml(t.title)}</div>
                <div class="task-meta">
                    <span>${formatDate(t.due_date)}</span>
                    <span class="badge ${priorityClass(t.priority)}">${t.priority}</span>
                    <span class="badge">${t.tag}</span>
                </div>
            </div>
            <div class="task-actions">
                <button class="small-btn" onclick="openEdit(${t.id})">Edit</button>
                <button class="small-btn danger" onclick="deleteTask(${t.id})">Delete</button>
            </div>
        </article>
    `).join("");

    $("emptyState").classList.toggle("hidden", visible.length !== 0);
}

function updateStats() {
    $("totalCount").textContent = tasks.length;
    $("activeCount").textContent = tasks.filter(t => !t.completed).length;
    $("doneCount").textContent = tasks.filter(t => t.completed).length;
}

function escapeHtml(text) {
    const div = document.createElement("div");
    div.textContent = text;
    return div.innerHTML;
}

function openAdd() {
    editingId = null;
    $("modalTitle").textContent = "Add Task";
    $("taskForm").reset();
    $("priority").value = "Med";
    $("tag").value = "School";
    $("taskId").value = "";
    $("modal").classList.remove("hidden");
    $("title").focus();
}

function openEdit(id) {
    const task = tasks.find(t => t.id === id);
    if (!task) return;
    editingId = id;
    $("modalTitle").textContent = "Edit Task";
    $("title").value = task.title;
    $("dueDate").value = task.due_date;
    $("priority").value = task.priority;
    $("tag").value = task.tag;
    $("modal").classList.remove("hidden");
}

function closeModal() {
    $("modal").classList.add("hidden");
}

async function saveTask(event) {
    event.preventDefault();

    const data = {
        title: $("title").value,
        due_date: $("dueDate").value,
        priority: $("priority").value,
        tag: $("tag").value
    };

    const url = editingId ? `/api/tasks/${editingId}` : "/api/tasks";
    const method = editingId ? "PUT" : "POST";

    const response = await fetch(url, {
        method,
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data)
    });

    const result = await response.json();
    if (!response.ok) {
        showToast(result.error || "Something went wrong.");
        return;
    }

    closeModal();
    showToast(editingId ? "Task updated." : "Task added.");
    await loadTasks();
}

async function toggleTask(id) {
    const response = await fetch(`/api/tasks/${id}/complete`, { method: "PATCH" });
    if (response.ok) {
        showToast("Task status updated.");
        await loadTasks();
    }
}

let undoTimer = null;

async function deleteTask(id) {
    if (!confirm("Are you sure you want to delete this task?")) {
        return;
    }

    const response = await fetch(`/api/tasks/${id}`, {
        method: "DELETE"
    });

    if (!response.ok) {
        showToast("Failed to delete task");
        return;
    }

    await loadTasks();

    showUndoToast(id);
}

function showUndoToast(taskId) {
    const toast = document.getElementById("toast");

    if (undoTimer) {
        clearTimeout(undoTimer);
    }

    toast.innerHTML = `
        <span>Task deleted</span>
        <button id="undoDeleteBtn">Undo</button>
    `;

    toast.classList.add("show");

    const undoButton = document.getElementById("undoDeleteBtn");

    undoButton.addEventListener("click", async () => {
        clearTimeout(undoTimer);

        const response = await fetch(
            `/api/tasks/${taskId}/undo`,
            {
                method: "POST"
            }
        );

        if (response.ok) {
            toast.classList.remove("show");
            await loadTasks();
            showToast("Task restored");
        } else {
            toast.classList.remove("show");
            showToast("Undo period expired");
        }
    });

    undoTimer = setTimeout(async () => {
        toast.classList.remove("show");

        await fetch(
            `/api/tasks/${taskId}/finalize`,
            {
                method: "DELETE"
            }
        );

    }, 5000);
}

function showToast(message) {
    const toast = $("toast");
    toast.textContent = message;
    toast.classList.add("show");
    setTimeout(() => toast.classList.remove("show"), 2200);
}

function openCalendar() {
    $("calendarModal").classList.remove("hidden");
    renderCalendar();
}

function renderCalendar() {
    const year = calendarDate.getFullYear();
    const month = calendarDate.getMonth();
    $("monthLabel").textContent = calendarDate.toLocaleDateString([], { month: "long", year: "numeric" });

    const firstDay = new Date(year, month, 1);
    const lastDay = new Date(year, month + 1, 0);
    const startWeekday = firstDay.getDay();
    const totalDays = lastDay.getDate();

    const headers = ["Sun","Mon","Tue","Wed","Thu","Fri","Sat"]
        .map(d => `<div class="day-name">${d}</div>`).join("");

    let html = headers;
    for (let i = 0; i < startWeekday; i++) {
        html += `<div class="day other"></div>`;
    }

    for (let day = 1; day <= totalDays; day++) {
        const dateKey = `${year}-${String(month+1).padStart(2,"0")}-${String(day).padStart(2,"0")}`;
        const dayTasks = tasks.filter(t => t.due_date.startsWith(dateKey));
        const today = new Date();
        const isToday = today.getFullYear() === year && today.getMonth() === month && today.getDate() === day;

        html += `
            <button class="day ${dayTasks.length ? "has-task" : ""} ${isToday ? "today" : ""}"
                    onclick="showCalendarTasks('${dateKey}')">
                ${day}
                ${dayTasks.length ? `<span class="dot"></span>` : ""}
            </button>`;
    }
    $("calendar").innerHTML = html;
}

function showCalendarTasks(dateKey) {
    const dayTasks = tasks.filter(t => t.due_date.startsWith(dateKey));
    if (!dayTasks.length) {
        $("calendarTasks").textContent = "No tasks due on this date.";
        return;
    }
    $("calendarTasks").innerHTML =
        `<strong>Tasks for ${dateKey}</strong><br>` +
        dayTasks.map(t => `• ${escapeHtml(t.title)} — ${t.priority} — ${t.tag}`).join("<br>");
}

$("addBtn").addEventListener("click", openAdd);
$("closeModal").addEventListener("click", closeModal);
$("cancelBtn").addEventListener("click", closeModal);
$("taskForm").addEventListener("submit", saveTask);
$("calendarBtn").addEventListener("click", openCalendar);
$("closeCalendar").addEventListener("click", () => $("calendarModal").classList.add("hidden"));
$("prevMonth").addEventListener("click", () => { calendarDate.setMonth(calendarDate.getMonth()-1); renderCalendar(); });
$("nextMonth").addEventListener("click", () => { calendarDate.setMonth(calendarDate.getMonth()+1); renderCalendar(); });

["searchInput", "tagFilter", "priorityFilter", "sortSelect"].forEach(id =>
    $(id).addEventListener("input", renderTasks)
);

window.addEventListener("click", event => {
    if (event.target === $("modal")) closeModal();
    if (event.target === $("calendarModal")) $("calendarModal").classList.add("hidden");
});

loadTasks();
