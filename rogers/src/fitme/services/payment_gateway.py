"""
聚合支付网关（虎皮椒 xunhupay）

个人可开通、无需营业执照。订单机制：下单返回二维码 → 用户扫码付款 →
虎皮椒 POST 回调 notify_url → 验签后发放额度（付款后才到账，无人工核销）。

签名算法（下单与回调一致）：
  1. 取除 hash 外的所有参数（空值参数不参与）
  2. 按 key 字典序排序，以 & 连接为 key1=value1&key2=value2... 的字符串
  3. 末尾拼接 appsecret，整体 md5 小写 = hash

回调约定：服务器返回纯文本 `success` 表示收到，否则虎皮椒会重试 6 次。
"""
import hashlib
import logging
import time
from typing import Any, Optional

import httpx

from app.config import settings

logger = logging.getLogger("fitcream.billing")

_XUNHUPAY_DEFAULT_API = "https://api.xunhupay.com/payment/do.html"


def sign_params(params: dict[str, Any], appsecret: str) -> str:
    """虎皮椒签名（非空参数按 key 排序以 & 拼接 + appsecret，md5 小写）。"""
    keys = sorted(
        k for k in params.keys() if k != "hash" and str(params[k]) != ""
    )
    raw = "&".join(f"{k}={params[k]}" for k in keys) + appsecret
    return hashlib.md5(raw.encode("utf-8")).hexdigest()


def _nonce_str(seed: str) -> str:
    return f"{int(time.time())}{hashlib.md5(seed.encode('utf-8')).hexdigest()[:8]}"


class XunhupayGateway:
    """虎皮椒支付网关（未配置 appid/secret 时 configured=False，走备用流程）。"""

    @property
    def configured(self) -> bool:
        return bool(
            settings.XUNHUPAY_APPID
            and settings.XUNHUPAY_APP_SECRET
            and settings.XUNHUPAY_NOTIFY_URL
        )

    async def create_order(
        self,
        *,
        trade_order_id: str,
        amount: Any,
        title: str = "FitCream 充值",
        attach: Optional[str] = None,
    ) -> dict:
        """下单。amount 为元（str/Decimal/int 均可，转字符串传参）。

        成功返回虎皮椒响应：{errcode, errmsg, url_qrcode, url, orderid}。
        失败（errcode!=0 或网络异常）抛 RuntimeError。
        """
        params: dict[str, Any] = {
            "version": "1.1",
            "appid": settings.XUNHUPAY_APPID,
            "trade_order_id": str(trade_order_id),
            "total_fee": str(amount),
            "title": (title or "充值")[:40],
            "time": str(int(time.time())),
            "notify_url": settings.XUNHUPAY_NOTIFY_URL,
            "plugins": "fitcream",
            "attach": attach or "",
            "nonce_str": _nonce_str(str(trade_order_id)),
        }
        if settings.XUNHUPAY_RETURN_URL:
            params["return_url"] = settings.XUNHUPAY_RETURN_URL
        params["hash"] = sign_params(params, settings.XUNHUPAY_APP_SECRET)

        try:
            async with httpx.AsyncClient(timeout=20) as client:
                api_url = settings.XUNHUPAY_API_URL or _XUNHUPAY_DEFAULT_API
                resp = await client.post(api_url, json=params)
                resp.raise_for_status()
                data = resp.json()
        except Exception as e:
            logger.error("[Xunhupay] 下单请求失败: %s", e)
            raise RuntimeError(f"支付下单失败：{e}") from e

        if int(data.get("errcode", -1)) != 0:
            logger.error("[Xunhupay] 下单被拒: %s", data)
            raise RuntimeError(f"支付下单失败：{data.get('errmsg', '未知错误')}")
        return data

    def verify_notify(self, params: dict[str, Any]) -> bool:
        """回调验签：hash 字段与本地计算一致才为真。"""
        if not self.configured:
            return False
        got = params.get("hash", "")
        if not got:
            return False
        expected = sign_params(params, settings.XUNHUPAY_APP_SECRET)
        return got == expected


# 全局单例（配置读取惰性，属性实时读 settings）
payment_gateway = XunhupayGateway()
