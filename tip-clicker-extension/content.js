// content.js
console.log('[BuzzExt Content] Script loaded on:', window.location.href);

// Listen for messages from background script
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  console.log('[BuzzExt Content] *** MESSAGE RECEIVED ***:', message);
  
  try {
    if (message.action === 'click_tip') {
      console.log('[BuzzExt Content] Looking for Send Tip button...');
      
      // Find the button
      const button = document.querySelector('button.lv-send-button');
      
      if (button) {
        console.log('[BuzzExt Content] Found Send Tip button! Clicking...');
        button.click();
        sendResponse({ success: true, message: 'Button clicked' });
      } else {
        console.error('[BuzzExt Content] Send Tip button not found!');
        sendResponse({ success: false, message: 'Button not found' });
      }
    } else {
      console.warn('[BuzzExt Content] Unknown action:', message.action);
      sendResponse({ success: false, message: 'Unknown action' });
    }
  } catch (error) {
    console.error('[BuzzExt Content] Error handling message:', error);
    sendResponse({ success: false, message: error.message });
  }
  
  return true; // Keep the message channel open for async response
});

console.log('[BuzzExt Content] Message listener registered');
