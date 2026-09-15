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
  const [adminToken, setAdminToken] = useState(() => sessionStorage.getItem("adminToken"));
  const [view, setView] = useState(() => sessionStorage.getItem("adminToken") ? "admin" : "landing");
  const [captureDuration, setCaptureDuration] = useState(
    () => Number(localStorage.getItem("captureDuration")) || 7.5,
  );
  const [login, setLogin] = useState({ username: "", password: "" });
  const [loginError, setLoginError] = useState("");
  const [isRegistering, setIsRegistering] = useState(false);
  const [isClockingIn, setIsClockingIn] = useState(false);
  const [isClockingOut, setIsClockingOut] = useState(false);
  const videoRef = useRef(null);
  const streamRef = useRef(null);
  const registrationRef = useRef(false);
  const stableMatchRef = useRef({ id: null, count: 0 });
  const attendanceCooldownRef = useRef(new Map());
  const attendanceInFlightRef = useRef(false);
  const analysisInFlightRef = useRef(false);

  const adminFetch = (url, options = {}) => fetch(url, {
    ...options,
    headers: { ...(options.headers || {}), Authorization: `Bearer ${adminToken}` },
  });

  const handleLogin = async (event) => {
    event.preventDefault();
    setLoginError("");
    const username = login.username.trim();
    const form = new FormData();
    form.append("username", username);
    form.append("password", login.password);
    try {
      const response = await fetch(`${API_BASE}/admin/login`, { method: "POST", body: form });
      if (!response.ok) {
        const error = await response.json().catch(() => ({}));
        setLoginError(error.detail || "Invalid admin username or password");
        return;
      }
      const data = await response.json();
      sessionStorage.setItem("adminToken", data.token);
      setAdminToken(data.token);
      setView("admin");
    } catch (error) {
      setLoginError(`Unable to reach the API: ${error.message}`);
    }
  };

  const handleLogout = (returnToLogin = false) => {
    sessionStorage.removeItem("adminToken");
    setAdminToken(null);
    setView(returnToLogin ? "login" : "landing");
  };

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
    if (analysisInFlightRef.current || registrationRef.current) return;
    analysisInFlightRef.current = true;
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
        if (
          stable.count >= 2 &&
          !attendanceInFlightRef.current &&
          Date.now() - lastMarked > 10 * 60 * 1000
        ) {
          attendanceInFlightRef.current = true;
          try {
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
              if (adminToken) await loadLogs();
            } else {
              const error = await clockResponse.json().catch(() => ({}));
              setStatusMessage(`Automatic attendance failed: ${error.detail || "clock-in rejected"}`);
            }
          } finally {
            attendanceInFlightRef.current = false;
          }
        }
      } else {
        stableMatchRef.current = { id: null, count: 0 };
      }
    } catch (err) {
      if (cameraActive) setStatusMessage(`Analysis error: ${err.message}`);
    } finally {
      analysisInFlightRef.current = false;
    }
  };

  const handleEnroll = async () => {
    try {
      if (!adminToken || view !== "admin") throw new Error("Open Admin login to register employees");
      if (!employeeName.trim() || !employeeId.trim()) throw new Error("Enter employee name and ID");
      if (!cameraActive) throw new Error("Start the camera first");
      setIsRegistering(true);
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
        let acceptedFrame = null;
        for (let attempt = 1; attempt <= 3 && !acceptedFrame; attempt += 1) {
          setRegistration({ key, instruction, countdown: captureDuration, attempt });
          for (let countdown = captureDuration; countdown > 0; countdown -= 0.5) {
            setRegistration({ key, instruction, countdown, attempt });
            await new Promise((resolve) => window.setTimeout(resolve, 500));
          }
          const candidate = await captureFrame();
          const checkForm = new FormData();
          checkForm.append("face_image", candidate, `${key}.jpg`);
          const checkResponse = await adminFetch(`${API_BASE}/registration-check`, {
            method: "POST",
            body: checkForm,
          });
          const check = await checkResponse.json().catch(() => ({}));
          if (checkResponse.ok && check.valid) {
            acceptedFrame = candidate;
          } else if (attempt < 3) {
            setRegistration({
              key,
              instruction: `${key.toUpperCase()} image is unclear — please take it again`,
              countdown: 2,
              attempt,
              retry: true,
            });
            setStatusMessage(`${key.toUpperCase()} angle needs a retake: ${check.message || "face not clear"}`);
            await new Promise((resolve) => window.setTimeout(resolve, 2000));
          } else {
            throw new Error(`${key.toUpperCase()} angle is still unclear after 3 attempts. Improve lighting and try again.`);
          }
        }
        frames.push(acceptedFrame);
        setCapturedAngles((current) => [...current, key]);
      }
      const form = new FormData();
      frames.forEach((frame, index) => form.append("face_images", frame, `${angles[index][0]}.jpg`));
      const response = await adminFetch(
        `${API_BASE}/register?name=${encodeURIComponent(employeeName)}&employee_id=${encodeURIComponent(employeeId)}`,
        { method: "POST", body: form },
      );
      if (!response.ok) {
        const error = await response.json().catch(() => ({}));
        throw new Error(error.detail || "Registration failed");
      }
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
      setIsRegistering(false);
    }
  };

  const handleClockIn = async () => {
    try {
      setIsClockingIn(true);
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
      if (adminToken) await loadLogs();
    } catch (err) {
      setStatusMessage(`Clock-in error: ${err.message}`);
    } finally {
      setIsClockingIn(false);
    }
  };

  const handleClockOut = async () => {
    try {
      setIsClockingOut(true);
      if (!employeeId) throw new Error("Enter an employee ID");
      const response = await fetch(`${API_BASE}/clock-out?employee_id=${encodeURIComponent(employeeId)}`, {
        method: "POST",
      });
      if (!response.ok) throw new Error((await response.json()).detail || "Clock-out failed");
      setStatusMessage((await response.json()).message);
      if (adminToken) await loadLogs();
    } catch (err) {
      setStatusMessage(`Clock-out error: ${err.message}`);
    } finally {
      setIsClockingOut(false);
    }
  };

  const loadEmployees = async () => {
    try {
      const response = await adminFetch(`${API_BASE}/users`);
      if (response.status === 401) {
        handleLogout(true);
        throw new Error("Admin session expired; please sign in again");
      }
      if (!response.ok) throw new Error("Could not load employees");
      setEmployees(await response.json());
    } catch (err) {
      setStatusMessage(`Employee load error: ${err.message}`);
    }
  };

  const loadLogs = async () => {
    try {
      const response = await adminFetch(`${API_BASE}/logs`);
      if (response.status === 401) {
        handleLogout(true);
        throw new Error("Admin session expired; please sign in again");
      }
      if (!response.ok) throw new Error("Could not load attendance logs");
      setLogs(await response.json());
    } catch (err) {
      setStatusMessage(`Log load error: ${err.message}`);
    }
  };

  const handleDeleteEmployee = async (user) => {
    if (!window.confirm(`Delete ${user.name} (${user.employee_id}) and attendance history?`)) return;
    const response = await adminFetch(`${API_BASE}/users/${user.id}`, { method: "DELETE" });
    if (!response.ok) {
      setStatusMessage("Could not delete employee");
      return;
    }
    setStatusMessage(`${user.employee_id} deleted`);
    await loadEmployees();
    await loadLogs();
  };

  const handleExport = async () => {
    const response = await adminFetch(`${API_BASE}/logs/export`);
    if (!response.ok) {
      setStatusMessage("Could not export attendance");
      return;
    }
    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = "attendance-report.csv";
    link.click();
    URL.revokeObjectURL(url);
  };

  useEffect(() => {
    if (!adminToken) return undefined;
    loadEmployees();
    loadLogs();
    return undefined;
  }, [adminToken]);

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

  useEffect(() => {
    if (view === "attendance" && !cameraActive) {
      handleStartCamera();
    }
    if (view !== "attendance" && cameraActive && !registrationRef.current) {
      handleStopCamera();
    }
  }, [view]);

  if (view === "landing") {
    return (
      <div className="landing-page">
        <div className="landing-brand"><div className="brand-mark">✓</div><span>Smart Attendance</span></div>
        <div className="landing-content">
          <span className="eyebrow">SECURE BIOMETRIC ATTENDANCE</span>
          <h1>How would you like to continue?</h1>
          <p>Choose an option below to access the attendance system.</p>
          <div className="entry-options">
            <button className="entry-card" onClick={() => setView("attendance")}>
              <span className="entry-icon">◉</span>
              <strong>Mark attendance</strong>
              <span>Use the camera to recognize and mark attendance.</span>
              <b>Continue to camera →</b>
            </button>
            <button className="entry-card admin-entry" onClick={() => setView("login")}>
              <span className="entry-icon">▣</span>
              <strong>Admin login</strong>
              <span>Manage employees, settings, reports, and attendance data.</span>
              <b>Open admin portal →</b>
            </button>
          </div>
        </div>
      </div>
    );
  }

  if (view === "login") {
    return (
      <div className="login-page">
        <form className="login-card" onSubmit={handleLogin}>
          <div className="brand-mark">✓</div>
          <span className="eyebrow">SECURE ADMIN AREA</span>
          <h1>Welcome back</h1>
          <p>Sign in to manage employees and attendance records.</p>
          <label>Username<input value={login.username} onChange={(event) => setLogin({ ...login, username: event.target.value })} autoComplete="username" required /></label>
          <label>Password<input type="password" value={login.password} onChange={(event) => setLogin({ ...login, password: event.target.value })} autoComplete="current-password" required /></label>
          {loginError && <div className="login-error">{loginError}</div>}
          <button className="primary-btn" type="submit">Sign in securely</button>
          <button type="button" className="text-button" onClick={() => setView("landing")}>← Back to options</button>
        </form>
      </div>
    );
  }

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
        <button className="logout-btn" onClick={() => view === "admin" ? handleLogout() : setView("landing")}>
          {view === "admin" ? "Log out" : "Back to options"}
        </button>
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
              <h2>{view === "admin" ? "Live camera feed" : "Mark attendance"}</h2>
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
                  <small>{capturedAngles.length}/5 angles captured · {registration.countdown}s
                    {registration.attempt > 1 && ` · attempt ${registration.attempt}/3`}
                  </small>
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

        <section className={`controls-section ${view === "attendance" ? "attendance-controls" : ""}`}>
          {view === "admin" && <div className="control-card registration-card">
            <span className="card-icon">＋</span>
            <div>
              <h3>Register employee</h3>
              <p>Capture five angles for a reliable match.</p>
            </div>
            <input value={employeeName} onChange={(event) => setEmployeeName(event.target.value)} placeholder="Full name" />
            <input value={employeeId} onChange={(event) => setEmployeeId(event.target.value)} placeholder="Employee ID" />
            <label className="duration-setting">Seconds per registration angle
              <input type="number" min="1" max="30" step="0.5" value={captureDuration} onChange={(event) => {
                const value = Math.max(1, Math.min(30, Number(event.target.value) || 7.5));
                setCaptureDuration(value);
                localStorage.setItem("captureDuration", value);
              }} />
            </label>
            <button
              onClick={handleEnroll}
              className="secondary-btn"
              disabled={!cameraActive || isRegistering}
            >
              {isRegistering ? "Capturing angles..." : "Register employee"}
            </button>
          </div>}
          <div className="control-card">
            <span className="card-icon">◷</span>
            <div>
              <h3>Manual attendance</h3>
              <p>Use this when automatic recognition needs help.</p>
            </div>
            <button
              onClick={handleClockIn}
              className="primary-btn"
              disabled={!cameraActive || isClockingIn || isRegistering}
            >
              {isClockingIn ? "Marking..." : "Clock in"}
            </button>
            <button
              onClick={handleClockOut}
              className="secondary-btn"
              disabled={!cameraActive || isClockingOut || isRegistering}
            >
              {isClockingOut ? "Processing..." : "Clock out"}
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
        {view === "admin" && <section className="employees-section data-card">
          <div className="card-heading"><h3>Registered employees</h3><span>{employees.length}</span></div>
          <ul>
            {employees.map((emp) => (
              <li key={emp.id} style={{ marginBottom: "0.5rem" }}>
                <span style={{ fontWeight: "bold" }}>{emp.employee_id}</span>
                - {emp.name} <button className="delete-btn" onClick={() => handleDeleteEmployee(emp)}>Delete</button>
              </li>
            ))}
          </ul>
          <p style={{ fontSize: "0.8rem", color: "666" }}>
            <em>Click "Register Employee" to add via biometric enrollment</em>
          </p>
        </section>}

        {view === "admin" && <section className="logs-section data-card">
          <div className="card-heading"><h3>Recent attendance</h3><div><span>{logs.length}</span><button className="export-btn" onClick={handleExport}>Export Excel</button></div></div>
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
        </section>}
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