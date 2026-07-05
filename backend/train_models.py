"""
train_models.py - Model Training Pipeline for BuildFlow AI
Trains the Budget Forecast Linear Regression model and the Delay Risk RandomForestClassifier model.
Saves model files to backend/data/models/.
"""

import os
import sys
import pickle
import logging
from datetime import datetime, timedelta
import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression
from sklearn.ensemble import RandomForestClassifier

# Setup path to import settings and data loader
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import settings
from data_loader import data_loader

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-8s | %(message)s")
logger = logging.getLogger("model_trainer")

MODELS_DIR = os.path.join(os.path.dirname(settings.DATA_PATH), "models")


def train_budget_forecast(df: pd.DataFrame) -> dict:
    """Train the Linear Regression model for budget forecasting."""
    logger.info("Training Budget Forecast Model...")
    
    # Generate synthetic monthly spend trend from project data
    total_spent = float(df["spent_lac"].sum()) if "spent_lac" in df.columns else 0.0
    months = 12
    historical = []
    today = datetime.utcnow()
    rng = np.random.default_rng(seed=7)

    for i in range(months - 1, -1, -1):
        dt = today - timedelta(days=30 * i)
        label = dt.strftime("%b %Y")
        frac = (months - i) / months
        noise = rng.uniform(0.88, 1.07)
        monthly_spend = round(total_spent * frac / months * noise * months / 6, 2)
        historical.append({"month": label, "spent": monthly_spend})

    X = np.array(range(len(historical))).reshape(-1, 1)
    y = np.array([h["spent"] for h in historical])

    model = LinearRegression()
    model.fit(X, y)
    
    # Calculate training score
    r2_score = model.score(X, y)
    logger.info("Budget Forecast Model Trained. R2 Score: %.4f", r2_score)
    
    # Save model and historical data metadata
    model_path = os.path.join(MODELS_DIR, "budget_forecast.pkl")
    with open(model_path, "wb") as f:
        pickle.dump({
            "model": model,
            "historical_trend": historical,
            "trained_at": datetime.utcnow().isoformat(),
            "r2_score": float(r2_score)
        }, f)
        
    logger.info("Saved Budget Forecast Model to %s", model_path)
    return {"r2_score": r2_score}


def train_delay_risk_classifier(df: pd.DataFrame) -> dict:
    """Train a RandomForestClassifier to predict if a project will be delayed."""
    logger.info("Training Delay Risk Classification Model...")
    
    # Prepare features and target
    # Target: 1 if status is Delayed, else 0
    if "status" not in df.columns:
        logger.error("Column 'status' not found in projects dataset.")
        return {"error": "Missing 'status' column"}
        
    y = (df["status"].astype(str).str.lower().str.contains("delay|behind", na=False)).astype(int)
    
    # Features
    X_data = pd.DataFrame()
    
    # 1. Budget
    X_data["budget_lac"] = pd.to_numeric(df["budget_lac"], errors="coerce").fillna(0.0)
    # 2. Spent
    X_data["spent_lac"] = pd.to_numeric(df["spent_lac"], errors="coerce").fillna(0.0)
    # 3. Labour count
    X_data["labourcount"] = pd.to_numeric(df["labourcount"], errors="coerce").fillna(0.0)
    # 4. Cement used
    X_data["cementused_tons"] = pd.to_numeric(df["cementused_tons"], errors="coerce").fillna(0.0)
    # 5. Material used
    X_data["materialused_tons"] = pd.to_numeric(df["materialused_tons"], errors="coerce").fillna(0.0)
    # 6. Progress percent
    X_data["progresspercent"] = pd.to_numeric(df["progresspercent"], errors="coerce").fillna(0.0)
    # 7. Spent ratio (Spent / Budget)
    X_data["spent_ratio"] = (X_data["spent_lac"] / X_data["budget_lac"]).replace([np.inf, -np.inf], 0.0).fillna(0.0)
    
    # Train Random Forest Classifier
    clf = RandomForestClassifier(n_estimators=50, max_depth=5, random_state=42)
    clf.fit(X_data, y)
    
    # Evaluate accuracy on training set
    accuracy = clf.score(X_data, y)
    logger.info("Delay Risk Model Trained. Accuracy: %.4f", accuracy)
    
    # Save model and feature names
    model_path = os.path.join(MODELS_DIR, "delay_risk_model.pkl")
    with open(model_path, "wb") as f:
        pickle.dump({
            "model": clf,
            "features": list(X_data.columns),
            "trained_at": datetime.utcnow().isoformat(),
            "accuracy": float(accuracy)
        }, f)
        
    logger.info("Saved Delay Risk Model to %s", model_path)
    return {"accuracy": accuracy}


def run_training() -> dict:
    """Main training coordinator function."""
    os.makedirs(MODELS_DIR, exist_ok=True)
    
    # Load fresh data
    if not data_loader.is_loaded:
        data_loader.load()
        
    df = data_loader.get_dataframe()
    if df.empty:
        logger.error("Dataset is empty. Cannot train models.")
        return {"status": "error", "message": "Dataset is empty"}
        
    # Standardise column names
    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]
    
    results = {}
    results["forecast"] = train_budget_forecast(df)
    results["delay_risk"] = train_delay_risk_classifier(df)
    results["trained_at"] = datetime.utcnow().isoformat()
    results["status"] = "success"
    
    logger.info("Model training pipeline finished successfully!")
    return results


if __name__ == "__main__":
    run_training()
