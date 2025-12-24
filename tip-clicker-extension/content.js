// content.js
console.log('[BuzzExt] content.js loaded on', window.location.href);

chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  console.log('[BuzzExt] *** MESSAGE RECEIVED ***', request);

  if (request.action === 'click_tip') {
    console.log('[BuzzExt] Processing click_tip action...');
    
    // Wait a moment for any dynamic content to load
    setTimeout(() => {
      // Try to find the button
      let btn = document.querySelector('button.lv-send-button');
      console.log('[BuzzExt] Button found:', btn);

      if (btn) {
        const isVisible = btn.offsetWidth > 0 && btn.offsetHeight > 0;
        const isEnabled = !btn.disabled;
        
        console.log('[BuzzExt] Button state - visible:', isVisible, 'enabled:', isEnabled);
        
        if (isVisible && isEnabled) {
          console.log('[BuzzExt] Clicking button NOW!');
          btn.focus();
          btn.click();
          sendResponse({ success: true });
        } else {
          console.warn('[BuzzExt] Button not clickable');
          sendResponse({ success: false, reason: 'not clickable' });
        }
      } else {
        console.warn('[BuzzExt] Button NOT FOUND');
        sendResponse({ success: false, reason: 'not found' });
      }
    }, 100);
    
    return true; // Keep channel open for async response
  }
});

console.log('[BuzzExt] Message listener registered');
