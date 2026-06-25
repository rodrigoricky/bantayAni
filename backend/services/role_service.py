from utils.database import execute_query, is_demo_mode, _load_demo_data


def get_role_data(user: dict) -> dict:
    role = user.get("role")
    municipality_id = user.get("municipality_id")

    if role == "DA_REGIONAL":
        municipalities = execute_query(
            """
            SELECT m.id, m.name FROM municipalities m
            WHERE m.region = (
                SELECT region FROM municipalities WHERE id = %s
            )
            """,
            (municipality_id,),
            fetch_all=True,
        )
        if is_demo_mode() and not municipalities:
            data = _load_demo_data()
            municipalities = data.get("municipalities", [data["municipality"]])
        return {"municipalities": municipalities or []}

    if role == "PCIC":
        return {"coverage_region": "Region V (Bicol)"}

    if role == "ADMIN":
        return {"admin_access": True}

    return {}