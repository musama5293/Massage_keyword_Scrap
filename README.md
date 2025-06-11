# Telegram Group Keyword Scraper

A Streamlit web application that scrapes Telegram groups for specific keywords and exports results to Excel.

## Features
- 🔐 Frontend Telegram authentication (no terminal required)
- 📱 Phone verification & 2FA support
- 🔍 Keyword-based message scraping
- 📊 Excel export with download functionality
- 🌐 Cloud deployment ready

## Setup for Development

1. **Clone the repository**
2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Create `.env` file with your Telegram credentials:**
   ```
   TELEGRAM_API_ID=your_api_id_here
   TELEGRAM_API_HASH=your_api_hash_here
   ```

4. **Run locally:**
   ```bash
   streamlit run app.py
   ```

## Deployment Options

### Option 1: Streamlit Cloud (Recommended - FREE)
1. Push code to GitHub
2. Go to [share.streamlit.io](https://share.streamlit.io)
3. Connect your GitHub repo
4. Add environment variables in Streamlit Cloud settings
5. Deploy!

### Option 2: Heroku (FREE tier available)
1. Install Heroku CLI
2. Login: `heroku login`
3. Create app: `heroku create your-app-name`
4. Set environment variables:
   ```bash
   heroku config:set TELEGRAM_API_ID=your_api_id
   heroku config:set TELEGRAM_API_HASH=your_api_hash
   ```
5. Deploy: `git push heroku main`

### Option 3: Railway (FREE tier)
1. Connect GitHub to Railway
2. Import your repository
3. Add environment variables in Railway dashboard
4. Deploy automatically

## Client Usage Guide

### For Your Clients:
1. **Get Telegram API Credentials:**
   - Go to [my.telegram.org](https://my.telegram.org)
   - Login with phone number
   - Create new application
   - Copy `api_id` and `api_hash`

2. **Update Environment Variables:**
   - Replace values in `.env` file (for local)
   - Update environment variables in cloud platform

3. **First-time Authentication:**
   - Open the web app
   - Enter phone number (with country code)
   - Enter verification code from SMS/Telegram
   - Enter 2FA password if enabled
   - ✅ Session saved for future use

4. **Usage:**
   - Enter Telegram group link
   - Enter keywords (comma-separated)
   - Click "Start Scraping"
   - Download Excel file with results

## Session Management

- **Persistent Sessions:** Once authenticated, sessions are saved
- **Multiple Clients:** Each deployment can have different API credentials
- **Logout Option:** Available in sidebar to reset authentication

## Security Notes

- Never share your API credentials
- Use environment variables for sensitive data
- Each client should have their own API credentials
- Session files are stored locally/temporarily 