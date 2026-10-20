/**
 * Momentum Todo Application — Vanilla JavaScript Frontend
 * Handles asynchronous REST communication, form submission, task state, and UI updates.
 */

document.addEventListener("DOMContentLoaded", () => {
  // Global Application State
  const state = {
    currentFilter: "all", // 'all' | 'pending' | 'completed'
    tasks: [],
    counts: { total: 0, pending: 0, completed: 0 },
    isLoading: false,
    isSubmitting: false,
  };

  // Cache DOM Elements
  const form = document.getElementById("add-task-form");
  const taskInput = document.getElementById("task-title-input");
  const addTaskBtn = document.getElementById("add-task-btn");
  const charCounter = document.getElementById("char-counter");
  const formError = document.getElementById("form-error");

  const countTotalEl = document.getElementById("count-total");
  const countPendingEl = document.getElementById("count-pending");
  const countCompletedEl = document.getElementById("count-completed");

  const badgeAllEl = document.getElementById("badge-all");
  const badgePendingEl = document.getElementById("badge-pending");
  const badgeCompletedEl = document.getElementById("badge-completed");

  const filterButtons = document.querySelectorAll(".filter-pill");
  const statusSummaryEl = document.getElementById("status-summary");

  const taskListEl = document.getElementById("task-list");
  const loadingStateEl = document.getElementById("loading-state");
  const errorStateEl = document.getElementById("error-state");
  const errorMessageEl = document.getElementById("error-message");
  const retryBtn = document.getElementById("retry-btn");

  const emptyGlobalEl = document.getElementById("empty-state-global");
  const emptyFilterEl = document.getElementById("empty-state-filter");
  const emptyFilterTitle = document.getElementById("empty-filter-title");
  const emptyFilterDesc = document.getElementById("empty-filter-desc");

  const toastContainer = document.getElementById("toast-container");

  // ============================================================================
  // Toast Notifications
  // ============================================================================
  function showToast(message, type = "success", duration = 3500) {
    const toast = document.createElement("div");
    toast.className = `toast toast-${type}`;
    toast.setAttribute("role", "status");

    let iconSvg = "";
    if (type === "success") {
      iconSvg = `
        <svg class="toast-icon" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#059669" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
          <polyline points="20 6 9 17 4 12"></polyline>
        </svg>`;
    } else if (type === "celebrate") {
      iconSvg = `
        <svg class="toast-icon" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#6366f1" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
          <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"></polygon>
        </svg>`;
    } else {
      iconSvg = `
        <svg class="toast-icon" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#dc2626" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
          <circle cx="12" cy="12" r="10"></circle>
          <line x1="12" y1="8" x2="12" y2="12"></line>
          <line x1="12" y1="16" x2="12.01" y2="16"></line>
        </svg>`;
    }

    toast.innerHTML = `
      ${iconSvg}
      <span class="toast-message">${escapeHtml(message)}</span>
    `;

    toastContainer.appendChild(toast);

    setTimeout(() => {
      toast.style.opacity = "0";
      toast.style.transform = "translateX(20px)";
      setTimeout(() => {
        if (toast.parentNode) {
          toast.parentNode.removeChild(toast);
        }
      }, 200);
    }, duration);
  }

  // ============================================================================
  // Utility Functions
  // ============================================================================
  function escapeHtml(str) {
    if (!str) return "";
    return String(str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  function formatTimestamp(isoStr) {
    if (!isoStr) return "";
    try {
      const date = new Date(isoStr);
      if (isNaN(date.getTime())) return isoStr;
      return new Intl.DateTimeFormat("en-US", {
        month: "short",
        day: "numeric",
        hour: "numeric",
        minute: "numeric",
        hour12: true,
      }).format(date);
    } catch {
      return isoStr;
    }
  }

  // ============================================================================
  // API Operations
  // ============================================================================
  async function fetchCounts() {
    try {
      const res = await fetch("/api/tasks/counts");
      if (res.ok) {
        const counts = await res.json();
        state.counts = counts;
        updateCountsUI();
      }
    } catch (err) {
      console.warn("Could not retrieve counts from /api/tasks/counts:", err);
    }
  }

  async function loadTasks() {
    state.isLoading = true;
    updateVisibility();

    try {
      let url = "/api/tasks";
      if (state.currentFilter !== "all") {
        url += `?status=${encodeURIComponent(state.currentFilter)}`;
      }

      const [tasksRes] = await Promise.all([
        fetch(url),
        fetchCounts(),
      ]);

      if (!tasksRes.ok) {
        const errData = await tasksRes.json().catch(() => ({}));
        throw new Error(errData.detail || `Server returned HTTP ${tasksRes.status}`);
      }

      const tasks = await tasksRes.json();
      state.tasks = tasks;

      // Fallback count calculation if counts endpoint wasn't reached
      if (state.currentFilter === "all") {
        const total = tasks.length;
        const pending = tasks.filter((t) => t.status === "pending").length;
        const completed = tasks.filter((t) => t.status === "completed").length;
        state.counts = { total, pending, completed };
        updateCountsUI();
      }

      state.isLoading = false;
      renderTasks();
    } catch (error) {
      console.error("Error loading tasks:", error);
      state.isLoading = false;
      showErrorState(error.message || "Failed to load tasks. Please verify the server connection.");
    }
  }

  async function handleAddTask(e) {
    if (e) {
      e.preventDefault();
      e.stopPropagation();
    }

    if (state.isSubmitting) return;

    const rawTitle = taskInput.value || "";
    const cleanedTitle = rawTitle.trim();

    // Client-side Validation
    if (!cleanedTitle) {
      showFormError("Task title cannot be empty or whitespace only.");
      taskInput.focus();
      return;
    }

    if (cleanedTitle.length > 200) {
      showFormError("Task title must not exceed 200 characters.");
      taskInput.focus();
      return;
    }

    clearFormError();
    state.isSubmitting = true;
    addTaskBtn.disabled = true;
    const btnText = addTaskBtn.querySelector(".btn-text");
    if (btnText) btnText.textContent = "Adding...";

    try {
      const response = await fetch("/api/tasks", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title: cleanedTitle }),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || `Server error (${response.status})`);
      }

      const newTask = await response.json();

      // Clear input and reset counter
      taskInput.value = "";
      updateCharCounter();
      showToast(`Task added: "${newTask.title}"`, "success");

      // Refresh list & counters from backend
      await loadTasks();
      taskInput.focus();
    } catch (err) {
      console.error("Failed to add task:", err);
      showFormError(err.message || "An unexpected error occurred.");
      showToast(err.message || "Error creating task", "error");
    } finally {
      state.isSubmitting = false;
      addTaskBtn.disabled = false;
      if (btnText) btnText.textContent = "Add Task";
    }
  }

  async function handleCompleteTask(taskId, buttonElement) {
    if (!taskId) return;

    buttonElement.disabled = true;
    buttonElement.innerHTML = `
      <div class="spinner" style="width: 14px; height: 14px; border-width: 2px;"></div>
      <span>Completing...</span>
    `;

    try {
      const response = await fetch(`/api/tasks/${taskId}/complete`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
      });

      if (response.status === 409) {
        showToast("Task is already completed.", "error");
        await loadTasks();
        return;
      }

      if (response.status === 404) {
        showToast("Task not found.", "error");
        await loadTasks();
        return;
      }

      if (!response.ok) {
        const errData = await response.json().catch(() => ({}));
        throw new Error(errData.detail || `Failed to complete task (${response.status})`);
      }

      const updatedTask = await response.json();

      // Trigger celebratory visual effect
      const card = document.getElementById(`task-card-${taskId}`);
      if (card) {
        card.classList.add("task-celebrate-animation");
      }

      showToast(`Completed: "${updatedTask.title}"! Excellent progress!`, "celebrate");

      setTimeout(async () => {
        await loadTasks();
      }, 350);
    } catch (err) {
      console.error("Failed to complete task:", err);
      showToast(err.message || "Could not complete task.", "error");
      buttonElement.disabled = false;
      buttonElement.innerHTML = `
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
          <polyline points="20 6 9 17 4 12"></polyline>
        </svg>
        <span>Complete</span>
      `;
    }
  }

  // ============================================================================
  // UI Rendering & State Updates
  // ============================================================================
  function updateCountsUI() {
    countTotalEl.textContent = state.counts.total;
    countPendingEl.textContent = state.counts.pending;
    countCompletedEl.textContent = state.counts.completed;

    badgeAllEl.textContent = state.counts.total;
    badgePendingEl.textContent = state.counts.pending;
    badgeCompletedEl.textContent = state.counts.completed;
  }

  function updateVisibility() {
    if (state.isLoading) {
      loadingStateEl.style.display = "flex";
      errorStateEl.style.display = "none";
      emptyGlobalEl.style.display = "none";
      emptyFilterEl.style.display = "none";
      taskListEl.style.display = "none";
    }
  }

  function showErrorState(msg) {
    loadingStateEl.style.display = "none";
    taskListEl.style.display = "none";
    emptyGlobalEl.style.display = "none";
    emptyFilterEl.style.display = "none";
    errorStateEl.style.display = "flex";
    errorMessageEl.textContent = msg;
  }

  function renderTasks() {
    loadingStateEl.style.display = "none";
    errorStateEl.style.display = "none";

    // Update filter status text
    if (state.currentFilter === "all") {
      statusSummaryEl.textContent = `Showing all tasks (${state.tasks.length})`;
    } else if (state.currentFilter === "pending") {
      statusSummaryEl.textContent = `Showing pending tasks (${state.tasks.length})`;
    } else {
      statusSummaryEl.textContent = `Showing completed tasks (${state.tasks.length})`;
    }

    // Global empty state: no tasks exist anywhere
    if (state.counts.total === 0) {
      taskListEl.style.display = "none";
      emptyGlobalEl.style.display = "flex";
      emptyFilterEl.style.display = "none";
      return;
    }

    // Filter empty state: current filter has 0 matches
    if (state.tasks.length === 0) {
      taskListEl.style.display = "none";
      emptyGlobalEl.style.display = "none";
      emptyFilterEl.style.display = "flex";

      if (state.currentFilter === "pending") {
        emptyFilterTitle.textContent = "All caught up!";
        emptyFilterDesc.textContent = "There are no pending tasks right now. Great job!";
      } else if (state.currentFilter === "completed") {
        emptyFilterTitle.textContent = "No completed tasks yet";
        emptyFilterDesc.textContent = "Mark pending tasks as complete above to see them in this list.";
      } else {
        emptyFilterTitle.textContent = "No tasks found";
        emptyFilterDesc.textContent = "No tasks match the selected filter.";
      }
      return;
    }

    // Display tasks
    emptyGlobalEl.style.display = "none";
    emptyFilterEl.style.display = "none";
    taskListEl.style.display = "flex";
    taskListEl.innerHTML = "";

    state.tasks.forEach((task) => {
      const isCompleted = task.status === "completed";
      const li = document.createElement("li");
      li.className = `task-item-card ${isCompleted ? "is-completed" : ""}`;
      li.id = `task-card-${task.id}`;

      // Status Badge
      const statusBadge = isCompleted
        ? `<span class="badge-pill badge-completed">
             <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round">
               <polyline points="20 6 9 17 4 12"></polyline>
             </svg>
             Completed
           </span>`
        : `<span class="badge-pill badge-pending">
             <svg width="10" height="10" viewBox="0 0 24 24" fill="currentColor">
               <circle cx="12" cy="12" r="8"></circle>
             </svg>
             Pending
           </span>`;

      // Complete Action Button (Only for Pending tasks)
      const actionButton = !isCompleted
        ? `<button
             type="button"
             class="btn-complete-task"
             data-task-id="${task.id}"
             aria-label="Complete task: ${escapeHtml(task.title)}"
           >
             <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
               <polyline points="20 6 9 17 4 12"></polyline>
             </svg>
             <span>Complete</span>
           </button>`
        : "";

      li.innerHTML = `
        <div class="task-body">
          <div class="task-title-row">
            ${statusBadge}
            <span class="task-title-text">${escapeHtml(task.title)}</span>
          </div>
          <div class="task-meta-row">
            <span>Created ${formatTimestamp(task.created_at)}</span>
            <span class="meta-dot">•</span>
            <span>Task #${task.id}</span>
          </div>
        </div>
        <div class="task-actions">
          ${actionButton}
        </div>
      `;

      if (!isCompleted) {
        const btn = li.querySelector(".btn-complete-task");
        if (btn) {
          btn.addEventListener("click", () => handleCompleteTask(task.id, btn));
        }
      }

      taskListEl.appendChild(li);
    });
  }

  function showFormError(msg) {
    formError.textContent = msg;
    formError.style.display = "flex";
  }

  function clearFormError() {
    formError.textContent = "";
    formError.style.display = "none";
  }

  function updateCharCounter() {
    const len = (taskInput.value || "").length;
    charCounter.textContent = `${len}/200`;
    charCounter.classList.remove("warning", "danger");

    if (len >= 190) {
      charCounter.classList.add("danger");
    } else if (len >= 160) {
      charCounter.classList.add("warning");
    }
  }

  // ============================================================================
  // Event Attachments
  // ============================================================================
  form.addEventListener("submit", handleAddTask);

  taskInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleAddTask(e);
    }
  });

  taskInput.addEventListener("input", () => {
    updateCharCounter();
    if (formError.style.display !== "none") {
      clearFormError();
    }
  });

  retryBtn.addEventListener("click", loadTasks);

  filterButtons.forEach((btn) => {
    btn.addEventListener("click", () => {
      const filter = btn.dataset.filter;
      if (state.currentFilter === filter) return;

      filterButtons.forEach((b) => {
        b.classList.remove("active");
        b.setAttribute("aria-selected", "false");
      });
      btn.classList.add("active");
      btn.setAttribute("aria-selected", "true");

      state.currentFilter = filter;
      loadTasks();
    });
  });

  // Initial Load
  loadTasks();
});
