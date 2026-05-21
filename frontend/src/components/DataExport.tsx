import type { AtlasData, FilterState } from "../map/types";
import { exportCSV, exportGeoJSON } from "../utils/export";

interface Props {
  data: AtlasData;
  filters: FilterState;
}

export default function DataExport({ data, filters }: Props) {
  return (
    <div className="panel-section">
      <h2>Export</h2>
      <div className="export-group">
        <span className="export-label">Power plants</span>
        <div className="export-buttons">
          <button className="export-btn" onClick={() => exportCSV(data, filters, "power_plants")}>CSV</button>
          <button className="export-btn" onClick={() => exportGeoJSON(data, filters, "power_plants")}>GeoJSON</button>
        </div>
      </div>
      <div className="export-group">
        <span className="export-label">Cables</span>
        <div className="export-buttons">
          <button className="export-btn" onClick={() => exportCSV(data, filters, "cables")}>CSV</button>
          <button className="export-btn" onClick={() => exportGeoJSON(data, filters, "cables")}>GeoJSON</button>
        </div>
      </div>
      <div className="export-group">
        <span className="export-label">Data centers</span>
        <div className="export-buttons">
          <button className="export-btn" onClick={() => exportCSV(data, filters, "data_centers")}>CSV</button>
          <button className="export-btn" onClick={() => exportGeoJSON(data, filters, "data_centers")}>GeoJSON</button>
        </div>
      </div>
      <div className="export-group">
        <span className="export-label">All layers</span>
        <div className="export-buttons">
          <button className="export-btn" onClick={() => exportCSV(data, filters, "all")}>CSV</button>
          <button className="export-btn" onClick={() => exportGeoJSON(data, filters, "all")}>GeoJSON</button>
        </div>
      </div>
    </div>
  );
}
