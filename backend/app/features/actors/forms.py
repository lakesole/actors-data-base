"""배우 등록/수정 multipart 폼을 ActorForm으로 받는 의존성. 화면 router와 api가 같이 쓴다."""
from fastapi import Form

from app.features.actors.service import ActorForm


def actor_form(
    name: str = Form(...),
    manager_name: str = Form(""),
    gender: str = Form(""),
    birth_year: str = Form(""),
    height_cm: str = Form(""),
    weight_kg: str = Form(""),
    school: str = Form(""),
    hobby: str = Form(""),
    specialty: str = Form(""),
    contract_date: str = Form(""),
    contract_end_date: str = Form(""),
    bio: str = Form(""),
    teacher_user_id: str = Form(""),
    phone_last4: str = Form(""),
) -> ActorForm:
    return ActorForm(
        name=name, manager_name=manager_name, gender=gender, birth_year=birth_year,
        height_cm=height_cm, weight_kg=weight_kg, school=school, hobby=hobby,
        specialty=specialty, contract_date=contract_date, contract_end_date=contract_end_date,
        bio=bio, teacher_user_id=teacher_user_id, phone_last4=phone_last4,
    )
