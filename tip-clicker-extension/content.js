// content.js
console.log('[BuzzExt] content.js loaded on', window.location.href);

chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  console.log('[BuzzExt] content.js got message:', request);

  if (request.action === 'click_tip') {
    // Try several selectors and log what we get
    const btn1 = document.querySelector('button.lv-send-button');
    const btn2 = document.querySelector('button.el-button.lvs-common-button.lv-send-button.el-button--primary.el-button--mini');

    console.log('[BuzzExt] btn1 (lv-send-button) =', btn1);
    console.log('[BuzzExt] btn2 (full classes) =', btn2);

    const btn = btn1 || btn2;

    if (btn) {
      btn.focus();
      btn.click();
      console.log('[BuzzExt] Tip button CLICKED!', btn);
    } else {
      console.warn('[BuzzExt] Tip button NOT found');
    }

    sendResponse({ success: !!btn });
  }
});
