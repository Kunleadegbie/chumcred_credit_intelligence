import pandas as pd
from sklearn.linear_model import LogisticRegression

from ml.model import save_model


def prepare_dataset(records):

    data = []

    for r in records:
        if r.get("actual_default") is None:
            continue

        data.append({
            "income": r.get("monthly_income") or r.get("monthly_revenue") or 0,
            "expenses": r.get("monthly_expenses") or 0,
            "repayment": r.get("monthly_repayment") or 0,
            "collateral": r.get("collateral_value") or 0,
            "loan_amount": r.get("loan_amount") or 1,
            "default": 1 if r.get("actual_default") else 0
        })

    return pd.DataFrame(data)


def train_model(records):

    df = prepare_dataset(records)

    if len(df) < 20:
        return "Not enough data to train model"

    X = df[["income", "expenses", "repayment", "collateral", "loan_amount"]]
    y = df["default"]

    model = LogisticRegression()
    model.fit(X, y)

    save_model(model)

    return "Model trained successfully"

from ml.trainer import train_model

if st.button("Train ML Model"):

    records = supabase.table("loan_applications").select("*").execute().data

    result = train_model(records)

    st.success(result)