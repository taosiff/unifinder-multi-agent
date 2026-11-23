# 🚀 Render Deployment & Cloud Database Guide for UniFinder AI

This guide shows you how to deploy **UniFinder AI** to **Render** (`render.com`) with a **100% Free Persistent PostgreSQL Database** so your chat threads, conversation memory, and student profiles persist permanently across restarts!

---

## 🎯 Why Do We Need a Cloud Database on Render?

On Render's Free Web Service tier:
- The server container is ephemeral (local files like `.db` or `.sqlite` are reset when the container spins down after inactivity or redeploys).
- **The Solution**: We built **dual-mode database support** ([database.py](file:///g:/GITHUB%20AND%20PROJECTS/University%20Finder/database.py) & [backend.py](file:///g:/GITHUB%20AND%20PROJECTS/University%20Finder/backend.py)). If `DATABASE_URL` is set, it automatically uses **PostgreSQL** (`PostgresSaver`) for cloud persistence! If not set, it runs on local SQLite.

---

## 🗄️ Step 1: Get a 100% Free PostgreSQL Database (2 Options)

You have two great free options:

### Option A: Render Free PostgreSQL (Easiest — All in One Place)
1. Log in to [Render Dashboard](https://dashboard.render.com).
2. Click **"New +"** (top right) ➔ Select **"PostgreSQL"**.
3. Fill in:
   - **Name**: `unifinder-db`
   - **Database**: `unifinder`
   - **User**: `unifinder_user`
   - **Region**: Select the region closest to you (e.g., `Oregon (US West)` or `Frankfurt (EU)`).
   - **Plan**: Select **Free**.
4. Click **"Create Database"**.
5. Once created, scroll down to **"Connections"**:
   - Copy the **"Internal Database URL"** (if your web service is in the same Render region) OR **"External Database URL"** (starts with `postgresql://...`).

---

### Option B: Neon Serverless PostgreSQL (Recommended — Forever Free)
1. Go to [Neon.tech](https://neon.tech) and sign up with GitHub/Google.
2. Click **"Create Project"** ➔ Name it `unifinder-ai`.
3. In your dashboard, copy the **Connection String** (e.g. `postgresql://alex:password@ep-xyz.us-east-2.aws.neon.tech/neondb?sslmode=require`).
4. That's it! Neon gives 0.5 GB forever free with zero maintenance.

---

## 🚢 Step 2: Push Your Project to GitHub

1. In your local project directory `University Finder`:
   ```bash
   git add .
   git commit -m "feat: complete UniFinder AI multi-agent platform with Render support"
   ```
2. Create a new repository on your GitHub (e.g. `UniFinder-AI`).
3. Push your code:
   ```bash
   git remote add origin https://github.com/YOUR_USERNAME/UniFinder-AI.git
   git branch -M main
   git push -u origin main
   ```

---

## 🌐 Step 3: Deploy Web Service on Render

### Method 1: Using the Render Blueprint (1-Click Automated)
Because we included [render.yaml](file:///g:/GITHUB%20AND%20PROJECTS/University%20Finder/render.yaml), Render can automatically create both the database and web service:
1. In Render Dashboard, click **"New +"** ➔ Select **"Blueprint"**.
2. Connect your `UniFinder-AI` GitHub repository.
3. Render will read `render.yaml` and configure everything automatically!
4. Add your `GOOGLE_API_KEY` or `GROQ_API_KEY` in the prompt, then click **"Apply"**.

---

### Method 2: Manual Setup on Render (Takes 2 Minutes)
1. In Render Dashboard, click **"New +"** ➔ Select **"Web Service"**.
2. Connect your GitHub repository.
3. Configure the settings:
   - **Name**: `unifinder-ai`
   - **Region**: Same as your database
   - **Branch**: `main`
   - **Runtime**: `Python 3`
   - **Build Command**:
     ```bash
     pip install -r requirements.txt
     ```
   - **Start Command**:
     ```bash
     uvicorn app:app --host 0.0.0.0 --port $PORT
     ```
   - **Instance Type**: Select **Free**.

4. Scroll down to **"Environment Variables"** and add:

| Key | Value | Description |
| :--- | :--- | :--- |
| `DATABASE_URL` | `postgresql://...` | Connection URL from Step 1 (Render Postgres or Neon) |
| `GOOGLE_API_KEY` | `AIzaSy...` | Your free Google Gemini key from Google AI Studio |
| `GROQ_API_KEY` | `gsk_...` | *(Alternative)* Free Groq key from console.groq.com |
| `PYTHON_VERSION`| `3.12.0` | Recommended Python version |
| `LANGCHAIN_API_KEY` | `lsv2_...` | *(Optional)* For LangSmith tracing |
| `LANGCHAIN_TRACING_V2` | `true` | *(Optional)* LangSmith tracing toggle |

5. Click **"Deploy Web Service"**!
6. Render will build and launch your application. Within 2 minutes, your live URL will be active (e.g., `https://unifinder-ai.onrender.com`).

---

## 🧪 Testing Your Production Deployment

Once your Render URL is live:
1. Visit `https://your-app-name.onrender.com/health`.
   You will see:
   ```json
   {
     "status": "online",
     "service": "UniFinder AI Multi-Agent Higher-Ed Platform",
     "version": "2.5.0",
     "has_google_key": true,
     "has_groq_key": true
   }
   ```
2. Open the main URL in your browser:
   - You can chat in real time with token streaming.
   - You can upload academic transcripts or CVs (indexed with C-RAG).
   - Your chat history, threads, and shortlists will persist permanently in your PostgreSQL database!
