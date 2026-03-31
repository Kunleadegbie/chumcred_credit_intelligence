from db.supabase_client import supabase

def save_credit_assessment(data, institution):

    supabase.table("credit_assessments").insert({
        "client_name": data["client_name"],
        "institution": institution,   # ✅ IMPORTANT
        "borrower_type": data["borrower_type"],
        "loan_amount": data["loan_amount"],
        "tenor": data["tenor"],
        "decision": data["decision"],
        "score": data["score"],
        "ai_recommendation": data["ai_recommendation"]
    }).execute()



