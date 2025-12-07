import os
import json
import requests
from flask import Flask, request, jsonify
from groq import Groq

# --- CONFIGURATION & SECRETS ---
app = Flask(__name__)

# Load keys from the "Environment Variables" you set in Render
WHATSAPP_TOKEN = os.environ.get("WHATSAPP_TOKEN")
PHONE_NUMBER_ID = os.environ.get("PHONE_NUMBER_ID")
VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN", "my_super_secret_password")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
BOOK_LINK = os.environ.get("BOOK_LINK", "https://yourwebsite.com/buy")

# Initialize the AI Client
client = Groq(api_key=GROQ_API_KEY)

# --- THE BRAIN: OBJECTION HANDLING DATABASE ---
# This dictionary teaches the AI how to win specific arguments.
OBJECTION_DB = {
    "price_expensive": {
        "trigger_keywords": ["expensive", "cost", "money", "broke", "cant afford", "price", "dollars", "cheap"],
        "strategy": "Value Reframe",
        "response": "I hear you. But let me ask you: is the price of the book higher than the cost of staying exactly where you are right now? It's a small investment for a skill that pays you back for life. Do you want the outcome, or do you want to save the cash?"
    },
    "no_time": {
        "trigger_keywords": ["time", "busy", "schedule", "read", "long", "pages", "too much"],
        "strategy": "Format Pivot",
        "response": "That is exactly why you need this. The system is designed for speed. Plus, if you order the paperback now, I'll unlock the Audio Summary instantly. You can absorb the key concepts in 20 minutes while you drive. Fair?"
    },
    "skeptical": {
        "trigger_keywords": ["work", "scam", "real", "legit", "reviews", "sure", "fraud", "lie"],
        "strategy": "Risk Reversal",
        "response": "I understand the hesitation. There's a lot of noise online. That’s why we offer a 30-day 'Action Guarantee'. If you use the frameworks and don't see a shift, just text us here and we refund you. You take zero risk. Ready to try?"
    },
    "later": {
        "trigger_keywords": ["later", "tomorrow", "think", "wait", "next week", "soon"],
        "strategy": "Urgency Injection",
        "response": "You can wait, but the 'Fast-Action Bonus Bundle' is attached to this specific chat session. If you close this chat, the system removes the bonuses. Is it worth losing the extra tools just to wait?"
    }
}

# We convert the database to text so the AI can read it
db_string = json.dumps(OBJECTION_DB)

# The "Personality" of the Bot
SYSTEM_PROMPT = f"""
You are 'Ace', the elite sales AI for the book 'Activate Your Dreams'.
Your goal is to close the sale. You are helpful but authoritative.

Here is your STRICT Playbook (OBJECTION DATABASE):
{db_string}

INSTRUCTIONS:
1. Detect the Objection from the user's text based on the database keywords.
2. If a match is found, adapt the 'response' from the database.
3. If No Objection is found, answer briefly and ask: "Ready to grab your copy?"
4. Keep messages under 50 words.
5. If the user agrees or says YES, strictly output: "Great choice. Here is your secure link: {BOOK_LINK}"
"""

# --- HELPER: Send Message to WhatsApp ---
def send_whatsapp_message(to_number, text_body):
    url = f"https://graph.facebook.com/v17.0/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": to_number,
        "type": "text",
        "text": {"body": text_body}
    }
    try:
        requests.post(url, json=payload, headers=headers)
    except Exception as e:
        print(f"Error sending message: {e}")

# --- HELPER: Ask the AI ---
def get_ai_response(user_message):
    try:
        completion = client.chat.completions.create(
            model="llama3-70b-8192", # Free, fast, smart model
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_message}
            ],
            temperature=0.7,
            max_tokens=150
        )
        return completion.choices[0].message.content
    except Exception as e:
        print(f"AI Error: {e}")
        return "I'm having a bit of trouble connecting. Could you say that again?"

# --- ENDPOINT 1: The Heartbeat (For UptimeRobot) ---
@app.route("/health", methods=["GET"])
def health_check():
    return "OK", 200

# --- ENDPOINT 2: The Webhook Verification (Meta checks this once) ---
@app.route("/webhook", methods=["GET"])
def verify_webhook():
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")

    if mode == "subscribe" and token == VERIFY_TOKEN:
        return challenge, 200
    else:
        return "Forbidden", 403

# --- ENDPOINT 3: Receiving Messages (The Main Loop) ---
@app.route("/webhook", methods=["POST"])
def handle_message():
    data = request.json
    try:
        # Check if it's a valid WhatsApp message
        if data.get("object") == "whatsapp_business_account":
            for entry in data["entry"]:
                for change in entry["changes"]:
                    value = change["value"]
                    
                    # Ensure it's a message (not a status update like 'read' or 'delivered')
                    if "messages" in value:
                        message_data = value["messages"][0]
                        sender_id = message_data["from"]
                        
                        # Only process text messages
                        if message_data["type"] == "text":
                            user_text = message_data["text"]["body"]
                            
                            # 1. Get AI Response
                            ai_reply = get_ai_response(user_text)
                            
                            # 2. Send back to WhatsApp
                            send_whatsapp_message(sender_id, ai_reply)

        return jsonify({"status": "success"}), 200

    except Exception as e:
        print(f"Webhook Error: {e}")
        return jsonify({"status": "error"}), 500

# --- START THE SERVER ---
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
