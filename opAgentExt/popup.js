// Popup script for opAgent extension
// This handles the popup UI and interactions

document.addEventListener('DOMContentLoaded', function() {
  // Get elements
  const priceTag = document.querySelector('.price-tag');
  const continueButton = document.getElementById('continueButton');
  const cancelButton = document.getElementById('cancelButton');
  const savingsTarget = document.querySelector('p strong:first-of-type');
  const savingsProgress = document.querySelector('p strong:nth-of-type(2)');
  const remainingBudget = document.querySelector('p strong:last-of-type');
  const savingsTip = document.querySelector('.savings-tip');
  
  // Get stored data
  chrome.storage.local.get(['detectedPrice', 'productName', 'productUrl'], function(data) {
    if (data.detectedPrice) {
      // Update price display
      priceTag.textContent = `$${data.detectedPrice.toFixed(2)}`;
      
      // Get savings data
      chrome.storage.sync.get(['savingsTarget', 'currentSavings'], function(result) {
        const target = result.savingsTarget || 1000;
        const current = result.currentSavings || 650;
        const remaining = target - current;
        
        // Update savings info
        savingsTarget.textContent = `$${target}`;
        savingsProgress.textContent = `${Math.round((current/target) * 100)}%`;
        remainingBudget.textContent = `$${remaining.toFixed(2)}`;
        
        // Calculate percentage of savings target
        const percentOfTarget = (data.detectedPrice / target) * 100;
        savingsTip.textContent = `This purchase is equivalent to ${percentOfTarget.toFixed(0)}% of your monthly savings target.`;
      });
    }
  });
  
  // Continue button handler
  continueButton.addEventListener('click', function() {
    // Get the product URL
    chrome.storage.local.get(['productUrl'], function(data) {
      if (data.productUrl) {
        // Close popup and continue to site
        chrome.tabs.query({active: true, currentWindow: true}, function(tabs) {
          chrome.tabs.update(tabs[0].id, {url: data.productUrl});
          window.close();
        });
      }
    });
  });
  
  // Cancel button handler
  cancelButton.addEventListener('click', function() {
    // Just close the popup
    window.close();
  });
});