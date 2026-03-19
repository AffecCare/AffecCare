# AffecCare

AffecCare is an enterprise-grade AI solution designed to maximize the business value of employee retention through predictive analytics. By leveraging advanced machine learning models, AffecCare identifies at-risk employees and provides actionable insights for HR departments.

## 🚀 Core Features

- **Predictive ML Engine**: Built with XGBoost and Scikit-Learn pipelines to predict voluntary resignation risk.
- **Business-Centric Optimization**: Fine-tuned thresholds (Recall @ 0.3) to prioritize capturing potential leavers over simple accuracy.
- **Data-Driven Insights**: Analyzes key dimensions such as Salary Compa-Ratio, Engagement Scores, and Tenure to provide a holistic view of employee behavior.
- **MLOps Ready**: Automated training (`train.py`) and rigorous evaluation (`evaluate.py`) pipelines with full versioning of models and tuning reports.

## 📂 Project Structure

- `ml/`: The Intelligence Core. Contains data, model training scripts, evaluation logic, and generated plots.
- `backend/`: The API Layer. Linked as a Git submodule to the [AffecCare/backend](https://github.com/AffecCare/backend) repository.
- `requirements.txt`: Python dependencies for the ML engine.

## 🛠️ Installation & Setup

### 1. Cloning the Repository

Since this project uses Git submodules for the backend, you must clone recursively to include all components:

**For a new clone:**
```bash
git clone --recursive https://github.com/AffecCare/AffecCare.git
```

**If you have already cloned without submodules:**
```bash
git submodule update --init --recursive
```

### 2. Setting Up the Environment

Ensure you have Python 3.8+ installed. It is recommended to use a virtual environment:

```bash
# Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

## 🧠 ML Pipeline Usage

The ML engine is located in the `ml/` directory.

- **Training**: To retrain the model and perform hyperparameter tuning:
  ```bash
  python ml/train.py
  ```
- **Evaluation**: To run diagnostics on the trained model and generate performance plots:
  ```bash
  python ml/evaluate.py
  ```

## 🛠 Tech Stack

- **Languages**: Python
- **ML Frameworks**: XGBoost, Scikit-Learn
- **Data Processing**: Pandas, NumPy
- **Visualization**: Matplotlib, Seaborn
- **API (Backend)**: Refer to the `backend/` directory for details.

---

*This project is part of the AffecCare ecosystem.*
