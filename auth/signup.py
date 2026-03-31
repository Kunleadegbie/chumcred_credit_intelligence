import streamlit as st
from db.supabase_client import supabase


def signup_page():
    st.title("📝 Create Account")

    email = st.text_input("Email", key="signup_email")
    password = st.text_input("Password", type="password", key="signup_password")
    institution = st.text_input("Institution Name", key="signup_institution")

    if st.button("Sign Up", key="signup_button"):
        if not email.strip():
            st.error("Email is required.")
            return

        if not password.strip():
            st.error("Password is required.")
            return

        if not institution.strip():
            st.error("Institution Name is required.")
            return

        try:
            response = supabase.auth.sign_up({
                "email": email,
                "password": password,
                "options": {
                    "email_redirect_to": "http://localhost:8501"
                }
            })

            user = response.user

            if user:
                supabase.table("user_profiles").insert({
                    "id": user.id,
                    "email": email,
                    "role": "pending",
                    "institution": institution
                }).execute()

                st.success(
                    "Account created successfully. Please confirm your email. "
                    "After confirmation, an administrator will assign your role."
                )
            else:
                st.warning(
                    "Signup request was submitted, but no user record was returned yet. "
                    "Please check your email for confirmation."
                )

        except Exception as e:
            st.error(f"Signup failed: {e}")