import React, { useState, useEffect } from "react";
import "./App.css";

function App() {
  const [cameraActive, setCameraActive] = useState(false);
  const [statusMessage, setStatusMessage] = useState("");
  const [employees, setEmployees] = useState([]);
  const [logs, setLogs] = useState([]);

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
      setCameraActive(true);
      setStatusMessage("Camera active - positioning for face recognition");
      return stream;
    } catch (err) {
      setStatusMessage(`Camera error: ${err.message}`);
      return null;
    }
  };

  const handleStopCamera = () => {
    setCameraActive(false);
    setStatusMessage("Camera stopped");
  };

  const handleEnroll = async (stream) => {
    setStatusMessage("Processing face enrollment...");
    // TODO: Send frame to backend /api/v1/register
    // with employee name + employee_id + captured frame
    setStatusMessage("Employee enrollment initiated");
    // In a full implementation, would capture canvas frame and POST
  };

  const handleClockIn = async (stream) => {
    setStatusMessage("Verifying face for clock-in...");
    // TODO: Send frame to backend /api/v1/clock-in
    // with employee_id and live frame for verification
    // Backend returns: { log_id, employee_id, name, confidence, clock_in }
    setStatusMessage("Clock-in request sent");
  };

  const handleClockOut = async (stream) => {
    setStatusMessage("Verifying face for clock-out...");
    // TODO: Send frame to backend /api/v1/clock-out
    setStatusMessage("Clock-out request sent");
  };

  const loadEmployees = () => {
    setEmployees(
      Object.entries(employeesRef).map(([id, info]) => ({
        id,
        ...info,
      }))
    );
  };

  const loadLogs = () => {
    // TODO: Fetch from /api/v1/logs
    setLogs([
      {
        id: 1,
        employee_id: "EMP-001",
        name: "John Doe",
        clock_in: "2026-09-13T08:30:00Z",
        confidence: 0.94,
      },
      {
        id: 2,
        employee_id: "EMP-002",
        name: "Jane Smith",
        clock_in: "2026-09-13T08:25:00Z",
        confidence: 0.92,
      },
    ]);
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
              autoplay
              playsInline
              style={{ width: "100%", height: "400px" }}
              muted
            >
              <source srcObject={null} type="video/mp4" />
              Your browser does not support the video tag.
            </video>
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
          <div style={{ marginBottom: "1rem" }}>
            <button
              onClick={() => handleEnroll(cameraActive ? "stream" : null)}
              className="secondary-btn"
              disabled={!cameraActive}
            >
              📸 Register Employee
            </button>
            <button
              onClick={() => handleClockIn(cameraActive ? "stream" : null)}
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