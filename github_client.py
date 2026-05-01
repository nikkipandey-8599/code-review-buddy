import os
from github import GithubIntegration, Github
import httpx


def get_github_client_for_installation(installation_id: int):
    app_id = os.getenv("GITHUB_APP_ID")
    
    # This works both locally (reads from file) and on Render (reads from env variable)
    private_key = os.getenv("GITHUB_PRIVATE_KEY")
    if not private_key:
        private_key_path = os.getenv("GITHUB_PRIVATE_KEY_PATH", "private-key.pem")
        with open(private_key_path, "r") as f:
            private_key = f.read()

    integration = GithubIntegration(app_id, private_key)
    token = integration.get_access_token(installation_id).token
    return Github(token), token


def post_review_comment(installation_id: int, repo_full_name: str, pr_number: int, review: str):
    try:
        gh, _ = get_github_client_for_installation(installation_id)
        repo = gh.get_repo(repo_full_name)
        pr = repo.get_pull(pr_number)

        comment_body = f"""### 🤖 Code Review Buddy

{review}

---
*Powered by Gemini AI*"""
        pr.create_issue_comment(comment_body)
        print(f"✅ Posted review on PR #{pr_number} in {repo_full_name}")

    except Exception as e:
        print(f"❌ GitHub error: {e}")


async def fetch_pr_diff(diff_url: str, installation_id: int) -> str:
    try:
        _, token = get_github_client_for_installation(installation_id)

        async with httpx.AsyncClient() as client:
            response = await client.get(
                diff_url,
                headers={
                    "Authorization": f"token {token}",
                    "Accept": "application/vnd.github.v3.diff"
                },
                follow_redirects=True
            )
            print(f"📡 Diff response status: {response.status_code}")
            return response.text
    except Exception as e:
        print(f"❌ Diff fetch error: {e}")
        return ""