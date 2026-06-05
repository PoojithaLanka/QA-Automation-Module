import React, { useState } from "react";
import axios from "axios";

export default function UploadPage() {

  const [file1, setFile1] = useState(null);
  const [file2, setFile2] = useState(null);

  const [preview1, setPreview1] = useState(null);
  const [preview2, setPreview2] = useState(null);

  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);

  const [options, setOptions] = useState({
    annotation: true,
    changes: true,
    clash: true
  });

  const runQA = async () => {

    if (!file1 || !file2) {
      alert("Upload both files");
      return;
    }

    setLoading(true);
    setResult(null);

    const formData = new FormData();

    formData.append("file1", file1);
    formData.append("file2", file2);
    formData.append("options", JSON.stringify(options));

    try {

      const res = await axios.post(
        "http://127.0.0.1:8000/analyze",
        formData
      );

      setResult(res.data.image);

    } catch (err) {

      console.error(err);
      alert("Error running QA");

    } finally {

      setLoading(false);

    }
  };

  return (
    <div
      className="dashboard"
      style={{
        padding: "20px",
        width: "100%"
      }}
    >

      <h2>QA Automation Module</h2>

      {/* FILE UPLOADS */}

      <div style={{ marginBottom: "10px" }}>
        <input
          type="file"
          accept=".png,.jpg,.jpeg,.pdf"
          onChange={(e) => {

            const file = e.target.files[0];

            setFile1(file);

            if (file) {
              setPreview1(URL.createObjectURL(file));
            }
          }}
        />
      </div>

      <div style={{ marginBottom: "20px" }}>
        <input
          type="file"
          accept=".png,.jpg,.jpeg,.pdf"
          onChange={(e) => {

            const file = e.target.files[0];

            setFile2(file);

            if (file) {
              setPreview2(URL.createObjectURL(file));
            }
          }}
        />
      </div>

      {/* PREVIEW SECTION */}

      {(preview1 || preview2) && (
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "1fr 1fr",
            gap: "20px",
            marginBottom: "30px",
            width: "100%"
          }}
        >

          {/* INPUT PREVIEW */}

          <div>
            <h3>Input Drawing</h3>

            {preview1 && (
              file1?.type === "application/pdf" ? (
                <iframe
                  src={preview1}
                  title="Input PDF"
                  style={{
                    width: "100%",
                    height: "500px",
                    border: "1px solid #ccc"
                  }}
                />
              ) : (
                <img
                  src={preview1}
                  alt="Input Drawing"
                  style={{
                    width: "100%",
                    maxHeight: "500px",
                    objectFit: "contain",
                    border: "1px solid #ccc"
                  }}
                />
              )
            )}
          </div>

          {/* OUTPUT PREVIEW */}

          <div>
            <h3>Output Drawing</h3>

            {preview2 && (
              file2?.type === "application/pdf" ? (
                <iframe
                  src={preview2}
                  title="Output PDF"
                  style={{
                    width: "100%",
                    height: "500px",
                    border: "1px solid #ccc"
                  }}
                />
              ) : (
                <img
                  src={preview2}
                  alt="Output Drawing"
                  style={{
                    width: "100%",
                    maxHeight: "500px",
                    objectFit: "contain",
                    border: "1px solid #ccc"
                  }}
                />
              )
            )}
          </div>

        </div>
      )}

      {/* OPTIONS */}

      <div style={{ marginBottom: "20px" }}>

        <label style={{ marginRight: "20px" }}>
          <input
            type="checkbox"
            checked={options.annotation}
            onChange={() =>
              setOptions({
                ...options,
                annotation: !options.annotation
              })
            }
          />
          Annotation
        </label>

        <label style={{ marginRight: "20px" }}>
          <input
            type="checkbox"
            checked={options.changes}
            onChange={() =>
              setOptions({
                ...options,
                changes: !options.changes
              })
            }
          />
          Changes
        </label>

        <label>
          <input
            type="checkbox"
            checked={options.clash}
            onChange={() =>
              setOptions({
                ...options,
                clash: !options.clash
              })
            }
          />
          Clash
        </label>

      </div>

      {/* BUTTON */}

      <button
        onClick={runQA}
        disabled={loading}
      >
        {loading ? "Processing..." : "Run QA"}
      </button>

      {/* LOADING */}

      {loading && (
        <p style={{ color: "orange" }}>
          Processing drawing... please wait
        </p>
      )}

      {/* RESULT */}

      {result && (
        <div style={{ marginTop: "40px" }}>

          <h2>QA Result</h2>

          <img
            src={result}
            alt="QA Result"
            style={{
              width: "100%",
              border: "2px solid #444"
            }}
          />

        </div>
      )}

    </div>
  );
}