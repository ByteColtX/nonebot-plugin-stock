"""免费数据源的 HTTP 取数辅助。"""

from __future__ import annotations

import httpx

from .base import ProviderError

DEFAULT_TIMEOUT = 5.0
USER_AGENT = "Mozilla/5.0 (compatible; nonebot-plugin-stock)"


async def get_text(
    url: str,
    *,
    encoding: str = "gbk",
    headers: dict[str, str] | None = None,
    timeout: float = DEFAULT_TIMEOUT,
    transport: httpx.AsyncBaseTransport | None = None,
) -> str:
    """请求一个文本接口并按指定编码解码。

    Args:
        url: 请求地址。
        encoding: 响应体编码，免费源多为 GBK。
        headers: 额外请求头。
        timeout: 请求超时秒数。
        transport: 自定义传输层，测试时注入 MockTransport。

    Returns:
        解码后的响应文本。

    Raises:
        ProviderError: 请求失败或状态码非 2xx。
    """
    request_headers = {"User-Agent": USER_AGENT}
    if headers:
        request_headers.update(headers)
    try:
        async with httpx.AsyncClient(
            timeout=timeout,
            transport=transport,
            headers=request_headers,
            follow_redirects=True,
        ) as client:
            response = await client.get(url)
            response.raise_for_status()
    except httpx.HTTPError as error:
        raise ProviderError(f"请求失败：{error}") from error
    return response.content.decode(encoding, errors="replace")
