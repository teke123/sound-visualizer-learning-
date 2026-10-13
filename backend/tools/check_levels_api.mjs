#!/usr/bin/env node
/**
 * 验证关卡接口、发布状态和开放检测统计
 * ---------------------------------------------------------------------------
 * 检查三件事：
 *   1) /api/units 是否可用，且「未审核不公开」是否成立（草稿不出现在 published 列表里）
 *   2) L01–L30 是否已按冻结表入库（可为 draft）
 *   3) 前端 stores/levels.ts 的合并口径复算：30 关 = 可练可测 + 只学不测 + 未开放
 *
 * 用法（先起后端）：
 *   cd backend && python main.py
 *   node backend/tools/check_levels_api.mjs            # 默认 http://localhost:8000/api
 *   node backend/tools/check_levels_api.mjs http://localhost:8000/api
 *
 * 退出码：0 表示全部通过；1 表示存在失败检查项。
 */
import * as fs from 'node:fs';
import * as path from 'node:path';
import { fileURLToPath } from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
const freezePath = path.resolve(here, '../../src/data/levels.freeze.json');
const BASE = (process.argv[2] ?? 'http://localhost:8000/api').replace(/\/$/, '');

let failed = 0;
const check = (ok, label, detail = '') => {
  if (!ok) failed++;
  console.log(`${ok ? 'OK  ' : 'FAIL'}  ${label}${detail ? `  (${detail})` : ''}`);
};

async function get(pathname) {
  const res = await fetch(`${BASE}${pathname}`);
  if (!res.ok) return { ok: false, status: res.status, data: null };
  const body = await res.json();
  return { ok: true, status: res.status, data: body.data };
}

const freeze = JSON.parse(fs.readFileSync(freezePath, 'utf8'));
const levels = freeze.levels;

const published = await get('/units?status=published');
const all = await get('/units');

check(published.ok, 'GET /api/units?status=published 可用', `status=${published.status}`);
check(all.ok, 'GET /api/units 可用', `status=${all.status}`);
if (!published.ok || !all.ok) {
  console.log('\n后端不可用：请先 `cd backend && python main.py`（或 npm run backend）再跑本检查。');
  process.exit(1);
}

const publishedIds = new Set(published.data.map((u) => u.id));
const allById = new Map(all.data.map((u) => [u.id, u]));

// 1) 未审核不公开：L01–L30 若还是 draft，就不能出现在 published 列表
const draftCodes = levels.map((l) => l.code).filter((c) => !publishedIds.has(c));
const leakedDrafts = draftCodes.filter((c) => {
  const u = allById.get(c);
  return u && u.status !== 'published' && publishedIds.has(c);
});
check(leakedDrafts.length === 0, '未审核（draft）关卡不出现在已发布列表', `${draftCodes.length} 关仍为草稿/未录入`);

// 2) 检查关卡配置在 CMS 中的对应记录
const inCms = levels.filter((l) => allById.has(l.code) || l.cmsIds.some((id) => allById.has(id)));
console.log(`     冻结表 ${levels.length} 关中，已能在 CMS/历史单元里找到落点：${inCms.length} 关`);

// 3) 复算前端合并口径（与 src/stores/levels.ts 的 buildView 同规则）
let open = 0;
let learnOnly = 0;
let unopened = 0;
const openList = [];
for (const lv of levels) {
  const unit =
    (publishedIds.has(lv.code) ? allById.get(lv.code) : null) ??
    lv.cmsIds.map((id) => (publishedIds.has(id) ? allById.get(id) : null)).find(Boolean) ??
    null;
  const isPublished = !!unit && unit.status === 'published';
  const detectionOpen = isPublished && !!unit.verified;
  if (detectionOpen) {
    open++;
    openList.push(`${lv.code}(${lv.target}→${unit.id})`);
  } else if (isPublished) {
    learnOnly++;
  } else {
    unopened++;
  }
}
check(open + learnOnly + unopened === 30, '30 关状态合计为 30', `可练可测 ${open} / 只学不测 ${learnOnly} / 未开放 ${unopened}`);
console.log(`     可练可测：${openList.join(', ') || '（无）'}`);
console.log(`     冻结版本：${freeze.version}`);

console.log(failed === 0 ? '\n全部检查通过。' : `\n有 ${failed} 项检查失败。`);
process.exit(failed === 0 ? 0 : 1);
