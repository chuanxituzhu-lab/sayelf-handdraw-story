import crypto from 'node:crypto';
import { validateProject } from './continuity.mjs';

export function createWorkspace(language = 'zh') {
  return { id: crypto.randomUUID(), language: language === 'en' ? 'en' : 'zh', project: null, messages: [], updatedAt: new Date().toISOString() };
}

export function workspaceView(workspace) {
  const project = workspace.project;
  return {
    id: workspace.id,
    language: workspace.language,
    hasProject: Boolean(project),
    summary: project ? {
      title: project.story?.title || '',
      characters: (project.characters || []).map((item) => item.name || item.id),
      style: project.style?.id || '',
      scenes: (project.scenes || []).length,
      shots: (project.shots || []).length,
      status: validateProject(project).status
    } : null,
    messages: workspace.messages.slice(-30),
    updatedAt: workspace.updatedAt
  };
}

export function buildHarnessPrompt(workspace, userMessage, language) {
  const locale = language === 'en' ? 'en' : 'zh';
  const contract = locale === 'en'
    ? 'Reply naturally. If you create or revise the hidden project, append one JSON code block with {"message":"short reply","project":<complete v0.1.0 project>}. Do not expose raw project JSON otherwise.'
    : '请自然回复。如果你创建或修改后台项目，请在末尾附加一个 JSON 代码块，格式为 {"message":"简短回复","project":<完整的 v0.1.0 项目>}。除此之外不要展示原始项目 JSON。';
  const context = workspace.project ? JSON.stringify(workspace.project) : 'null';
  return `${contract}\n\nHidden current project:\n${context}\n\nUser request:\n${userMessage}`;
}

export function applyHarnessResult(workspace, userMessage, result, language) {
  const data = result.data;
  let projectAccepted = false;
  let validation = null;
  if (data?.project) {
    validation = validateProject(data.project);
    if (validation.status === 'PASS') { workspace.project = data.project; projectAccepted = true; }
  }
  const reply = data?.message || result.text || '';
  workspace.language = language === 'en' ? 'en' : 'zh';
  const media = Array.isArray(result.media) ? result.media : [];
  workspace.messages.push({ role: 'user', text: userMessage }, { role: 'assistant', text: stripJsonBlock(reply), media });
  workspace.updatedAt = new Date().toISOString();
  return { reply: stripJsonBlock(reply), media, projectAccepted, validation, workspace: workspaceView(workspace) };
}

function stripJsonBlock(text) { return String(text || '').replace(/```json[\s\S]*?```/gi, '').trim(); }
