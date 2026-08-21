import { applyHarnessResult, buildHarnessPrompt } from './workspace.mjs';
import { streamHarness } from './harness/registry.mjs';
import crypto from 'node:crypto';
import { tryLocalAssist } from './local-assist.mjs';

const SESSIONS = new Map();

export function createLiveSession({ workspace, harnessId, language }) {
  const session = { id: crypto.randomUUID(), workspace, harnessId, language: language === 'en' ? 'en' : 'zh', events: [], subscribers: new Set(), queue: Promise.resolve(), closed: false, cancel: null };
  SESSIONS.set(session.id, session);
  emit(session, 'ready', { sessionId: session.id, harnessId });
  return session;
}

export function getLiveSession(id) { return SESSIONS.get(id); }

export function subscribeLiveSession(session, subscriber) {
  for (const event of session.events) subscriber(event);
  session.subscribers.add(subscriber);
  return () => session.subscribers.delete(subscriber);
}

export function sendLiveMessage(session, message) {
  const text = String(message || '').trim();
  if (!text) throw coded('MESSAGE_REQUIRED', 'Message is required');
  if (session.closed) throw coded('LIVE_SESSION_CLOSED', 'Live session is closed');
  session.queue = session.queue.then(() => runTurn(session, text));
  return session.queue;
}

export function closeLiveSession(session) {
  if (session.closed) return;
  session.closed = true; session.cancel?.(); emit(session, 'closed', {}); SESSIONS.delete(session.id);
}

async function runTurn(session, message) {
  emit(session, 'user', { text: message });
  const local = tryLocalAssist(session.workspace, message, session.language);
  if (local) { emit(session, 'status', { state: 'local' }); emit(session, 'complete', applyHarnessResult(session.workspace, message, local, session.language)); return; }
  const history = session.workspace.messages.slice(-10).map((item) => `${item.role}: ${item.text}`).join('\n');
  const prompt = `${buildHarnessPrompt(session.workspace, message, session.language)}\n\nRecent conversation (use only as context):\n${history}`;
  emit(session, 'turn-start', { message });
  await new Promise((resolve) => {
    streamHarness(session.harnessId, { prompt, language: session.language, context: { workspaceId: session.workspace.id, liveSessionId: session.id } }, {
      onChunk: (text) => emit(session, 'delta', { text }),
      onStatus: () => emit(session, 'status', { state: 'working' }),
      onComplete: (result) => { const applied = applyHarnessResult(session.workspace, message, result, session.language); emit(session, 'complete', applied); resolve(); },
      onError: (error) => { emit(session, 'error', { code: error.code || 'HARNESS_ERROR', message: error.message }); resolve(); }
    }).then((controller) => { session.cancel = controller.cancel; }).catch((error) => { emit(session, 'error', { code: error.code || 'HARNESS_ERROR', message: error.message }); resolve(); });
  });
  session.cancel = null;
}

function emit(session, type, payload) {
  const event = { id: crypto.randomUUID(), type, payload, at: new Date().toISOString() };
  session.events.push(event); session.events = session.events.slice(-100);
  for (const subscriber of session.subscribers) subscriber(event);
}

function coded(code, message) { const error = new Error(message); error.code = code; return error; }
