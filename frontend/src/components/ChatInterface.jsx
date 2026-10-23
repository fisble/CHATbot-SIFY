/**
 * Main chat interface with PreAct plan preview and live agent streaming.
 */

import SourcesPanel from './SourcesPanel';

import { useState, useEffect, useRef, useCallback } from 'react';
import { useSelector, useDispatch } from 'react-redux';
import {
  selectSelectedDomain,
  selectSessionId,
  selectLoading,
  selectAvailableDomains,
  setSelectedDomain,
  setQuery,
  setSessionId,
  fetchDomains,
} from '../store/querySlice';
import {
  selectEvents,
  selectScenes,
  selectFinalStoryboard,
  selectMasterPlan,
  selectStatus,
  selectCurrentAgent,
  clearEvents,
  setStatus,
  addEvent,
  setMasterPlan,
} from '../store/agentSlice';
import { connectAndStart, disconnect } from '../utils/wsClient';
import ThinkingPanel from './ThinkingPanel';
import StoryboardDisplay from './StoryboardDisplay';
import PlanPreview from './PlanPreview';

const MODES = {
  NORMAL: 'normal',
  MULTIAGENT: 'multiagent',
  COMPARE: 'compare',
  VISION: 'vision',
};

// Simplified domain display (optional, auto-detect when not specified)
const DOMAIN_LABELS = {
  product_demo: 'Product Demo',
  education: 'Education',
  medical: 'Healthcare',
  marketing: 'Marketing',
  film_style: 'Film',
  gaming: 'Gaming',
  healthcare: 'Healthcare',
  finance: 'Finance',
  hr: 'HR',
  cloud: 'Cloud',
  software: 'Software',
  sales: 'Sales',
  general: 'General',
};

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';
const WS_BASE_URL = import.meta.env.VITE_WS_URL || 'ws://localhost:8000';

/**
 * Format content for display - handles markdown-style formatting
 */
function formatContentForDisplay(content, sources = []) {
  if (!content) return '';
  
  // Check if content is JSON (starts with { or [)
  const trimmed = content.trim();
  if ((trimmed.startsWith('{') || trimmed.startsWith('[')) && (trimmed.endsWith('}') || trimmed.endsWith(']'))) {
    try {
      const parsed = JSON.parse(trimmed);
      return (
        <pre className="json-content">
          <code>{JSON.stringify(parsed, null, 2)}</code>
        </pre>
      );
    } catch {
      // Not valid JSON, continue with normal formatting
    }
  }
  
  // Helper function to process citations in text and return React elements
  const processCitations = (text, keyPrefix = '') => {
    if (!sources || sources.length === 0) return text;
    
    const parts = [];
    const citationRegex = /\[(\d+)(?:,\s*(\d+))*\]/g;
    let lastIndex = 0;
    let match;
    let citationKeyCounter = 0;
    
    while ((match = citationRegex.exec(text)) !== null) {
      // Add text before citation
      if (match.index > lastIndex) {
        const beforeText = text.substring(lastIndex, match.index);
        if (beforeText) {
          parts.push(<span key={`${keyPrefix}-text-${lastIndex}`}>{beforeText}</span>);
        }
      }
      
      // Extract citation numbers
      const citationNumbers = [];
      for (let i = 1; i < match.length; i++) {
        const num = match[i];
        if (num && !isNaN(parseInt(num)) && parseInt(num) <= sources.length) {
          citationNumbers.push(parseInt(num));
        }
      }
      
      // Add citation links
      citationNumbers.forEach(num => {
        const sourceIndex = num - 1;
        const source = sources[sourceIndex];
        if (source) {
          parts.push(
            <sup key={`${keyPrefix}-cite-${match.index}-${num}-${citationKeyCounter++}`}>
              <a
                href={source.url}
                target="_blank"
                rel="noopener noreferrer"
                style={{
                  color: '#6b7cff',
                  textDecoration: 'none',
                  fontWeight: '600',
                  fontSize: '0.85em',
                  marginLeft: '2px',
                  cursor: 'pointer'
                }}
                onMouseEnter={(e) => {
                  e.target.style.textDecoration = 'underline';
                }}
                onMouseLeave={(e) => {
                  e.target.style.textDecoration = 'none';
                }}
                title={source.title}
              >
                [{num}]
              </a>
            </sup>
          );
        } else {
          parts.push(<sup key={`${keyPrefix}-cite-${match.index}-${num}-${citationKeyCounter++}`} style={{ color: '#6b7cff' }}>[{num}]</sup>);
        }
      });
      
      lastIndex = match.index + match[0].length;
    }
    
    // Add remaining text
    if (lastIndex < text.length) {
      const remainingText = text.substring(lastIndex);
      if (remainingText) {
        parts.push(<span key={`${keyPrefix}-text-${lastIndex}`}>{remainingText}</span>);
      }
    }
    
    // If no citations found, return original text
    return parts.length === 0 ? text : parts;
  };
  
  // Split content into paragraphs and format
  const lines = content.split('\n');
  const elements = [];
  let currentList = [];
  let listType = null;
  
  const flushList = () => {
    if (currentList.length > 0) {
      elements.push(
        <ul key={`list-${elements.length}`} className="content-list">
          {currentList.map((item, i) => {
            const processed = processCitations(item, `list-${i}`);
            return <li key={i}>{Array.isArray(processed) ? processed : processed}</li>;
          })}
        </ul>
      );
      currentList = [];
      listType = null;
    }
  };
  
  lines.forEach((line, index) => {
    const trimmedLine = line.trim();
    
    // Headers
    if (trimmedLine.startsWith('## ')) {
      flushList();
      const headerText = trimmedLine.slice(3);
      const processed = processCitations(headerText, `h2-${index}`);
      elements.push(<h2 key={index} className="content-heading">{Array.isArray(processed) ? processed : processed}</h2>);
    } else if (trimmedLine.startsWith('### ')) {
      flushList();
      const headerText = trimmedLine.slice(4);
      const processed = processCitations(headerText, `h3-${index}`);
      elements.push(<h3 key={index} className="content-subheading">{Array.isArray(processed) ? processed : processed}</h3>);
    } else if (trimmedLine.startsWith('# ')) {
      flushList();
      const headerText = trimmedLine.slice(2);
      const processed = processCitations(headerText, `h1-${index}`);
      elements.push(<h1 key={index} className="content-title">{Array.isArray(processed) ? processed : processed}</h1>);
    }
    // Bullet points
    else if (trimmedLine.startsWith('- ') || trimmedLine.startsWith('* ')) {
      currentList.push(trimmedLine.slice(2));
    }
    // Numbered lists
    else if (/^\d+\.\s/.test(trimmedLine)) {
      currentList.push(trimmedLine.replace(/^\d+\.\s/, ''));
    }
    // Bold text within line
    else if (trimmedLine.length > 0) {
      flushList();
      
      // Process line with citations
      const parts = [];
      const citationRegex = /\[(\d+)(?:,\s*(\d+))*\]/g;
      let lastIndex = 0;
      let match;
      
      while ((match = citationRegex.exec(trimmedLine)) !== null) {
        // Add text before citation
        if (match.index > lastIndex) {
          const beforeText = trimmedLine.substring(lastIndex, match.index);
          if (beforeText) {
            // Handle bold formatting in the text
            const boldFormatted = beforeText.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
            parts.push(<span key={`text-${lastIndex}`} dangerouslySetInnerHTML={{ __html: boldFormatted }} />);
          }
        }
        
        // Add citation(s)
        const citationNumbers = [];
        for (let i = 1; i < match.length; i++) {
          const num = match[i];
          if (num && !isNaN(parseInt(num)) && parseInt(num) <= sources.length) {
            citationNumbers.push(parseInt(num));
          }
        }
        
        citationNumbers.forEach(num => {
          const sourceIndex = num - 1;
          const source = sources && Array.isArray(sources) && sourceIndex >= 0 && sourceIndex < sources.length ? sources[sourceIndex] : null;
          if (source && source.url) {
            parts.push(
              <sup key={`cite-${match.index}-${num}`}>
                <a
                  href={source.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  style={{
                    color: '#6b7cff',
                    textDecoration: 'none',
                    fontWeight: '600',
                    fontSize: '0.9em',
                    marginLeft: '2px',
                    cursor: 'pointer'
                  }}
                  onMouseEnter={(e) => {
                    e.target.style.textDecoration = 'underline';
                  }}
                  onMouseLeave={(e) => {
                    e.target.style.textDecoration = 'none';
                  }}
                  title={source.title || source.url}
                >
                  [{num}]
                </a>
              </sup>
            );
          } else {
            parts.push(<sup key={`cite-${match.index}-${num}`} style={{ color: '#6b7cff' }}>[{num}]</sup>);
          }
        });
        
        lastIndex = match.index + match[0].length;
      }
      
      // Add remaining text
      if (lastIndex < trimmedLine.length) {
        const remainingText = trimmedLine.substring(lastIndex);
        if (remainingText) {
          const boldFormatted = remainingText.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
          parts.push(<span key={`text-${lastIndex}`} dangerouslySetInnerHTML={{ __html: boldFormatted }} />);
        }
      }
      
      // If no citations found, use original formatting
      if (parts.length === 0) {
        const formattedLine = trimmedLine.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
        elements.push(
          <p key={index} className="content-paragraph" dangerouslySetInnerHTML={{ __html: formattedLine }} />
        );
      } else {
        elements.push(
          <p key={index} className="content-paragraph">{parts}</p>
        );
      }
    }
    // Empty line - end of paragraph/list
    else if (trimmedLine === '' && currentList.length > 0) {
      flushList();
    }
  });
  
  flushList(); // Flush any remaining list items
  
  return <div className="formatted-content">{elements}</div>;
}

function ChatInterface({ mode }) {
  const dispatch = useDispatch();
  const chatContainerRef = useRef(null);
  const eventSourceRef = useRef(null);
  
  // Redux state
  const selectedDomain = useSelector(selectSelectedDomain);
  const sessionId = useSelector(selectSessionId);
  const loading = useSelector(selectLoading);
  const availableDomains = useSelector(selectAvailableDomains);
  const events = useSelector(selectEvents);
  const scenes = useSelector(selectScenes);
  const finalStoryboard = useSelector(selectFinalStoryboard);
  const masterPlan = useSelector(selectMasterPlan);
  const status = useSelector(selectStatus);
  const currentAgent = useSelector(selectCurrentAgent);
  
  // Local state
  const [inputValue, setInputValue] = useState('');
  const [messages, setMessages] = useState([]);
  const [showThinking, setShowThinking] = useState(true);
  const [normalResponse, setNormalResponse] = useState('');
  const [normalSources, setNormalSources] = useState([]);
  const [normalLoading, setNormalLoading] = useState(false);
  const [isSearching, setIsSearching] = useState(false);
  const [forceWebSearch, setForceWebSearch] = useState(false);
  const [multiagentLoading, setMultiagentLoading] = useState(false);
  const [pendingPlan, setPendingPlan] = useState(null);
  const [showPlanPreview, setShowPlanPreview] = useState(false);
  
  // Vision mode state
  const fileInputRef = useRef(null);
  const [selectedImage, setSelectedImage] = useState(null);
  const [imageDataUrl, setImageDataUrl] = useState(null);
  const [imageDescription, setImageDescription] = useState('');
  const [isProcessingImage, setIsProcessingImage] = useState(false);
  const [imageError, setImageError] = useState(null);
  
  // Fetch domains on mount
  useEffect(() => {
    dispatch(fetchDomains());
  }, [dispatch]);
  
  // Auto-scroll
  useEffect(() => {
    if (chatContainerRef.current) {
      chatContainerRef.current.scrollTop = chatContainerRef.current.scrollHeight;
    }
  }, [messages, events, scenes, normalResponse]);
  
  // Update when storyboard is complete
  useEffect(() => {
    if (status === 'complete' && (finalStoryboard || scenes.length > 0)) {
      setMultiagentLoading(false);
      if (mode !== MODES.COMPARE) {
        setMessages(prev => [
          ...prev,
          {
            type: 'assistant',
            responseType: 'multiagent',
            content: 'storyboard',
            data: { masterPlan, scenes, finalStoryboard },
            timestamp: new Date(),
          }
        ]);
      }
    }
  }, [status, finalStoryboard, scenes, masterPlan, mode]);
  
  // SSE event handler
  const connectSSE = useCallback((sessionId) => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
    }
    
    const eventSource = new EventSource(`${API_BASE_URL}/api/events/${sessionId}`);
    eventSourceRef.current = eventSource;
    
    eventSource.onopen = () => {
      console.log('SSE connected');
      dispatch(setStatus('running'));
    };
    
    eventSource.onerror = (error) => {
      console.error('SSE error:', error);
    };
    
    eventSource.addEventListener('connected', (e) => {
      console.log('SSE connected event:', JSON.parse(e.data));
    });
    
    eventSource.addEventListener('status', (e) => {
      const data = JSON.parse(e.data);
      dispatch(addEvent(data));
    });
    
    eventSource.addEventListener('thought', (e) => {
      const data = JSON.parse(e.data);
      dispatch(addEvent(data));
    });
    
    eventSource.addEventListener('action', (e) => {
      const data = JSON.parse(e.data);
      dispatch(addEvent(data));
    });
    
    eventSource.addEventListener('observation', (e) => {
      const data = JSON.parse(e.data);
      dispatch(addEvent(data));
    });
    
    eventSource.addEventListener('rag_result', (e) => {
      const data = JSON.parse(e.data);
      dispatch(addEvent(data));
    });
    
    eventSource.addEventListener('memory_update', (e) => {
      const data = JSON.parse(e.data);
      dispatch(addEvent(data));
    });
    
    eventSource.addEventListener('scene', (e) => {
      const data = JSON.parse(e.data);
      dispatch(addEvent(data));
      
      // Check if this is the final output event or react output event
      const eventType = data.metadata?.event_type;
      const finalOutput = data.metadata?.final_output;
      
      if ((eventType === 'final_output' || eventType === 'react_output') && finalOutput) {
        console.log('[SSE] Scene event with final output:', eventType, 'length:', finalOutput.length);
        
        // Add final output to messages
        setMessages(prev => {
          // Check if this exact output was already added
          const hasOutput = prev.some(m => 
            m.responseType === 'multiagent' && 
            m.content === finalOutput
          );
          if (!hasOutput) {
            return [
              ...prev,
              {
                type: 'assistant',
                responseType: 'multiagent',
                content: finalOutput,
                quality_score: data.metadata?.quality_score,
                detectedDomain: data.metadata?.detected_domain,
                timestamp: new Date(),
              }
            ];
          }
          return prev;
        });
      }
    });
    
    eventSource.addEventListener('plan', (e) => {
      const data = JSON.parse(e.data);
      dispatch(addEvent(data));
      if (data.metadata?.master_plan) {
        dispatch(setMasterPlan(data.metadata.master_plan));
      }
    });
    
    eventSource.addEventListener('complete', (e) => {
      const data = JSON.parse(e.data);
      dispatch(addEvent(data));
      
      console.log('[SSE] Complete event:', data.agent, 'has final_output:', !!data.metadata?.final_output);
      
      // Helper to add final output message
      const addFinalOutput = (output, metadata = {}) => {
        if (!output) return;
        setMessages(prev => {
          // Check if this exact output was already added
          const hasOutput = prev.some(m => 
            m.responseType === 'multiagent' && 
            m.content === output
          );
          if (!hasOutput) {
            console.log('[SSE] Adding final output to messages, length:', output.length);
            return [
              ...prev,
              {
                type: 'assistant',
                responseType: 'multiagent',
                content: output,
                quality_score: metadata.quality_score,
                detectedDomain: metadata.detected_domain,
                timestamp: new Date(),
              }
            ];
          }
          return prev;
        });
      };
      
      // Capture final output from ReFlect agent (case-insensitive check)
      const agentLower = (data.agent || '').toLowerCase();
      if (agentLower === 'reflect' && data.metadata?.final_output) {
        console.log('[SSE] ReFlect completed with final output');
        addFinalOutput(data.metadata.final_output, data.metadata);
      }
      
      // Handle system complete event
      if (agentLower === 'system') {
        dispatch(setStatus('complete'));
        setMultiagentLoading(false);
        setShowThinking(false);
        
        // Always try to add final output from system complete
        if (data.metadata?.final_output) {
          console.log('[SSE] System complete with final output');
          addFinalOutput(data.metadata.final_output, data.metadata);
        }
        
        eventSource.close();
      } else {
        console.log(`[SSE] Agent ${data.agent} completed`);
      }
    });
    
    eventSource.addEventListener('error', (e) => {
      console.error('[SSE] Error event received:', e);
      try {
        // Try to parse if there's data
        if (e.data) {
          const data = JSON.parse(e.data);
          dispatch(addEvent(data));
        }
      } catch (parseError) {
        console.error('[SSE] Error parsing error event data:', parseError);
      }
      dispatch(setStatus('error'));
      setMultiagentLoading(false);
      eventSource.close();
    });
    
    // Also handle native onerror for connection errors
    eventSource.onerror = (e) => {
      console.error('[SSE] Connection error:', e);
      if (eventSource.readyState === EventSource.CLOSED) {
        console.log('[SSE] EventSource connection closed');
      }
    };
    
    eventSource.addEventListener('heartbeat', (e) => {
      console.log('SSE heartbeat');
    });
    
    return eventSource;
  }, [dispatch]);
  
  // Generate PreAct plan - domain is optional, will auto-detect
  const generatePlan = async (query, domain = null) => {
    setMultiagentLoading(true);
    dispatch(clearEvents());
    
    try {
      const response = await fetch(`${API_BASE_URL}/api/preact-plan`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query, domain: domain || undefined }),
      });
      
      const data = await response.json();
      
      // Add planning events
      if (data.events) {
        data.events.forEach(event => {
          dispatch(addEvent(event));
        });
      }
      
      // Extract reasoning plan with steps
      const reasoningPlan = data.reasoning_plan || data.plan?.reasoning_plan || {};
      const planWithSteps = {
        ...data.plan,
        reasoning_plan: reasoningPlan,
        steps: reasoningPlan.steps || data.plan?.steps || [],
        task_understanding: reasoningPlan.task_understanding || data.plan?.task_understanding || '',
        approach: reasoningPlan.approach || data.plan?.approach || '',
        constraints: reasoningPlan.constraints || data.plan?.constraints || [],
        success_criteria: reasoningPlan.success_criteria || data.plan?.success_criteria || [],
        estimated_complexity: reasoningPlan.estimated_complexity || data.plan?.estimated_complexity || 'moderate'
      };
      
      setPendingPlan({
        sessionId: data.session_id,
        plan: planWithSteps,
        mermaid: data.mermaid_diagram,
        events: data.events,
        stepCount: data.step_count || reasoningPlan.steps?.length || 0
      });
      
      dispatch(setSessionId(data.session_id));
      setShowPlanPreview(true);
      setMultiagentLoading(false);
      
    } catch (error) {
      console.error('Error generating plan:', error);
      setMultiagentLoading(false);
    }
  };
  
  // State for plan refinement loading
  const [isRefining, setIsRefining] = useState(false);
  
  // Handle plan refinement via chat
  const handlePlanRefine = async (refinementData) => {
    if (!pendingPlan) return;
    
    setIsRefining(true);
    
    try {
      const response = await fetch(`${API_BASE_URL}/api/preact-plan/refine`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: pendingPlan.sessionId,
          user_responses: refinementData.user_responses || {},
          chat_message: refinementData.chat_message || '',
          chat_history: refinementData.chat_history || [],
        }),
      });
      
      const data = await response.json();
      
      if (data.status === 'plan_refined') {
        // Update pending plan with refined version
        const reasoningPlan = data.reasoning_plan || data.plan?.reasoning_plan || {};
        const planWithSteps = {
          ...data.plan,
          reasoning_plan: reasoningPlan,
          steps: reasoningPlan.steps || data.plan?.steps || [],
          task_understanding: reasoningPlan.task_understanding || '',
          approach: reasoningPlan.approach || '',
          constraints: reasoningPlan.constraints || [],
          success_criteria: reasoningPlan.success_criteria || [],
          estimated_complexity: reasoningPlan.estimated_complexity || 'moderate',
          clarification_questions: reasoningPlan.clarification_questions || [],
          chat_history: data.chat_history || [],
          is_refined: true,
        };
        
        setPendingPlan({
          ...pendingPlan,
          plan: planWithSteps,
          mermaid: data.mermaid_diagram || pendingPlan.mermaid,
          events: data.events || pendingPlan.events,
          stepCount: data.step_count || reasoningPlan.steps?.length || 0,
          is_refined: true,
          refinement_count: data.refinement_count || 1,
        });
        
        // Add events to thinking panel
        if (data.events) {
          data.events.forEach(event => {
            dispatch(addEvent(event));
          });
        }
      }
    } catch (error) {
      console.error('Error refining plan:', error);
    } finally {
      setIsRefining(false);
    }
  };
  
  // Legacy: Handle plan enhancement - regenerate with additional instructions
  const handlePlanEnhance = async (enhanceText) => {
    if (!pendingPlan || !enhanceText.trim()) return;
    
    // Use the new refinement API
    await handlePlanRefine({
      chat_message: enhanceText,
      user_responses: {},
      chat_history: pendingPlan.plan?.chat_history || [],
    });
  };
  
  // Execute approved plan
  const executePlan = async (enhancedPlan = null) => {
    const planToExecute = enhancedPlan || pendingPlan;
    if (!planToExecute) return;
    
    setMultiagentLoading(true);
    setShowPlanPreview(false);
    
    try {
      // Include any confirmed steps and clarification responses
      // Include web search flag (only when user explicitly enables it)
      const executePayload = {
        session_id: planToExecute.sessionId || pendingPlan.sessionId,
        approved: true,
        confirmed_steps: enhancedPlan?.confirmed_steps || undefined,
        clarification_responses: enhancedPlan?.clarification_responses || undefined,
        enable_web_search: forceWebSearch,  // Pass web search flag to backend
      };
      
      const response = await fetch(`${API_BASE_URL}/api/execute`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(executePayload),
      });
      
      const data = await response.json();
      
      if (data.status === 'executing') {
        // Connect to SSE for live updates
        const sessionId = planToExecute.sessionId || pendingPlan.sessionId;
        connectSSE(sessionId);
        setShowThinking(true);
        // Reset web search flag after sending (similar to normal chat)
        setForceWebSearch(false);
      }
      
    } catch (error) {
      console.error('Error executing plan:', error);
      setMultiagentLoading(false);
    }
  };
  
  // Cancel plan
  const cancelPlan = async () => {
    if (pendingPlan) {
      try {
        await fetch(`${API_BASE_URL}/api/execute`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            session_id: pendingPlan.sessionId,
            approved: false,
          }),
        });
      } catch (error) {
        console.error('Error cancelling plan:', error);
      }
    }
    
    setPendingPlan(null);
    setShowPlanPreview(false);
    setMultiagentLoading(false);
  };
  
  // Run with WebSocket (legacy mode)
  const runWithWebSocket = async (domain, query) => {
    setMultiagentLoading(true);
    dispatch(clearEvents());
    
    try {
      // Create session
      const response = await fetch(`${API_BASE_URL}/api/agent/run`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ domain, query }),
      });
      
      const data = await response.json();
      dispatch(setSessionId(data.session_id));
      
      // Connect and start
      await connectAndStart(data.session_id, dispatch);
      setShowThinking(true);
      
    } catch (error) {
      console.error('Error starting multi-agent:', error);
      setMultiagentLoading(false);
    }
  };
  
  // Vision mode: Process image with vision API
  const processImageWithVision = async (dataUrl) => {
    setIsProcessingImage(true);
    setImageError(null);
    
    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 30000); // 30s timeout
      
      const response = await fetch(`${API_BASE_URL}/vision`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          image_data_url: dataUrl
        }),
        signal: controller.signal
      });
      
      clearTimeout(timeoutId);
      
      if (!response.ok) {
        throw new Error(`Vision API error: ${response.status}`);
      }
      
      const data = await response.json();
      
      if (data.error) {
        throw new Error(data.error);
      }
      
      const description = data.reply || 'No description available';
      setImageDescription(description);
      setInputValue(prev => prev ? `${prev}\n\n${description}` : description);
      setIsProcessingImage(false);
      return description;
    } catch (error) {
      setIsProcessingImage(false);
      const errorMessage = error.name === 'AbortError' 
        ? 'Vision API request timed out. Please try again.'
        : error.message || 'Failed to process image';
      setImageError(errorMessage);
      console.error('Vision API error:', error);
      return null;
    }
  };
  
  // Vision mode: Call vision backend
  const callVisionBackend = async () => {
    if (!imageDataUrl) {
      return null;
    }
    
    setIsProcessingImage(true);
    setImageError(null);
    
    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 30000); // 30s timeout
      
      const response = await fetch(`${API_BASE_URL}/vision`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          image_data_url: imageDataUrl
        }),
        signal: controller.signal
      });
      
      clearTimeout(timeoutId);
      
      if (!response.ok) {
        throw new Error(`Vision API error: ${response.status}`);
      }
      
      const data = await response.json();
      
      if (data.error) {
        throw new Error(data.error);
      }
      
      setIsProcessingImage(false);
      return data.reply || 'No response from vision model';
    } catch (error) {
      setIsProcessingImage(false);
      const errorMessage = error.name === 'AbortError' 
        ? 'Vision API request timed out. Please try again.'
        : error.message || 'Vision backend failed';
      setImageError(errorMessage);
      console.error('Vision backend error:', error);
      return `❌ Error: ${errorMessage}`;
    }
  };
  
  // Normal chat - domain is optional, will auto-detect
  const runNormalChat = async (query, domain = null) => {
    setNormalLoading(true);
    setNormalResponse('');
    
    try {
      const wsUrl = `${WS_BASE_URL}/ws/direct/${Date.now()}`;
      const ws = new WebSocket(wsUrl);
      
      ws.onopen = () => {
        // Send query, domain (optional), and web search preference
        ws.send(JSON.stringify({ 
          query, 
          domain: domain || undefined,
          force_web_search: forceWebSearch 
        }));
        // Reset force web search after sending
        setForceWebSearch(false);
      };
      
      ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        if (data.type === 'start') {
          // Auto-detected domain info
          console.log('Chat started, detected domain:', data.domain);
          setIsSearching(false);
        } else if (data.type === 'status') {
          // Handle status updates (like web search status)
          if (data.status === 'searching') {
            setIsSearching(true);
            // Optionally show status message in UI
            if (mode === MODES.NORMAL || mode === MODES.COMPARE) {
              setNormalResponse('🔍 Searching the web for current information...\n\n');
            }
          } else if (data.status === 'search_complete') {
            setIsSearching(false);
            // Clear the searching message when complete
            if (mode === MODES.NORMAL || mode === MODES.COMPARE) {
              setNormalResponse('');
            }
          } else if (data.status === 'search_error') {
            setIsSearching(false);
            // Clear the searching message on error
            if (mode === MODES.NORMAL || mode === MODES.COMPARE) {
              setNormalResponse('');
            }
          }
        } else if (data.type === 'chunk') {
          setNormalResponse(prev => prev + data.content);
          setIsSearching(false); // Search done, now streaming answer
        } else if (data.type === 'complete') {
          setIsSearching(false);
          setNormalLoading(false);
          
          // Store sources for compare mode (must happen before setting messages)
          // Always store sources if they exist, so compare mode can display them
          // Also store if web_search_used is true (even if sources is empty) to show search was attempted
          if (data.web_search_used && data.sources && Array.isArray(data.sources)) {
            setNormalSources(data.sources);
            console.log('[WEBSOCKET] Sources received and stored:', data.sources.length, 'sources');
          } else if (data.sources && Array.isArray(data.sources) && data.sources.length > 0) {
            setNormalSources(data.sources);
            console.log('[WEBSOCKET] Sources received and stored:', data.sources.length, 'sources');
          }
          
          if (mode === MODES.NORMAL) {
            // Always include sources if they were provided or if web search was used
            const sourcesToInclude = data.sources && Array.isArray(data.sources) ? data.sources : [];
            setMessages(prev => [
              ...prev,
              {
                type: 'assistant',
                responseType: 'normal',
                content: data.content,
                detectedDomain: data.domain,
                sources: sourcesToInclude,
                timestamp: new Date(),
              }
            ]);
            // Also update normalSources for consistency
            if (sourcesToInclude.length > 0) {
              setNormalSources(sourcesToInclude);
            }
          }
        } else if (data.type === 'error') {
          setNormalLoading(false);
          setIsSearching(false);
          console.error('Normal chat error:', data.content);
          
          // Display error message to user
          const errorMessage = data.content || 'An error occurred while processing your request. Please try again.';
          setMessages(prev => [
            ...prev,
            {
              type: 'assistant',
              responseType: 'error',
              content: `❌ Error: ${errorMessage}`,
              timestamp: new Date(),
            }
          ]);
          
          // Also update normalResponse to show error
          setNormalResponse(errorMessage);
        }
      };
      
      ws.onerror = (error) => {
        setNormalLoading(false);
        setIsSearching(false);
        console.error('WebSocket error:', error);
        // Try fallback, but also show error message
        setMessages(prev => [
          ...prev,
          {
            type: 'assistant',
            responseType: 'error',
            content: 'Connection error. Trying alternative method...',
            timestamp: new Date(),
          }
        ]);
        fallbackNormalChat(query, domain);
      };
      
      ws.onclose = (event) => {
        // Only show error if connection closed unexpectedly (not normal completion)
        if (event.code !== 1000 && normalLoading) {
          setNormalLoading(false);
          setIsSearching(false);
          if (!normalResponse) {
            // Only show error if we didn't get a response
            setMessages(prev => [
              ...prev,
              {
                type: 'assistant',
                responseType: 'error',
                content: 'Connection closed unexpectedly. Please try again.',
                timestamp: new Date(),
              }
            ]);
          }
        }
      };
      
    } catch (error) {
      console.error('Normal chat error:', error);
      fallbackNormalChat(query, domain);
    }
  };
  
  const fallbackNormalChat = async (query, domain = null) => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/chat/direct`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query, domain: domain || undefined }),
      });
      
      const data = await response.json();
      setNormalResponse(data.response);
      setNormalLoading(false);
      
      if (mode === MODES.NORMAL) {
        setMessages(prev => [
          ...prev,
          {
            type: 'assistant',
            responseType: 'normal',
            content: data.response,
            detectedDomain: data.domain,
            timestamp: new Date(),
          }
        ]);
      }
    } catch (error) {
      console.error('Fallback error:', error);
      setNormalLoading(false);
      setMessages(prev => [
        ...prev,
        {
          type: 'assistant',
          responseType: 'error',
          content: 'Sorry, there was an error processing your request. Please try again.',
          timestamp: new Date(),
        }
      ]);
    }
  };
  
  const handleSubmit = async (e) => {
    e.preventDefault();
    
    // Vision mode handling - completely separate from other modes
    if (mode === MODES.VISION) {
      // Check if image exists
      if (!imageDataUrl && !inputValue.trim()) {
        setImageError('Please upload an image or enter a question');
        return;
      }
      
      // If image exists but not processed yet, process it first
      if (imageDataUrl && !imageDescription) {
        await processImageWithVision(imageDataUrl);
        return; // Wait for image to be processed
      }
      
      // Prepare user message
      const userMessage = inputValue.trim() || imageDescription;
      
      if (!userMessage) {
        return;
      }
      
      // Add user message to chat
      setMessages(prev => [
        ...prev,
        {
          type: 'user',
          content: userMessage,
          imageDataUrl: imageDataUrl,
          timestamp: new Date(),
        }
      ]);
      
      // Call vision backend
      const visionReply = await callVisionBackend();
      
      if (visionReply) {
        setMessages(prev => [
          ...prev,
          {
            type: 'assistant',
            responseType: 'vision',
            content: visionReply,
            timestamp: new Date(),
          }
        ]);
      }
      
      // Clean up image state after sending (only in Vision mode)
      setInputValue('');
      setSelectedImage(null);
      setImageDataUrl(null);
      setImageDescription('');
      setImageError(null);
      return;
    }
    
    // Other modes (Normal, Multi-Agent, Compare) - no vision processing
    if (!inputValue.trim()) return;
    
    const userMessage = inputValue.trim();
    
    setMessages(prev => [
      ...prev,
      {
        type: 'user',
        content: userMessage,
        domain: selectedDomain || 'auto',
        timestamp: new Date(),
      }
    ]);
    
    setInputValue('');
    dispatch(clearEvents());
    disconnect();
    dispatch(setStatus('idle'));
    setNormalResponse('');
    setNormalSources([]);
    setIsSearching(false);
    setPendingPlan(null);
    // Don't reset forceWebSearch here - let it reset after sending
    
    if (mode === MODES.NORMAL) {
      // Pass query first, domain is optional
      runNormalChat(userMessage, selectedDomain);
    } else if (mode === MODES.MULTIAGENT) {
      // Use PreAct plan workflow - domain optional
      generatePlan(userMessage, selectedDomain);
    } else if (mode === MODES.COMPARE) {
      runNormalChat(userMessage, selectedDomain);
      generatePlan(userMessage, selectedDomain);
    }
  };
  
  const handleNewChat = () => {
    disconnect();
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
    }
    dispatch(clearEvents());
    dispatch(setStatus('idle'));
    setMessages([]);
    setShowThinking(true);
    setInputValue('');
    setNormalResponse('');
    setNormalSources([]);
    setIsSearching(false);
    setForceWebSearch(false);
    setNormalLoading(false);
    setMultiagentLoading(false);
    setPendingPlan(null);
    setShowPlanPreview(false);
    // Clean up vision state
    setSelectedImage(null);
    setImageDataUrl(null);
    setImageDescription('');
    setImageError(null);
    setIsProcessingImage(false);
  };
  
  const isRunning = status === 'running' || status === 'connecting' || normalLoading || multiagentLoading || isProcessingImage;
  
  return (
    <div className="chat-interface">
      {/* Sidebar - Cleaner, domain is optional */}
      <aside className="chat-sidebar">
        <button className="new-chat-btn" onClick={handleNewChat}>
          + New Chat
        </button>
        
        <div className="domain-section">
          <h3>Domain (Optional)</h3>
          <p className="domain-hint">Auto-detects from your query</p>
          <div className="domain-list">
            <button
              className={`domain-btn ${!selectedDomain ? 'active' : ''}`}
              onClick={() => dispatch(setSelectedDomain(null))}
              disabled={isRunning}
            >
              <span className="domain-name">Auto-detect</span>
            </button>
            {availableDomains.map((domain) => (
              <button
                key={domain}
                className={`domain-btn ${selectedDomain === domain ? 'active' : ''}`}
                onClick={() => dispatch(setSelectedDomain(domain))}
                disabled={isRunning}
              >
                <span className="domain-name">{DOMAIN_LABELS[domain] || domain.replace('_', ' ')}</span>
              </button>
            ))}
          </div>
        </div>
      </aside>
      
      {/* Main area */}
      <div className="chat-main">
        {/* Plan Preview Modal */}
        {showPlanPreview && pendingPlan && (
          <PlanPreview
            plan={pendingPlan.plan}
            mermaid={pendingPlan.mermaid}
            events={pendingPlan.events}
            onApprove={executePlan}
            onCancel={cancelPlan}
            onClose={() => setShowPlanPreview(false)}
            onRefine={handlePlanRefine}
            isRefining={isRefining}
            sessionId={pendingPlan.sessionId}
          />
        )}
        
        {mode === MODES.COMPARE ? (
          /* Comparison mode */
          <div className="comparison-container">
            {/* Normal Chat Panel */}
            <div className="comparison-panel">
              <div className="panel-header normal">
                <span className="panel-indicator normal"></span>
                <span className="panel-title" style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                  <span>💬 Normal Chat</span>
                  {normalSources && normalSources.length > 0 && (
                    <span
                      style={{
                        width: "18px",
                        height: "18px",
                        borderRadius: "50%",
                        background: "linear-gradient(135deg, #6b7cff, #8b5cf6)",
                        display: "inline-flex",
                        alignItems: "center",
                        justifyContent: "center",
                        fontSize: "10px",
                        color: "white",
                        fontWeight: "bold",
                        boxShadow: "0 2px 4px rgba(107, 124, 255, 0.3)"
                      }}
                      title={`Web search used - ${normalSources.length} sources`}
                    >
                      🔍
                    </span>
                  )}
                </span>
                <span className="panel-status">
                  {isSearching ? '🔍 Searching...' : normalLoading ? 'Generating...' : normalResponse ? 'Complete' : 'Waiting'}
                </span>
              </div>
              <div className="panel-content">
                {normalResponse ? (
                  <>
                    <div className="response-content">
                      {formatContentForDisplay(normalResponse, normalSources || [])}
                    </div>
                    <SourcesPanel sources={normalSources} />
                  </>
                ) : normalLoading ? (
                  <div className="thinking-message">
                    {isSearching ? (
                      <>
                        <span
                          style={{
                            width: "18px",
                            height: "18px",
                            borderRadius: "50%",
                            background: "linear-gradient(135deg, #6b7cff, #8b5cf6)",
                            display: "inline-flex",
                            alignItems: "center",
                            justifyContent: "center",
                            fontSize: "11px",
                            marginRight: "8px",
                            animation: "pulse 1.5s ease-in-out infinite"
                          }}
                        >
                          🔍
                        </span>
                        <span className="thinking-text">
                          🔍 Searching the web for current information...
                        </span>
                      </>
                    ) : (
                      <>
                        <div className="thinking-indicator">
                          <span className="thinking-dot"></span>
                          <span className="thinking-dot"></span>
                          <span className="thinking-dot"></span>
                        </div>
                        <span className="thinking-text">Generating response...</span>
                      </>
                    )}
                  </div>
                ) : (
                  <div className="chat-welcome" style={{ padding: '2rem' }}>
                    <p style={{ color: 'var(--text-muted)' }}>
                      Normal chat response will appear here
                    </p>
                  </div>
                )}
              </div>
            </div>
            
            {/* Multi-Agent Panel */}
            <div className="comparison-panel">
              <div className="panel-header multiagent">
                <span className="panel-indicator multiagent"></span>
                <span className="panel-title">🧠 Multi-Agent</span>
                <span className="panel-status">
                  {multiagentLoading || status === 'running' 
                    ? `${currentAgent || 'Agents'} working...` 
                    : status === 'complete' ? 'Complete' : 'Waiting'}
                </span>
              </div>
              <div className="panel-content">
                {scenes.length > 0 || finalStoryboard ? (
                  <StoryboardDisplay 
                    masterPlan={masterPlan}
                    scenes={scenes}
                    storyboard={finalStoryboard}
                  />
                ) : multiagentLoading || status === 'running' ? (
                  <>
                    <div className="thinking-message">
                      <div className="thinking-indicator">
                        <span className="thinking-dot"></span>
                        <span className="thinking-dot"></span>
                        <span className="thinking-dot"></span>
                      </div>
                      <span className="thinking-text">
                        {currentAgent ? `${currentAgent} is working...` : 'Agents initializing...'}
                      </span>
                    </div>
                    {/* Live events display */}
                    <div className="live-events-mini">
                      {events.slice(-5).map((event, i) => (
                        <div key={i} className={`mini-event ${event.agent}`}>
                          <span className="mini-event-agent">{event.agent}</span>
                          <span className="mini-event-content">
                            {event.content?.substring(0, 100)}...
                          </span>
                        </div>
                      ))}
                    </div>
                  </>
                ) : (
                  <div className="chat-welcome" style={{ padding: '2rem' }}>
                    <p style={{ color: 'var(--text-muted)' }}>
                      Multi-agent storyboard will appear here
                    </p>
                  </div>
                )}
              </div>
            </div>
            
            {/* Compare mode: Toggle button for Agent Activity sidebar */}
            {mode === MODES.COMPARE && events.length > 0 && (
              <button
                style={{
                  position: "fixed",
                  right: showThinking ? "420px" : "20px",
                  top: "50%",
                  transform: "translateY(-50%)",
                  background: "linear-gradient(135deg, #6b7cff, #8b5cf6)",
                  color: "white",
                  border: "none",
                  borderRadius: "8px 0 0 8px",
                  padding: "12px 16px",
                  cursor: "pointer",
                  fontSize: "13px",
                  fontWeight: "500",
                  boxShadow: "0 4px 6px rgba(0,0,0,0.1)",
                  zIndex: 1000,
                  transition: "right 0.3s ease",
                  display: "flex",
                  alignItems: "center",
                  gap: "6px"
                }}
                onClick={() => setShowThinking(!showThinking)}
                title={showThinking ? "Hide Agent Activity" : "Show Agent Activity"}
              >
                <span>{showThinking ? "←" : "→"}</span>
                <span>{showThinking ? "Hide" : "Show"}</span>
              </button>
            )}
          </div>
        ) : (
          /* Single mode view */
          <>
            <div className="chat-messages" ref={chatContainerRef}>
              {messages.length === 0 && !isRunning ? (
                <div className="chat-welcome">
                  <div className="welcome-icon">🤖</div>
                  <h2>Welcome to AgentFlow AI</h2>
                  <p>
                    {mode === MODES.NORMAL 
                      ? 'Get quick AI responses with normal chat mode.'
                      : 'Watch PreAct design a custom multi-agent pipeline. You\'ll see ALL generated prompts and can approve before execution.'}
                  </p>
                  <div className="example-prompts">
                    <p className="example-label">Try asking:</p>
                    <button 
                      className="example-btn"
                      onClick={() => setInputValue('Create a comprehensive analysis of renewable energy trends with market predictions')}
                    >
                      "Analyze renewable energy trends"
                    </button>
                    <button 
                      className="example-btn"
                      onClick={() => setInputValue('Design a marketing campaign for a new fitness app targeting young professionals')}
                    >
                      "Design a marketing campaign"
                    </button>
                  </div>
                </div>
              ) : (
                <>
                  {messages.map((msg, index) => (
                    <div key={index} className={`chat-message ${msg.type}`}>
                      {msg.type === 'user' ? (
                        <div className="message-content user-message">
                          <p>{msg.content}</p>
                        </div>
                      ) : msg.responseType === 'error' ? (
                        <div className="message-content assistant-message error-response">
                          <p>{msg.content}</p>
                        </div>
                      ) : msg.responseType === 'vision' ? (
                        <div className="message-content assistant-message vision-response">
                          <div className="response-label vision">
                            👁️ Vision
                          </div>
                          {msg.imageDataUrl && (
                            <div style={{ marginBottom: '12px' }}>
                              <img
                                src={msg.imageDataUrl}
                                alt="User uploaded"
                                style={{ maxWidth: '300px', maxHeight: '300px', borderRadius: '8px', border: '1px solid #ddd' }}
                              />
                            </div>
                          )}
                          <div className="response-content">
                            {formatContentForDisplay(msg.content)}
                          </div>
                        </div>
                      ) : msg.content === 'storyboard' ? (
                        <div className={`message-content assistant-message ${msg.responseType}-response`}>
                          <div className={`response-label ${msg.responseType}`}>
                            {msg.responseType === 'normal' ? 'Chat' : 'Multi-Agent'}
                            {msg.detectedDomain && <span className="detected-domain">{DOMAIN_LABELS[msg.detectedDomain] || msg.detectedDomain}</span>}
                          </div>
                          <StoryboardDisplay 
                            masterPlan={msg.data.masterPlan}
                            scenes={msg.data.scenes}
                            storyboard={msg.data.finalStoryboard}
                          />
                        </div>
                      ) : (
                        <div className={`message-content assistant-message ${msg.responseType}-response`}>
                          <div className={`response-label ${msg.responseType}`} style={{ display: "flex", alignItems: "center", gap: "8px", flexWrap: "wrap" }}>
                            <span>{msg.responseType === 'normal' ? 'Chat' : 'Multi-Agent'}</span>
                            {msg.sources && msg.sources.length > 0 && (
                              <span
                                style={{
                                  width: "20px",
                                  height: "20px",
                                  borderRadius: "50%",
                                  background: "linear-gradient(135deg, #6b7cff, #8b5cf6)",
                                  display: "inline-flex",
                                  alignItems: "center",
                                  justifyContent: "center",
                                  fontSize: "11px",
                                  color: "white",
                                  fontWeight: "bold",
                                  boxShadow: "0 2px 4px rgba(107, 124, 255, 0.3)",
                                  cursor: "help"
                                }}
                                title={`Web search was used - ${msg.sources.length} sources found`}
                              >
                                🔍
                              </span>
                            )}
                            {msg.detectedDomain && <span className="detected-domain">{DOMAIN_LABELS[msg.detectedDomain] || msg.detectedDomain}</span>}
                          </div>
                          <div className="response-content">
                            {formatContentForDisplay(msg.content, msg.sources || [])}
                          </div>

                          <div className="response-content">
                          {/* ✅ Sources ONLY for normal chat */}
                       {msg.responseType === 'normal' && (
                        <SourcesPanel sources={msg.sources} />
                        )}
                        </div>
                        </div>
                      )}
                    </div>
                  ))}
                  
                  {/* Thinking indicator */}
                  {isRunning && (
                    <div className="chat-message assistant">
                      <div className="message-content assistant-message thinking-message">
                        {isSearching ? (
                          <>
                            <span
                              style={{
                                width: "18px",
                                height: "18px",
                                borderRadius: "50%",
                                background: "linear-gradient(135deg, #6b7cff, #8b5cf6)",
                                display: "inline-flex",
                                alignItems: "center",
                                justifyContent: "center",
                                fontSize: "11px",
                                marginRight: "8px",
                                animation: "pulse 1.5s ease-in-out infinite"
                              }}
                            >
                              🔍
                            </span>
                            <span className="thinking-text">
                              🔍 Searching the web for current information...
                            </span>
                          </>
                        ) : (
                          <>
                            <div className="thinking-indicator">
                              <span className="thinking-dot"></span>
                              <span className="thinking-dot"></span>
                              <span className="thinking-dot"></span>
                            </div>
                            <span className="thinking-text">
                              {mode === MODES.NORMAL 
                                ? 'Generating response...'
                                : pendingPlan 
                                  ? 'Plan ready! Review to proceed...'
                                  : currentAgent 
                                    ? `${currentAgent} is thinking...` 
                                    : 'Generating plan...'}
                            </span>
                          </>
                        )}
                        {mode === MODES.MULTIAGENT && events.length > 0 && (
                          <button 
                            className="show-thinking-btn"
                            onClick={() => setShowThinking(!showThinking)}
                          >
                            {showThinking ? 'Hide' : 'Show'} Agent Activity
                          </button>
                        )}
                      </div>
                    </div>
                  )}
                </>
              )}
            </div>
            
            {/* Thinking panel - always visible in multi-agent mode */}
            {mode === MODES.MULTIAGENT && events.length > 0 && showThinking && (
              <ThinkingPanel 
                events={events} 
                isOpen={showThinking}
                onClose={() => setShowThinking(false)}
                currentAgent={currentAgent}
                status={status}
              />
            )}
          </>
        )}
        
        {/* Compare mode thinking panel */}
        {mode === MODES.COMPARE && events.length > 0 && showThinking && (
          <ThinkingPanel 
            events={events} 
            isOpen={showThinking}
            onClose={() => setShowThinking(false)}
            currentAgent={currentAgent}
            status={status}
          />
        )}
        
        {/* Compare mode: Toggle button for Agent Activity sidebar */}
        {mode === MODES.COMPARE && events.length > 0 && (
          <button
            style={{
              position: "fixed",
              right: showThinking ? "420px" : "20px",
              top: "50%",
              transform: "translateY(-50%)",
              background: "linear-gradient(135deg, #6b7cff, #8b5cf6)",
              color: "white",
              border: "none",
              borderRadius: showThinking ? "8px 0 0 8px" : "8px",
              padding: "12px 16px",
              cursor: "pointer",
              fontSize: "13px",
              fontWeight: "500",
              boxShadow: "0 4px 6px rgba(0,0,0,0.1)",
              zIndex: 1000,
              transition: "right 0.3s ease",
              display: "flex",
              alignItems: "center",
              gap: "6px"
            }}
            onClick={() => setShowThinking(!showThinking)}
            title={showThinking ? "Hide Agent Activity" : "Show Agent Activity"}
          >
            <span>{showThinking ? "←" : "→"}</span>
            <span>{showThinking ? "Hide" : "Show"}</span>
          </button>
        )}
        
        {/* Input area - domain not required */}
        <div className="chat-input-area">
          <form onSubmit={handleSubmit} className="chat-form">
            {/* Vision mode: Image upload UI */}
            {mode === MODES.VISION && (
              <>
                <input
                  type="file"
                  accept="image/*"
                  ref={fileInputRef}
                  style={{ display: 'none' }}
                  onChange={(e) => {
                    const file = e.target.files[0];
                    if (!file) return;

                    setSelectedImage(file);
                    setImageDataUrl(null);
                    setImageDescription('');
                    setImageError(null);
                    if (fileInputRef.current) {
                      fileInputRef.current.value = '';
                    }
                    const reader = new FileReader();
                    reader.onloadend = () => {
                      setImageDataUrl(reader.result); // data:image/jpeg;base64,...
                      // Auto-process image when loaded
                      processImageWithVision(reader.result);
                    };
                    reader.readAsDataURL(file);
                  }}
                />
                {imageDataUrl && (
                  <div className="image-preview" style={{ marginBottom: '8px', padding: '8px', background: '#f5f5f5', borderRadius: '8px', display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <img
                      src={imageDataUrl}
                      alt="preview"
                      style={{ width: '60px', height: '60px', objectFit: 'cover', borderRadius: '8px', border: '1px solid #ddd' }}
                    />
                    <div style={{ flex: 1 }}>
                      {isProcessingImage ? (
                        <div style={{ fontSize: '0.85rem', color: '#666' }}>Processing image...</div>
                      ) : imageDescription ? (
                        <div style={{ fontSize: '0.85rem', color: '#10b981' }}>Image described ✓</div>
                      ) : imageError ? (
                        <div style={{ fontSize: '0.85rem', color: '#ef4444' }}>{imageError}</div>
                      ) : (
                        <div style={{ fontSize: '0.85rem', color: '#666' }}>Image ready</div>
                      )}
                    </div>
                    <button
                      type="button"
                      onClick={() => {
                        setSelectedImage(null);
                        setImageDataUrl(null);
                        setImageDescription('');
                        setImageError(null);
                      }}
                      style={{ background: 'transparent', border: 'none', fontSize: '18px', cursor: 'pointer', color: '#888', padding: '4px' }}
                      title="Remove image"
                    >
                      ✕
                    </button>
                  </div>
                )}
              </>
            )}
            
            <div className="input-wrapper">
              {/* Vision mode: Image upload button */}
              {mode === MODES.VISION && (
                <button
                  type="button"
                  className="plus-btn"
                  disabled={isRunning || isProcessingImage}
                  title="Upload image"
                  onClick={() => fileInputRef.current?.click()}
                >
                  +
                </button>
              )}
              
              {/* Web Search Icon/Logo Button - only show in non-vision modes */}
              {mode !== MODES.VISION && (
                <button
                  type="button"
                  className={`web-search-toggle ${forceWebSearch ? 'active' : ''}`}
                  onClick={() => setForceWebSearch(!forceWebSearch)}
                  disabled={isRunning}
                  title={forceWebSearch ? 'Web search enabled - Click to disable' : 'Enable web search'}
                >
                  {isSearching ? (
                    <span className="search-icon-animated">🔍</span>
                  ) : (
                    <span className={`search-icon ${forceWebSearch ? 'active' : ''}`}>🔍</span>
                  )}
                </button>
              )}
              
              <textarea
                className="chat-input"
                value={inputValue}
                onChange={(e) => setInputValue(e.target.value)}
                placeholder={mode === MODES.VISION ? "Upload an image or ask a question about an image..." : "Ask anything... (domain auto-detected)"}
                disabled={isRunning || isProcessingImage}
                rows={1}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    handleSubmit(e);
                  }
                }}
              />
              <button
                type="submit"
                className="send-btn"
                disabled={isRunning || isProcessingImage || (mode === MODES.VISION ? (!inputValue.trim() && !imageDataUrl) : !inputValue.trim())}
              >
                {isRunning || isProcessingImage ? (
                  <span className="loading-spinner-small"></span>
                ) : (
                  'Send'
                )}
              </button>
            </div>
          </form>
          <p className="input-hint">
            {mode === MODES.VISION
              ? 'Upload an image to get a description, or ask questions about uploaded images'
              : mode === MODES.COMPARE 
                ? 'Compare normal chat vs multi-agent responses'
                : mode === MODES.MULTIAGENT
                  ? 'Multi-agent: PreAct plans, ReAct executes, ReFlect validates'
                  : 'Press Enter to send'}
          </p>
        </div>
      </div>
    </div>
  );
}

export default ChatInterface;
