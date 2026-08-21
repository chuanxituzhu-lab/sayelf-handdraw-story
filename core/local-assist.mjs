import { validateProject } from './continuity.mjs';

export function tryLocalAssist(workspace, message, language = 'zh') {
  const text = String(message || '').trim().toLowerCase();
  if (!workspace.project) {
    if (/(状态|status|连续性|continuity|预览|preview)/i.test(text)) return reply(language, 'empty');
    return null;
  }
  const report = validateProject(workspace.project);
  if (/(连续性|continuity|一致性|consistency|检查|check)/i.test(text)) {
    return reply(language, report.status === 'PASS' ? 'pass' : 'revise', report);
  }
  if (/(状态|status|项目概览|summary|概览)/i.test(text)) return reply(language, 'status', report);
  if (/(预览|preview|四格|frames|media)/i.test(text)) return reply(language, 'preview', report);
  return null;
}

function reply(language, kind, report) {
  const en = language === 'en';
  const messages = {
    empty: en ? 'There is no local project yet. Describe the story idea to start one.' : '本地还没有故事项目，请先描述故事想法。',
    pass: en ? `Local continuity check: PASS. ${report.issues.length} issues.` : `本地连续性检查：通过。发现 ${report.issues.length} 个问题。`,
    revise: en ? `Local continuity check: REVISE. ${report.issues.length} issues need attention.` : `本地连续性检查：需要修改。有 ${report.issues.length} 个问题需要处理。`,
    status: en ? 'The project summary is available in the backstage panel. No model call was needed.' : '项目摘要已显示在后台面板，本次没有调用大模型。',
    preview: en ? 'The four local preview frames are ready for generated media. No model call was needed.' : '四格本地预览区已准备好生成内容，本次没有调用大模型。'
  };
  return { text: messages[kind], data: null, media: [] };
}
