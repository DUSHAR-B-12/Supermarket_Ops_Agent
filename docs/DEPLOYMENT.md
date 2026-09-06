# Production Deployment Guide

This guide explains how to properly deploy the Supermarket Ops Agent to a production environment. 

Because this application relies on SQLite for persistent storage of inventory, active draft bills, khata balances, and user preferences, **stateless environments (like Heroku Free tier or AWS Lambda) without volume mounts will result in data loss upon restart.**

You MUST use a deployment platform that supports persistent volumes or persistent disk attachments (e.g., AWS EC2, DigitalOcean Droplet, Railway with Volumes, or a local server).

## 1. Required Environment Variables

Before starting the bot, ensure the following environment variables are securely injected into the environment. 
**DO NOT commit these to source control.**

- `TELEGRAM_BOT_TOKEN`: The API key from BotFather.
- `GEMINI_API_KEY`: Primary Google Gemini API key.
- `GEMINI_MODEL`: (Optional) Defaults to `gemini-3.1-flash-lite`.
- `GROQ_API_KEY`: Fallback Groq API key for high-availability.
- `DATABASE_URL`: Set to `sqlite:///./data/supermarket.db` (Default).
- `SHOP_NAME`: (Optional) e.g. "GreenBasket Supermart".

## 2. Persistent SQLite Storage Requirements

The default database location is `./data/supermarket.db`. 
When deploying using Docker, you **must** mount a volume to the `/app/data` directory to ensure data survives container restarts.

## 3. Deployment using Railway.app (Easiest Cloud Option)

Railway is an excellent platform for this bot because it supports persistent volumes out-of-the-box.

### Option A: Manual UI Deployment (via GitHub)
1. Push your latest code to your GitHub repository.
2. Go to [Railway.app](https://railway.app) and click **New Project** -> **Deploy from GitHub repo**.
3. Select your `Supermarket_Ops_Agent` repository. Railway will detect the `Dockerfile` automatically.
4. **Important**: Before the first deployment finishes, go to the **Settings** of your service.
5. Go to the **Volumes** section and click **Add Volume**.
6. Set the Mount Path to `/app/data`. (This is where SQLite will save `supermarket.db`).
7. Go to the **Variables** tab and add your required secrets:
   - `TELEGRAM_BOT_TOKEN`
   - `GEMINI_API_KEY`
   - `GROQ_API_KEY`
8. Restart/Deploy the service. The bot will now run continuously in the background using long-polling. Railway won't terminate it for not having a web port, because it detects it as a background worker.

### Option B: Deployment via Railway CLI
If you prefer deploying directly from your terminal:
1. Ensure the Railway CLI is installed (I've installed it for you, or run `npm i -g @railway/cli`).
2. Run `railway login` in your terminal to authenticate.
3. Run `railway link` and select your project.
4. Run `railway volume add` and map it to `/app/data`.
5. Run `railway up` to push your code and deploy.

## 4. Deployment using Docker (Local/VPS)

1. **Build the image**:
   ```bash
   docker build -t supermarket-ops-agent .
   ```

2. **Run the container with a persistent volume**:
   ```bash
   docker run -d \
     --name supermarket-bot \
     --restart unless-stopped \
     -v $(pwd)/data:/app/data \
     -e TELEGRAM_BOT_TOKEN="your_token_here" \
     -e GEMINI_API_KEY="your_gemini_key_here" \
     -e GROQ_API_KEY="your_groq_key_here" \
     supermarket-ops-agent
   ```

## 5. Deployment using Bare-Metal / VPS (Ubuntu/Debian)

If you prefer to run it directly on a Linux server without Docker:

1. Clone the repository and navigate to it.
2. Set up a virtual environment:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```
3. Create a `.env` file containing your keys.
4. Use `tmux` or `systemd` to keep the bot running continuously:

**Using Systemd (Preferred for Production)**
Create `/etc/systemd/system/supermarketbot.service`:
```ini
[Unit]
Description=Supermarket Ops Agent Telegram Bot
After=network.target

[Service]
User=ubuntu
WorkingDirectory=/home/ubuntu/Supermarket_Ops_Agent
EnvironmentFile=/home/ubuntu/Supermarket_Ops_Agent/.env
ExecStart=/home/ubuntu/Supermarket_Ops_Agent/venv/bin/python run.py
Restart=always

[Install]
WantedBy=multi-user.target
```
Enable and start the service:
```bash
sudo systemctl enable supermarketbot
sudo systemctl start supermarketbot
```

## 6. Verification & Checking Logs

- **Verify Telegram Connectivity**: Open Telegram and send `/start` or `hello` to your bot. If it replies, the webhook/polling loop is active.
- **Check Railway Logs**: Click the "View Logs" button on your Railway dashboard.
- **Check Docker Logs**: `docker logs -f supermarket-bot`
- **Check Systemd Logs**: `journalctl -u supermarketbot -f`

## 7. Graceful Shutdown & Restarts

The bot's underlying `python-telegram-bot` application is configured to handle SIGINT and SIGTERM gracefully. 
- To restart on Railway: Click "Restart" in the UI.
- To restart via Docker: `docker restart supermarket-bot`
- To restart via systemd: `sudo systemctl restart supermarketbot`
The bot will finish processing current updates before shutting down.
