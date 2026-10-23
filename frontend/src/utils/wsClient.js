/**
 * WebSocket client for real-time agent event streaming.
 * Manages connection lifecycle and dispatches events to Redux store.
 */

import {
  addEvent,
  setStatus,
  setConnected,
  setError,
} from '../store/agentSlice';

/**
 * WebSocket base URL - configure based on environment
 */
const WS_BASE_URL = import.meta.env.VITE_WS_URL || 'ws://localhost:8000';

/**
 * WebSocket client class for managing connections.
 */
class WebSocketClient {
  constructor() {
    this.socket = null;
    this.sessionId = null;
    this.dispatch = null;
    this.reconnectAttempts = 0;
    this.maxReconnectAttempts = 3;
    this.reconnectDelay = 2000;
    this.heartbeatInterval = null;
    this.isManualClose = false;
  }

  /**
   * Connect to WebSocket server for a session.
   * @param {string} sessionId - Session ID to connect to
   * @param {function} dispatch - Redux dispatch function
   * @returns {Promise} Resolves when connected
   */
  connect(sessionId, dispatch) {
    return new Promise((resolve, reject) => {
      this.sessionId = sessionId;
      this.dispatch = dispatch;
      this.isManualClose = false;

      const wsUrl = `${WS_BASE_URL}/ws/${sessionId}`;
      console.log(`Connecting to WebSocket: ${wsUrl}`);

      try {
        this.socket = new WebSocket(wsUrl);

        this.socket.onopen = () => {
          console.log('WebSocket connected');
          this.reconnectAttempts = 0;
          this.dispatch(setConnected(true));
          this.startHeartbeat();
          resolve();
        };

        this.socket.onmessage = (event) => {
          this.handleMessage(event);
        };

        this.socket.onclose = (event) => {
          console.log('WebSocket closed:', event.code, event.reason);
          this.dispatch(setConnected(false));
          this.stopHeartbeat();

          if (!this.isManualClose && this.reconnectAttempts < this.maxReconnectAttempts) {
            this.attemptReconnect();
          }
        };

        this.socket.onerror = (error) => {
          console.error('WebSocket error:', error);
          this.dispatch(setError('WebSocket connection error'));
          reject(error);
        };
      } catch (error) {
        console.error('Failed to create WebSocket:', error);
        reject(error);
      }
    });
  }

  /**
   * Handle incoming WebSocket message.
   * @param {MessageEvent} event - WebSocket message event
   */
  handleMessage(event) {
    try {
      const data = JSON.parse(event.data);
      console.log('WebSocket message:', data);

      // Handle system messages
      if (data.agent === 'system') {
        this.handleSystemMessage(data);
        return;
      }

      // Dispatch agent event to Redux store
      this.dispatch(addEvent(data));

      // Update status based on event type
      if (data.event === 'status') {
        this.dispatch(setStatus('running'));
      } else if (data.event === 'complete') {
        this.dispatch(setStatus('complete'));
      } else if (data.event === 'error') {
        this.dispatch(setError(data.content));
      }
    } catch (error) {
      console.error('Error parsing WebSocket message:', error);
    }
  }

  /**
   * Handle system-level WebSocket messages.
   * @param {object} data - Parsed message data
   */
  handleSystemMessage(data) {
    switch (data.event) {
      case 'connected':
        console.log('Session connected:', data.content);
        break;
      case 'heartbeat':
      case 'pong':
        // Heartbeat received, connection is alive
        break;
      case 'error':
        this.dispatch(setError(data.content));
        break;
      default:
        console.log('System message:', data);
    }
  }

  /**
   * Send a command to the WebSocket server.
   * @param {string} command - Command to send
   * @param {object} data - Additional data
   */
  send(command, data = {}) {
    if (this.socket && this.socket.readyState === WebSocket.OPEN) {
      const message = { command, ...data };
      this.socket.send(JSON.stringify(message));
      console.log('Sent WebSocket message:', message);
    } else {
      console.error('WebSocket not connected');
    }
  }

  /**
   * Start the agent pipeline.
   */
  start() {
    this.send('start');
    this.dispatch(setStatus('running'));
  }

  /**
   * Send a ping to keep connection alive.
   */
  ping() {
    this.send('ping');
  }

  /**
   * Start heartbeat interval.
   */
  startHeartbeat() {
    this.stopHeartbeat();
    this.heartbeatInterval = setInterval(() => {
      if (this.socket && this.socket.readyState === WebSocket.OPEN) {
        this.ping();
      }
    }, 25000); // Send ping every 25 seconds
  }

  /**
   * Stop heartbeat interval.
   */
  stopHeartbeat() {
    if (this.heartbeatInterval) {
      clearInterval(this.heartbeatInterval);
      this.heartbeatInterval = null;
    }
  }

  /**
   * Attempt to reconnect to WebSocket.
   */
  attemptReconnect() {
    this.reconnectAttempts++;
    console.log(`Attempting reconnect (${this.reconnectAttempts}/${this.maxReconnectAttempts})...`);

    setTimeout(() => {
      if (this.sessionId && this.dispatch) {
        this.connect(this.sessionId, this.dispatch).catch((error) => {
          console.error('Reconnect failed:', error);
        });
      }
    }, this.reconnectDelay * this.reconnectAttempts);
  }

  /**
   * Disconnect from WebSocket server.
   */
  disconnect() {
    this.isManualClose = true;
    this.stopHeartbeat();

    if (this.socket) {
      this.socket.close(1000, 'Client disconnect');
      this.socket = null;
    }

    this.sessionId = null;
    this.dispatch = null;
    this.reconnectAttempts = 0;
  }

  /**
   * Check if WebSocket is connected.
   * @returns {boolean} Connection status
   */
  isConnected() {
    return this.socket && this.socket.readyState === WebSocket.OPEN;
  }

  /**
   * Get current connection state.
   * @returns {string} Connection state
   */
  getState() {
    if (!this.socket) return 'DISCONNECTED';
    
    switch (this.socket.readyState) {
      case WebSocket.CONNECTING:
        return 'CONNECTING';
      case WebSocket.OPEN:
        return 'OPEN';
      case WebSocket.CLOSING:
        return 'CLOSING';
      case WebSocket.CLOSED:
        return 'CLOSED';
      default:
        return 'UNKNOWN';
    }
  }
}

// Create singleton instance
const wsClient = new WebSocketClient();

/**
 * Connect to WebSocket and start agent pipeline.
 * @param {string} sessionId - Session ID
 * @param {function} dispatch - Redux dispatch function
 * @returns {Promise} Resolves when started
 */
export const connectAndStart = async (sessionId, dispatch) => {
  try {
    await wsClient.connect(sessionId, dispatch);
    wsClient.start();
    return true;
  } catch (error) {
    console.error('Failed to connect and start:', error);
    dispatch(setError('Failed to connect to server'));
    return false;
  }
};

/**
 * Disconnect from WebSocket.
 */
export const disconnect = () => {
  wsClient.disconnect();
};

/**
 * Check if WebSocket is connected.
 * @returns {boolean} Connection status
 */
export const isConnected = () => {
  return wsClient.isConnected();
};

/**
 * Get WebSocket client instance.
 * @returns {WebSocketClient} Client instance
 */
export const getClient = () => wsClient;

export default wsClient;

