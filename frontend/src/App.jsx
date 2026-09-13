import React, { useState, useEffect } from "react";
import "./App.css";

function App() {
  const [cameraStream, setCameraStream] = useState(null);
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [statusMessage, setStatusMessage] = useState("");

  const startCamera = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: "environment" },
        audio: false,
      });
      setCameraStream(stream);
      setStatusMessage("Camera active - position face for recognition");
    } catch (err) {
      setStatusMessage(`Camera error: ${err.message}`);
    }
  };

  const stopCamera = () => {
    if (cameraStream) {
      cameraStream.getTracks().forEach((track) => track.stop());
      setCameraStream(null);
    }
    setStatusMessage("Camera stopped");
  };

  const enrollUser = async () => {
    setStatusMessage("Enrolling user... (this may take a moment)");
    // TODO: Send frame to backend for enrollment
    setStatusMessage("User enrollment initiated");
  };

  const clockIn = async () => {
    setStatusMessage("Clocking in...");
    // TODO: Send frame to backend for verification and clock-in
    setStatusMessage("Clock-in submitted");
  };

  const clockOut = async () => {
    setStatusMessage("Clocking out...");
    // TODO: Send frame to backend for verification and clock-out
    setStatusMessage("Clock-out submitted");
  };

  return (
    <div className="app-container">
      <header>
        <h1>🏢 Smart Attendance System</h1>
        <p>Biometric-based automated attendance tracking</p>
      </header>

      <main>
        <section className="camera-section">
          <h2>Live Camera Feed</h2>
          {cameraStream ? (
            <video
              autoplay
              playsInline
              style={{ width: "100%", height: "400px" }}
              objectFit "cover"
            >
              <source src={cameraStream} type="video/mp4" />
              Your browser does not support the video tag.
            </video>
          ) : (
            <div className="camera-placeholder">
              <p>Click "Start Camera" to begin</p>
              <button onClick={startCamera} className="primary-btn">
                Start Camera
              </button>
            </div>
          )}
        </section>

        <section className="-controls-section">
          <button onClick={enrollUser} className="secondary-btn">
            📸 Register Employee
          </button>
          <button onClick={clockIn} className="primary-btn">
            🕐 Clock In
          </button>
          <button onClick={clockOut} className="secondary-btn">
            🕓 Clock Out
          </button>
        </section>

        <section className="-status-section">
          <h3>System Status</h3>
          <p>{statusMessage}</p>
        </section>
      </main>

      <footer>
        <p>
          <a href="https://deepface.ai">DeepFace</a> | <a href="https://opencv.org">OpenCV</a>
        </p>
      </footer>
    </div>
  );
}

export default App;