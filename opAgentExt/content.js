// Content script for opAgent extension
// This runs on web pages and detects shopping activities

// Function to extract price from Amazon page
function extractAmazonPrice() {
  // Amazon-specific price selectors
  const amazonPriceSelectors = [
    '#priceblock_ourprice', 
    '#priceblock_dealprice', 
    '#priceblock_saleprice',
    '.a-price .a-offscreen',
    '#corePrice_feature_div .a-price .a-offscreen',
    '#corePriceDisplay_desktop_feature_div .a-price .a-offscreen',
    '.a-section .a-price .a-offscreen'
  ];
  
  for (const selector of amazonPriceSelectors) {
    const elements = document.querySelectorAll(selector);
    for (const element of elements) {
      const text = element.textContent.trim();
      const priceMatch = text.match(/\$?(\d+(\.\d{1,2})?)/);
      
      if (priceMatch && priceMatch[1]) {
        const price = parseFloat(priceMatch[1]);
        if (price > 0 && price < 10000) { // Reasonable price range
          return price;
        }
      }
    }
  }
  
  // If Amazon-specific selectors fail, try generic price extraction
  return extractPrice();
}

// Function to extract price from the page
function extractPrice() {
  // Common price selectors used by popular shopping sites
  const priceSelectors = [
    '.price', '#price', '.product-price', '.offer-price', '.sales-price',
    '[data-price]', '[itemprop="price"]', '.current-price', '.a-price',
    '.product_price', '.product-price', '.price-value', '.price-current',
    '.product-info-price', '.product-price-value', '.product_amount'
  ];
  
  // Try each selector until we find a price
  for (const selector of priceSelectors) {
    const elements = document.querySelectorAll(selector);
    for (const element of elements) {
      // Extract text and look for price patterns
      const text = element.textContent.trim();
      const priceMatch = text.match(/\$?(\d+(\.\d{1,2})?)/);
      
      if (priceMatch && priceMatch[1]) {
        const price = parseFloat(priceMatch[1]);
        if (price > 0 && price < 10000) { // Reasonable price range
          return price;
        }
      }
      
      // Check for data-price attribute
      const dataPrice = element.getAttribute('data-price');
      if (dataPrice) {
        const price = parseFloat(dataPrice);
        if (price > 0 && price < 10000) {
          return price;
        }
      }
    }
  }
  
  // Fallback: scan the entire page for price patterns
  const bodyText = document.body.textContent;
  const priceMatches = bodyText.match(/\$\s?(\d+(\.\d{1,2})?)/g);
  
  if (priceMatches && priceMatches.length > 0) {
    // Get the most prominent price (assuming it appears first or most frequently)
    const priceStr = priceMatches[0].replace('$', '').trim();
    const price = parseFloat(priceStr);
    if (price > 0 && price < 10000) {
      return price;
    }
  }
  
  return null;
}

// Function to extract product name from Amazon
function extractAmazonProductName() {
  // Amazon-specific product name selectors
  const amazonNameSelectors = [
    '#productTitle',
    '#title',
    '.product-title'
  ];
  
  for (const selector of amazonNameSelectors) {
    const element = document.querySelector(selector);
    if (element) {
      const text = element.textContent.trim();
      if (text && text.length > 3) {
        return text;
      }
    }
  }
  
  // If Amazon-specific selectors fail, try generic name extraction
  return extractProductName();
}

// Function to extract product name
function extractProductName() {
  // Common product name selectors
  const nameSelectors = [
    'h1', '.product-title', '.product-name', '[itemprop="name"]',
    '.product_title', '.product-single__title', '.product-info__title',
    '#productTitle', '.item-title', '.product-detail-name'
  ];
  
  for (const selector of nameSelectors) {
    const elements = document.querySelectorAll(selector);
    for (const element of elements) {
      const text = element.textContent.trim();
      if (text && text.length > 3 && text.length < 200) {
        return text;
      }
    }
  }
  
  // Fallback to page title
  const titleParts = document.title.split('|');
  if (titleParts.length > 0 && titleParts[0].trim().length > 3) {
    return titleParts[0].trim();
  }
  
  return "Product";
}

// Function to detect checkout or add-to-cart actions
function detectPurchaseIntent() {
  // Listen for clicks on buttons that might indicate purchase intent
  document.addEventListener('click', (event) => {
    const clickedElement = event.target;
    const buttonText = clickedElement.textContent.toLowerCase();
    const buttonClasses = clickedElement.className.toLowerCase();
    const buttonId = clickedElement.id.toLowerCase();
    
    // Check if the clicked element is a purchase-related button
    const purchaseKeywords = [
      'add to cart', 'buy now', 'checkout', 'purchase', 'place order',
      'complete order', 'submit order', 'pay now', 'proceed to checkout'
    ];
    
    const isPurchaseButton = purchaseKeywords.some(keyword => 
      buttonText.includes(keyword) || 
      buttonClasses.includes(keyword) || 
      buttonId.includes(keyword)
    );
    
    if (isPurchaseButton) {
      const price = isAmazonSite() ? extractAmazonPrice() : extractPrice();
      if (price) {
        // Send message to background script
        chrome.runtime.sendMessage({
          type: 'PURCHASE_DETECTED',
          price: price,
          productName: isAmazonSite() ? extractAmazonProductName() : extractProductName(),
          productUrl: window.location.href
        });
        
        // Prevent the default action to show our popup first
        event.preventDefault();
        event.stopPropagation();
      }
    }
  }, true); // Use capture to intercept events before they reach the target
}

// Function to check if we're on Amazon
function isAmazonSite() {
  return window.location.hostname.includes('amazon.com');
}

// Function to handle Amazon product pages specifically
function handleAmazonProduct() {
  // Check if we're on a product page
  const isProductPage = window.location.href.includes('/dp/') || 
                        window.location.href.includes('/gp/product/') ||
                        window.location.href.includes('/product-reviews/');
  
  if (isProductPage) {
    // Extract price and product name
    const price = extractAmazonPrice();
    const productName = extractAmazonProductName();
    
    if (price) {
      console.log(`Amazon product detected: ${productName} - $${price}`);
      
      // Send message to background script
      chrome.runtime.sendMessage({
        type: 'AMAZON_PRODUCT_DETECTED',
        price: price,
        productName: productName,
        productUrl: window.location.href
      });
    }
  }
}

// Function to observe DOM changes for dynamic content
function observePageChanges() {
  // Create a MutationObserver to watch for changes to the page
  const observer = new MutationObserver((mutations) => {
    // Check if price elements have been added
    const price = isAmazonSite() ? extractAmazonPrice() : extractPrice();
    if (price && price > 50) { // Only trigger for higher-priced items
      // Store the detected price
      chrome.storage.local.set({ 
        detectedPrice: price,
        productName: isAmazonSite() ? extractAmazonProductName() : extractProductName(),
        productUrl: window.location.href
      });
    }
  });
  
  // Start observing the document with the configured parameters
  observer.observe(document.body, { 
    childList: true, 
    subtree: true,
    attributes: true,
    characterData: true
  });
}

// Initialize the content script
function initialize() {
  console.log('opAgent content script initialized');
  
  // Check if we're on Amazon
  if (isAmazonSite()) {
    console.log('Amazon site detected');
    handleAmazonProduct();
  } else {
    // For other sites, check if we're on a product page by looking for price
    const price = extractPrice();
    if (price) {
      console.log(`Detected product price: $${price}`);
      
      // Store the detected price
      chrome.storage.local.set({ 
        detectedPrice: price,
        productName: extractProductName(),
        productUrl: window.location.href
      });
    }
  }
  
  // Set up purchase detection
  detectPurchaseIntent();
  
  // Observe page changes
  observePageChanges();
}

// Run the initialization
initialize();