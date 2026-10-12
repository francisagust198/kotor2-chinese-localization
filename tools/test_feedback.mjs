import assert from 'node:assert/strict';
import test from 'node:test';
import {buildReport, ISSUE_URL, URL_LIMIT} from '../docs/feedback.mjs';

test('Chinese text and reserved characters survive the GitHub URL round trip', () => {
  const input = {title:'修理提示 & 字体 #1', category:'漏译或英文残留', location:'佩拉格斯终端', details:'第1行\n第2行：需要零件 + 2？', current:'A&B <repair> 100%', suggestion:'需要两个零件。'};
  const result = buildReport(input);
  const url = new URL(result.url);
  assert.equal(result.tooLong, false);
  assert.equal(url.origin + url.pathname, ISSUE_URL);
  assert.equal(url.searchParams.get('template'), 'translation.md');
  assert.equal(url.searchParams.get('title'), '[汉化反馈] ' + input.title);
  assert.equal(url.searchParams.get('body'), result.body);
  for (const key of ['location','details','current','suggestion']) assert.ok(result.body.includes(input[key]));
  assert.equal(url.hash, '');
});

test('long feedback preserves full content and switches to manual paste', () => {
  const input = {title:'说明显示问题', details:'中'.repeat(12000)};
  const result = buildReport(input);
  const url = new URL(result.url);
  assert.equal(result.tooLong, true);
  assert.equal(url.searchParams.has('body'), false);
  assert.ok(result.url.length < URL_LIMIT);
  assert.ok(result.body.includes(input.details));
});

test('optional fields are not falsely presented as confirmed environment data', () => {
  const result = buildReport({title:'问题', details:'测试'});
  assert.ok(result.body.includes('汉化版本：未填写'));
  assert.ok(result.body.includes('高帧修复与中文缓存兼容：未填写'));
});
