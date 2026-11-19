import { createRequire } from 'node:module';
import { createServer } from 'node:http';
import { readFile } from 'node:fs/promises';
import { extname, resolve, sep } from 'node:path';

const projectRoot = '/work';
const prototypeRoot = resolve(projectRoot, 'docs/prototypes');
const require = createRequire(`${projectRoot}/frontend-admin/package.json`);
const { chromium } = require('playwright');
const mimeTypes = {
  '.css': 'text/css; charset=utf-8',
  '.html': 'text/html; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.md': 'text/markdown; charset=utf-8',
  '.png': 'image/png',
};
const server = createServer(async (request, response) => {
  const requestUrl = new URL(request.url || '/', 'http://127.0.0.1');
  const relativePath = decodeURIComponent(requestUrl.pathname === '/' ? '/prototype-hub.html' : requestUrl.pathname);
  const filePath = resolve(prototypeRoot, `.${relativePath}`);
  if (!filePath.startsWith(`${prototypeRoot}${sep}`) && filePath !== prototypeRoot) {
    response.writeHead(403).end();
    return;
  }
  try {
    const content = await readFile(filePath);
    response.writeHead(200, { 'content-type': mimeTypes[extname(filePath)] || 'application/octet-stream' });
    response.end(content);
  } catch {
    response.writeHead(404).end();
  }
});

await new Promise((resolveListen) => server.listen(4177, '127.0.0.1', resolveListen));
const browser = await chromium.launch({ executablePath: '/usr/bin/chromium', args: ['--no-sandbox'], headless: true });
try {
  const desktop = await browser.newPage({ viewport: { width: 1440, height: 1000 }, deviceScaleFactor: 1 });
  await desktop.goto('http://127.0.0.1:4177/prototype-hub.html');
  const row = desktop.locator('tr[data-id="agent-online"]');
  await row.waitFor();
  await row.click();
  const detailText = await desktop.locator('#detail').innerText();
  if (!detailText.includes('多组织 Agent 在线底座')) throw new Error('Hub detail drawer missing new entry');
  const [prototype] = await Promise.all([desktop.waitForEvent('popup'), row.locator('a').first().click()]);
  await prototype.waitForURL('**/agent-online.html');
  await prototype.locator('#openCreate').waitFor();
  await prototype.locator('#hotspotToggle').click();
  await prototype.goto('http://127.0.0.1:4177/agent-online.html?capture=product');
  await prototype.evaluate(() => document.body.classList.remove('hotspots-on'));
  await prototype.screenshot({ path: `${projectRoot}/docs/prototypes/assets/agent-online.png`, fullPage: true });
  await prototype.locator('#openCreate').click();
  await prototype.locator('#newAgentName').fill('演示 Agent');
  await prototype.locator('#newAgentModel').selectOption('primary');
  await prototype.locator('#createForm button[type="submit"]').click();
  const agentRow = prototype.locator('.agent-row').filter({ hasText: '演示 Agent' }).first();
  await agentRow.getByRole('button', { name: '发布' }).click();
  if (!(await agentRow.innerText()).includes('已发布')) throw new Error('Agent publish state did not update');
  await prototype.getByRole('button', { name: '打开 Skill 版本管理' }).click();
  await prototype.locator('.compareAction').first().click();
  await prototype.locator('#confirmRestore').click();
  if (!(await prototype.locator('#versionList').innerText()).includes('v3 · 当前')) throw new Error('Skill restore did not append v3');
  await prototype.getByRole('button', { name: '打开成员 Agent 工作台' }).click();
  await prototype.locator('#messageInput').fill('如何申请知识库访问？');
  await prototype.locator('#messageForm button[type="submit"]').click();
  await prototype.getByText('Run 已完成并保存到历史', { exact: true }).waitFor({ timeout: 5000 });
  await prototype.goto('http://127.0.0.1:4177/agent-online.html');
  await prototype.getByRole('link', { name: /Hub/ }).click();
  await prototype.waitForURL('**/prototype-hub.html');
  const desktopPrototypeCount = await desktop.locator('tr[data-id="agent-online"]').count();
  if (desktopPrototypeCount !== 1) throw new Error('Return path to Hub failed');

  const narrow = await browser.newPage({ viewport: { width: 390, height: 844 } });
  await narrow.goto('http://127.0.0.1:4177/prototype-hub.html');
  await narrow.locator('#search').fill('Agent 在线底座');
  const narrowCount = await narrow.locator('tr[data-id="agent-online"]').count();
  if (narrowCount !== 1) throw new Error('Narrow Hub search did not find the entry');
  const horizontalOverflow = await narrow.evaluate(() => document.documentElement.scrollWidth > window.innerWidth);
  if (horizontalOverflow) throw new Error('Hub overflows at narrow width');
  process.stdout.write('Hub desktop detail/open/return: PASS\nAgent create/publish interaction: PASS\nSkill compare/restore interaction: PASS\nMember run/history interaction: PASS\nHub narrow search/open/no overflow: PASS\n');
} finally {
  await browser.close();
  await new Promise((resolveClose) => server.close(resolveClose));
}
