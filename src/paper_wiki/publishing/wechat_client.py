from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import requests

from paper_wiki.publishing.exceptions import WeChatAPIError

WECHAT_API_BASE = "https://api.weixin.qq.com/cgi-bin"


class WeChatClient:
    """Small wrapper around the official WeChat Official Account APIs used here."""

    def __init__(
        self,
        appid: str,
        secret: str,
        *,
        timeout: float = 30.0,
        session: requests.Session | None = None,
    ) -> None:
        self.appid = appid
        self.secret = secret
        self.timeout = timeout
        self.session = session or requests.Session()
        self._access_token: str | None = None

    def get_access_token(self) -> str:
        if self._access_token:
            return self._access_token

        response = self.session.get(
            f"{WECHAT_API_BASE}/token",
            params={"grant_type": "client_credential", "appid": self.appid, "secret": self.secret},
            timeout=self.timeout,
        )
        payload = self._json(response)
        token = payload.get("access_token")
        if not token:
            self._raise_api_error(payload, fallback="missing access_token in WeChat response")
        self._access_token = str(token)
        return self._access_token

    def upload_article_image(self, image_path: Path) -> str:
        token = self.get_access_token()
        with image_path.open("rb") as handle:
            response = self.session.post(
                f"{WECHAT_API_BASE}/media/uploadimg",
                params={"access_token": token},
                files={"media": (image_path.name, handle)},
                timeout=self.timeout,
            )
        payload = self._json(response)
        url = payload.get("url")
        if not url:
            self._raise_api_error(payload, fallback=f"failed to upload article image: {image_path.name}")
        return str(url)

    def upload_permanent_image(self, image_path: Path) -> str:
        token = self.get_access_token()
        with image_path.open("rb") as handle:
            response = self.session.post(
                f"{WECHAT_API_BASE}/material/add_material",
                params={"access_token": token, "type": "image"},
                files={"media": (image_path.name, handle)},
                timeout=self.timeout,
            )
        payload = self._json(response)
        media_id = payload.get("media_id")
        if not media_id:
            self._raise_api_error(payload, fallback=f"failed to upload cover image: {image_path.name}")
        return str(media_id)

    def create_draft(
        self,
        *,
        title: str,
        content: str,
        thumb_media_id: str,
        author: str | None = None,
        digest: str | None = None,
    ) -> dict[str, Any]:
        token = self.get_access_token()
        article: dict[str, Any] = {
            "title": title,
            "content": content,
            "thumb_media_id": thumb_media_id,
            "need_open_comment": 0,
            "only_fans_can_comment": 0,
        }
        if author:
            article["author"] = author
        if digest:
            article["digest"] = digest

        body = json.dumps({"articles": [article]}, ensure_ascii=False).encode("utf-8")
        response = self.session.post(
            f"{WECHAT_API_BASE}/draft/add",
            params={"access_token": token},
            data=body,
            headers={"Content-Type": "application/json; charset=utf-8"},
            timeout=self.timeout,
        )
        payload = self._json(response)
        media_id = payload.get("media_id")
        if not media_id:
            self._raise_api_error(payload, fallback="failed to create WeChat draft")
        return payload

    @staticmethod
    def _json(response: requests.Response) -> dict[str, Any]:
        try:
            payload = response.json()
        except ValueError as exc:
            raise WeChatAPIError(None, f"non-JSON WeChat response with HTTP {response.status_code}") from exc
        if response.status_code >= 400:
            WeChatClient._raise_api_error(payload, fallback=f"HTTP {response.status_code}")
        errcode = payload.get("errcode")
        if errcode not in (None, 0):
            WeChatClient._raise_api_error(payload, fallback="WeChat API returned an error")
        return payload

    @staticmethod
    def _raise_api_error(payload: dict[str, Any], *, fallback: str) -> None:
        code = payload.get("errcode")
        message = payload.get("errmsg") or fallback
        raise WeChatAPIError(int(code) if isinstance(code, int) else None, str(message), response=payload)
