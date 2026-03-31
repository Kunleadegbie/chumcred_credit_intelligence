def build_credit_prompt(data, score, decision):

    return f"""
You are a senior credit risk analyst in a commercial bank.

Analyze the borrower profile below and provide structured credit insights.

IMPORTANT:
- Do NOT change the decision or score
- Only provide supporting analysis
- Be concise, professional, and risk-aware

BORROWER DATA:
{data}

SYSTEM SCORE: {score}
SYSTEM DECISION: {decision}

RETURN STRICT JSON ONLY:

{{
  "ai_risk_flags": [],
  "ai_strengths": [],
  "ai_recommendation": "",
  "ai_narrative": ""
}}
"""