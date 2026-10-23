/**
 * Redux slice for query and domain state management.
 * Handles user input, domain selection, and session information.
 */

import { createSlice, createAsyncThunk } from '@reduxjs/toolkit';

/**
 * API base URL - configure based on environment
 */
const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

/**
 * Async thunk to fetch available domains from the API.
 */
export const fetchDomains = createAsyncThunk(
  'query/fetchDomains',
  async (_, { rejectWithValue }) => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/domains`);
      if (!response.ok) {
        throw new Error('Failed to fetch domains');
      }
      const data = await response.json();
      return data.domains;
    } catch (error) {
      return rejectWithValue(error.message);
    }
  }
);

/**
 * Async thunk to start a new agent session.
 */
export const startSession = createAsyncThunk(
  'query/startSession',
  async ({ domain, query }, { rejectWithValue }) => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/agent/run`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ domain, query }),
      });
      
      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to start session');
      }
      
      const data = await response.json();
      return data;
    } catch (error) {
      return rejectWithValue(error.message);
    }
  }
);

/**
 * Async thunk to fetch a storyboard by session ID.
 */
export const fetchStoryboard = createAsyncThunk(
  'query/fetchStoryboard',
  async (sessionId, { rejectWithValue }) => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/storyboard/${sessionId}`);
      if (!response.ok) {
        throw new Error('Failed to fetch storyboard');
      }
      return await response.json();
    } catch (error) {
      return rejectWithValue(error.message);
    }
  }
);

/**
 * Initial state for the query slice.
 */
const initialState = {
  // Selected domain
  selectedDomain: '',
  // User query text
  query: '',
  // Current session ID
  sessionId: null,
  // Available domains list
  availableDomains: [],
  // Loading state for API calls
  loading: false,
  // Error message
  error: null,
  // Submission status
  submitted: false,
};

/**
 * Query slice with reducers.
 */
const querySlice = createSlice({
  name: 'query',
  initialState,
  reducers: {
    /**
     * Set the selected domain.
     */
    setSelectedDomain: (state, action) => {
      state.selectedDomain = action.payload;
    },
    
    /**
     * Set the query text.
     */
    setQuery: (state, action) => {
      state.query = action.payload;
    },
    
    /**
     * Set the session ID.
     */
    setSessionId: (state, action) => {
      state.sessionId = action.payload;
    },
    
    /**
     * Clear error message.
     */
    clearError: (state) => {
      state.error = null;
    },
    
    /**
     * Reset the query state for a new generation.
     */
    resetQuery: (state) => {
      state.query = '';
      state.sessionId = null;
      state.error = null;
      state.submitted = false;
    },
    
    /**
     * Full reset to initial state.
     */
    fullReset: () => initialState,
  },
  extraReducers: (builder) => {
    // Fetch domains
    builder
      .addCase(fetchDomains.pending, (state) => {
        state.loading = true;
        state.error = null;
      })
      .addCase(fetchDomains.fulfilled, (state, action) => {
        state.loading = false;
        state.availableDomains = action.payload;
        // Set default domain if none selected
        if (!state.selectedDomain && action.payload.length > 0) {
          state.selectedDomain = action.payload[0];
        }
      })
      .addCase(fetchDomains.rejected, (state, action) => {
        state.loading = false;
        state.error = action.payload;
        // Set default domains if API fails
        state.availableDomains = [
          'product_demo',
          'education',
          'medical',
          'marketing',
          'film_style',
          'gaming',
        ];
        if (!state.selectedDomain) {
          state.selectedDomain = 'product_demo';
        }
      });
    
    // Start session
    builder
      .addCase(startSession.pending, (state) => {
        state.loading = true;
        state.error = null;
        state.submitted = true;
      })
      .addCase(startSession.fulfilled, (state, action) => {
        state.loading = false;
        state.sessionId = action.payload.session_id;
      })
      .addCase(startSession.rejected, (state, action) => {
        state.loading = false;
        state.error = action.payload;
        state.submitted = false;
      });
    
    // Fetch storyboard
    builder
      .addCase(fetchStoryboard.pending, (state) => {
        state.loading = true;
      })
      .addCase(fetchStoryboard.fulfilled, (state) => {
        state.loading = false;
      })
      .addCase(fetchStoryboard.rejected, (state, action) => {
        state.loading = false;
        state.error = action.payload;
      });
  },
});

// Export actions
export const {
  setSelectedDomain,
  setQuery,
  setSessionId,
  clearError,
  resetQuery,
  fullReset,
} = querySlice.actions;

// Selectors
export const selectSelectedDomain = (state) => state.query.selectedDomain;
export const selectQuery = (state) => state.query.query;
export const selectSessionId = (state) => state.query.sessionId;
export const selectAvailableDomains = (state) => state.query.availableDomains;
export const selectLoading = (state) => state.query.loading;
export const selectQueryError = (state) => state.query.error;
export const selectSubmitted = (state) => state.query.submitted;

// Export API base URL for use in other modules
export const getApiBaseUrl = () => API_BASE_URL;

export default querySlice.reducer;

