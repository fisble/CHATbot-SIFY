/**
 * Query input component for submitting storyboard generation requests.
 */

import { useState, useEffect } from 'react';
import { useSelector, useDispatch } from 'react-redux';
import {
  selectSelectedDomain,
  selectQuery,
  selectSessionId,
  selectLoading,
  selectQueryError,
  setQuery,
  startSession,
  fetchDomains,
} from '../store/querySlice';
import {
  selectStatus,
  clearEvents,
  setStatus,
} from '../store/agentSlice';
import { connectAndStart, disconnect } from '../utils/wsClient';

/**
 * Example queries for each domain.
 */
const EXAMPLE_QUERIES = {
  product_demo: 'Create a storyboard for a mobile banking app demo showing the key features: account overview, money transfers, and bill payments.',
  education: 'Design an educational storyboard explaining how photosynthesis works for middle school students.',
  medical: 'Create a patient education storyboard about preparing for knee replacement surgery.',
  marketing: 'Design a 30-second social media ad storyboard for a new eco-friendly water bottle brand.',
  film_style: 'Create a dramatic opening sequence storyboard for a sci-fi film about first contact with aliens.',
  gaming: 'Design a game trailer storyboard for an open-world fantasy RPG featuring exploration, combat, and magic.',
};

/**
 * QueryBox component.
 */
function QueryBox() {
  const dispatch = useDispatch();
  const selectedDomain = useSelector(selectSelectedDomain);
  const query = useSelector(selectQuery);
  const sessionId = useSelector(selectSessionId);
  const loading = useSelector(selectLoading);
  const error = useSelector(selectQueryError);
  const status = useSelector(selectStatus);
  
  const [localQuery, setLocalQuery] = useState(query);
  
  // Fetch domains on mount
  useEffect(() => {
    dispatch(fetchDomains());
  }, [dispatch]);
  
  // Connect to WebSocket when session is created
  useEffect(() => {
    if (sessionId && status !== 'running' && status !== 'complete') {
      connectAndStart(sessionId, dispatch);
    }
  }, [sessionId, dispatch, status]);
  
  // Update local query when domain changes (show example)
  useEffect(() => {
    if (selectedDomain && !localQuery) {
      // Don't auto-fill, just show placeholder
    }
  }, [selectedDomain, localQuery]);
  
  const handleQueryChange = (e) => {
    setLocalQuery(e.target.value);
    dispatch(setQuery(e.target.value));
  };
  
  const handleSubmit = async (e) => {
    e.preventDefault();
    
    if (!selectedDomain || !localQuery.trim()) {
      return;
    }
    
    // Clear previous events and disconnect
    dispatch(clearEvents());
    disconnect();
    dispatch(setStatus('idle'));
    
    // Start new session
    dispatch(startSession({
      domain: selectedDomain,
      query: localQuery.trim(),
    }));
  };
  
  const handleUseExample = () => {
    const example = EXAMPLE_QUERIES[selectedDomain] || '';
    setLocalQuery(example);
    dispatch(setQuery(example));
  };
  
  const handleReset = () => {
    disconnect();
    dispatch(clearEvents());
    dispatch(setStatus('idle'));
    setLocalQuery('');
    dispatch(setQuery(''));
  };
  
  const isRunning = status === 'running' || status === 'connecting';
  const isComplete = status === 'complete';
  
  return (
    <div className="query-box">
      <h3 className="section-title">Describe Your Storyboard</h3>
      
      <form onSubmit={handleSubmit}>
        <div className="query-input-container">
          <textarea
            className="query-input"
            value={localQuery}
            onChange={handleQueryChange}
            placeholder={EXAMPLE_QUERIES[selectedDomain] || 'Describe the storyboard you want to create...'}
            disabled={isRunning}
            rows={4}
          />
          
          <div className="query-actions">
            <button
              type="button"
              className="btn btn-secondary"
              onClick={handleUseExample}
              disabled={isRunning || !selectedDomain}
            >
              Use Example
            </button>
            
            {(isRunning || isComplete) && (
              <button
                type="button"
                className="btn btn-danger"
                onClick={handleReset}
              >
                Reset
              </button>
            )}
            
            <button
              type="submit"
              className="btn btn-primary"
              disabled={isRunning || !selectedDomain || !localQuery.trim()}
            >
              {loading ? 'Starting...' : isRunning ? 'Generating...' : 'Generate Storyboard'}
            </button>
          </div>
        </div>
      </form>
      
      {error && (
        <div className="error-message">
          <span className="error-icon">⚠️</span>
          {error}
        </div>
      )}
      
      {isRunning && (
        <div className="status-message">
          <span className="loading-spinner"></span>
          Agents are working on your storyboard...
        </div>
      )}
    </div>
  );
}

export default QueryBox;

