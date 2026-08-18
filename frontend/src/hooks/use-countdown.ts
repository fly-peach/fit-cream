import { useEffect, useState } from "react";

/** 验证码发送 60s 倒计时（login/profile 等共用）。 */
export function useCountdown() {
  const [countdown, setCountdown] = useState(0);

  useEffect(() => {
    if (countdown <= 0) return;
    const t = setTimeout(() => setCountdown((c) => c - 1), 1000);
    return () => clearTimeout(t);
  }, [countdown]);

  const start = (seconds: number) => setCountdown(seconds);

  return { countdown, start };
}
