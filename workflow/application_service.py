from db.supabase_client import supabase


def create_application(payload: dict):
    return supabase.table("loan_applications").insert(payload).execute()


def get_applications_by_status(institution: str, status: str):
    return (
        supabase.table("loan_applications")
        .select("*")
        .eq("institution", institution)
        .eq("workflow_status", status)
        .order("created_at", desc=True)
        .execute()
    )


def update_application_status(app_id: str, updates: dict):
    return (
        supabase.table("loan_applications")
        .update(updates)
        .eq("id", app_id)
        .execute()
    )


def get_institution_applications(institution: str):
    return (
        supabase.table("loan_applications")
        .select("*")
        .eq("institution", institution)
        .order("created_at", desc=True)
        .execute()
    )


def get_all_applications():
    return (
        supabase.table("loan_applications")
        .select("*")
        .order("created_at", desc=True)
        .execute()
    )