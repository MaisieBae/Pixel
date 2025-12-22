// background.js
const WS_URL = 'ws://192.168.1.127:8080/extension/ws';  // your bot

let ws = null;

function connect() {
  console.log('[BuzzExt] Connecting to bot at', WS_URL);
  ws = new WebSocket(WS_URL);

  ws.onopen = () => {
    console.log('[BuzzExt] Connected to bot');
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

    if (data.action === 'click_tip') {
      console.log('[BuzzExt] click_tip action received');
      chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
        if (!tabs.length) {
          console.warn('[BuzzExt] No active tab to send message to');
          return;
        }
        chrome.tabs.sendMessage(
          tabs[0].id,
          { action: 'click_tip' },
          (response) => {
            if (chrome.runtime.lastError) {
              console.error(
                '[BuzzExt] sendMessage error:',
                chrome.runtime.lastError.message
              );
            } else {
              console.log('[BuzzExt] content response:', response);
            }
          }
        );
      });
    }
  };

  ws.onerror = (err) => {
    console.error('[BuzzExt] WebSocket error:', err);
  };

  ws.onclose = () => {
    console.log('[BuzzExt] Disconnected from bot, reconnecting in 5s...');
    setTimeout(connect, 5000);
  };
}

connect();
