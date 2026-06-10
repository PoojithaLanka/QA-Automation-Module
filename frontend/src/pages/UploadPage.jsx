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

  // Default options for image/PDF pipeline
  const [imageOptions, setImageOptions] = useState({
    annotation: true,
    changes: true,
    clash: true
  });

  // Default options for CAD pipeline
  const [cadOptions, setCadOptions] = useState({
    moved: true,
    modified: true,
    missing: true,
    added: true,
    clash: true,
    labels: true,
    outlinesOnly: false
  });

  // Determine which pipeline based on file extensions
  const [isCadMode, setIsCadMode] = useState(false);

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
    // Send the appropriate options based on mode
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

  const isDxf = (file) => file && file.name.toLowerCase().endsWith(".dxf");

  const renderPreview = (file, previewUrl) => {
    if (!file) return <p>No file selected</p>;
    if (file.type === "application/pdf") {
      return (
        <iframe
          src={previewUrl}
          title="PDF Preview"
          style={{ width: "100%", height: "500px", border: "1px solid #ccc" }}
        />
      );
    }
    if (isDxf(file)) {
      return (
        <div style={{
          background: "#2a2a2a",
          borderRadius: "8px",
          padding: "20px",
          textAlign: "center",
          border: "1px solid #555",
          minHeight: "200px",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center"
        }}>
          <div style={{ fontSize: "48px", marginBottom: "10px" }}>📐</div>
          <div style={{ fontWeight: "bold", marginBottom: "5px" }}>{file.name}</div>
          <div style={{ fontSize: "12px", marginTop: "10px", color: "#ffaa44" }}>
            DXF file – processed by CAD engine
          </div>
        </div>
      );
    }
    return (
      <img
        src={previewUrl}
        alt="Preview"
        style={{ width: "100%", maxHeight: "500px", objectFit: "contain", border: "1px solid #ccc" }}
      />
    );
  };

  return (
    <div className="dashboard" style={{ padding: "20px", width: "100%" }}>
      <h2>QA Automation Module</h2>

      {/* FILE UPLOADS */}
      <div style={{ marginBottom: "10px" }}>
        <input
          type="file"
          accept=".png,.jpg,.jpeg,.pdf,.dxf"
          onChange={(e) => {
            const file = e.target.files[0];
            setFile1(file);
            if (file) setPreview1(URL.createObjectURL(file));
          }}
        />
      </div>
      <div style={{ marginBottom: "20px" }}>
        <input
          type="file"
          accept=".png,.jpg,.jpeg,.pdf,.dxf"
          onChange={(e) => {
            const file = e.target.files[0];
            setFile2(file);
            if (file) setPreview2(URL.createObjectURL(file));
          }}
        />
      </div>

      {/* PREVIEW SECTION */}
      {(preview1 || preview2) && (
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "20px", marginBottom: "30px" }}>
          <div>
            <h3>Input Drawing</h3>
            {renderPreview(file1, preview1)}
          </div>
          <div>
            <h3>Output Drawing</h3>
            {renderPreview(file2, preview2)}
          </div>
        </div>
      )}

      {/* DYNAMIC OPTIONS BASED ON FILE TYPE */}
      {file1 && file2 && (
        <div style={{ marginBottom: "20px" }}>
          <h3>{isCadMode ? "CAD Analysis Options" : "Image/PDF Analysis Options"}</h3>
          {!isCadMode ? (
            // Image/PDF options (original three)
            <div>
              <label style={{ marginRight: "20px" }}>
                <input
                  type="checkbox"
                  checked={imageOptions.annotation}
                  onChange={() => setImageOptions({ ...imageOptions, annotation: !imageOptions.annotation })}
                /> Annotation
              </label>
              <label style={{ marginRight: "20px" }}>
                <input
                  type="checkbox"
                  checked={imageOptions.changes}
                  onChange={() => setImageOptions({ ...imageOptions, changes: !imageOptions.changes })}
                /> Changes
              </label>
              <label>
                <input
                  type="checkbox"
                  checked={imageOptions.clash}
                  onChange={() => setImageOptions({ ...imageOptions, clash: !imageOptions.clash })}
                /> Clash
              </label>
            </div>
          ) : (
            // CAD options (fine-grained)
            <div style={{ display: "grid", gridTemplateColumns: "repeat(4, auto)", gap: "10px", justifyContent: "center" }}>
              <label><input type="checkbox" checked={cadOptions.moved} onChange={() => setCadOptions({ ...cadOptions, moved: !cadOptions.moved })} /> Show Moved</label>
              <label><input type="checkbox" checked={cadOptions.modified} onChange={() => setCadOptions({ ...cadOptions, modified: !cadOptions.modified })} /> Show Modified</label>
              <label><input type="checkbox" checked={cadOptions.missing} onChange={() => setCadOptions({ ...cadOptions, missing: !cadOptions.missing })} /> Show Missing</label>
              <label><input type="checkbox" checked={cadOptions.added} onChange={() => setCadOptions({ ...cadOptions, added: !cadOptions.added })} /> Show Added</label>
              <label><input type="checkbox" checked={cadOptions.clash} onChange={() => setCadOptions({ ...cadOptions, clash: !cadOptions.clash })} /> Show Clashes</label>
              <label><input type="checkbox" checked={cadOptions.labels} onChange={() => setCadOptions({ ...cadOptions, labels: !cadOptions.labels })} /> Show Labels</label>
              <label><input type="checkbox" checked={cadOptions.outlinesOnly} onChange={() => setCadOptions({ ...cadOptions, outlinesOnly: !cadOptions.outlinesOnly })} /> Outlines Only</label>
            </div>
          )}
        </div>
      )}

      <button onClick={runQA} disabled={loading}>
        {loading ? "Processing..." : "Run QA"}
      </button>

      {loading && <p style={{ color: "orange" }}>Processing drawing... please wait</p>}
      {error && <p style={{ color: "red" }}>Error: {error}</p>}

      {result && (
        <div style={{ marginTop: "40px" }}>
          <h2>QA Result</h2>
          <img src={result} alt="QA Result" style={{ width: "100%", border: "2px solid #444" }} />
        </div>
      )}
    </div>
  );
}