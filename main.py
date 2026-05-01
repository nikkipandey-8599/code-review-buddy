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
    cards = ""
    if not reviews_log:
        cards = """
        <div class="empty">
            <p>No reviews yet.</p>
            <p>Open a Pull Request on a repo where your bot is installed.</p>
        </div>
        """
    else:
        for r in reversed(reviews_log):
            review_html = r['review'].replace('\n', '<br>')
            cards += f"""
            <div class="card">
                <div class="card-header">
                    <span class="repo">{r['repo']}</span>
                    <span class="pr">PR #{r['pr_number']}</span>
                    <span class="time">{r['time']}</span>
                </div>
                <div class="card-body">{review_html}</div>
                <a href="{r['pr_url']}" target="_blank" class="view-btn">View on GitHub →</a>
            </div>
            """

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Code Review Buddy</title>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            * {{ margin: 0; padding: 0; box-sizing: border-box; }}
            body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #0d1117; color: #c9d1d9; min-height: 100vh; }}
            
            header {{ background: #161b22; border-bottom: 1px solid #30363d; padding: 1rem 2rem; display: flex; align-items: center; gap: 12px; }}
            header h1 {{ font-size: 1.2rem; font-weight: 600; color: #f0f6fc; }}
            .badge {{ background: #238636; color: white; font-size: 11px; padding: 2px 8px; border-radius: 12px; font-weight: 500; }}
            .count {{ margin-left: auto; font-size: 13px; color: #8b949e; }}
            
            .container {{ max-width: 900px; margin: 2rem auto; padding: 0 1.5rem; }}
            
            .stats {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 1rem; margin-bottom: 2rem; }}
            .stat {{ background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 1.2rem; text-align: center; }}
            .stat-number {{ font-size: 2rem; font-weight: 700; color: #58a6ff; }}
            .stat-label {{ font-size: 12px; color: #8b949e; margin-top: 4px; }}
            
            .section-title {{ font-size: 14px; font-weight: 600; color: #8b949e; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 1rem; }}
            
            .card {{ background: #161b22; border: 1px solid #30363d; border-radius: 10px; margin-bottom: 1rem; overflow: hidden; }}
            .card-header {{ padding: 0.9rem 1.2rem; background: #1c2128; border-bottom: 1px solid #30363d; display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }}
            .repo {{ font-weight: 600; color: #58a6ff; font-size: 14px; }}
            .pr {{ background: #1f4b8e; color: #79c0ff; font-size: 12px; padding: 2px 8px; border-radius: 12px; }}
            .time {{ margin-left: auto; font-size: 12px; color: #8b949e; }}
            .card-body {{ padding: 1.2rem; font-size: 13px; line-height: 1.7; color: #c9d1d9; max-height: 300px; overflow-y: auto; }}
            .view-btn {{ display: block; padding: 0.7rem 1.2rem; background: #21262d; color: #58a6ff; text-decoration: none; font-size: 13px; border-top: 1px solid #30363d; transition: background 0.15s; }}
            .view-btn:hover {{ background: #30363d; }}
            
            .empty {{ text-align: center; padding: 4rem 2rem; color: #8b949e; background: #161b22; border: 1px dashed #30363d; border-radius: 10px; }}
            .empty p {{ margin-bottom: 8px; }}
            
            .status-bar {{ background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 0.8rem 1.2rem; margin-bottom: 2rem; display: flex; align-items: center; gap: 8px; font-size: 13px; }}
            .dot {{ width: 8px; height: 8px; border-radius: 50%; background: #3fb950; animation: pulse 2s infinite; }}
            @keyframes pulse {{ 0%, 100% {{ opacity: 1; }} 50% {{ opacity: 0.4; }} }}
            
            footer {{ text-align: center; padding: 2rem; font-size: 12px; color: #484f58; }}
        </style>
        <meta http-equiv="refresh" content="30">
    </head>
    <body>
        <header>
            <span style="font-size:1.4rem">🤖</span>
            <h1>Code Review Buddy</h1>
            <span class="badge">Live</span>
            <span class="count">{len(reviews_log)} reviews posted</span>
        </header>
        
        <div class="container">
            <div class="status-bar">
                <div class="dot"></div>
                <span>Bot is online and listening for Pull Requests</span>
                <span style="margin-left:auto;color:#8b949e">Auto-refreshes every 30s</span>
            </div>
            
            <div class="stats">
                <div class="stat">
                    <div class="stat-number">{len(reviews_log)}</div>
                    <div class="stat-label">Total Reviews</div>
                </div>
                <div class="stat">
                    <div class="stat-number">{len(set(r['repo'] for r in reviews_log)) if reviews_log else 0}</div>
                    <div class="stat-label">Repos Reviewed</div>
                </div>
                <div class="stat">
                    <div class="stat-number">{len(set(r['pr_number'] for r in reviews_log)) if reviews_log else 0}</div>
                    <div class="stat-label">PRs Reviewed</div>
                </div>
            </div>
            
            <p class="section-title">Recent Reviews</p>
            {cards}
        </div>
        
        <footer>Code Review Buddy — Built with FastAPI + Gemini AI</footer>
    </body>
    </html>
    """
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