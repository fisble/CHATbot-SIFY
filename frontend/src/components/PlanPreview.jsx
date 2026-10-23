/**
 * Plan Preview component - Unified view for PreAct reasoning plan.
 * 
 * Features:
 * - Single unified view (no tabs)
 * - Chat interface for plan refinement
 * - LLM clarification questions with interactive responses
 * - Step confirmation checkboxes
 * - Real-time plan updates
 */

import { useState, useEffect, useRef } from 'react';

const COMPLEXITY_COLORS = {
  simple: '#22c55e',
  moderate: '#f59e0b',
  complex: '#ef4444'
};

function PlanPreview({ 
  plan, 
  mermaid, 
  events, 
  onApprove, 
  onCancel, 
  onClose, 
  onRefine,
  isRefining = false,
  sessionId 
}) {
  const [copied, setCopied] = useState(false);
  const [chatInput, setChatInput] = useState('');
  const [stepConfirmations, setStepConfirmations] = useState({});
  const [clarificationResponses, setClarificationResponses] = useState({});
  const [showDiagram, setShowDiagram] = useState(false);
  const [chatHistory, setChatHistory] = useState([]);
  const mermaidRef = useRef(null);
  const chatInputRef = useRef(null);
  const chatMessagesRef = useRef(null);
  
  // Initialize step confirmations when plan changes
  useEffect(() => {
    if (plan) {
      const reasoningPlan = plan.reasoning_plan || plan.dynamic_plan || plan;
      const steps = reasoningPlan.steps || [];
      const confirmations = {};
      steps.forEach((_, i) => {
        confirmations[i] = true; // Default all confirmed
      });
      setStepConfirmations(confirmations);
      
      // Initialize chat history from plan if exists
      if (reasoningPlan.chat_history?.length) {
        setChatHistory(reasoningPlan.chat_history);
      }
    }
  }, [plan]);
  
  // Scroll chat to bottom when new messages arrive
  useEffect(() => {
    if (chatMessagesRef.current) {
      chatMessagesRef.current.scrollTop = chatMessagesRef.current.scrollHeight;
    }
  }, [chatHistory]);
  
  // Render Mermaid diagram
  useEffect(() => {
    if (mermaid && mermaidRef.current && window.mermaid && showDiagram) {
      try {
        mermaidRef.current.innerHTML = mermaid;
        window.mermaid.init(undefined, mermaidRef.current);
      } catch (e) {
        console.log('Mermaid init:', e);
      }
    }
  }, [mermaid, showDiagram]);
  
  // Copy plan to clipboard
  const copyPlan = async () => {
    const planText = formatPlanText(plan, mermaid);
    try {
      await navigator.clipboard.writeText(planText);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (e) {
      console.error('Failed to copy:', e);
    }
  };
  
  const formatPlanText = (plan, mermaid) => {
    if (!plan) return '';
    const reasoningPlan = plan.reasoning_plan || plan.dynamic_plan || plan;
    let text = `# ${reasoningPlan.title || 'Task Plan'}\n\n`;
    text += `## Understanding\n${reasoningPlan.task_understanding || ''}\n\n`;
    text += `## Approach\n${reasoningPlan.approach || ''}\n\n`;
    text += `## Steps\n`;
    (reasoningPlan.steps || []).forEach((step, i) => {
      const title = typeof step === 'string' ? step : step.title;
      text += `${i + 1}. ${title}\n`;
    });
    return text;
  };
  
  // Handle step confirmation toggle
  const toggleStepConfirmation = (index) => {
    setStepConfirmations(prev => ({
      ...prev,
      [index]: !prev[index]
    }));
  };
  
  // Handle clarification response for choice/text questions
  const handleClarificationResponse = (questionId, value) => {
    setClarificationResponses(prev => ({
      ...prev,
      [questionId]: value
    }));
  };
  
  // Handle chat message submission
  const handleChatSubmit = async (e) => {
    e.preventDefault();
    if (!chatInput.trim() || isRefining) return;
    
    const userMessage = chatInput.trim();
    setChatInput('');
    
    // Add user message to chat history immediately
    const updatedHistory = [
      ...chatHistory,
      { role: 'user', content: userMessage }
    ];
    setChatHistory(updatedHistory);
    
    // Call onRefine with current state
    if (onRefine) {
      onRefine({
        chat_message: userMessage,
        user_responses: clarificationResponses,
        chat_history: updatedHistory
      });
    }
  };
  
  // Handle quick response to clarification questions
  const handleQuickRefine = () => {
    if (Object.keys(clarificationResponses).length === 0) return;
    
    if (onRefine) {
      onRefine({
        chat_message: '',
        user_responses: clarificationResponses,
        chat_history: chatHistory
      });
    }
  };
  
  // Handle approve with confirmations
  const handleApprove = () => {
    const confirmedSteps = Object.entries(stepConfirmations)
      .filter(([_, confirmed]) => confirmed)
      .map(([index]) => parseInt(index));
    
    const enhancedPlan = {
      ...plan,
      confirmed_steps: confirmedSteps,
      clarification_responses: clarificationResponses,
      chat_history: chatHistory
    };
    
    onApprove(enhancedPlan);
  };
  
  if (!plan) {
    return (
      <div className="plan-preview-overlay">
        <div className="plan-preview-modal compact">
          <div className="plan-loading">
            <div className="loading-spinner"></div>
            <p>PreAct is designing your plan...</p>
          </div>
        </div>
      </div>
    );
  }
  
  const reasoningPlan = plan.reasoning_plan || plan.dynamic_plan || plan;
  const steps = reasoningPlan.steps || [];
  const complexity = reasoningPlan.estimated_complexity || 'moderate';
  const complexityColor = COMPLEXITY_COLORS[complexity] || COMPLEXITY_COLORS.moderate;
  const clarificationQuestions = reasoningPlan.clarification_questions || [];
  const allStepsConfirmed = Object.values(stepConfirmations).every(v => v);
  const hasResponses = Object.keys(clarificationResponses).length > 0;
  
  return (
    <div className="plan-preview-overlay">
      <div className="plan-preview-modal unified">
        {/* Compact Header */}
        <div className="plan-header-compact">
          <div className="plan-title-row">
            <h2>{reasoningPlan.title || 'Execution Plan'}</h2>
            <div className="plan-badges">
              <span className="complexity-badge" style={{ background: complexityColor }}>
                {complexity}
              </span>
              <span className="step-count">{steps.length} steps</span>
              {plan.is_refined && (
                <span className="refined-badge">Refined</span>
              )}
            </div>
          </div>
          <div className="plan-actions-row">
            <button className="btn-text" onClick={copyPlan}>
              {copied ? '✓ Copied' : 'Copy'}
            </button>
            <button className="btn-text" onClick={() => setShowDiagram(!showDiagram)}>
              {showDiagram ? 'Hide Diagram' : 'Show Diagram'}
            </button>
            <button className="btn-close" onClick={onClose}>×</button>
          </div>
        </div>
        
        {/* Unified Content */}
        <div className="plan-content-unified">
          {/* Understanding & Approach - Compact */}
          <div className="plan-summary">
            <div className="summary-item">
              <strong>Understanding:</strong>
              <p>{reasoningPlan.task_understanding || 'Analyzing your request...'}</p>
            </div>
            <div className="summary-item">
              <strong>Approach:</strong>
              <p>{reasoningPlan.approach || 'Step-by-step execution'}</p>
            </div>
          </div>
          
          {/* AI Clarification Questions - Interactive */}
          {clarificationQuestions.length > 0 && (
            <div className="clarification-section">
              <h4>Questions from AI</h4>
              <p className="clarification-hint">Help me understand your needs better:</p>
              <div className="clarification-list">
                {clarificationQuestions.map((q, i) => {
                  const qId = q.id || `q${i}`;
                  const currentValue = clarificationResponses[qId];
                  
                  return (
                    <div key={qId} className="clarification-item">
                      <label className="question-label">{q.question}</label>
                      
                      {q.type === 'boolean' ? (
                        <div className="boolean-options">
                          <button
                            className={`option-btn ${currentValue === 'yes' ? 'selected' : ''}`}
                            onClick={() => handleClarificationResponse(qId, 'yes')}
                          >
                            Yes
                          </button>
                          <button
                            className={`option-btn ${currentValue === 'no' ? 'selected' : ''}`}
                            onClick={() => handleClarificationResponse(qId, 'no')}
                          >
                            No
                          </button>
                        </div>
                      ) : q.type === 'choice' && q.options?.length > 0 ? (
                        <div className="choice-options">
                          {q.options.map((option, optIdx) => (
                            <button
                              key={optIdx}
                              className={`option-btn ${currentValue === option ? 'selected' : ''}`}
                              onClick={() => handleClarificationResponse(qId, option)}
                            >
                              {option}
                            </button>
                          ))}
                        </div>
                      ) : (
                        <input
                          type="text"
                          className="text-response"
                          placeholder="Your answer..."
                          value={currentValue || ''}
                          onChange={(e) => handleClarificationResponse(qId, e.target.value)}
                        />
                      )}
                    </div>
                  );
                })}
              </div>
              {hasResponses && (
                <button 
                  className="btn-apply-responses" 
                  onClick={handleQuickRefine}
                  disabled={isRefining}
                >
                  {isRefining ? 'Updating...' : 'Apply My Preferences'}
                </button>
              )}
            </div>
          )}
          
          {/* Chat Interface */}
          <div className="chat-section">
            <h4>Chat with AI</h4>
            <div className="chat-messages" ref={chatMessagesRef}>
              {chatHistory.length === 0 ? (
                <div className="chat-empty">
                  <p>Ask questions or give instructions to refine the plan</p>
                  <div className="chat-suggestions">
                    <button onClick={() => setChatInput('Add more detail to step 1')}>
                      Add more detail
                    </button>
                    <button onClick={() => setChatInput('Include code examples')}>
                      Include examples
                    </button>
                    <button onClick={() => setChatInput('Make it more beginner-friendly')}>
                      Simplify it
                    </button>
                  </div>
                </div>
              ) : (
                chatHistory.map((msg, i) => (
                  <div key={i} className={`chat-message ${msg.role}`}>
                    <div className="message-role">{msg.role === 'user' ? 'You' : 'AI'}</div>
                    <div className="message-content">{msg.content}</div>
                  </div>
                ))
              )}
              {isRefining && (
                <div className="chat-message assistant refining">
                  <div className="message-role">AI</div>
                  <div className="message-content">
                    <span className="typing-indicator">
                      <span></span><span></span><span></span>
                    </span>
                    Refining plan...
                  </div>
                </div>
              )}
            </div>
            <form onSubmit={handleChatSubmit} className="chat-input-form">
              <input
                ref={chatInputRef}
                type="text"
                value={chatInput}
                onChange={(e) => setChatInput(e.target.value)}
                placeholder="Type to refine the plan..."
                className="chat-input"
                disabled={isRefining}
              />
              <button 
                type="submit" 
                className="btn-send" 
                disabled={!chatInput.trim() || isRefining}
              >
                {isRefining ? '...' : 'Send'}
              </button>
            </form>
          </div>
          
          {/* Steps with Checkboxes */}
          <div className="steps-section">
            <div className="steps-header">
              <h4>Execution Steps</h4>
              <button 
                className="btn-text small"
                onClick={() => {
                  const allTrue = Object.values(stepConfirmations).every(v => v);
                  const newValue = !allTrue;
                  const newConfirmations = {};
                  steps.forEach((_, i) => { newConfirmations[i] = newValue; });
                  setStepConfirmations(newConfirmations);
                }}
              >
                {allStepsConfirmed ? 'Deselect All' : 'Select All'}
              </button>
            </div>
            <div className="steps-list-compact">
              {steps.map((step, i) => {
                const isString = typeof step === 'string';
                const stepNum = isString ? i + 1 : step.step_number;
                const title = isString ? step : step.title;
                const description = isString ? '' : step.description;
                const isConfirmed = stepConfirmations[i];
                
                return (
                  <div 
                    key={i} 
                    className={`step-item-compact ${isConfirmed ? 'confirmed' : 'unconfirmed'}`}
                  >
                    <label className="step-checkbox-label">
                      <input
                        type="checkbox"
                        checked={isConfirmed}
                        onChange={() => toggleStepConfirmation(i)}
                      />
                      <span className="step-number">{stepNum}</span>
                      <span className="step-content">
                        <span className="step-title">{title}</span>
                        {description && <span className="step-desc">{description}</span>}
                      </span>
                    </label>
                  </div>
                );
              })}
            </div>
          </div>
          
          {/* Diagram (collapsible) */}
          {showDiagram && mermaid && (
            <div className="diagram-section">
              <div className="mermaid-container">
                <pre className="mermaid" ref={mermaidRef}>{mermaid}</pre>
              </div>
            </div>
          )}
          
          {/* Constraints & Success Criteria - Compact */}
          {(reasoningPlan.constraints?.length > 0 || reasoningPlan.success_criteria?.length > 0) && (
            <div className="meta-section">
              {reasoningPlan.constraints?.length > 0 && (
                <div className="meta-item constraints">
                  <strong>Constraints:</strong>
                  <ul>
                    {reasoningPlan.constraints.slice(0, 3).map((c, i) => (
                      <li key={i}>{c}</li>
                    ))}
                    {reasoningPlan.constraints.length > 3 && (
                      <li className="more">+{reasoningPlan.constraints.length - 3} more</li>
                    )}
                  </ul>
                </div>
              )}
              {reasoningPlan.success_criteria?.length > 0 && (
                <div className="meta-item success">
                  <strong>Success Criteria:</strong>
                  <ul>
                    {reasoningPlan.success_criteria.slice(0, 3).map((c, i) => (
                      <li key={i}>{c}</li>
                    ))}
                    {reasoningPlan.success_criteria.length > 3 && (
                      <li className="more">+{reasoningPlan.success_criteria.length - 3} more</li>
                    )}
                  </ul>
                </div>
              )}
            </div>
          )}
        </div>
        
        {/* Footer Actions */}
        <div className="plan-footer-compact">
          <div className="footer-info">
            <span className="confirmed-count">
              {Object.values(stepConfirmations).filter(v => v).length}/{steps.length} steps selected
            </span>
            {chatHistory.length > 0 && (
              <span className="chat-count">{chatHistory.length} messages</span>
            )}
          </div>
          <div className="footer-buttons">
            <button className="btn-cancel" onClick={onCancel}>
              Cancel
            </button>
            <button 
              className="btn-execute" 
              onClick={handleApprove}
              disabled={Object.values(stepConfirmations).filter(v => v).length === 0 || isRefining}
            >
              {isRefining ? 'Updating Plan...' : 'Execute Selected Steps'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

export default PlanPreview;
