// Read the logged-in page's rendered grids. No direct trading-data requests.
const target = JSON.parse(process.argv[2]);
const endpoints = process.env.JQCLI_CDP_URL ? [process.env.JQCLI_CDP_URL] : ['http://127.0.0.1:9222', 'http://127.0.0.1:9223'];
let ws;
try {
  const matches = [];
  for (const base of endpoints) {
    const u = new URL(base);
    if (!['127.0.0.1', 'localhost', '[::1]'].includes(u.hostname)) throw Error('PAGE_CDP_MUST_BE_LOCAL');
    let pages;
    try { pages = await (await fetch(`${base}/json/list`, {signal: AbortSignal.timeout(2000)})).json(); } catch { continue; }
    for (const p of pages) {
      const url = new URL(p.url || 'about:blank');
      if (url.hostname !== 'www.joinquant.com' || url.pathname !== '/algorithm/live/index') continue;
      const title = p.title.replace(/^[-+\d.]+%\s*/, '').trim();
      if (target.name ? title === target.name : url.searchParams.get('backtestId') === target.id) matches.push(p);
    }
  }
  if (matches.length !== 1) throw Error(matches.length ? 'PAGE_IDENTITY_AMBIGUOUS' : 'PAGE_NOT_OPEN');
  const debuggerUrl = new URL(matches[0].webSocketDebuggerUrl);
  if (debuggerUrl.protocol !== 'ws:' || !['127.0.0.1', 'localhost', '[::1]'].includes(debuggerUrl.hostname)) {
    throw Error('PAGE_CDP_MUST_BE_LOCAL');
  }
  ws = new WebSocket(debuggerUrl);
  await new Promise((resolve, reject) => {ws.onopen = resolve; ws.onerror = () => reject(Error('PAGE_CDP_CONNECT_FAILED'));});
  let id = 0;
  const pending = new Map();
  ws.onmessage = e => {const d = JSON.parse(e.data); if (pending.has(d.id)) {pending.get(d.id)(d); pending.delete(d.id);}};
  function call(method, params = {}) {
    return new Promise((resolve, reject) => {
      const key = ++id;
      const timer = setTimeout(() => {pending.delete(key); reject(Error('PAGE_CDP_TIMEOUT'));}, 15000);
      pending.set(key, d => {clearTimeout(timer); d.error ? reject(Error('PAGE_CDP_ERROR')) : resolve(d.result);});
      ws.send(JSON.stringify({id:key, method, params}));
    });
  }
  const old = await call('Runtime.evaluate', {expression:'performance.timeOrigin',returnByValue:true});
  const timeOrigin = old?.result?.value;
  if (!Number.isFinite(timeOrigin)) throw Error('PAGE_CDP_ERROR');
  await call('Page.reload', {ignoreCache:true});
  const expression = `(() => {
    if (performance.timeOrigin === ${timeOrigin} || document.readyState !== 'complete' || !window.jQuery) return null;
    const read = id => {
      const el = document.getElementById(id);
      if (!el || !el.grid || el.grid.hDiv.loading) return null;
      const p = jQuery(el).jqGrid('getGridParam');
      if (p.datatype !== 'local' || !Array.isArray(p.data) || p.records !== p.data.length || p.reccount !== p.data.length || Number(p.lastpage) > 1) return null;
      return {rows:p.data, records:p.records};
    };
    const positions=read('positioninfo'), transactions=read('transactioninfo');
    if (!positions || !transactions) return null;
    const title=document.title.replace(/^[-+\\d.]+%\\s*/, '').trim();
    const dates=[...document.querySelectorAll('*')].filter(e=>e.children.length===0).map(e=>e.textContent.trim()).filter(t=>/^(持仓详情|下单详情)[(（]/.test(t));
    return {name:title,url:location.href,positions,transactions,dates,cash:document.getElementById('available_cash')?.textContent,read_at:new Date().toISOString()};
  })()`;
  let result;
  const end = Date.now() + 20000;
  while (Date.now() < end) {
    const r = await call('Runtime.evaluate', {expression,returnByValue:true});
    result = r.result?.value;
    if (result) break;
    await new Promise(r => setTimeout(r, 500));
  }
  if (!result) throw Error('PAGE_TABLES_NOT_READY_OR_INCOMPLETE');
  if (target.name && result.name !== target.name) throw Error('PAGE_IDENTITY_CHANGED');
  console.log(JSON.stringify(result));
} catch(e) { console.log(JSON.stringify({error:String(e.message)})); process.exitCode=2; }
finally {ws?.close();}
