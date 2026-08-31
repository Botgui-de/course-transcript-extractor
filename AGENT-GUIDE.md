# Agent Guide — the complete runbook

Written for a Claude (or any agent) driving Chrome via extension tools. Every payload below is battle-tested verbatim from the 2026-08-31 ZTM Claude Code Bootcamp run (77/77 videos captured). A human can run the same JS in DevTools.

## Phase 0 — Setup

1. Human signs into the course site in a Chrome profile with the Claude extension connected.
2. Start both services from the repo root (keep them running the whole session):
   ```bash
   python tools/transcript_receiver.py    # 127.0.0.1:8765 → ./queue and ./transcripts
   python tools/hotmart_captions.py       # watches ./queue, exits after 5 idle minutes — restart if it times out
   ```
3. Verify the receiver from the browser (run as JS in any course tab):
   ```js
   await fetch('http://127.0.0.1:8765/list', {signal: AbortSignal.timeout(8000)}).then(r=>r.text())
   ```
   If this times out: the receiver sends `Access-Control-Allow-Private-Network: true`, which Chrome requires for public-page→localhost fetches — make sure you're running THIS repo's receiver, and retry once (first PNA preflight can be slow).

## Phase 1 — Enumerate the curriculum (once)

Navigate to any lecture page, wait ~3s, then run — this both returns counts and saves the full map through the receiver:

```js
const items=[...document.querySelectorAll('.course-section')].map(sec=>({section:(sec.querySelector('.section-title')?.textContent||'').trim().replace(/\s+/g,' '), lectures:[...sec.querySelectorAll('a[href*="/lectures/"]')].map(a=>({id:(a.href.match(/lectures\/(\d+)/)||[])[1], title:(a.textContent||'').trim().replace(/\s+/g,' ')}))}));
const r = await fetch('http://127.0.0.1:8765/save',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name:'00-curriculum', text:JSON.stringify(items,null,2)})}); await r.text()
```

Read the saved `transcripts/00-curriculum.md`. Titles containing a `(mm:ss)` duration are **videos**; the rest are **text pages**. Build your worklist with names like `m<module>-<nn> <Title> (id <lectureId>)` — the receiver slugifies them into filenames.

## Phase 2 — Per-video harvest loop

Two lectures per browser batch is a good rhythm. Per lecture, five sequential actions:

1. `navigate` → `https://<academy-domain>/courses/<course>/lectures/<id>`
2. `wait 3`
3. **Hop into the player embed as a top-level page** (cross-origin iframe network is invisible otherwise):
   ```js
   const f=document.querySelector('iframe[src*="hotmart"]'); if(f){location.href=f.src;'hop'}else{'NOIFRAME'}
   ```
   `NOIFRAME` ⇒ it's a text page; handle in Phase 3 instead.
4. `wait 4`
5. **Collect and fire** (replace `<NAME>` with your worklist name; the POST is fire-and-forget with `keepalive` so navigation can't kill it):
   ```js
   const v=document.querySelector('video'); if(v) v.muted=true;
   let master=null, child=null;
   for(let t=0;t<16;t++){ const res=performance.getEntriesByType('resource').map(e=>e.name);
     master=res.find(u=>u.includes('master')&&u.includes('.m3u8'))||null;
     child=res.find(u=>u.includes('vod-akm')&&u.includes('.m3u8')&&!u.includes('master'))||null;
     if(master&&child) break; await new Promise(r=>setTimeout(r,500)); }
   if(master){ fetch('http://127.0.0.1:8765/urls',{method:'POST',headers:{'Content-Type':'application/json'},keepalive:true,body:JSON.stringify({name:'<NAME>', master, child})}).catch(()=>{}); await new Promise(r=>setTimeout(r,800)); 'FIRED' } else 'NOMASTER'
   ```

**Pacing matters:** the master URL's `hdnts` token expires ~8 minutes after page load. The worker processes jobs in ~5–15s each, so at 2-lectures-per-batch it keeps up. If you harvest much faster than the worker drains, late jobs expire (yt-dlp 403) and get shelved as `queue/*.failed` — that's recoverable, see Phase 4.

## Phase 3 — Text pages

```js
const el=document.querySelector('.lecture-attachment')||document.querySelector('[id*=lecture_content]')||document.querySelector('.course-mainbar')||document.body;
const links=[...el.querySelectorAll('a')].map(a=>'- ['+a.textContent.trim()+']('+a.href+')').join('\n');
const r=await fetch('http://127.0.0.1:8765/save',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name:'<NAME>', text: el.innerText.trim().slice(0,100000)+'\n\n## Links\n'+links})}); 'SAVED '+(await r.text())
```
Teachable text pages are often genuinely tiny (200–600 chars) — that's the page, not a bug. If the course has a Notion/external "resources" page, capture it too (note: Notion's CSP blocks fetches to localhost — extract the text via the extension's page-text tool and save the file directly instead).

## Phase 4 — Audit until zero missing

1. Build the expected-ID list from `00-curriculum.md` (videos only).
2. Check every ID appears in a `transcripts/*.md` filename (`id-<lectureId>`).
3. For each missing ID and each `queue/*.failed`: re-run Phase 2 for just that lecture (fresh page = fresh token) — the worker retries automatically when the new job lands.
4. Done = expected count matches, queue empty. Then generate an index (filename + word count table) and copy `QUALITY-NOTES-TEMPLATE.md` into the output folder.

## Troubleshooting (all encountered in the field)

| Symptom | Cause | Fix |
|---------|-------|-----|
| JS tool times out at 45s but page keeps working | Background-tab CDP throttling; the code usually DID run | Treat as cosmetic — verify via receiver/queue, don't re-run blindly |
| Fetch to 127.0.0.1 times out | Chrome Private Network Access | Receiver must send `Access-Control-Allow-Private-Network: true` (this repo's does) |
| `NOMASTER` | Player not initialized yet | Increase step-4 wait; reload the lecture page once |
| yt-dlp `403 Forbidden` on master | `hdnts` token expired (>~8 min old) | Re-harvest that lecture fresh; keep worker running DURING harvest |
| In-page fetches of caption segments 403 intermittently | Akamai burst protection | Don't fetch segments in-browser at all — that's why yt-dlp owns this step |
| Agent tool result shows `[BLOCKED: Cookie/query string data]` | Extension redacts signed URLs from model output | Never try to print/return URLs containing `signature=`, `hdnts`, `hdntl`, `token=`; let page JS handle them and return only statuses/counts |
| "You are NOT signed in as a student" banner | Session quirk on Teachable SSO | Content usually still loads; only re-login if lectures show a paywall |
| Worker exited | 5-minute idle timeout | Just restart it; it skips anything already saved |

## Ground rules for the agent

- Use ONE tab of your own; never touch the user's other tabs.
- Mute every video immediately (`v.muted=true`) — the payload does this.
- Never attempt sign-in, purchases, or account changes; if a paywall appears, stop and tell the human.
- Transcripts are the user's personal study aid — no republishing, and derivative docs must be original writing.
