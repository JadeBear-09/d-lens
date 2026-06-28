from typing import Literal

from pydantic import BaseModel

from app.core.config import Settings, get_settings

DLensStatus = Literal["offline", "online"]
Mode = Literal["local_rules_only", "user_llm_key_active"]
ApiKeyStatus = Literal["not_used", "user_provided"]
ApiKeyOwner = Literal["none", "user"]
RuntimeJudgementSource = Literal["offline_rules", "online_llm_assisted"]


class ServiceStatus(BaseModel):
    status: Literal["ok"] = "ok"
    dlens_status: DLensStatus
    mode: Mode
    api_key_status: ApiKeyStatus
    api_key_owner: ApiKeyOwner
    external_llm_calls: bool
    judgement_source: RuntimeJudgementSource


def build_service_status(settings: Settings | None = None) -> ServiceStatus:
    active_settings = settings or get_settings()

    if active_settings.llm_online:
        return ServiceStatus(
            dlens_status="online",
            mode="user_llm_key_active",
            api_key_status="user_provided",
            api_key_owner="user",
            external_llm_calls=True,
            judgement_source="online_llm_assisted",
        )

    return ServiceStatus(
        dlens_status="offline",
        mode="local_rules_only",
        api_key_status="not_used",
        api_key_owner="none",
        external_llm_calls=False,
        judgement_source="offline_rules",
    )
