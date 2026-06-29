/**
 * Unified local office task store (halOfficeTasks persistence).
 */
const OfficeTaskStore = (function () {
  let tasks = [];
  let loaded = false;
  const listeners = [];

  function bridge() {
    if (typeof DesktopBridge !== "undefined") return DesktopBridge;
    if (typeof window !== "undefined" && window.DesktopBridge) return window.DesktopBridge;
    return null;
  }

  function onChange(fn) {
    if (typeof fn === "function") listeners.push(fn);
  }

  function notify() {
    listeners.forEach((fn) => {
      try {
        fn(tasks.slice());
      } catch {
        /* optional */
      }
    });
  }

  async function load() {
    const br = bridge();
    if (br && typeof br.storageGet === "function") {
      try {
        tasks = (await br.storageGet("halOfficeTasks")) || [];
      } catch (err) {
        tasks = [];
        if (window.RuntimeIssues) RuntimeIssues.record("office-task-store", err, { op: "load" });
      }
    }
    loaded = true;
    return tasks.slice();
  }

  async function save(next) {
    tasks = Array.isArray(next) ? next.slice() : tasks;
    const br = bridge();
    if (br && typeof br.storageSet === "function") {
      try {
        await br.storageSet("halOfficeTasks", tasks);
      } catch (err) {
        if (window.RuntimeIssues) RuntimeIssues.record("office-task-store", err, { op: "save" });
      }
    }
    notify();
    return tasks.slice();
  }

  async function list() {
    if (!loaded) await load();
    return tasks.slice();
  }

  async function add(task) {
    if (!loaded) await load();
    tasks.unshift(task);
    return save(tasks);
  }

  async function update(taskId, updates) {
    if (!loaded) await load();
    const index = tasks.findIndex((task) => task.taskId === taskId);
    if (index < 0) throw new Error("Task not found.");
    const HalSkillsRef =
      typeof HalSkills !== "undefined" ? HalSkills : typeof window !== "undefined" && window.HalSkills ? window.HalSkills : null;
    tasks[index] = HalSkillsRef ? HalSkillsRef.applyTaskUpdate(tasks[index], updates) : Object.assign({}, tasks[index], updates);
    return save(tasks);
  }

  async function upsert(task) {
    if (!loaded) await load();
    const HalSkillsRef =
      typeof HalSkills !== "undefined" ? HalSkills : typeof window !== "undefined" && window.HalSkills ? window.HalSkills : null;
    if (!HalSkillsRef || typeof HalSkillsRef.upsertHalTask !== "function") {
      tasks.unshift(task);
      return save(tasks);
    }
    const result = HalSkillsRef.upsertHalTask(tasks, task, { actor: "hal-office-manager" });
    tasks = result.tasks;
    return save(tasks);
  }

  async function replaceAll(next) {
    return save(next);
  }

  function isConfigured() {
    const br = bridge();
    return Boolean(br && typeof br.storageGet === "function");
  }

  function state() {
    return {
      configured: isConfigured(),
      count: tasks.length,
      loaded,
    };
  }

  return { load, save, list, add, update, upsert, replaceAll, onChange, isConfigured, state };
})();

if (typeof module !== "undefined" && module.exports) {
  module.exports = OfficeTaskStore;
}
if (typeof window !== "undefined") {
  window.OfficeTaskStore = OfficeTaskStore;
}
