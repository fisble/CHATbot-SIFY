/**
 * Redux slice for agent state management.
 * Handles events, scenes, and storyboard status.
 */

import { createSlice } from '@reduxjs/toolkit';

/**
 * Initial state for the agent slice.
 */
const initialState = {
  // All agent events for the live feed
  events: [],
  // Generated scenes
  scenes: [],
  // Final storyboard data
  finalStoryboard: null,
  // Master plan from preAct
  masterPlan: null,
  // Current status: 'idle' | 'connecting' | 'running' | 'complete' | 'error'
  status: 'idle',
  // Current active agent
  currentAgent: null,
  // Error message if any
  error: null,
  // WebSocket connection status
  connected: false,
};

/**
 * Agent event types for styling
 */
export const EVENT_TYPES = {
  thought: 'thought',
  action: 'action',
  observation: 'observation',
  plan: 'plan',
  scene: 'scene',
  memory_update: 'memory_update',
  rag_result: 'rag_result',
  error: 'error',
  complete: 'complete',
  status: 'status',
};

/**
 * Agent names
 */
export const AGENT_NAMES = {
  preAct: 'preAct',
  ReAct: 'ReAct',
  ReFlect: 'ReFlect',
  TME: 'TME',
  RAG: 'RAG',
  system: 'system',
};

/**
 * Agent slice with reducers.
 */
const agentSlice = createSlice({
  name: 'agent',
  initialState,
  reducers: {
    /**
     * Add a new event to the feed.
     */
    addEvent: (state, action) => {
      const event = {
        id: Date.now() + Math.random(),
        ...action.payload,
        receivedAt: new Date().toISOString(),
      };
      state.events.push(event);
      
      // Update current agent
      if (action.payload.agent && action.payload.agent !== 'system') {
        state.currentAgent = action.payload.agent;
      }
      
      // Handle special event types
      if (action.payload.event === 'plan' && action.payload.metadata?.master_plan) {
        state.masterPlan = action.payload.metadata.master_plan;
      }
      
      if (action.payload.event === 'scene' && action.payload.metadata?.scene) {
        state.scenes.push(action.payload.metadata.scene);
      }
      
      // Handle complete event with storyboard (case-insensitive check)
      const eventName = (action.payload.event || '').toLowerCase();
      if (eventName === 'complete' && action.payload.metadata?.storyboard) {
        state.finalStoryboard = action.payload.metadata.storyboard;
        state.status = 'complete';
        console.log('[REDUX] Storyboard set from complete event:', {
          has_storyboard: !!action.payload.metadata.storyboard,
          scenes_count: action.payload.metadata.storyboard.scenes?.length || 0
        });
      }
      
      if (action.payload.event === 'error') {
        state.error = action.payload.content;
      }
    },
    
    /**
     * Add a scene to the list.
     */
    addScene: (state, action) => {
      state.scenes.push(action.payload);
    },
    
    /**
     * Set the master plan.
     */
    setMasterPlan: (state, action) => {
      state.masterPlan = action.payload;
    },
    
    /**
     * Set the final storyboard.
     */
    setFinalStoryboard: (state, action) => {
      state.finalStoryboard = action.payload;
    },
    
    /**
     * Set the current status.
     */
    setStatus: (state, action) => {
      state.status = action.payload;
    },
    
    /**
     * Set the current active agent.
     */
    setCurrentAgent: (state, action) => {
      state.currentAgent = action.payload;
    },
    
    /**
     * Set error message.
     */
    setError: (state, action) => {
      state.error = action.payload;
      state.status = 'error';
    },
    
    /**
     * Set WebSocket connection status.
     */
    setConnected: (state, action) => {
      state.connected = action.payload;
      if (action.payload) {
        state.status = 'connecting';
      }
    },
    
    /**
     * Clear all events (reset for new generation).
     */
    clearEvents: (state) => {
      state.events = [];
      state.scenes = [];
      state.finalStoryboard = null;
      state.masterPlan = null;
      state.error = null;
      state.currentAgent = null;
    },
    
    /**
     * Reset the entire agent state.
     */
    resetAgent: () => initialState,
  },
});

// Export actions
export const {
  addEvent,
  addScene,
  setMasterPlan,
  setFinalStoryboard,
  setStatus,
  setCurrentAgent,
  setError,
  setConnected,
  clearEvents,
  resetAgent,
} = agentSlice.actions;

// Selectors
export const selectEvents = (state) => state.agent.events;
export const selectScenes = (state) => state.agent.scenes;
export const selectFinalStoryboard = (state) => state.agent.finalStoryboard;
export const selectMasterPlan = (state) => state.agent.masterPlan;
export const selectStatus = (state) => state.agent.status;
export const selectCurrentAgent = (state) => state.agent.currentAgent;
export const selectError = (state) => state.agent.error;
export const selectConnected = (state) => state.agent.connected;

// Filtered event selectors
export const selectEventsByAgent = (state, agentName) =>
  state.agent.events.filter((e) => e.agent === agentName);

export const selectEventsByType = (state, eventType) =>
  state.agent.events.filter((e) => e.event === eventType);

export default agentSlice.reducer;

