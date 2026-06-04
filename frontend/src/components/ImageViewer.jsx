export default function ImageViewer({ imageUrl }) {
  return (
    <div className="viewer">
      <h3>Result</h3>
      <img src={imageUrl} />
    </div>
  );
}