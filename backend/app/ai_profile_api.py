"""Editable AI profiles and explicit, billable connection testing."""
from typing import Literal
from urllib.parse import urlsplit
import re
from fastapi import APIRouter, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from pydantic import BaseModel, ConfigDict, Field, field_validator
from .model_gateway import complete_json, public_profile, GatewayError
from .platform_harness import encrypt_secret

ROLES = ('requirement_gate', 'file_understanding', 'etl_specification', 'qa_review')


class PrivateValidationRoute(APIRoute):
    def get_route_handler(self):
        handler = super().get_route_handler()
        async def safe_handler(request):
            try:
                return await handler(request)
            except RequestValidationError:
                return JSONResponse(status_code=422, content={'detail': 'AI 設定格式不合法：請檢查必填欄位、模型角色及連線網址；不得在網址或一般欄位填入機密'})
        return safe_handler


class ProfileInput(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    display_name: str = Field(min_length=1, max_length=120)
    provider_type: Literal['LITELLM_BEDROCK', 'LITELLM_PROXY', 'LOCAL_COPILOT'] = 'LITELLM_BEDROCK'
    endpoint: str | None = Field(default=None, max_length=1000)
    region: str | None = Field(default=None, max_length=80)
    model_routes: dict[str, str] = Field(default_factory=dict)
    enabled: bool = True

    @field_validator('endpoint')
    @classmethod
    def endpoint_format(cls, value):
        if not value:
            return None
        try:
            parsed = urlsplit(value)
            if parsed.scheme not in ('http', 'https') or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
                raise ValueError()
            _ = parsed.port
        except ValueError:
            raise ValueError('Endpoint 必須是無帳密、query 或 fragment 的 HTTP(S) URL') from None
        return value.rstrip('/')

    @field_validator('model_routes')
    @classmethod
    def routes_format(cls, value):
        if any(key not in ROLES or not model.strip() or len(model) > 200 for key, model in value.items()):
            raise ValueError('模型路由必須指定受支援角色與非空模型名稱')
        return {key: model.strip() for key, model in value.items()}


class SecretInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    secret_value: str = Field(min_length=1, max_length=10000)


def create_ai_profile_router(repo, *, complete=complete_json):
    router = APIRouter(prefix='/api/settings/ai-profiles', tags=['AI profiles'], route_class=PrivateValidationRoute)

    def get_profile(profile_id):
        profile = repo.ai_profile(profile_id)
        if not profile:
            raise HTTPException(404, 'AI Profile 不存在')
        return profile

    @router.get('')
    def list_profiles():
        return repo.ai_profiles()

    @router.put('/{profile_id}')
    def save_profile(profile_id: str, value: ProfileInput):
        if not re.fullmatch(r'[a-zA-Z0-9_-]{2,80}', profile_id):
            raise HTTPException(422, 'Profile ID 格式不合法')
        if value.provider_type == 'LITELLM_BEDROCK' and value.endpoint:
            raise HTTPException(422, '直接 Bedrock 連線請清空 Endpoint；代理連線請選 LiteLLM Proxy')
        if value.provider_type == 'LOCAL_COPILOT' and (value.endpoint or value.region):
            raise HTTPException(422, '本機 Copilot 使用 Windows 登入，不接受 Endpoint 或 AWS Region')
        try:
            return public_profile(repo.upsert_ai_profile({**value.model_dump(), 'profile_id': profile_id}))
        except Exception:
            raise HTTPException(503, 'AI Profile 儲存失敗，請檢查平台資料庫') from None

    @router.post('/{profile_id}/secret')
    def save_profile_secret(profile_id: str, value: SecretInput):
        profile = get_profile(profile_id)
        if profile['provider_type'] == 'LOCAL_COPILOT':
            raise HTTPException(422, '本機 Copilot 使用既有 CLI 登入，平台不保存其 Token')
        try:
            cipher, nonce = encrypt_secret(value.secret_value)
            secret_ref = f'ai-profile:{profile_id}'
            repo.save_secret(secret_ref, cipher, nonce)
            repo.upsert_ai_profile({**profile, 'secret_ref': secret_ref})
            return {'profile_id': profile_id, 'secret_configured': True}
        except Exception:
            raise HTTPException(503, '機密儲存失敗，請檢查主金鑰與平台資料庫') from None

    @router.post('/{profile_id}/test')
    def test_profile(profile_id: str, role: Literal['requirement_gate', 'file_understanding', 'etl_specification', 'qa_review'] = 'requirement_gate'):
        profile = get_profile(profile_id)
        try:
            secret = repo.read_secret(profile['secret_ref']) if profile.get('secret_ref') else None
            data, usage = complete(profile, role, [{'role': 'user', 'content': 'Connection test. Return exactly this JSON object: {"ok":true}'}], secret=secret)
            if data.get('ok') is not True:
                raise GatewayError('MODEL_TEST_RESPONSE_INVALID')
            return {'status': 'CONNECTED', 'profile_id': profile_id, 'role': role, 'usage': usage, 'scope': 'MODEL_CALL_ONLY'}
        except GatewayError as exc:
            raise HTTPException(422, detail={'code': str(exc), 'message': '模型呼叫未通過；請檢查角色模型、區域、Endpoint、憑證與服務權限'}) from None
        except Exception:
            raise HTTPException(503, '模型測試失敗；未回傳服務端原始錯誤或機密') from None

    return router
