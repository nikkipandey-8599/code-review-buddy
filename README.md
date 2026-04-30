# 🤖 Code Review Buddy

A GitHub App that automatically reviews Pull Requests using AI. When a PR is opened or updated, the bot reads the code diff and posts a structured review comment with a summary, potential risks, and one improvement suggestion.

## Demo

![Bot commenting on a PR](demo.png)

## Features

- Auto-triggered on every PR open or update
- AI-powered code analysis using Gemini
- Structured review format (Summary / Risks / Suggestion)
- Lightweight — no database, fully stateless

## Tech Stack

- **Python** + **FastAPI** — webhook server
- **Google Gemini API** — AI code review
- **PyGithub** — GitHub API integration
- **ngrok** — local tunnel for development

## Setup

### 1. Clone the repo
```bash
git clone https://github.com/YOUR_USERNAME/code-review-buddy.git
cd code-review-buddy
```

### 2. Create virtual environment
```bash
python -m venv venv
venv\Scripts\activate  # Windows
source venv/bin/activate  # Mac/Linux
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure environment variables
Create a `.env` file:
```
GITHUB_APP_ID=your_app_id
GITHUB_PRIVATE_KEY_PATH=private-key.pem
GEMINI_API_KEY=your_gemini_key
WEBHOOK_SECRET=your_webhook_secret
```

### 5. Run the server
```bash
uvicorn main:app --reload --port 8000
```

### 6. Expose with ngrok
```bash
ngrok http 8000
```

Update your GitHub App webhook URL with the ngrok URL + `/webhook`.

## How It Works

1. Developer opens a Pull Request
2. GitHub sends a webhook to this server
3. Server fetches the PR diff from GitHub API
4. Diff is sent to Gemini AI for analysis
5. AI review is posted as a comment on the PR

## Project Structure

```
code-review-buddy/
├── main.py           # FastAPI webhook server
├── github_client.py  # GitHub API interactions
├── llm_client.py     # Gemini AI integration
├── prompt.py         # AI system prompt
├── requirements.txt  # Dependencies
└── .env              # Secrets (never commit)
```

## Author

Made by [@nikkipandey-8599](https://github.com/nikkipandey-8599)