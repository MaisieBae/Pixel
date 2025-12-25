// background.js
const WS_URL = 'ws://192.168.1.127:8080/extension/ws';

let ws = null;
let pingInterval = null;

function connect() {
  console.log('[BuzzExt] Connecting to bot at', WS_URL);
  ws = new WebSocket(WS_URL);

  ws.onopen = () => {
    console.log('[BuzzExt] Connected to bot');
    
    // Start sending pings every 30 seconds to keep connection alive
    pingInterval = setInterval(() => {
      if (ws && ws.readyState === WebSocket.OPEN) {
        console.log('[BuzzExt] Sending ping');
        ws.send(JSON.stringify({ type: 'ping' }));
      }
    }, 30000);
  };

  ws.onmessage = (event) => {
    console.log('[BuzzExt] Message from bot:', event.data);

    let data;
    try {
      data = JSON.parse(event.data);
    } catch (e) {
      console.error('[BuzzExt] Invalid JSON:', event.data);
      return;
    }

    // Ignore pong messages
    if (data.type === 'pong') {
      console.log('[BuzzExt] Received pong');
      return;
    }

    if (data.action === 'click_tip') {
      console.log('[BuzzExt] click_tip action received');
      
      // Query ALL joystick.tv tabs
      chrome.tabs.query({ url: '*://joystick.tv/*' }, (tabs) => {
        console.log('[BuzzExt] Found tabs:', tabs.length);
        
        if (!tabs.length) {
          console.warn('[BuzzExt] No joystick.tv tabs found');
          return;
        }
        
        // Send to all matching tabs
        let sentCount = 0;
        tabs.forEach((tab) => {
          console.log(`[BuzzExt] Sending to tab ${tab.id}: ${tab.url}`);
          
          chrome.tabs.sendMessage(
            tab.id,
            { action: 'click_tip' },
            (response) => {
              if (chrome.runtime.lastError) {
                console.error(
                  `[BuzzExt] Tab ${tab.id} error:`,
                  chrome.runtime.lastError.message
                );
              } else {
                console.log(`[BuzzExt] Tab ${tab.id} response:`, response);
                sentCount++;
              }
            }
          );
        });
        
        console.log(`[BuzzExt] Message sent to ${sentCount} tab(s)`);
      });
    }
  };

  ws.onerror = (err) => {
    console.error('[BuzzExt] WebSocket error:', err);
  };

  ws.onclose = () => {
    console.log('[BuzzExt] Disconnected from bot, reconnecting in 5s...');
    
    // Clear ping interval
    if (pingInterval) {
      clearInterval(pingInterval);
      pingInterval = null;
    }
    
    // Reconnect after delay
    setTimeout(connect, 5000);
  };
}

connect();
