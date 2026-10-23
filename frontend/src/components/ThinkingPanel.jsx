/**
 * Thinking panel component - Shows live agent activity with clear descriptions.
 * Features: Expandable content, copy buttons, full output display.
 */

import { useState, useEffect, useRef } from 'react';

/**
 * Agent colors for styling
 */
const AGENT_COLORS = {
  preAct: { bg: 'rgba(99, 102, 241, 0.1)', border: '#6366f1', text: '#818cf8', label: 'PreAct' },
  ReAct: { bg: 'rgba(34, 197, 94, 0.1)', border: '#22c55e', text: '#4ade80', label: 'ReAct' },
  ReFlect: { bg: 'rgba(6, 182, 212, 0.1)', border: '#06b6d4', text: '#22d3ee', label: 'ReFlect' },
  TME: { bg: 'rgba(249, 115, 22, 0.1)', border: '#f97316', text: '#fb923c', label: 'Memory' },
  RAG: { bg: 'rgba(168, 85, 247, 0.1)', border: '#a855f7', text: '#c084fc', label: 'Search' },
  system: { bg: 'rgba(107, 114, 128, 0.1)', border: '#6b7280', text: '#9ca3af', label: 'System' },
};

/**
 * Event descriptions - cleaner labels without excessive icons
 */
const EVENT_INFO = {
  thought: { label: 'Thinking', desc: 'Reasoning about the task' },
  action: { label: 'Action', desc: 'Taking an action' },
  observation: { label: 'Result', desc: 'Observing results' },
  plan: { label: 'Plan', desc: 'Created execution plan' },
  scene: { label: 'Output', desc: 'Generated content' },
  memory_update: { label: 'Memory', desc: 'Saved to memory' },
  rag_result: { label: 'Search', desc: 'Found information' },
  error: { label: 'Error', desc: 'Something went wrong' },
  complete: { label: 'Done', desc: 'Task finished' },
  status: { label: 'Status', desc: 'Status update' },
};

/**
 * Agent phase descriptions - cleaner without excessive icons
 */
const AGENT_PHASES = {
  preAct: {
    title: 'PreAct — Planning',
    desc: 'Analyzing request and creating execution plan'
  },
  ReAct: {
    title: 'ReAct — Executing',
    desc: 'Think → Act → Observe loop'
  },
  ReFlect: {
    title: 'ReFlect — Validating',
    desc: 'Critique → Improve → Final output'
  }
};

/**
 * Format timestamp
 */
const formatTime = (timestamp) => {
  const date = new Date(timestamp);
  return date.toLocaleTimeString('en-US', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  });
};

/**
 * Single event item - cleaner without excessive icons
 */
function EventItem({ event }) {
  const colors = AGENT_COLORS[event.agent] || AGENT_COLORS.system;
  const info = EVENT_INFO[event.event] || { label: event.event, desc: '' };
  
  // Parse content for better display - reduce icons
  const formatContent = (content) => {
    if (!content) return '';
    
    // Clean up patterns without adding more icons
    return content
      .replace(/THOUGHT:/g, 'Thinking:')
      .replace(/ACTION:/g, 'Action:')
      .replace(/OBSERVATION:/g, 'Result:')
      .replace(/💭/g, '')
      .replace(/⚡/g, '')
      .replace(/👁️/g, '')
      .trim();
  };
  
  return (
    <div 
      className="thinking-event animate-in"
      style={{ 
        backgroundColor: colors.bg,
        borderLeftColor: colors.border,
      }}
    >
      <div className="event-header">
        <span className="event-agent" style={{ color: colors.text }}>
          {colors.label}
        </span>
        <span className="event-type-label">{info.label}</span>
        <span className="event-time">
          {formatTime(event.timestamp || event.receivedAt)}
        </span>
      </div>
      
      <div className="event-content">
        {/* Show full content for scene/output events, truncate others */}
        {event.event === 'scene' || event.metadata?.event_type === 'react_output' || event.metadata?.event_type === 'final_output'
          ? formatContent(event.content)
          : formatContent(event.content?.length > 300 
              ? event.content.substring(0, 300) + '...' 
              : event.content)}
      </div>
      
      {/* Show metadata if it's important */}
      {event.metadata?.quality_score && (
        <div className="event-meta">
          Quality Score: {event.metadata.quality_score}/10
        </div>
      )}
      {event.metadata?.event_type === 'final_output' && (
        <div className="event-meta success">
          Final output ready
        </div>
      )}
    </div>
  );
}

/**
 * Agent phase header
 */
function PhaseHeader({ agent }) {
  const phase = AGENT_PHASES[agent];
  if (!phase) return null;
  
  const colors = AGENT_COLORS[agent] || AGENT_COLORS.system;
  
  return (
    <div 
      className="phase-header"
      style={{ borderColor: colors.border, backgroundColor: colors.bg }}
    >
      <div className="phase-title">{phase.title}</div>
      <div className="phase-desc">{phase.desc}</div>
    </div>
  );
}

/**
 * ThinkingPanel component
 */
function ThinkingPanel({ events, isOpen, onClose, currentAgent, status }) {
  const panelRef = useRef(null);
  
  // Auto-scroll to bottom
  useEffect(() => {
    if (panelRef.current) {
      panelRef.current.scrollTop = panelRef.current.scrollHeight;
    }
  }, [events]);
  
  if (!isOpen) return null;
  
  const isRunning = status === 'running' || status === 'connecting';
  
  // Group events by agent phase
  const groupedEvents = events.reduce((groups, event) => {
    const agent = event.agent || 'system';
    if (!groups[agent]) {
      groups[agent] = [];
    }
    groups[agent].push(event);
    return groups;
  }, {});
  
  // Get current phase info
  const currentPhase = currentAgent ? AGENT_PHASES[currentAgent] : null;
  
  return (
    <div className="thinking-panel">
      <div className="thinking-header">
        <div className="thinking-title">
          <h3>Agent Activity</h3>
          {isRunning && (
            <span className="live-badge">
              <span className="live-dot"></span>
              LIVE
            </span>
          )}
        </div>
        <button className="close-btn" onClick={onClose}>×</button>
      </div>
      
      {/* Current phase indicator - more lively with animation */}
      {currentPhase && isRunning && (
        <div className="current-phase-indicator pulse-animation">
          <span className="phase-name">{currentPhase.title}</span>
          <span className="phase-info">{currentPhase.desc}</span>
        </div>
      )}
      
      <div className="agent-legend">
        <span className="legend-item" style={{ color: AGENT_COLORS.preAct.text }}>
          PreAct
        </span>
        <span className="legend-item" style={{ color: AGENT_COLORS.ReAct.text }}>
          ReAct
        </span>
        <span className="legend-item" style={{ color: AGENT_COLORS.ReFlect.text }}>
          ReFlect
        </span>
      </div>
      
      <div className="thinking-content" ref={panelRef}>
        {/* Show events in order */}
        {events.map((event, index) => {
          // Check if this is a new phase
          const prevAgent = index > 0 ? events[index - 1].agent : null;
          const showPhaseHeader = event.agent !== prevAgent && AGENT_PHASES[event.agent];
          
          return (
            <div key={event.id || index}>
              {showPhaseHeader && <PhaseHeader agent={event.agent} />}
              <EventItem event={event} />
            </div>
          );
        })}
        
        {/* Typing indicator - more lively */}
        {isRunning && (
          <div className="thinking-typing pulse-animation">
            <span className="typing-dot"></span>
            <span className="typing-dot"></span>
            <span className="typing-dot"></span>
            <span className="typing-agent">
              {currentAgent ? `${AGENT_COLORS[currentAgent]?.label || currentAgent} working...` : 'Processing...'}
            </span>
          </div>
        )}
        
        {/* Show summary when complete */}
        {status === 'complete' && (
          <div className="thinking-summary fade-in">
            <div className="summary-text">
              Complete! Check the chat for your results.
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default ThinkingPanel;
