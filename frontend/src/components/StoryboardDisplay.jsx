/**
 * Storyboard display component - Shows the generated storyboard in the chat.
 */

import { useState } from 'react';

/**
 * Scene card component
 */
function SceneCard({ scene, index, isExpanded, onToggle }) {
  return (
    <div className={`storyboard-scene ${isExpanded ? 'expanded' : ''}`}>
      <div className="scene-header" onClick={onToggle}>
        <div className="scene-number">{scene.scene_number || index + 1}</div>
        <h4 className="scene-title">{scene.title}</h4>
        {scene.duration_seconds && (
          <span className="scene-duration">{scene.duration_seconds}s</span>
        )}
        <span className="expand-icon">{isExpanded ? '▼' : '▶'}</span>
      </div>
      
      {isExpanded && (
        <div className="scene-details">
          <p className="scene-description">{scene.description}</p>
          
          {scene.visual_elements && scene.visual_elements.length > 0 && (
            <div className="scene-field">
              <span className="field-label">🎨 Visuals:</span>
              <div className="visual-tags">
                {scene.visual_elements.map((el, i) => (
                  <span key={i} className="visual-tag">{el}</span>
                ))}
              </div>
            </div>
          )}
          
          {scene.camera_direction && (
            <div className="scene-field">
              <span className="field-label">📷 Camera:</span>
              <span>{scene.camera_direction}</span>
            </div>
          )}
          
          {scene.dialogue && scene.dialogue !== 'None' && (
            <div className="scene-field">
              <span className="field-label">💬 Dialogue:</span>
              <span className="dialogue-text">"{scene.dialogue}"</span>
            </div>
          )}
          
          {scene.sound_effects && (
            <div className="scene-field">
              <span className="field-label">🔊 Sound:</span>
              <span>{scene.sound_effects}</span>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

/**
 * StoryboardDisplay component
 */
function StoryboardDisplay({ masterPlan, scenes, storyboard }) {
  const [expandedScenes, setExpandedScenes] = useState(new Set([0])); // First scene expanded by default
  const [showFullPlan, setShowFullPlan] = useState(false);
  
  const displayScenes = storyboard?.scenes || scenes || [];
  const displayPlan = storyboard?.master_plan || masterPlan;
  
  const toggleScene = (index) => {
    setExpandedScenes(prev => {
      const next = new Set(prev);
      if (next.has(index)) {
        next.delete(index);
      } else {
        next.add(index);
      }
      return next;
    });
  };
  
  const expandAll = () => {
    setExpandedScenes(new Set(displayScenes.map((_, i) => i)));
  };
  
  const collapseAll = () => {
    setExpandedScenes(new Set());
  };
  
  const handleExport = () => {
    const exportData = {
      title: displayPlan?.title || 'Storyboard',
      masterPlan: displayPlan,
      scenes: displayScenes,
      exportedAt: new Date().toISOString(),
    };
    
    const blob = new Blob([JSON.stringify(exportData, null, 2)], {
      type: 'application/json',
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `storyboard-${Date.now()}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };
  
  if (!displayScenes.length && !displayPlan) {
    return (
      <div className="storyboard-empty">
        <p>No storyboard data available.</p>
      </div>
    );
  }
  
  return (
    <div className="storyboard-display">
      {/* Header */}
      <div className="storyboard-header">
        <div className="storyboard-title-section">
          <span className="storyboard-icon">🎬</span>
          <h3>{displayPlan?.title || 'Generated Storyboard'}</h3>
        </div>
        <div className="storyboard-actions">
          <button className="action-btn" onClick={expandAll}>Expand All</button>
          <button className="action-btn" onClick={collapseAll}>Collapse All</button>
          <button className="action-btn export-btn" onClick={handleExport}>
            📥 Export
          </button>
        </div>
      </div>
      
      {/* Overview */}
      {displayPlan && (
        <div className="storyboard-overview">
          <div className="overview-stats">
            <div className="stat">
              <span className="stat-value">{displayScenes.length}</span>
              <span className="stat-label">Scenes</span>
            </div>
            <div className="stat">
              <span className="stat-value">
                {displayScenes.reduce((sum, s) => sum + (s.duration_seconds || 0), 0)}s
              </span>
              <span className="stat-label">Duration</span>
            </div>
          </div>
          
          <button 
            className="show-plan-btn"
            onClick={() => setShowFullPlan(!showFullPlan)}
          >
            {showFullPlan ? 'Hide' : 'Show'} Master Plan
          </button>
          
          {showFullPlan && (
            <div className="master-plan-details">
              {displayPlan.world_setting && (
                <div className="plan-section">
                  <h4>🌍 World Setting</h4>
                  <p>{displayPlan.world_setting}</p>
                </div>
              )}
              {displayPlan.visual_style && (
                <div className="plan-section">
                  <h4>🎨 Visual Style</h4>
                  <p>{displayPlan.visual_style}</p>
                </div>
              )}
              {displayPlan.tone && (
                <div className="plan-section">
                  <h4>🎭 Tone</h4>
                  <p>{displayPlan.tone}</p>
                </div>
              )}
              {displayPlan.characters && displayPlan.characters.length > 0 && (
                <div className="plan-section">
                  <h4>👥 Characters</h4>
                  <ul>
                    {displayPlan.characters.map((char, i) => (
                      <li key={i}>
                        <strong>{char.name}:</strong> {char.description}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}
        </div>
      )}
      
      {/* Scenes */}
      <div className="storyboard-scenes">
        {displayScenes.map((scene, index) => (
          <SceneCard
            key={scene.scene_number || index}
            scene={scene}
            index={index}
            isExpanded={expandedScenes.has(index)}
            onToggle={() => toggleScene(index)}
          />
        ))}
      </div>
      
      {/* Footer */}
      <div className="storyboard-footer">
        <span className="complete-badge">✅ Storyboard Complete</span>
        <span className="footer-text">
          Generated by preAct → ReAct → ReFlect agents
        </span>
      </div>
    </div>
  );
}

export default StoryboardDisplay;

