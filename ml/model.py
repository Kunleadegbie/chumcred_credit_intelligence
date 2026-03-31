import pickle
import os

from ml.model import predict_default_ml

ml_pd = predict_default_ml(ai_data)

if ml_pd is not None:
    pd = ml_pd

MODEL_PATH = "ml/credit_model.pkl"


def save_model(model):
    with open(MODEL_PATH, "wb") as f:
        pickle.dump(model, f)


def load_model():
    if os.path.exists(MODEL_PATH):
        with open(MODEL_PATH, "rb") as f:
            return pickle.load(f)
    return None


def predict_default_ml(data):

    model = load_model()

    if model is None:
        return None  # fallback to rule model

    features = [[
        data.get("monthly_income") or data.get("monthly_revenue") or 0,
        data.get("monthly_expenses") or 0,
        data.get("monthly_repayment") or 0,
        data.get("collateral_value") or 0,
        data.get("loan_amount") or 1
    ]]

    prob = model.predict_proba(features)[0][1]

    return prob