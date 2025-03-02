// Background script for opAgent extension
// This runs in the background and manages the extension's state

// Listen for installation
chrome.runtime.onInstalled.addListener(() => {
  console.log('opAgent extension installed');
  
  // Initialize storage with default settings
  chrome.storage.sync.get(['savingsTarget', 'currentSavings'], (result) => {
    if (!result.savingsTarget) {
      chrome.storage.sync.set({ savingsTarget: 1000 }); // Default monthly savings target: $1000
    }
    if (!result.currentSavings) {
      chrome.storage.sync.set({ currentSavings: 650 }); // Default current savings: $650 (65%)
    }
  });
});

// Listen for messages from content script
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.type === 'PURCHASE_DETECTED') {
    // When a purchase is detected, show the popup
    chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
      const activeTab = tabs[0];
      
      // Store the detected price temporarily
      chrome.storage.local.set({ 
        detectedPrice: message.price,
        productName: message.productName,
        productUrl: message.productUrl
      });
      
      // Show the popup notification
      chrome.action.setPopup({ tabId: activeTab.id, popup: "popup.html" });
      
      // Programmatically open the popup
      chrome.action.openPopup();
    });
    
    sendResponse({ status: 'showing_alert' });
    return true;
  }
  
  if (message.type === 'AMAZON_PRODUCT_DETECTED') {
    // When an Amazon product is detected, show the popup
    chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
      const activeTab = tabs[0];
      
      // Store the detected price temporarily
      chrome.storage.local.set({ 
        detectedPrice: message.price,
        productName: message.productName,
        productUrl: message.productUrl
      });
      
      // Show the popup notification
      chrome.action.setPopup({ tabId: activeTab.id, popup: "popup.html" });
      
      // Programmatically open the popup
      chrome.action.openPopup();
    });
    
    sendResponse({ status: 'showing_alert' });
    return true;
  }
});

// Listen for tab updates to detect Amazon
chrome.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
  if (changeInfo.status === 'complete' && tab.url) {
    // Check if the URL is from Amazon and likely a product page
    const isAmazonProduct = tab.url.includes('amazon.com') && 
                           (tab.url.includes('/dp/') || 
                            tab.url.includes('/gp/product/') || 
                            tab.url.includes('/product-reviews/'));
    
    if (isAmazonProduct) {
      console.log('Amazon product page detected');
      
      // Inject the content script for Amazon
      chrome.scripting.executeScript({
        target: { tabId: tabId },
        files: ['content.js']
      }).catch(err => console.error('Script injection failed:', err));
    }
    
    // Also check for other shopping sites
    const shoppingDomains = [
      'ebay.com', 'walmart.com', 'target.com', 'bestbuy.com',
      'etsy.com', 'newegg.com', 'homedepot.com', 'wayfair.com', 'macys.com',
      'nordstrom.com', 'zappos.com', 'costco.com'
    ];
    
    const isOtherShoppingSite = shoppingDomains.some(domain => tab.url.includes(domain));
    
    if (isOtherShoppingSite) {
      // Inject the content script if it's another shopping site
      chrome.scripting.executeScript({
        target: { tabId: tabId },
        files: ['content.js']
      }).catch(err => console.error('Script injection failed:', err));
    }
  }
});