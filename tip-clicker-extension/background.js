// Listen for connections from your bot
const WS_URL = 'ws://192.168.1.127:8080/extension/ws';
let ws = null;

function connect() {
  ws = new WebSocket(WS_URL);
  
  ws.onopen = () => {
    console.log('[Extension] Connected to bot');
  };
  
  ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    
    if (data.action === 'click_tip') {
      // Send message to content script to click the button
      chrome.tabs.query({active: true, currentWindow: true}, (tabs) => {
        chrome.tabs.sendMessage(tabs[0].id, {action: 'click_tip'});
      });
    }
  };
  
  ws.onerror = (error) => {
    console.error('[Extension] WebSocket error:', error);
  };
  
  ws.onclose = () => {
    console.log('[Extension] Disconnected, reconnecting in 5s...');
    setTimeout(connect, 5000);
  };
}

connect();
