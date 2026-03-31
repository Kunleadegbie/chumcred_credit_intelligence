def extract_learning_features(record):

    return {
        "score": record.get("score"),
        "pd": record.get("probability_of_default"),
        "risk_grade": record.get("risk_grade"),
        "loan_amount": record.get("loan_amount"),
        "repayment_status": record.get("repayment_status"),
        "actual_default": record.get("actual_default")
    }


def evaluate_prediction(record):

    predicted_pd = record.get("probability_of_default", 0)
    actual_default = record.get("actual_default", False)

    if predicted_pd > 0.4 and actual_default:
        return "Correct High Risk"
    elif predicted_pd < 0.2 and not actual_default:
        return "Correct Low Risk"
    else:
        return "Mismatch"


def analyze_portfolio(records):

    total = len(records)
    defaults = sum(1 for r in records if r.get("actual_default"))
    
    avg_pd = sum(r.get("probability_of_default", 0) for r in records) / total

    actual_default_rate = defaults / total

    return {
        "avg_predicted_pd": avg_pd,
        "actual_default_rate": actual_default_rate,
        "model_bias": avg_pd - actual_default_rate
    }

def adjust_score(score, model_bias):

    # if model is too optimistic → reduce score
    if model_bias < -0.1:
        return score - 5
    
    # if model too conservative → increase score
    elif model_bias > 0.1:
        return score + 5

    return score

update_application_status(app_id, {
    "repayment_status": "DEFAULT",
    "actual_default": True,
    "days_past_due": 90
})

st.markdown("## 🧠 Model Performance")

defaults = df["actual_default"].sum()
avg_pd = df["probability_of_default"].mean()

actual_rate = defaults / len(df)

st.metric("Avg Predicted PD", f"{avg_pd:.2%}")
st.metric("Actual Default Rate", f"{actual_rate:.2%}")
st.metric("Model Bias", f"{avg_pd - actual_rate:.2%}")

