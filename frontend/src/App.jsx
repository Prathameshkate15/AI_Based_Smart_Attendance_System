import React, { useRef, useState, useEffect } from "react";
import "./App.css";

const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000/api/v1";

function App() {
  const [cameraActive, setCameraActive] = useState(false);
  const [statusMessage, setStatusMessage] = useState("");
  const [employees, setEmployees] = useState([]);
  const [logs, setLogs] = useState([]);
  const [employeeId, setEmployeeId] = useState("");
  const [employeeName, setEmployeeName] = useState("");
  const videoRef = useRef(null);
  const streamRef = useRef(null);

  const employeesRef = {
    "EMP-001": { name: "John Doe", department: "Engineering" },
    "EMP-002": { name: "Jane Smith", department: "HR" },
    "EMP-003": { name: "Robert Johnson", department: "Finance" },
  };

  const handleStartCamera = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: {
          facingMode: "environment",
          width: { ideal: 1920 },
          height: { ideal: 1080 },
        },
        audio: false,
      });
      streamRef.current = stream;
      setCameraActive(true);
      setStatusMessage("Camera active - positioning for face recognition");
      return stream;
    } catch (err) {
      setStatusMessage(`Camera error: ${err.message}`);
      return null;
    }
  };

  const handleStopCamera = () => {
    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;
    setCameraActive(false);
    setStatusMessage("Camera stopped");
  };

  const captureFrame = () => {
    const video = videoRef.current;
    if (!video || video.readyState < 2) throw new Error("Camera frame is not ready");
    const canvas = document.createElement("canvas");
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    canvas.getContext("2d").drawImage(video, 0, 0);
    return new Promise((resolve) => canvas.toBlob(resolve, "image/jpeg", 0.9));
  };

  const handleEnroll = async () => {
    try {
      if (!employeeName || !employeeId) throw new Error("Enter employee name and ID");
      const frame = await captureFrame();
      const form = new FormData();
      form.append("face_images", frame, "face.jpg");
      const response = await fetch(
        `${API_BASE}/register?name=${encodeURIComponent(employeeName)}&employee_id=${encodeURIComponent(employeeId)}`,
        { method: "POST", body: form },
      );
      if (!response.ok) throw new Error((await response.json()).detail || "Registration failed");
      setStatusMessage("Employee registered successfully");
      setEmployeeName("");
      await loadEmployees();
    } catch (err) {
      setStatusMessage(`Registration error: ${err.message}`);
    }
  };

  const handleClockIn = async () => {
    try {
      if (!employeeId) throw new Error("Enter an employee ID");
      const frame = await captureFrame();
      const form = new FormData();
      form.append("face_image", frame, "face.jpg");
      const response = await fetch(`${API_BASE}/clock-in?employee_id=${encodeURIComponent(employeeId)}`, {
        method: "POST",
        body: form,
      });
      if (!response.ok) throw new Error((await response.json()).detail || "Clock-in failed");
      setStatusMessage((await response.json()).message);
      await loadLogs();
    } catch (err) {
      setStatusMessage(`Clock-in error: ${err.message}`);
    }
  };

  const handleClockOut = async () => {
    try {
      if (!employeeId) throw new Error("Enter an employee ID");
      const response = await fetch(`${API_BASE}/clock-out?employee_id=${encodeURIComponent(employeeId)}`, {
        method: "POST",
      });
      if (!response.ok) throw new Error((await response.json()).detail || "Clock-out failed");
      setStatusMessage((await response.json()).message);
      await loadLogs();
    } catch (err) {
      setStatusMessage(`Clock-out error: ${err.message}`);
    }
  };

  const loadEmployees = async () => {
    try {
      const response = await fetch(`${API_BASE}/users`);
      if (!response.ok) throw new Error("Could not load employees");
      setEmployees(await response.json());
    } catch (err) {
      setStatusMessage(`Employee load error: ${err.message}`);
    }
  };

  const loadLogs = async () => {
    try {
      const response = await fetch(`${API_BASE}/logs`);
      if (!response.ok) throw new Error("Could not load attendance logs");
      setLogs(await response.json());
    } catch (err) {
      setStatusMessage(`Log load error: ${err.message}`);
    }
  };

  useEffect(() => {
    loadEmployees();
    loadLogs();
  }, []);

  return (
    <div className="app-container">
      <header>
        <h1>🏢 Smart Attendance System</h1>
        <p>Biometric-based automated attendance tracking</p>
      </header>

      <main>
        <section className="camera-section">
          <h2>Live Camera Feed</h2>
          {cameraActive ? (
            <video
              ref={videoRef}
              autoPlay
              playsInline
              style={{ width: "100%", height: "400px" }}
              muted
              onLoadedMetadata={() => {
                videoRef.current.srcObject = streamRef.current;
              }}
            />
          ) : (
            <div className="camera-placeholder">
              <p>Click "Start Camera" to begin biometric tracking</p>
              <button
                onClick={() => handleStartCamera()}
                className="primary-btn"
                disabled={cameraActive}
              >
                Start Camera
              </button>
              <button
                onClick={handleStopCamera}
                className="secondary-btn"
                disabled={!cameraActive}
              >
                Stop Camera
              </button>
            </div>
          )}
        </section>

        <section className="controls-section">
          <input value={employeeName} onChange={(event) => setEmployeeName(event.target.value)} placeholder="Employee name" />
          <input value={employeeId} onChange={(event) => setEmployeeId(event.target.value)} placeholder="Employee ID" />
          <div style={{ marginBottom: "1rem" }}>
            <button
              onClick={handleEnroll}
              className="secondary-btn"
              disabled={!cameraActive}
            >
              📸 Register Employee
            </button>
            <button
              onClick={handleClockIn}
              className="primary-btn"
              disabled={!cameraActive}
            >
              🕐 Clock In
            </button>
            <button
              onClick={handleClockOut}
              className="secondary-btn"
              disabled={!cameraActive}
            >
              🕓 Clock Out
            </button>
          </div>
        </section>

        <section className="status-section">
          <h3>System Status</h3>
          <p>{statusMessage}</p>
        </section>

        <section className="employees-section">
          <h3>Registered Employees</h3>
          <ul>
            {employees.map((emp) => (
              <li key={emp.id} style={{ marginBottom: "0.5rem" }}>
                <span style={{ fontWeight: "bold" }}>{emp.employee_id}</span>
                - {emp.name} ({emp.department})
              </li>
            ))}
          </ul>
          <p style={{ fontSize: "0.8rem", color: "666" }}>
            <em>Click "Register Employee" to add via biometric enrollment</em>
          </p>
        </section>

        <section className="logs-section">
          <h3>Attendance Logs</h3>
          <ul>
            {logs.map((log) => (
              <li key={log.id} style={{ marginBottom: "0.5rem" }}>
                <span style={{ fontWeight: "bold" }}>
                  {log.employee_id}: {log.name}
                </span>
                at {new Date(log.clock_in).toLocaleTimeString()} —
                confidence: {Math.round(log.confidence * 100)}%
              </li>
            ))}
            {logs.length === 0 && <li>No attendance records yet</li>}
          </ul>
        </section>
      </main>

      <footer>
        <p>
          {"DeepFace & InsightFace"} | {"OpenCV"}
        </p>
      </footer>
    </div>
  );
}

export default App;