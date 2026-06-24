import React, { useState, useEffect } from "react";
import axios from "axios";
import { Bar } from 'react-chartjs-2';
import { Chart as ChartJS, CategoryScale, LinearScale, BarElement, Title, Tooltip, Legend } from 'chart.js';

ChartJS.register(CategoryScale, LinearScale, BarElement, Title, Tooltip, Legend);

// Lazy load the IsometricViewer to avoid errors if Three.js is not installed
const IsometricViewer = React.lazy(() => import('../components/IsometricViewer'));

export default function UploadPage() {
  // ==================== QA STATE ====================
  const [file1, setFile1] = useState(null);
  const [file2, setFile2] = useState(null);
  const [preview1, setPreview1] = useState(null);
  const [preview2, setPreview2] = useState(null);
  const [dxfPreview1, setDxfPreview1] = useState(null);
  const [dxfPreview2, setDxfPreview2] = useState(null);
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [report, setReport] = useState(null);
  const [previewLoading1, setPreviewLoading1] = useState(false);
  const [previewLoading2, setPreviewLoading2] = useState(false);

  const [imageOptions, setImageOptions] = useState({
    annotation: true,
    changes: true,
    clash: true
  });

  const [cadOptions, setCadOptions] = useState({
    moved: true,
    modified: true,
    missing: true,
    added: true,
    clash: true,
    labels: true,
    outlinesOnly: false
  });

  const [isCadMode, setIsCadMode] = useState(false);
  const [dragging1, setDragging1] = useState(false);
  const [dragging2, setDragging2] = useState(false);

  // ==================== MTO STATE ====================
  const [activeTab, setActiveTab] = useState('qa');
  const [mtoFile, setMtoFile] = useState(null);
  const [mtoPreview, setMtoPreview] = useState(null);
  const [mtoDxfPreview, setMtoDxfPreview] = useState(null);
  const [mtoLoading, setMtoLoading] = useState(false);
  const [mtoResult, setMtoResult] = useState(null);
  const [mtoPreviewLoading, setMtoPreviewLoading] = useState(false);

  // ==================== ISOMETRIC STATE ====================
  const [isoMode, setIsoMode] = useState('upload');
  const [segments, setSegments] = useState([{ dir: 'x', length: 3, fitting: '' }]);
  const [isometricImage, setIsometricImage] = useState(null);
  const [genLoading, setGenLoading] = useState(false);
  const [isoFile, setIsoFile] = useState(null);
  const [isoPreview, setIsoPreview] = useState(null);
  const [rotation, setRotation] = useState(0);
  const [isoSegments, setIsoSegments] = useState(null);
  const [isoFittings, setIsoFittings] = useState([]);
  const [viewerError, setViewerError] = useState(null);

  // ==================== SHARED DXF PREVIEW ====================
  const fetchDxfPreview = async (file, setPreview, setLoading) => {
    if (!file || !file.name.toLowerCase().endsWith(".dxf")) return;
    setLoading(true);
    const formData = new FormData();
    formData.append("file", file);
    try {
      const res = await axios.post("http://127.0.0.1:8000/preview", formData, {
        responseType: "blob"
      });
      if (res.data && res.data.size > 0) {
        const url = URL.createObjectURL(res.data);
        setPreview(url);
      } else {
        setPreview(null);
      }
    } catch (err) {
      console.error("DXF preview failed", err);
      setPreview(null);
    } finally {
      setLoading(false);
    }
  };

  // ==================== QA LOGIC ====================
  useEffect(() => {
    if (file1 && file2) {
      const isDxf1 = file1.name.toLowerCase().endsWith(".dxf");
      const isDxf2 = file2.name.toLowerCase().endsWith(".dxf");
      setIsCadMode(isDxf1 && isDxf2);
    } else {
      setIsCadMode(false);
    }
  }, [file1, file2]);

  const runQA = async () => {
    if (!file1 || !file2) {
      alert("Please upload both files");
      return;
    }
    setLoading(true);
    setError(null);
    setResult(null);
    setReport(null);
    const formData = new FormData();
    formData.append("file1", file1);
    formData.append("file2", file2);
    const optionsToSend = isCadMode ? cadOptions : imageOptions;
    formData.append("options", JSON.stringify(optionsToSend));
    try {
      const res = await axios.post("http://127.0.0.1:8000/analyze", formData);
      setResult(res.data.image);
      setReport(res.data.report);
    } catch (err) {
      console.error(err);
      setError(err.response?.data?.detail || err.message || "Unknown error");
    } finally {
      setLoading(false);
    }
  };

  const handleFileDrop = (index, e) => {
    e.preventDefault();
    const file = e.dataTransfer.files[0];
    if (!file) return;
    if (index === 1) {
      setFile1(file);
      setPreview1(URL.createObjectURL(file));
      setDxfPreview1(null);
      if (file.name.toLowerCase().endsWith(".dxf")) {
        fetchDxfPreview(file, setDxfPreview1, setPreviewLoading1);
      }
      setDragging1(false);
    } else {
      setFile2(file);
      setPreview2(URL.createObjectURL(file));
      setDxfPreview2(null);
      if (file.name.toLowerCase().endsWith(".dxf")) {
        fetchDxfPreview(file, setDxfPreview2, setPreviewLoading2);
      }
      setDragging2(false);
    }
  };

  const handleFileSelect = (index, e) => {
    const file = e.target.files[0];
    if (!file) return;
    if (index === 1) {
      setFile1(file);
      setPreview1(URL.createObjectURL(file));
      setDxfPreview1(null);
      if (file.name.toLowerCase().endsWith(".dxf")) {
        fetchDxfPreview(file, setDxfPreview1, setPreviewLoading1);
      }
    } else {
      setFile2(file);
      setPreview2(URL.createObjectURL(file));
      setDxfPreview2(null);
      if (file.name.toLowerCase().endsWith(".dxf")) {
        fetchDxfPreview(file, setDxfPreview2, setPreviewLoading2);
      }
    }
  };

  const isDxf = (file) => file && file.name.toLowerCase().endsWith(".dxf");

  const renderPreview = (file, previewUrl, dxfPreviewUrl, isLoading) => {
    if (!file) return <p className="preview-placeholder">No file selected</p>;
    if (file.type === "application/pdf") {
      return <iframe src={previewUrl} title="PDF Preview" className="preview-iframe" />;
    }
    if (isDxf(file)) {
      if (isLoading) {
        return (
          <div className="dxf-preview">
            <div className="dxf-icon">📐</div>
            <div className="dxf-name">{file.name}</div>
            <div className="dxf-badge">⏳ Rendering preview...</div>
          </div>
        );
      }
      if (dxfPreviewUrl) {
        return <img src={dxfPreviewUrl} alt="DXF Preview" className="preview-image" />;
      }
      return (
        <div className="dxf-preview">
          <div className="dxf-icon">⚠️</div>
          <div className="dxf-name">{file.name}</div>
          <div className="dxf-badge">Preview unavailable</div>
        </div>
      );
    }
    return <img src={previewUrl} alt="Preview" className="preview-image" />;
  };

  const getChartData = () => {
    if (!report || report.identical) return null;
    if (report.moved !== undefined) {
      return {
        labels: ['Moved', 'Modified', 'Missing', 'Added', 'Clashes'],
        datasets: [{
          label: 'Count',
          data: [report.moved, report.modified, report.missing, report.added, report.clashes],
          backgroundColor: ['#FFA500', '#FF4444', '#FF3333', '#33CC55', '#CC33FF'],
          borderRadius: 8
        }]
      };
    } else {
      return {
        labels: ['Changes', 'Clashes', 'Unlabeled'],
        datasets: [{
          label: 'Count',
          data: [report.changes, report.clashes, report.annotation_missing],
          backgroundColor: ['#FFA500', '#FF4444', '#FF3333'],
          borderRadius: 8
        }]
      };
    }
  };

  const renderTable = (title, items, columns) => {
    if (!items || items.length === 0) return null;
    return (
      <div className="table-category">
        <h4>{title} ({items.length})</h4>
        <div className="table-wrapper">
          <table className="qa-table">
            <thead>
              <tr>
                {columns.map(col => <th key={col.key}>{col.label}</th>)}
              </tr>
            </thead>
            <tbody>
              {items.map((item, idx) => (
                <tr key={idx}>
                  {columns.map(col => <td key={col.key}>{item[col.key] || '-'}</td>)}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    );
  };

  // ==================== MTO LOGIC ====================
  const handleMtoFileSelect = (e) => {
    const file = e.target.files[0];
    if (!file) return;
    setMtoFile(file);
    setMtoPreview(URL.createObjectURL(file));
    setMtoDxfPreview(null);
    if (file.name.toLowerCase().endsWith(".dxf")) {
      fetchDxfPreview(file, setMtoDxfPreview, setMtoPreviewLoading);
    }
  };

  const handleMtoFileDrop = (e) => {
    e.preventDefault();
    const file = e.dataTransfer.files[0];
    if (!file) return;
    setMtoFile(file);
    setMtoPreview(URL.createObjectURL(file));
    setMtoDxfPreview(null);
    if (file.name.toLowerCase().endsWith(".dxf")) {
      fetchDxfPreview(file, setMtoDxfPreview, setMtoPreviewLoading);
    }
  };

  const runMTO = async () => {
    if (!mtoFile) {
      alert("Please upload a drawing for MTO extraction");
      return;
    }
    setMtoLoading(true);
    const formData = new FormData();
    formData.append("file", mtoFile);
    try {
      const res = await axios.post("http://127.0.0.1:8000/mto", formData);
      setMtoResult(res.data.mto);
    } catch (err) {
      console.error(err);
      alert("MTO extraction failed: " + (err.response?.data?.detail || err.message));
    } finally {
      setMtoLoading(false);
    }
  };

  // ==================== ISOMETRIC LOGIC ====================
  const addSegment = () => setSegments([...segments, { dir: 'x', length: 1, fitting: '' }]);
  const updateSegment = (idx, field, value) => {
    const newSeg = [...segments];
    newSeg[idx][field] = value;
    setSegments(newSeg);
  };
  const removeSegment = (idx) => {
    setSegments(segments.filter((_, i) => i !== idx));
  };
  const handleIsoFileSelect = (e) => {
    const file = e.target.files[0];
    if (!file) return;
    setIsoFile(file);
    setIsoPreview(URL.createObjectURL(file));
  };
  const handleIsoFileDrop = (e) => {
    e.preventDefault();
    const file = e.dataTransfer.files[0];
    if (!file) return;
    setIsoFile(file);
    setIsoPreview(URL.createObjectURL(file));
  };
  const generateIsometric = async () => {
    setViewerError(null);
    setGenLoading(true);
    try {
      const formData = new FormData();
      formData.append("rotation", rotation);
      formData.append("format", "json");
      if (isoMode === 'upload' && isoFile) {
        formData.append("file", isoFile);
      } else if (isoMode === 'manual' && segments.length > 0) {
        formData.append("segments", JSON.stringify(segments));
      } else {
        alert("Please provide either segments or a file.");
        setGenLoading(false);
        return;
      }
      const res = await axios.post("http://127.0.0.1:8000/isometric/generate", formData);
      if (res.data.segments && Array.isArray(res.data.segments)) {
        setIsoSegments(res.data.segments);
        setIsoFittings(res.data.fittings || []);
        setIsometricImage(null);
      } else {
        setIsoSegments(null);
        setIsoFittings([]);
        alert("No geometry found in the drawing");
      }
    } catch (err) {
      console.error(err);
      setViewerError(err.message);
      alert("Isometric generation failed");
    } finally {
      setGenLoading(false);
    }
  };

  const downloadPNG = async () => {
    try {
      const formData = new FormData();
      formData.append("rotation", rotation);
      formData.append("format", "png");
      if (isoMode === 'upload' && isoFile) {
        formData.append("file", isoFile);
      } else if (isoMode === 'manual' && segments.length > 0) {
        formData.append("segments", JSON.stringify(segments));
      } else {
        return;
      }
      const res = await axios.post("http://127.0.0.1:8000/isometric/generate", formData, {
        responseType: "blob"
      });
      const url = URL.createObjectURL(res.data);
      const link = document.createElement('a');
      link.href = url;
      link.download = 'isometric.png';
      link.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      console.error(err);
      alert("Download failed");
    }
  };

  // ==================== CLEANUP ====================
  useEffect(() => {
    return () => {
      if (preview1) URL.revokeObjectURL(preview1);
      if (preview2) URL.revokeObjectURL(preview2);
      if (dxfPreview1) URL.revokeObjectURL(dxfPreview1);
      if (dxfPreview2) URL.revokeObjectURL(dxfPreview2);
      if (mtoPreview) URL.revokeObjectURL(mtoPreview);
      if (mtoDxfPreview) URL.revokeObjectURL(mtoDxfPreview);
      if (isometricImage) URL.revokeObjectURL(isometricImage);
      if (isoPreview) URL.revokeObjectURL(isoPreview);
    };
  }, [preview1, preview2, dxfPreview1, dxfPreview2, mtoPreview, mtoDxfPreview, isometricImage, isoPreview]);

  // ==================== RENDER ====================
  return (
    <div className="app-layout">
      <aside className="sidebar">
        <div className="sidebar-logo">
          <img src="/logo.png" alt="PRAXSOL" />
        </div>
        <nav className="sidebar-nav">
          <button className={`nav-item ${activeTab === 'qa' ? 'active' : ''}`} onClick={() => setActiveTab('qa')}>
            <span className="nav-icon">🔍</span>
            <span>QA Analysis</span>
          </button>
          <button className={`nav-item ${activeTab === 'mto' ? 'active' : ''}`} onClick={() => setActiveTab('mto')}>
            <span className="nav-icon">📋</span>
            <span>MTO Extraction</span>
          </button>
          <button className={`nav-item ${activeTab === 'isometric' ? 'active' : ''}`} onClick={() => setActiveTab('isometric')}>
            <span className="nav-icon">📐</span>
            <span>Isometric Generator</span>
          </button>
        </nav>
      </aside>

      <main className="main-content">
        {/* ==================== QA TAB ==================== */}
        {activeTab === 'qa' && (
          <div className="dashboard">
            <header className="dashboard-header">
              <div className="header-title">
                <h1>QA Automation Module</h1>
                <p>Intelligent drawing comparison – Image, PDF & DXF</p>
              </div>
            </header>

            <div className="upload-cards">
              <div
                className={`upload-card ${dragging1 ? "drag-over" : ""}`}
                onDragOver={(e) => { e.preventDefault(); setDragging1(true); }}
                onDragLeave={() => setDragging1(false)}
                onDrop={(e) => handleFileDrop(1, e)}
              >
                <div className="upload-icon">📄</div>
                <h3>Input Drawing</h3>
                <input type="file" id="file1" accept=".png,.jpg,.jpeg,.pdf,.dxf" onChange={(e) => handleFileSelect(1, e)} style={{ display: "none" }} />
                <label htmlFor="file1" className="file-label">Choose file</label>
                <span className="file-name">{file1 ? file1.name : "or drag & drop"}</span>
              </div>

              <div
                className={`upload-card ${dragging2 ? "drag-over" : ""}`}
                onDragOver={(e) => { e.preventDefault(); setDragging2(true); }}
                onDragLeave={() => setDragging2(false)}
                onDrop={(e) => handleFileDrop(2, e)}
              >
                <div className="upload-icon">📄</div>
                <h3>Output Drawing</h3>
                <input type="file" id="file2" accept=".png,.jpg,.jpeg,.pdf,.dxf" onChange={(e) => handleFileSelect(2, e)} style={{ display: "none" }} />
                <label htmlFor="file2" className="file-label">Choose file</label>
                <span className="file-name">{file2 ? file2.name : "or drag & drop"}</span>
              </div>
            </div>

            {(preview1 || preview2) && (
              <div className="preview-grid">
                <div className="preview-card">
                  <h3>Input Preview</h3>
                  {renderPreview(file1, preview1, dxfPreview1, previewLoading1)}
                </div>
                <div className="preview-card">
                  <h3>Output Preview</h3>
                  {renderPreview(file2, preview2, dxfPreview2, previewLoading2)}
                </div>
              </div>
            )}

            {file1 && file2 && (
              <div className="options-panel">
                <h3>{isCadMode ? "CAD Analysis Options" : "Image / PDF Analysis Options"}</h3>
                <div className="options-grid">
                  {!isCadMode ? (
                    <>
                      <label className="checkbox-label">
                        <input type="checkbox" checked={imageOptions.annotation} onChange={() => setImageOptions({ ...imageOptions, annotation: !imageOptions.annotation })} />
                        <span>Annotation</span>
                      </label>
                      <label className="checkbox-label">
                        <input type="checkbox" checked={imageOptions.changes} onChange={() => setImageOptions({ ...imageOptions, changes: !imageOptions.changes })} />
                        <span>Changes</span>
                      </label>
                      <label className="checkbox-label">
                        <input type="checkbox" checked={imageOptions.clash} onChange={() => setImageOptions({ ...imageOptions, clash: !imageOptions.clash })} />
                        <span>Clash</span>
                      </label>
                    </>
                  ) : (
                    <>
                      <label><input type="checkbox" checked={cadOptions.moved} onChange={() => setCadOptions({ ...cadOptions, moved: !cadOptions.moved })} /> Moved</label>
                      <label><input type="checkbox" checked={cadOptions.modified} onChange={() => setCadOptions({ ...cadOptions, modified: !cadOptions.modified })} /> Modified</label>
                      <label><input type="checkbox" checked={cadOptions.missing} onChange={() => setCadOptions({ ...cadOptions, missing: !cadOptions.missing })} /> Missing</label>
                      <label><input type="checkbox" checked={cadOptions.added} onChange={() => setCadOptions({ ...cadOptions, added: !cadOptions.added })} /> Added</label>
                      <label><input type="checkbox" checked={cadOptions.clash} onChange={() => setCadOptions({ ...cadOptions, clash: !cadOptions.clash })} /> Clashes</label>
                      <label><input type="checkbox" checked={cadOptions.labels} onChange={() => setCadOptions({ ...cadOptions, labels: !cadOptions.labels })} /> Labels</label>
                      <label><input type="checkbox" checked={cadOptions.outlinesOnly} onChange={() => setCadOptions({ ...cadOptions, outlinesOnly: !cadOptions.outlinesOnly })} /> Outlines Only</label>
                    </>
                  )}
                </div>
              </div>
            )}

            <button className="qa-button" onClick={runQA} disabled={loading}>
              {loading ? <span className="spinner"></span> : "Run QA Analysis"}
            </button>

            {error && <div className="error-message">{error}</div>}

            {result && (
              <div className="result-section">
                <h2>QA Result</h2>
                <img src={result} alt="QA Result" className="result-image" />
              </div>
            )}

            {report && (
              <div className="report-section">
                <h3>QA Report</h3>
                {report.identical && <p className="success-message">✅ No differences detected. The two drawings are identical.</p>}
                {!report.identical && !report.error && (
                  <>
                    <div className="report-stats">
                      {report.moved !== undefined ? (
                        <>
                          <div className="stat-card">Moved: {report.moved}</div>
                          <div className="stat-card">Modified: {report.modified}</div>
                          <div className="stat-card">Missing: {report.missing}</div>
                          <div className="stat-card">Added: {report.added}</div>
                          <div className="stat-card">Clashes: {report.clashes}</div>
                        </>
                      ) : (
                        <>
                          <div className="stat-card">Changes: {report.changes}</div>
                          <div className="stat-card">Clashes: {report.clashes}</div>
                          <div className="stat-card">Unlabeled: {report.annotation_missing}</div>
                        </>
                      )}
                    </div>

                    {getChartData() && (
                      <div className="chart-container">
                        <Bar data={getChartData()} options={{ responsive: true, maintainAspectRatio: true, plugins: { legend: { position: 'top' } } }} />
                      </div>
                    )}

                    {report.moved !== undefined && report.details ? (
                      <div className="report-tables">
                        {renderTable("📌 Moved Entities", report.details.moved, [
                          { key: "type", label: "Type" },
                          { key: "label", label: "Label" },
                          { key: "layer", label: "Layer" },
                          { key: "change_description", label: "Change Description" },
                          { key: "position", label: "New Position" }
                        ])}
                        {renderTable("🔧 Modified Entities", report.details.modified, [
                          { key: "type", label: "Type" },
                          { key: "label", label: "Label" },
                          { key: "layer", label: "Layer" },
                          { key: "change_description", label: "Change Description" },
                          { key: "position", label: "Position" }
                        ])}
                        {renderTable("❌ Missing Entities", report.details.missing, [
                          { key: "type", label: "Type" },
                          { key: "label", label: "Label" },
                          { key: "layer", label: "Layer" },
                          { key: "position", label: "Position" }
                        ])}
                        {renderTable("➕ Added Entities", report.details.added, [
                          { key: "type", label: "Type" },
                          { key: "label", label: "Label" },
                          { key: "layer", label: "Layer" },
                          { key: "position", label: "Position" }
                        ])}
                        {renderTable("⚡ Clashes", report.details.clashes, [
                          { key: "type", label: "Types" },
                          { key: "label", label: "Description" },
                          { key: "layer", label: "Layer" },
                          { key: "position", label: "Position" }
                        ])}
                      </div>
                    ) : (
                      report.details && (
                        <details className="report-details">
                          <summary>View detailed list</summary>
                          <div className="detail-list">
                            {report.details.moved?.length > 0 && <div><strong>Moved:</strong><ul>{report.details.moved.map((d, i) => <li key={i}>{d}</li>)}</ul></div>}
                            {report.details.modified?.length > 0 && <div><strong>Modified:</strong><ul>{report.details.modified.map((d, i) => <li key={i}>{d}</li>)}</ul></div>}
                            {report.details.missing?.length > 0 && <div><strong>Missing:</strong><ul>{report.details.missing.map((d, i) => <li key={i}>{d}</li>)}</ul></div>}
                            {report.details.added?.length > 0 && <div><strong>Added:</strong><ul>{report.details.added.map((d, i) => <li key={i}>{d}</li>)}</ul></div>}
                            {report.details.clashes?.length > 0 && <div><strong>Clashes:</strong><ul>{report.details.clashes.map((d, i) => <li key={i}>{d}</li>)}</ul></div>}
                          </div>
                        </details>
                      )
                    )}
                  </>
                )}
                {report.error && <p className="error-message">Error: {report.error}</p>}
              </div>
            )}
          </div>
        )}

        {/* ==================== MTO TAB ==================== */}
        {activeTab === 'mto' && (
          <div className="dashboard">
            <header className="dashboard-header">
              <div className="header-title">
                <h1>Material Take-Off (MTO)</h1>
                <p>Extract bill of materials from a single drawing – DXF, PDF, Image</p>
              </div>
            </header>

            <div className="upload-cards">
              <div
                className="upload-card"
                onDragOver={(e) => e.preventDefault()}
                onDrop={handleMtoFileDrop}
              >
                <div className="upload-icon">📦</div>
                <h3>Drawing for MTO</h3>
                <input
                  type="file"
                  id="mtoFile"
                  accept=".png,.jpg,.jpeg,.pdf,.dxf"
                  onChange={handleMtoFileSelect}
                  style={{ display: "none" }}
                />
                <label htmlFor="mtoFile" className="file-label">Choose file</label>
                <span className="file-name">{mtoFile ? mtoFile.name : "or drag & drop"}</span>
              </div>
            </div>

            {mtoPreview && (
              <div className="preview-grid">
                <div className="preview-card">
                  <h3>Preview</h3>
                  {renderPreview(mtoFile, mtoPreview, mtoDxfPreview, mtoPreviewLoading)}
                </div>
              </div>
            )}

            <button
              className="qa-button"
              onClick={runMTO}
              disabled={mtoLoading}
              style={{ background: '#0B5E2E' }}
            >
              {mtoLoading ? <span className="spinner"></span> : "Extract MTO"}
            </button>

            {mtoResult && (
              <div className="report-section">
                <h3>📦 Material Take-Off Results</h3>
                <div className="table-wrapper">
                  <table className="qa-table">
                    <thead>
                      <tr>
                        <th>Type</th>
                        <th>Layer</th>
                        <th>Size</th>
                        <th>Schedule</th>
                        <th>Material</th>
                        <th>Quantity</th>
                        <th>Total Length</th>
                        <th>Description</th>
                      </tr>
                    </thead>
                    <tbody>
                      {mtoResult.map((item, idx) => (
                        <tr key={idx}>
                          <td>{item.type}</td>
                          <td>{item.layer}</td>
                          <td>{item.size || '-'}</td>
                          <td>{item.schedule || '-'}</td>
                          <td>{item.material || '-'}</td>
                          <td>{item.quantity}</td>
                          <td>{item.total_length > 0 ? item.total_length : '-'}</td>
                          <td>{item.description}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </div>
        )}

        {/* ==================== ISOMETRIC TAB ==================== */}
        {activeTab === 'isometric' && (
          <div className="dashboard">
            <header className="dashboard-header">
              <div className="header-title">
                <h1>Smart Isometric Generator</h1>
                <p>Upload a DXF file or define manual segments</p>
              </div>
            </header>

            <div className="options-panel" style={{ marginBottom: '1.5rem' }}>
              <div style={{ display: 'flex', gap: '1rem', justifyContent: 'center' }}>
                <button
                  className={`file-label ${isoMode === 'upload' ? 'active' : ''}`}
                  onClick={() => {
                    setIsoMode('upload');
                    setIsometricImage(null);
                    setIsoSegments(null);
                    setIsoFittings([]);
                    setIsoFile(null);
                    setIsoPreview(null);
                  }}
                  style={{
                    background: isoMode === 'upload' ? '#1E88E5' : '#4b5563',
                    margin: 0,
                  }}
                >
                  📤 Upload DXF
                </button>
                <button
                  className={`file-label ${isoMode === 'manual' ? 'active' : ''}`}
                  onClick={() => {
                    setIsoMode('manual');
                    setIsometricImage(null);
                    setIsoSegments(null);
                    setIsoFittings([]);
                    setSegments([{ dir: 'x', length: 3, fitting: '' }]);
                  }}
                  style={{
                    background: isoMode === 'manual' ? '#1E88E5' : '#4b5563',
                    margin: 0,
                  }}
                >
                  ✏️ Manual Input
                </button>
              </div>
            </div>

            {isoMode === 'upload' && (
              <div className="upload-cards">
                <div
                  className="upload-card"
                  onDragOver={(e) => e.preventDefault()}
                  onDrop={handleIsoFileDrop}
                >
                  <div className="upload-icon">📄</div>
                  <h3>Upload 3D DXF</h3>
                  <input
                    type="file"
                    id="isoFile"
                    accept=".dxf"
                    onChange={handleIsoFileSelect}
                    style={{ display: "none" }}
                  />
                  <label htmlFor="isoFile" className="file-label">Choose file</label>
                  <span className="file-name">{isoFile ? isoFile.name : "or drag & drop"}</span>
                </div>
              </div>
            )}

            {isoMode === 'manual' && (
              <div className="options-panel">
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
                  <h3 style={{ margin: 0 }}>Pipe Route</h3>
                  <div>
                    <button onClick={() => setSegments([{ dir: 'x', length: 3, fitting: '' }])} className="file-label" style={{ background: '#dc2626', marginRight: '0.5rem' }}>
                      Clear All
                    </button>
                    <button onClick={addSegment} className="file-label" style={{ background: '#4b5563' }}>
                      + Add Segment
                    </button>
                  </div>
                </div>

                {segments.map((seg, idx) => (
                  <div key={idx} style={{ display: 'flex', gap: '10px', marginBottom: '10px', alignItems: 'center', flexWrap: 'wrap', background: '#f8fafc', padding: '10px', borderRadius: '8px' }}>
                    <span style={{ fontWeight: 'bold', minWidth: '30px' }}>{idx + 1}.</span>
                    <select value={seg.dir} onChange={(e) => updateSegment(idx, 'dir', e.target.value)} style={{ padding: '4px 8px' }}>
                      <option value="x">X (right)</option>
                      <option value="y">Y (up-left)</option>
                      <option value="z">Z (up)</option>
                    </select>
                    <input
                      type="number"
                      value={seg.length}
                      onChange={(e) => updateSegment(idx, 'length', parseFloat(e.target.value))}
                      step="0.5"
                      style={{ width: '80px', padding: '4px 8px' }}
                    />
                    <select value={seg.fitting} onChange={(e) => updateSegment(idx, 'fitting', e.target.value)} style={{ padding: '4px 8px' }}>
                      <option value="">None</option>
                      <option value="elbow">Elbow</option>
                      <option value="flange">Flange</option>
                    </select>
                    {segments.length > 1 && (
                      <button onClick={() => removeSegment(idx)} style={{ background: '#dc2626', color: 'white', border: 'none', borderRadius: '20px', padding: '4px 12px', cursor: 'pointer' }}>
                        ✖
                      </button>
                    )}
                  </div>
                ))}

                <div style={{ marginTop: '1rem', padding: '0.5rem', background: '#f1f5f9', borderRadius: '8px' }}>
                  <small>
                    <strong>Tip:</strong> Use negative lengths to go backwards. Add fittings (elbow, flange) at segment ends.
                  </small>
                </div>
              </div>
            )}

            <button className="qa-button" onClick={generateIsometric} disabled={genLoading}>
              {genLoading ? <span className="spinner"></span> : "Generate 3D View"}
            </button>

            {isoSegments && Array.isArray(isoSegments) && isoSegments.length>0 && (
              <div className="result-section">
                <h3>3D View – Click & Drag to Rotate</h3>
                <React.Suspense fallback={<div style={{ height: '600px', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>Loading 3D viewer...</div>}>
                  <IsometricViewer segments={isoSegments} fittings={isoFittings} />
                </React.Suspense>
                <div style={{ marginTop: '0.5rem', display: 'flex', gap: '1rem', justifyContent: 'center' }}>
                  <button
                    onClick={downloadPNG}
                    className="file-label"
                    style={{ background: '#0B5E2E' }}
                  >
                    Download PNG
                  </button>
                  <button
                    onClick={() => {
                      setIsoSegments(null);
                      setIsoFittings([]);
                      setIsometricImage(null);
                      setIsoFile(null);
                      setIsoPreview(null);
                      setSegments([{ dir: 'x', length: 3, fitting: '' }]);
                      setRotation(0);
                    }}
                    className="file-label"
                    style={{ background: '#dc2626' }}
                  >
                    Clear All
                  </button>
                </div>
              </div>
            )}

            {isometricImage && !isoSegments && (
              <div className="result-section">
                <h3>Generated Isometric Drawing</h3>
                <img src={isometricImage} alt="Isometric" className="result-image" />
                <div style={{ marginTop: '0.5rem', display: 'flex', gap: '1rem', justifyContent: 'center' }}>
                  <button
                    onClick={() => {
                      const link = document.createElement('a');
                      link.href = isometricImage;
                      link.download = 'isometric.png';
                      link.click();
                    }}
                    className="file-label"
                    style={{ background: '#0B5E2E' }}
                  >
                    Download PNG
                  </button>
                  <button
                    onClick={() => {
                      setIsometricImage(null);
                      setIsoFile(null);
                      setIsoPreview(null);
                      setSegments([{ dir: 'x', length: 3, fitting: '' }]);
                      setRotation(0);
                    }}
                    className="file-label"
                    style={{ background: '#dc2626' }}
                  >
                    Clear All
                  </button>
                </div>
              </div>
            )}
          </div>
        )}
      </main>
    </div>
  );
}