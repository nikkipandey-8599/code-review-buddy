import hmac
import hashlib
import os
from fastapi import FastAPI, Request, HTTPException
from dotenv import load_dotenv
from github_client import fetch_pr_diff, post_review_comment
from llm_client import get_code_review

load_dotenv()

app = FastAPI()

WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "")


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


@app.get("/")
def health_check():
    return {"status": "Code Review Buddy is running"}


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
        print(f"⏭️ Skipping action: {action}")
        return {"status": f"ignored action: {action}"}

    pr = body.get("pull_request", {})
    pr_number = pr.get("number")
    diff_url = pr.get("diff_url")
    repo_full_name = body.get("repository", {}).get("full_name")
    installation_id = body.get("installation", {}).get("id")

    print(f"📥 PR #{pr_number} received from {repo_full_name}")
    print(f"🔗 Diff URL: {diff_url}")
    print(f"🔧 Installation ID: {installation_id}")

    if not all([pr_number, diff_url, repo_full_name, installation_id]):
        print("❌ Missing required fields!")
        return {"status": "missing required fields"}

    print("📄 Fetching diff...")
    diff = await fetch_pr_diff(diff_url, installation_id)
    print(f"📄 Diff length: {len(diff)} characters")

    if not diff.strip():
        print("❌ Empty diff!")
        return {"status": "empty diff, skipping"}

    print("🤖 Sending diff to Gemini...")
    review = get_code_review(diff)
    print(f"✅ Got review: {review[:100]}...")

    print("💬 Posting comment to GitHub...")
    post_review_comment(installation_id, repo_full_name, pr_number, review)

    return {"status": "review posted"}