import { validateProject } from './continuity.mjs';

export function tryLocalAssist(workspace, message, language = 'zh') {
  const text = String(message || '').trim().toLowerCase();
  if (/(规划|计划|镜头|shot|plan|storyboard)/i.test(text) && /(狐狸|fox|故事|story)/i.test(text)) {
    return reply(language, 'plan');
  }
  if (/(蒲公英|dandelion)/i.test(text) && /(规划|计划|镜头|shot|plan|storyboard)/i.test(text)) {
    return reply(language, 'dandelionPlan');
  }
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

function reply(language, kind, report = { issues: [] }) {
  const en = language === 'en';
  const messages = {
    plan: en ? 'Offline shot plan (no model call):\n\nShot 1 · Snowfield setup · 4s\nA small fox wearing a red scarf stands on the left side of a quiet snowy landscape and looks toward the distant right. Soft winter light, pencil-and-ink hand-drawn lines, visible paper grain. The scarf moves gently in the breeze.\n\nShot 2 · Following the tracks · 5s\nIn the same snowfield and light, the fox walks from left to right while studying paw prints. Its tail sways lightly and the camera follows. Keep the red scarf, fox proportions, palette, and direction consistent. Do not show the home yet.' : '本地离线镜头规划（没有调用大模型）：\n\n镜头 1 · 雪地建立 · 4 秒\n小狐狸戴着红围巾，站在寂静雪地的画面左侧，望向右侧远方。使用柔和冬日光、铅笔与墨线、可见纸张颗粒。红围巾随微风轻轻摆动。\n\n镜头 2 · 沿脚印寻找 · 5 秒\n延续同一片雪地与光线，小狐狸从左向右行走，低头观察雪地脚印。尾巴轻摆，镜头轻微跟随。保持红围巾、狐狸比例、色彩和移动方向一致；暂不显示家。',
    dandelionPlan: en ? 'Offline shot plan (no model call):\n\nShot 1 · The mature dandelion · 4s\nA fully mature dandelion remains attached to its green stem in a quiet meadow. The camera holds close on the white seed head as sunlight catches the fine parachutes.\n\nShot 2 · Lifted by the wind · 5s\nA gentle gust loosens the mature seed head from the mother plant. Individual seeds rise and dance through the air, drifting from left to right. Keep the meadow, warm hand-drawn texture, and wind direction continuous.' : '本地离线镜头规划（没有调用大模型）：\n\n镜头 1 · 成熟的蒲公英 · 4 秒\n一朵成熟的蒲公英仍连接在绿色茎秆上，生长在安静的草地中。镜头近距离观察白色绒球，阳光照亮细小的冠毛。\n\n镜头 2 · 随风飞舞 · 5 秒\n一阵微风使成熟的种球脱离母株，种子一个个升起，在空中轻盈飞舞并由左向右飘散。保持草地、暖手绘质感和风向连续。',
    empty: en ? 'There is no local project yet. Describe the story idea to start one.' : '本地还没有故事项目，请先描述故事想法。',
    pass: en ? `Local continuity check: PASS. ${report.issues.length} issues.` : `本地连续性检查：通过。发现 ${report.issues.length} 个问题。`,
    revise: en ? `Local continuity check: REVISE. ${report.issues.length} issues need attention.` : `本地连续性检查：需要修改。有 ${report.issues.length} 个问题需要处理。`,
    status: en ? 'The project summary is available in the backstage panel. No model call was needed.' : '项目摘要已显示在后台面板，本次没有调用大模型。',
    preview: en ? 'The four local preview frames are ready for generated media. No model call was needed.' : '四格本地预览区已准备好生成内容，本次没有调用大模型。'
  };
  return { text: messages[kind], data: null, media: [] };
}
