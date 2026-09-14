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
  const [faceMatches, setFaceMatches] = useState([]);
  const [registration, setRegistration] = useState(null);
  const [capturedAngles, setCapturedAngles] = useState([]);
  const [attendanceNotice, setAttendanceNotice] = useState(null);
  const videoRef = useRef(null);
  const streamRef = useRef(null);
  const registrationRef = useRef(false);
  const stableMatchRef = useRef({ id: null, count: 0 });
  const attendanceCooldownRef = useRef(new Map());

  const employeesRef = {
    "EMP-001": { name: "John Doe", department: "Engineering" },
    "EMP-002": { name: "Jane Smith", department: "HR" },
    "EMP-003": { name: "Robert Johnson", department: "Finance" },
  };

  const handleStartCamera = async () => {
    try {
      if (!navigator.mediaDevices?.getUserMedia) {
        throw new Error("Camera access is unavailable. Use HTTPS or localhost.");
      }
      let stream;
      try {
        stream = await navigator.mediaDevices.getUserMedia({
          video: { facingMode: { ideal: "environment" }, width: { ideal: 1920 }, height: { ideal: 1080 } },
          audio: false,
        });
      } catch (constraintError) {
        stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false });
      }
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

  const analyzeCurrentFrame = async () => {
    try {
      const frame = await captureFrame();
      const form = new FormData();
      form.append("face_image", frame, "analysis.jpg");
      const response = await fetch(`${API_BASE}/analyze`, { method: "POST", body: form });
      if (!response.ok) throw new Error("Face analysis failed");
      const faces = (await response.json()).faces;
      setFaceMatches(faces);
      const recognized = faces.find((face) => face.recognized);
      if (recognized) {
        const stable = stableMatchRef.current;
        if (stable.id === recognized.user_id) {
          stable.count += 1;
        } else {
          stable.id = recognized.user_id;
          stable.count = 1;
        }
        const lastMarked = attendanceCooldownRef.current.get(recognized.employee_id) || 0;
        if (stable.count >= 2 && Date.now() - lastMarked > 10 * 60 * 1000) {
          const clockForm = new FormData();
          clockForm.append("face_image", frame, "attendance.jpg");
          const clockResponse = await fetch(
            `${API_BASE}/clock-in?employee_id=${encodeURIComponent(recognized.employee_id)}`,
            { method: "POST", body: clockForm },
          );
          if (clockResponse.ok) {
            const attendance = await clockResponse.json();
            attendanceCooldownRef.current.set(recognized.employee_id, Date.now());
            setAttendanceNotice(attendance);
            setStatusMessage("Attendance marked automatically");
            await loadLogs();
          }
        }
      } else {
        stableMatchRef.current = { id: null, count: 0 };
      }
    } catch (err) {
      if (cameraActive) setStatusMessage(`Analysis error: ${err.message}`);
    }
  };

  const handleEnroll = async () => {
    try {
      if (!employeeName || !employeeId) throw new Error("Enter employee name and ID");
      if (!cameraActive) throw new Error("Start the camera first");
      registrationRef.current = true;
      setCapturedAngles([]);
      const angles = [
        ["center", "Look straight at the camera"],
        ["left", "Turn your face slowly to the left"],
        ["right", "Turn your face slowly to the right"],
        ["up", "Look slightly up"],
        ["down", "Look slightly down"],
      ];
      const frames = [];
      for (const [key, instruction] of angles) {
        setRegistration({ key, instruction, countdown: 3 });
        for (let countdown = 3; countdown > 0; countdown -= 1) {
          setRegistration({ key, instruction, countdown });
          await new Promise((resolve) => window.setTimeout(resolve, 700));
        }
        frames.push(await captureFrame());
        setCapturedAngles((current) => [...current, key]);
      }
      const form = new FormData();
      frames.forEach((frame, index) => form.append("face_images", frame, `${angles[index][0]}.jpg`));
      const response = await fetch(
        `${API_BASE}/register?name=${encodeURIComponent(employeeName)}&employee_id=${encodeURIComponent(employeeId)}`,
        { method: "POST", body: form },
      );
      if (!response.ok) throw new Error((await response.json()).detail || "Registration failed");
      setStatusMessage("Employee registered successfully");
      setRegistration(null);
      setCapturedAngles([]);
      setEmployeeName("");
      await loadEmployees();
    } catch (err) {
      setStatusMessage(`Registration error: ${err.message}`);
      setRegistration(null);
      setCapturedAngles([]);
    } finally {
      registrationRef.current = false;
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
      const attendance = await response.json();
      setAttendanceNotice(attendance);
      setStatusMessage("Attendance marked successfully");
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

  useEffect(() => {
    if (!cameraActive || !videoRef.current || !streamRef.current) return undefined;
    videoRef.current.srcObject = streamRef.current;
    videoRef.current.play().catch(() => {
      setStatusMessage("Camera is ready. Click the video to start playback.");
    });
    return undefined;
  }, [cameraActive]);

  useEffect(() => {
    if (!cameraActive) {
      setFaceMatches([]);
      return undefined;
    }
    const timer = window.setInterval(() => {
      if (!registrationRef.current) analyzeCurrentFrame();
    }, 1500);
    return () => window.clearInterval(timer);
  }, [cameraActive]);

  return (
    <div className="app-container">
      <header className="app-header">
        <div className="brand">
          <div className="brand-mark">✓</div>
          <div>
            <h1>Smart Attendance</h1>
            <p>Biometric attendance, made simple</p>
          </div>
        </div>
        <div className={`system-pill ${cameraActive ? "online" : ""}`}>
          <span />
          {cameraActive ? "Camera online" : "Camera offline"}
        </div>
      </header>

      <main>
        {attendanceNotice && (
          <section className="attendance-notice" role="status">
            <div className="success-icon">✓</div>
            <div className="attendance-copy">
              <strong>Attendance marked</strong>
              <span>{attendanceNotice.name || "Employee"} is checked in successfully</span>
              <div className="attendance-meta">
                <b>ID: {attendanceNotice.employee_id}</b>
                <span>{attendanceNotice.clock_in ? new Date(attendanceNotice.clock_in).toLocaleTimeString() : "Just now"}</span>
                {attendanceNotice.confidence && <span>{Math.round(attendanceNotice.confidence * 100)}% match</span>}
              </div>
            </div>
            <button className="notice-dismiss" onClick={() => setAttendanceNotice(null)} aria-label="Dismiss attendance confirmation">×</button>
          </section>
        )}

        <section className="camera-section">
          <div className="section-heading">
            <div>
              <span className="eyebrow">RECOGNITION</span>
              <h2>Live camera feed</h2>
            </div>
            <span className="scan-state">{cameraActive ? "Scanning for faces" : "Ready to scan"}</span>
          </div>
          {cameraActive ? (
            <div className="video-wrapper">
              <video
                ref={videoRef}
                autoPlay
                playsInline
                style={{ width: "100%", height: "400px" }}
                muted
              />
              {faceMatches.map((face, index) => (
                <div
                  className={`face-box ${face.recognized ? "recognized" : "unknown"}`}
                  key={`${face.box.x}-${face.box.y}-${index}`}
                  style={{
                    left: `${(face.box.x / (videoRef.current?.videoWidth || 1)) * 100}%`,
                    top: `${(face.box.y / (videoRef.current?.videoHeight || 1)) * 100}%`,
                    width: `${(face.box.width / (videoRef.current?.videoWidth || 1)) * 100}%`,
                    height: `${(face.box.height / (videoRef.current?.videoHeight || 1)) * 100}%`,
                  }}
                >
                  <span>
                    {face.recognized
                      ? `${face.name} (${face.employee_id}) ${Math.round(face.confidence * 100)}%`
                      : "Unknown"}
                  </span>
                </div>
              ))}
              {registration && (
                <div className="registration-guide">
                  <strong>{registration.instruction}</strong>
                  <span>Capturing in {registration.countdown}...</span>
                  <small>{capturedAngles.length}/5 angles captured</small>
                </div>
              )}
            </div>
          ) : (
            <div className="camera-placeholder">
              <div className="camera-placeholder-icon">◉</div>
              <strong>Start your camera to begin</strong>
              <p>Position your face inside the frame for automatic recognition.</p>
              <button
                onClick={() => handleStartCamera()}
                className="primary-btn"
                disabled={cameraActive}
              >
                Start Camera
              </button>
            </div>
          )}
          {cameraActive && <button onClick={handleStopCamera} className="stop-camera">Stop camera</button>}
        </section>

        <section className="controls-section">
          <div className="control-card registration-card">
            <span className="card-icon">＋</span>
            <div>
              <h3>Register employee</h3>
              <p>Capture five angles for a reliable match.</p>
            </div>
            <input value={employeeName} onChange={(event) => setEmployeeName(event.target.value)} placeholder="Full name" />
            <input value={employeeId} onChange={(event) => setEmployeeId(event.target.value)} placeholder="Employee ID" />
            <button
              onClick={handleEnroll}
              className="secondary-btn"
              disabled={!cameraActive}
            >
              Register employee
            </button>
          </div>
          <div className="control-card">
            <span className="card-icon">◷</span>
            <div>
              <h3>Manual attendance</h3>
              <p>Use this when automatic recognition needs help.</p>
            </div>
            <button
              onClick={handleClockIn}
              className="primary-btn"
              disabled={!cameraActive}
            >
              Clock in
            </button>
            <button
              onClick={handleClockOut}
              className="secondary-btn"
              disabled={!cameraActive}
            >
              Clock out
            </button>
          </div>
        </section>

        <section className="status-section">
          <span className="status-dot" />
          <div><h3>System status</h3>
          <p>{statusMessage}</p>
          </div>
        </section>

        <section className="data-grid">
        <section className="employees-section data-card">
          <div className="card-heading"><h3>Registered employees</h3><span>{employees.length}</span></div>
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

        <section className="logs-section data-card">
          <div className="card-heading"><h3>Recent attendance</h3><span>{logs.length}</span></div>
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