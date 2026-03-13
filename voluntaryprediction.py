import pandas as pd
import xgboost as xgb
from imblearn.over_sampling import SMOTE
from sklearn.base import BaseEstimator, TransformerMixin
from imblearn.pipeline import Pipeline
from sklearn.model_selection import StratifiedKFold, cross_val_predict
from sklearn.metrics import classification_report
import joblib

# 1. Define a custom preprocessor
class HRDataPreprocessor(BaseEstimator, TransformerMixin):
    def fit(self, X, y=None):
        # Calculate medians on training data only
        self.medians = X.median(numeric_only=True)
        return self
    
    def transform(self, X):
        X = X.copy()
        # Clean the data exactly how we did before
        X = X.fillna(self.medians) 
        X = X.replace({'True': 1, 'False': 0, True: 1, False: 0})
        return X.apply(pd.to_numeric)

# 2. Load Data
df = pd.read_csv('Cleaned_HR_Data_Combined_V2.csv')
df.columns = df.columns.str.strip()

# Define Features and Target
X = df.drop(['Target'], axis=1)
y_vol = (df['Target'] == 2).astype(int) # Voluntary Termination binary target

# 2. Setup the Pipeline
# We use a pipeline so SMOTE is applied correctly during cross-validation
vol_pipeline = Pipeline([
    ('preprocessor', HRDataPreprocessor()),
    ('smote', SMOTE(random_state=42)),
    ('model', xgb.XGBClassifier(
        n_estimators=100, 
        learning_rate=0.05, 
        max_depth=4, 
        eval_metric='logloss', 
        random_state=42
    ))
])

# 3. Generate the Classification Report using Cross-Validation
# This creates the report using "out-of-sample" predictions
cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
y_pred_cv = cross_val_predict(vol_pipeline, X, y_vol, cv=cv)

print("\n====================")
print("RISK ENGINE: VOLUNTARY TERMINATION")
print("====================")
print(classification_report(y_vol, y_pred_cv, target_names=['Stayed (0)', 'Voluntary Term (1)']))

# 4. Train the final model on ALL data to use for scoring employees
vol_pipeline.fit(X, y_vol)

joblib.dump(vol_pipeline, 'Voluntary_Risk_Engine.pkl')

print("Model saved successfully as 'Voluntary_Risk_Engine.pkl'")

# 5. Isolate Active Employees and Score them
active_employees = df[df['Target'] == 0].copy()
X_active = active_employees.drop(['Target'], axis=1, errors='ignore')

# Predict probability
active_employees['Voluntary_Risk_Score'] = vol_pipeline.predict_proba(X_active)[:, 1]

# Display top risks
print("\n--- Top 10 High Risk Employees ---")
print(active_employees.sort_values(by='Voluntary_Risk_Score', ascending=False)[['Voluntary_Risk_Score']].head(10))
