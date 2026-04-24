import subprocess
import json
import sys

def get_safari_polymarket_data():
    """
    Uses AppleScript + JavaScript to extract title and prices from the active Safari tab.
    """
    # JavaScript to execute within the browser context for precise DOM extraction
    js_code = """
    (function() {
        if (!window.location.href.includes('polymarket.com')) return 'ERROR: NOT_POLYMARKET';
        
        // Extract Market Title
        let title = document.querySelector('h1') ? document.querySelector('h1').innerText : document.title;
        
        // Find Yes/No price buttons
        // Polymarket typically uses specific classes or text patterns for prices (e.g., '54¢' or '54%')
        let buttons = Array.from(document.querySelectorAll('button'));
        let prices = buttons
            .map(b => b.innerText)
            .filter(t => t && (t.includes('¢') || t.includes('%')))
            .slice(0, 2); // Get first two (usually Yes and No)

        return JSON.stringify({
            title: title.trim(),
            prices: prices,
            url: window.location.href
        });
    })()
    """

    # AppleScript wrapper
    apple_script = f'''
    if application "Safari" is running then
        tell application "Safari"
            try
                set theData to do JavaScript "{js_code}" in document 1
                return theData
            on error
                return "ERROR: SCRIPT_FAILED"
            end try
        end tell
    else
        return "ERROR: SAFARI_NOT_RUNNING"
    end if
    '''

    try:
        output = subprocess.check_output(["osascript", "-e", apple_script], text=True).strip()
        
        if "ERROR" in output:
            return {"error": output}
            
        data = json.loads(output)
        return data

    except Exception as e:
        return {"error": str(e)}

def format_market_string(data):
    if "error" in data:
        return f"Signal Lost: {data['error']}"
    
    title = data.get('title', 'Unknown Market')
    prices = data.get('prices', [])
    price_str = " | ".join(prices) if prices else "Price Data Missing"
    
    return f"MARKET: {title}\nPRICES: {price_str}\nSOURCE: {data.get('url')}"

if __name__ == "__main__":
    market_data = get_safari_polymarket_data()
    print(format_market_string(market_data))
