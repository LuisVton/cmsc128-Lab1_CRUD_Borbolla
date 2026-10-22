let currentListId = null;
const csrf = document.querySelector('meta[name="csrf-token"]').content;
const apiFetch = (url, options={}) => fetch(url, {...options, headers: {...(options.headers||{}), 'X-CSRF-Token':csrf}});
async function loadLists(preferred=null) {
 const r=await apiFetch('/api/lists'); if(!r.ok) throw Error('Cannot load lists');
 const lists=await r.json(); const select=document.getElementById('listSelect');
 select.replaceChildren(); for(const list of lists){const option=document.createElement('option');option.value=list.id;option.textContent=`${list.name} (${list.kind}${list.is_owner?' · owner':''})`;select.append(option);}
 currentListId=lists.some(l=>l.id===Number(preferred??currentListId))?Number(preferred??currentListId):lists[0]?.id;
 select.value=currentListId; const selected=lists.find(l=>l.id===currentListId); const canManage=Boolean(selected?.is_owner && selected?.kind==='collaborative'); document.getElementById('inviteBtn').hidden=!canManage; document.getElementById('membersBtn').hidden=!canManage;
 await loadTasks();
}
let tasks = [];
let editingId = null;
let calendarDate = new Date();

const $ = (id) => document.getElementById(id);

async function loadTasks() {
    const response = await apiFetch(`/api/tasks?list_id=${currentListId}`);
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

    const response = await apiFetch(url, {
        method,
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({...data, list_id: currentListId})
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
    const response = await apiFetch(`/api/tasks/${id}/complete`, { method: "PATCH" });
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

    const response = await apiFetch(`/api/tasks/${id}`, {
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

        const response = await apiFetch(
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

        await apiFetch(
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


document.getElementById('listSelect').addEventListener('change', async e=>{currentListId=Number(e.target.value);await loadLists(currentListId)});
function showDialog(id, focusId) {
    $(id).classList.remove('hidden');
    if (focusId) $(focusId).focus();
}
function hideDialog(id) { $(id).classList.add('hidden'); }
function bindDialog(id, closeIds) {
    closeIds.forEach(buttonId => $(buttonId).addEventListener('click', () => hideDialog(id)));
    $(id).addEventListener('click', event => { if (event.target === $(id)) hideDialog(id); });
}
bindDialog('listModal', ['closeListModal', 'cancelListModal']);
bindDialog('inviteModal', ['closeInviteModal', 'cancelInviteModal']);
bindDialog('membersModal', ['closeMembersModal', 'doneMembersModal']);
$('newListBtn').addEventListener('click', () => {
    $('listForm').reset(); showDialog('listModal', 'listName');
});
$('listForm').addEventListener('submit', async event => {
    event.preventDefault();
    const name=$('listName').value.trim(); if (!name) return;
    try {
        const r=await apiFetch('/api/lists', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name})});
        const d=await r.json(); if(!r.ok) throw Error(d.error || 'Could not create list');
        hideDialog('listModal'); await loadLists(d.id); showToast('Collaborative list created.');
    } catch(e) { showToast(e.message); }
});
$('inviteBtn').addEventListener('click', () => {
    $('inviteForm').reset(); showDialog('inviteModal', 'inviteIdentifier');
});
$('inviteForm').addEventListener('submit', async event => {
    event.preventDefault();
    const identifier=$('inviteIdentifier').value.trim(); if(!identifier) return;
    try {
        const r=await apiFetch(`/api/lists/${currentListId}/members`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({identifier})});
        const d=await r.json(); if(!r.ok) throw Error(d.error || 'Could not invite member');
        hideDialog('inviteModal'); showToast('Member added successfully.');
    } catch(e) { showToast(e.message); }
});
async function refreshMembers() {
    const r=await apiFetch(`/api/lists/${currentListId}/members`);
    if(!r.ok) { showToast('Cannot load members.'); return; }
    const members=await r.json(); const container=$('membersList'); container.replaceChildren();
    if (!members.length) { const p=document.createElement('p');p.textContent='No invited members yet.';container.append(p);return; }
    members.forEach(member => {
        const row=document.createElement('div');row.className='member-row';
        const details=document.createElement('div');
        const name=document.createElement('strong');name.textContent=member.display_name || member.username;
        const username=document.createElement('small');username.textContent=`@${member.username}`;
        details.append(name,username);
        const remove=document.createElement('button');remove.className='secondary member-remove';remove.type='button';remove.textContent='Remove';
        remove.addEventListener('click', async () => {
            if (!confirm(`Remove ${member.username} from this list?`)) return;
            const r=await apiFetch(`/api/lists/${currentListId}/members/${member.id}`,{method:'DELETE'});
            if(!r.ok) { const d=await r.json();showToast(d.error || 'Could not remove member');return; }
            showToast('Member removed.'); await refreshMembers();
        });
        row.append(details,remove);container.append(row);
    });
}
$('membersBtn').addEventListener('click',async () => {showDialog('membersModal');await refreshMembers();});
document.addEventListener('keydown',event => {
    if(event.key==='Escape') ['listModal','inviteModal','membersModal'].forEach(hideDialog);
});
loadLists().catch(e=>showToast(e.message));
