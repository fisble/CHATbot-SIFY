/**
 * Live agent feed component showing real-time agent events.
 * Enhanced with copy buttons and expandable messages.
 */

import { useEffect, useRef, useState } from 'react';
import { useSelector } from 'react-redux';
import {
  selectEvents,
  selectStatus,
  selectCurrentAgent,
  EVENT_TYPES,
  AGENT_NAMES,
} from '../store/agentSlice';

/**
 * Color mapping for agents.
 */
const AGENT_COLORS = {
  [AGENT_NAMES.preAct]: 'agent-preact',
  [AGENT_NAMES.ReAct]: 'agent-react',
  [AGENT_NAMES.ReFlect]: 'agent-reflect',
  [AGENT_NAMES.TME]: 'agent-tme',
  [AGENT_NAMES.RAG]: 'agent-rag',
  system: 'agent-system',
};

/**
 * Event type icons.
 */
const EVENT_ICONS = {
  [EVENT_TYPES.thought]: '💭',
  [EVENT_TYPES.action]: '⚡',
  [EVENT_TYPES.observation]: '👁️',
  [EVENT_TYPES.plan]: '📋',
  [EVENT_TYPES.scene]: '🎬',
  [EVENT_TYPES.memory_update]: '💾',
  [EVENT_TYPES.rag_result]: '🔍',
  [EVENT_TYPES.error]: '❌',
  [EVENT_TYPES.complete]: '✅',
  [EVENT_TYPES.status]: '📢',
};

/** Content length threshold for expandable content */
const EXPAND_THRESHOLD = 300;

/**
 * Format timestamp for display.
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
 * Single event item component with copy and expand functionality.
 */
function EventItem({ event }) {
  const [isExpanded, setIsExpanded] = useState(false);
  const [copied, setCopied] = useState(false);
  
  const agentClass = AGENT_COLORS[event.agent] || 'agent-default';
  const icon = EVENT_ICONS[event.event] || '📌';
  const content = event.content || '';
  const isLongContent = content.length > EXPAND_THRESHOLD;
  
  // Copy content to clipboard
  const handleCopy = async () => {
    try {
      const textToCopy = `[${event.agent}] ${event.event}\n${content}`;
      await navigator.clipboard.writeText(textToCopy);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error('Failed to copy:', err);
    }
  };
  
  // Display content (truncated or full)
  const displayContent = isLongContent && !isExpanded 
    ? content.substring(0, EXPAND_THRESHOLD) + '...' 
    : content;
  
  return (
    <div className={`event-item ${agentClass} event-${event.event}`}>
      <div className="event-header">
        <span className="event-icon">{icon}</span>
        <span className="event-agent">{event.agent}</span>
        <span className="event-type">{event.event}</span>
        <span className="event-time">{formatTime(event.timestamp || event.receivedAt)}</span>
        <div className="event-actions">
          <button 
            className={`btn-copy ${copied ? 'copied' : ''}`} 
            onClick={handleCopy}
            title="Copy content"
          >
            {copied ? '✓' : '📋'}
          </button>
        </div>
      </div>
      <div className={`event-content ${isExpanded ? 'expanded' : ''}`}>
        <pre className="content-text">{displayContent}</pre>
        {isLongContent && (
          <button 
            className="btn-expand" 
            onClick={() => setIsExpanded(!isExpanded)}
          >
            {isExpanded ? '▲ Show less' : `▼ Show more (${content.length} chars)`}
          </button>
        )}
      </div>
      {event.metadata?.sources && (
        <div className="event-sources">
          <span className="sources-label">Sources:</span>
          {event.metadata.sources.map((source, i) => (
            <span key={i} className="source-tag">{source}</span>
          ))}
        </div>
      )}
      {event.metadata?.final_output && (
        <div className="event-final-output">
          <div className="final-output-header">
            <span>📄 Full Output ({event.metadata.final_output.length} chars)</span>
            <button 
              className="btn-copy-full"
              onClick={async () => {
                await navigator.clipboard.writeText(event.metadata.final_output);
                alert('Full output copied!');
              }}
            >
              📋 Copy Full Output
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

/**
 * LiveAgentFeed component.
 */
function LiveAgentFeed() {
  const events = useSelector(selectEvents);
  const status = useSelector(selectStatus);
  const currentAgent = useSelector(selectCurrentAgent);
  const feedRef = useRef(null);
  
  // Auto-scroll to bottom when new events arrive
  useEffect(() => {
    if (feedRef.current) {
      feedRef.current.scrollTop = feedRef.current.scrollHeight;
    }
  }, [events]);
  
  const isRunning = status === 'running' || status === 'connecting';
  
  return (
    <div className="live-agent-feed">
      <div className="feed-header">
        <h3 className="section-title">
          <span className="feed-icon">📡</span>
          Live Agent Feed
        </h3>
        <div className="feed-status">
          {isRunning && (
            <>
              <span className="status-dot active"></span>
              <span className="status-text">
                {currentAgent ? `${currentAgent} active` : 'Processing...'}
              </span>
            </>
          )}
          {status === 'complete' && (
            <>
              <span className="status-dot complete"></span>
              <span className="status-text">Complete</span>
            </>
          )}
          {status === 'idle' && (
            <>
              <span className="status-dot idle"></span>
              <span className="status-text">Waiting</span>
            </>
          )}
        </div>
      </div>
      
      <div className="feed-legend">
        <span className="legend-item agent-preact">preAct</span>
        <span className="legend-item agent-react">ReAct</span>
        <span className="legend-item agent-reflect">ReFlect</span>
        <span className="legend-item agent-rag">RAG</span>
        <span className="legend-item agent-tme">TME</span>
      </div>
      
      <div className="feed-container" ref={feedRef}>
        {events.length === 0 ? (
          <div className="feed-empty">
            <span className="empty-icon">🎯</span>
            <p>Agent events will appear here in real-time</p>
            <p className="empty-hint">Submit a query to start generation</p>
          </div>
        ) : (
          events.map((event) => (
            <EventItem key={event.id} event={event} />
          ))
        )}
        
        {isRunning && (
          <div className="feed-typing">
            <span className="typing-dot"></span>
            <span className="typing-dot"></span>
            <span className="typing-dot"></span>
          </div>
        )}
      </div>
    </div>
  );
}

export default LiveAgentFeed;

