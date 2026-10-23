/**
 * Redux store configuration for the multi-agent storyboard system.
 */

import { configureStore } from '@reduxjs/toolkit';
import agentReducer from './agentSlice';
import queryReducer from './querySlice';

/**
 * Configure and create the Redux store.
 */
const store = configureStore({
  reducer: {
    agent: agentReducer,
    query: queryReducer,
  },
  middleware: (getDefaultMiddleware) =>
    getDefaultMiddleware({
      serializableCheck: {
        // Ignore these action types for serializable check
        ignoredActions: ['agent/addEvent'],
        // Ignore these paths in the state
        ignoredPaths: ['agent.events'],
      },
    }),
  devTools: process.env.NODE_ENV !== 'production',
});

export default store;

