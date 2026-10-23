/**
 * Main App component - Chatbot interface with comparison mode.
 */

import { useState } from 'react';
import { Provider } from 'react-redux';
import store from './store/store';
import ChatInterface from './components/ChatInterface';
import './App.css';

/**
 * Mode options
 */
const MODES = {
  NORMAL: 'normal',
  MULTIAGENT: 'multiagent',
  COMPARE: 'compare',
  VISION: 'vision',
};

/**
 * Header component with mode toggle.
 */
function Header({ mode, onModeChange }) {
  return (
    <header className="app-header">
      <div className="header-content">
        <div className="header-left">
          <div className="logo">
            <span className="logo-icon">🤖</span>
            <h1>AgentFlow AI</h1>
          </div>
          <p className="tagline">Dynamic Multi-Agent Orchestration</p>
        </div>
        
        <div className="mode-toggle">
          <button
            className={`mode-btn normal ${mode === MODES.NORMAL ? 'active' : ''}`}
            onClick={() => onModeChange(MODES.NORMAL)}
          >
            💬 Normal Chat
          </button>
          <button
            className={`mode-btn multiagent ${mode === MODES.MULTIAGENT ? 'active' : ''}`}
            onClick={() => onModeChange(MODES.MULTIAGENT)}
          >
            🧠 Multi-Agent
          </button>
          <button
            className={`mode-btn compare ${mode === MODES.COMPARE ? 'active' : ''}`}
            onClick={() => onModeChange(MODES.COMPARE)}
          >
            ⚖️ Compare
          </button>
          <button
            className={`mode-btn vision ${mode === MODES.VISION ? 'active' : ''}`}
            onClick={() => onModeChange(MODES.VISION)}
          >
            👁️ Vision
          </button>
        </div>
      </div>
    </header>
  );
}

/**
 * Main App layout component.
 */
function AppLayout() {
  const [mode, setMode] = useState(MODES.MULTIAGENT);
  
  return (
    <div className="app">
      <Header mode={mode} onModeChange={setMode} />
      <main className="app-main">
        <ChatInterface mode={mode} />
      </main>
    </div>
  );
}

/**
 * App component with Redux Provider.
 */
function App() {
  return (
    <Provider store={store}>
      <AppLayout />
    </Provider>
  );
}

export default App;
