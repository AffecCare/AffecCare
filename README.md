# AffecCare (EQ-Care AI)
*A Privacy-Preserving EAP Recommendation Engine based on Behavioral Feedback*

AffecCare empowers enterprises to safeguard employee mental health and deliver precise wellness resources through intelligent, privacy-first recommendations.

## 🎯 Project Goal
To bridge the gap between corporate HR management and employee well-being by replacing traditional "one-size-fits-all" EAP (Employee Assistance Program) newsletters with a proactive, personalized recommendation system.

## ⚠️ Key Pain Points
- **For Enterprises (HR)**: Unable to gauge the real-time mental well-being of the organization. Traditional EAP resources are often ignored by employees.
- **For Employees**: Workplace stress is high, but EAP adoption remains low due to "high-frequency, low-relevance" generic content delivery.

## 💡 Our Solutions (The New Paradigm)

### 1. Vector Space Recommendation Engine (VSM)
We abandoned static profiling. Each article and user is mapped into a 3D latent space (`Stress & Emotion`, `Work & Career`, `Health & Life`). The engine calculates the **Cosine Similarity** to push the most relevant top N articles directly to the employee's inbox.

### 2. Real-Time Implicit Feedback Loop (Online Learning)
We track lightweight interactions (Likes, Dislikes, and Clicks):
- **Dynamic Vector Updates**: Instead of weekly batch training, user preference vectors are updated instantly using an Exponential Decay mechanism. A "Like" pulls the user closer to the article's topic cluster, while preserving past behavioral history (50/50 blend).
- **Gamification**: Employees earn points for providing feedback, increasing overall engagement.

### 3. HR Insight Dashboard & Interventions
The recommendation engine acts as a reverse-sensor for HR:
- **Macro Trend Analytics**: Aggregates individual vectors into department-wide **Stress Levels** and **Primary Concerns**.
- **Actionable Interventions**: The dashboard automatically flags high-risk cohorts and suggests concrete interventions (e.g., "Schedule 1-on-1s" or "Push Emotion Awareness content").

## 🚀 Technical Features

- **Content-Based Filtering**: Zero cold-start problem. Works immediately based on explicit onboarding preferences.
- **High Interpretability**: No black-box AI. Every recommendation can be traced back to clear, semantic dimensions, allowing HR to trust the data.
- **PostgreSQL Integrated**: Real-time aggregation via SQLAlchemy, completely dropping legacy static CSV dependencies.

## 📂 Project Structure

- `backend/`: The API Layer (Flask). Contains the recommendation engine (`app/services/recommendation.py`), vector updater (`vector_updater.py`), and HR dashboard logic.
- `frontend/`: The Presentation Layer. A modern SPA built with TanStack Start/Router.
- `data/`: Seed data and mock HR databases for local development.
- `docs/`: System documentation and analysis reports.

## 🛠️ Installation & Setup

### 1. Cloning the Repository

Since this project uses Git submodules for both the backend and frontend, you must clone recursively:

**For a new clone:**
```bash
git clone --recursive https://github.com/AffecCare/AffecCare.git
```

**If you have already cloned without submodules:**
```bash
git submodule update --init --recursive
```

**Update submodules to latest main branch:**
```bash
git submodule foreach --recursive 'git checkout main && git pull origin main'
```

### 2. Setting Up the Environment

Ensure you have Python 3.8+ installed.

```bash
# Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

---

*This project is part of the AffecCare ecosystem.*
