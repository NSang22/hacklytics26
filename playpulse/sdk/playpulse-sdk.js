/**
 * PlayPulse SDK — Universal Game Event Client
 * Lightweight WebSocket-based telemetry for game playtesting.
 * Single file, zero dependencies.
 */
class PlayPulseSDK {
  constructor(sessionId, apiKey, endpoint) {
    this.sessionId = sessionId;
    this.apiKey = apiKey;
    this.startTime = Date.now();
    this.queue = [];
    this.connected = false;
    this.endpoint = endpoint || 'ws://localhost:8000/v1/stream';
    this.ws = new WebSocket(
      `${this.endpoint}?session_id=${encodeURIComponent(sessionId)}&api_key=${encodeURIComponent(apiKey)}`
    );

    this.ws.onopen = () => {
      this.connected = true;
      this.send('session_start', 'connected');
      // Flush queued messages
      this.queue.forEach((msg) => this.ws.send(JSON.stringify(msg)));
      this.queue = [];
    };

    this.ws.onerror = (err) => console.error('[PlayPulse] WebSocket error:', err);
    this.ws.onclose = () => {
      this.connected = false;
    };
  }

  _getTimestamp() {
    return (Date.now() - this.startTime) / 1000;
  }

  send(eventType, eventName, payload = {}) {
    const msg = {
      session_id: this.sessionId,
      event_type: eventType,
      event_name: eventName,
      timestamp: this._getTimestamp(),
      payload,
    };
    if (this.connected) {
      this.ws.send(JSON.stringify(msg));
    } else {
      this.queue.push(msg);
    }
  }

  gameEvent(name, payload = {}) {
    this.send('game_event', name, payload);
  }
  playerAction(name, payload = {}) {
    this.send('player_action', name, payload);
  }
  stateChange(name, payload = {}) {
    this.send('state_change', name, payload);
  }
  milestone(name, payload = {}) {
    this.send('milestone', name, payload);
  }
  metric(name, payload = {}) {
    this.send('metric', name, payload);
  }

  endSession(payload = {}) {
    this.send('session_end', 'complete', {
      ...payload,
      total_time_sec: this._getTimestamp(),
    });
    setTimeout(() => this.ws.close(), 500);
  }
}

// Export for module environments, also available as global
if (typeof module !== 'undefined' && module.exports) {
  module.exports = PlayPulseSDK;
}
