# AffecCare (EQ-Care AI)
*A Privacy-Preserving EAP Recommendation Engine based on Behavioral Feedback*

AffecCare empowers enterprises to safeguard employee mental health and minimize turnover costs through predictive analytics and personalized recommendations.

## 🎯 Project Goal
To bridge the gap between corporate HR management and employee well-being by providing a proactive, privacy-first recommendation system for Employee Assistance Programs (EAP).

## ⚠️ Key Pain Points
- **For Enterprises (HR)**: High turnover costs and the inability to proactively identify at-risk talent before they resign.
- **For Employees**: Workplace stress is high, but EAP adoption remains low due to privacy concerns and "high-frequency, low-relevance" content delivery.

## 💡 Our Solutions

### 1. AI Attrition & Stress Prediction
By analyzing existing HR data (such as tenure, overtime hours, and performance metrics), our model automatically calculates an employee's **Potential Attrition Risk** and **Stress Index**.

### 2. Context-Aware Recommendations
We replace intrusive "spam" with precision. Instead of frequent notifications, we naturally integrate tailored EAP content (e.g., stress-relief techniques for those with high overtime, or management coaching for new leads) into daily newsletters or internal communication tools.

### 3. Behavioral Feedback Loop (Privacy-First)
We track anonymized interaction data (clicks and dwell time) to create a continuous improvement cycle:
- **Model Fine-tuning**: Automatically updates recommendation weights based on user-item interaction matrices.
- **Macro Trend Analytics**: Provides HR with de-identified insights into organization-wide stressors (e.g., "The marketing department has a high demand for #WorkLifeBalance content this month") without exposing individual identities.

## 🚀 Technical Features

- **Predictive ML Engine**: Built with XGBoost and Scikit-Learn pipelines to predict voluntary resignation risk with high recall.
- **EAP Recommendation Pipeline**: A closed-loop system that processes click logs into interaction matrices to retrain models weekly.
- **HR Insight Dashboard**: Aggregates behavioral data into macro trends for data-driven wellness decision-making.
- **MLOps Ready**: Automated training (`train.py`) and rigorous evaluation (`evaluate.py`) with full versioning.

## 📂 Project Structure

- `ml/`: The Intelligence Core. Contains data, model training scripts, evaluation logic, and feedback loop scripts.
- `backend/`: The API Layer. Linked as a Git submodule to the [AffecCare/backend](https://github.com/AffecCare/backend) repository.
- `frontend/`: The Presentation Layer. Linked as a Git submodule to the [AffecCare/frontend](https://github.com/AffecCare/frontend) repository.
- `requirements.txt`: Python dependencies for the ML engine.

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

### 2. Setting Up the Environment

Ensure you have Python 3.8+ installed.

```bash
# Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

## 🧠 ML Pipeline Usage

The ML engine is located in the `ml/` directory.

- **Training & Tuning**: retrain the risk prediction model:
  ```bash
  python ml/train.py
  ```
- **Evaluation**: Generate performance plots and diagnostics:
  ```bash
  python ml/evaluate.py
  ```

## 🛠 Tech Stack

- **Languages**: Python
- **ML Frameworks**: XGBoost, Scikit-Learn
- **Data Processing**: Pandas, NumPy
- **API (Backend)**: Refer to the `backend/` directory for details.
- **Web UI (Frontend)**: Refer to the `frontend/` directory for details.

---

*This project is part of the AffecCare ecosystem.*
