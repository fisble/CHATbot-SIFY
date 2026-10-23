/**
 * Scene viewer component showing generated scenes in real-time.
 */

import { useSelector } from 'react-redux';
import {
  selectScenes,
  selectMasterPlan,
  selectStatus,
} from '../store/agentSlice';

/**
 * Single scene card component.
 */
function SceneCard({ scene, index }) {
  return (
    <div className="scene-card">
      <div className="scene-header">
        <span className="scene-number">Scene {scene.scene_number || index + 1}</span>
        <span className="scene-title">{scene.title}</span>
        {scene.duration_seconds && (
          <span className="scene-duration">{scene.duration_seconds}s</span>
        )}
      </div>
      
      <div className="scene-description">
        {scene.description}
      </div>
      
      {scene.visual_elements && scene.visual_elements.length > 0 && (
        <div className="scene-visuals">
          <span className="label">Visual Elements:</span>
          <div className="visual-tags">
            {scene.visual_elements.map((element, i) => (
              <span key={i} className="visual-tag">{element}</span>
            ))}
          </div>
        </div>
      )}
      
      {scene.camera_direction && (
        <div className="scene-camera">
          <span className="label">📷 Camera:</span>
          <span className="value">{scene.camera_direction}</span>
        </div>
      )}
      
      {scene.dialogue && scene.dialogue !== 'None' && (
        <div className="scene-dialogue">
          <span className="label">💬 Dialogue:</span>
          <span className="value">{scene.dialogue}</span>
        </div>
      )}
      
      {scene.sound_effects && (
        <div className="scene-sound">
          <span className="label">🔊 Sound:</span>
          <span className="value">{scene.sound_effects}</span>
        </div>
      )}
      
      {scene.notes && (
        <div className="scene-notes">
          <span className="label">📝 Notes:</span>
          <span className="value">{scene.notes}</span>
        </div>
      )}
    </div>
  );
}

/**
 * Master plan summary component.
 */
function MasterPlanSummary({ plan }) {
  if (!plan) return null;
  
  return (
    <div className="master-plan-summary">
      <h4 className="plan-title">{plan.title}</h4>
      
      <div className="plan-details">
        {plan.world_setting && (
          <div className="plan-item">
            <span className="label">🌍 World:</span>
            <span className="value">{plan.world_setting}</span>
          </div>
        )}
        
        {plan.tone && (
          <div className="plan-item">
            <span className="label">🎭 Tone:</span>
            <span className="value">{plan.tone}</span>
          </div>
        )}
        
        {plan.visual_style && (
          <div className="plan-item">
            <span className="label">🎨 Visual Style:</span>
            <span className="value">{plan.visual_style}</span>
          </div>
        )}
        
        {plan.characters && plan.characters.length > 0 && (
          <div className="plan-characters">
            <span className="label">👥 Characters:</span>
            <div className="character-list">
              {plan.characters.map((char, i) => (
                <div key={i} className="character-item">
                  <span className="char-name">{char.name}:</span>
                  <span className="char-desc">{char.description}</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

/**
 * SceneViewer component.
 */
function SceneViewer() {
  const scenes = useSelector(selectScenes);
  const masterPlan = useSelector(selectMasterPlan);
  const status = useSelector(selectStatus);
  
  const isRunning = status === 'running' || status === 'connecting';
  const totalPlanned = masterPlan?.total_scenes || 0;
  
  return (
    <div className="scene-viewer">
      <div className="viewer-header">
        <h3 className="section-title">
          <span className="viewer-icon">🎬</span>
          Scene Viewer
        </h3>
        {totalPlanned > 0 && (
          <span className="scene-progress">
            {scenes.length} / {totalPlanned} scenes
          </span>
        )}
      </div>
      
      {masterPlan && (
        <MasterPlanSummary plan={masterPlan} />
      )}
      
      <div className="scenes-container">
        {scenes.length === 0 ? (
          <div className="scenes-empty">
            <span className="empty-icon">🎞️</span>
            <p>Scenes will appear here as they're generated</p>
            {isRunning && (
              <div className="generating-indicator">
                <span className="loading-spinner"></span>
                <span>Generating scenes...</span>
              </div>
            )}
          </div>
        ) : (
          <div className="scenes-grid">
            {scenes.map((scene, index) => (
              <SceneCard key={scene.scene_number || index} scene={scene} index={index} />
            ))}
            
            {isRunning && scenes.length < totalPlanned && (
              <div className="scene-card scene-placeholder">
                <div className="placeholder-content">
                  <span className="loading-spinner"></span>
                  <span>Generating Scene {scenes.length + 1}...</span>
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

export default SceneViewer;

