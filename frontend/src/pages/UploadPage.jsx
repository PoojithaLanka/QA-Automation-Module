import React, { useState, useEffect } from "react";
import axios from "axios";

export default function UploadPage() {
  const [file1, setFile1] = useState(null);
  const [file2, setFile2] = useState(null);
  const [preview1, setPreview1] = useState(null);
  const [preview2, setPreview2] = useState(null);
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

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

    const formData = new FormData();
    formData.append("file1", file1);
    formData.append("file2", file2);
    const optionsToSend = isCadMode ? cadOptions : imageOptions;
    formData.append("options", JSON.stringify(optionsToSend));

    try {
      const res = await axios.post("http://127.0.0.1:8000/analyze", formData);
      setResult(res.data.image);
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
    if (index === 1) {
      setFile1(file);
      setPreview1(URL.createObjectURL(file));
    } else {
      setFile2(file);
      setPreview2(URL.createObjectURL(file));
    }
    if (index === 1) setDragging1(false);
    else setDragging2(false);
  };

  const handleFileSelect = (index, e) => {
    const file = e.target.files[0];
    if (index === 1) {
      setFile1(file);
      if (file) setPreview1(URL.createObjectURL(file));
    } else {
      setFile2(file);
      if (file) setPreview2(URL.createObjectURL(file));
    }
  };

  const isDxf = (file) => file && file.name.toLowerCase().endsWith(".dxf");

  const renderPreview = (file, previewUrl) => {
    if (!file) return <p className="preview-placeholder">No file selected</p>;
    if (file.type === "application/pdf") {
      return (
        <iframe
          src={previewUrl}
          title="PDF Preview"
          className="preview-iframe"
        />
      );
    }
    if (isDxf(file)) {
      return (
        <div className="dxf-preview">
          <div className="dxf-icon">📐</div>
          <div className="dxf-name">{file.name}</div>
          <div className="dxf-badge">DXF file – CAD engine</div>
        </div>
      );
    }
    return (
      <img
        src={previewUrl}
        alt="Preview"
        className="preview-image"
      />
    );
  };

  return (
    <div className="dashboard">
      {/* Header with logo */}
      <header className="dashboard-header">
        <img src="/logo.png" alt="PRAXSOL" className="logo" />
        <div className="header-title">
          <h1>QA Automation Module</h1>
          <p>Intelligent drawing comparison – Image, PDF & DXF</p>
        </div>
      </header>

      {/* Upload Cards */}
      <div className="upload-cards">
        <div
          className={`upload-card ${dragging1 ? "drag-over" : ""}`}
          onDragOver={(e) => { e.preventDefault(); setDragging1(true); }}
          onDragLeave={() => setDragging1(false)}
          onDrop={(e) => handleFileDrop(1, e)}
        >
          <div className="upload-icon">📄</div>
          <h3>Input Drawing</h3>
          <input
            type="file"
            id="file1"
            accept=".png,.jpg,.jpeg,.pdf,.dxf"
            onChange={(e) => handleFileSelect(1, e)}
            style={{ display: "none" }}
          />
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
          <input
            type="file"
            id="file2"
            accept=".png,.jpg,.jpeg,.pdf,.dxf"
            onChange={(e) => handleFileSelect(2, e)}
            style={{ display: "none" }}
          />
          <label htmlFor="file2" className="file-label">Choose file</label>
          <span className="file-name">{file2 ? file2.name : "or drag & drop"}</span>
        </div>
      </div>

      {/* Preview Section */}
      {(preview1 || preview2) && (
        <div className="preview-grid">
          <div className="preview-card">
            <h3>Input Preview</h3>
            {renderPreview(file1, preview1)}
          </div>
          <div className="preview-card">
            <h3>Output Preview</h3>
            {renderPreview(file2, preview2)}
          </div>
        </div>
      )}

      {/* Options Panel */}
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

      {/* Action Button */}
      <button className="qa-button" onClick={runQA} disabled={loading}>
        {loading ? (
          <span className="spinner"></span>
        ) : (
          "Run QA Analysis"
        )}
      </button>

      {error && <div className="error-message">{error}</div>}

      {result && (
        <div className="result-section">
          <h2>QA Result</h2>
          <img src={result} alt="QA Result" className="result-image" />
        </div>
      )}
    </div>
  );
}