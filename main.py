import os
import logging
import requests
import random
import string
from datetime import datetime
from flask import Flask, request, jsonify, render_template
import json
import traceback
from enum import Enum
from upstash_redis import Redis

app = Flask(__name__)

# Environment variables
wa_token = os.environ.get("WA_TOKEN")
phone_id = os.environ.get("PHONE_ID")
redis_url = os.environ.get("REDIS_URL")
owner_phone = os.environ.get("OWNER_PHONE")
AGENT_NUMBERS = ["+263785019494"]

# Redis client setup
redis_client = Redis(
    url=os.environ.get('UPSTASH_REDIS_URL'),
    token=os.environ.get('UPSTASH_REDIS_TOKEN')
)

# Test connection
try:
    redis_client.set("foo", "bar")
    print("✅ Upstash Redis connection successful")
except Exception as e:
    print(f"❌ Upstash Redis error: {e}")
    raise
    
logging.basicConfig(level=logging.INFO)

class MainMenuOptions(Enum):
    CAKES = "View Cake Options"
    CUPCAKES = "Cupcakes"
    PLACE_ORDER = "Place an Order"
    PRICING = "Pricing Information"
    CONTACT = "Contact Us"
    AGENT = "Speak to an Agent"

class PaymentOptions(Enum):
    ECOCASH = "Ecocash"
    INNBUCKS = "InnBucks"
    OMARI = "Omari"

class CakeTypeOptions(Enum):
    FRESH_CREAM = "Fresh Cream Cakes"
    FRUIT = "Fruit Cakes"
    PLASTIC_ICING = "Plastic Icing Cakes"
    BACK = "Back to main menu"

class FreshCreamOptions(Enum):
    CAKE_FAIRY = "Cake Fairy Cake - $20"
    DOUBLE_DELITE = "Double Delite (2 flavours) - $25"
    TRIPLE_DELITE = "Triple Delite (3 flavours) - $30"
    SMALL = "Small 6" - $30"
    LARGE = "Large 8" - $40"
    LARGE_10 = "Large 10" - $60"
    XL = "Extra Large 12" - $80"
    EXTRA_TALL = "Extra Tall Cake 7" - $65"
    BACK = "Back to cake types"

class TierCakesOptions(Enum):
    TWO_TIER = "2 Tier Cakes - Fresh Cream"
    THREE_TIER = "3 Tier Cakes - Fresh Cream"
    BACK = "Back to cake types"

class TwoTierOptions(Enum):
    SIZE_4_6 = "4 inch + 6 inch - $60"
    SIZE_5_7 = "5 inch + 7 inch - $80"
    SIZE_6_8 = "6 inch + 8 inch - $110"
    SIZE_7_9 = "7 inch + 9 inch - $140"
    SIZE_8_10 = "8 inch + 10 inch - $170"
    FONDANT = "Fondant Additional - $20"
    GANACHE = "Ganache Additional - $10"
    SMBC = "SMBC Additional - $15"
    BACK = "Back to tier options"

class ThreeTierOptions(Enum):
    SIZE_4_6_8 = "4 inch + 6 inch + 8 inch - $140"
    SIZE_5_7_9 = "5 inch + 7 inch + 9 inch - $170"
    SIZE_6_8_10 = "6 inch + 8 inch + 10 inch - $210"
    FONDANT = "Fondant Additional - $20"
    GANACHE = "Ganache Additional - $10"
    SMBC = "SMBC Additional - $15"
    BACK = "Back to tier options"

class FruitCakeOptions(Enum):
    SIZE_6 = "6 inch - $40"
    SIZE_8 = "8 inch - $70"
    BACK = "Back to cake types"

class PlasticIcingOptions(Enum):
    SMALL = "Small - $40"
    MEDIUM = "Medium - $50"
    LARGE = "Large - $70"
    XL = "Extra Large - $100"
    BACK = "Back to cake types"

class OrderOptions(Enum):
    NEW_ORDER = "Start New Order"
    EXISTING_ORDER = "Check Existing Order"
    BACK = "Back to main menu"

class ContactOptions(Enum):
    CALLBACK = "Request a call back"
    DIRECT = "Direct contact information"
    BACK = "Back to main menu"

class User:
    def __init__(self, name, phone):
        self.name = name
        self.phone = phone
        self.email = None
        self.cake_type = None
        self.cake_size = None
        self.flavor = None
        self.filling = None
        self.icing = None
        self.shape = None
        self.theme = None
        self.due_date = None
        self.due_time = None
        self.message = None
        self.colors = None
        self.special_requests = None
        self.referral_source = None
        self.callback_requested = False
        self.payment_method = None

    def to_dict(self):
        return {
            "name": self.name,
            "phone": self.phone,
            "email": self.email,
            "cake_type": self.cake_type.value if self.cake_type else None,
            "cake_size": self.cake_size,
            "flavor": self.flavor,
            "filling": self.filling,
            "icing": self.icing,
            "shape": self.shape,
            "theme": self.theme,
            "due_date": self.due_date,
            "due_time": self.due_time,
            "message": self.message,
            "colors": self.colors,
            "special_requests": self.special_requests,
            "referral_source": self.referral_source,
            "callback_requested": self.callback_requested,
            "payment_method": self.payment_method
        }

    @classmethod
    def from_dict(cls, data):
        user = cls(data["name"], data["phone"])
        user.email = data.get("email")
        if data.get("cake_type"):
            # Map cake type string back to enum
            for option in CakeTypeOptions:
                if data["cake_type"] == option.value:
                    user.cake_type = option
                    break
        user.cake_size = data.get("cake_size")
        user.flavor = data.get("flavor")
        user.filling = data.get("filling")
        user.icing = data.get("icing")
        user.shape = data.get("shape")
        user.theme = data.get("theme")
        user.due_date = data.get("due_date")
        user.due_time = data.get("due_time")
        user.message = data.get("message")
        user.colors = data.get("colors")
        user.special_requests = data.get("special_requests")
        user.referral_source = data.get("referral_source")
        user.callback_requested = data.get("callback_requested", False)
        user.payment_method = data.get("payment_method")
        return user

# Phone number normalization function
def normalize_phone_number(phone):
    """Normalize phone number to handle different formats"""
    if not phone:
        return phone
    
    # Remove any non-digit characters except +
    cleaned = ''.join(c for c in phone if c.isdigit() or c == '+')
    
    # Handle Zimbabwe numbers
    if cleaned.startswith('+263'):
        return cleaned
    elif cleaned.startswith('263'):
        return '+' + cleaned
    elif cleaned.startswith('0'):
        return '+263' + cleaned[1:]
    else:
        return cleaned

# Redis state functions
def log_conversation(phone_number, direction, message_type, payload):
    try:
        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'direction': direction,  # 'in' or 'out' or 'state'
            'type': message_type,    # 'text' | 'button' | 'list' | 'state' | 'raw'
            'payload': payload,
        }
        redis_client.lpush(f"conversation:{phone_number}", json.dumps(log_entry))
        redis_client.ltrim(f"conversation:{phone_number}", 0, 499)
    except Exception as e:
        logging.error(f"Failed to log conversation: {e}")
def get_user_state(phone_number):
    state_json = redis_client.get(f"user_state:{phone_number}")
    if state_json:
        state = json.loads(state_json)
        print(f"Retrieved state for {phone_number}: {state}")
        return state
    default_state = {'step': 'welcome', 'sender': phone_number}
    print(f"No state found for {phone_number}, returning default: {default_state}")
    return default_state

def update_user_state(phone_number, updates):
    print("#########################")
    print(f"Updating state for {phone_number}")
    print(f"Updates: {updates}")
    current = get_user_state(phone_number)
    print(f"Current state: {current}")
    current.update(updates)
    current['phone_number'] = phone_number
    if 'sender' not in current:
        current['sender'] = phone_number
    print(f"Final state to save: {current}")
    redis_client.setex(f"user_state:{phone_number}", 86400, json.dumps(current))
    print(f"State saved for {phone_number}")
    # Log state snapshot
    try:
        log_conversation(phone_number, 'state', 'state', current)
    except Exception:
        pass

def send_message(text, recipient, phone_id):
    url = f"https://graph.facebook.com/v19.0/{phone_id}/messages"
    headers = {
        'Authorization': f'Bearer {wa_token}',
        'Content-Type': 'application/json'
    }
    
    if len(text) > 3000:
        parts = [text[i:i+3000] for i in range(0, len(text), 3000)]
        for part in parts:
            data = {
                "messaging_product": "whatsapp",
                "to": recipient,
                "type": "text",
                "text": {"body": part}
            }
            try:
                requests.post(url, headers=headers, json=data)
            except requests.exceptions.RequestException as e:
                logging.error(f"Failed to send message: {e}")
        return
    
    data = {
        "messaging_product": "whatsapp",
        "to": recipient,
        "type": "text",
        "text": {"body": text}
    }
    try:
        response = requests.post(url, headers=headers, json=data)
        response.raise_for_status()
        # Log outgoing text
        try:
            log_conversation(recipient, 'out', 'text', {'text': text})
        except Exception:
            pass
    except requests.exceptions.RequestException as e:
        logging.error(f"Failed to send message: {e}")

def send_button_message(text, buttons, recipient, phone_id):
    url = f"https://graph.facebook.com/v19.0/{phone_id}/messages"
    headers = {
        'Authorization': f'Bearer {wa_token}',
        'Content-Type': 'application/json'
    }
    
    # Validate recipient phone number
    if not recipient or not recipient.strip():
        print(f"Invalid recipient: {recipient}")
        return False
    
    # Ensure recipient is in international format
    original_recipient = recipient
    if recipient.startswith('0'):
        recipient = '+263' + recipient[1:]
    elif not recipient.startswith('+'):
        recipient = '+' + recipient
    
    print(f"Original recipient: {original_recipient}")
    print(f"Normalized recipient: {recipient}")
    
    # Try different phone number formats if the first one fails
    phone_formats = [recipient]
    if recipient.startswith('+263'):
        phone_formats.append(recipient[1:])  # Remove +
        phone_formats.append('0' + recipient[4:])  # Local format
    elif recipient.startswith('263'):
        phone_formats.append('+' + recipient)
        phone_formats.append('0' + recipient[3:])  # Local format
    
    print(f"Phone formats to try: {phone_formats}")
    
    # Try the first format first
    recipient = phone_formats[0]
    
    # WhatsApp button message format
    button_items = []
    for i, button in enumerate(buttons[:3]):  # WhatsApp allows max 3 buttons
        button_id = button.get("id", f"button_{i+1}")
        button_title = button.get("title", "Button")
        
        # Ensure button title is within WhatsApp limits
        if len(button_title) > 20:
            button_title = button_title[:17] + "..."
        
        # Ensure button ID is valid
        if not button_id or len(button_id) > 256:
            button_id = f"button_{i+1}"
        
        button_items.append({
            "type": "reply",
            "reply": {
                "id": button_id,
                "title": button_title
            }
        })
        
        print(f"Button {i+1}: id='{button_id}', title='{button_title}'")
    
    if not button_items:
        print("No valid buttons found, falling back to text message")
        fallback_text = f"{text}\n\n" + "\n".join(f"- {btn.get('title', 'Option')}" for btn in buttons[:3])
        send_message(fallback_text, recipient, phone_id)
        return False
    
    # Ensure text is within WhatsApp limits and clean it
    if len(text) > 1024:
        text = text[:1021] + "..."
    
    # Clean text of any problematic characters
    text = text.replace('\x00', '').replace('\r', '\n').strip()
    
    # Ensure text is not empty
    if not text:
        text = "New message"
    
    print(f"Final text to send: '{text}' (length: {len(text)})")
    
    data = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": recipient,
        "type": "interactive",
        "interactive": {
            "type": "button",
            "body": {
                "text": text
            },
            "action": {
                "buttons": button_items
            }
        }
    }
    
    print(f"Final data to send: {json.dumps(data, indent=2)}")
    
    try:
        print(f"Sending button message to {recipient}: {data}")
        response = requests.post(url, headers=headers, json=data)
        response.raise_for_status()
        print(f"Button message sent successfully to {recipient}")
        try:
            log_conversation(recipient, 'out', 'button', {'text': text, 'buttons': buttons})
        except Exception:
            pass
        return True
    except requests.exceptions.RequestException as e:
        logging.error(f"Failed to send button message: {e}")
        print(f"Button message failed: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"Response status: {e.response.status_code}")
            print(f"Response text: {e.response.text}")
            print(f"Response headers: {dict(e.response.headers)}")
            
            # Try to parse the error response
            try:
                error_data = e.response.json()
                print(f"Error details: {error_data}")
                if 'error' in error_data:
                    print(f"Error message: {error_data['error'].get('message', 'Unknown error')}")
                    print(f"Error code: {error_data['error'].get('code', 'Unknown code')}")
            except:
                print("Could not parse error response as JSON")
        
        # Fallback to simple text message
        fallback_text = f"{text}\n\n" + "\n".join(f"- {btn.get('title', 'Option')}" for btn in buttons[:3])
        send_message(fallback_text, recipient, phone_id)
        return False

def send_list_message(text, options, recipient, phone_id):
    url = f"https://graph.facebook.com/v19.0/{phone_id}/messages"
    headers = {
        'Authorization': f'Bearer {wa_token}',
        'Content-Type': 'application/json'
    }
    
    # Validate and prepare the list items
    formatted_rows = []
    for i, option in enumerate(options[:10]):  # WhatsApp allows max 10 items
        formatted_rows.append({
            "id": f"option_{i+1}",
            "title": option[:24],  # Max 24 characters for title
            "description": option[24:72] if len(option) > 24 else ""  # Optional description
        })
    
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": recipient,
        "type": "interactive",
        "interactive": {
            "type": "list",
            "header": {
                "type": "text",
                "text": ""[:60]  # Max 60 chars for header
            },
            "body": {
                "text": text[:1024]  # Max 1024 chars for body
            },
            "footer": {
                "text": " "[:60]  # Max 60 chars for footer
            },
            "action": {
                "button": "Options"[:20],  # Max 20 chars for button text
                "sections": [
                    {
                        "title": "Available Options"[:24],  # Max 24 chars for section title
                        "rows": formatted_rows
                    }
                ]
            }
        }
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        logging.info(f"List message sent successfully to {recipient}")
        try:
            log_conversation(recipient, 'out', 'list', {'text': text, 'options': options})
        except Exception:
            pass
        return True
    except requests.exceptions.HTTPError as e:
        error_detail = f"Status: {e.response.status_code}, Response: {e.response.text}"
        logging.error(f"Failed to send list message: {error_detail}")
        # Fallback to simple message if list fails
        fallback_msg = f"{text}\n\n" + "\n".join(f"{i+1}. {opt}" for i, opt in enumerate(options[:10]))
        send_message(fallback_msg, recipient, phone_id)
        return False
    except Exception as e:
        logging.error(f"Unexpected error sending list message: {str(e)}")
        return False

# Handlers
def handle_welcome(prompt, user_data, phone_id):
    welcome_msg = (
        "🎂 *Welcome to Cake Fairy!* 🎂\n\n"
        "We create delicious, beautifully decorated cakes for all occasions.\n"
        "Fresh cream is the default filling for all our $20 cakes.\n\n"
        "Please choose an option to continue:"
    )
    
    menu_options = [option.value for option in MainMenuOptions]
    send_list_message(
        welcome_msg,
        menu_options,
        user_data['sender'],
        phone_id
    )
    
    update_user_state(user_data['sender'], {'step': 'main_menu'})
    return {'step': 'main_menu'}

def handle_main_menu(prompt, user_data, phone_id):
    try:
        selected_option = None
        for option in MainMenuOptions:
            if prompt.lower() in option.value.lower():
                selected_option = option
                break
                
        if not selected_option:
            send_message("Invalid selection. Please choose an option from the list.", user_data['sender'], phone_id)
            return {'step': 'main_menu'}
        
        if selected_option == MainMenuOptions.CAKES:
            cake_types_msg = "Please select the type of cake you're interested in:"
            cake_options = [option.value for option in CakeTypeOptions]
            send_list_message(
                cake_types_msg,
                cake_options,
                user_data['sender'],
                phone_id
            )
            update_user_state(user_data['sender'], {'step': 'cake_types_menu'})
            return {'step': 'cake_types_menu'}
            
        elif selected_option == MainMenuOptions.CUPCAKES:
            send_message(
                "Our cupcakes start at $15 per dozen. Please provide more details about your cupcake needs:\n"
                "- Quantity\n"
                "- Flavors\n"
                "- Decorations\n"
                "- Any special requests",
                user_data['sender'],
                phone_id
            )
            update_user_state(user_data['sender'], {'step': 'cupcake_inquiry'})
            return {'step': 'cupcake_inquiry'}
            
        elif selected_option == MainMenuOptions.PLACE_ORDER:
            order_msg = "Would you like to start a new order or check an existing order?"
            order_options = [option.value for option in OrderOptions]
            send_list_message(
                order_msg,
                order_options,
                user_data['sender'],
                phone_id
            )
            update_user_state(user_data['sender'], {'step': 'order_menu'})
            return {'step': 'order_menu'}
            
        elif selected_option == MainMenuOptions.PRICING:
            pricing_msg = (
                "💰 *Pricing Information* 💰\n\n"
                "Our cakes range from $20 to $210 depending on size, type, and decorations.\n\n"
                "Please select a cake type to see detailed pricing:"
            )
            cake_options = [option.value for option in CakeTypeOptions if option != CakeTypeOptions.BACK]
            send_list_message(
                pricing_msg,
                cake_options,
                user_data['sender'],
                phone_id
            )
            update_user_state(user_data['sender'], {'step': 'pricing_menu'})
            return {'step': 'pricing_menu'}
            
        elif selected_option == MainMenuOptions.CONTACT:
            contact_msg = "How would you like to contact us?"
            contact_options = [option.value for option in ContactOptions]
            send_list_message(
                contact_msg,
                contact_options,
                user_data['sender'],
                phone_id
            )
            update_user_state(user_data['sender'], {'step': 'contact_menu'})
            return {'step': 'contact_menu'}
            
        elif selected_option == MainMenuOptions.AGENT:
            return human_agent("", user_data, phone_id)
            
    except Exception as e:
        logging.error(f"Error in handle_main_menu: {e}")
        send_message("An error occurred. Please try again.", user_data['sender'], phone_id)
        return {'step': 'welcome'}

def handle_cake_types_menu(prompt, user_data, phone_id):
    try:
        selected_option = None
        for option in CakeTypeOptions:
            if prompt.lower() in option.value.lower():
                selected_option = option
                break
                
        if not selected_option:
            send_message("Invalid selection. Please choose an option from the list.", user_data['sender'], phone_id)
            return {'step': 'cake_types_menu'}
            
        if selected_option == CakeTypeOptions.FRESH_CREAM:
            fresh_cream_msg = "Please select a Fresh Cream Cake option:"
            fresh_cream_options = [option.value for option in FreshCreamOptions]
            send_list_message(
                fresh_cream_msg,
                fresh_cream_options,
                user_data['sender'],
                phone_id
            )
            update_user_state(user_data['sender'], {'step': 'fresh_cream_menu'})
            return {'step': 'fresh_cream_menu'}
            
        elif selected_option == CakeTypeOptions.FRUIT:
            fruit_msg = "Please select a Fruit Cake option:"
            fruit_options = [option.value for option in FruitCakeOptions]
            send_list_message(
                fruit_msg,
                fruit_options,
                user_data['sender'],
                phone_id
            )
            update_user_state(user_data['sender'], {'step': 'fruit_cake_menu'})
            return {'step': 'fruit_cake_menu'}
            
        elif selected_option == CakeTypeOptions.PLASTIC_ICING:
            plastic_msg = "Please select a Plastic Icing Cake option:"
            plastic_options = [option.value for option in PlasticIcingOptions]
            send_list_message(
                plastic_msg,
                plastic_options,
                user_data['sender'],
                phone_id
            )
            update_user_state(user_data['sender'], {'step': 'plastic_icing_menu'})
            return {'step': 'plastic_icing_menu'}
            
        elif selected_option == CakeTypeOptions.BACK:
            return handle_restart_confirmation("", user_data, phone_id)
            
    except Exception as e:
        logging.error(f"Error in handle_cake_types_menu: {e}")
        send_message("An error occurred. Please try again.", user_data['sender'], phone_id)
        return {'step': 'welcome'}

def handle_restart_confirmation(prompt, user_data, phone_id):
    try:
        text = (prompt or "").strip().lower()

        # Initial entry or unrecognized input -> show Yes/No buttons
        if text == "" or text in ["restart", "start", "menu"]:
            send_button_message(
                "Is there anything else I can help you with?",
                [
                    {"id": "restart_yes", "title": "Yes"},
                    {"id": "restart_no", "title": "No"}
                ],
                user_data['sender'],
                phone_id
            )
            update_user_state(user_data['sender'], {'step': 'restart_confirmation'})
            return {'step': 'restart_confirmation'}

        # Positive confirmation -> go to welcome flow
        if text in ["yes", "y", "restart_yes", "ok", "sure", "yeah", "yep"]:
            return handle_welcome("", user_data, phone_id)

        # Negative confirmation -> send goodbye and move to a neutral state
        if text in ["no", "n", "restart_no", "nope", "nah"]:
            send_message("Have a good day!", user_data['sender'], phone_id)
            update_user_state(user_data['sender'], {'step': 'goodbye'})
            return {'step': 'goodbye'}

        # Any other input -> re-send buttons
        send_button_message(
            "Is there anything else I can help you with?",
            [
                {"id": "restart_yes", "title": "Yes"},
                {"id": "restart_no", "title": "No"}
            ],
            user_data['sender'],
            phone_id
        )
        return {'step': 'restart_confirmation'}

    except Exception as e:
        logging.error(f"Error in handle_restart_confirmation: {e}")
        send_message("An error occurred. Returning to main menu.", user_data['sender'], phone_id)
        return {'step': 'welcome'}

def handle_fresh_cream_menu(prompt, user_data, phone_id):
    try:
        selected_option = None
        for option in FreshCreamOptions:
            if prompt.lower() in option.value.lower():
                selected_option = option
                break
                
        if not selected_option:
            send_message("Invalid selection. Please choose an option from the list.", user_data['sender'], phone_id)
            return {'step': 'fresh_cream_menu'}
            
        if selected_option == FreshCreamOptions.BACK:
            return handle_main_menu(MainMenuOptions.CAKES.value, user_data, phone_id)
            
        # For tier cakes, show tier options
        if selected_option in [FreshCreamOptions.SMALL, FreshCreamOptions.LARGE, 
                              FreshCreamOptions.LARGE_10, FreshCreamOptions.XL, 
                              FreshCreamOptions.EXTRA_TALL]:
            tier_msg = "Would you like to see tier cake options for this size?"
            send_button_message(
                tier_msg,
                [
                    {"id": "tier_yes", "title": "Yes, show tier options"},
                    {"id": "tier_no", "title": "No, continue with single tier"}
                ],
                user_data['sender'],
                phone_id
            )
            update_user_state(user_data['sender'], {
                'step': 'tier_decision',
                'selected_option': selected_option.value
            })
            return {'step': 'tier_decision'}
            
        # For other options, just show the selection
        send_message(
            f"You selected: {selected_option.value}\n\n"
            "Would you like to place an order for this item?",
            user_data['sender'],
            phone_id
        )
        update_user_state(user_data['sender'], {
            'step': 'order_decision',
            'selected_option': selected_option.value
        })
        return {'step': 'order_decision'}
            
    except Exception as e:
        logging.error(f"Error in handle_fresh_cream_menu: {e}")
        send_message("An error occurred. Please try again.", user_data['sender'], phone_id)
        return {'step': 'cake_types_menu'}

def handle_tier_decision(prompt, user_data, phone_id):
    try:
        if "yes" in prompt.lower() or "tier_yes" in prompt:
            tier_msg = "Please select tier cake options:"
            tier_options = [option.value for option in TierCakesOptions]
            send_list_message(
                tier_msg,
                tier_options,
                user_data['sender'],
                phone_id
            )
            update_user_state(user_data['sender'], {'step': 'tier_cakes_menu'})
            return {'step': 'tier_cakes_menu'}
        else:
            send_message(
                f"You selected: {user_data.get('selected_option', 'this item')}\n\n"
                "Would you like to place an order?",
                user_data['sender'],
                phone_id
            )
            update_user_state(user_data['sender'], {
                'step': 'order_decision',
                'selected_option': user_data.get('selected_option')
            })
            return {'step': 'order_decision'}
            
    except Exception as e:
        logging.error(f"Error in handle_tier_decision: {e}")
        send_message("An error occurred. Please try again.", user_data['sender'], phone_id)
        return {'step': 'fresh_cream_menu'}

def handle_tier_cakes_menu(prompt, user_data, phone_id):
    try:
        selected_option = None
        for option in TierCakesOptions:
            if prompt.lower() in option.value.lower():
                selected_option = option
                break
                
        if not selected_option:
            send_message("Invalid selection. Please choose an option from the list.", user_data['sender'], phone_id)
            return {'step': 'tier_cakes_menu'}
            
        if selected_option == TierCakesOptions.BACK:
            return handle_fresh_cream_menu("", user_data, phone_id)
            
        if selected_option == TierCakesOptions.TWO_TIER:
            two_tier_msg = "Please select a 2-tier cake option:"
            two_tier_options = [option.value for option in TwoTierOptions]
            send_list_message(
                two_tier_msg,
                two_tier_options,
                user_data['sender'],
                phone_id
            )
            update_user_state(user_data['sender'], {'step': 'two_tier_menu'})
            return {'step': 'two_tier_menu'}
            
        elif selected_option == TierCakesOptions.THREE_TIER:
            three_tier_msg = "Please select a 3-tier cake option:"
            three_tier_options = [option.value for option in ThreeTierOptions]
            send_list_message(
                three_tier_msg,
                three_tier_options,
                user_data['sender'],
                phone_id
            )
            update_user_state(user_data['sender'], {'step': 'three_tier_menu'})
            return {'step': 'three_tier_menu'}
            
    except Exception as e:
        logging.error(f"Error in handle_tier_cakes_menu: {e}")
        send_message("An error occurred. Please try again.", user_data['sender'], phone_id)
        return {'step': 'tier_cakes_menu'}

def handle_two_tier_menu(prompt, user_data, phone_id):
    try:
        selected_option = None
        for option in TwoTierOptions:
            if prompt.lower() in option.value.lower():
                selected_option = option
                break
                
        if not selected_option:
            send_message("Invalid selection. Please choose an option from the list.", user_data['sender'], phone_id)
            return {'step': 'two_tier_menu'}
            
        if selected_option == TwoTierOptions.BACK:
            return handle_tier_cakes_menu("", user_data, phone_id)
            
        send_message(
            f"You selected: {selected_option.value}\n\n"
            "Would you like to place an order for this item?",
            user_data['sender'],
            phone_id
        )
        update_user_state(user_data['sender'], {
            'step': 'order_decision',
            'selected_option': selected_option.value
        })
        return {'step': 'order_decision'}
            
    except Exception as e:
        logging.error(f"Error in handle_two_tier_menu: {e}")
        send_message("An error occurred. Please try again.", user_data['sender'], phone_id)
        return {'step': 'two_tier_menu'}

def handle_three_tier_menu(prompt, user_data, phone_id):
    try:
        selected_option = None
        for option in ThreeTierOptions:
            if prompt.lower() in option.value.lower():
                selected_option = option
                break
                
        if not selected_option:
            send_message("Invalid selection. Please choose an option from the list.", user_data['sender'], phone_id)
            return {'step': 'three_tier_menu'}
            
        if selected_option == ThreeTierOptions.BACK:
            return handle_tier_cakes_menu("", user_data, phone_id)
            
        send_message(
            f"You selected: {selected_option.value}\n\n"
            "Would you like to place an order for this item?",
            user_data['sender'],
            phone_id
        )
        update_user_state(user_data['sender'], {
            'step': 'order_decision',
            'selected_option': selected_option.value
        })
        return {'step': 'order_decision'}
            
    except Exception as e:
        logging.error(f"Error in handle_three_tier_menu: {e}")
        send_message("An error occurred. Please try again.", user_data['sender'], phone_id)
        return {'step': 'three_tier_menu'}

def handle_fruit_cake_menu(prompt, user_data, phone_id):
    try:
        selected_option = None
        for option in FruitCakeOptions:
            if prompt.lower() in option.value.lower():
                selected_option = option
                break
                
        if not selected_option:
            send_message("Invalid selection. Please choose an option from the list.", user_data['sender'], phone_id)
            return {'step': 'fruit_cake_menu'}
            
        if selected_option == FruitCakeOptions.BACK:
            return handle_main_menu(MainMenuOptions.CAKES.value, user_data, phone_id)
            
        send_message(
            f"You selected: {selected_option.value}\n\n"
            "Would you like to place an order for this item?",
            user_data['sender'],
            phone_id
        )
        update_user_state(user_data['sender'], {
            'step': 'order_decision',
            'selected_option': selected_option.value
        })
        return {'step': 'order_decision'}
            
    except Exception as e:
        logging.error(f"Error in handle_fruit_cake_menu: {e}")
        send_message("An error occurred. Please try again.", user_data['sender'], phone_id)
        return {'step': 'fruit_cake_menu'}

def handle_plastic_icing_menu(prompt, user_data, phone_id):
    try:
        selected_option = None
        for option in PlasticIcingOptions:
            if prompt.lower() in option.value.lower():
                selected_option = option
                break
                
        if not selected_option:
            send_message("Invalid selection. Please choose an option from the list.", user_data['sender'], phone_id)
            return {'step': 'plastic_icing_menu'}
            
        if selected_option == PlasticIcingOptions.BACK:
            return handle_main_menu(MainMenuOptions.CAKES.value, user_data, phone_id)
            
        send_message(
            f"You selected: {selected_option.value}\n\n"
            "Would you like to place an order for this item?",
            user_data['sender'],
            phone_id
        )
        update_user_state(user_data['sender'], {
            'step': 'order_decision',
            'selected_option': selected_option.value
        })
        return {'step': 'order_decision'}
            
    except Exception as e:
        logging.error(f"Error in handle_plastic_icing_menu: {e}")
        send_message("An error occurred. Please try again.", user_data['sender'], phone_id)
        return {'step': 'plastic_icing_menu'}

def handle_order_decision(prompt, user_data, phone_id):
    try:
        if "yes" in prompt.lower() or "order" in prompt.lower():
            send_message(
                "Great! Let's start your order. Please provide your full name:",
                user_data['sender'],
                phone_id
            )
            user = User(name="", phone=user_data['sender'])
            update_user_state(user_data['sender'], {
                'step': 'get_order_info',
                'user': user.to_dict(),
                'field': 'name',
                'selected_item': user_data.get('selected_option')
            })
            return {
                'step': 'get_order_info',
                'user': user.to_dict(),
                'field': 'name'
            }
        else:
            send_message(
                "No problem! Is there anything else I can help you with?",
                user_data['sender'],
                phone_id
            )
            return handle_welcome("", user_data, phone_id)
            
    except Exception as e:
        logging.error(f"Error in handle_order_decision: {e}")
        send_message("An error occurred. Please try again.", user_data['sender'], phone_id)
        return {'step': 'main_menu'}

def handle_get_order_info(prompt, user_data, phone_id):
    try:
        user = User.from_dict(user_data['user'])
        current_field = user_data.get('field')
        
        if current_field == 'name':
            user.name = prompt
            update_user_state(user_data['sender'], {
                'step': 'get_order_info',
                'user': user.to_dict(),
                'field': 'contact',
                'selected_item': user_data.get('selected_item')
            })
            send_message("Thank you. Please provide your email or WhatsApp number:", user_data['sender'], phone_id)
            return {
                'step': 'get_order_info',
                'user': user.to_dict(),
                'field': 'contact'
            }
            
        elif current_field == 'contact':
            # Check if it's an email or phone number
            if "@" in prompt:
                user.email = prompt
            else:
                user.phone = prompt  # In case they provide a different number
                
            update_user_state(user_data['sender'], {
                'step': 'get_order_info',
                'user': user.to_dict(),
                'field': 'flavor',
                'selected_item': user_data.get('selected_item')
            })
            send_message("Please choose one flavor: chocolate, vanilla, orange, strawberry, or lemon.\n\nN.B Choosing 2 flavors attracts an extra charge of $5", user_data['sender'], phone_id)
            return {
                'step': 'get_order_info',
                'user': user.to_dict(),
                'field': 'flavor'
            }
            
        elif current_field == 'flavor':
            user.flavor = prompt
            update_user_state(user_data['sender'], {
                'step': 'get_order_info',
                'user': user.to_dict(),
                'field': 'filling',
                'selected_item': user_data.get('selected_item')
            })
            send_message("The filling available is fresh cream, confirm by sending fresh cream.", user_data['sender'], phone_id)
            return {
                'step': 'get_order_info',
                'user': user.to_dict(),
                'field': 'filling'
            }
            
        elif current_field == 'filling':
            user.filling = prompt
            update_user_state(user_data['sender'], {
                'step': 'get_order_info',
                'user': user.to_dict(),
                'field': 'icing',
                'selected_item': user_data.get('selected_item')
            })
            send_message("The icing available is fresh cream, confirm by sending fresh cream.", user_data['sender'], phone_id)
            return {
                'step': 'get_order_info',
                'user': user.to_dict(),
                'field': 'icing'
            }
            
        elif current_field == 'icing':
            user.icing = prompt
            update_user_state(user_data['sender'], {
                'step': 'get_order_info',
                'user': user.to_dict(),
                'field': 'shape',
                'selected_item': user_data.get('selected_item')
            })
            send_message("The shape available is round, confirm by sending round.", user_data['sender'], phone_id)
            return {
                'step': 'get_order_info',
                'user': user.to_dict(),
                'field': 'shape'
            }
            
        elif current_field == 'shape':
            user.shape = prompt
            update_user_state(user_data['sender'], {
                'step': 'get_order_info',
                'user': user.to_dict(),
                'field': 'theme',
                'selected_item': user_data.get('selected_item')
            })
            send_message("What theme would you like? (e.g., birthday, wedding, anniversary):", user_data['sender'], phone_id)
            return {
                'step': 'get_order_info',
                'user': user.to_dict(),
                'field': 'theme'
            }
            
        elif current_field == 'theme':
            user.theme = prompt
            update_user_state(user_data['sender'], {
                'step': 'get_order_info',
                'user': user.to_dict(),
                'field': 'due_date',
                'selected_item': user_data.get('selected_item')
            })
            send_message("When do you need the cake? (Please provide date in DD/MM/YYYY format):", user_data['sender'], phone_id)
            return {
                'step': 'get_order_info',
                'user': user.to_dict(),
                'field': 'due_date'
            }
            
        elif current_field == 'due_date':
            user.due_date = prompt
            update_user_state(user_data['sender'], {
                'step': 'get_order_info',
                'user': user.to_dict(),
                'field': 'due_time',
                'selected_item': user_data.get('selected_item')
            })
            send_message("What time do you need the cake? (e.g., 2:00 PM):", user_data['sender'], phone_id)
            return {
                'step': 'get_order_info',
                'user': user.to_dict(),
                'field': 'due_time'
            }
            
        elif current_field == 'due_time':
            user.due_time = prompt
            update_user_state(user_data['sender'], {
                'step': 'get_order_info',
                'user': user.to_dict(),
                'field': 'colors',
                'selected_item': user_data.get('selected_item')
            })
            send_message("What colors would you like on the cake? (e.g., blue and white)\n\nN.B Colors like black and gold attractan extra charge of $5", user_data['sender'], phone_id)
            return {
                'step': 'get_order_info',
                'user': user.to_dict(),
                'field': 'colors'
            }
            
        elif current_field == 'colors':
            user.colors = prompt
            update_user_state(user_data['sender'], {
                'step': 'get_order_info',
                'user': user.to_dict(),
                'field': 'message',
                'selected_item': user_data.get('selected_item')
            })
            send_message("What message would you like on the cake? (e.g., Happy Birthday!):", user_data['sender'], phone_id)
            return {
                'step': 'get_order_info',
                'user': user.to_dict(),
                'field': 'message'
            }
            
        elif current_field == 'message':
            user.message = prompt
            update_user_state(user_data['sender'], {
                'step': 'get_order_info',
                'user': user.to_dict(),
                'field': 'referral',
                'selected_item': user_data.get('selected_item')
            })
            send_message("How did you hear about us? (e.g., Facebook, Friend, Google):", user_data['sender'], phone_id)
            return {
                'step': 'get_order_info',
                'user': user.to_dict(),
                'field': 'referral'
            }
            
        elif current_field == 'referral':
            user.referral_source = prompt
            update_user_state(user_data['sender'], {
                'step': 'get_order_info',
                'user': user.to_dict(),
                'field': 'special_requests',
                'selected_item': user_data.get('selected_item')
            })
            send_message("Any special requests or dietary requirements?", user_data['sender'], phone_id)
            return {
                'step': 'get_order_info',
                'user': user.to_dict(),
                'field': 'special_requests'
            }
            
        elif current_field == 'special_requests':
            user.special_requests = prompt
            # Ask for payment method next
            payment_options = [option.value for option in PaymentOptions]
            send_list_message(
                "Please choose a payment method:",
                payment_options,
                user_data['sender'],
                phone_id
            )
            update_user_state(user_data['sender'], {
                'step': 'choose_payment',
                'user': user.to_dict(),
                'selected_item': user_data.get('selected_item')
            })
            return {
                'step': 'choose_payment',
                'user': user.to_dict()
            }
            
    except Exception as e:
        logging.error(f"Error in handle_get_order_info: {e}")
        send_message("An error occurred. Please try again.", user_data['sender'], phone_id)
        return {'step': 'main_menu'}

def handle_confirm_order(prompt, user_data, phone_id):
    try:
        if "yes" in prompt.lower() or "confirm_yes" in prompt:
            user = User.from_dict(user_data['user'])
            
            # Generate order number
            order_number = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
            
            # Save order to Redis
            order_data = {
                'order_number': order_number,
                'user': user.to_dict(),
                'selected_item': user_data.get('selected_item'),
                'timestamp': datetime.now().isoformat(),
                'status': 'pending'
            }
            
            redis_client.setex(f"order:{order_number}", 604800, json.dumps(order_data))  # 7 days expiration
            
            # Send confirmation to customer
            confirmation_msg = f"""
✅ *ORDER CONFIRMED* ✅

*Order Number:* {order_number}
*Item:* {user_data.get('selected_item', 'Custom Cake')}

Thank you for your order, {user.name}! Your order has been received and is being processed.

We'll contact you at {user.email or user.phone} if we need any additional information.

*Note:* Dark colors (red, pink, black) may have a bitter/metallic aftertaste.

Please visit www.cakefairy1.com for terms and conditions.
            """
            
            send_message(confirmation_msg, user_data['sender'], phone_id)
            
            # Notify agent/owner
            if owner_phone:
                agent_notification = f"""
📋 *NEW CAKE ORDER* 📋

*Order Number:* {order_number}
*Customer:* {user.name}
*Phone:* {user.phone}
*Email:* {user.email}
*Item:* {user_data.get('selected_item', 'Custom Cake')}
*Theme:* {user.theme}
*Flavor:* {user.flavor}
*Filling:* {user.filling}
*Icing:* {user.icing}
*Shape:* {user.shape}
*Due Date:* {user.due_date}
*Due Time:* {user.due_time}
*Colors:* {user.colors}
*Message:* {user.message}
*Referral Source:* {user.referral_source}
*Special Requests:* {user.special_requests}
*Payment:* {user.payment_method}

                """
                send_message(agent_notification, owner_phone, phone_id)
            
            # Ask if they need anything else (Yes/No)
            return handle_restart_confirmation("", user_data, phone_id)
            
        else:
            # Restart order process
            send_message("Let's start over with your order. Please provide your full name:", user_data['sender'], phone_id)
            user = User(name="", phone=user_data['sender'])
            update_user_state(user_data['sender'], {
                'step': 'get_order_info',
                'user': user.to_dict(),
                'field': 'name',
                'selected_item': user_data.get('selected_item')
            })
            return {
                'step': 'get_order_info',
                'user': user.to_dict(),
                'field': 'name'
            }
            
    except Exception as e:
        logging.error(f"Error in handle_confirm_order: {e}")
        send_message("An error occurred. Please try again.", user_data['sender'], phone_id)
        return {'step': 'main_menu'}

def handle_cupcake_inquiry(prompt, user_data, phone_id):
    try:
        # Save cupcake inquiry
        inquiry_data = {
            'details': prompt,
            'timestamp': datetime.now().isoformat(),
            'phone': user_data['sender']
        }
        
        inquiry_id = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
        redis_client.setex(f"cupcake_inquiry:{inquiry_id}", 604800, json.dumps(inquiry_data))
        
        # Send confirmation
        send_message(
            "Thank you for your cupcake inquiry! We've received your details and will contact you shortly with a quote.",
            user_data['sender'],
            phone_id
        )
        
        # Notify agent/owner
        if owner_phone:
            agent_msg = f"""
🧁 *NEW CUPCAKE INQUIRY* 🧁

*Inquiry ID:* {inquiry_id}
*Customer:* {user_data['sender']}
*Details:* {prompt[:200]}{'...' if len(prompt) > 200 else ''}

Please contact the customer for more details.
            """
            send_message(agent_msg, owner_phone, phone_id)
        
        # Ask if they need anything else (Yes/No)
        return handle_restart_confirmation("", user_data, phone_id)
            
    except Exception as e:
        logging.error(f"Error in handle_cupcake_inquiry: {e}")
        send_message("An error occurred. Please try again.", user_data['sender'], phone_id)
        return {'step': 'main_menu'}

def handle_pricing_menu(prompt, user_data, phone_id):
    try:
        selected_option = None
        for option in CakeTypeOptions:
            if prompt.lower() in option.value.lower() and option != CakeTypeOptions.BACK:
                selected_option = option
                break
                
        if not selected_option:
            send_message("Invalid selection. Please choose an option from the list.", user_data['sender'], phone_id)
            return {'step': 'pricing_menu'}
            
        if selected_option == CakeTypeOptions.FRESH_CREAM:
            pricing_msg = """
💰 *Fresh Cream Cakes Pricing* 💰

• Cake Fairy Cake - $20
• Double Delite - $25
• Triple Delite - $30
• Small - $30
• Large - $40
• Large - $60
• Extra Large - $80
• Extra Tall Cake - $65

*2-Tier Cakes:*
• 4 inch + 6 inch - $60
• 5 inch + 7 inch - $80
• 6 inch + 8 inch - $110
• 7 inch + 9 inch - $140
• 8 inch + 10 inch - $170

*3-Tier Cakes:*
• 4 inch + 6 inch + 8 inch - $140
• 5 inch + 7 inch + 9 inch - $170
• 6 inch + 8 inch + 10 inch - $210
            """
            
        elif selected_option == CakeTypeOptions.FRUIT:
            pricing_msg = """
💰 *Fruit Cakes Pricing* 💰

• 6 inch - $40
• 8 inch - $70
            """
            
        elif selected_option == CakeTypeOptions.PLASTIC_ICING:
            pricing_msg = """
💰 *Plastic Icing Cakes Pricing* 💰

• Small - $40
• Medium - $50
• Large - $70
• Extra Large - $100
            """
            
        send_message(pricing_msg, user_data['sender'], phone_id)
        
        # Ask if they want to order
        send_button_message(
            "Would you like to place an order?",
            [
                {"id": "order_yes", "title": "Yes, place order"},
                {"id": "order_no", "title": "No, back to menu"}
            ],
            user_data['sender'],
            phone_id
        )
        
        update_user_state(user_data['sender'], {
            'step': 'pricing_order_decision',
            'cake_type': selected_option.value
        })
        return {'step': 'pricing_order_decision'}
            
    except Exception as e:
        logging.error(f"Error in handle_pricing_menu: {e}")
        send_message("An error occurred. Please try again.", user_data['sender'], phone_id)
        return {'step': 'main_menu'}

def handle_pricing_order_decision(prompt, user_data, phone_id):
    try:
        if "yes" in prompt.lower() or "order_yes" in prompt:
            # Redirect to cake type menu based on selection
            cake_type = user_data.get('cake_type')
            if cake_type == CakeTypeOptions.FRESH_CREAM.value:
                return handle_cake_types_menu(CakeTypeOptions.FRESH_CREAM.value, user_data, phone_id)
            elif cake_type == CakeTypeOptions.FRUIT.value:
                return handle_cake_types_menu(CakeTypeOptions.FRUIT.value, user_data, phone_id)
            elif cake_type == CakeTypeOptions.PLASTIC_ICING.value:
                return handle_cake_types_menu(CakeTypeOptions.PLASTIC_ICING.value, user_data, phone_id)
            else:
                return handle_main_menu(MainMenuOptions.CAKES.value, user_data, phone_id)
        else:
            return handle_main_menu("", user_data, phone_id)
            
    except Exception as e:
        logging.error(f"Error in handle_pricing_order_decision: {e}")
        send_message("An error occurred. Please try again.", user_data['sender'], phone_id)
        return {'step': 'main_menu'}

def handle_contact_menu(prompt, user_data, phone_id):
    try:
        selected_option = None
        for option in ContactOptions:
            if prompt.lower() in option.value.lower():
                selected_option = option
                break
                
        if not selected_option:
            send_message("Invalid selection. Please choose an option from the list.", user_data['sender'], phone_id)
            return {'step': 'contact_menu'}
            
        if selected_option == ContactOptions.CALLBACK:
            send_message(
                "Please provide your name and the best time to call you back:",
                user_data['sender'],
                phone_id
            )
            update_user_state(user_data['sender'], {'step': 'callback_request'})
            return {'step': 'callback_request'}
            
        elif selected_option == ContactOptions.DIRECT:
            contact_info = """
📞 *Contact Information* 📞

You can reach us at:
• Phone: [Your business phone number]
• Email: [Your business email]
• Website: www.cakefairy1.com

Business Hours:
• Monday-Friday: 8:00 AM - 6:00 PM
• Saturday: 9:00 AM - 4:00 PM
• Sunday: Closed

We're located at:
[Your business address]
            """
            send_message(contact_info, user_data['sender'], phone_id)
            return handle_restart_confirmation("", user_data, phone_id)
            
        elif selected_option == ContactOptions.BACK:
            return handle_welcome("", user_data, phone_id)
            
    except Exception as e:
        logging.error(f"Error in handle_contact_menu: {e}")
        send_message("An error occurred. Please try again.", user_data['sender'], phone_id)
        return {'step': 'main_menu'}

def handle_callback_request(prompt, user_data, phone_id):
    try:
        # Save callback request
        callback_data = {
            'request': prompt,
            'timestamp': datetime.now().isoformat(),
            'phone': user_data['sender']
        }
        
        callback_id = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
        redis_client.setex(f"callback:{callback_id}", 604800, json.dumps(callback_data))
        
        # Send confirmation
        send_message(
            "Thank you for your callback request! We've received your information and will contact you shortly.",
            user_data['sender'],
            phone_id
        )
        
        # Notify agent/owner
        if owner_phone:
            agent_msg = f"""
📞 *NEW CALLBACK REQUEST* 📞

*Request ID:* {callback_id}
*Customer:* {user_data['sender']}
*Details:* {prompt[:200]}{'...' if len(prompt) > 200 else ''}

Please contact the customer as soon as possible.
            """
            send_message(agent_msg, owner_phone, phone_id)
        
        # Ask if they need anything else (Yes/No)
        return handle_restart_confirmation("", user_data, phone_id)
            
    except Exception as e:
        logging.error(f"Error in handle_callback_request: {e}")
        send_message("An error occurred. Please try again.", user_data['sender'], phone_id)
        return {'step': 'main_menu'}

def handle_order_menu(prompt, user_data, phone_id):
    try:
        selected_option = None
        for option in OrderOptions:
            if prompt.lower() in option.value.lower():
                selected_option = option
                break
                
        if not selected_option:
            send_message("Invalid selection. Please choose an option from the list.", user_data['sender'], phone_id)
            return {'step': 'order_menu'}
            
        if selected_option == OrderOptions.NEW_ORDER:
            return handle_main_menu(MainMenuOptions.CAKES.value, user_data, phone_id)
            
        elif selected_option == OrderOptions.EXISTING_ORDER:
            send_message(
                "Please provide your order number or phone number associated with your order:",
                user_data['sender'],
                phone_id
            )
            update_user_state(user_data['sender'], {'step': 'check_existing_order'})
            return {'step': 'check_existing_order'}
            
        elif selected_option == OrderOptions.BACK:
            return handle_restart_confirmation("", user_data, phone_id)
            
    except Exception as e:
        logging.error(f"Error in handle_order_menu: {e}")
        send_message("An error occurred. Please try again.", user_data['sender'], phone_id)
        return {'step': 'main_menu'}

def handle_check_existing_order(prompt, user_data, phone_id):
    try:
        # Search for order by order number or phone number
        order_key = None
        
        # Check if it's an order number (alphanumeric, typically 6-8 characters)
        if len(prompt) >= 6 and len(prompt) <= 8 and prompt.isalnum():
            order_data = redis_client.get(f"order:{prompt.upper()}")
            if order_data:
                order_key = f"order:{prompt.upper()}"
        
        # If not found by order number, search by phone number
        if not order_key:
            # Normalize phone number for search
            search_phone = normalize_phone_number(prompt)
            if not search_phone:
                search_phone = user_data['sender']  # Use current phone if search fails
            
            # This is a simplified approach - in production you'd want a better index
            # For now, we'll check a few common formats
            phone_variations = [
                search_phone,
                search_phone.replace('+', ''),
                '0' + search_phone[4:] if search_phone.startswith('+263') else None,
                search_phone[3:] if search_phone.startswith('263') else None
            ]
            
            for phone_var in phone_variations:
                if not phone_var:
                    continue
                    
                # Scan for orders with this phone (this is simplified)
                # In production, you'd want a proper index
                cursor = 0
                found = False
                while True:
                    cursor, keys = redis_client.scan(cursor, match="order:*", count=100)
                    for key in keys:
                        order_data = redis_client.get(key)
                        if order_data:
                            order_json = json.loads(order_data)
                            user_info = order_json.get('user', {})
                            order_phone = user_info.get('phone', '')
                            
                            # Check if phone matches any variation
                            if order_phone and any(
                                phone_var in norm_phone 
                                for norm_phone in [
                                    order_phone,
                                    normalize_phone_number(order_phone),
                                    order_phone.replace('+', ''),
                                    '0' + order_phone[4:] if order_phone.startswith('+263') else None,
                                    order_phone[3:] if order_phone.startswith('263') else None
                                ]
                                if norm_phone
                            ):
                                order_key = key
                                found = True
                                break
                    
                    if found or cursor == 0:
                        break
        
        if order_key:
            order_data = redis_client.get(order_key)
            order_json = json.loads(order_data)
            
            order_info = f"""
📋 *ORDER STATUS* 📋

*Order Number:* {order_json.get('order_number', 'N/A')}
*Status:* {order_json.get('status', 'pending').upper()}
*Item:* {order_json.get('selected_item', 'Custom Cake')}
*Customer:* {order_json.get('user', {}).get('name', 'N/A')}
*Due Date:* {order_json.get('user', {}).get('due_date', 'N/A')}

For more details or to make changes, please contact us directly.
            """
            
            send_message(order_info, user_data['sender'], phone_id)
        else:
            send_message(
                "Sorry, we couldn't find an order matching that information. "
                "Please check your order number or phone number and try again, "
                "or contact us directly for assistance.",
                user_data['sender'],
                phone_id
            )
        
        # Ask if they need anything else (Yes/No)
        return handle_restart_confirmation("", user_data, phone_id)
            
    except Exception as e:
        logging.error(f"Error in handle_check_existing_order: {e}")
        send_message("An error occurred. Please try again.", user_data['sender'], phone_id)
        return {'step': 'main_menu'}

def human_agent(prompt, user_data, phone_id):
    try:
        send_message(
            "You've requested to speak with a human agent. "
            "One of our team members will contact you shortly. "
            "Please provide a brief description of what you need help with:",
            user_data['sender'],
            phone_id
        )
        
        # Save agent request
        agent_request = {
            'timestamp': datetime.now().isoformat(),
            'phone': user_data['sender'],
            'initial_message': prompt
        }
        
        request_id = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
        redis_client.setex(f"agent_request:{request_id}", 3600, json.dumps(agent_request))  # 1 hour expiration
        
        # Notify agent/owner
        if owner_phone:
            agent_msg = f"""
👨‍💼 *HUMAN AGENT REQUEST* 👩‍💼

*Request ID:* {request_id}
*Customer:* {user_data['sender']}
*Initial Message:* {prompt[:200]}{'...' if len(prompt) > 200 else ''}

Please contact the customer as soon as possible.
            """
            send_message(agent_msg, owner_phone, phone_id)
        
        update_user_state(user_data['sender'], {'step': 'waiting_for_agent'})
        return {'step': 'waiting_for_agent'}
            
    except Exception as e:
        logging.error(f"Error in human_agent: {e}")
        send_message("An error occurred. Please try again.", user_data['sender'], phone_id)
        return {'step': 'main_menu'}
        

def handle_waiting_for_agent(prompt, user_data, phone_id):
    try:
        # Customer waiting for agent
        if owner_phone:
            send_message(f"📩 *Message from customer {user_data['sender']}:*\n\n{prompt}", owner_phone, phone_id)
            # Start agent session
            start_agent_session(user_data['sender'], owner_phone)
        return {'step': 'agent_chat'}
    except Exception as e:
        logging.error(f"Error in handle_waiting_for_agent: {e}")
        send_message("An error occurred. Please try again.", user_data['sender'], phone_id)
        return {'step': 'main_menu'}



def start_agent_session(customer, agent):
    update_user_state(customer, {"step": "agent_chat", "agent": agent})
    update_user_state(agent, {"step": "agent_chat", "customer": customer})
    send_message("✅ You are now connected to a human agent.", customer, phone_id)
    send_message(f"✅ You are now connected with customer {customer}. Send 'exit' to end the chat.", agent, phone_id)

def end_agent_session(customer, agent):
    update_user_state(customer, {"step": "main_menu"})
    update_user_state(agent, {"step": "main_menu"})
    send_message("👋 The agent has left the chat. You're now back with the bot.", customer, phone_id)
    send_message(f"👋 Chat with {customer} ended. Handover back to bot.", agent, phone_id)


# Main message handler
def handle_message(prompt, user_data, phone_id):
    sender = user_data["sender"]

    # ===== AGENT HANDLING =====
    if sender in AGENT_NUMBERS:
        if user_data.get("step") == "agent_chat" and "customer" in user_data:
            customer = user_data["customer"]
            if prompt.lower().strip() == "exit":
                end_agent_session(customer, sender)
                return {"step": "main_menu"}
            else:
                # Forward agent message to customer
                send_message(f"👨‍💼 Agent: {prompt}", customer, phone_id)
                return user_data
        else:
            send_message("⚠️ No active customer session. Please wait for a request.", sender, phone_id)
            return user_data

    # ===== CUSTOMER HANDLING =====
    if user_data.get("step") == "agent_chat" and "agent" in user_data:
        agent = user_data["agent"]
        # Forward customer message to agent
        send_message(f"🧑 Customer {sender}: {prompt}", agent, phone_id)
        return user_data
        

    try:
        print(f"Handling message: '{prompt}' for user: {user_data}")
        
        # Handle empty or very short messages
        if not prompt or len(prompt.strip()) < 1:
            send_message("Please type a message or select an option from the menu.", user_data['sender'], phone_id)
            return user_data
        
        # Convert prompt to lowercase for easier matching
        prompt_lower = prompt.lower()
        # Log inbound text
        try:
            log_conversation(user_data['sender'], 'in', 'text', {'text': prompt})
        except Exception:
            pass
        
        # Check for explicit restart commands (exact match only to avoid accidental triggers)
        if prompt_lower.strip() in {"restart", "start over", "main menu", "menu", "hie", "hey", "hi"}:
            return handle_welcome("", user_data, phone_id)
            
        # Check for agent request at any point
        if any(word in prompt_lower for word in ["agent", "human", "representative", "speak to someone"]):
            return human_agent(prompt, user_data, phone_id)
        
        # Route based on current step
        current_step = user_data.get('step', 'welcome')
        
        if current_step == 'welcome':
            return handle_welcome(prompt, user_data, phone_id)
        
        elif current_step == 'goodbye':
            # Stay idle after saying goodbye; only react to explicit restart/menu/agent keywords
            if any(word in prompt_lower for word in ["restart", "start over", "main menu", "menu", "hi", "hey", "hie"]):
                return handle_welcome("", user_data, phone_id)
            if any(word in prompt_lower for word in ["agent", "human", "representative", "speak to someone"]):
                return human_agent(prompt, user_data, phone_id)
            send_message("If you need anything else later, just say 'menu' to start again.", user_data['sender'], phone_id)
            return {'step': 'goodbye'}

        elif current_step == 'restart_confirmation':
            return handle_restart_confirmation(prompt, user_data, phone_id)
            
        elif current_step == 'main_menu':
            return handle_main_menu(prompt, user_data, phone_id)
            
        elif current_step == 'cake_types_menu':
            return handle_cake_types_menu(prompt, user_data, phone_id)
            
        elif current_step == 'fresh_cream_menu':
            return handle_fresh_cream_menu(prompt, user_data, phone_id)
            
        elif current_step == 'tier_decision':
            return handle_tier_decision(prompt, user_data, phone_id)
            
        elif current_step == 'tier_cakes_menu':
            return handle_tier_cakes_menu(prompt, user_data, phone_id)
            
        elif current_step == 'two_tier_menu':
            return handle_two_tier_menu(prompt, user_data, phone_id)
            
        elif current_step == 'three_tier_menu':
            return handle_three_tier_menu(prompt, user_data, phone_id)
            
        elif current_step == 'fruit_cake_menu':
            return handle_fruit_cake_menu(prompt, user_data, phone_id)
            
        elif current_step == 'plastic_icing_menu':
            return handle_plastic_icing_menu(prompt, user_data, phone_id)
            
        elif current_step == 'order_decision':
            return handle_order_decision(prompt, user_data, phone_id)
            
        elif current_step == 'get_order_info':
            return handle_get_order_info(prompt, user_data, phone_id)

        elif current_step == 'choose_payment':
            # Parse payment option
            selected_option = None
            for option in PaymentOptions:
                if prompt_lower in option.value.lower():
                    selected_option = option
                    break
            user = User.from_dict(user_data['user'])
            if selected_option:
                user.payment_method = selected_option.value
            else:
                user.payment_method = prompt

            # Show final summary including payment
            order_summary = f"""
🎂 *ORDER SUMMARY* 🎂

*Selected Item:* {user_data.get('selected_item', 'Custom Cake')}
*Name:* {user.name}
*Contact:* {user.email or user.phone}
*Flavor:* {user.flavor}
*Filling:* {user.filling}
*Icing:* {user.icing}
*Shape:* {user.shape}
*Theme:* {user.theme}
*Due Date:* {user.due_date}
*Due Time:* {user.due_time}
*Colors:* {user.colors}
*Message:* {user.message}
*Referral Source:* {user.referral_source}
*Special Requests:* {user.special_requests}
*Payment:* {user.payment_method}

*Note:* Dark colors (red, pink, black) may have a bitter/metallic aftertaste.

Please confirm if this order is correct.
            """

            send_button_message(
                order_summary,
                [
                    {"id": "confirm_yes", "title": "✅ Yes, confirm order"},
                    {"id": "confirm_no", "title": "❌ No, edit order"}
                ],
                user_data['sender'],
                phone_id
            )
            update_user_state(user_data['sender'], {
                'step': 'confirm_order',
                'user': user.to_dict(),
                'selected_item': user_data.get('selected_item')
            })
            return {
                'step': 'confirm_order',
                'user': user.to_dict()
            }
            
        elif current_step == 'confirm_order':
            return handle_confirm_order(prompt, user_data, phone_id)
            
        elif current_step == 'cupcake_inquiry':
            return handle_cupcake_inquiry(prompt, user_data, phone_id)
            
        elif current_step == 'pricing_menu':
            return handle_pricing_menu(prompt, user_data, phone_id)
            
        elif current_step == 'pricing_order_decision':
            return handle_pricing_order_decision(prompt, user_data, phone_id)
            
        elif current_step == 'contact_menu':
            return handle_contact_menu(prompt, user_data, phone_id)
            
        elif current_step == 'callback_request':
            return handle_callback_request(prompt, user_data, phone_id)
            
        elif current_step == 'order_menu':
            return handle_order_menu(prompt, user_data, phone_id)
            
        elif current_step == 'check_existing_order':
            return handle_check_existing_order(prompt, user_data, phone_id)
            
        elif current_step == 'waiting_for_agent':
            return handle_waiting_for_agent(prompt, user_data, phone_id)
            
        else:
            # Default fallback
            send_message("I'm not sure how to help with that. Let me show you our main menu.", user_data['sender'], phone_id)
            return handle_welcome("", user_data, phone_id)
            
    except Exception as e:
        logging.error(f"Error in handle_message: {e}")
        logging.error(traceback.format_exc())
        send_message("An error occurred. Please try again.", user_data['sender'], phone_id)
        return {'step': 'welcome'}

@app.route('/webhook', methods=['GET', 'POST'])
def webhook():
    if request.method == 'GET':
        # Verify webhook
        mode = request.args.get('hub.mode')
        token = request.args.get('hub.verify_token')
        challenge = request.args.get('hub.challenge')
        
        if mode == "subscribe" and token == "BOT":
            return challenge, 200
               
        else:
            return 'Forbidden', 403
        
    
    elif request.method == 'POST':
        try:
            data = request.get_json()
            print(f"Incoming webhook data: {data}")
            
            if data.get('object') == 'whatsapp_business_account':
                for entry in data.get('entry', []):
                    for change in entry.get('changes', []):
                        if change.get('field') == 'messages':
                            value = change.get('value')
                            if value:
                                message = value.get('messages', [{}])[0]
                                sender = message.get('from')
                                sender = normalize_phone_number(sender)
                                incoming_text = None
                                # Interactive replies
                                if message.get('type') == 'interactive':
                                    interactive = message.get('interactive', {})
                                    if interactive.get('type') == 'list_reply':
                                        selected = interactive.get('list_reply', {})
                                        incoming_text = selected.get('title') or selected.get('id')
                                    elif interactive.get('type') == 'button_reply':
                                        selected = interactive.get('button_reply', {})
                                        incoming_text = selected.get('id') or selected.get('title')
                                    else:
                                        incoming_text = ''
                                elif message.get('type') == 'text':
                                    incoming_text = message.get('text', {}).get('body', '')
                                else:
                                    incoming_text = ''

                                # Log raw inbound
                                try:
                                    log_conversation(sender, 'in', message.get('type', 'unknown'), message)
                                except Exception:
                                    pass

                                if incoming_text is not None:
                                    print(f"Processing message from {sender}: {incoming_text}")
                                    user_data_obj = get_user_state(sender)
                                    print(f"User state: {user_data_obj}")
                                    new_state = handle_message(incoming_text, user_data_obj, phone_id)
                                    print(f"New state: {new_state}")
                                    if new_state != user_data_obj:
                                        update_user_state(sender, new_state)
            
            return jsonify({'status': 'success'}), 200
            
        except Exception as e:
            print(f"Error processing webhook: {e}")
            print(traceback.format_exc())
            return jsonify({'status': 'error', 'message': str(e)}), 500
    
    return jsonify({'status': 'bad_request'}), 400

@app.route('/')
def home():
    return render_template('connected.html')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
