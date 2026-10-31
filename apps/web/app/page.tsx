"use client";

import { FormEvent, useEffect, useRef, useState } from "react";

type Setup = { configured: boolean; provider: string; chat_ready: boolean };
type Project = { id: string; name: string; root_path: string | null; notes: string; status: string };
type Conversation = { id: string; title: string; updated_at: string; project_id: string | null; agent_id: string };
type Message = { id: string; role: "user" | "assistant"; content: string; created_at: string };
type Usage = { requests: number; prompt_tokens: number; completion_tokens: number; providers: { provider: string; requests: number }[] };
type Agent = { id: string; name: string; purpose: string; workflow: string[]; permission: string };
type Step = { id: string; title: string; status: string; requires_approval: boolean };
type Task = { id: string; title: string; request: string; agent_id: string; status: string; steps: Step[] };
type Memory = { id: string; category: string; kind: string; title: string; content: string; project_id: string | null; source: string; confidence: number | null; updated_at: string };
type Tool = { id: string; name: string; risk_level: number; description: string; enabled: boolean };
type Approval = { id: string; tool_id: string; project_id: string; args: Record<string, string>; preview: string; action_hash: string; risk_level: number; status: string; expires_at: string; result?: Record<string, unknown> };
type Job = { id: string; title: string; due_at: string; interval_seconds: number | null; status: string; payload?: { body: string } };
type Notification = { id: string; title: string; body: string; read_at: string | null; created_at: string };
type Integration = { id: string; name: string; service: "gmail" | "calendar"; state: string; scopes: string[]; connected_at: string | null; can_connect: boolean; connected: boolean };
type GoogleMessage = { id: string; from: string; subject: string; date: string; snippet: string; untrusted: true };
type GoogleEvent = { id: string; summary: string; start: { dateTime?: string; date?: string }; end: { dateTime?: string; date?: string }; location: string; untrusted: true };
type SensorSample = { sensor: string; value: number; unit: string; recorded_at: string };
type Device = { id: string; name: string; active: boolean; created_at: string; latest: SensorSample[] };
type Maintenance = { database: string; schema_version: number; size_bytes: number; pending_jobs: number };
type Tab = "chat" | "projects" | "usage" | "agents" | "memory" | "tools" | "automation" | "devices";
type RecognitionChunk = ArrayLike<{ transcript: string }> & { isFinal: boolean };
type RecognitionEventLike = { resultIndex: number; results: ArrayLike<RecognitionChunk> };
type BrowserRecognition = { lang: string; continuous: boolean; interimResults: boolean; onresult: ((event: RecognitionEventLike) => void) | null; onerror: (() => void) | null; onend: (() => void) | null; start(): void; stop(): void };

async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch("/api/v1" + path, {
    ...init,
    credentials: "include",
    headers: { "Content-Type": "application/json", ...init.headers }
  });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(body.detail || "Request failed.");
  return body as T;
}

function Icon({ name }: { name: "spark" | "chat" | "folder" | "chart" | "plus" | "send" | "lock" | "brain" | "memory" | "check" }) {
  const paths = {
    spark: <><path d="m12 3 1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8L12 3Z"/><path d="m19 14 .9 2.1L22 17l-2.1.9L19 20l-.9-2.1L16 17l2.1-.9L19 14Z"/></>,
    chat: <><path d="M21 11.5a8.4 8.4 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.4 8.4 0 0 1-3.8-.9L3 21l1.9-5.7a8.4 8.4 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.4 8.4 0 0 1 3.8-.9h.5a8.5 8.5 0 0 1 8 8v.5Z"/></>,
    folder: <><path d="M3 7.5A2.5 2.5 0 0 1 5.5 5H10l2 2h6.5A2.5 2.5 0 0 1 21 9.5v8a2.5 2.5 0 0 1-2.5 2.5h-13A2.5 2.5 0 0 1 3 17.5v-10Z"/><path d="M3 10h18"/></>,
    chart: <><path d="M4 19V5"/><path d="M4 19h17"/><path d="m7 15 4-4 3 2 5-6"/></>,
    plus: <><path d="M12 5v14M5 12h14"/></>,
    send: <><path d="m22 2-7 20-4-9-9-4Z"/><path d="M22 2 11 13"/></>,
    lock: <><rect x="4" y="10" width="16" height="11" rx="2"/><path d="M8 10V7a4 4 0 1 1 8 0v3"/></>,
    brain: <><path d="M12 18V5"/><path d="M8 8a4 4 0 0 1 8 0c2 0 3 1.5 3 3.5S17.5 15 16 15"/><path d="M8 8c-2 0-3 1.5-3 3.5S6.5 15 8 15"/><path d="M8 15c-1.5 1.8-.2 4 2 4"/></>,
    memory: <><path d="M5 6h14M5 12h14M5 18h14"/><circle cx="8" cy="6" r="1"/><circle cx="15" cy="12" r="1"/><circle cx="10" cy="18" r="1"/></>,
    check: <><path d="m5 12 4 4L19 6"/></>
  }[name];
  return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{paths}</svg>;
}

export default function Home() {
  const [setup, setSetup] = useState<Setup | null>(null);
  const [signedIn, setSignedIn] = useState<boolean | null>(null);
  const [password, setPassword] = useState("");
  const [tab, setTab] = useState<Tab>("chat");
  const [projects, setProjects] = useState<Project[]>([]);
  const [agents, setAgents] = useState<Agent[]>([]);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [memories, setMemories] = useState<Memory[]>([]);
  const [tools, setTools] = useState<Tool[]>([]);
  const [approvals, setApprovals] = useState<Approval[]>([]);
  const [emergencyStop, setEmergencyStop] = useState(false);
  const [toolChoice, setToolChoice] = useState("files.list");
  const [toolPath, setToolPath] = useState("");
  const [toolQuery, setToolQuery] = useState("");
  const [toolContent, setToolContent] = useState("");
  const [toolResult, setToolResult] = useState<Record<string, unknown> | null>(null);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [integrations, setIntegrations] = useState<Integration[]>([]);
  const [integrationBusy, setIntegrationBusy] = useState("");
  const [gmailPreview, setGmailPreview] = useState<GoogleMessage[] | null>(null);
  const [calendarPreview, setCalendarPreview] = useState<GoogleEvent[] | null>(null);
  const [reminderTitle, setReminderTitle] = useState("");
  const [reminderBody, setReminderBody] = useState("");
  const [reminderDue, setReminderDue] = useState("");
  const [reminderInterval, setReminderInterval] = useState("0");
  const [devices, setDevices] = useState<Device[]>([]);
  const [deviceName, setDeviceName] = useState("");
  const [newDeviceToken, setNewDeviceToken] = useState<{ id: string; name: string; token: string } | null>(null);
  const [maintenance, setMaintenance] = useState<Maintenance | null>(null);
  const [listening, setListening] = useState(false);
  const recognitionRef = useRef<BrowserRecognition | null>(null);
  const [selectedAgent, setSelectedAgent] = useState("orchestrator");
  const [selectedProject, setSelectedProject] = useState("");
  const [summary, setSummary] = useState("");
  const [planRequest, setPlanRequest] = useState("");
  const [planAgent, setPlanAgent] = useState("auto");
  const [memoryCategory, setMemoryCategory] = useState("owner_preference");
  const [memoryKind, setMemoryKind] = useState("confirmed");
  const [memoryTitle, setMemoryTitle] = useState("");
  const [memoryContent, setMemoryContent] = useState("");
  const [memoryProject, setMemoryProject] = useState("");
  const [memoryQuery, setMemoryQuery] = useState("");
  const [editingMemory, setEditingMemory] = useState("");
  const [editTitle, setEditTitle] = useState("");
  const [editContent, setEditContent] = useState("");
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [messages, setMessages] = useState<Message[]>([]);
  const [activeId, setActiveId] = useState("");
  const [prompt, setPrompt] = useState("");
  const [usage, setUsage] = useState<Usage | null>(null);
  const [projectName, setProjectName] = useState("");
  const [projectPath, setProjectPath] = useState("");
  const [projectNotes, setProjectNotes] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [apiOffline, setApiOffline] = useState(false);

  useEffect(() => {
    void bootstrap();
    if ("serviceWorker" in navigator) void navigator.serviceWorker.register("/sw.js").catch(() => undefined);
  }, []);
  useEffect(() => {
    if (!signedIn) return;
    let active = true;
    const poll = async () => { try { const latest = await api<Notification[]>("/notifications?limit=50"); if (active) setNotifications(latest); } catch { /* API reconnects on the next poll. */ } };
    const timer = window.setInterval(() => void poll(), 20000);
    return () => { active = false; window.clearInterval(timer); };
  }, [signedIn]);

  async function bootstrap() {
    setApiOffline(false);
    let state: Setup;
    try {
      state = await api<Setup>("/setup/status");
      setSetup(state);
    } catch {
      setApiOffline(true);
      setSignedIn(false);
      return;
    }
    if (!state.configured) { setSignedIn(false); return; }
    try {
      await api("/auth/me");
      setSignedIn(true);
      await refreshWorkspace();
    } catch {
      setSignedIn(false);
    }
  }

  async function refreshWorkspace() {
    const [p, c, u, a, t, m, toolState, approvalState, j, n, integrationState, d, system] = await Promise.all([
      api<Project[]>("/projects"),
      api<Conversation[]>("/conversations"),
      api<Usage>("/usage"),
      api<Agent[]>("/agents"),
      api<Task[]>("/tasks"),
      api<Memory[]>("/memories?limit=100"),
      api<{ tools: Tool[]; emergency_stop: boolean }>("/tools"),
      api<Array<Omit<Approval, "args" | "result"> & { args_json: string; result_json: string | null }>>("/approvals"),
      api<Array<Job & { payload_json?: string }>>("/jobs"),
      api<Notification[]>("/notifications?limit=50"),
      api<Integration[]>("/integrations"),
      api<Device[]>("/devices"),
      api<Maintenance>("/maintenance/status")
    ]);
    setProjects(p);
    setConversations(c);
    setUsage(u);
    setAgents(a);
    setTasks(t);
    setMemories(m);
    setTools(toolState.tools);
    setEmergencyStop(toolState.emergency_stop);
    setApprovals(approvalState.map((item) => ({ ...item, args: JSON.parse(item.args_json || "{}"), result: item.result_json ? JSON.parse(item.result_json) : undefined })));
    setJobs(j.map((item) => ({ ...item, payload: item.payload || JSON.parse(item.payload_json || "{}") })));
    setNotifications(n);
    setIntegrations(integrationState);
    setDevices(d);
    setMaintenance(system);
    if (activeId && c.some((item) => item.id === activeId)) {
      const active = c.find((item) => item.id === activeId);
      setSelectedProject(active?.project_id || "");
      setSelectedAgent(active?.agent_id || "orchestrator");
      return;
    }
    if (c.length) {
      setActiveId(c[0].id);
      setSelectedProject(c[0].project_id || "");
      setSelectedAgent(c[0].agent_id || "orchestrator");
      await loadMessages(c[0].id, c[0]);
    } else {
      setActiveId("");
      setSelectedProject("");
      setSelectedAgent("orchestrator");
      setMessages([]);
      setSummary("");
    }
  }

  async function loadMessages(id: string, selected?: Conversation) {
    setActiveId(id);
    const conversation = selected || conversations.find((item) => item.id === id);
    setSelectedProject(conversation?.project_id || "");
    setSelectedAgent(conversation?.agent_id || "orchestrator");
    try {
      const [items, saved] = await Promise.all([
        api<Message[]>("/conversations/" + id + "/messages"),
        api<{ summary: string }>("/conversations/" + id + "/summary")
      ]);
      setMessages(items);
      setSummary(saved.summary || "");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to load conversation.");
    }
  }

  async function signIn(event: FormEvent) {
    event.preventDefault();
    setBusy(true); setError("");
    try {
      await api("/auth/login", { method: "POST", body: JSON.stringify({ password }) });
      setPassword(""); setSignedIn(true);
      await refreshWorkspace();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Sign in failed.");
    } finally { setBusy(false); }
  }

  async function createConversation() {
    setError("");
    try {
      const conversation = await api<Conversation>("/conversations", {
        method: "POST", body: JSON.stringify({ title: "New conversation", project_id: selectedProject || null, agent_id: selectedAgent })
      });
      setConversations((current) => [conversation, ...current]);
      setMessages([]); setSummary(""); setActiveId(conversation.id); setTab("chat");
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Could not start a conversation."); }
  }

  async function sendMessage(event: FormEvent) {
    event.preventDefault();
    const text = prompt.trim();
    if (!text || busy || !setup?.chat_ready) return;
    setError("");
    setBusy(true);
    try {
      let conversationId = activeId;
      if (!conversationId) {
        const created = await api<Conversation>("/conversations", {
          method: "POST", body: JSON.stringify({ title: text.slice(0, 52), project_id: selectedProject || null, agent_id: selectedAgent })
        });
        conversationId = created.id;
        setActiveId(created.id);
        setConversations((current) => [created, ...current]);
      }
      const userMessage: Message = { id: String(Date.now()), role: "user", content: text, created_at: new Date().toISOString() };
      setMessages((current) => [...current, userMessage]);
      setPrompt("");
      const answer = await api<{ role: "assistant"; content: string }>("/conversations/" + conversationId + "/chat", {
        method: "POST", body: JSON.stringify({ message: text })
      });
      setMessages((current) => [...current, { id: String(Date.now() + 1), role: "assistant", content: answer.content, created_at: new Date().toISOString() }]);
      await refreshWorkspace();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "The message could not be sent.");
    } finally { setBusy(false); }
  }

  function toggleDictation() {
    if (listening) { recognitionRef.current?.stop(); return; }
    const speechWindow = window as Window & { SpeechRecognition?: new () => BrowserRecognition; webkitSpeechRecognition?: new () => BrowserRecognition };
    const Recognition = speechWindow.SpeechRecognition || speechWindow.webkitSpeechRecognition;
    if (!Recognition) { setError("Dictation is not available in this browser."); return; }
    const recognition = new Recognition();
    recognition.lang = navigator.language || "en-US";
    recognition.continuous = true;
    recognition.interimResults = false;
    recognition.onresult = (event) => {
      const words: string[] = [];
      for (let index = event.resultIndex; index < event.results.length; index++) if (event.results[index].isFinal) words.push(event.results[index][0].transcript.trim());
      if (words.length) setPrompt((current) => (current.trim() ? current.trimEnd() + " " : "") + words.join(" "));
    };
    recognition.onerror = () => { setListening(false); setError("The browser could not capture speech. Check microphone access and try again."); };
    recognition.onend = () => setListening(false);
    recognitionRef.current = recognition;
    try { recognition.start(); setListening(true); }
    catch { setListening(false); setError("Dictation could not start. Try again in a moment."); }
  }

  function speakMessage(content: string) {
    if (!("speechSynthesis" in window)) { setError("Speech playback is not available in this browser."); return; }
    window.speechSynthesis.cancel();
    window.speechSynthesis.speak(new SpeechSynthesisUtterance(content));
  }

  async function addProject(event: FormEvent) {
    event.preventDefault();
    if (!projectName.trim()) return;
    setBusy(true); setError("");
    try {
      const project = await api<Project>("/projects", {
        method: "POST",
        body: JSON.stringify({ name: projectName, root_path: projectPath || null, notes: projectNotes })
      });
      setProjects((current) => [...current, project].sort((a, b) => a.name.localeCompare(b.name)));
      setProjectName(""); setProjectPath(""); setProjectNotes("");
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Could not save project."); }
    finally { setBusy(false); }
  }

  async function archiveProject(id: string) {
    try {
      await api("/projects/" + id + "/archive", { method: "POST" });
      setProjects((current) => current.filter((project) => project.id !== id));
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Could not archive project."); }
  }

  async function changeProjectPath(project: Project) {
    const value = window.prompt("Local folder path for this project", project.root_path || "");
    if (value === null) return;
    try { const updated = await api<Project>("/projects/" + project.id, { method: "PATCH", body: JSON.stringify({ root_path: value.trim() || null }) }); setProjects((current) => current.map((item) => item.id === updated.id ? updated : item)); }
    catch (cause) { setError(cause instanceof Error ? cause.message : "Could not update project folder."); }
  }

  async function updateConversation(patch: Partial<Pick<Conversation, "project_id" | "agent_id">>) {
    if (patch.project_id !== undefined) setSelectedProject(patch.project_id || "");
    if (patch.agent_id) setSelectedAgent(patch.agent_id);
    if (!activeId) return;
    try {
      const updated = await api<Conversation>("/conversations/" + activeId, {
        method: "PATCH", body: JSON.stringify(patch)
      });
      setConversations((current) => current.map((item) => item.id === activeId ? updated : item));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not update conversation settings.");
    }
  }

  async function saveSummary() {
    if (!activeId) return;
    setError("");
    try {
      const result = await api<{ summary: string }>("/conversations/" + activeId + "/summarize", { method: "POST" });
      setSummary(result.summary);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not summarize this conversation.");
    }
  }

  async function createAgentPlan(event: FormEvent) {
    event.preventDefault();
    if (!planRequest.trim()) return;
    setBusy(true); setError("");
    try {
      const result = await api<{ task: Task; steps: Step[] }>("/agents/plan", {
        method: "POST",
        body: JSON.stringify({
          request: planRequest,
          agent_id: planAgent === "auto" ? undefined : planAgent,
          project_id: selectedProject || null
        })
      });
      setTasks((current) => [{ ...result.task, steps: result.steps }, ...current]);
      setPlanRequest("");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not create an agent plan.");
    } finally { setBusy(false); }
  }

  async function completeTaskStep(taskId: string, stepId: string) {
    try {
      const result = await api<{ status: string; steps: Step[] }>(
        "/tasks/" + taskId + "/steps/" + stepId + "/complete",
        { method: "POST" }
      );
      setTasks((current) => current.map((task) => task.id === taskId ? { ...task, status: result.status, steps: result.steps } : task));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not update this task.");
    }
  }

  async function updateTaskStatus(taskId: string, status: string) {
    try {
      const updated = await api<Task>("/tasks/" + taskId, {
        method: "PATCH", body: JSON.stringify({ status })
      });
      setTasks((current) => current.map((task) => task.id === taskId ? updated : task));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not update task status.");
    }
  }

  async function addMemory(event: FormEvent) {
    event.preventDefault();
    if (!memoryTitle.trim() || !memoryContent.trim()) return;
    setBusy(true); setError("");
    try {
      const saved = await api<Memory>("/memories", {
        method: "POST",
        body: JSON.stringify({
          category: memoryCategory, kind: memoryKind, title: memoryTitle,
          content: memoryContent, project_id: memoryProject || null,
          source: "owner", confidence: memoryKind === "unverified" ? 0.3 : 1
        })
      });
      setMemories((current) => [saved, ...current]);
      setMemoryTitle(""); setMemoryContent("");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not save this memory.");
    } finally { setBusy(false); }
  }

  async function searchMemories(event: FormEvent) {
    event.preventDefault();
    try {
      const items = memoryQuery.trim()
        ? await api<Memory[]>("/memories/search?q=" + encodeURIComponent(memoryQuery))
        : await api<Memory[]>("/memories?limit=100");
      setMemories(items);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not search memory.");
    }
  }

  function beginMemoryEdit(memory: Memory) {
    setEditingMemory(memory.id);
    setEditTitle(memory.title);
    setEditContent(memory.content);
  }

  async function saveMemoryEdit(id: string) {
    try {
      const saved = await api<Memory>("/memories/" + id, {
        method: "PATCH", body: JSON.stringify({ title: editTitle, content: editContent })
      });
      setMemories((current) => current.map((item) => item.id === id ? saved : item));
      setEditingMemory("");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not update memory.");
    }
  }

  async function deleteMemory(id: string) {
    if (!window.confirm("Delete this memory permanently?")) return;
    try {
      await api("/memories/" + id, { method: "DELETE" });
      setMemories((current) => current.filter((item) => item.id !== id));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not delete memory.");
    }
  }

  async function previewTool(event: FormEvent) {
    event.preventDefault();
    if (!selectedProject) { setError("Choose a project with a local folder path first."); return; }
    const args: Record<string, string> = {};
    if (["files.list", "files.search"].includes(toolChoice) && toolPath.trim()) args.path = toolPath.trim();
    if (["files.read", "files.create"].includes(toolChoice)) args.path = toolPath.trim();
    if (toolChoice === "files.search") args.query = toolQuery.trim();
    if (toolChoice === "files.create") args.content = toolContent;
    setBusy(true); setError(""); setToolResult(null);
    try {
      const preview = await api<Approval & { requires_approval: boolean }>("/tools/preview", { method: "POST", body: JSON.stringify({ tool_id: toolChoice, project_id: selectedProject, args }) });
      setApprovals((current) => [preview, ...current.filter((item) => item.id !== preview.id)]);
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Could not prepare that action."); }
    finally { setBusy(false); }
  }

  async function runPreview(id: string) {
    setBusy(true); setError("");
    try {
      const result = await api<{ status: string; result: Record<string, unknown> }>("/approvals/" + id + "/execute", { method: "POST" });
      setToolResult(result.result);
      await refreshWorkspace();
    } catch (cause) { setError(cause instanceof Error ? cause.message : "The preview could not run."); }
    finally { setBusy(false); }
  }

  async function approveAndRun(id: string) {
    setBusy(true); setError("");
    try {
      await api("/approvals/" + id + "/approve", { method: "POST" });
      const result = await api<{ status: string; result: Record<string, unknown> }>("/approvals/" + id + "/execute", { method: "POST" });
      setToolResult(result.result);
      await refreshWorkspace();
    } catch (cause) { setError(cause instanceof Error ? cause.message : "The approved action could not run."); await refreshWorkspace(); }
    finally { setBusy(false); }
  }

  async function setToolEnabled(tool: Tool, enabled: boolean) {
    try { await api("/tools/" + tool.id, { method: "PATCH", body: JSON.stringify({ enabled }) }); await refreshWorkspace(); }
    catch (cause) { setError(cause instanceof Error ? cause.message : "Could not update tool."); }
  }

  async function setStop(enabled: boolean) {
    try { const result = await api<{ enabled: boolean }>("/system/emergency-stop", { method: "PUT", body: JSON.stringify({ enabled }) }); setEmergencyStop(result.enabled); await refreshWorkspace(); }
    catch (cause) { setError(cause instanceof Error ? cause.message : "Could not update emergency stop."); }
  }

  async function cancelPreview(id: string) {
    try { await api("/approvals/" + id + "/cancel", { method: "POST" }); await refreshWorkspace(); }
    catch (cause) { setError(cause instanceof Error ? cause.message : "Could not cancel action."); }
  }

  async function addReminder(event: FormEvent) {
    event.preventDefault();
    if (!reminderTitle.trim() || !reminderDue) return;
    try {
      await api("/jobs", { method: "POST", body: JSON.stringify({ title: reminderTitle, body: reminderBody, due_at: new Date(reminderDue).toISOString(), interval_seconds: Number(reminderInterval) || null }) });
      setReminderTitle(""); setReminderBody(""); setReminderDue(""); await refreshWorkspace();
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Could not save reminder."); }
  }

  async function markNotificationRead(id: string) {
    try { await api("/notifications/" + id + "/read", { method: "POST" }); await refreshWorkspace(); }
    catch (cause) { setError(cause instanceof Error ? cause.message : "Could not update notification."); }
  }

  async function disconnectGoogle(service: "gmail" | "calendar") {
    if (!window.confirm("Disconnect " + (service === "gmail" ? "Gmail" : "Google Calendar") + " and delete its saved refresh token?")) return;
    setIntegrationBusy(service); setError("");
    try {
      await api("/integrations/google/" + service, { method: "DELETE" });
      if (service === "gmail") setGmailPreview(null); else setCalendarPreview(null);
      await refreshWorkspace();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not disconnect Google.");
    } finally { setIntegrationBusy(""); }
  }

  async function loadGooglePreview(service: "gmail" | "calendar") {
    setIntegrationBusy(service); setError("");
    try {
      if (service === "gmail") {
        const result = await api<{ messages: GoogleMessage[] }>("/integrations/google/gmail/messages?limit=10");
        setGmailPreview(result.messages);
      } else {
        const result = await api<{ events: GoogleEvent[] }>("/integrations/google/calendar/events");
        setCalendarPreview(result.events);
      }
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not load Google data.");
    } finally { setIntegrationBusy(""); }
  }

  async function cancelReminder(id: string) {
    try { await api("/jobs/" + id + "/cancel", { method: "POST" }); await refreshWorkspace(); }
    catch (cause) { setError(cause instanceof Error ? cause.message : "Could not cancel reminder."); }
  }

  async function addDevice(event: FormEvent) {
    event.preventDefault();
    if (!deviceName.trim()) return;
    try { const created = await api<{ id: string; name: string; token: string }>("/devices", { method: "POST", body: JSON.stringify({ name: deviceName }) }); setNewDeviceToken(created); setDeviceName(""); await refreshWorkspace(); }
    catch (cause) { setError(cause instanceof Error ? cause.message : "Could not register device."); }
  }

  async function disableDevice(id: string) {
    try { await api("/devices/" + id + "/disable", { method: "POST" }); await refreshWorkspace(); }
    catch (cause) { setError(cause instanceof Error ? cause.message : "Could not disable device."); }
  }
  if (signedIn === null) return <main className="loading"><span className="brand-mark"><Icon name="spark"/></span><p>Opening your private workspace…</p></main>;

  if (apiOffline) return (
    <main className="login-wrap">
      <section className="login-card">
        <div className="brand-mark"><Icon name="spark"/></div>
        <p className="eyebrow">BIKASH AI · PRIVATE WORKSPACE</p>
        <h1>Start the local API</h1>
        <p className="muted">The dashboard is running, but its local service is not responding. Start it in another PowerShell terminal:</p>
        <code className="command">./scripts/run-api.ps1</code>
        <button className="primary wide" onClick={() => { setSignedIn(null); void bootstrap(); }}>Try again</button>
      </section>
    </main>
  );
  if (!setup?.configured) return (
    <main className="login-wrap">
      <section className="login-card">
        <div className="brand-mark"><Icon name="spark"/></div>
        <p className="eyebrow">BIKASH AI · PRIVATE WORKSPACE</p>
        <h1>Set up your private workspace</h1>
        <p className="muted">Create the local owner profile once from the project folder:</p>
        <code className="command">./scripts/setup.ps1</code>
        <p className="muted small">Then refresh this page. The setup script stores a password hash locally and does not save your password.</p>
      </section>
    </main>
  );

  if (!signedIn) return (
    <main className="login-wrap">
      <section className="login-card">
        <div className="brand-mark"><Icon name="spark"/></div>
        <p className="eyebrow">BIKASH AI · PRIVATE WORKSPACE</p>
        <h1>Good to see you.</h1>
        <p className="muted">Sign in to open your local assistant.</p>
        <form onSubmit={signIn} className="stack">
          <label htmlFor="owner-password">Owner password</label>
          <input id="owner-password" type="password" autoComplete="current-password" value={password} onChange={(event) => setPassword(event.target.value)} required />
          <button className="primary wide" disabled={busy}><Icon name="lock"/>{busy ? "Opening…" : "Unlock workspace"}</button>
        </form>
        {error && <p className="error" role="alert">{error}</p>}
        <p className="muted small privacy"><span className="dot green"/>Your data stays in the local project database.</p>
      </section>
    </main>
  );

  return (
    <main className="shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark small-mark"><Icon name="spark"/></div>
          <div><strong>Bikash AI</strong><span>Personal workspace</span></div>
        </div>
        <button className="new-chat" onClick={() => void createConversation()}><Icon name="plus"/>New conversation</button>
        <nav className="nav">
          <button className={tab === "chat" ? "nav-item selected" : "nav-item"} onClick={() => setTab("chat")}><Icon name="chat"/>Assistant</button>
          <button className={tab === "projects" ? "nav-item selected" : "nav-item"} onClick={() => setTab("projects")}><Icon name="folder"/>Projects<span className="nav-count">{projects.length}</span></button>
          <button className={tab === "usage" ? "nav-item selected" : "nav-item"} onClick={() => setTab("usage")}><Icon name="chart"/>Usage</button>
          <button className={tab === "agents" ? "nav-item selected" : "nav-item"} onClick={() => setTab("agents")}><Icon name="brain"/>Agents & tasks<span className="nav-count">{tasks.filter((task) => task.status !== "done" && task.status !== "cancelled").length}</span></button>
          <button className={tab === "memory" ? "nav-item selected" : "nav-item"} onClick={() => setTab("memory")}><Icon name="memory"/>Memory<span className="nav-count">{memories.length}</span></button>
          <button className={tab === "automation" ? "nav-item selected" : "nav-item"} onClick={() => setTab("automation")}><Icon name="check"/>Automation<span className="nav-count">{notifications.filter((item) => !item.read_at).length}</span></button>
          <button className={tab === "devices" ? "nav-item selected" : "nav-item"} onClick={() => setTab("devices")}><Icon name="folder"/>Sensors</button>
          <button className={tab === "tools" ? "nav-item selected" : "nav-item"} onClick={() => setTab("tools")}><Icon name="lock"/>Tools & safety</button>
        </nav>
        <div className="history">
          <p className="section-label">RECENT CONVERSATIONS</p>
          {conversations.length === 0 && <p className="muted small">Your chats will appear here.</p>}
          {conversations.slice(0, 8).map((conversation) => (
            <button key={conversation.id} className={activeId === conversation.id && tab === "chat" ? "history-item active" : "history-item"} onClick={() => { setTab("chat"); void loadMessages(conversation.id); }}>
              <Icon name="chat"/><span>{conversation.title}</span>
            </button>
          ))}
        </div>
        <div className="sidebar-bottom">
          <div className="owner-avatar">B</div>
          <div className="owner-copy"><strong>Owner</strong><span>Local session</span></div>
          <button className="quiet-button" title="Sign out" onClick={async () => { await api("/auth/logout", { method: "POST" }); setSignedIn(false); }}>↗</button>
        </div>
      </aside>

      <section className="workspace">
        <header className="topbar">
          <div className="crumb"><span>Workspace</span><span className="slash">/</span><strong>{tab === "chat" ? "Assistant" : tab === "projects" ? "Projects" : tab === "usage" ? "Usage" : tab === "agents" ? "Agents & tasks" : tab === "tools" ? "Tools & safety" : tab === "automation" ? "Automation" : tab === "devices" ? "Sensors" : "Memory"}</strong></div>
          <div className="top-actions"><span className="model-pill"><i className={setup.chat_ready ? "dot green" : "dot amber"}/>{setup.chat_ready ? "Model connected" : "Model paused"}</span><button className="avatar">B</button></div>
        </header>
        <div className="content">
          {error && <div className="notice" role="alert">{error}<button onClick={() => setError("")}>Dismiss</button></div>}
          {tab === "chat" && (
            <div className="chat-page">
              <div className="chat-heading">
                <div><p className="eyebrow">YOUR PRIVATE AI ASSISTANT</p><h1>{activeId ? conversations.find((item) => item.id === activeId)?.title || "Assistant" : "What can I help with?"}</h1><p className="muted">A calm space for your work, projects, and ideas.</p></div>
                <span className={setup.chat_ready ? "status-chip ready" : "status-chip"}><span className="dot"/> {setup.chat_ready ? setup.provider : "Provider not configured"}</span>
              </div>
              <div className="chat-settings">
                <label>Specialist
                  <select value={selectedAgent} onChange={(event) => void updateConversation({ agent_id: event.target.value })}>
                    {agents.map((agent) => <option key={agent.id} value={agent.id}>{agent.name}</option>)}
                  </select>
                </label>
                <label>Project context
                  <select value={selectedProject} onChange={(event) => void updateConversation({ project_id: event.target.value || null })}>
                    <option value="">No project</option>
                    {projects.map((project) => <option key={project.id} value={project.id}>{project.name}</option>)}
                  </select>
                </label>
                <button className="text-button" disabled={!activeId} onClick={() => void saveSummary()}>Save compact summary</button>
              </div>
              {summary && <details className="summary-card"><summary>Saved local conversation summary</summary><p>{summary}</p></details>}              {messages.length === 0 ? (
                <div className="welcome">
                  <div className="welcome-icon"><Icon name="spark"/></div>
                  <h2>Start with one clear question.</h2>
                  <p>{setup.chat_ready ? "Your recent messages are used as context to keep each request focused." : "Chat is paused until a model is configured. Your account, project list, and conversations are ready locally."}</p>
                  <div className="suggestions"><button onClick={() => setPrompt("Help me plan my next work session.")}>Plan my work</button><button onClick={() => setPrompt("Help me choose what to focus on.")}>Review projects</button><button onClick={() => setPrompt("Help me break a big task into small steps.")}>Break down a task</button></div>
                </div>
              ) : (
                <div className="messages">
                  {messages.map((message) => <article key={message.id} className={"message " + message.role}><div className="message-avatar">{message.role === "assistant" ? <Icon name="spark"/> : "B"}</div><div className="message-body"><span className="message-label">{message.role === "assistant" ? "Bikash AI" : "You"}</span><p>{message.content}</p>{message.role === "assistant" && <button className="voice-inline" onClick={() => speakMessage(message.content)}>Read aloud</button>}</div></article>)}
                  {busy && <div className="thinking"><span className="dot green"/>Thinking within your local workspace…</div>}
                </div>
              )}
              <form className="composer" onSubmit={sendMessage}>
                <textarea value={prompt} onChange={(event) => setPrompt(event.target.value)} placeholder={setup.chat_ready ? "Ask something. Keep it focused to save context." : "Configure a model to start chatting."} maxLength={8000} disabled={!setup.chat_ready || busy} rows={2}/>
                <div className="composer-bottom"><span><Icon name="lock"/> Private · 8 messages · 12k chars max</span><div className="composer-actions"><button type="button" className={listening ? "voice-button listening" : "voice-button"} disabled={!setup.chat_ready || busy} onClick={toggleDictation}>{listening ? "Stop dictation" : "Dictate"}</button><button className="send-button" disabled={!setup.chat_ready || !prompt.trim() || busy} aria-label="Send message"><Icon name="send"/></button></div></div>
              </form>
              <p className="disclaimer">Bikash AI can make mistakes. Review important work before acting.</p>
            </div>
          )}

          {tab === "projects" && (
            <div className="section-page">
              <div className="section-heading"><div><p className="eyebrow">KEEP YOUR WORK IN VIEW</p><h1>Projects</h1><p className="muted">A private index of your work.</p></div><span className="count-card">{projects.length}<small>active</small></span></div>
              <form className="project-form" onSubmit={addProject}>
                <h2>Add a project</h2>
                <div className="form-grid"><label>Project name<input value={projectName} onChange={(event) => setProjectName(event.target.value)} placeholder="e.g. Wildlife Management System" required maxLength={120}/></label><label>Local folder path <span className="optional">optional</span><input value={projectPath} onChange={(event) => setProjectPath(event.target.value)} placeholder="C:/Users/you/Projects/…"/></label></div>
                <label>Notes <span className="optional">optional</span><textarea value={projectNotes} onChange={(event) => setProjectNotes(event.target.value)} placeholder="What is this project for?" rows={2}/></label>
                <button className="primary" disabled={busy}><Icon name="plus"/>Add project</button>
              </form>
              <div className="project-list">
                {projects.map((project) => <article key={project.id} className="project-card"><div className="project-icon"><Icon name="folder"/></div><div className="project-copy"><h3>{project.name}</h3>{project.root_path && <p className="path">{project.root_path}</p>}{project.notes && <p className="muted">{project.notes}</p>}</div><button className="text-button" onClick={() => void changeProjectPath(project)}>{project.root_path ? "Change folder" : "Set folder"}</button><button className="text-button" onClick={() => void archiveProject(project.id)}>Archive</button></article>)}
                {!projects.length && <div className="empty-card"><span className="empty-icon"><Icon name="folder"/></span><strong>No projects yet</strong><p>Add one above to make your workspace easier to navigate.</p></div>}
              </div>
            </div>
          )}

          {tab === "agents" && (
            <div className="section-page">
              <div className="section-heading"><div><p className="eyebrow">SPECIALISTS, ONE ORCHESTRATOR</p><h1>Agents & tasks</h1><p className="muted">Local planning and task tracking. Plans do not run tools or take external actions.</p></div><span className="count-card">{agents.length}<small>agents</small></span></div>
              <div className="agent-grid">
                {agents.map((agent) => <article className="agent-card" key={agent.id}><div className="agent-icon"><Icon name={agent.id === "orchestrator" ? "spark" : "brain"}/></div><div><h3>{agent.name}</h3><p>{agent.purpose}</p><small>Permission: analysis and drafts</small></div></article>)}
              </div>
              <form className="project-form agent-form" onSubmit={createAgentPlan}>
                <h2>Plan a task</h2>
                <div className="form-grid">
                  <label>Specialist
                    <select value={planAgent} onChange={(event) => setPlanAgent(event.target.value)}>
                      <option value="auto">Choose automatically</option>
                      {agents.map((agent) => <option key={agent.id} value={agent.id}>{agent.name}</option>)}
                    </select>
                  </label>
                  <label>Project
                    <select value={selectedProject} onChange={(event) => setSelectedProject(event.target.value)}>
                      <option value="">No project</option>
                      {projects.map((project) => <option key={project.id} value={project.id}>{project.name}</option>)}
                    </select>
                  </label>
                </div>
                <label>What should be planned?<textarea value={planRequest} onChange={(event) => setPlanRequest(event.target.value)} maxLength={8000} rows={3} placeholder="Describe the outcome. The local router assigns a specialist; you can change it above."/></label>
                <button className="primary" disabled={busy || !planRequest.trim()}><Icon name="plus"/>Create plan</button>
              </form>
              <div className="task-list">
                <h2 className="table-title">Tracked tasks</h2>
                {!tasks.length && <div className="empty-card"><strong>No tasks yet</strong><p>Create a plan above. You control each step.</p></div>}
                {tasks.map((task) => <article className="task-card" key={task.id}>
                  <div className="task-top"><div><span className="task-agent">{agents.find((agent) => agent.id === task.agent_id)?.name || task.agent_id}</span><h3>{task.title}</h3></div><select value={task.status} onChange={(event) => void updateTaskStatus(task.id, event.target.value)}><option value="planned">Planned</option><option value="in_progress">In progress</option><option value="blocked">Blocked</option><option value="done">Done</option><option value="cancelled">Cancelled</option></select></div>
                  <ol className="task-steps">{task.steps.map((step) => <li key={step.id} className={step.status === "done" ? "step-done" : ""}><span>{step.title}</span><button disabled={step.status === "done"} onClick={() => void completeTaskStep(task.id, step.id)} aria-label={"Complete " + step.title}><Icon name="check"/></button></li>)}</ol>
                </article>)}
              </div>
            </div>
          )}

          {tab === "memory" && (
            <div className="section-page">
              <div className="section-heading"><div><p className="eyebrow">OWNER-CONTROLLED CONTEXT</p><h1>Memory</h1><p className="muted">Nothing is saved automatically. Review, correct, export, or delete every record.</p></div><a className="text-button export-link" href="/api/v1/memories/export" target="_blank" rel="noreferrer">Export JSON</a></div>
              <form className="project-form memory-form" onSubmit={addMemory}>
                <h2>Add a memory</h2>
                <div className="form-grid">
                  <label>Category<select value={memoryCategory} onChange={(event) => setMemoryCategory(event.target.value)}>{["owner_preference","professional_profile","project","technical_decision","business","customer_contact","conversation_summary","task_history","research","operations"].map((value) => <option key={value} value={value}>{value.replaceAll("_"," ")}</option>)}</select></label>
                  <label>Confidence type<select value={memoryKind} onChange={(event) => setMemoryKind(event.target.value)}>{["confirmed","preference","temporary","assumption","unverified"].map((value) => <option key={value}>{value}</option>)}</select></label>
                </div>
                <div className="form-grid">
                  <label>Project<select value={memoryProject} onChange={(event) => setMemoryProject(event.target.value)}><option value="">General memory</option>{projects.map((project) => <option key={project.id} value={project.id}>{project.name}</option>)}</select></label>
                  <label>Title<input value={memoryTitle} onChange={(event) => setMemoryTitle(event.target.value)} required maxLength={160} placeholder="A short, searchable title"/></label>
                </div>
                <label>Memory<textarea value={memoryContent} onChange={(event) => setMemoryContent(event.target.value)} required maxLength={4000} rows={3} placeholder="A fact or preference you want to keep. Do not add passwords or API keys."/></label>
                <button className="primary" disabled={busy}><Icon name="plus"/>Save memory</button>
              </form>
              <div className="memory-toolbar"><form onSubmit={searchMemories}><input value={memoryQuery} onChange={(event) => setMemoryQuery(event.target.value)} placeholder="Search all memory"/><button className="primary">Search</button></form><span>{memories.length} records shown</span></div>
              <div className="memory-list">
                {!memories.length && <div className="empty-card"><strong>No saved memory</strong><p>Add only the facts and preferences that will help later.</p></div>}
                {memories.map((memory) => <article className="memory-card" key={memory.id}>
                  {editingMemory === memory.id ? <div className="memory-edit"><input value={editTitle} onChange={(event) => setEditTitle(event.target.value)} maxLength={160}/><textarea value={editContent} onChange={(event) => setEditContent(event.target.value)} maxLength={4000} rows={3}/><div><button className="primary" onClick={() => void saveMemoryEdit(memory.id)}>Save changes</button><button className="text-button" onClick={() => setEditingMemory("")}>Cancel</button></div></div> : <><div className="memory-card-top"><div><span className="task-agent">{memory.category.replaceAll("_"," ")} · {memory.kind}</span><h3>{memory.title}</h3></div><div><button className="text-button" onClick={() => beginMemoryEdit(memory)}>Edit</button><button className="text-button danger-link" onClick={() => void deleteMemory(memory.id)}>Delete</button></div></div><p>{memory.content}</p><small>Source: {memory.source}{memory.confidence === null ? "" : " · confidence " + Math.round(memory.confidence * 100) + "%"}</small></>}
                </article>)}
              </div>
            </div>
          )}
          {tab === "tools" && (
            <div className="section-page">
              <div className="section-heading"><div><p className="eyebrow">OWNER-GATED LOCAL ACTIONS</p><h1>Tools & safety</h1><p className="muted">Tools run only from your dashboard. Read results as untrusted project data.</p></div><button className={emergencyStop ? "stop-button active" : "stop-button"} onClick={() => void setStop(!emergencyStop)}>{emergencyStop ? "Emergency stop is on" : "Turn on emergency stop"}</button></div>
              <div className="agent-grid">
                {tools.map((tool) => <article className="agent-card tool-card" key={tool.id}><div><span className="task-agent">Risk level {tool.risk_level}</span><h3>{tool.name}</h3><p>{tool.description}</p></div><label className="toggle-label"><input type="checkbox" checked={tool.enabled} onChange={(event) => void setToolEnabled(tool, event.target.checked)}/><span>{tool.enabled ? "On" : "Off"}</span></label></article>)}
              </div>
              <form className="project-form" onSubmit={previewTool}>
                <h2>Prepare an action</h2>
                <div className="form-grid">
                  <label>Tool<select value={toolChoice} onChange={(event) => setToolChoice(event.target.value)}>{tools.filter((tool) => tool.enabled).map((tool) => <option key={tool.id} value={tool.id}>{tool.name}</option>)}</select></label>
                  <label>Project<select value={selectedProject} onChange={(event) => setSelectedProject(event.target.value)}><option value="">Choose a project</option>{projects.map((project) => <option key={project.id} value={project.id}>{project.name}{project.root_path ? "" : " · folder not set"}</option>)}</select></label>
                </div>
                {(["files.list", "files.read", "files.search", "files.create"].includes(toolChoice)) && <label>Relative path<input value={toolPath} onChange={(event) => setToolPath(event.target.value)} maxLength={300} placeholder={toolChoice === "files.list" || toolChoice === "files.search" ? "Optional folder, for example src" : "For example README.md"} required={toolChoice === "files.read" || toolChoice === "files.create"}/></label>}
                {toolChoice === "files.search" && <label>Search text<input value={toolQuery} onChange={(event) => setToolQuery(event.target.value)} maxLength={160} required placeholder="Text to find in project files"/></label>}
                {toolChoice === "files.create" && <label>Exact new file content<textarea value={toolContent} onChange={(event) => setToolContent(event.target.value)} maxLength={20000} rows={6} required placeholder="This exact text is shown and bound to your approval."/></label>}
                <button className="primary" disabled={busy || emergencyStop || !tools.some((tool) => tool.id === toolChoice && tool.enabled)}>Preview action</button>
                {emergencyStop && <p className="muted">The emergency stop is on; previews cannot run until you turn it off.</p>}
              </form>
              {toolResult && <pre className="tool-output">{JSON.stringify(toolResult, null, 2)}</pre>}
              <h2 className="table-title">Action previews and approvals</h2>
              <div className="approval-list">
                {approvals.map((item) => <article className="approval-card" key={item.id}>
                  <div className="task-top"><div><span className="task-agent">{item.tool_id} · risk {item.risk_level}</span><h3>{item.preview}</h3></div><span className={"approval-status status-" + item.status}>{item.status}</span></div>
                  <pre>{JSON.stringify(item.args, null, 2)}</pre>
                  <small>Expires {new Date(item.expires_at).toLocaleString()} · preview hash {item.action_hash.slice(0, 16)}…</small>
                  {item.result && <pre className="tool-output">{JSON.stringify(item.result, null, 2)}</pre>}
                  {(["pending", "approved"].includes(item.status)) && <div className="approval-actions">{item.risk_level >= 2 ? <button className="primary" disabled={busy || emergencyStop} onClick={() => void approveAndRun(item.id)}>Approve exact action and run</button> : <button className="primary" disabled={busy || emergencyStop} onClick={() => void runPreview(item.id)}>Run this preview</button>}<button className="text-button" onClick={() => void cancelPreview(item.id)}>Cancel</button></div>}
                </article>)}
                {!approvals.length && <div className="empty-card"><strong>No actions prepared</strong><p>Choose a local tool above to create a reviewable preview.</p></div>}
              </div>
              <h2 className="table-title automation-subtitle">Workspace health and backup</h2>
              <div className="usage-note"><div className="note-icon"><Icon name="lock"/></div><div><strong>Database {maintenance?.database || "checking"}</strong><p>Schema {maintenance?.schema_version ?? "—"} · {(maintenance?.size_bytes ?? 0).toLocaleString()} bytes · {maintenance?.pending_jobs ?? 0} scheduled reminders</p><a className="text-button" href="/api/v1/maintenance/backup">Download private database snapshot</a><p>The snapshot contains your private workspace data. Store it somewhere private. Offline recovery steps are in <strong>docs/PHASE10.md</strong>.</p></div></div>
            </div>
          )}
          {tab === "automation" && (
            <div className="section-page">
              <div className="section-heading"><div><p className="eyebrow">PERSISTENT, LOCAL SCHEDULING</p><h1>Automation</h1><p className="muted">Reminders are stored in SQLite and delivered to this workspace by the queue worker.</p></div><span className="count-card">{notifications.filter((item) => !item.read_at).length}<small>unread</small></span></div>
              <div className="usage-note"><div className="note-icon"><Icon name="check"/></div><div><strong>Reminder worker</strong><p>For scheduled notifications, keep <code>scripts/run-worker.ps1</code> running in a separate terminal. The worker only creates in-app reminders.</p></div></div>
              <form className="project-form" onSubmit={addReminder}>
                <h2>Schedule a reminder</h2>
                <div className="form-grid"><label>Title<input value={reminderTitle} onChange={(event) => setReminderTitle(event.target.value)} required maxLength={120} placeholder="Review the greenhouse sensors"/></label><label>Time<input type="datetime-local" value={reminderDue} onChange={(event) => setReminderDue(event.target.value)} required/></label></div>
                <div className="form-grid"><label>Details<textarea value={reminderBody} onChange={(event) => setReminderBody(event.target.value)} maxLength={800} rows={2} placeholder="Optional note"/></label><label>Repeat<select value={reminderInterval} onChange={(event) => setReminderInterval(event.target.value)}><option value="0">One time</option><option value="3600">Every hour</option><option value="86400">Every day</option><option value="604800">Every week</option></select></label></div>
                <button className="primary"><Icon name="plus"/>Save reminder</button>
              </form>
              <h2 className="table-title">Scheduled reminders</h2>
              <div className="approval-list">{jobs.filter((job) => job.status === "pending").map((job) => <article className="approval-card" key={job.id}><div className="task-top"><div><h3>{job.title}</h3><p className="muted">{job.payload?.body || "No details"}</p><small>Due {new Date(job.due_at).toLocaleString()}{job.interval_seconds ? " · repeats" : ""}</small></div><button className="text-button" onClick={() => void cancelReminder(job.id)}>Cancel</button></div></article>)}{!jobs.some((job) => job.status === "pending") && <div className="empty-card"><strong>No scheduled reminders</strong><p>Create a reminder above.</p></div>}</div>
              <h2 className="table-title automation-subtitle">Notifications</h2>
              <div className="approval-list">{notifications.map((item) => <article className="approval-card notification-card" key={item.id}><div><span className="task-agent">{item.read_at ? "Read" : "Unread"} · {new Date(item.created_at).toLocaleString()}</span><h3>{item.title}</h3><p className="muted">{item.body}</p></div>{!item.read_at && <button className="text-button" onClick={() => void markNotificationRead(item.id)}>Mark read</button>}</article>)}{!notifications.length && <div className="empty-card"><strong>No notifications yet</strong><p>Completed reminders will appear here.</p></div>}</div>
              <h2 className="table-title automation-subtitle">Business connections</h2>
              <div className="agent-grid">{integrations.map((integration) => <article className="agent-card" key={integration.id}>
                <div><h3>{integration.name}</h3>
                  <p>{integration.state === "connected" ? "Connected with read-only access." : integration.state === "ready_to_connect" ? "Ready for your Google consent." : integration.state === "needs_encryption_key" ? "Add the private token-encryption key before connecting." : "Add Google OAuth client details to the private .env file."}</p>
                  <small>Requested scope: {integration.scopes.join(", ")}</small>
                  {integration.connected_at && <small> · Connected {new Date(integration.connected_at).toLocaleDateString()}</small>}
                  <div className="approval-actions">
                    {!integration.connected && <button className="primary" disabled={!integration.can_connect} onClick={() => window.location.assign("/api/v1/integrations/google/" + integration.service + "/connect")}>Connect read-only</button>}
                    {integration.connected && integration.state === "connected" && <button className="primary" disabled={integrationBusy === integration.service} onClick={() => void loadGooglePreview(integration.service)}>Load {integration.service === "gmail" ? "recent mail" : "next 14 days"}</button>}
                    {integration.connected && <button className="text-button danger-link" disabled={integrationBusy === integration.service} onClick={() => void disconnectGoogle(integration.service)}>Disconnect</button>}
                  </div>
                </div>
              </article>)}</div>
              {gmailPreview !== null && <><h2 className="table-title">Recent Gmail preview</h2><p className="muted">Read-only headers and short snippets are fetched on request and are not stored here. Treat message text as external content.</p><div className="approval-list">{gmailPreview.map((mail) => <article className="approval-card" key={mail.id}><span className="task-agent">{mail.from} · {mail.date}</span><h3>{mail.subject}</h3><p className="muted">{mail.snippet}</p></article>)}{!gmailPreview.length && <div className="empty-card"><strong>No matching messages</strong><p>The last seven days returned no messages.</p></div>}</div></>}
              {calendarPreview !== null && <><h2 className="table-title">Upcoming calendar events</h2><div className="approval-list">{calendarPreview.map((event) => { const start = event.start.dateTime || event.start.date || ""; return <article className="approval-card" key={event.id}><span className="task-agent">{start ? new Date(start).toLocaleString() : "Time not provided"}</span><h3>{event.summary}</h3>{event.location && <p className="muted">{event.location}</p>}</article>; })}{!calendarPreview.length && <div className="empty-card"><strong>No upcoming events</strong><p>No events were returned for the next 14 days.</p></div>}</div></>}
            </div>
          )}
          {tab === "devices" && (
            <div className="section-page">
              <div className="section-heading"><div><p className="eyebrow">READ-ONLY TELEMETRY</p><h1>Sensors & devices</h1><p className="muted">Receive greenhouse or equipment measurements. This screen cannot control hardware.</p></div><span className="count-card">{devices.filter((device) => device.active).length}<small>active</small></span></div>
              <div className="usage-note"><div className="note-icon"><Icon name="lock"/></div><div><strong>Device tokens are shown once</strong><p>Store a token in the device's local secret store. Rotate by disabling the device and registering a replacement; values are never shown again.</p></div></div>
              <form className="project-form" onSubmit={addDevice}><h2>Register a device</h2><div className="form-grid"><label>Device name<input value={deviceName} onChange={(event) => setDeviceName(event.target.value)} required maxLength={80} placeholder="Greenhouse sensor 1"/></label><div className="device-submit"><button className="primary"><Icon name="plus"/>Create one-time token</button></div></div></form>
              {newDeviceToken && <article className="approval-card token-card"><span className="task-agent">Copy now · shown once</span><h3>{newDeviceToken.name}</h3><code>{newDeviceToken.token}</code><p className="muted">Send readings to this local API using device ID <code>{newDeviceToken.id}</code> and an Authorization Bearer token. Setup notes are in the project file <strong>docs/TELEMETRY.md</strong>.</p><button className="text-button" onClick={() => setNewDeviceToken(null)}>I saved it</button></article>}
              <div className="device-grid">{devices.map((device) => <article className="project-form device-card" key={device.id}><div className="task-top"><div><span className="task-agent">{device.active ? "Active" : "Disabled"}</span><h2>{device.name}</h2><small>Device ID: {device.id}</small></div>{device.active && <button className="text-button danger-link" onClick={() => void disableDevice(device.id)}>Disable</button>}</div><div className="sensor-list">{device.latest.map((sample, index) => <div className="sensor-row" key={sample.sensor + sample.recorded_at + index}><span>{sample.sensor}</span><strong>{sample.value} {sample.unit}</strong><small>{new Date(sample.recorded_at).toLocaleString()}</small></div>)}{!device.latest.length && <p className="muted">Waiting for first reading.</p>}</div></article>)}{!devices.length && <div className="empty-card"><strong>No sensor devices</strong><p>Register a device to create its one-time ingestion token.</p></div>}</div>
            </div>
          )}
          {tab === "usage" && (
            <div className="section-page">
              <div className="section-heading"><div><p className="eyebrow">MEASURED, NOT GUESSED</p><h1>Usage</h1><p className="muted">Usage recorded by this workspace. Token values depend on provider reporting.</p></div></div>
              <div className="metric-grid"><article className="metric-card"><span>Requests</span><strong>{usage?.requests ?? 0}</strong><small>model requests recorded</small></article><article className="metric-card"><span>Input tokens</span><strong>{(usage?.prompt_tokens ?? 0).toLocaleString()}</strong><small>reported by provider</small></article><article className="metric-card"><span>Output tokens</span><strong>{(usage?.completion_tokens ?? 0).toLocaleString()}</strong><small>reported by provider</small></article></div>
              <div className="usage-note"><div className="note-icon"><Icon name="spark"/></div><div><strong>Designed to use less context</strong><p>Each request is capped at 8 messages and 12,000 characters. No provider is called unless you configure one.</p></div></div>
              <h2 className="table-title">Providers</h2>
              <div className="provider-row"><span>Active provider</span><strong>{setup.provider === "disabled" ? "None configured" : setup.provider}</strong><span className={setup.chat_ready ? "provider-state ready" : "provider-state"}>{setup.chat_ready ? "Ready" : "Paused"}</span></div>
            </div>
          )}
        </div>
      </section>
    </main>
  );
}
