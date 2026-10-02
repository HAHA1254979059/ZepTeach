// The host may restore draft state, but only a received message becomes a log.
const q = selector => root.querySelector(selector);
const form = q('[data-zt-prediction]');
const status = q('[data-zt-status]');
function capabilities() {
  const styles = getComputedStyle(root);
  return {script_execution:true,
    host_styles:['--foreground','--muted','--primary','--viz-series-1'].every(name=>!!styles.getPropertyValue(name).trim()),
    follow_up:typeof window.openai?.sendFollowUpMessage === 'function'};
}
let renderingReady = capabilities().host_styles;
root.dataset.rendererReady = String(renderingReady);
const scope = [spec.interaction_id, spec.learning_thread_id, spec.lab_id, spec.part_id].join('/');
let state = {scope, prediction: null, events: [], simulationCount: 0, completionRequested: false};
let sending = false;
const acknowledged = new Set(spec.acknowledged_event_ids || []);
const MAX_STATE_BYTES = 14500;
function say(message, error = false) {
  status.textContent = message;
  status.dataset.error = String(error);
}
function snapshot() {
  return {zepteach: {...state, draft: Object.fromEntries(new FormData(form).entries())}};
}
function fits(value) { return new TextEncoder().encode(JSON.stringify(value)).length < MAX_STATE_BYTES; }
function save() {
  const privateContent = snapshot();
  if (!fits(privateContent)) { say('本地记录缓冲已满，请发送到对话并等待接收确认。', true); return false; }
  try {
    Promise.resolve(window.openai?.setWidgetState?.({
      modelContent: {interaction_id: spec.interaction_id, learning_thread_id: spec.learning_thread_id,
        capabilities: capabilities(),
        phase: state.completionRequested ? 'review_requested' : state.prediction ? 'exploring' : 'predicting'},
      privateContent
    })).catch(() => {});
  } catch (_) {}
  return true;
}
function makeEvent(type, text, behavior, values = {}) {
  const event = {schema_version: 1,
    event_id: 'ui-' + (globalThis.crypto?.randomUUID?.() || Date.now() + '-' + Math.random().toString(16).slice(2)),
    timestamp_utc: new Date().toISOString(), learning_thread_id: spec.learning_thread_id,
    lab_id: spec.lab_id, part_id: spec.part_id, event_type: type,
    source: {kind: 'inline_control', reference: spec.interaction_id + ':' + type},
    actual_user_input: text, observed_ui_behavior: behavior, values,
    artifact_path_if_exists: spec.artifact_path};
  return event;
}
function queue(event) {
  const candidate = {zepteach: {...state, events: [...state.events, event]}};
  if (!fits(candidate) || state.events.length >= 60) {
    say('记录缓冲已满，请先发送到对话。未丢弃已有记录。', true); return false;
  }
  state.events.push(event);
  save();
  return true;
}
function update() {
  const wasReady = renderingReady;
  renderingReady = capabilities().host_styles;
  root.dataset.rendererReady = String(renderingReady);
  q('[data-zt-scene]').hidden = !renderingReady;
  q('[data-zt-simulation]').hidden = !state.prediction || !renderingReady;
  q('[data-zt-reflection]').hidden = state.simulationCount === 0 || !renderingReady;
  for (const element of form.elements) element.disabled = !!state.prediction || !renderingReady;
  q('[data-zt-confirm]').disabled = state.completionRequested;
  if (wasReady && !renderingReady) say('此端交互显示不完整，请按对话正文继续当前环节。', true);
  if (!wasReady && renderingReady) say('此端显示已恢复，可继续当前环节。');
}
function restore(saved) {
  if (!saved || saved.scope !== scope || !Array.isArray(saved.events)) return;
  state = {...state, ...saved, events: saved.events.filter(event => !acknowledged.has(event.event_id))};
  const draft = saved.draft || state.prediction?.values || {};
  for (const element of form.elements) if (element.name && draft[element.name] != null) element.value = draft[element.name];
  update();
  if (state.prediction) say('已恢复本地预测。对话收到并写入日志后才有持久回执。');
}
q('[data-zt-title]').textContent = spec.title;
q('[data-zt-prompt]').textContent = spec.prompt;
q('[data-zt-confidence]').hidden = !spec.collect_confidence;
if (!q('[data-zt-fields]').children.length) for (const field of spec.prediction_fields) {
  const label = document.createElement('label');
  label.className = 'form-label';
  label.append(document.createTextNode(field.label));
  let input;
  if (field.kind === 'choice') {
    input = document.createElement('select'); input.className = 'form-select';
    input.add(new Option('请选择', ''));
    for (const option of field.options) input.add(new Option(option.label, option.value));
  } else {
    input = document.createElement('input'); input.className = 'form-control';
    input.type = field.kind === 'numeric' ? 'number' : 'text';
    if (field.kind === 'numeric') {
      input.step = field.step ?? 'any';
      if (field.min != null) input.min = field.min;
      if (field.max != null) input.max = field.max;
    }
  }
  input.name = field.field_id; input.required = true;
  label.append(input); q('[data-zt-fields]').append(label);
}
form.addEventListener('input', save);
function submitPrediction(event) {
  event.preventDefault();
  if (!renderingReady || state.prediction || !form.reportValidity()) return;
  const values = Object.fromEntries(new FormData(form).entries());
  if (!values.reason.trim()) { say('请先写出你的理由。', true); return; }
  const answer = makeEvent('answer', JSON.stringify(values), '用户保存预测与理由，模拟区解锁。', values);
  if (values.confidence !== '' && values.confidence != null && spec.collect_confidence) {
    answer.confidence_if_supplied = Number(values.confidence);
  }
  if (!queue(answer)) return;
  state.prediction = {values}; update(); save();
  say('预测已保存在本地界面；可进行实验，再将操作与回答发送到对话。');
}
q('[data-zt-predict]').addEventListener('click', submitPrediction);
form.addEventListener('submit', submitPrediction);
form.addEventListener('keydown', event => {
  if (event.key === 'Enter' && (event.ctrlKey || event.target.tagName !== 'TEXTAREA')) {
    event.preventDefault(); submitPrediction(event);
  }
});
async function send() {
  if (sending || !state.events.length) return;
  const prompt = '[ZepTeach interaction] ' + JSON.stringify({schema_version: 1,
    learning_thread_id: spec.learning_thread_id, events: state.events});
  if (typeof window.openai?.sendFollowUpMessage !== 'function') {
    q('[data-zt-manual]').hidden = false; q('[data-zt-packet]').value = prompt;
    say('客户端没有发送能力。请把下方真实记录发送到学习对话；尚未写入日志。'); return;
  }
  sending = true;
  say('等待客户端发送确认。');
  try {
    await window.openai.sendFollowUpMessage({prompt, title: '发送本环节的操作、回答和反馈'});
    say('发送请求已返回。等待学习对话接收并写入日志；课程没有自动前进。');
  } catch (_) {
    q('[data-zt-manual]').hidden = false; q('[data-zt-packet]').value = prompt;
    say('发送未成功。已有本地记录仍在，请将下方文本发送到学习对话。', true);
  } finally { sending = false; }
}
q('[data-zt-send]').addEventListener('click', send);
q('[data-zt-feedback-send]').addEventListener('click', () => {
  const input = q('[data-zt-feedback-text]'); const text = input.value;
  if (!text.trim()) { say('请先填写实际遇到的问题。', true); return; }
  if (queue(makeEvent(q('[data-zt-feedback-type]').value, text, '用户点击发送反馈。'))) {
    input.value = ''; send();
  }
});
q('[data-zt-confirm]').addEventListener('click', () => {
  if (!state.simulationCount || state.completionRequested) return;
  const text = q('[data-zt-observation]').value;
  if (!text.trim()) { say('请先说明你的观察或仍有的疑问。', true); return; }
  if (!queue(makeEvent('completion_confirmation', text,
    '用户确认当前环节并请求老师检查。未进入下一环节。'))) return;
  state.completionRequested = true; update(); save(); send();
});
root.ztInteractive = {
  capabilities,
  get prediction() { return state.prediction?.values || null; },
  get canSimulate() { return renderingReady && !!state.prediction && !state.completionRequested; },
  perform(action, work) {
    if (!renderingReady || !state.prediction || state.completionRequested) {
      say('请先保存预测与理由；已请求检查的环节需等待老师回应。', true); return null;
    }
    // Reserve space before executing an action so a full buffer cannot run
    // an experiment whose event would then be silently lost.
    if (!fits({padding: ' '.repeat(2500), state}) || state.events.length >= 60) {
      say('请先发送已有操作，并等待学习对话确认接收。', true); return null;
    }
    try {
      const result = work();
      if (!result || typeof result.observed_ui_behavior !== 'string') throw new Error('missing observation');
      const logged = makeEvent('ui_action', action.label, result.observed_ui_behavior,
        {action: action.id, parameters: action.parameters || {}, result: result.values || {}});
      if (!queue(logged)) return null;
      state.simulationCount += 1; update(); save();
      return result;
    } catch (_) { say('实验未完成，请检查输入或报告实际错误。', true); return null; }
  },
  send,
  get phase() { return state.completionRequested ? 'review_requested' : state.prediction ? 'exploring' : 'predicting'; }
};
restore(window.openai?.widgetState?.privateContent?.zepteach);
window.addEventListener('openai:set_globals', event => {
  restore(event.detail?.globals?.widgetState?.privateContent?.zepteach);
  update();
});
update();
q('[data-zt-feedback-send]').disabled = false;
if (!renderingReady) say('此端交互显示不完整，请按对话正文提供预测与理由。', true);
