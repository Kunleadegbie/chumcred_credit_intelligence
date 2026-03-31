import streamlit as st
from db.supabase_client import supabase

def login_page():

    st.title("🔐 Chumcred AI Login")


    email = st.text_input("Email").strip().lower()
    password = st.text_input("Password", type="password").strip()

    if st.button("Login"):

        try:
            # 🔥 DEFINE res HERE
            res = supabase.auth.sign_in_with_password({
                "email": email,
                "password": password
            })

            # ✅ NOW SAFE TO USE res
            if res.user:

                st.session_state.user = res.user

                # 🔥 RESET LANDING FLAG
                st.session_state.go_to_login = False

                st.success("Login successful")
                st.rerun()

            else:
                st.error("Invalid login credentials")

        except Exception as e:
            st.error(f"Login failed: {e}")

    