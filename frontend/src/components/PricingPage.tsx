import { useCallback, useState } from "react";
import {
  type CheckoutSessionResponse,
  type CommercialApiConfig,
  commercialApiRequest,
} from "../api/commercialApi";

interface PricingTier {
  key: "launch" | "scale" | "enterprise";
  name: string;
  price: string;
  cadence: string;
  audience: string;
  included: string[];
  extraction: string;
  overage: string;
}

const PRICING_TIERS: PricingTier[] = [
  {
    key: "launch",
    name: "Launch",
    price: "$299",
    cadence: "per month",
    audience: "Prototype users and small research teams",
    included: ["25k API requests", "500k tile requests", "5 exports up to 50k rows each", "CSV and GeoJSON exports"],
    extraction: "$49 per extra extraction",
    overage: "$0.002 per additional record",
  },
  {
    key: "scale",
    name: "Scale",
    price: "$1,250",
    cadence: "per month",
    audience: "Commercial teams building recurring workflows",
    included: ["250k API requests", "5M tile requests", "50 exports up to 500k rows each", "CSV, GeoJSON, and Parquet exports"],
    extraction: "$149 per extra extraction",
    overage: "$0.001 per additional record",
  },
  {
    key: "enterprise",
    name: "Enterprise",
    price: "$4,900+",
    cadence: "per month",
    audience: "Data resale, model enrichment, and bulk procurement",
    included: ["2M API requests", "50M tile requests", "500 exports with negotiated caps", "Dedicated commercial rights review"],
    extraction: "Custom bulk extraction pricing",
    overage: "Contracted usage bands",
  },
];

interface Props {
  onClose?: () => void;
  baseUrl?: string;
  checkoutSuccess?: { sessionId: string; plan: string } | null;
  checkoutCancelled?: boolean;
}

export default function PricingPage({ onClose, baseUrl, checkoutSuccess, checkoutCancelled }: Props) {
  const [email, setEmail] = useState("");
  const [checkoutMessage, setCheckoutMessage] = useState("");
  const [busy, setBusy] = useState(false);

  const startCheckout = useCallback(async (tier: PricingTier) => {
    if (!email.includes("@")) {
      setCheckoutMessage("Please enter a valid email address.");
      return;
    }
    setCheckoutMessage("");
    setBusy(true);
    const config: CommercialApiConfig = { baseUrl: baseUrl || "http://127.0.0.1:8000", apiKey: "" };
    const result = await commercialApiRequest<CheckoutSessionResponse>(config, "/v1/billing/checkout", {
      method: "POST",
      apiKeyRequired: false,
      body: { plan: tier.key, email },
    });
    setBusy(false);
    if (result.ok && result.data?.checkout_url) {
      window.location.href = result.data.checkout_url;
      return;
    }
    setCheckoutMessage(result.error?.message || `Checkout could not start for ${tier.name}.`);
  }, [baseUrl, email]);

  if (checkoutSuccess) {
    return (
      <div className="pricing-page">
        <div className="pricing-header">
          <h1>Subscription confirmed</h1>
          <p className="pricing-subtitle">
            Your <strong>{checkoutSuccess.plan}</strong> plan is active.
          </p>
        </div>
        <div className="pricing-success">
          <div className="pricing-success-icon">&#10003;</div>
          <p>
            Your API key has been generated and will be sent to the email address
            you provided. Check your inbox within the next few minutes.
          </p>
          <div className="pricing-success-details">
            <h3>What happens next?</h3>
            <ul>
              <li>You'll receive an email with your API key (format: <code>fia_...</code>)</li>
              <li>Use the key in the <code>X-API-Key</code> header of your API requests</li>
              <li>Visit the <strong>Enterprise Dashboard</strong> to test endpoints and manage usage</li>
            </ul>
          </div>
          {onClose && (
            <button className="pricing-back" onClick={onClose} type="button">
              ← Back to map
            </button>
          )}
        </div>
      </div>
    );
  }

  if (checkoutCancelled) {
    return (
      <div className="pricing-page">
        <div className="pricing-header">
          <h1>Checkout cancelled</h1>
          <p className="pricing-subtitle">No charges were made. You can try again whenever you're ready.</p>
          <button className="pricing-back" onClick={() => { window.location.href = "/?pricing=1"; }} type="button">
            ← Back to plans
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="pricing-page">
      <div className="pricing-header">
        <h1>FUTURE Intelligence API</h1>
        <p className="pricing-subtitle">Recurring API access plus metered extraction. No hidden fees.</p>
        {onClose && (
          <button className="pricing-back" onClick={onClose} type="button">
            ← Back to map
          </button>
        )}
      </div>

      <div className="pricing-email-bar">
        <label htmlFor="pricing-email">Work email for API key delivery</label>
        <input
          id="pricing-email"
          type="email"
          placeholder="you@company.com"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required
        />
      </div>

      <div className="pricing-grid">
        {PRICING_TIERS.map((tier) => (
          <article className={`pricing-card pricing-card--${tier.key}`} key={tier.key}>
            <div className="pricing-card-top">
              <span className="pricing-card-name">{tier.name}</span>
              <strong className="pricing-card-price">{tier.price}</strong>
              <em className="pricing-card-cadence">{tier.cadence}</em>
            </div>
            <p className="pricing-card-audience">{tier.audience}</p>
            <ul className="pricing-card-features">
              {tier.included.map((item) => <li key={item}>{item}</li>)}
            </ul>
            <div className="pricing-card-meter">
              <span>{tier.extraction}</span>
              <small>{tier.overage}</small>
            </div>
            <button
              className="pricing-card-btn"
              type="button"
              disabled={busy}
              onClick={() => startCheckout(tier)}
            >
              {busy ? "Redirecting to Stripe..." : "Start checkout"}
            </button>
          </article>
        ))}
      </div>

      {checkoutMessage && <div className="pricing-note">{checkoutMessage}</div>}

      <div className="pricing-faq">
        <h2>Frequently asked</h2>
        <dl>
          <dt>What happens after checkout?</dt>
          <dd>Your API key is provisioned within 60 seconds of successful payment. You'll receive it at the email you provided.</dd>
          <dt>Can I upgrade or downgrade?</dt>
          <dd>Yes. Contact us to switch plans mid-cycle. Credits are applied prorated.</dd>
          <dt>Is there a free trial?</dt>
          <dd>Not yet. Email us for a guided demo and we'll set up temporary access.</dd>
          <dt>What data licenses are included?</dt>
          <dd>Each plan includes commercial use of all open-license datasets (WRI, OSM, Epoch AI, PeeringDB). Third-party licensed data (TeleGeography) is excluded unless separately negotiated.</dd>
        </dl>
      </div>
    </div>
  );
}
