#!/usr/bin/env node

import { access, mkdir, readFile, writeFile } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import path from 'node:path';
import process from 'node:process';

const VERSION = '0.4.0-pro-bridge';
const MAX_ACTION_LABEL_LENGTH = 80;

const DEFAULT_CONFIG = {
  pollMs: 240000,
  endMarker: 'PRO_RESPONSE_END',
  networkIdleMs: 15000,
  domIdleMs: 30000,
  uiStablePolls: 3,
  timeoutMs: 0,
  monitorStatusPath: '',
  sendStatePath: '',
  projectId: 'PUT_PRO_PROJECT_ID_HERE',
  projectUrl: 'https://chatgpt.com/g/PUT_PRO_PROJECT_ID_HERE/project',
  currentFormalSessionKey: 'session_1',
  expectedConversationId: '',
  projectSessionMode: 'formal',
  requireProjectSessionStatus: true,
  sessionRegistryPath: 'integrations/pro_bridge/runtime/registries/pro_project_sessions.jsonl',
  testSessionRegistryPath: 'integrations/pro_bridge/runtime/registries/pro_test_sessions.jsonl',
  projectSessionStatusPath: '',
  responseWaitMode: 'state_based_completion',
  promptIntegrityMode: 'strict',
  requiredPromptSubstrings: [],
  sendPolicy: 'manual_only',
  sendAuthorizationNonce: '',
  inputSelectors: [
    '#prompt-textarea[contenteditable="true"]',
    'div#prompt-textarea.ProseMirror',
    '[contenteditable="true"][role="textbox"]',
    '[role="textbox"]',
    'textarea'
  ],
  inputRejectSelectors: [
    '.ait-notepad-editor'
  ],
  assistantResponseSelectors: [
    '[data-message-author-role="assistant"]',
    '[data-testid*="assistant"]',
    '[class*="assistant"]',
    '[role="article"]',
    'article',
    '.markdown',
    '.prose'
  ],
  stopGeneratingButtonTexts: ['stop generating', 'stop'],
  sendButtonTexts: ['send'],
  doneButtonTexts: ['regenerate', 'copy'],
  trackedNetworkUrlPatterns: [
    'chatgpt\\.com',
    'chat\\.openai\\.com',
    'openai\\.com',
    '/backend-api/',
    '/conversation',
    '/responses'
  ],
  trackedNetworkResourceTypes: ['Fetch', 'XHR', 'EventSource', 'WebSocket', 'Document'],
  browserWindowLock: {
    source: 'user_provided',
    scope: 'visible_window_identification_only',
    ref: '',
    lockPath: '',
    expectedTargetId: '',
    expectedTitlePattern: '',
    expectedUrlPattern: '',
    expectedProcessId: '',
    expiresMs: 120000
  }
};

class CliError extends Error {
  constructor(message, details = {}, exitCode = 1, status = 'failed') {
    super(message);
    this.name = 'CliError';
    this.details = details;
    this.exitCode = exitCode;
    this.status = status;
  }
}

function normalizeUiText(value) {
  return String(value ?? '').toLowerCase().replace(/\s+/g, ' ').trim();
}

function deriveButtonActionLabel({ ariaLabel = '', title = '', visibleText = '' } = {}) {
  const explicit = normalizeUiText([ariaLabel, title].filter(Boolean).join(' '));
  const visible = normalizeUiText(visibleText);
  if (explicit && explicit.length <= MAX_ACTION_LABEL_LENGTH) {
    return [explicit, visible.length <= MAX_ACTION_LABEL_LENGTH ? visible : ''].filter(Boolean).join(' ');
  }
  if (explicit) return '';
  if (visible.length <= MAX_ACTION_LABEL_LENGTH) return visible;
  return '';
}

function isStopActionLabel(label, stopTexts = DEFAULT_CONFIG.stopGeneratingButtonTexts) {
  const normalized = normalizeUiText(label);
  return stopTexts.map(normalizeUiText).some((needle) => {
    if (!needle) return false;
    if (needle === 'stop' || needle === '停止') return normalized === needle;
    return normalized.includes(needle);
  });
}

function isStopGeneratingActionButton(button, stopTexts = DEFAULT_CONFIG.stopGeneratingButtonTexts) {
  return isStopActionLabel(deriveButtonActionLabel(button), stopTexts);
}

class CdpClient {
  constructor(wsUrl) {
    this.wsUrl = wsUrl;
    this.ws = null;
    this.nextId = 1;
    this.pending = new Map();
    this.eventHandlers = new Map();
  }

  async connect() {
    if (typeof WebSocket === 'undefined') {
      throw new CliError('Node global WebSocket is unavailable. Use Node 22+.', {}, 1, 'blocked_not_found');
    }

    await new Promise((resolve, reject) => {
      const ws = new WebSocket(this.wsUrl);
      this.ws = ws;
      const timeout = setTimeout(() => {
        reject(new CliError('Timed out connecting to browser debug endpoint.', { wsUrl: redactDebugUrl(this.wsUrl) }, 1, 'blocked_not_found'));
      }, 15000);

      ws.addEventListener('open', () => {
        clearTimeout(timeout);
        resolve();
      }, { once: true });

      ws.addEventListener('error', () => {
        clearTimeout(timeout);
        reject(new CliError('Failed to connect to browser debug endpoint.', { wsUrl: redactDebugUrl(this.wsUrl) }, 1, 'blocked_not_found'));
      }, { once: true });

      ws.addEventListener('message', (event) => this.handleMessage(event));
      ws.addEventListener('close', () => this.rejectAll(new CliError('Browser debug endpoint closed.')));
    });
  }

  handleMessage(event) {
    let message;
    try {
      message = JSON.parse(String(event.data));
    } catch {
      return;
    }

    if (message.method) this.dispatchEvent(message);
    if (!message.id) return;
    const pending = this.pending.get(message.id);
    if (!pending) return;
    this.pending.delete(message.id);

    if (message.error) {
      pending.reject(new CliError(`Browser command ${pending.method} failed: ${message.error.message}`, { error: message.error }));
    } else {
      pending.resolve(message.result ?? {});
    }
  }

  rejectAll(error) {
    for (const pending of this.pending.values()) pending.reject(error);
    this.pending.clear();
  }

  send(method, params = {}, sessionId = undefined) {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
      return Promise.reject(new CliError('Browser debug endpoint is not open.', { method }, 1, 'blocked_not_found'));
    }

    const id = this.nextId++;
    const payload = { id, method, params };
    if (sessionId) payload.sessionId = sessionId;

    return new Promise((resolve, reject) => {
      this.pending.set(id, { resolve, reject, method });
      this.ws.send(JSON.stringify(payload));
    });
  }

  async close() {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) this.ws.close();
  }

  on(method, handler) {
    const handlers = this.eventHandlers.get(method) ?? new Set();
    handlers.add(handler);
    this.eventHandlers.set(method, handlers);
    return () => handlers.delete(handler);
  }

  dispatchEvent(message) {
    const handlers = [
      ...(this.eventHandlers.get(message.method) ?? []),
      ...(this.eventHandlers.get('*') ?? [])
    ];
    for (const handler of handlers) {
      try {
        handler(message);
      } catch {
        // Event observers must never break command flow.
      }
    }
  }
}

function usage() {
  return `BitBrowser Pro chat monitor v${VERSION}

Usage:
  node pro_chat_monitor.mjs --help
  node pro_chat_monitor.mjs self-test [--json]
  node pro_chat_monitor.mjs probe --config <config.json> [--json]
  node pro_chat_monitor.mjs targets --config <config.json> [--json]
  node pro_chat_monitor.mjs lock --config <config.json> [--json]
  node pro_chat_monitor.mjs project-sessions --config <config.json> [--json]
  node pro_chat_monitor.mjs fill --config <config.json> [--json]
  node pro_chat_monitor.mjs snapshot --config <config.json> [--json]
  node pro_chat_monitor.mjs watch --config <config.json> [--json]
  node pro_chat_monitor.mjs capture --config <config.json> [--json]
  node pro_chat_monitor.mjs capture-latest --config <config.json> [--json]
  node pro_chat_monitor.mjs validate-prompt --config <config.json> [--json]
  node pro_chat_monitor.mjs validate-response --config <config.json> [--json]
  node pro_chat_monitor.mjs send --config <config.json> --authorization-nonce <nonce> [--json]

Commands:
  probe     Check that the configured browser provider returns a debug endpoint.
  targets   List candidate visible browser page targets. Read-only, no prompt input.
  lock      Lock exactly one user-specified browser window target, or fail closed.
  project-sessions
            Read fixed-project visible chat links and reconcile them with the session registry.
  fill      Fill promptPath into the locked browser window. Does not click send.
  snapshot  Read visible message/state summary from the locked window. No writes.
  watch     Watch the locked browser window until page state proves the visible response is complete.
  capture   Watch, then write the completed response to responsePath.
  capture-latest
            Recovery capture for the latest visible PRO_RESPONSE after a verified send.
  validate-prompt
            Validate promptPath UTF-8 text and mojibake guard before fill/send.
  validate-response
            Validate captured PRO_RESPONSE structure without reading the browser or changing state.
  send      Guarded one-run send. Disabled unless explicitly authorized and input matches prompt.
  self-test Run dependency-free local tests.

Boundary:
  - This tool is for visible browser-window automation only.
  - User-provided process/window hints are local target-lock clues only.
  - fill/watch/capture/send require a valid browser-window lock.
  - watch/capture use observable reply-state completion; timeoutMs 0 means no fixed total wait.
  - Final send is manual by default unless the current run explicitly authorizes it.
`;
}

function parseArgs(argv) {
  const args = { command: '', config: '', json: false, authorizationNonce: '' };
  const rest = [...argv];

  while (rest.length) {
    const item = rest.shift();
    if (item === '--help' || item === '-h') args.command = 'help';
    else if (item === '--json') args.json = true;
    else if (item === '--config') args.config = rest.shift() ?? '';
    else if (item?.startsWith('--config=')) args.config = item.slice('--config='.length);
    else if (item === '--authorization-nonce' || item === '--nonce') args.authorizationNonce = rest.shift() ?? '';
    else if (item?.startsWith('--authorization-nonce=')) args.authorizationNonce = item.slice('--authorization-nonce='.length);
    else if (item?.startsWith('--nonce=')) args.authorizationNonce = item.slice('--nonce='.length);
    else if (!args.command) args.command = item;
    else throw new CliError(`Unknown argument: ${item}`);
  }

  if (!args.command) args.command = 'help';
  return args;
}

async function readConfig(configPath) {
  if (!configPath) throw new CliError('Missing --config <config.json>.');

  let raw;
  try {
    raw = await readFile(configPath, 'utf8');
  } catch (error) {
    throw new CliError('Config file cannot be read.', { configPath, cause: error.message });
  }

  let parsed;
  try {
    parsed = JSON.parse(raw.replace(/^\uFEFF/, ''));
  } catch (error) {
    throw new CliError('Config file is not valid JSON.', { configPath, cause: error.message });
  }

  const config = mergeConfig(DEFAULT_CONFIG, parsed);
  validateConfig(config);
  config.configPath = path.resolve(configPath);
  config.promptPath = path.resolve(config.promptPath);
  config.responsePath = path.resolve(config.responsePath);
  if (config.monitorStatusPath) config.monitorStatusPath = path.resolve(config.monitorStatusPath);
  config.sessionRegistryPath = path.resolve(config.sessionRegistryPath);
  config.projectSessionStatusPath = config.projectSessionStatusPath
    ? path.resolve(config.projectSessionStatusPath)
    : path.join(path.dirname(config.responsePath), 'PROJECT_SESSION_STATUS.json');
  config.browserWindowLock.lockPath = resolveLockPath(config);
  return config;
}

function mergeConfig(defaults, input) {
  const lockInput = input.browserWindowLock ?? {};
  return {
    ...defaults,
    ...input,
    inputSelectors: input.inputSelectors ?? defaults.inputSelectors,
    inputRejectSelectors: input.inputRejectSelectors ?? defaults.inputRejectSelectors,
    assistantResponseSelectors: input.assistantResponseSelectors ?? defaults.assistantResponseSelectors,
    stopGeneratingButtonTexts: input.stopGeneratingButtonTexts ?? defaults.stopGeneratingButtonTexts,
    sendButtonTexts: input.sendButtonTexts ?? defaults.sendButtonTexts,
    doneButtonTexts: input.doneButtonTexts ?? defaults.doneButtonTexts,
    requiredPromptSubstrings: input.requiredPromptSubstrings ?? defaults.requiredPromptSubstrings,
    trackedNetworkUrlPatterns: input.trackedNetworkUrlPatterns ?? defaults.trackedNetworkUrlPatterns,
    trackedNetworkResourceTypes: input.trackedNetworkResourceTypes ?? defaults.trackedNetworkResourceTypes,
    browserWindowLock: {
      ...defaults.browserWindowLock,
      ...lockInput
    }
  };
}

function validateConfig(config) {
  const missing = [];
  for (const key of ['apiBase', 'profileId', 'promptPath', 'responsePath']) {
    if (!config[key] || typeof config[key] !== 'string') missing.push(key);
  }
  if (missing.length) throw new CliError('Config is missing required fields.', { missing });

  for (const key of ['pollMs', 'networkIdleMs', 'domIdleMs', 'uiStablePolls']) {
    if (!Number.isFinite(Number(config[key])) || Number(config[key]) <= 0) {
      throw new CliError(`Config field ${key} must be a positive number.`);
    }
    config[key] = Number(config[key]);
  }
  if (!Number.isFinite(Number(config.timeoutMs)) || Number(config.timeoutMs) !== 0) {
    throw new CliError('Config field timeoutMs must be 0. Pro reply monitoring is state-based and must not use a fixed total wait timeout.');
  }
  config.timeoutMs = Number(config.timeoutMs);
  if (config.responseWaitMode !== 'state_based_completion') {
    throw new CliError('responseWaitMode must be state_based_completion.');
  }

  for (const key of ['inputSelectors', 'inputRejectSelectors', 'assistantResponseSelectors', 'trackedNetworkUrlPatterns', 'trackedNetworkResourceTypes']) {
    if (!Array.isArray(config[key]) || !config[key].every((value) => typeof value === 'string' && value.trim())) {
      throw new CliError(`Config field ${key} must be a non-empty string array.`);
    }
  }
  if (typeof config.endMarker !== 'string') throw new CliError('Config field endMarker must be a string.');
  if (typeof config.projectId !== 'string' || !config.projectId.trim()) throw new CliError('Config field projectId must be a non-empty string.');
  if (!['formal', 'test_only', 'read_only'].includes(config.projectSessionMode)) {
    throw new CliError('projectSessionMode must be formal, test_only, or read_only.');
  }
  if (typeof config.requireProjectSessionStatus !== 'boolean') {
    throw new CliError('requireProjectSessionStatus must be a boolean.');
  }

  const lock = config.browserWindowLock;
  if (!lock || typeof lock !== 'object') throw new CliError('browserWindowLock must be an object.');
  if (lock.source !== 'user_provided') throw new CliError('browserWindowLock.source must be user_provided.');
  if (lock.scope !== 'visible_window_identification_only') throw new CliError('browserWindowLock.scope must be visible_window_identification_only.');
  lock.expiresMs = Number(lock.expiresMs || DEFAULT_CONFIG.browserWindowLock.expiresMs);
  if (!Number.isFinite(lock.expiresMs) || lock.expiresMs <= 0) {
    throw new CliError('browserWindowLock.expiresMs must be a positive number.');
  }
}

function resolveLockPath(config) {
  const configured = config.browserWindowLock?.lockPath;
  if (configured && typeof configured === 'string') return path.resolve(configured);
  return path.join(path.dirname(path.resolve(config.responsePath)), 'BROWSER_WINDOW_LOCK.json');
}

async function postJson(apiBase, endpoint, body) {
  const url = new URL(endpoint, ensureTrailingSlash(apiBase)).toString();
  const response = await fetch(url, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify(body)
  });

  const text = await response.text();
  let json;
  try {
    json = text ? JSON.parse(text) : {};
  } catch {
    throw new CliError('Browser provider returned non-JSON data.', { url, status: response.status, bodyPreview: text.slice(0, 200) });
  }

  if (!response.ok) {
    throw new CliError('Browser provider request failed.', { url, status: response.status, response: json }, 1, 'blocked_not_found');
  }
  if (json.success === false) {
    throw new CliError('Browser provider reported failure.', { url, response: json }, 1, 'blocked_not_found');
  }
  return json;
}

async function openBitBrowser(config) {
  const response = await postJson(config.apiBase, '/browser/open', {
    id: config.profileId,
    queue: true
  });

  const endpoints = collectDebugEndpoints(response.data ?? response);
  if (!endpoints.ws.length && !endpoints.http.length) {
    throw new CliError('No usable browser debug endpoint found.', { responseShape: summarizeShape(response) }, 1, 'blocked_not_found');
  }
  return { response, endpoints };
}

function collectDebugEndpoints(value, keyHint = '', out = { ws: [], http: [], driver: [] }) {
  if (typeof value === 'string') {
    const trimmed = value.trim();
    if (/^wss?:\/\//i.test(trimmed)) out.ws.push(trimmed);
    if (/^https?:\/\//i.test(trimmed)) out.http.push(trimmed);
    if (keyHint.toLowerCase().includes('http') && /^[\w.-]+:\d+/.test(trimmed)) out.http.push(`http://${trimmed}`);
    if (keyHint.toLowerCase().includes('driver')) out.driver.push(trimmed);
  } else if (Array.isArray(value)) {
    for (const item of value) collectDebugEndpoints(item, keyHint, out);
  } else if (value && typeof value === 'object') {
    for (const [key, item] of Object.entries(value)) collectDebugEndpoints(item, key, out);
  }

  out.ws = [...new Set(out.ws)];
  out.http = [...new Set(out.http)];
  out.driver = [...new Set(out.driver)];
  return out;
}

async function listTargets(config) {
  const { response, endpoints } = await openBitBrowser(config);
  const targets = [];

  for (const httpEndpoint of endpoints.http) {
    const base = httpEndpoint.replace(/\/+$/, '');
    try {
      const listResponse = await fetch(`${base}/json/list`);
      if (listResponse.ok) {
        const pages = await listResponse.json();
        for (const target of pages) {
          if (target.type === 'page') {
            targets.push(normalizeTarget(target, 'http-json-list'));
          }
        }
      }
    } catch {
      // Try other endpoints.
    }
  }

  if (!targets.length) {
    for (const wsEndpoint of endpoints.ws) {
      if (!wsEndpoint.includes('/devtools/browser/')) continue;
      const cdp = new CdpClient(wsEndpoint);
      try {
        await cdp.connect();
        const result = await cdp.send('Target.getTargets');
        for (const target of result.targetInfos ?? []) {
          if (target.type === 'page') targets.push(normalizeTarget(target, 'browser-targets'));
        }
      } finally {
        await cdp.close();
      }
    }
  }

  return {
    openResponse: response,
    endpoints,
    targets: dedupeTargets(targets)
  };
}

function normalizeTarget(target, source) {
  return {
    targetId: target.id ?? target.targetId ?? '',
    type: target.type ?? 'page',
    title: target.title ?? '',
    url: target.url ?? '',
    source,
    webSocketDebuggerUrl: target.webSocketDebuggerUrl ?? ''
  };
}

function dedupeTargets(targets) {
  const seen = new Set();
  const out = [];
  for (const target of targets) {
    const key = target.targetId || `${target.title}|${target.url}`;
    if (seen.has(key)) continue;
    seen.add(key);
    out.push(target);
  }
  return out;
}

function getLockHints(lock) {
  return {
    expectedTargetId: String(lock.expectedTargetId ?? '').trim(),
    expectedTitlePattern: String(lock.expectedTitlePattern ?? '').trim(),
    expectedUrlPattern: String(lock.expectedUrlPattern ?? '').trim(),
    expectedProcessId: String(lock.expectedProcessId ?? '').trim(),
    ref: String(lock.ref ?? '').trim()
  };
}

function hasUsableLockHint(lock) {
  const hints = getLockHints(lock);
  return Boolean(hints.expectedTargetId || hints.expectedTitlePattern || hints.expectedUrlPattern || hints.ref);
}

function assertUsableLockHint(config) {
  const lock = config.browserWindowLock;
  if (hasUsableLockHint(lock)) return;
  const hints = getLockHints(lock);
  throw new CliError(
    'No usable browser-window lock clue is configured. Provide a user-supplied target id, title pattern, URL pattern, or local ref.',
    { lockSource: lock.source, lockScope: lock.scope, processHintPresent: Boolean(hints.expectedProcessId) },
    1,
    'blocked_not_found'
  );
}

function assertFormalLockHintNotFuzzy(config) {
  if (config.projectSessionMode !== 'formal') return;
  const hints = getLockHints(config.browserWindowLock);
  if (hints.expectedTargetId) return;
  const pattern = hints.expectedUrlPattern;
  if (pattern && pattern.includes(config.projectId) && pattern.includes('/c/')) {
    if (config.expectedConversationId && !pattern.includes(config.expectedConversationId)) {
      throw new CliError(
        'Formal Pro actions require the lock URL pattern to include the exact registered conversation id.',
        {
          projectSessionMode: config.projectSessionMode,
          currentFormalSessionKey: config.currentFormalSessionKey,
          expectedConversationId: config.expectedConversationId,
          hasExpectedTargetId: Boolean(hints.expectedTargetId),
          hasExpectedUrlPattern: Boolean(pattern)
        },
        1,
        'blocked_target_lock_fuzzy'
      );
    }
    return;
  }
  throw new CliError(
    'Formal Pro actions require an exact target id or a project conversation URL pattern; title/ref-only locking is too fuzzy.',
    {
      projectSessionMode: config.projectSessionMode,
      currentFormalSessionKey: config.currentFormalSessionKey,
      hasExpectedTargetId: Boolean(hints.expectedTargetId),
      hasExpectedUrlPattern: Boolean(pattern),
      hasTitlePattern: Boolean(hints.expectedTitlePattern),
      hasRef: Boolean(hints.ref)
    },
    1,
    'blocked_target_lock_fuzzy'
  );
}

function filterTargetsByLock(targets, lock) {
  const hints = getLockHints(lock);
  let candidates = [...targets];

  if (hints.expectedTargetId) {
    candidates = candidates.filter((target) => target.targetId === hints.expectedTargetId);
  }
  if (hints.expectedTitlePattern) {
    const regex = new RegExp(hints.expectedTitlePattern, 'i');
    candidates = candidates.filter((target) => regex.test(target.title ?? ''));
  }
  if (hints.expectedUrlPattern) {
    const regex = new RegExp(hints.expectedUrlPattern, 'i');
    candidates = candidates.filter((target) => regex.test(target.url ?? ''));
  }
  if (hints.ref && !hints.expectedTargetId && !hints.expectedTitlePattern && !hints.expectedUrlPattern) {
    const lower = hints.ref.toLowerCase();
    candidates = candidates.filter((target) => {
      return String(target.targetId).toLowerCase().includes(lower)
        || String(target.title).toLowerCase().includes(lower)
        || String(target.url).toLowerCase().includes(lower);
    });
  }

  return candidates;
}

async function writeLockFile(config, target) {
  const now = new Date();
  const expiresAt = new Date(now.getTime() + config.browserWindowLock.expiresMs);
  const lock = {
    status: 'locked',
    browser_window_lock_status: 'locked',
    browser_window_lock_source: 'user_provided',
    browser_window_lock_scope: 'visible_window_identification_only',
    createdAt: now.toISOString(),
    expiresAt: expiresAt.toISOString(),
    target: {
      targetId: target.targetId,
      title: target.title,
      url: target.url,
      source: target.source
    },
    hintHash: sha256(JSON.stringify(getLockHints(config.browserWindowLock)))
  };

  await mkdir(path.dirname(config.browserWindowLock.lockPath), { recursive: true });
  await writeFile(config.browserWindowLock.lockPath, JSON.stringify(lock, null, 2), 'utf8');
  return lock;
}

async function loadLockFile(config) {
  const lockPath = config.browserWindowLock.lockPath;
  try {
    await access(lockPath);
  } catch {
    throw new CliError('Browser window is not locked. Run targets/lock first with a user-provided window clue.', { lockPath }, 1, 'blocked_not_found');
  }

  let lock;
  try {
    lock = JSON.parse(await readFile(lockPath, 'utf8'));
  } catch (error) {
    throw new CliError('Browser window lock file is invalid.', { lockPath, cause: error.message }, 1, 'blocked_not_found');
  }

  if (lock.status !== 'locked' || !lock.target?.targetId) {
    throw new CliError('Browser window lock is not valid.', { lockPath }, 1, 'blocked_not_found');
  }
  if (Date.parse(lock.expiresAt) <= Date.now()) {
    throw new CliError('Browser window lock expired.', { lockPath, expiresAt: lock.expiresAt }, 1, 'blocked_not_found');
  }
  return lock;
}

async function commandProbe(config) {
  const { endpoints } = await openBitBrowser(config);
  return {
    status: 'probe_passed',
    bitbrowser_probe_status: 'probe_passed',
    endpoints: redactEndpoints(endpoints),
    boundary: 'probe_only_no_page_action'
  };
}

async function commandTargets(config) {
  const result = await listTargets(config);
  return {
    status: 'targets_listed',
    browser_window_lock_status: hasUsableLockHint(config.browserWindowLock) ? 'user_hint_provided' : 'not_requested',
    endpoints: redactEndpoints(result.endpoints),
    targets: result.targets.map(redactTarget)
  };
}

async function commandLock(config) {
  assertUsableLockHint(config);
  assertFormalLockHintNotFuzzy(config);
  const result = await listTargets(config);
  const candidates = filterTargetsByLock(result.targets, config.browserWindowLock);

  if (!candidates.length) {
    throw new CliError('No browser page target matched the user-provided window clue.', {
      browser_window_lock_scope: 'visible_window_identification_only',
      candidateCount: result.targets.length,
      hintSummary: summarizeLockHints(config.browserWindowLock)
    }, 1, 'blocked_not_found');
  }

  if (candidates.length > 1) {
    throw new CliError('More than one browser page target matched the user-provided window clue.', {
      browser_window_lock_scope: 'visible_window_identification_only',
      candidateCount: candidates.length,
      candidates: candidates.map(redactTarget)
    }, 1, 'blocked_ambiguous');
  }

  const lock = await writeLockFile(config, candidates[0]);
  return {
    status: 'locked',
    browser_window_lock_status: 'locked',
    browser_window_lock_source: 'user_provided',
    browser_window_lock_scope: 'visible_window_identification_only',
    lockPath: config.browserWindowLock.lockPath,
    expiresAt: lock.expiresAt,
    target: redactTarget(candidates[0])
  };
}

async function commandProjectSessions(config) {
  await loadLockFile(config);
  const { cdp, sessionId, target } = await createLockedPageSession(config);
  const pageState = await evaluateJson(cdp, sessionId, buildProjectSessionsExpression(config));
  await cdp.close();

  if (!pageState?.projectMatched) {
    throw new CliError('Locked page is not inside the fixed Pro project.', {
      projectId: config.projectId,
      url: pageState?.url ?? '',
      title: pageState?.title ?? '',
      target: redactTarget(target)
    }, 1, 'blocked_project_session_mismatch');
  }

  const registry = await readSessionRegistry(config);
  const status = reconcileProjectSessions(config, pageState, registry);
  await writeProjectSessionStatus(config, status);
  return {
    ...status,
    target: redactTarget(target),
    statusPath: config.projectSessionStatusPath
  };
}

async function createLockedPageSession(config) {
  const lock = await loadLockFile(config);
  const { endpoints } = await openBitBrowser(config);
  const targetId = lock.target.targetId;

  for (const httpEndpoint of endpoints.http) {
    const base = httpEndpoint.replace(/\/+$/, '');
    try {
      const listResponse = await fetch(`${base}/json/list`);
      if (!listResponse.ok) continue;
      const targets = await listResponse.json();
      const target = targets.map((item) => normalizeTarget(item, 'http-json-list')).find((item) => item.targetId === targetId);
      if (target?.webSocketDebuggerUrl) {
        const cdp = new CdpClient(target.webSocketDebuggerUrl);
        await cdp.connect();
        await safeSend(cdp, 'Runtime.enable');
        await safeSend(cdp, 'Page.enable');
        await safeSend(cdp, 'Network.enable');
        return { cdp, sessionId: undefined, target, lock };
      }
    } catch {
      // Try browser endpoint below.
    }
  }

  for (const wsEndpoint of endpoints.ws) {
    if (!wsEndpoint.includes('/devtools/browser/')) continue;
    const cdp = new CdpClient(wsEndpoint);
    try {
      await cdp.connect();
      const targetsResult = await cdp.send('Target.getTargets');
      const target = (targetsResult.targetInfos ?? []).map((item) => normalizeTarget(item, 'browser-targets')).find((item) => item.targetId === targetId);
      if (!target) {
        await cdp.close();
        continue;
      }
      const attach = await cdp.send('Target.attachToTarget', { targetId, flatten: true });
      await safeSend(cdp, 'Runtime.enable', {}, attach.sessionId);
      await safeSend(cdp, 'Page.enable', {}, attach.sessionId);
      await safeSend(cdp, 'Network.enable', {}, attach.sessionId);
      return { cdp, sessionId: attach.sessionId, target, lock };
    } catch (error) {
      await cdp.close();
      throw error;
    }
  }

  throw new CliError('Locked browser page target was not found in the current browser target list.', { targetId }, 1, 'blocked_not_found');
}

async function safeSend(cdp, method, params = {}, sessionId = undefined) {
  try {
    return await cdp.send(method, params, sessionId);
  } catch {
    return null;
  }
}

async function evaluateJson(cdp, sessionId, expression) {
  const result = await cdp.send('Runtime.evaluate', {
    expression,
    awaitPromise: true,
    returnByValue: true
  }, sessionId);

  if (result.exceptionDetails) {
    throw new CliError('Page evaluation failed.', { exception: result.exceptionDetails.text });
  }
  return result.result?.value;
}

async function commandFill(config) {
  await loadLockFile(config);
  const prompt = await readFile(config.promptPath, 'utf8');
  if (!prompt.trim()) throw new CliError('Prompt file is empty.', { promptPath: config.promptPath });
  const promptIntegrity = assertPromptIntegrity(prompt, config, 'promptPath');

  const { cdp, sessionId, target } = await createLockedPageSession(config);
  const projectSessionStatus = await requireProjectSessionStatus(config, 'fill');
  verifyProjectSessionForUrl(config, projectSessionStatus, target.url, 'fill');
  const focus = await evaluateJson(cdp, sessionId, buildFocusInputExpression(config));
  if (!focus?.found) {
    await cdp.close();
    throw new CliError('No visible Pro chat input was found in the locked browser window.', { checkedSelectors: config.inputSelectors });
  }

  await cdp.send('Input.insertText', { text: prompt }, sessionId);
  const verify = await evaluateJson(cdp, sessionId, buildActiveInputExpression());
  await cdp.close();

  return {
    status: 'prompt_filled_waiting_user_send',
    pro_chat_send_status: 'prompt_filled_waiting_user_send',
    browser_window_lock_status: 'locked',
    target: redactTarget(target),
    input: focus,
    promptLength: prompt.length,
    promptIntegrity,
    activeInputLength: verify?.length ?? 0,
    sendBoundary: 'User must manually click send or explicitly authorize guarded send in this run.'
  };
}

async function commandWatch(config) {
  await loadLockFile(config);
  const { cdp, sessionId, target } = await createLockedPageSession(config);
  const result = await waitForStableResponse(cdp, sessionId, config);
  await cdp.close();
  return { ...withoutResponseText(result), target: redactTarget(target), browser_window_lock_status: 'locked' };
}

async function commandCapture(config) {
  await loadLockFile(config);
  const { cdp, sessionId, target } = await createLockedPageSession(config);
  const result = await waitForStableResponse(cdp, sessionId, config);
  await cdp.close();

  if (result.status !== 'response_captured_high_confidence') {
    return {
      ...withoutResponseText(result),
      target: redactTarget(target),
      browser_window_lock_status: 'locked',
      responsePath: config.responsePath,
      note: 'Response was not written because completion was uncertain.'
    };
  }

  return await writeCapturedResponse(config, target, result);
}

async function commandSnapshot(config) {
  await loadLockFile(config);
  const { cdp, sessionId, target } = await createLockedPageSession(config);
  const snapshot = await getSnapshot(cdp, sessionId, config);
  await cdp.close();

  const assistantMessages = snapshot.assistantMessages ?? [];
  const tail = assistantMessages.slice(-5).map((message) => ({
    id: message.id,
    index: message.index,
    selector: message.selector,
    length: message.length ?? message.text?.length ?? 0,
    hash: message.hash,
    startsWithProResponse: String(message.text ?? '').trim().startsWith('PRO_RESPONSE:'),
    hasEndMarker: Boolean(config.endMarker && String(message.text ?? '').includes(config.endMarker)),
    preview: compactPreview(message.text ?? '', 240)
  }));

  return {
    status: 'snapshot',
    browser_window_lock_status: 'locked',
    target: redactTarget(target),
    url: snapshot.url,
    title: snapshot.title,
    assistantMessageCount: assistantMessages.length,
    lastAssistantHash: assistantMessages[assistantMessages.length - 1]?.hash ?? '',
    lastAssistantLength: assistantMessages[assistantMessages.length - 1]?.length ?? assistantMessages[assistantMessages.length - 1]?.text?.length ?? 0,
    pageSignals: snapshot.pageSignals,
    replyDomState: snapshot.replyDomState,
    assistantTail: tail
  };
}

async function commandCaptureLatest(config) {
  await loadLockFile(config);
  const { cdp, sessionId, target } = await createLockedPageSession(config);
  const snapshot = await getSnapshot(cdp, sessionId, config);
  await cdp.close();
  const projectSessionStatus = await requireProjectSessionStatus(config, 'capture-latest');
  verifyProjectSessionForUrl(config, projectSessionStatus, snapshot.url, 'capture-latest');

  const messages = snapshot.assistantMessages ?? [];
  const proResponseCandidates = messages.filter((message) => String(message.text ?? '').trim().startsWith('PRO_RESPONSE:'));
  const selected = proResponseCandidates[proResponseCandidates.length - 1] ?? null;
  if (!selected) {
    throw new CliError('No visible assistant message starts with PRO_RESPONSE:.', {
      assistantMessageCount: messages.length,
      pageSignals: snapshot.pageSignals
    }, 1, 'blocked_not_found');
  }
  if (!isRealAssistantMessageNode(selected)) {
    throw new CliError('Latest visible Pro response is not safe to capture because it is not a real assistant message node.', {
      pageSignals: snapshot.pageSignals,
      selectedAnchor: selected.id,
      selectedRole: selected.role,
      dataMessageId: selected.dataMessageId,
      dataTurnStartMessage: selected.dataTurnStartMessage,
      finalizing: selected.finalizing,
      thinking: selected.thinking,
      placeholderState: selected.placeholderState
    }, 1, 'blocked_completion_uncertain');
  }

  const completionSignal = 'real_assistant_message_node_stable_recovered_latest_pro_response';
  const result = {
    status: 'response_captured_high_confidence',
    pro_response_capture_status: 'response_captured_high_confidence',
    pro_response_wait_mode: 'state_based_completion',
    reply_lifecycle_status: 'response_captured_high_confidence',
    responseText: selected.text,
    responseHash: selected.hash,
    responseLength: selected.text.length,
    completionSignal,
    completion_confidence: 'high',
    end_marker_present: Boolean(config.endMarker && selected.text.includes(config.endMarker)),
    assistant_message_anchor: selected.id,
    assistant_candidate_count: proResponseCandidates.length,
    latest_assistant_index: messages[messages.length - 1]?.index ?? -1,
    selected_anchor_reason: 'latest_visible_pro_response_recovery',
    anchor_switched: false,
    previous_anchor: null,
    network_stream_active: 'unknown',
    network_last_activity_at: '',
    network_blocking_effective: false,
    ui_completion_signals: snapshot.pageSignals,
    pageSignals: snapshot.pageSignals,
    reply_state: {
      reply_lifecycle_status: 'response_captured_high_confidence',
      assistant_message_anchor: selected.id,
      assistant_message_index: selected.index,
      assistant_candidate_count: proResponseCandidates.length,
      latest_assistant_index: messages[messages.length - 1]?.index ?? -1,
      selected_anchor_reason: 'latest_visible_pro_response_recovery',
      assistant_text_length: selected.text.length,
      assistant_text_hash: selected.hash,
      ui_completion_signals: snapshot.pageSignals,
      end_marker_present: Boolean(config.endMarker && selected.text.includes(config.endMarker)),
      completion_confidence: 'high',
      completion_signal: completionSignal
    },
    url: snapshot.url,
    title: snapshot.title
  };

  await writeMonitorStatus(config, withoutResponseText(result));
  return await writeCapturedResponse(config, target, result);
}

async function writeCapturedResponse(config, target, result) {
  const responseText = result.responseText;
  const hash = sha256(responseText);
  const capturedAt = new Date().toISOString();
  const body = [
    '# Pro Response Capture',
    '',
    `captured_at: ${capturedAt}`,
    'status: response_captured_high_confidence',
    `response_hash_sha256: ${hash}`,
    `response_length: ${responseText.length}`,
    `completion_confidence: ${result.completion_confidence}`,
    `completion_signal: ${result.completionSignal}`,
    `end_marker_present: ${result.end_marker_present}`,
    `assistant_message_anchor: ${result.assistant_message_anchor}`,
    '',
    '---',
    '',
    responseText
  ].join('\n');

  await mkdir(path.dirname(config.responsePath), { recursive: true });
  await writeFile(config.responsePath, body, 'utf8');

  return {
    status: 'response_captured_high_confidence',
    pro_response_capture_status: 'response_captured_high_confidence',
    pro_response_wait_mode: 'state_based_completion',
    reply_lifecycle_status: 'response_captured_high_confidence',
    browser_window_lock_status: 'locked',
    responsePath: config.responsePath,
    responseHash: hash,
    responseLength: responseText.length,
    capturedAt,
    completion_confidence: result.completion_confidence,
    end_marker_present: result.end_marker_present,
    assistant_message_anchor: result.assistant_message_anchor,
    target: redactTarget(target),
    completion: withoutResponseText(result)
  };
}

function validateFormalResponseText(raw, config = DEFAULT_CONFIG) {
  const proIndex = String(raw ?? '').indexOf('PRO_RESPONSE:');
  if (proIndex < 0) {
    return {
      status: 'missing_required_marker',
      pro_response_formal_status: 'invalid',
      pro_response_schema_status: 'missing_required_marker',
      errors: ['missing PRO_RESPONSE: marker'],
      findingIds: [],
      findingCount: 0
    };
  }

  const body = String(raw).slice(proIndex).trim();
  const errors = [];
  const confidenceMatch = body.match(/^confidence_percent:\s*(\d{1,3})\s*$/im);
  const confidencePercent = confidenceMatch ? Number(confidenceMatch[1]) : null;
  if (confidencePercent === null || confidencePercent < 0 || confidencePercent > 100) {
    errors.push('missing or invalid confidence_percent');
  }

  const confidentMatch = body.match(/^is_100_percent_confident:\s*(yes|no|true|false)\s*$/im);
  const is100 = confidentMatch ? /^(yes|true)$/i.test(confidentMatch[1]) : null;
  if (is100 === null) errors.push('missing is_100_percent_confident');

  const requiredSections = [
    ['overall_judgment', 'overall_verdict'],
    ['all_findings'],
    ['fix_order'],
    ['remaining_unknowns']
  ];
  for (const aliases of requiredSections) {
    if (!aliases.some((section) => new RegExp(`^${section}:`, 'im').test(body))) {
      errors.push(`missing ${aliases.join(' or ')}`);
    }
  }

  const findingIds = [...body.matchAll(/^\s*(?:-\s*)?id:\s*([A-Z0-9]+-[Pp][0-2]-\d+|[Pp][0-2]-\d+)\s*$/gm)].map((match) => match[1]);
  const severities = [...body.matchAll(/^\s*severity:\s*(P0|P1|P2)\s*$/gim)].map((match) => match[1].toUpperCase());
  if (findingIds.length !== severities.length) errors.push('finding id/severity count mismatch');
  if (is100 === false && findingIds.length === 0) errors.push('not 100 percent but no findings listed');
  if (is100 === true && findingIds.length > 0) errors.push('100 percent response contains findings');

  const endMarkerPresent = Boolean(config.endMarker && body.includes(config.endMarker));
  const schemaStatus = errors.length ? 'missing_required_fields' : 'schema_valid';
  return {
    status: schemaStatus,
    pro_response_formal_status: errors.length ? 'invalid' : 'valid',
    pro_response_schema_status: schemaStatus,
    errors,
    confidencePercent,
    is100PercentConfident: is100,
    endMarkerPresent,
    findingIds,
    findingCount: findingIds.length,
    severityCounts: {
      P0: severities.filter((item) => item === 'P0').length,
      P1: severities.filter((item) => item === 'P1').length,
      P2: severities.filter((item) => item === 'P2').length
    }
  };
}

function validatePromptIntegrityText(raw, config = DEFAULT_CONFIG) {
  const text = String(raw ?? '');
  const errors = [];
  const warnings = [];
  const commonMojibakeFragments = [
    String.fromCharCode(0x5bb8, 0x30e4, 0x7dbd),
    String.fromCharCode(0x937c, 0x6edb),
    String.fromCharCode(0x9366, 0x6ec4),
    String.fromCharCode(0x95c1, 0x63d2)
  ];
  const badPatterns = [
    { id: 'replacement_character', regex: /\uFFFD/u, description: 'contains Unicode replacement character' },
    { id: 'question_mark_mojibake', regex: /\?{3,}/u, description: 'contains repeated question marks that usually indicate mojibake' },
    { id: 'common_cn_mojibake', regex: new RegExp(commonMojibakeFragments.map(escapeRegExp).join('|'), 'u'), description: 'contains common Chinese mojibake fragments' }
  ];

  if (!text.trim()) errors.push('prompt is empty');
  for (const item of badPatterns) {
    if (item.regex.test(text)) errors.push(`${item.id}: ${item.description}`);
  }

  const required = Array.isArray(config.requiredPromptSubstrings) ? config.requiredPromptSubstrings : [];
  for (const fragment of required) {
    if (fragment && !text.includes(fragment)) {
      errors.push(`missing required prompt substring: ${fragment}`);
    }
  }

  if (text.includes('PRO_RESPONSE:') && !text.includes('confidence_percent')) {
    warnings.push('prompt contains PRO_RESPONSE marker but not the expected response schema hint');
  }

  return {
    status: errors.length ? 'blocked_prompt_integrity_failed' : 'prompt_integrity_passed',
    prompt_integrity_status: errors.length ? 'failed' : 'passed',
    errors,
    warnings,
    promptHash: sha256(text),
    promptLength: text.length,
    requiredPromptSubstringCount: required.length
  };
}

function assertPromptIntegrity(raw, config, label = 'prompt') {
  if (config.promptIntegrityMode === 'off') return validatePromptIntegrityText(raw, config);
  const result = validatePromptIntegrityText(raw, config);
  if (result.errors.length) {
    throw new CliError(`${label} failed prompt integrity checks; guarded Pro action is blocked.`, result, 1, 'blocked_prompt_integrity_failed');
  }
  return result;
}

async function commandValidatePrompt(config) {
  const raw = await readFile(config.promptPath, 'utf8');
  return validatePromptIntegrityText(raw, config);
}

async function commandValidateResponse(config) {
  const raw = await readFile(config.responsePath, 'utf8');
  const result = validateFormalResponseText(raw, config);
  return {
    ...result,
    responsePath: config.responsePath,
    responseHash: sha256(raw),
    responseLength: raw.length
  };
}

async function commandSend(config, args) {
  await loadLockFile(config);
  validateSendAuthorization(config, args);
  const prompt = await readFile(config.promptPath, 'utf8');
  const promptIntegrity = assertPromptIntegrity(prompt, config, 'promptPath');
  const promptHash = sha256(prompt);

  const { cdp, sessionId, target } = await createLockedPageSession(config);
  const preSendSnapshot = await getSnapshot(cdp, sessionId, config);
  const projectSessionStatus = await requireProjectSessionStatus(config, 'send');
  verifyProjectSessionForUrl(config, projectSessionStatus, preSendSnapshot.url, 'send');
  const composerInput = await evaluateJson(cdp, sessionId, buildFocusExistingInputExpression(config));
  if (!composerInput?.found) {
    await cdp.close();
    throw new CliError('Guarded send could not locate the visible composer input.', {
      checkedSelectors: config.inputSelectors
    }, 1, 'blocked_not_found');
  }
  const inputText = composerInput?.text ?? '';
  const inputIntegrity = assertPromptIntegrity(inputText, config, 'visible composer input');
  const inputHash = sha256(inputText);
  const trimEndInputHash = sha256(inputText.trimEnd());
  const trimEndPromptHash = sha256(prompt.trimEnd());
  const whitespaceNormalizedInputHash = sha256(normalizeForComposerComparison(inputText));
  const whitespaceNormalizedPromptHash = sha256(normalizeForComposerComparison(prompt));
  const inputMatchesPrompt = inputHash === promptHash;
  const inputMatchesPromptTrimEnd = !inputMatchesPrompt && trimEndInputHash === trimEndPromptHash;
  const inputMatchesPromptWhitespaceNormalized = !inputMatchesPrompt && !inputMatchesPromptTrimEnd && whitespaceNormalizedInputHash === whitespaceNormalizedPromptHash;
  if (!inputMatchesPrompt && !inputMatchesPromptTrimEnd && !inputMatchesPromptWhitespaceNormalized) {
    await cdp.close();
    throw new CliError('Active input does not match promptPath content; guarded send is blocked.', {
      inputSelector: composerInput.selector,
      inputId: composerInput.id,
      inputRole: composerInput.role,
      inputTextLength: composerInput?.length ?? 0,
      promptLength: prompt.length,
      normalizedInputLength: normalizeForComposerComparison(inputText).length,
      normalizedPromptLength: normalizeForComposerComparison(prompt).length
    }, 1, 'blocked_input_mismatch');
  }

  const clicked = await evaluateJson(cdp, sessionId, buildClickSendExpression(config));
  await cdp.close();

  if (!clicked?.clicked) {
    throw new CliError('Send button was not clicked because no enabled visible send button was found.', { clicked }, 1, 'blocked_not_found');
  }

  await writeSendState(config, {
    status: 'user_confirmed_sent',
    sentAt: new Date().toISOString(),
    promptHash,
    promptLength: prompt.length,
    promptIntegrity,
    inputIntegrity,
    inputHashMode: inputMatchesPrompt ? 'exact' : (inputMatchesPromptTrimEnd ? 'trimEnd' : 'whitespaceNormalized'),
    target: redactTarget(target),
    preSendAssistantMessageCount: preSendSnapshot.assistantMessages?.length ?? 0,
    preSendLastAssistantHash: preSendSnapshot.assistantMessages?.[preSendSnapshot.assistantMessages.length - 1]?.hash ?? '',
    preSendUrl: preSendSnapshot.url
  });

  return {
    status: 'user_confirmed_sent',
    pro_chat_send_status: 'user_confirmed_sent',
    browser_window_lock_status: 'locked',
    target: redactTarget(target),
    promptHash,
    promptIntegrity,
    inputIntegrity,
    inputHashMode: inputMatchesPrompt ? 'exact' : (inputMatchesPromptTrimEnd ? 'trimEnd' : 'whitespaceNormalized'),
    clicked: true,
    inputSelector: composerInput.selector
  };
}

function validateSendAuthorization(config, args) {
  if (config.sendPolicy !== 'per_run_authorized') {
    throw new CliError('Guarded send is disabled by default.', { sendPolicy: config.sendPolicy }, 1, 'blocked_user_send_confirmation_required');
  }
  if (!config.sendAuthorizationNonce || !args.authorizationNonce || args.authorizationNonce !== config.sendAuthorizationNonce) {
    throw new CliError('Guarded send is missing the current-run authorization nonce.', {}, 1, 'blocked_user_send_confirmation_required');
  }
}

async function waitForStableResponse(cdp, sessionId, config) {
  const startedAt = Date.now();
  const initialSnapshot = await getSnapshot(cdp, sessionId, config);
  const projectSessionStatus = await requireProjectSessionStatus(config, 'capture');
  verifyProjectSessionForUrl(config, projectSessionStatus, initialSnapshot.url, 'capture');
  const baseline = await resolveCaptureBaseline(config, initialSnapshot);
  await ensureReplyObserver(cdp, sessionId);
  const network = createNetworkMonitor(cdp, sessionId, config);
  let anchor = null;
  let lastHash = '';
  let stableStartedAt = 0;
  let unchangedPolls = 0;
  let pageIdleStartedAt = 0;
  let pageIdlePolls = 0;

  await writeMonitorStatus(config, buildReplyStatus({
    status: 'pro_generating',
    lifecycle: 'sent_observed',
    config,
    startedAt,
    baseline,
    snapshot: baseline,
    networkState: network.state(),
    anchor,
    hash: '',
    text: '',
    stableMs: 0,
    unchangedPolls: 0,
    pageIdleMs: 0,
    pageIdlePolls: 0,
    completionSignal: 'waiting_for_new_assistant_message'
  }));

  while (true) {
    const snapshot = await getSnapshot(cdp, sessionId, config);
    const detectedAnchor = detectAssistantAnchor(baseline, snapshot, anchor, config);
    if (detectedAnchor) {
      const anchorChanged = !anchor || detectedAnchor.id !== anchor.id;
      if (anchorChanged) {
        unchangedPolls = 0;
        stableStartedAt = 0;
        lastHash = '';
      }
      anchor = detectedAnchor;
    }

    const text = anchor?.text ?? '';
    const hash = sha256(text);
    const hasText = text.trim().length > 0;
    const endMarkerPresent = Boolean(config.endMarker && text.includes(config.endMarker));

    if (hasText && hash === lastHash) {
      unchangedPolls += 1;
      if (!stableStartedAt) stableStartedAt = Date.now();
    } else {
      unchangedPolls = hasText ? 1 : 0;
      stableStartedAt = hasText ? Date.now() : 0;
      lastHash = hash;
    }

    const stableMs = stableStartedAt ? Date.now() - stableStartedAt : 0;
    const pageIdle = isPageIdle(snapshot.pageSignals);
    if (pageIdle) {
      pageIdlePolls += 1;
      if (!pageIdleStartedAt) pageIdleStartedAt = Date.now();
    } else {
      pageIdlePolls = 0;
      pageIdleStartedAt = 0;
    }
    const pageIdleMs = pageIdleStartedAt ? Date.now() - pageIdleStartedAt : 0;
    const uiStable = pageIdle && pageIdlePolls >= config.uiStablePolls;
    const networkState = network.state();
    const networkReady = isNetworkReady(networkState, config);
    const domReady = isDomReady(snapshot.replyDomState, config);
    const realAssistantStable = isRealAssistantMessageStable(anchor, unchangedPolls, config)
      && snapshot.pageSignals?.stopGeneratingVisible !== true;
    const networkBlockingEffective = false;
    const confidence = realAssistantStable ? 'high' : 'low';

    if (realAssistantStable) {
      const completionSignal = 'real_assistant_message_node_stable';
      const completed = {
        status: 'response_captured_high_confidence',
        pro_response_capture_status: 'response_captured_high_confidence',
        pro_response_wait_mode: 'state_based_completion',
        reply_lifecycle_status: 'response_captured_high_confidence',
        responseText: text,
        responseHash: hash,
        responseLength: text.length,
        stablePollCount: unchangedPolls,
        stableDurationMs: stableMs,
        completionSignal,
        completion_confidence: confidence,
        end_marker_present: endMarkerPresent,
        network_blocking_effective: networkBlockingEffective,
        assistant_message_anchor: anchor.id,
        assistant_candidate_count: anchor.assistantCandidateCount ?? 0,
        latest_assistant_index: anchor.latestAssistantIndex ?? -1,
        selected_anchor_reason: anchor.selectedAnchorReason ?? '',
        anchor_switched: Boolean(anchor.anchorSwitched),
        previous_anchor: anchor.previousAnchor ?? null,
        assistant_last_mutated_at: snapshot.replyDomState?.lastMutationAt ?? '',
        network_stream_active: networkState.active,
        network_last_activity_at: networkState.lastActivityAt,
        ui_completion_signals: snapshot.pageSignals,
        pageSignals: snapshot.pageSignals,
        reply_state: makeReplyState({
          lifecycle: 'response_captured_high_confidence',
          networkState,
          snapshot,
          anchor,
          confidence,
          endMarkerPresent,
          stableMs,
          unchangedPolls,
          pageIdleMs,
          pageIdlePolls,
          completionSignal,
          networkBlockingEffective
        }),
        url: snapshot.url,
        title: snapshot.title
      };
      await writeMonitorStatus(config, withoutResponseText(completed));
      return completed;
    }

    const lifecycle = deriveLifecycle({
      anchor,
      stopGeneratingVisible: snapshot.pageSignals?.stopGeneratingVisible,
      uiStable: unchangedPolls >= config.uiStablePolls
    });
    const completionSignal = deriveCompletionSignal({
      anchor,
      stopGeneratingVisible: snapshot.pageSignals?.stopGeneratingVisible,
      uiStable: unchangedPolls >= config.uiStablePolls
    });
    const waiting = buildReplyStatus({
      status: 'pro_generating',
      lifecycle,
      config,
      startedAt,
      baseline,
      snapshot,
      networkState,
      anchor,
      hash,
      text,
      stableMs,
      unchangedPolls,
      pageIdleMs,
      pageIdlePolls,
      completionSignal,
      completionConfidence: confidence,
      endMarkerPresent,
      networkBlockingEffective
    });
    await writeMonitorStatus(config, waiting);

    await sleep(config.pollMs);
  }
}

function createNetworkMonitor(cdp, sessionId, config) {
  const requests = new Map();
  const active = new Set();
  const state = {
    observed: false,
    active: 'unknown',
    lastActivityAt: '',
    streamingObserved: false,
    activeCount: 0,
    trackedRequestCount: 0
  };
  const sameSession = (message) => (sessionId ? message.sessionId === sessionId : !message.sessionId);
  const markActivity = () => {
    state.lastActivityAt = new Date().toISOString();
  };

  cdp.on('*', (message) => {
    if (!sameSession(message)) return;
    const params = message.params ?? {};
    const requestId = params.requestId;
    if (!requestId) return;

    if (message.method === 'Network.requestWillBeSent') {
      const info = {
        url: params.request?.url ?? '',
        type: params.type ?? '',
        tracked: false
      };
      info.tracked = isTrackedNetwork(info.url, info.type, config);
      requests.set(requestId, info);
      if (info.tracked) {
        active.add(requestId);
        state.observed = true;
        state.active = true;
        state.trackedRequestCount += 1;
        markActivity();
      }
    } else if (message.method === 'Network.responseReceived') {
      const info = requests.get(requestId) ?? { url: '', type: '', tracked: false };
      info.url = params.response?.url ?? info.url;
      info.type = params.type ?? info.type;
      info.tracked = info.tracked || isTrackedNetwork(info.url, info.type, config);
      requests.set(requestId, info);
      if (info.tracked) {
        active.add(requestId);
        state.observed = true;
        state.active = true;
        state.streamingObserved = true;
        markActivity();
      }
    } else if (message.method === 'Network.loadingFinished' || message.method === 'Network.loadingFailed') {
      const info = requests.get(requestId);
      if (info?.tracked || active.has(requestId)) {
        active.delete(requestId);
        state.observed = true;
        state.active = active.size > 0;
        markActivity();
      }
    }
    state.activeCount = active.size;
  });

  return {
    state() {
      return {
        observed: state.observed,
        active: state.observed ? active.size > 0 : 'unknown',
        lastActivityAt: state.lastActivityAt,
        streamingObserved: state.streamingObserved,
        activeCount: active.size,
        trackedRequestCount: state.trackedRequestCount
      };
    }
  };
}

function isTrackedNetwork(url, type, config) {
  const typeAllowed = !type || config.trackedNetworkResourceTypes.some((item) => item.toLowerCase() === String(type).toLowerCase());
  if (!typeAllowed) return false;
  return config.trackedNetworkUrlPatterns.some((pattern) => {
    try {
      return new RegExp(pattern, 'i').test(url);
    } catch {
      return false;
    }
  });
}

async function ensureReplyObserver(cdp, sessionId) {
  return await evaluateJson(cdp, sessionId, `(() => {
    const now = new Date().toISOString();
    if (window.__pro_bridgeReplyMonitor && window.__pro_bridgeReplyMonitor.observerActive) {
      return { installed: true, reused: true, ...window.__pro_bridgeReplyMonitor };
    }
    const state = {
      observerActive: true,
      startedAt: now,
      lastMutationAt: now,
      mutationCount: 0
    };
    const observer = new MutationObserver(() => {
      state.lastMutationAt = new Date().toISOString();
      state.mutationCount += 1;
    });
    observer.observe(document.body, { childList: true, subtree: true, characterData: true });
    window.__pro_bridgeReplyMonitor = state;
    window.__pro_bridgeReplyMonitorObserver = observer;
    return { installed: true, reused: false, ...state };
  })()`);
}

function detectAssistantAnchor(baseline, snapshot, existingAnchor, config = DEFAULT_CONFIG) {
  const messages = snapshot.assistantMessages ?? [];
  if (!messages.length) return existingAnchor;

  const baselineMessages = baseline.assistantMessages ?? [];
  const baselineCount = baselineMessages.length;
  const last = messages[messages.length - 1];
  const baselineLast = baselineMessages[baselineMessages.length - 1] ?? null;
  const postBaselineCandidates = messages.filter((message) => message.index >= baselineCount);
  const changedBaselineLast = !postBaselineCandidates.length && baselineLast && last.hash !== baselineLast.hash ? [last] : [];
  const candidates = postBaselineCandidates.length ? postBaselineCandidates : changedBaselineLast;

  if (!candidates.length) return existingAnchor;
  const realCandidates = candidates.filter(isRealAssistantMessageNode);
  if (!realCandidates.length) return existingAnchor;

  const endMarkerCandidates = config.endMarker
    ? realCandidates.filter((message) => String(message.text ?? '').includes(config.endMarker))
    : [];
  const selected = endMarkerCandidates.length
    ? endMarkerCandidates[endMarkerCandidates.length - 1]
    : realCandidates[realCandidates.length - 1];
  const selectedAnchorReason = endMarkerCandidates.length
    ? 'latest_end_marker_candidate'
    : postBaselineCandidates.length
      ? 'latest_real_post_baseline_message_node'
      : 'changed_baseline_last_candidate';
  const anchorSwitched = Boolean(existingAnchor && existingAnchor.id !== selected.id);
  const previousAnchor = existingAnchor
    ? {
        id: existingAnchor.id,
        index: existingAnchor.index,
        hash: existingAnchor.hash,
        length: existingAnchor.text?.length ?? 0
      }
    : null;

  return {
    ...selected,
    detectedAt: anchorSwitched ? new Date().toISOString() : existingAnchor?.detectedAt ?? new Date().toISOString(),
    baselineMessageCount: baselineCount,
    assistantCandidateCount: candidates.length,
    latestAssistantIndex: last?.index ?? -1,
    selectedAnchorReason,
    anchorSwitched,
    previousAnchor
  };
}

function isNetworkReady(networkState, config) {
  if (!networkState.observed) return true;
  if (networkState.active === true) return false;
  if (!networkState.lastActivityAt) return false;
  return Date.now() - Date.parse(networkState.lastActivityAt) >= config.networkIdleMs;
}

function isRealAssistantMessageNode(message) {
  return Boolean(
    message?.text?.trim() &&
    message.realAssistantMessage === true &&
    message.role === 'assistant' &&
    message.dataMessageId &&
    String(message.dataTurnStartMessage).toLowerCase() === 'true' &&
    !message.finalizing &&
    !message.thinking &&
    !message.placeholderState
  );
}

function isRealAssistantMessageStable(anchor, unchangedPolls, config) {
  return isRealAssistantMessageNode(anchor) && unchangedPolls >= config.uiStablePolls;
}

function isDomReady(replyDomState, config) {
  if (!replyDomState?.observerActive || !replyDomState.lastMutationAt) return false;
  return Date.now() - Date.parse(replyDomState.lastMutationAt) >= config.domIdleMs;
}

function deriveLifecycle({ anchor, stopGeneratingVisible, networkState = {}, networkReady = true, networkBlockingEffective = !networkReady, domReady = true, uiStable = true }) {
  if (!anchor) return 'sent_observed';
  if (stopGeneratingVisible === true) return 'streaming_observed';
  if (stopGeneratingVisible === false) return 'assistant_message_detected';
  if (networkState.active === true && networkBlockingEffective) return 'streaming_observed';
  if (!networkReady && networkBlockingEffective) return 'network_idle_settling';
  if (!domReady) return 'dom_idle_settling';
  if (!uiStable) return 'assistant_message_detected';
  return 'assistant_message_detected';
}

function deriveCompletionSignal({ anchor, stopGeneratingVisible, networkState = {}, networkReady = true, networkBlockingEffective = !networkReady, domReady = true, uiStable = true, endMarkerPresent = false }) {
  if (!anchor) return 'waiting_for_new_assistant_message';
  if (stopGeneratingVisible === true) return 'stop_generating_visible';
  if (isRealAssistantMessageNode(anchor) && uiStable) return 'real_assistant_message_node_stable';
  if (isRealAssistantMessageNode(anchor)) return 'real_assistant_message_node_settling';
  if (stopGeneratingVisible === false) return 'waiting_for_real_assistant_message_node';
  if (!networkReady && !networkBlockingEffective && endMarkerPresent) return 'network_stream_active_nonblocking_with_end_marker';
  if (networkState.active === true && networkBlockingEffective) return 'network_stream_active';
  if (!networkReady && networkBlockingEffective) return 'network_idle_settling';
  if (!domReady) return 'dom_mutation_active';
  if (!uiStable) return 'ui_completion_pending';
  return endMarkerPresent ? 'ready_with_end_marker' : 'ready_without_end_marker';
}

function makeReplyState({ lifecycle, networkState, snapshot, anchor, confidence, endMarkerPresent, stableMs, unchangedPolls, pageIdleMs, pageIdlePolls, completionSignal, networkBlockingEffective = false }) {
  return {
    reply_lifecycle_status: lifecycle,
    network_stream_active: networkState.active,
    network_last_activity_at: networkState.lastActivityAt,
    network_observed: networkState.observed,
    network_tracked_request_count: networkState.trackedRequestCount,
    network_blocking_effective: networkBlockingEffective,
    assistant_message_anchor: anchor?.id ?? '',
    assistant_message_index: Number.isFinite(anchor?.index) ? anchor.index : -1,
    assistant_candidate_count: anchor?.assistantCandidateCount ?? 0,
    latest_assistant_index: anchor?.latestAssistantIndex ?? -1,
    selected_anchor_reason: anchor?.selectedAnchorReason ?? '',
    anchor_switched: Boolean(anchor?.anchorSwitched),
    previous_anchor: anchor?.previousAnchor ?? null,
    assistant_last_mutated_at: snapshot.replyDomState?.lastMutationAt ?? '',
    assistant_mutation_count: snapshot.replyDomState?.mutationCount ?? 0,
    assistant_text_length: anchor?.text?.length ?? 0,
    assistant_text_hash: anchor?.hash ?? '',
    stable_poll_count: unchangedPolls,
    stable_duration_ms: stableMs,
    page_idle_duration_ms: pageIdleMs,
    page_idle_poll_count: pageIdlePolls,
    ui_completion_signals: snapshot.pageSignals,
    end_marker_present: endMarkerPresent,
    completion_confidence: confidence,
    completion_signal: completionSignal
  };
}

function buildReplyStatus({ status, lifecycle, config, startedAt, baseline, snapshot, networkState, anchor, hash, text, stableMs, unchangedPolls, pageIdleMs, pageIdlePolls, completionSignal, completionConfidence = 'low', endMarkerPresent = false, networkBlockingEffective = false }) {
  const replyState = makeReplyState({
    lifecycle,
    networkState,
    snapshot,
    anchor,
    confidence: completionConfidence,
    endMarkerPresent,
    stableMs,
    unchangedPolls,
    pageIdleMs,
    pageIdlePolls,
    completionSignal,
    networkBlockingEffective
  });
  return {
    status,
    pro_response_capture_status: status,
    pro_response_wait_mode: 'state_based_completion',
    reply_lifecycle_status: lifecycle,
    responseHash: hash,
    responseLength: text.length,
    stablePollCount: unchangedPolls,
    stableDurationMs: stableMs,
    elapsedMs: Date.now() - startedAt,
    timeoutMs: config.timeoutMs,
    fixedTotalTimeoutEnabled: false,
    completionSignal,
    completion_confidence: completionConfidence,
    end_marker_present: endMarkerPresent,
    network_stream_active: networkState.active,
    network_last_activity_at: networkState.lastActivityAt,
    network_blocking_effective: networkBlockingEffective,
    assistant_message_anchor: anchor?.id ?? '',
    assistant_candidate_count: anchor?.assistantCandidateCount ?? 0,
    latest_assistant_index: anchor?.latestAssistantIndex ?? -1,
    selected_anchor_reason: anchor?.selectedAnchorReason ?? '',
    anchor_switched: Boolean(anchor?.anchorSwitched),
    previous_anchor: anchor?.previousAnchor ?? null,
    assistant_last_mutated_at: snapshot.replyDomState?.lastMutationAt ?? '',
    ui_completion_signals: snapshot.pageSignals,
    baseline: {
      assistantMessageCount: baseline.assistantMessages?.length ?? 0,
      lastAssistantHash: baseline.assistantMessages?.[baseline.assistantMessages.length - 1]?.hash ?? ''
    },
    reply_state: replyState,
    pageSignals: snapshot.pageSignals,
    url: snapshot.url,
    title: snapshot.title,
    observedAt: snapshot.observedAt
  };
}

async function getSnapshot(cdp, sessionId, config) {
  const snapshot = await evaluateJson(cdp, sessionId, buildSnapshotExpression(config));
  const messages = (snapshot.assistantMessages ?? []).map((message, index) => ({
    ...message,
    index,
    hash: sha256(message.text ?? ''),
    id: message.dataMessageId
      ? `assistant:${index}:${message.dataMessageId}`
      : `assistant:${index}:${sha256(message.selector ?? '').slice(0, 8)}`
  }));
  const last = messages[messages.length - 1] ?? null;
  return {
    ...snapshot,
    assistantMessages: messages,
    responseText: last?.text ?? '',
    responseSelector: last?.selector ?? snapshot.responseSelector ?? '',
    responseHash: last?.hash ?? sha256('')
  };
}

function escapeRegExp(value) {
  return String(value).replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

function parseProjectConversationUrl(url, projectId) {
  const text = String(url ?? '');
  const projectPattern = new RegExp(`/g/(${escapeRegExp(projectId)}(?:-[^/?#]+)?)`, 'i');
  const conversationPattern = new RegExp(`/g/${escapeRegExp(projectId)}(?:-[^/?#]+)?/c/([0-9a-f-]{36})`, 'i');
  const projectMatch = text.match(projectPattern);
  const conversationMatch = text.match(conversationPattern);
  return {
    projectMatched: Boolean(projectMatch),
    projectSlug: projectMatch?.[1] ?? '',
    conversationId: conversationMatch?.[1] ?? ''
  };
}

async function readJsonlRegistry(filePath, { required, label }) {
  let raw;
  try {
    raw = await readFile(filePath, 'utf8');
  } catch (error) {
    if (!required && error?.code === 'ENOENT') return [];
    throw new CliError('Pro session registry cannot be read.', {
        sessionRegistryPath: filePath,
      label,
      cause: error.message
    }, 1, 'blocked_project_session_mismatch');
  }

  const sessions = [];
  let lineNo = 0;
  for (const rawLine of raw.split(/\r?\n/)) {
    lineNo += 1;
    const line = lineNo === 1 ? rawLine.replace(/^\uFEFF/, '') : rawLine;
    if (!line.trim()) continue;
    try {
      sessions.push(JSON.parse(line));
    } catch (error) {
      throw new CliError('Pro session registry contains invalid JSONL.', {
        sessionRegistryPath: filePath,
        label,
        lineNo,
        cause: error.message
      }, 1, 'blocked_project_session_mismatch');
    }
  }
  return sessions;
}

async function readSessionRegistry(config) {
  const formalSessions = await readJsonlRegistry(config.sessionRegistryPath, { required: true, label: 'formal' });
  const testSessions = await readJsonlRegistry(config.testSessionRegistryPath, { required: false, label: 'test_only' });
  return [...formalSessions, ...testSessions];
}

function summarizeRegisteredSession(session, observedByConversationId) {
  const observed = observedByConversationId.get(session.conversation_id) ?? null;
  return {
    session_key: String(session.session_key ?? ''),
    project_id: String(session.project_id ?? ''),
    conversation_id: String(session.conversation_id ?? ''),
    conversation_url: String(session.conversation_url ?? ''),
    status: String(session.status ?? ''),
    handoff_count: Number(session.handoff_count ?? 0),
    handoff_limit: Number(session.handoff_limit ?? 30),
    created_by_pro_bridge: Boolean(session.created_by_pro_bridge),
    test_only: Boolean(session.test_only) || String(session.session_key ?? '').includes('test'),
    delete_status: String(session.delete_status ?? ''),
    observed_in_project_page: Boolean(observed),
    current_open: Boolean(observed?.current_open)
  };
}

function reconcileProjectSessions(config, pageState, registry) {
  const observedRaw = Array.isArray(pageState.observed_sessions) ? pageState.observed_sessions : [];
  const observedByConversationId = new Map();
  for (const observed of observedRaw) {
    if (!observed.conversation_id || observedByConversationId.has(observed.conversation_id)) continue;
    observedByConversationId.set(observed.conversation_id, observed);
  }

  const registeredByConversationId = new Map();
  for (const session of registry) {
    if (session.conversation_id) registeredByConversationId.set(session.conversation_id, session);
  }

  const observed_sessions = [...observedByConversationId.values()].map((observed) => {
    const registered = registeredByConversationId.get(observed.conversation_id) ?? null;
    const deleteAllowed = Boolean(
      registered &&
      registered.created_by_pro_bridge === true &&
      registered.project_id === config.projectId &&
      registered.conversation_id === observed.conversation_id &&
      registered.status === 'retired_delete_pending'
    );
    return {
      conversation_id: observed.conversation_id,
      conversation_url: observed.conversation_url,
      title_preview: observed.title_preview,
      title_hash: observed.title_hash,
      title_length: observed.title_length,
      current_open: Boolean(observed.current_open),
      registered: Boolean(registered),
      session_key: registered?.session_key ?? '',
      registry_status: registered?.status ?? '',
      handoff_count: Number(registered?.handoff_count ?? 0),
      handoff_limit: Number(registered?.handoff_limit ?? 30),
      test_only: Boolean(registered?.test_only) || String(registered?.session_key ?? '').includes('test'),
      delete_allowed: deleteAllowed
    };
  });

  const registered_sessions = registry.map((session) => summarizeRegisteredSession(session, observedByConversationId));
  const missing_in_page = registered_sessions.filter((session) => {
    if (session.observed_in_project_page) return false;
    return !['deleted', 'archived'].includes(session.status);
  });
  const unregistered_in_page = observed_sessions.filter((session) => !session.registered);
  const activeFormal = registry.find((session) => session.session_key === config.currentFormalSessionKey)
    ?? registry.find((session) => session.status === 'active' && session.project_id === config.projectId)
    ?? null;
  const active_formal_session_match = Boolean(
    activeFormal &&
    activeFormal.status === 'active' &&
    activeFormal.project_id === config.projectId &&
    observedByConversationId.has(activeFormal.conversation_id)
  );
  const delete_safe_sessions = observed_sessions.filter((session) => session.delete_allowed);
  const blocked_reasons = [];
  if (!pageState.projectMatched) blocked_reasons.push('locked_page_not_in_fixed_project');
  if (activeFormal?.project_id && activeFormal.project_id !== config.projectId) blocked_reasons.push('active_formal_session_project_mismatch');
  if (activeFormal?.status === 'active' && !active_formal_session_match) blocked_reasons.push('active_formal_session_missing_in_project_page');

  return {
    status: blocked_reasons.length ? 'blocked_project_session_mismatch' : 'project_sessions_reconciled',
    project_id: config.projectId,
    project_url: config.projectUrl,
    observed_at: new Date().toISOString(),
    source_url: pageState.url,
    source_title: pageState.title,
    observed_count: observed_sessions.length,
    registered_count: registered_sessions.length,
    active_formal_session_key: activeFormal?.session_key ?? config.currentFormalSessionKey,
    active_formal_conversation_id: activeFormal?.conversation_id ?? '',
    active_formal_session_match,
    observed_sessions,
    registered_sessions,
    missing_in_page,
    unregistered_in_page,
    delete_safe_sessions,
    blocked_reasons,
    notes: 'Read-only project Chats reconciliation. Does not read conversation bodies, send messages, or delete sessions.'
  };
}

async function writeProjectSessionStatus(config, status) {
  await mkdir(path.dirname(config.projectSessionStatusPath), { recursive: true });
  await writeFile(config.projectSessionStatusPath, JSON.stringify(status, null, 2), 'utf8');
}

async function requireProjectSessionStatus(config, action) {
  if (config.requireProjectSessionStatus === false || config.projectSessionMode === 'read_only') {
    return { status: 'not_required', skipped: true };
  }
  let status;
  try {
    status = JSON.parse(await readFile(config.projectSessionStatusPath, 'utf8'));
  } catch (error) {
    throw new CliError('PROJECT_SESSION_STATUS.json is required before this Pro action. Run project-sessions first.', {
      action,
      projectSessionStatusPath: config.projectSessionStatusPath,
      cause: error.message
    }, 1, 'blocked_project_session_status_required');
  }
  if (status.project_id !== config.projectId || status.status !== 'project_sessions_reconciled') {
    throw new CliError('Project session reconciliation is not in a pass state.', {
      action,
      projectSessionStatusPath: config.projectSessionStatusPath,
      project_id: status.project_id,
      status: status.status,
      blocked_reasons: status.blocked_reasons ?? []
    }, 1, 'blocked_project_session_mismatch');
  }
  return status;
}

function verifyProjectSessionForUrl(config, projectSessionStatus, url, action) {
  if (!projectSessionStatus || projectSessionStatus.skipped) return;
  const parsed = parseProjectConversationUrl(url, config.projectId);
  if (!parsed.projectMatched) {
    throw new CliError('Current browser URL is not inside the fixed Pro project.', {
      action,
      url,
      projectId: config.projectId
    }, 1, 'blocked_project_session_mismatch');
  }
  if (config.projectSessionMode !== 'formal') return;

  const expectedConversationId = config.expectedConversationId || projectSessionStatus.active_formal_conversation_id;
  if (!expectedConversationId) {
    throw new CliError('No active formal conversation id is available for this Pro action.', {
      action,
      projectSessionStatusPath: config.projectSessionStatusPath
    }, 1, 'blocked_project_session_mismatch');
  }
  if (!parsed.conversationId) {
    throw new CliError('Formal Pro action must target the active formal project conversation, not the project home page.', {
      action,
      url,
      expectedConversationId
    }, 1, 'blocked_project_session_mismatch');
  }
  if (parsed.conversationId !== expectedConversationId) {
    throw new CliError('Current project conversation does not match the reconciled active formal session.', {
      action,
      url,
      currentConversationId: parsed.conversationId,
      expectedConversationId
    }, 1, 'blocked_project_session_mismatch');
  }
}

function buildFocusInputExpression(config) {
  return `(() => {
    const selectors = ${JSON.stringify(config.inputSelectors)};
    const rejectSelectors = ${JSON.stringify(config.inputRejectSelectors)};
    const visible = (el) => {
      if (!el) return false;
      const style = window.getComputedStyle(el);
      const rect = el.getBoundingClientRect();
      return style && style.visibility !== 'hidden' && style.display !== 'none' && rect.width > 0 && rect.height > 0;
    };
    const enabled = (el) => !el.disabled && el.getAttribute('aria-disabled') !== 'true' && !el.readOnly;
    const rejected = (el) => rejectSelectors.some((selector) => {
      try { return el.matches(selector); } catch { return false; }
    });
    const textOf = (el) => 'value' in el ? el.value : (el.innerText || el.textContent || '');
    for (const selector of selectors) {
      const nodes = Array.from(document.querySelectorAll(selector)).filter((el) => visible(el) && enabled(el) && !rejected(el));
      const el = nodes[nodes.length - 1];
      if (!el) continue;
      el.scrollIntoView({ block: 'center', inline: 'nearest' });
      el.focus();
      if ('value' in el) el.value = '';
      else el.textContent = '';
      el.dispatchEvent(new InputEvent('input', { bubbles: true, inputType: 'deleteContentBackward', data: null }));
      el.dispatchEvent(new Event('change', { bubbles: true }));
      return {
        found: true,
        selector,
        tagName: el.tagName,
        id: el.id || '',
        role: el.getAttribute('role') || '',
        ariaLabel: el.getAttribute('aria-label') || '',
        placeholder: el.getAttribute('placeholder') || '',
        contenteditable: el.isContentEditable,
        rejected: false,
        textLengthAfterClear: textOf(el).length
      };
    }
    return { found: false };
  })()`;
}

function buildActiveInputExpression() {
  return `(() => {
    const el = document.activeElement;
    if (!el) return { length: 0, text: '' };
    const text = 'value' in el ? el.value : (el.innerText || el.textContent || '');
    return { length: text.length, text, tagName: el.tagName, role: el.getAttribute('role') || '', contenteditable: el.isContentEditable };
  })()`;
}

function buildFocusExistingInputExpression(config) {
  return `(() => {
    const selectors = ${JSON.stringify(config.inputSelectors)};
    const rejectSelectors = ${JSON.stringify(config.inputRejectSelectors)};
    const visible = (el) => {
      if (!el) return false;
      const style = window.getComputedStyle(el);
      const rect = el.getBoundingClientRect();
      return style && style.visibility !== 'hidden' && style.display !== 'none' && rect.width > 0 && rect.height > 0;
    };
    const enabled = (el) => !el.disabled && el.getAttribute('aria-disabled') !== 'true' && !el.readOnly;
    const rejected = (el) => rejectSelectors.some((selector) => {
      try { return el.matches(selector); } catch { return false; }
    });
    const textOf = (el) => 'value' in el ? el.value : (el.innerText || el.textContent || '');
    for (const selector of selectors) {
      const nodes = Array.from(document.querySelectorAll(selector)).filter((el) => visible(el) && enabled(el) && !rejected(el));
      const el = nodes[nodes.length - 1];
      if (!el) continue;
      el.scrollIntoView({ block: 'center', inline: 'nearest' });
      el.focus();
      const text = textOf(el);
      return {
        found: true,
        selector,
        tagName: el.tagName,
        id: el.id || '',
        role: el.getAttribute('role') || '',
        ariaLabel: el.getAttribute('aria-label') || '',
        placeholder: el.getAttribute('placeholder') || '',
        contenteditable: el.isContentEditable,
        length: text.length,
        text
      };
    }
    return { found: false, length: 0, text: '' };
  })()`;
}

function buildClickSendExpression(config) {
  return `(() => {
    const sendTexts = ${JSON.stringify(config.sendButtonTexts.map((s) => s.toLowerCase()))};
    const visible = (el) => {
      if (!el) return false;
      const style = window.getComputedStyle(el);
      const rect = el.getBoundingClientRect();
      return style && style.visibility !== 'hidden' && style.display !== 'none' && rect.width > 0 && rect.height > 0;
    };
    const normalizedText = (el) => [
      el.innerText || el.textContent || '',
      el.getAttribute('aria-label') || '',
      el.getAttribute('title') || ''
    ].join(' ').toLowerCase().replace(/\\s+/g, ' ').trim();
    const buttons = Array.from(document.querySelectorAll('button,[role="button"]')).filter(visible);
    const button = buttons.find((item) => sendTexts.some((text) => text && normalizedText(item).includes(text)) && !item.disabled && item.getAttribute('aria-disabled') !== 'true');
    if (!button) return { clicked: false };
    button.click();
    return { clicked: true, label: normalizedText(button) };
  })()`;
}

function buildProjectSessionsExpression(config) {
  return `(async () => {
    const projectId = ${JSON.stringify(config.projectId)};
    const projectPattern = new RegExp('/g/' + projectId + '(?:-[^/?#]+)?(?:/|$)', 'i');
    const conversationPattern = new RegExp('/g/' + projectId + '(?:-[^/?#]+)?/c/([0-9a-f-]{36})', 'i');
    const visible = (el) => {
      if (!el) return false;
      const style = window.getComputedStyle(el);
      const rect = el.getBoundingClientRect();
      return style && style.visibility !== 'hidden' && style.display !== 'none' && rect.width > 0 && rect.height > 0;
    };
    const compact = (text, maxLength = 120) => {
      const value = String(text || '').replace(/\\s+/g, ' ').trim();
      return value.length <= maxLength ? value : value.slice(0, maxLength - 3) + '...';
    };
    const sha256 = async (text) => {
      const bytes = new TextEncoder().encode(String(text || ''));
      const digest = await crypto.subtle.digest('SHA-256', bytes);
      return Array.from(new Uint8Array(digest)).map((b) => b.toString(16).padStart(2, '0')).join('');
    };
    const currentConversationMatch = location.href.match(conversationPattern);
    const anchors = Array.from(document.querySelectorAll('a[href]'))
      .filter(visible)
      .map((a) => {
        const href = new URL(a.getAttribute('href'), location.href).href;
        const match = href.match(conversationPattern);
        if (!match) return null;
        const rawTitle = [
          a.getAttribute('aria-label') || '',
          a.getAttribute('title') || '',
          a.innerText || a.textContent || ''
        ].filter(Boolean).join(' ').replace(/\\s+/g, ' ').trim();
        return {
          conversation_id: match[1],
          conversation_url: href,
          raw_title: rawTitle,
          title_preview: compact(rawTitle),
          title_length: rawTitle.length,
          current_open: currentConversationMatch?.[1] === match[1]
        };
      })
      .filter(Boolean);
    const deduped = [];
    const seen = new Set();
    for (const item of anchors) {
      if (seen.has(item.conversation_id)) continue;
      seen.add(item.conversation_id);
      deduped.push(item);
    }
    const observed_sessions = [];
    for (const item of deduped) {
      observed_sessions.push({
        conversation_id: item.conversation_id,
        conversation_url: item.conversation_url,
        title_preview: item.title_preview,
        title_hash: await sha256(item.raw_title),
        title_length: item.title_length,
        current_open: item.current_open
      });
    }
    return {
      url: location.href,
      title: document.title,
      projectMatched: projectPattern.test(location.href),
      project_id: projectId,
      observed_sessions
    };
  })()`;
}

function buildSnapshotExpression(config) {
  return `(() => {
    const assistantSelectors = ${JSON.stringify(config.assistantResponseSelectors)};
    const stopTexts = ${JSON.stringify(config.stopGeneratingButtonTexts.map((s) => s.toLowerCase()))};
    const sendTexts = ${JSON.stringify(config.sendButtonTexts.map((s) => s.toLowerCase()))};
    const doneTexts = ${JSON.stringify(config.doneButtonTexts.map((s) => s.toLowerCase()))};
    const visible = (el) => {
      if (!el) return false;
      const style = window.getComputedStyle(el);
      const rect = el.getBoundingClientRect();
      return style && style.visibility !== 'hidden' && style.display !== 'none' && rect.width > 0 && rect.height > 0;
    };
    const normalizedText = (el) => [
      el.innerText || el.textContent || '',
      el.getAttribute('aria-label') || '',
      el.getAttribute('title') || ''
    ].join(' ').toLowerCase().replace(/\\s+/g, ' ').trim();
    const maxActionLabelLength = ${MAX_ACTION_LABEL_LENGTH};
    const actionLabel = (el) => {
      const explicit = [
        el.getAttribute('aria-label') || '',
        el.getAttribute('title') || ''
      ].join(' ').toLowerCase().replace(/\\s+/g, ' ').trim();
      const visibleText = (el.innerText || el.textContent || '').toLowerCase().replace(/\\s+/g, ' ').trim();
      if (explicit && explicit.length <= maxActionLabelLength) return [explicit, visibleText.length <= maxActionLabelLength ? visibleText : ''].filter(Boolean).join(' ');
      if (explicit) return '';
      if (visibleText.length <= maxActionLabelLength) return visibleText;
      return '';
    };
    const includesAny = (text, needles) => needles.some((needle) => needle && text.includes(needle));
    const isStopAction = (label) => stopTexts.some((needle) => {
      if (!needle) return false;
      if (needle === 'stop' || needle === '停止') return label === needle;
      return label.includes(needle);
    });
    const buttons = Array.from(document.querySelectorAll('button,[role="button"]')).filter(visible);
    const stopGeneratingVisible = buttons.some((button) => isStopAction(actionLabel(button)));
    const sendButtonEnabled = buttons.some((button) => includesAny(normalizedText(button), sendTexts) && !button.disabled && button.getAttribute('aria-disabled') !== 'true');
    const regenerateOrCopyVisible = buttons.some((button) => includesAny(normalizedText(button), doneTexts));
    const stopGeneratingCandidates = buttons
      .map((button) => ({
        tagName: button.tagName,
        role: button.getAttribute('role') || '',
        label: actionLabel(button),
        textPreview: normalizedText(button).slice(0, 120)
      }))
      .filter((item) => isStopAction(item.label))
      .slice(0, 5);
    const attrFromTree = (el, attr) => {
      if (!el) return '';
      const direct = el.getAttribute(attr);
      if (direct) return direct;
      const closest = el.closest('[' + attr + ']');
      if (closest) return closest.getAttribute(attr) || '';
      const child = el.querySelector('[' + attr + ']');
      return child ? (child.getAttribute(attr) || '') : '';
    };
    const placeholderState = (text, el) => {
      const finalizing = /Finalizing answer|正在完成|整理答案|完成回答/i.test(text);
      const thinking = /Pro thinking|Thinking|思考中|正在思考/i.test(text);
      const spinner = Boolean(el.querySelector('[aria-busy="true"], [data-testid*="spinner" i], [class*="spinner" i], [class*="animate-spin" i]'));
      return { finalizing, thinking, spinner, placeholder: finalizing || thinking || spinner };
    };
    const assistantMessages = [];
    let responseText = '';
    let responseSelector = '';
    for (const selector of assistantSelectors) {
      const nodes = Array.from(document.querySelectorAll(selector))
        .filter((el) => visible(el))
        .map((el) => ({ el, text: (el.innerText || el.textContent || '').trim() }))
        .filter((item) => item.text.length > 0);
      if (nodes.length) {
        for (const item of nodes) {
          const role = attrFromTree(item.el, 'data-message-author-role') || (item.text.startsWith('ChatGPT said:') ? 'assistant' : '');
          const dataMessageId = attrFromTree(item.el, 'data-message-id');
          const dataTurnStartMessage = attrFromTree(item.el, 'data-turn-start-message');
          const placeholder = placeholderState(item.text, item.el);
          assistantMessages.push({
            selector,
            text: item.text,
            length: item.text.length,
            role,
            dataMessageId,
            dataTurnStartMessage,
            finalizing: placeholder.finalizing,
            thinking: placeholder.thinking,
            spinner: placeholder.spinner,
            placeholderState: placeholder.placeholder,
            realAssistantMessage: role === 'assistant' && Boolean(dataMessageId) && String(dataTurnStartMessage).toLowerCase() === 'true' && !placeholder.placeholder
          });
        }
        const item = assistantMessages[assistantMessages.length - 1];
        responseText = item.text;
        responseSelector = item.selector;
        break;
      }
    }
    const replyDomState = window.__pro_bridgeReplyMonitor ? {
      observerActive: Boolean(window.__pro_bridgeReplyMonitor.observerActive),
      startedAt: window.__pro_bridgeReplyMonitor.startedAt || '',
      lastMutationAt: window.__pro_bridgeReplyMonitor.lastMutationAt || '',
      mutationCount: Number(window.__pro_bridgeReplyMonitor.mutationCount || 0)
    } : {
      observerActive: false,
      startedAt: '',
      lastMutationAt: '',
      mutationCount: 0
    };
    return {
      url: location.href,
      title: document.title,
      responseText,
      responseSelector,
      assistantMessages,
      assistantMessageCount: assistantMessages.length,
      replyDomState,
      pageSignals: { stopGeneratingVisible, sendButtonEnabled, regenerateOrCopyVisible, stopGeneratingCandidates },
      observedAt: new Date().toISOString()
    };
  })()`;
}

function isPageIdle(signals) {
  return signals && !signals.stopGeneratingVisible && (signals.sendButtonEnabled || signals.regenerateOrCopyVisible);
}

function withoutResponseText(result) {
  const { responseText, ...rest } = result;
  return rest;
}

async function writeMonitorStatus(config, status) {
  if (!config.monitorStatusPath) return;
  const payload = {
    ...status,
    updatedAt: new Date().toISOString()
  };
  await mkdir(path.dirname(config.monitorStatusPath), { recursive: true });
  await writeFile(config.monitorStatusPath, JSON.stringify(payload, null, 2), 'utf8');
}

function getSendStatePath(config) {
  if (config.sendStatePath) return config.sendStatePath;
  if (!config.responsePath) return '';
  return path.join(path.dirname(config.responsePath), 'PRO_SEND_STATE.json');
}

async function writeSendState(config, payload) {
  const sendStatePath = getSendStatePath(config);
  if (!sendStatePath) return;
  await mkdir(path.dirname(sendStatePath), { recursive: true });
  await writeFile(sendStatePath, JSON.stringify(payload, null, 2), 'utf8');
}

async function readSendState(config) {
  const sendStatePath = getSendStatePath(config);
  if (!sendStatePath) return null;
  try {
    return JSON.parse(await readFile(sendStatePath, 'utf8'));
  } catch {
    return null;
  }
}

async function resolveCaptureBaseline(config, initialSnapshot) {
  const sendState = await readSendState(config);
  const count = Number(sendState?.preSendAssistantMessageCount);
  const messages = initialSnapshot.assistantMessages ?? [];
  if (Number.isInteger(count) && count >= 0 && count <= messages.length) {
    return {
      ...initialSnapshot,
      assistantMessages: messages.slice(0, count),
      responseText: messages[count - 1]?.text ?? '',
      responseSelector: messages[count - 1]?.selector ?? initialSnapshot.responseSelector ?? '',
      responseHash: messages[count - 1]?.hash ?? sha256('')
    };
  }
  return initialSnapshot;
}

function sha256(text) {
  return createHash('sha256').update(String(text), 'utf8').digest('hex');
}

function normalizeForComposerComparison(text) {
  return String(text)
    .replace(/\r\n?/g, '\n')
    .replace(/\u00a0/g, ' ')
    .replace(/[\u200B-\u200D\uFEFF]/g, '')
    .replace(/\s+/g, '');
}

function compactPreview(text, maxLength = 160) {
  const compact = String(text ?? '').replace(/\s+/g, ' ').trim();
  if (compact.length <= maxLength) return compact;
  return `${compact.slice(0, Math.max(0, maxLength - 3))}...`;
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function ensureTrailingSlash(value) {
  return value.endsWith('/') ? value : `${value}/`;
}

function redactDebugUrl(url) {
  return String(url).replace(/(devtools\/(?:browser|page)\/)[^/?#]+/i, '$1<redacted>');
}

function redactEndpoints(endpoints) {
  return {
    ws: endpoints.ws.map(redactDebugUrl),
    http: endpoints.http,
    driver: endpoints.driver.map((item) => path.basename(item))
  };
}

function redactTarget(target) {
  return {
    targetId: target.targetId ? shortId(target.targetId) : '',
    type: target.type ?? '',
    title: target.title ?? '',
    url: target.url ?? '',
    source: target.source ?? ''
  };
}

function shortId(value) {
  const text = String(value);
  return text.length > 14 ? `${text.slice(0, 6)}...${text.slice(-4)}` : text;
}

function summarizeShape(value) {
  if (!value || typeof value !== 'object') return typeof value;
  return Object.fromEntries(Object.entries(value).map(([key, item]) => [key, Array.isArray(item) ? 'array' : typeof item]));
}

function summarizeLockHints(lock) {
  const hints = getLockHints(lock);
  return {
    hasTargetId: Boolean(hints.expectedTargetId),
    hasTitlePattern: Boolean(hints.expectedTitlePattern),
    hasUrlPattern: Boolean(hints.expectedUrlPattern),
    hasProcessHint: Boolean(hints.expectedProcessId),
    hasRef: Boolean(hints.ref)
  };
}

function printResult(result, jsonMode = false) {
  console.log(JSON.stringify(result, null, 2));
}

async function selfTest() {
  const tests = [];
  const assert = (name, condition, details = {}) => {
    if (!condition) throw new CliError(`Self-test failed: ${name}`, details);
    tests.push(name);
  };

  try {
    validateConfig({});
    throw new Error('validateConfig unexpectedly passed');
  } catch (error) {
    assert('missing required config fields fail clearly', error instanceof CliError && error.details.missing.includes('apiBase'));
  }

  const endpoints = collectDebugEndpoints({
    ws: 'ws://127.0.0.1:9222/devtools/browser/abc',
    http: '127.0.0.1:9222',
    nested: { ws: { page: 'ws://127.0.0.1:9333/devtools/page/def' } },
    driver: 'C:/BitBrowser/chromedriver.exe'
  });
  assert('extract ws endpoints recursively', endpoints.ws.length === 2, endpoints);
  assert('normalize http endpoint without scheme', endpoints.http[0] === 'http://127.0.0.1:9222', endpoints);
  assert('extract driver endpoint', endpoints.driver.length === 1, endpoints);
  const selectorOrder = DEFAULT_CONFIG.inputSelectors;
  assert('chat composer selectors are preferred before generic textarea', selectorOrder.indexOf('#prompt-textarea[contenteditable="true"]') < selectorOrder.indexOf('textarea'), selectorOrder);
  assert('known non-composer notepad textarea is rejected by default', DEFAULT_CONFIG.inputRejectSelectors.includes('.ait-notepad-editor'));
  assert('guarded send has a composer-specific input reader', buildFocusExistingInputExpression(DEFAULT_CONFIG).includes('#prompt-textarea'));
  assert('guarded send may accept only trailing whitespace differences', sha256('hello\n\n'.trimEnd()) === sha256('hello'.trimEnd()));
  assert('guarded send may accept contenteditable whitespace expansion', sha256(normalizeForComposerComparison('A\n\n- B')) === sha256(normalizeForComposerComparison('A\n- B')));

  const defaultConfig = mergeConfig(DEFAULT_CONFIG, {
    apiBase: 'http://127.0.0.1:54345',
    profileId: 'profile',
    promptPath: 'prompt.md',
    responsePath: 'response.md'
  });
  validateConfig(defaultConfig);
  assert('state-based wait mode is required', defaultConfig.responseWaitMode === 'state_based_completion');
  assert('timeoutMs zero means no fixed total response wait', defaultConfig.timeoutMs === 0);
  assert('default Pro monitor poll interval is four minutes', defaultConfig.pollMs === 240000);
  assert('valid UTF-8 prompt passes integrity guard', validatePromptIntegrityText('Please review Meta_workflow Pro Bridge.\nPRO_RESPONSE:\nconfidence_percent: <0-100>', defaultConfig).status === 'prompt_integrity_passed');
  assert('question mark mojibake prompt is blocked', validatePromptIntegrityText('???? agents ???? 100% ????', defaultConfig).status === 'blocked_prompt_integrity_failed');
  assert('replacement character prompt is blocked', validatePromptIntegrityText('PRO_RESPONSE: ' + String.fromCharCode(0xfffd), defaultConfig).status === 'blocked_prompt_integrity_failed');
  assert('common mojibake fragment prompt is blocked', validatePromptIntegrityText('bad ' + String.fromCharCode(0x5bb8, 0x30e4, 0x7dbd), defaultConfig).status === 'blocked_prompt_integrity_failed');
  assert('required prompt substring is enforced', validatePromptIntegrityText('PRO_RESPONSE:', { ...defaultConfig, requiredPromptSubstrings: ['must include this sentence'] }).status === 'blocked_prompt_integrity_failed');
  try {
    validateConfig({ ...defaultConfig, timeoutMs: 600000 });
    throw new Error('validateConfig unexpectedly allowed fixed timeout');
  } catch (error) {
    assert('fixed total response timeout is rejected', error instanceof CliError && error.message.includes('must be 0'));
  }
  try {
    assertUsableLockHint(defaultConfig);
    throw new Error('assertUsableLockHint unexpectedly passed');
  } catch (error) {
    assert('missing lock hint blocks before browser access', error instanceof CliError && error.status === 'blocked_not_found');
  }

  const ambiguousLock = {
    ...defaultConfig.browserWindowLock,
    expectedTitlePattern: 'ChatGPT'
  };
  const ambiguousTargets = [
    { targetId: 'one', title: 'ChatGPT', url: 'https://chatgpt.com/a' },
    { targetId: 'two', title: 'ChatGPT', url: 'https://chatgpt.com/b' }
  ];
  assert('ambiguous title pattern yields multiple candidates', filterTargetsByLock(ambiguousTargets, ambiguousLock).length === 2);

  const exactLock = {
    ...defaultConfig.browserWindowLock,
    expectedTargetId: 'one'
  };
  assert('exact target id yields one candidate', filterTargetsByLock(ambiguousTargets, exactLock).length === 1);
  try {
    assertFormalLockHintNotFuzzy({ ...defaultConfig, browserWindowLock: ambiguousLock });
    throw new Error('assertFormalLockHintNotFuzzy unexpectedly allowed title-only formal lock');
  } catch (error) {
    assert('formal Pro lock blocks title-only fuzzy target lock', error instanceof CliError && error.status === 'blocked_target_lock_fuzzy');
  }
  try {
    assertFormalLockHintNotFuzzy({
      ...defaultConfig,
      expectedConversationId: '69fdbba2-f014-83e8-9477-7f1920dba234',
      browserWindowLock: {
        ...defaultConfig.browserWindowLock,
        expectedUrlPattern: 'chatgpt\\.com/g/PUT_PRO_PROJECT_ID_HERE/c/69fed4a7-9e5c-83e8-b474-ed0bf99e7b50'
      }
    });
    throw new Error('assertFormalLockHintNotFuzzy unexpectedly allowed wrong formal conversation id');
  } catch (error) {
    assert('formal Pro lock URL pattern must include exact registered conversation id', error instanceof CliError && error.status === 'blocked_target_lock_fuzzy');
  }
  assertFormalLockHintNotFuzzy({
    ...defaultConfig,
    expectedConversationId: '69fdbba2-f014-83e8-9477-7f1920dba234',
    browserWindowLock: {
      ...defaultConfig.browserWindowLock,
      expectedUrlPattern: 'chatgpt\\.com/g/PUT_PRO_PROJECT_ID_HERE/c/69fdbba2-f014-83e8-9477-7f1920dba234'
    }
  });
  const longPromptWithStopWords = [
    '# Pro review task: workflow confidence check',
    'Please review stop-generating detection, stop button false positives, and state-based completion.',
    'This is a long prompt that mentions stop words, not a real action control.'
  ].join(' ');
  assert('long prompt containing stop words is not stop action', !isStopGeneratingActionButton({ visibleText: longPromptWithStopWords }));
  assert('real short stop button is stop action', isStopGeneratingActionButton({ ariaLabel: 'Stop generating' }) && isStopGeneratingActionButton({ visibleText: 'Stop' }));
  assert('stop false-positive regression for DEF-20260508-027-001', !isStopGeneratingActionButton({ ariaLabel: longPromptWithStopWords, visibleText: longPromptWithStopWords }));
  assert('reply length does not define completion gate', deriveCompletionSignal({ anchor: { text: 'x'.repeat(12000) }, stopGeneratingVisible: true }) === 'stop_generating_visible');
  assert('end marker does not override stop action state', deriveCompletionSignal({ anchor: { text: `PRO_RESPONSE:\n${'x'.repeat(12000)}\nPRO_RESPONSE_END` }, stopGeneratingVisible: true, endMarkerPresent: true }) === 'stop_generating_visible');
  assert('page idle when stop is absent and send enabled', isPageIdle({ stopGeneratingVisible: false, sendButtonEnabled: true, regenerateOrCopyVisible: false }));
  assert('page not idle while stop generating visible', !isPageIdle({ stopGeneratingVisible: true, sendButtonEnabled: true, regenerateOrCopyVisible: true }));
  assert('network active is not ready', !isNetworkReady({ observed: true, active: true, lastActivityAt: new Date(Date.now() - 60000).toISOString() }, defaultConfig));
  assert('network unknown can fall back to DOM/UI gate', isNetworkReady({ observed: false, active: 'unknown', lastActivityAt: '' }, defaultConfig));
  assert('old DOM mutation state is ready', isDomReady({ observerActive: true, lastMutationAt: new Date(Date.now() - 60000).toISOString() }, defaultConfig));
  assert('recent DOM mutation state is not ready', !isDomReady({ observerActive: true, lastMutationAt: new Date().toISOString() }, defaultConfig));
  const makeRealAssistant = (index, text, id = `msg-${index}`) => ({
    index,
    text,
    hash: sha256(text),
    id: `assistant:${index}:${id}`,
    role: 'assistant',
    dataMessageId: id,
    dataTurnStartMessage: 'true',
    realAssistantMessage: true,
    finalizing: false,
    thinking: false,
    placeholderState: false
  });
  const makePlaceholderAssistant = (index, text, id = `placeholder-${index}`) => ({
    index,
    text,
    hash: sha256(text),
    id: `assistant:${index}:${id}`,
    role: 'assistant',
    dataMessageId: '',
    dataTurnStartMessage: '',
    realAssistantMessage: false,
    finalizing: /Finalizing/.test(text),
    thinking: /thinking/i.test(text),
    placeholderState: true
  });
  const baseline = { assistantMessages: [makeRealAssistant(0, 'old', 'old-0')] };
  const changedSnapshot = { assistantMessages: [makeRealAssistant(0, 'new text', 'old-0')] };
  assert('changed last assistant message creates anchor', Boolean(detectAssistantAnchor(baseline, changedSnapshot, null)?.id));
  const falsePositiveSnapshot = {
    assistantMessages: [
      ...baseline.assistantMessages,
      makePlaceholderAssistant(1, 'ChatGPT said:Pro thinking'),
      { ...makePlaceholderAssistant(2, 'assistant-like stable placeholder'), finalizing: false, thinking: false, placeholderState: true }
    ]
  };
  assert('stop false completion cannot anchor placeholder without message id', !detectAssistantAnchor(baseline, falsePositiveSnapshot, null));
  const multiBaseline = {
    assistantMessages: [
      makeRealAssistant(0, 'old 0', 'old-0'),
      makeRealAssistant(1, 'old 1', 'old-1'),
      makeRealAssistant(2, 'old 2', 'old-2'),
      makeRealAssistant(3, 'old 3', 'old-3')
    ]
  };
  const shortAnchor = { ...makeRealAssistant(4, 'short acknowledgement', 'short'), detectedAt: '2026-05-08T00:00:00.000Z', baselineMessageCount: 4 };
  const finalSnapshot = {
    assistantMessages: [
      ...multiBaseline.assistantMessages,
      shortAnchor,
      makeRealAssistant(5, 'intermediate update', 'mid'),
      makeRealAssistant(6, 'PRO_RESPONSE:\nfinal answer\nPRO_RESPONSE_END', 'final')
    ]
  };
  const finalAnchor = detectAssistantAnchor(multiBaseline, finalSnapshot, shortAnchor, defaultConfig);
  assert('later final assistant with end marker replaces earlier short anchor', finalAnchor?.id === 'assistant:6:final');
  assert('anchor switch is reported when final response replaces short anchor', finalAnchor?.anchorSwitched === true);
  assert('end marker candidate reason is reported', finalAnchor?.selectedAnchorReason === 'latest_end_marker_candidate');
  const latestNoMarker = detectAssistantAnchor(multiBaseline, {
    assistantMessages: [
      ...multiBaseline.assistantMessages,
      shortAnchor,
      makeRealAssistant(5, 'latest without marker', 'latest')
    ]
  }, shortAnchor, defaultConfig);
  assert('latest post-baseline assistant replaces earlier short anchor without marker', latestNoMarker?.id === 'assistant:5:latest');
  assert('real assistant node is not complete before stability window', !isRealAssistantMessageStable(latestNoMarker, 1, defaultConfig));
  assert('real assistant node stable completes capture without end marker', isRealAssistantMessageStable(latestNoMarker, defaultConfig.uiStablePolls, defaultConfig));
  assert('real assistant node stable completion signal is reported', deriveCompletionSignal({ anchor: latestNoMarker, stopGeneratingVisible: false, uiStable: true }) === 'real_assistant_message_node_stable');
  assert('real assistant node settling signal is reported before stability window', deriveCompletionSignal({ anchor: latestNoMarker, stopGeneratingVisible: false, uiStable: false }) === 'real_assistant_message_node_settling');
  assert('stop generating visible signal is reported', deriveCompletionSignal({ anchor: latestNoMarker, stopGeneratingVisible: true }) === 'stop_generating_visible');
  assert('stop absent alone does not complete without a real node', deriveCompletionSignal({ anchor: null, stopGeneratingVisible: false }) === 'waiting_for_new_assistant_message');
  assert('end marker does not bypass stability window', !isRealAssistantMessageStable(finalAnchor, 1, defaultConfig));
  const formalValid = validateFormalResponseText(`PRO_RESPONSE:
confidence_percent: 82
is_100_percent_confident: no
overall_judgment:
  needs more hardening
all_findings:
  - id: P0-1
    severity: P0
    title: sample
fix_order:
  - fix sample
remaining_unknowns:
  - none
PRO_RESPONSE_END`, defaultConfig);
  assert('formal response validator accepts structured non-100 response', formalValid.pro_response_schema_status === 'schema_valid' && formalValid.findingCount === 1);
  const formalInvalid = validateFormalResponseText('short acknowledgement without marker', defaultConfig);
  assert('formal response validator rejects missing PRO_RESPONSE marker', formalInvalid.pro_response_schema_status === 'missing_required_marker');
  const registry = [
    {
      session_key: 'session_0',
      project_id: defaultConfig.projectId,
      conversation_id: '69fdbaab-f80c-83e8-8eca-3cf598fe9851',
      status: 'deleted',
      created_by_pro_bridge: true,
      handoff_count: 0,
      handoff_limit: 30,
      delete_status: 'deleted'
    },
    {
      session_key: 'session_1',
      project_id: defaultConfig.projectId,
      conversation_id: '69fdbba2-f014-83e8-9477-7f1920dba234',
      status: 'active',
      created_by_pro_bridge: true,
      handoff_count: 5,
      handoff_limit: 30,
      delete_status: 'not_requested'
    }
  ];
  const pageState = {
    url: `https://chatgpt.com/g/${defaultConfig.projectId}-produi-jie/project`,
    title: 'ChatGPT - pro',
    projectMatched: true,
    observed_sessions: [
      {
        conversation_id: '69fdbba2-f014-83e8-9477-7f1920dba234',
        conversation_url: `https://chatgpt.com/g/${defaultConfig.projectId}-produi-jie/c/69fdbba2-f014-83e8-9477-7f1920dba234`,
        title_preview: 'Greeting exchange',
        title_hash: sha256('Greeting exchange'),
        title_length: 17,
        current_open: true
      },
      {
        conversation_id: '69febf41-ae38-83e8-b13f-5f86412d2962',
        conversation_url: `https://chatgpt.com/g/${defaultConfig.projectId}-produi-jie/c/69febf41-ae38-83e8-b13f-5f86412d2962`,
        title_preview: 'Test-only observation',
        title_hash: sha256('Test-only observation'),
        title_length: 21,
        current_open: false
      }
    ]
  };
  const reconciled = reconcileProjectSessions(defaultConfig, pageState, registry);
  assert('project sessions reconcile active formal session from page and registry', reconciled.status === 'project_sessions_reconciled' && reconciled.active_formal_session_match === true, reconciled);
  assert('project sessions record unregistered project-local chat without mixing recents', reconciled.unregistered_in_page.length === 1 && reconciled.unregistered_in_page[0].conversation_id === '69febf41-ae38-83e8-b13f-5f86412d2962', reconciled.unregistered_in_page);
  assert('deleted registered session missing from page is not a mismatch', reconciled.missing_in_page.length === 0, reconciled.missing_in_page);
  const missingActive = reconcileProjectSessions(defaultConfig, { ...pageState, observed_sessions: [] }, registry);
  assert('missing active formal session blocks project session gate', missingActive.status === 'blocked_project_session_mismatch' && missingActive.blocked_reasons.includes('active_formal_session_missing_in_project_page'), missingActive);
  assert('parse project conversation URL extracts conversation id', parseProjectConversationUrl(pageState.observed_sessions[0].conversation_url, defaultConfig.projectId).conversationId === '69fdbba2-f014-83e8-9477-7f1920dba234');
  try {
    verifyProjectSessionForUrl(defaultConfig, reconciled, `https://chatgpt.com/g/${defaultConfig.projectId}-produi-jie/c/69febf41-ae38-83e8-b13f-5f86412d2962`, 'send');
    throw new Error('verifyProjectSessionForUrl unexpectedly allowed wrong conversation');
  } catch (error) {
    assert('formal send blocks wrong project conversation id', error instanceof CliError && error.status === 'blocked_project_session_mismatch');
  }

  return { status: 'passed', tests };
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  if (args.command === 'help') {
    console.log(usage());
    return;
  }
  if (args.command === 'self-test') {
    printResult(await selfTest(), args.json);
    return;
  }

  const config = await readConfig(args.config);
  let result;
  if (args.command === 'probe') result = await commandProbe(config);
  else if (args.command === 'targets') result = await commandTargets(config);
  else if (args.command === 'lock') result = await commandLock(config);
  else if (args.command === 'project-sessions') result = await commandProjectSessions(config);
  else if (args.command === 'fill') result = await commandFill(config);
  else if (args.command === 'snapshot') result = await commandSnapshot(config);
  else if (args.command === 'watch') result = await commandWatch(config);
  else if (args.command === 'capture') result = await commandCapture(config);
  else if (args.command === 'capture-latest') result = await commandCaptureLatest(config);
  else if (args.command === 'validate-prompt') result = await commandValidatePrompt(config);
  else if (args.command === 'validate-response') result = await commandValidateResponse(config);
  else if (args.command === 'send') result = await commandSend(config, args);
  else throw new CliError(`Unknown command: ${args.command}`);
  printResult(result, args.json);
}

main().catch((error) => {
  const exitCode = error instanceof CliError ? error.exitCode : 1;
  const result = {
    status: error.status ?? 'failed',
    error: error.message,
    details: error.details ?? {}
  };
  console.error(JSON.stringify(result, null, 2));
  process.exit(exitCode);
});
