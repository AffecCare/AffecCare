"""
Voluntary Turnover Risk Prediction - Automated Training & Tracking Pipeline
-------------------------------------------------------------------------
Architecture: Scikit-Learn Pipeline + XGBoost Native Imbalance Handling
Description: 
    This production-grade script ingests HR data, automatically searches 
    for the optimal XGBoost hyperparameters using GridSearchCV (optimizing 
    for ROC-AUC), logs the top configurations to a JSON artifact for 
    experiment tracking, and serializes the best model for downstream inference.
"""

import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Tuple

import numpy as np
import pandas as pd
import xgboost as xgb
import joblib

from sklearn.impute import SimpleImputer
from sklearn.model_selection import GridSearchCV, StratifiedKFold
from sklearn.pipeline import Pipeline
from sklearn import set_config

# Configure scikit-learn to output Pandas DataFrames to preserve feature names natively
set_config(transform_output="pandas")

# ==============================================================================
# CONFIGURATION & CONSTANTS
# ==============================================================================
# File Paths
DATA_PATH = Path("data/ml_data.csv")
MODEL_PATH = Path("models/voluntary_risk.pkl")
REPORT_PATH = Path("models/tuning_report.json")

# Data Schema & Labels
TARGET_COL = "Target"
LABEL_INVOLUNTARY = 1
LABEL_VOLUNTARY = 2
RANDOM_SEED = 42

# Logging Setup
logging.basicConfig(
    level=logging.INFO, 
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)

# ==============================================================================
# HYPERPARAMETER SEARCH SPACE
# ==============================================================================
# Grid search space for automated hyperparameter tuning.
# scale_pos_weight is utilized as a native alternative to SMOTE for class imbalance.
PARAM_GRID = {
    "classifier__n_estimators": [50, 100, 200],
    "classifier__max_depth": [3, 4, 5],
    "classifier__learning_rate": [0.01, 0.05, 0.1],
    "classifier__scale_pos_weight": [1.0, 2.0, 3.0] 
}


def load_and_prepare_data(filepath: Path) -> Tuple[pd.DataFrame, pd.Series]:
    """
    Loads raw data, strips whitespace, and isolates the voluntary turnover population.
    """
    try:
        logger.info(f"Loading dataset from {filepath}...")
        df = pd.read_csv(filepath)
        df.columns = df.columns.str.strip()
        
        # Isolate valid modeling population (Drop involuntary turnover records)
        df_valid = df[df[TARGET_COL] != LABEL_INVOLUNTARY].copy()
        
        X = df_valid.drop(columns=[TARGET_COL]).astype(np.float32)
        y = (df_valid[TARGET_COL] == LABEL_VOLUNTARY).astype(int)
        
        logger.info(f"Data ingestion complete. X shape: {X.shape}, y shape: {y.shape}")
        return X, y
        
    except FileNotFoundError:
        logger.error(f"Critical Error: Dataset not found at {filepath}.")
        sys.exit(1)


def build_base_pipeline() -> Pipeline:
    """
    Constructs the base machine learning pipeline without oversampling.
    """
    return Pipeline([
        ("imputer", SimpleImputer(strategy="median")),
        ("classifier", xgb.XGBClassifier(
            eval_metric="logloss", 
            random_state=RANDOM_SEED, 
            n_jobs=-1  # Utilize all CPU cores
        ))
    ])


def train_with_hyperparameter_tuning(X: pd.DataFrame, y: pd.Series) -> Pipeline:
    """
    Executes GridSearchCV to find the optimal hyperparameters, logs the top 
    results into a JSON artifact, and returns the best fitted pipeline.
    """
    base_pipeline = build_base_pipeline()
    cv_strategy = StratifiedKFold(n_splits=5, shuffle=True, random_state=RANDOM_SEED)
    
    total_combinations = (
        len(PARAM_GRID["classifier__n_estimators"]) * len(PARAM_GRID["classifier__max_depth"]) * len(PARAM_GRID["classifier__learning_rate"]) * len(PARAM_GRID["classifier__scale_pos_weight"])
    )
    
    logger.info("Initiating Hyperparameter Tuning via GridSearchCV...")
    logger.info(f"Exploring {total_combinations} candidate parameter configurations...")
    
    grid_search = GridSearchCV(
        estimator=base_pipeline,
        param_grid=PARAM_GRID,
        scoring="roc_auc",  # Optimizing for class separation capability
        cv=cv_strategy,
        n_jobs=-1,
        verbose=1
    )
    
    # Execute the intensive grid search
    grid_search.fit(X, y)
    
    logger.info("✅ Hyperparameter Tuning Successfully Completed!")
    logger.info(f"Peak ROC-AUC Score achieved: {grid_search.best_score_:.4f}")
    
    # ==========================================================
    # EXPERIMENT TRACKING: Serialize tuning history to JSON
    # ==========================================================
    results_df = pd.DataFrame(grid_search.cv_results_)
    top_5_results = results_df.sort_values(by="rank_test_score").head(5)
    
    experiment_log = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "best_score_roc_auc": float(grid_search.best_score_),
        "best_parameters": grid_search.best_params_,
        "top_5_configurations": []
    }
    
    for _, row in top_5_results.iterrows():
        # Casting to native Python types to ensure JSON serializability
        experiment_log["top_5_configurations"].append({
            "rank": int(row["rank_test_score"]),
            "mean_test_score_auc": float(row["mean_test_score"]),
            "std_test_score_auc": float(row["std_test_score"]),
            "params": row["params"]
        })
        
    # Ensure directory exists before saving
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        json.dump(experiment_log, f, indent=4, ensure_ascii=False)
        
    logger.info(f"Experiment tracking log safely serialized to {REPORT_PATH}")
    
    return grid_search.best_estimator_


def main() -> None:
    """
    Main orchestration function for the automated training pipeline.
    """
    try:
        # 1. Data Ingestion & Preprocessing
        X, y = load_and_prepare_data(DATA_PATH)
        
        # 2. Automated Training & Tuning
        best_model_pipeline = train_with_hyperparameter_tuning(X, y)
        
        # 3. Model Artifact Serialization
        MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(best_model_pipeline, MODEL_PATH)
        logger.info(f"Optimal production model successfully serialized to {MODEL_PATH}")
        
    except Exception as e:
        logger.error(f"Training pipeline encountered a fatal error: {str(e)}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()