export default function ResultCard({ result }) {

  const imageSrc = `data:image/png;base64,${result.image}`;

  return (
    <div>
      <h3>QA Output</h3>

      <img
        src={imageSrc}
        style={{
          width: "100%",
          border: "2px solid #ccc",
          borderRadius: "10px"
        }}
      />

      <h4>Issues</h4>
      <ul>
        {result.issues.map((item, i) => (
          <li key={i}>
            {item.type} - {item.status || item.count || "OK"}
          </li>
        ))}
      </ul>
    </div>
  );
}