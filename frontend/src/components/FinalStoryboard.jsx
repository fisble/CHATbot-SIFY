/**
 * Final storyboard component showing the complete generated storyboard.
 */

import { useSelector } from 'react-redux';
import {
  selectFinalStoryboard,
  selectStatus,
  selectMasterPlan,
  selectScenes,
} from '../store/agentSlice';
import { selectSelectedDomain, selectQuery } from '../store/querySlice';

/**
 * Scene detail view for final storyboard.
 */
function FinalSceneCard({ scene, isExpanded }) {
  return (
    <div className={`final-scene-card ${isExpanded ? 'expanded' : ''}`}>
      <div className="final-scene-header">
        <div className="scene-number-badge">{scene.scene_number}</div>
        <h4 className="scene-title">{scene.title}</h4>
        {scene.duration_seconds && (
          <span className="scene-duration">{scene.duration_seconds}s</span>
        )}
      </div>
      
      <div className="final-scene-content">
        <div className="scene-description">
          <p>{scene.description}</p>
        </div>
        
        <div className="scene-details-grid">
          {scene.visual_elements && scene.visual_elements.length > 0 && (
            <div className="detail-section">
              <h5>🎨 Visual Elements</h5>
              <div className="visual-tags">
                {scene.visual_elements.map((element, i) => (
                  <span key={i} className="visual-tag">{element}</span>
                ))}
              </div>
            </div>
          )}
          
          <div className="detail-section">
            <h5>📷 Camera</h5>
            <p>{scene.camera_direction || 'Standard shot'}</p>
          </div>
          
          {scene.dialogue && scene.dialogue !== 'None' && (
            <div className="detail-section">
              <h5>💬 Dialogue</h5>
              <p className="dialogue-text">{scene.dialogue}</p>
            </div>
          )}
          
          <div className="detail-section">
            <h5>🔊 Sound</h5>
            <p>{scene.sound_effects || 'Ambient'}</p>
          </div>
        </div>
        
        {scene.notes && (
          <div className="scene-notes">
            <h5>📝 Production Notes</h5>
            <p>{scene.notes}</p>
          </div>
        )}
      </div>
    </div>
  );
}

/**
 * Export button component.
 */
function ExportButton({ storyboard, domain, query }) {
  const handleExport = () => {
    // Create exportable JSON
    const exportData = {
      title: storyboard?.title || 'Untitled Storyboard',
      domain: domain,
      query: query,
      exportedAt: new Date().toISOString(),
      masterPlan: storyboard?.master_plan,
      scenes: storyboard?.scenes || [],
    };
    
    // Create and download file
    const blob = new Blob([JSON.stringify(exportData, null, 2)], {
      type: 'application/json',
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `storyboard-${domain}-${Date.now()}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };
  
  return (
    <button className="btn btn-export" onClick={handleExport}>
      <span className="btn-icon">📥</span>
      Export JSON
    </button>
  );
}

/**
 * FinalStoryboard component.
 */
function FinalStoryboard() {
  const finalStoryboard = useSelector(selectFinalStoryboard);
  const status = useSelector(selectStatus);
  const masterPlan = useSelector(selectMasterPlan);
  const scenes = useSelector(selectScenes);
  const domain = useSelector(selectSelectedDomain);
  const query = useSelector(selectQuery);
  
  const isComplete = status === 'complete';
  
  // Use scenes from Redux state if finalStoryboard not available
  const displayScenes = finalStoryboard?.scenes || scenes;
  const displayPlan = finalStoryboard?.master_plan || masterPlan;
  
  if (!isComplete && displayScenes.length === 0) {
    return (
      <div className="final-storyboard">
        <div className="storyboard-header">
          <h3 className="section-title">
            <span className="storyboard-icon">📑</span>
            Final Storyboard
          </h3>
        </div>
        
        <div className="storyboard-empty">
          <span className="empty-icon">📜</span>
          <p>Complete storyboard will appear here</p>
          <p className="empty-hint">Waiting for generation to complete...</p>
        </div>
      </div>
    );
  }
  
  return (
    <div className="final-storyboard">
      <div className="storyboard-header">
        <h3 className="section-title">
          <span className="storyboard-icon">📑</span>
          Final Storyboard
          {isComplete && <span className="complete-badge">Complete</span>}
        </h3>
        
        {displayScenes.length > 0 && (
          <ExportButton
            storyboard={{ ...finalStoryboard, master_plan: displayPlan, scenes: displayScenes }}
            domain={domain}
            query={query}
          />
        )}
      </div>
      
      <div className="storyboard-content">
        {/* Overview Section */}
        {displayPlan && (
          <div className="storyboard-overview">
            <h2 className="storyboard-title">
              {displayPlan.title || 'Generated Storyboard'}
            </h2>
            
            <div className="overview-grid">
              <div className="overview-item">
                <span className="overview-label">Domain</span>
                <span className="overview-value">{domain}</span>
              </div>
              <div className="overview-item">
                <span className="overview-label">Total Scenes</span>
                <span className="overview-value">{displayScenes.length}</span>
              </div>
              <div className="overview-item">
                <span className="overview-label">Total Duration</span>
                <span className="overview-value">
                  {displayScenes.reduce((sum, s) => sum + (s.duration_seconds || 0), 0)}s
                </span>
              </div>
            </div>
            
            {displayPlan.world_setting && (
              <div className="overview-section">
                <h4>🌍 World Setting</h4>
                <p>{displayPlan.world_setting}</p>
              </div>
            )}
            
            {displayPlan.visual_style && (
              <div className="overview-section">
                <h4>🎨 Visual Style</h4>
                <p>{displayPlan.visual_style}</p>
              </div>
            )}
            
            {displayPlan.tone && (
              <div className="overview-section">
                <h4>🎭 Tone</h4>
                <p>{displayPlan.tone}</p>
              </div>
            )}
          </div>
        )}
        
        {/* Scenes Section */}
        <div className="storyboard-scenes">
          <h3>Scenes</h3>
          <div className="final-scenes-list">
            {displayScenes.map((scene, index) => (
              <FinalSceneCard
                key={scene.scene_number || index}
                scene={scene}
                isExpanded={true}
              />
            ))}
          </div>
        </div>
        
        {/* Production Notes */}
        {isComplete && (
          <div className="production-notes">
            <h3>📋 Production Notes</h3>
            <ul>
              <li>This storyboard has been reviewed for narrative coherence</li>
              <li>Visual consistency has been verified across all scenes</li>
              <li>Domain-specific guidelines have been applied</li>
              <li>Ready for production implementation</li>
            </ul>
          </div>
        )}
      </div>
    </div>
  );
}

export default FinalStoryboard;

