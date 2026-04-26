import json
import subprocess


def get_safari_polymarket_data():
    js_code = """
    (function() {
        if (!window.location.href.includes('polymarket.com')) return 'ERROR: NOT_POLYMARKET';
        let title = document.querySelector('h1') ? document.querySelector('h1').innerText : document.title;
        let buttons = Array.from(document.querySelectorAll('button'));
        let prices = buttons
            .map(b => b.innerText)
            .filter(t => t && (t.includes('c') || t.includes('%')))
            .slice(0, 2);

        return JSON.stringify({
            title: title.trim(),
            prices: prices,
            url: window.location.href
        });
    })()
    """

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
        return json.loads(output)
    except Exception as e:
        return {"error": str(e)}


def format_market_string(data):
    if "error" in data:
        return f"Signal Lost: {data['error']}"

    title = data.get("title", "Unknown Market")
    prices = data.get("prices", [])
    price_str = " | ".join(prices) if prices else "Price Data Missing"
    return f"MARKET: {title}\nPRICES: {price_str}\nSOURCE: {data.get('url')}"
