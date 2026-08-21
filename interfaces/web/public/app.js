const $ = (selector) => document.querySelector(selector);
const previous = $('#previous');
const current = $('#current');
const run = $('#run');
const card = $('#status-card');
const issues = $('#issue-list');

$('#load-example').addEventListener('click', loadExample);
$('#previous-file').addEventListener('change', (event) => loadFile(event, previous));
$('#current-file').addEventListener('change', (event) => loadFile(event, current));
document.querySelectorAll('[data-clear]').forEach((button) => button.addEventListener('click', () => { $(`#${button.dataset.clear}`).value = ''; updateState(button.dataset.clear); }));
[previous, current].forEach((editor) => editor.addEventListener('input', () => updateState(editor.id)));
run.addEventListener('click', inspect);

async function loadExample() {
  busy(true, '正在载入…');
  try {
    const response = await fetch('/api/examples');
    if (!response.ok) throw new Error('示例载入失败');
    const data = await response.json();
    previous.value = pretty(data.previous); current.value = pretty(data.current);
    updateState('previous'); updateState('current');
    show('idle', '···', '等待检查', '示例已载入。运行检查以确认两个镜头之间的连续性。');
  } catch (error) { showError(error.message); }
  finally { busy(false); }
}

async function loadFile(event, editor) {
  const file = event.target.files[0];
  if (!file) return;
  try { editor.value = pretty(JSON.parse(await file.text())); updateState(editor.id); }
  catch { setState(editor.id, 'JSON 无法解析', 'invalid'); }
  event.target.value = '';
}

async function inspect() {
  let before; let now;
  try { now = parse(current, true); before = parse(previous, false); }
  catch (error) { return showError(error.message); }
  busy(true, '检查中…');
  try {
    const route = before ? '/api/continuity' : '/api/validate';
    const payload = before ? { previous: before, current: now } : { project: now };
    const response = await fetch(route, { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify(payload) });
    const report = await response.json();
    if (!response.ok) throw new Error(report.error || '检查失败');
    render(report, Boolean(before));
  } catch (error) { showError(error.message); }
  finally { busy(false); }
}

function render(report, compared) {
  const problems = [...(report.drifts || []).map((item) => ({ ...item, message: '稳定视觉信息与上一镜头不一致' })), ...(report.validation?.issues || report.issues || [])];
  const pass = report.status === 'PASS';
  show(pass ? 'pass' : 'revise', pass ? '✓' : '!', pass ? '连续性通过' : '需要修订', pass ? (compared ? '当前镜头保持了角色、道具、风格与场景连续性，可以进入下一步。' : '当前项目的结构、引用和时间线有效。') : `发现 ${problems.length} 个需要处理的问题。`);
  if (!problems.length) issues.innerHTML = '<div class="empty-report">没有发现漂移或结构问题。</div>';
  else problems.forEach((problem) => issues.append(renderIssue(problem)));
  $('#results').scrollIntoView({ behavior: 'smooth', block: 'start' });
}

function renderIssue(problem) {
  const item = document.createElement('article'); item.className = 'issue';
  const header = document.createElement('header'); const code = document.createElement('code'); const path = document.createElement('small'); const message = document.createElement('p');
  code.textContent = problem.code || 'CONTINUITY'; path.textContent = problem.path || '$'; message.textContent = problem.message || '连续性信息发生变化';
  header.append(code, path); item.append(header, message); return item;
}

function parse(editor, required) {
  if (!editor.value.trim()) { if (required) throw new Error('请先输入当前镜头 JSON'); return null; }
  try { return JSON.parse(editor.value); }
  catch { throw new Error(`${editor === previous ? '上一镜头' : '当前镜头'} JSON 无法解析`); }
}

function updateState(id) {
  const editor = $(`#${id}`);
  if (!editor.value.trim()) return setState(id, '等待输入', '');
  try { const value = JSON.parse(editor.value); setState(id, `JSON 有效 · ${value.story?.title || '未命名项目'}`, 'valid'); }
  catch { setState(id, 'JSON 无法解析', 'invalid'); }
}
function setState(id, text, className) { const state = $(`#${id}-state`); state.textContent = text; state.className = className; }
function show(kind, symbol, title, summary) { card.className = `status-card ${kind}`; $('#status-symbol').textContent = symbol; $('#status-text').textContent = title; $('#result-summary').textContent = summary; issues.replaceChildren(); }
function showError(message) { show('error', '×', '无法检查', message); }
function busy(value, label = '运行连续性检查') { run.disabled = value; run.querySelector('span').textContent = value ? label : '运行连续性检查'; }
function pretty(value) { return JSON.stringify(value, null, 2); }
