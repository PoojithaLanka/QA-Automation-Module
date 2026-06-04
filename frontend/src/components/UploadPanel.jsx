import { useDropzone } from "react-dropzone";

export default function UploadPanel({ setFile1, setFile2 }) {

  const drop1 = useDropzone({ onDrop: (f) => setFile1(f[0]) });
  const drop2 = useDropzone({ onDrop: (f) => setFile2(f[0]) });

  return (
    <div className="uploadGrid">

      <div {...drop1.getRootProps()} className="dropBox">
        <input {...drop1.getInputProps()} />
        Drop INPUT Drawing
      </div>

      <div {...drop2.getRootProps()} className="dropBox">
        <input {...drop2.getInputProps()} />
        Drop OUTPUT Drawing
      </div>

    </div>
  );
}