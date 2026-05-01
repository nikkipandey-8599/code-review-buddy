import hmac
import hashlib
import os
import json
from datetime import datetime
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse
from dotenv import load_dotenv
from github_client import fetch_pr_diff, post_review_comment
from llm_client import get_code_review

load_dotenv()

app = FastAPI()

WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "")

# In-memory store for reviews (resets on restart — fine for now)
reviews_log = []


def verify_signature(payload_bytes: bytes, signature_header: str) -> bool:
    if not signature_header:
        return False
    mac = hmac.new(
        WEBHOOK_SECRET.encode("utf-8"),
        msg=payload_bytes,
        digestmod=hashlib.sha256
    )
    expected = "sha256=" + mac.hexdigest()
    return hmac.compare_digest(expected, signature_header)


@app.get("/", response_class=HTMLResponse)
def dashboard():
    total = len(reviews_log)
    repos = len(set(r['repo'] for r in reviews_log)) if reviews_log else 0
    prs = len(set(r['pr_number'] for r in reviews_log)) if reviews_log else 0

    cards = ""
    if not reviews_log:
        cards = '<div class="empty-state"><div class="empty-icon">⏳</div><h3>Waiting for first review</h3><p>Install the bot on a repo and open a Pull Request to get started.</p></div>'
    else:
        for r in reversed(reviews_log):
            review_escaped = r['review'].replace('<','&lt;').replace('>','&gt;').replace('\n','<br>')
            cards += f"""
            <div class="review-card">
                <div class="review-header">
                    <div class="review-meta">
                        <span class="repo-icon">📁</span>
                        <a class="repo-name" href="https://github.com/{r['repo']}" target="_blank">{r['repo']}</a>
                        <span class="divider">·</span>
                        <a class="pr-link" href="{r['pr_url']}" target="_blank">PR #{r['pr_number']}</a>
                    </div>
                    <span class="review-time">{r['time']}</span>
                </div>
                <div class="review-body">{review_escaped}</div>
                <div class="review-footer">
                    <span class="ai-badge">✨ Gemini AI</span>
                    <a href="{r['pr_url']}" target="_blank" class="view-pr">View PR on GitHub →</a>
                </div>
            </div>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Code Review Buddy</title>
<meta http-equiv="refresh" content="30">
<style>
  :root {{
    --bg: #0a0a0f;
    --surface: #111118;
    --surface2: #1a1a24;
    --border: #2a2a3a;
    --border2: #353548;
    --text: #e8e8f0;
    --text2: #9090a8;
    --text3: #606078;
    --blue: #6366f1;
    --blue-light: #818cf8;
    --green: #22c55e;
    --green-dim: #166534;
  }}
  * {{ margin:0; padding:0; box-sizing:border-box; }}
  body {{ font-family: 'Segoe UI', system-ui, sans-serif; background:var(--bg); color:var(--text); min-height:100vh; }}

  /* NAV */
  nav {{ background:var(--surface); border-bottom:1px solid var(--border); padding:0 2rem; height:56px; display:flex; align-items:center; gap:12px; position:sticky; top:0; z-index:10; }}
  .nav-logo {{ font-size:1.3rem; }}
  .nav-title {{ font-weight:700; font-size:1rem; color:var(--text); letter-spacing:-0.3px; }}
  .nav-version {{ font-size:11px; color:var(--text3); background:var(--surface2); border:1px solid var(--border); padding:2px 8px; border-radius:20px; }}
  .nav-status {{ margin-left:auto; display:flex; align-items:center; gap:6px; font-size:12px; color:var(--green); }}
  .pulse {{ width:7px; height:7px; border-radius:50%; background:var(--green); animation:pulse 2s infinite; }}
  @keyframes pulse {{ 0%,100%{{opacity:1;box-shadow:0 0 0 0 rgba(34,197,94,0.4);}} 50%{{opacity:0.8;box-shadow:0 0 0 4px rgba(34,197,94,0);}} }}

  /* LAYOUT */
  .page {{ max-width:1000px; margin:0 auto; padding:2rem 1.5rem; }}

  /* HERO */
  .hero {{ margin-bottom:2rem; }}
  .hero h2 {{ font-size:1.5rem; font-weight:700; color:var(--text); letter-spacing:-0.5px; margin-bottom:6px; }}
  .hero p {{ font-size:14px; color:var(--text2); }}

  /* STATS */
  .stats {{ display:grid; grid-template-columns:repeat(3,1fr); gap:12px; margin-bottom:2rem; }}
  .stat-card {{ background:var(--surface); border:1px solid var(--border); border-radius:12px; padding:1.2rem 1.4rem; position:relative; overflow:hidden; }}
  .stat-card::before {{ content:''; position:absolute; top:0; left:0; right:0; height:2px; background:linear-gradient(90deg, var(--blue), var(--blue-light)); }}
  .stat-num {{ font-size:2.2rem; font-weight:800; color:var(--blue-light); letter-spacing:-1px; }}
  .stat-label {{ font-size:12px; color:var(--text2); margin-top:4px; font-weight:500; text-transform:uppercase; letter-spacing:0.5px; }}
  .stat-icon {{ position:absolute; right:1rem; top:50%; transform:translateY(-50%); font-size:1.8rem; opacity:0.15; }}

  /* ACTIVITY BAR */
  .activity-bar {{ background:var(--surface); border:1px solid var(--border); border-radius:10px; padding:0.9rem 1.2rem; margin-bottom:2rem; display:flex; align-items:center; gap:10px; font-size:13px; }}
  .activity-bar .label {{ color:var(--text2); }}
  .activity-bar .url {{ color:var(--blue-light); font-family:monospace; font-size:12px; }}
  .activity-bar .refresh {{ margin-left:auto; color:var(--text3); font-size:12px; }}

  /* SECTION */
  .section-header {{ display:flex; align-items:center; justify-content:space-between; margin-bottom:1rem; }}
  .section-title {{ font-size:13px; font-weight:600; color:var(--text2); text-transform:uppercase; letter-spacing:0.8px; }}
  .section-count {{ font-size:12px; color:var(--text3); background:var(--surface2); border:1px solid var(--border); padding:2px 10px; border-radius:20px; }}

  /* REVIEW CARDS */
  .review-card {{ background:var(--surface); border:1px solid var(--border); border-radius:12px; margin-bottom:14px; overflow:hidden; transition:border-color 0.2s; }}
  .review-card:hover {{ border-color:var(--border2); }}
  .review-header {{ padding:0.9rem 1.2rem; background:var(--surface2); border-bottom:1px solid var(--border); display:flex; align-items:center; justify-content:space-between; flex-wrap:wrap; gap:8px; }}
  .review-meta {{ display:flex; align-items:center; gap:8px; font-size:13px; }}
  .repo-icon {{ font-size:14px; }}
  .repo-name {{ color:var(--blue-light); text-decoration:none; font-weight:600; }}
  .repo-name:hover {{ text-decoration:underline; }}
  .divider {{ color:var(--text3); }}
  .pr-link {{ color:var(--text2); text-decoration:none; background:var(--border); padding:2px 8px; border-radius:20px; font-size:12px; font-weight:500; }}
  .pr-link:hover {{ color:var(--text); }}
  .review-time {{ font-size:12px; color:var(--text3); }}
  .review-body {{ padding:1.2rem; font-size:13px; line-height:1.8; color:#c8c8e0; max-height:280px; overflow-y:auto; border-bottom:1px solid var(--border); }}
  .review-body::-webkit-scrollbar {{ width:4px; }}
  .review-body::-webkit-scrollbar-track {{ background:transparent; }}
  .review-body::-webkit-scrollbar-thumb {{ background:var(--border2); border-radius:2px; }}
  .review-footer {{ padding:0.7rem 1.2rem; display:flex; align-items:center; justify-content:space-between; }}
  .ai-badge {{ font-size:11px; color:var(--text3); }}
  .view-pr {{ font-size:12px; color:var(--blue-light); text-decoration:none; font-weight:500; }}
  .view-pr:hover {{ text-decoration:underline; }}

  /* EMPTY */
  .empty-state {{ text-align:center; padding:4rem 2rem; background:var(--surface); border:1px dashed var(--border2); border-radius:12px; }}
  .empty-icon {{ font-size:2.5rem; margin-bottom:1rem; }}
  .empty-state h3 {{ font-size:1rem; color:var(--text2); margin-bottom:8px; font-weight:600; }}
  .empty-state p {{ font-size:13px; color:var(--text3); }}

  /* FOOTER */
  footer {{ text-align:center; padding:2.5rem 1rem 1.5rem; font-size:12px; color:var(--text3); border-top:1px solid var(--border); margin-top:3rem; }}
  footer a {{ color:var(--text2); text-decoration:none; }}
  footer a:hover {{ color:var(--text); }}

  @media(max-width:600px) {{
    .stats {{ grid-template-columns:1fr; }}
    nav {{ padding:0 1rem; }}
    .page {{ padding:1rem; }}
  }}
</style>
</head>
<body>

<nav>
  <span class="nav-logo">🤖</span>
  <span class="nav-title">Code Review Buddy</span>
  <span class="nav-version">v1.0</span>
  <div class="nav-status">
    <div class="pulse"></div>
    Online
  </div>
</nav>

<div class="page">
  <div class="hero">
    <h2>AI-Powered Code Reviews</h2>
    <p>Automatically reviews every Pull Request and posts structured feedback directly on GitHub.</p>
  </div>

  <div class="stats">
    <div class="stat-card">
      <div class="stat-num">{total}</div>
      <div class="stat-label">Reviews Posted</div>
      <div class="stat-icon">📝</div>
    </div>
    <div class="stat-card">
      <div class="stat-num">{repos}</div>
      <div class="stat-label">Repos Active</div>
      <div class="stat-icon">📁</div>
    </div>
    <div class="stat-card">
      <div class="stat-num">{prs}</div>
      <div class="stat-label">PRs Reviewed</div>
      <div class="stat-icon">🔀</div>
    </div>
  </div>

  <div class="activity-bar">
    <div class="pulse" style="background:#6366f1;animation:none;opacity:0.7;"></div>
    <span class="label">Webhook endpoint:</span>
    <span class="url">/webhook</span>
    <span class="refresh">↻ Auto-refreshes every 30s</span>
  </div>

  <div class="section-header">
    <span class="section-title">Recent Reviews</span>
    <span class="section-count">{total} total</span>
  </div>

  {cards}
</div>

<footer>
  Built with FastAPI + Gemini AI ·
  <a href="https://github.com/nikkipandey-8599/code-review-buddy" target="_blank">View Source</a> ·
  <a href="https://github.com/apps/code-review-buddy-nikki" target="_blank">Install Bot</a>
</footer>

</body>
</html>""" 

    return html


@app.post("/webhook")
async def webhook(request: Request):
    payload_bytes = await request.body()
    signature = request.headers.get("X-Hub-Signature-256", "")

    if not verify_signature(payload_bytes, signature):
        raise HTTPException(status_code=401, detail="Invalid signature")

    body = await request.json()
    action = body.get("action")
    print(f"📌 Event action: {action}")

    if action not in ["opened", "synchronize"]:
        return {"status": f"ignored action: {action}"}

    pr = body.get("pull_request", {})
    pr_number = pr.get("number")
    diff_url = pr.get("diff_url")
    pr_url = pr.get("html_url")
    repo_full_name = body.get("repository", {}).get("full_name")
    installation_id = body.get("installation", {}).get("id")

    print(f"📥 PR #{pr_number} received from {repo_full_name}")

    if not all([pr_number, diff_url, repo_full_name, installation_id]):
        return {"status": "missing required fields"}

    diff = await fetch_pr_diff(diff_url, installation_id)
    print(f"📄 Diff length: {len(diff)} characters")

    if not diff.strip():
        return {"status": "empty diff, skipping"}

    print("🤖 Sending diff to Gemini...")
    review = get_code_review(diff)
    print(f"✅ Got review")

    post_review_comment(installation_id, repo_full_name, pr_number, review)

    # Save to dashboard log
    reviews_log.append({
        "repo": repo_full_name,
        "pr_number": pr_number,
        "pr_url": pr_url,
        "review": review,
        "time": datetime.now().strftime("%d %b %Y, %I:%M %p")
    })

    return {"status": "review posted"}