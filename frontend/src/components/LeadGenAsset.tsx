import { useCallback, useRef, useState } from "react";

const REPORT_DATA = {
  title: "FUTURE Infrastructure Atlas — Sample Site Selection Report",
  date: "June 2026",
  content: [
    {
      heading: "Executive Summary",
      body: "This sample report demonstrates how the FUTURE Infrastructure Intelligence platform evaluates potential data center locations across three criteria: power availability, network connectivity, and water risk. The scoring methodology combines 34,936 power plant records, 1,283 submarine cable systems, and WRI Aqueduct 4.0 water risk data into a single site suitability score per 1°×1° grid cell.",
    },
    {
      heading: "Methodology",
      body: "Each grid cell receives a composite score (0–100) based on:\n\n• Power Score (40%): Weighted sum of nearby generation capacity (MW), diversity of fuel types, and proximity to HV power lines.\n• Network Score (35%): Number of submarine cable landings within 500 km, diversity of cable systems, and PeeringDB facility density.\n• Water Risk Score (25%): Inverted WRI Aqueduct overall water risk score (lower risk = higher score). Cells with extremely high water risk are penalized by 50%.\n\nScores are min-max normalized and combined using the weights above.",
    },
    {
      heading: "Top 10 Candidate Locations (Global)",
      body: "",
      table: [
        ["Rank", "Grid Cell", "Power Score", "Network Score", "Water Score", "Composite"],
        ["1", "45°N, 10°E (Northern Italy)", "88", "72", "91", "83"],
        ["2", "51°N, 0°W (Southeast England)", "76", "95", "85", "82"],
        ["3", "40°N, 75°W (New Jersey, USA)", "82", "88", "78", "81"],
        ["4", "47°N, 10°E (Switzerland/Alps)", "92", "65", "78", "79"],
        ["5", "37°N, 127°E (Seoul region, South Korea)", "85", "90", "62", "78"],
        ["6", "55°N, 12°E (Denmark/Sweden)", "90", "78", "68", "77"],
        ["7", "25°N, 55°E (UAE — Dubai region)", "74", "82", "55", "72"],
        ["8", "1°S, 37°E (Nairobi, Kenya)", "68", "45", "72", "63"],
        ["9", "-23°S, 47°E (São Paulo, Brazil)", "72", "50", "58", "61"],
        ["10", "19°N, 73°E (Mumbai, India)", "65", "60", "42", "58"],
      ],
    },
    {
      heading: "Key Insights",
      body: "1. Europe dominates the top tier due to dense power grid infrastructure, strong submarine cable connectivity, and generally low-to-moderate water stress.\n\n2. Southeast England scores highest on network connectivity (5 major cable landings within 200 km) but faces moderate water stress.\n\n3. Northern Italy benefits from hydroelectric capacity (lower water dependency from thermal plants) and growing cable landings in the Mediterranean.\n\n4. Emerging markets (Kenya, Brazil, India) show strong potential but are held back by lower power grid density and higher water risk in key regions.",
    },
    {
      heading: "Data Sources & Licensing",
      body: "• Power Plants: WRI Global Power Plant Database (CC BY 4.0)\n• Submarine Cables: KMCD Internet Infrastructure Map (to_verify) + OSM (ODbL 1.0)\n• Data Centers: PeeringDB (CC BY-SA 4.0)\n• Water Risk: WRI Aqueduct 4.0 (CC BY 4.0)\n• Power Lines & Substations: OpenStreetMap (ODbL 1.0)\n\nThis sample report is for demonstration purposes only. Actual site selection requires on-the-ground validation.",
    },
  ],
};

export default function LeadGenAsset({ onClose }: { onClose?: () => void }) {
  const [email, setEmail] = useState("");
  const [submitted, setSubmitted] = useState(false);
  const [error, setError] = useState("");
  const formRef = useRef<HTMLDivElement>(null);

  const handleSubmit = useCallback((e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    if (!email.includes("@")) {
      setError("Please enter a valid email address.");
      return;
    }
    setSubmitted(true);

    // Open report in new window for print-to-PDF
    const win = window.open("", "_blank");
    if (!win) return;

    const tableHtml = REPORT_DATA.content
      .filter((s) => s.table)
      .map(
        (s) => `
      <h2>${s.heading}</h2>
      <table>
        ${(s.table || []).map((row, ri) => `<tr>${row.map((c) => (ri === 0 ? `<th>${c}</th>` : `<td>${c}</td>`)).join("")}</tr>`).join("")}
      </table>`
      )
      .join("");

    const bodyHtml = REPORT_DATA.content
      .filter((s) => !s.table)
      .map(
        (s) => `
      <h2>${s.heading}</h2>
      ${s.body ? `<p>${s.body.replace(/\n/g, "</p><p>")}</p>` : ""}`
      )
      .join("");

    win.document.write(`
      <!DOCTYPE html>
      <html>
      <head>
        <meta charset="utf-8">
        <title>${REPORT_DATA.title}</title>
        <style>
          @page { margin: 20mm 15mm; }
          body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; color: #111; max-width: 800px; margin: 0 auto; padding: 32px; line-height: 1.6; }
          h1 { font-size: 18px; text-transform: uppercase; letter-spacing: 1px; color: #222; margin-bottom: 4px; }
          .date { font-size: 12px; color: #666; margin-bottom: 32px; }
          h2 { font-size: 14px; margin-top: 28px; margin-bottom: 8px; color: #333; border-bottom: 1px solid #ddd; padding-bottom: 4px; }
          p { font-size: 12px; margin: 0 0 12px; color: #444; }
          table { width: 100%; border-collapse: collapse; font-size: 11px; margin: 12px 0; }
          th { background: #f0f0f0; text-align: left; padding: 6px 8px; font-weight: 600; border: 1px solid #ddd; }
          td { padding: 5px 8px; border: 1px solid #ddd; }
          tr:nth-child(even) td { background: #f9f9f9; }
          .footer { margin-top: 40px; padding-top: 16px; border-top: 1px solid #ddd; font-size: 10px; color: #888; }
        </style>
      </head>
      <body>
        <h1>${REPORT_DATA.title}</h1>
        <div class="date">${REPORT_DATA.date} — Prepared for ${email}</div>
        ${bodyHtml}
        ${tableHtml}
        <div class="footer">Generated by FUTURE Infrastructure Intelligence. This is a sample report for demonstration purposes. Actual site selection requires independent verification of all data points.</div>
      </body>
      </html>
    `);
    win.document.close();
    win.focus();
  }, [email]);

  return (
    <div className="lead-gen-asset">
      <div className="lead-gen-header">
        <h2>Sample Site Selection Report</h2>
        {onClose && (
          <button className="lead-gen-close" onClick={onClose} type="button">&times;</button>
        )}
      </div>
      {!submitted ? (
        <div ref={formRef}>
          <p className="lead-gen-description">
            See how the FUTURE Intelligence Atlas evaluates global data center locations.
            This sample report scores 1° grid cells on power, network, and water risk.
          </p>
          <form onSubmit={handleSubmit} className="lead-gen-form">
            <label htmlFor="lead-email">Enter your work email to generate the report</label>
            <div className="lead-gen-input-row">
              <input
                id="lead-email"
                type="email"
                placeholder="you@company.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
              />
              <button type="submit">Download sample</button>
            </div>
            {error && <div className="lead-gen-error">{error}</div>}
          </form>
          <p className="lead-gen-note">
            No spam. This email is used only to deliver the sample report and follow up with relevant product updates.
          </p>
        </div>
      ) : (
        <div className="lead-gen-success">
          <div className="lead-gen-success-icon">&#10003;</div>
          <p>Report opened in a new tab. Use your browser's <strong>Print → Save as PDF</strong> to download.</p>
          {onClose && (
            <button className="pricing-back" onClick={onClose} type="button">← Back to map</button>
          )}
        </div>
      )}
    </div>
  );
}
