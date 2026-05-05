import React, { useState } from "react";
import { AuthRepository } from "./api/AuthRepository.js";
import { VideoRepository } from "./api/VideoRepository.js";
import { AuthPanel } from "./components/AuthPanel.jsx";
import { VideoPanel } from "./components/VideoPanel.jsx";

/**
 * Repositories are instantiated once here (the composition root) and injected
 * downward. Swapping implementations (e.g. a mock for tests) only requires
 * changing this file.
 */
const authRepo  = new AuthRepository();
const videoRepo = new VideoRepository();

export default function App() {
  const [session, setSession] = useState(null);

  return (
    <div style={{ minHeight: "100vh", background: "#080808", display: "flex", alignItems: "center", justifyContent: "center", padding: 24, fontFamily: "'DM Mono', 'Courier New', monospace" }}>
      <link href="https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&display=swap" rel="stylesheet" />
      {!session ? (
        <AuthPanel
          authRepo={authRepo}
          onLogin={(token, username) => setSession({ token, username })}
        />
      ) : (
        <VideoPanel
          token={session.token}
          username={session.username}
          onLogout={() => setSession(null)}
          videoRepo={videoRepo}
        />
      )}
    </div>
  );
}