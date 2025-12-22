// Listen for messages from background script
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === 'click_tip') {
    // Find and click the tip button
    const button = document.querySelector('.lv-send-button');
    
    if (button) {
      button.click();
      console.log('[Extension] Tip button clicked!');
      sendResponse({success: true});
    } else {
      console.error('[Extension] Tip button not found');
      sendResponse({success: false, error: 'Button not found'});
    }
  }
});
