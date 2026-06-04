import React, { useState } from "react";
import axios from "axios";

export default function UploadPage() {

  const [file1, setFile1] = useState(null);
  const [file2, setFile2] = useState(null);
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
      const res = await axios.post("http://127.0.0.1:8000/analyze", formData);
      setResult(res.data.image);
    } catch (err) {
      console.log(err);
      alert("Error running QA");
    }

    setLoading(false);
  };

  return (
    <div className="dashboard">

      <h2>QA Automation Module</h2>

      <input type="file" onChange={(e) => setFile1(e.target.files[0])} />
      <input type="file" onChange={(e) => setFile2(e.target.files[0])} />

      <div>
        <label>
          <input type="checkbox"
            checked={options.annotation}
            onChange={() => setOptions({ ...options, annotation: !options.annotation })}
          />
          Annotation
        </label>

        <label>
          <input type="checkbox"
            checked={options.changes}
            onChange={() => setOptions({ ...options, changes: !options.changes })}
          />
          Changes
        </label>

        <label>
          <input type="checkbox"
            checked={options.clash}
            onChange={() => setOptions({ ...options, clash: !options.clash })}
          />
          Clash
        </label>
      </div>

      <button onClick={runQA} disabled={loading}>
        {loading ? "Processing..." : "Run QA"}
      </button>

      {loading && (
        <p style={{ color: "orange" }}>
          Processing drawing... please wait
        </p>
      )}

      {result && (
        <div>
          <h3>Output</h3>
          <img src={result} width="90%" />
        </div>
      )}

    </div>
  );
}