def validate_inputs(data: dict):
    errors = []

    if not data.get("client_name"):
        errors.append("Client name required")

    if data.get("requested_amount", 0) <= 0:
        errors.append("Invalid loan amount")

    return errors