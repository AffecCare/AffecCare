"""
Voluntary Turnover Risk Prediction - Evaluation & Diagnostics (Tuned)
---------------------------------------------------------------------
Description: 
    Executes a rigorous Stratified K-Fold cross-validation on the HR dataset. 
    It automatically loads the optimal pipeline architecture serialized by 
    the training module, applies a business-driven threshold to maximize 
    Recall, and outputs professional diagnostic artifacts.
"""

import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import joblib

from sklearn.metrics import (
    classification_report, confusion_matrix, 
    roc_curve, auc, precision_recall_curve, average_precision_score
)
from sklearn.model_selection import StratifiedKFold, cross_val_predict

from train import DATA_PATH, MODEL_PATH, TARGET_COL, LABEL_INVOLUNTARY, LABEL_VOLUNTARY

# ==============================================================================
# CONFIGURATION & HYPERPARAMETERS
# ==============================================================================
PLOT_DIR = Path("plots")
PLOT_DIR.mkdir(parents=True, exist_ok=True)

plt.style.use('default')
sns.set_theme(style="whitegrid", palette="muted")

# Business Policy: Lower threshold to capture more flight-risk employees
BUSINESS_THRESHOLD = 0.30  

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def plot_confusion_matrix(y_true: pd.Series, y_pred: np.ndarray, output_path: Path, threshold: float):
    cm = confusion_matrix(y_true, y_pred)
    plt.figure(figsize=(6, 5))
    sns.heatmap(cm, annot=True, fmt='d', cmap='Blues', cbar=False,
                xticklabels=['Predicted Stay (0)', 'Predicted Leave (1)'],
                yticklabels=['Actual Stay (0)', 'Actual Leave (1)'],
                annot_kws={"size": 14})
    plt.title(f'Confusion Matrix (Threshold = {threshold:.2f})', fontsize=14, pad=15)
    plt.ylabel('True Label', fontsize=12)
    plt.xlabel('Predicted Label', fontsize=12)
    plt.tight_layout()
    plt.savefig(output_path, dpi=300)
    plt.close()


def plot_roc_and_pr_curves(y_true: pd.Series, y_proba: np.ndarray, output_path: Path):
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))

    # ROC
    fpr, tpr, _ = roc_curve(y_true, y_proba)
    roc_auc = auc(fpr, tpr)
    ax1.plot(fpr, tpr, color='#1f77b4', lw=2, label=f'ROC curve (AUC = {roc_auc:.3f})')
    ax1.plot([0, 1], [0, 1], color='gray', lw=1.5, linestyle='--')
    ax1.set_xlim([0.0, 1.0])
    ax1.set_ylim([0.0, 1.05])
    ax1.set_xlabel('False Positive Rate', fontsize=11)
    ax1.set_ylabel('True Positive Rate', fontsize=11)
    ax1.set_title('Receiver Operating Characteristic (ROC)', fontsize=13)
    ax1.legend(loc="lower right")

    # PR
    precision, recall, _ = precision_recall_curve(y_true, y_proba)
    pr_auc = average_precision_score(y_true, y_proba)
    ax2.plot(recall, precision, color='#ff7f0e', lw=2, label=f'PR curve (AP = {pr_auc:.3f})')
    baseline = y_true.sum() / len(y_true)
    ax2.axhline(y=baseline, color='gray', lw=1.5, linestyle='--', label=f'Baseline ({baseline:.2f})')
    ax2.set_xlim([0.0, 1.0])
    ax2.set_ylim([0.0, 1.05])
    ax2.set_xlabel('Recall (Sensitivity)', fontsize=11)
    ax2.set_ylabel('Precision (PPV)', fontsize=11)
    ax2.set_title('Precision-Recall Curve', fontsize=13)
    ax2.legend(loc="upper right")

    plt.tight_layout()
    plt.savefig(output_path, dpi=300)
    plt.close()


def find_optimal_threshold(y_true: pd.Series, y_proba: np.ndarray) -> float:
    precision, recall, thresholds = precision_recall_curve(y_true, y_proba)
    f1_scores = 2 * (precision * recall) / (precision + recall + 1e-10)
    optimal_idx = np.argmax(f1_scores)
    return thresholds[optimal_idx] if optimal_idx < len(thresholds) else 0.5


def main():
    logger.info("Starting automated evaluation pipeline...")
    
    # 1. Load Data
    df = pd.read_csv(DATA_PATH)
    df.columns = df.columns.str.strip()
    df_valid = df[df[TARGET_COL] != LABEL_INVOLUNTARY].copy()
    
    X = df_valid.drop(columns=[TARGET_COL]).astype(np.float32)
    y = (df_valid[TARGET_COL] == LABEL_VOLUNTARY).astype(int)
    
    # 2. 🌟 修正點：載入 train.py 訓練好的最佳模型架構
    if not MODEL_PATH.exists():
        logger.error(f"Model artifact not found at {MODEL_PATH}. Please run train.py first!")
        sys.exit(1)
        
    logger.info(f"Loading optimal model architecture from {MODEL_PATH}")
    # joblib.load 會還原我們在 GridSearchCV 找到的最佳參數配置 (best_estimator_)
    pipeline = joblib.load(MODEL_PATH)
    
    # 3. Cross-Validation Predictions
    logger.info("Executing 5-Fold Cross-Validation to extract unbiased probabilities...")
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    
    # cross_val_predict 會自動 Clone 我們的 pipeline 進行驗證，確保沒有資料洩漏
    y_proba = cross_val_predict(pipeline, X, y, cv=cv, method='predict_proba')[:, 1]
    
    # 4. Threshold Application
    optimal_f1_threshold = find_optimal_threshold(y, y_proba)
    logger.info(f"Statistical optimal threshold (Max F1): {optimal_f1_threshold:.3f}")
    logger.info(f"Applying Business-Driven Threshold: {BUSINESS_THRESHOLD:.3f}")
    
    y_pred_tuned = (y_proba >= BUSINESS_THRESHOLD).astype(int)
    
    # 5. Reporting
    print("\n" + "="*60)
    print(f"{'📊 BUSINESS-TUNED PERFORMANCE REPORT (AUTO-TUNED MODEL)':^60}")
    print("="*60)
    print(classification_report(y, y_pred_tuned, target_names=["Stayed (0)", "Voluntary Term (1)"]))
    
    # 6. Diagnostics Generation
    logger.info("Generating diagnostic plots in 'plots/' directory...")
    plot_confusion_matrix(y, y_pred_tuned, PLOT_DIR / "confusion_matrix_tuned.png", BUSINESS_THRESHOLD)
    plot_roc_and_pr_curves(y, y_proba, PLOT_DIR / "roc_pr_curves.png")
    
    logger.info("✅ Evaluation complete. Review the plots for business impact.")

if __name__ == "__main__":
    main()