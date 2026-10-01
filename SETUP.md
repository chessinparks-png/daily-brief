# Set up The Black Brief on your computer

A one-time setup of about 30–45 minutes. You type the commands in the **Terminal**
(Mac: press Cmd+Space, type "Terminal") or **PowerShell** (Windows: Start menu, type
"PowerShell"). Paste one command at a time and press Enter.

## 1. Make the GitHub repo private
On github.com, open `chessinparks-png/daily-brief` → **Settings** → scroll to
**Danger Zone** → **Change visibility** → **Make private**.

## 2. Install the tools

**Mac**
```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```
When that finishes, it prints a "Next steps" section with 2 commands. Run them, then:
```bash
brew install git python@3.12 gh ffmpeg
curl -fsSL https://claude.ai/install.sh | bash
```

**Windows**
```powershell
winget install Git.Git Python.Python.3.12 GitHub.cli Gyan.FFmpeg
irm https://claude.ai/install.ps1 | iex
```
Then **close PowerShell and open a new one** so it picks up the new tools.

Check that the tools installed. Each command should print a version number:
```bash
git --version
python3 --version     # Windows: py --version
gh --version
claude --version
```

## 3. Sign in to GitHub
```bash
gh auth login
```
Choose: **GitHub.com** → **HTTPS** → **Yes** (authenticate Git) → **Login with a web
browser**. Copy the code it shows and paste it into the browser page that opens.

## 4. Download the project
```bash
cd ~
gh repo clone chessinparks-png/daily-brief
cd daily-brief
git checkout claude/daily-brief-app-xjojem
```

## 5. Install the Python libraries
**Mac**
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```
**Windows**
```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```
If Windows says "running scripts is disabled", run
`Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`, answer **Y**, and try again.

You'll see `(.venv)` at the start of the line. That means it worked.

## 6. Test the fetcher from your home internet
```bash
python fetcher/fetch.py --limit 2
```
At the bottom you should see `SUMMARY: 9/9 sources OK`. Also check:
- YouTube items say `captions: ok`
- Letters from an American does **not** say "using fallback feed"

## 7. Start Claude Code in the project
```bash
claude
```
Sign in with your Claude account the first time. Then paste the test output from step 6
and type: **"Setup done. Here's the fetcher output. Start Stage 2."**

Claude Code reads `CLAUDE.md` and `PLAN.md` automatically, so it knows the project.

## Every day after that (once Stage 3 is built)
```bash
cd ~/daily-brief
source .venv/bin/activate     # Windows: .venv\Scripts\Activate.ps1
claude
```
then type `/black-brief`.
