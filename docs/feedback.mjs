export const ISSUE_URL = 'https://github.com/francisagust198/kotor2-chinese-localization/issues/new';
export const URL_LIMIT = 7000;
export function buildReport(values) {
  const value = key => String(values[key] || '').trim() || '未填写';
  const body = [
    '## 问题概况', `- 类型：${value('category')}`, `- 汉化版本：${value('version')}`,
    `- 发生位置：${value('location')}`, '', '## 问题表现与复现步骤', value('details'),
    '', '## 游戏中的文字', value('current'), '', '## 建议译文或预期效果', value('suggestion'),
    '', '## 游戏环境', `- 分辨率与显示模式：${value('resolution')}`,
    `- 高帧修复与中文缓存兼容：${value('native')}`, `- 存档情况：${value('save')}`,
    '', '### 其他 MOD 与加载顺序', value('mods'), '', '## 截图',
    '请在此粘贴或拖入截图；没有截图可删除本节。'
  ].join('\n');
  const title = `[汉化反馈] ${value('title')}`;
  const url = new URL(ISSUE_URL);
  url.searchParams.set('template', 'translation.md');
  url.searchParams.set('title', title);
  url.searchParams.set('body', body);
  const tooLong = url.href.length > URL_LIMIT;
  if (tooLong) url.searchParams.delete('body');
  return {title, body, url: url.href, tooLong};
}

if (typeof document !== 'undefined') {
  const form = document.getElementById('feedback-form');
  const message = document.getElementById('message');
  const preview = document.getElementById('preview');
  const previewDetails = document.getElementById('preview-details');
  const continueLink = document.getElementById('continue-link');
  const remember = document.getElementById('remember');
  const fields = [...form.querySelectorAll('[name]')];
  const storageKey = 'kotor2-feedback-draft-v1';
  const preferenceKey = 'kotor2-feedback-remember-v1';
  let draftStorageAvailable = true;
  const values = () => Object.fromEntries(fields.map(el => [el.name, el.value]));
  const report = () => {const result = buildReport(values()); preview.value = result.body; return result;};
  try {
    remember.checked = localStorage.getItem(preferenceKey) !== 'false';
    if (remember.checked) {
      const draft = JSON.parse(localStorage.getItem(storageKey) || 'null');
      if (draft && typeof draft === 'object') {
        for (const field of fields) if (typeof draft[field.name] === 'string') field.value = draft[field.name];
        message.textContent = '已恢复此浏览器中的草稿，尚未提交。';
      }
    }
  } catch {draftStorageAvailable = false; message.textContent = '此浏览器无法保留草稿。关闭网页前可复制或下载反馈内容。';}
  report();
  function saveDraft() {
    if (!draftStorageAvailable) return;
    try {
      localStorage.setItem(preferenceKey, String(remember.checked));
      if (remember.checked) localStorage.setItem(storageKey, JSON.stringify(values()));
      else localStorage.removeItem(storageKey);
    } catch {draftStorageAvailable = false; message.textContent = '草稿未能保存在本机，请复制或下载反馈内容。';}
  }
  form.addEventListener('input', () => {report(); saveDraft(); continueLink.hidden = true;});
  remember.addEventListener('change', saveDraft);
  async function copyBody() {
    const result = report();
    try {
      if (!navigator.clipboard?.writeText) throw new Error('clipboard unavailable');
      await navigator.clipboard.writeText(result.body);
      return true;
    } catch {previewDetails.open = true; preview.focus(); preview.select(); return false;}
  }
  document.getElementById('copy').addEventListener('click', async () => {
    const copied = await copyBody();
    message.textContent = copied ? '反馈内容已复制，尚未提交。' : '请复制下方已选中的反馈内容，或下载反馈文本。';
  });
  form.addEventListener('submit', event => {
    event.preventDefault();
    if (!form.reportValidity()) return;
    if (['title', 'location', 'details'].some(key => !values()[key].trim())) {
      message.textContent = '请填写问题描述、发生位置和复现信息，内容不能只有空格。';
      return;
    }
    const result = report();
    saveDraft();
    if (result.tooLong) {
      previewDetails.open = true;
      continueLink.href = result.url;
      continueLink.hidden = false;
      message.textContent = '内容较长，无法自动带入。请复制或下载下方反馈内容，再打开 GitHub 提交页，将内容粘贴到正文后提交。';
      preview.focus(); preview.select();
      return;
    }
    message.textContent = '正在前往 GitHub。请检查正文、添加截图，再确认提交；本机草稿会保留。';
    window.location.assign(result.url);
  });
  document.getElementById('download').addEventListener('click', () => {
    const result = report();
    const url = URL.createObjectURL(new Blob([result.body], {type:'text/markdown;charset=utf-8'}));
    const link = document.createElement('a'); link.href = url; link.download = 'KOTOR2-汉化反馈.md'; link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
    message.textContent = '反馈文本已下载，尚未提交。';
  });
  document.getElementById('clear').addEventListener('click', () => {
    const keepPreference = remember.checked;
    form.reset(); remember.checked = keepPreference;
    try {localStorage.removeItem(storageKey);} catch {}
    continueLink.hidden = true;
    report(); message.textContent = '已清空本机草稿。';
  });
}
