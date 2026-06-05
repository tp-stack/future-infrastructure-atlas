import { useCallback, useEffect, useState } from "react";
import { commercialApiRequest, type CommercialApiConfig } from "../api/commercialApi";

interface UsageData {
  customer_id: string;
  plan_key: string;
  monthly_request_quota: number;
  monthly_requests_used: number;
  monthly_export_quota_mb: number;
}

const STORAGE_API_KEY = "commercial-api-key";
const STORAGE_BASE_URL = "commercial-api-base-url";
const DEFAULT_BASE_URL = "http://127.0.0.1:8000";

export default function UsageMeter() {
  const [usage, setUsage] = useState<UsageData | null>(null);
  const [loading, setLoading] = useState(false);

  const fetchUsage = useCallback(async () => {
    const apiKey = sessionStorage.getItem(STORAGE_API_KEY);
    if (!apiKey) {
      setUsage(null);
      return;
    }
    setLoading(true);
    const config: CommercialApiConfig = {
      baseUrl: sessionStorage.getItem(STORAGE_BASE_URL) || DEFAULT_BASE_URL,
      apiKey,
    };
    const result = await commercialApiRequest<UsageData>(config, "/v1/billing/usage");
    setLoading(false);
    if (result.ok && result.data) {
      setUsage(result.data);
    }
  }, []);

  useEffect(() => {
    fetchUsage();
    const interval = setInterval(fetchUsage, 60000);
    return () => clearInterval(interval);
  }, [fetchUsage]);

  if (!usage) return null;

  const pct = usage.monthly_request_quota > 0
    ? Math.min(100, Math.round((usage.monthly_requests_used / usage.monthly_request_quota) * 100))
    : 0;

  const isExhausted = pct >= 100;
  const isWarning = pct >= 80 && !isExhausted;

  return (
    <a href="/?pricing=1" className={`usage-meter ${isExhausted ? "usage-meter--exhausted" : isWarning ? "usage-meter--warning" : ""}`} title={`${usage.monthly_requests_used.toLocaleString()} / ${usage.monthly_request_quota.toLocaleString()} requests used`}>
      <span className="usage-meter-label">{usage.plan_key}</span>
      <span className="usage-meter-bar">
        <span className="usage-meter-fill" style={{ width: `${pct}%` }} />
      </span>
      <span className="usage-meter-pct">{pct}%</span>
      {isExhausted && <span className="usage-meter-cta">Quota exceeded — upgrade</span>}
    </a>
  );
}
