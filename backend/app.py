from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS  
import wikipedia
import pyjokes
import requests
import datetime
import random
import os
import re
from urllib.parse import quote

app = Flask(__name__)
CORS(app)  

# ─── API KEYS ─────────────────────────────────────────────────────────────────
NEWS_API_KEY    = "pub_e3df609c881044969cdcd075982d2ecc"
WEATHER_API_KEY = "1fafffd81374024b137ade9da419b569"

# ─── In-memory storage ────────────────────────────────────────────────────────
notes = []
reminders = []
todos = []
conversation_history = []

# ─── Motivational quotes ──────────────────────────────────────────────────────
MOTIVATIONAL_QUOTES = [
    "Believe you can and you're halfway there. - Theodore Roosevelt",
    "The only way to do great work is to love what you do. - Steve Jobs",
    "Success is not final, failure is not fatal. - Winston Churchill",
    "Don't watch the clock; do what it does. Keep going. - Sam Levenson",
    "The future belongs to those who believe in their dreams. - Eleanor Roosevelt",
    "You are never too old to set another goal. - C.S. Lewis",
    "Everything you've ever wanted is on the other side of fear. - George Addair",
    "Believe in yourself. You are braver than you think. - Christopher Robin",
    "Dream big and dare to fail. - Norman Vaughan",
    "Act as if what you do makes a difference. It does. - William James"
]

# ─── Fun facts ────────────────────────────────────────────────────────────────
FUN_FACTS = [
    "Honey never spoils. Archaeologists have found 3000-year-old honey in Egyptian tombs that's still edible!",
    "Octopuses have three hearts and blue blood!",
    "A day on Venus is longer than a year on Venus!",
    "Bananas are berries, but strawberries aren't!",
    "The shortest war in history lasted only 38 minutes!",
    "Your brain uses 20% of your body's energy!",
    "There are more stars in the universe than grains of sand on Earth!",
    "A group of flamingos is called a 'flamboyance'!",
    "The Eiffel Tower can grow up to 6 inches in summer due to thermal expansion!",
    "Sharks have been around longer than trees!"
]

# ─── Riddles ──────────────────────────────────────────────────────────────────
RIDDLES = [
    {"question": "What has keys but no locks, space but no room?", "answer": "keyboard"},
    {"question": "What comes once in a minute, twice in a moment, but never in a thousand years?", "answer": "letter m"},
    {"question": "What has hands but cannot clap?", "answer": "clock"},
    {"question": "What gets wet while drying?", "answer": "towel"},
    {"question": "What can travel around the world while staying in a corner?", "answer": "stamp"},
    {"question": "I'm light as a feather, yet the strongest person can't hold me for long. What am I?", "answer": "breath"},
    {"question": "What has a head and tail but no body?", "answer": "coin"},
    {"question": "The more you take, the more you leave behind. What am I?", "answer": "footsteps"}
]

current_riddle = None

# ─── Unit conversions ─────────────────────────────────────────────────────────
def convert_temperature(value, from_unit, to_unit):
    """Convert between Celsius, Fahrenheit, and Kelvin"""
    if from_unit == 'fahrenheit' or from_unit == 'f':
        celsius = (value - 32) * 5/9
    elif from_unit == 'kelvin' or from_unit == 'k':
        celsius = value - 273.15
    else:
        celsius = value
    
    if to_unit == 'fahrenheit' or to_unit == 'f':
        return (celsius * 9/5) + 32
    elif to_unit == 'kelvin' or to_unit == 'k':
        return celsius + 273.15
    else:
        return celsius

def convert_distance(value, from_unit, to_unit):
    """Convert between various distance units"""
    to_meters = {
        'km': 1000, 'kilometer': 1000, 'kilometers': 1000,
        'm': 1, 'meter': 1, 'meters': 1,
        'cm': 0.01, 'centimeter': 0.01, 'centimeters': 0.01,
        'mm': 0.001, 'millimeter': 0.001, 'millimeters': 0.001,
        'mile': 1609.34, 'miles': 1609.34,
        'yard': 0.9144, 'yards': 0.9144,
        'foot': 0.3048, 'feet': 0.3048, 'ft': 0.3048,
        'inch': 0.0254, 'inches': 0.0254
    }
    
    meters = value * to_meters.get(from_unit.lower(), 1)
    result = meters / to_meters.get(to_unit.lower(), 1)
    return result

def convert_weight(value, from_unit, to_unit):
    """Convert between various weight units"""
    to_kg = {
        'kg': 1, 'kilogram': 1, 'kilograms': 1,
        'g': 0.001, 'gram': 0.001, 'grams': 0.001,
        'mg': 0.000001, 'milligram': 0.000001, 'milligrams': 0.000001,
        'lb': 0.453592, 'pound': 0.453592, 'pounds': 0.453592,
        'oz': 0.0283495, 'ounce': 0.0283495, 'ounces': 0.0283495,
        'ton': 1000, 'tons': 1000, 'tonne': 1000, 'tonnes': 1000
    }
    
    kg = value * to_kg.get(from_unit.lower(), 1)
    result = kg / to_kg.get(to_unit.lower(), 1)
    return result

# ─── Math calculations ────────────────────────────────────────────────────────
def calculate(expression):
    """Safely evaluate mathematical expressions"""
    try:
        expr = expression.lower().replace(' ', '')
        expr = expr.replace('x', '*').replace('×', '*').replace('÷', '/')
        expr = expr.replace('plus', '+').replace('minus', '-')
        expr = expr.replace('times', '*').replace('dividedby', '/')
        
        if not re.match(r'^[\d+\-*/().\s]+$', expr):
            return None
        
        result = eval(expr)
        return result
    except:
        return None

# ─── Serve the frontend ──────────────────────────────────────────────────────
@app.route("/")
def health():
    return jsonify({
        "status": "healthy",
        "service": "WALL-E Backend API",
        "endpoints": ["/api/chat", "/api/save_note", "/api/rps"]
    })

# ─── Main chat endpoint ──────────────────────────────────────────────────────
@app.route("/api/chat", methods=["POST"])
def chat():
    global current_riddle
    
    data  = request.get_json()
    query = data.get("message", "").strip()
    query_lower = query.lower()

    if not query or query_lower == "none":
        return jsonify({"reply": "I didn't catch that. Can you say it again?"})

    conversation_history.append({"user": query, "time": datetime.datetime.now()})

    # ── Greetings ─────────────────────────────────────────────────────────────
    if any(w in query_lower for w in ["hello", "hi", "hey", "namaste", "good morning", "good evening"]):
        hour = datetime.datetime.now().hour
        if hour < 12:
            greeting = "Good Morning"
        elif hour < 18:
            greeting = "Good Afternoon"
        else:
            greeting = "Good Evening"
        return jsonify({"reply": f"{greeting}! I am WALL-E. How can I help you?"})

    if "how are you" in query_lower:
        responses = [
            "I am fine, thank you! How are you doing?",
            "I'm doing great! Ready to help you with anything!",
            "I'm excellent! How about you?",
            "I'm functioning at optimal capacity! How can I help?"
        ]
        return jsonify({"reply": random.choice(responses)})

    if query_lower in ["fine", "good", "i am fine", "i am good", "great", "awesome"]:
        responses = [
            "That's great to hear! How can I help you today?",
            "Wonderful! What would you like me to do?",
            "Excellent! I'm here if you need anything!",
            "That's fantastic! What can I do for you?"
        ]
        return jsonify({"reply": random.choice(responses)})

    # ── Identity ──────────────────────────────────────────────────────────────
    if "who are you" in query_lower or "what are you" in query_lower:
        return jsonify({"reply": "I am WALL-E, your virtual AI assistant created by Koushik! I can help you with information, calculations, entertainment, and much more!"})

    if "who made you" in query_lower or "who created you" in query_lower:
        return jsonify({"reply": "I was created by Koushik! He built me as part of his project."})

    if "your name" in query_lower:
        return jsonify({"reply": "My name is WALL-E! It stands for Waste Allocation Load Lifter - Earth-class, but I prefer to help with information rather than waste! 😊"})

    # ── Capabilities ──────────────────────────────────────────────────────────
    if "what can you do" in query_lower or "help me" in query_lower or "help" == query_lower:
        reply = (
            "🤖 Here's what I can do:\n\n"
            "📚 INFORMATION:\n"
            "• Wikipedia — 'wikipedia [topic]'\n"
            "• News — 'news' or 'latest news'\n"
            "• Weather — 'weather in [city]'\n"
            "• Fun facts — 'tell me a fact'\n"
            "• What/Who is — 'what is [topic]'\n\n"
            "🧮 CALCULATIONS:\n"
            "• Math — 'calculate 25 * 48'\n"
            "• Temperature — 'convert 32 F to C'\n"
            "• Distance — 'convert 5 miles to km'\n"
            "• Weight — 'convert 10 pounds to kg'\n\n"
            "🎮 ENTERTAINMENT:\n"
            "• Jokes — 'tell me a joke'\n"
            "• Riddles — 'tell me a riddle'\n"
            "• Games — 'rock paper scissors'\n"
            "• Music — 'play [song name]'\n"
            "• Motivate me — 'motivate me'\n\n"
            "📝 PRODUCTIVITY:\n"
            "• Notes — 'write a note'\n"
            "• Show notes — 'show my notes'\n"
            "• Reminders — 'remind me to [task]'\n"
            "• To-do list — 'add todo [task]'\n"
            "• Show todos — 'show my todos'\n\n"
            "🌐 UTILITIES:\n"
            "• Search — 'search [topic]'\n"
            "• Location — 'where is [place]'\n"
            "• Time — 'what time is it'\n"
            "• Date — 'what's the date'\n"
            "• Translation — 'translate [text] to hindi'\n"
            "• Flip coin — 'flip a coin'\n"
            "• Roll dice — 'roll a dice'\n\n"
            "Say any of these to get started! 🚀"
            "And to Close Say Exit"
        )
        return jsonify({"reply": reply})

    # ── Wikipedia ─────────────────────────────────────────────────────────────
    if "wikipedia" in query_lower:
        topic = query_lower.replace("wikipedia", "").strip()
        if not topic:
            return jsonify({"reply": "Sure! What topic do you want me to search on Wikipedia?"})
        try:
            result = wikipedia.summary(topic, sentences=3)
            return jsonify({"reply": f"📖 Wikipedia says:\n\n{result}"})
        except wikipedia.exceptions.DisambiguationError as e:
            options = e.options[:5]
            return jsonify({"reply": f"That topic is ambiguous. Did you mean:\n\n" + "\n".join(f"• {o}" for o in options)})
        except wikipedia.exceptions.PageNotFoundError:
            return jsonify({"reply": "Sorry, I couldn't find that topic on Wikipedia. Try different keywords."})
        except Exception as e:
            return jsonify({"reply": f"Something went wrong: {str(e)}"})

    # ── News ──────────────────────────────────────────────────────────────────
    if "news" in query_lower or "headlines" in query_lower:
        try:
            url = f"https://newsdata.io/api/1/news?apikey={NEWS_API_KEY}&country=in&language=en"
            resp = requests.get(url, timeout=5)
            print(f"Status Code: {resp.status_code}")
            print(f"Response: {resp.text[:500]}")
            data = resp.json()
            
            if data.get("status") != "success":
                error_msg = data.get('message', 'Unknown error')
                return jsonify({"reply": f"News API error: {error_msg}"})
            
            articles = data.get("results", [])
            print(f"Number of articles: {len(articles)}")

            if not articles:
                return jsonify({"reply": "No news articles found right now. Try again later!"})
            
            headlines = []
            for i, art in enumerate(articles[:5], 1):
                title = art.get('title', 'No title')
                source = art.get('source_id', 'Unknown')
                headlines.append(f"{i}. {title}\n   📰 {source}")

            return jsonify({"reply": "📰 Top News Headlines:\n\n" + "\n".join(headlines)})
        
        except Exception as e:
            return jsonify({"reply": f"Error fetching news: {str(e)}"})

    # ── Weather ───────────────────────────────────────────────────────────────
    if "weather" in query_lower or "temperature" in query_lower:
        city = query_lower.replace("weather", "").replace("temperature", "").replace("in", "").replace("of", "").strip()
        if not city:
            return jsonify({"reply": "Which city's weather do you want? Say 'weather in [city name]'."})
        try:
            url  = f"https://api.openweathermap.org/data/2.5/weather?q={city}&appid={WEATHER_API_KEY}&units=metric"
            resp = requests.get(url, timeout=5)
            data = resp.json()
            if resp.status_code != 200:
                return jsonify({"reply": f"Couldn't find weather for '{city}'. Check the spelling!"})
            desc = data["weather"][0]["description"].capitalize()
            temp = data["main"]["temp"]
            feels_like = data["main"]["feels_like"]
            hum  = data["main"]["humidity"]
            wind = data["wind"]["speed"]
            return jsonify({"reply": f"🌤️ Weather in {city.title()}:\n\n• Condition: {desc}\n• Temperature: {temp}°C (feels like {feels_like}°C)\n• Humidity: {hum}%\n• Wind Speed: {wind} m/s"})
        except Exception as e:
            return jsonify({"reply": f"Error getting weather: {str(e)}"})

    # ── Jokes ─────────────────────────────────────────────────────────────────
    if "joke" in query_lower:
        return jsonify({"reply": f"😂 {pyjokes.get_joke()}"})

    # ── Fun Facts ─────────────────────────────────────────────────────────────
    if "fact" in query_lower or "tell me something interesting" in query_lower:
        return jsonify({"reply": f"🧠 Fun Fact:\n\n{random.choice(FUN_FACTS)}"})

    # ── Riddles ───────────────────────────────────────────────────────────────
    if "riddle" in query_lower and current_riddle is None:
        current_riddle = random.choice(RIDDLES)
        return jsonify({"reply": f"🤔 Riddle Time!\n\n{current_riddle['question']}\n\nThink you know the answer? Say it!"})
    
    if current_riddle and query_lower.replace(" ", "") in current_riddle["answer"].replace(" ", ""):
        reply = f"🎉 Correct! The answer is '{current_riddle['answer']}'! Well done!"
        current_riddle = None
        return jsonify({"reply": reply})
    elif current_riddle and len(query_lower) < 30:
        return jsonify({"reply": f"❌ Not quite! Try again, or say 'give up' for the answer.\n\nRiddle: {current_riddle['question']}"})

    if "give up" in query_lower and current_riddle:
        answer = current_riddle["answer"]
        current_riddle = None
        return jsonify({"reply": f"The answer was: '{answer}'. Want another riddle? Say 'tell me a riddle'!"})

    # ── Motivational Quotes ───────────────────────────────────────────────────
    if "motivate" in query_lower or "motivation" in query_lower or "inspire" in query_lower:
        return jsonify({"reply": f"💪 {random.choice(MOTIVATIONAL_QUOTES)}"})

    # ── Calculations ──────────────────────────────────────────────────────────
    if any(word in query_lower for word in ["calculate", "compute", "what is", "solve"]):
        expr = re.search(r'calculate|compute|what is|solve', query_lower)
        if expr:
            expression = query[expr.end():].strip()
            result = calculate(expression)
            if result is not None:
                return jsonify({"reply": f"🧮 {expression} = {result}"})

    if re.match(r'^[\d+\-*/().×÷\s]+$', query):
        result = calculate(query)
        if result is not None:
            return jsonify({"reply": f"🧮 {query} = {result}"})

    # ── Unit Conversions ──────────────────────────────────────────────────────
    if "convert" in query_lower:
        temp_match = re.search(r'(\d+\.?\d*)\s*(celsius|fahrenheit|kelvin|c|f|k)\s*to\s*(celsius|fahrenheit|kelvin|c|f|k)', query_lower)
        if temp_match:
            value = float(temp_match.group(1))
            from_unit = temp_match.group(2)
            to_unit = temp_match.group(3)
            result = convert_temperature(value, from_unit, to_unit)
            return jsonify({"reply": f"🌡️ {value}°{from_unit[0].upper()} = {result:.2f}°{to_unit[0].upper()}"})
        
        dist_match = re.search(r'(\d+\.?\d*)\s*(km|kilometer|kilometers|m|meter|meters|cm|mile|miles|foot|feet|ft|inch|inches|yard|yards)\s*to\s*(km|kilometer|kilometers|m|meter|meters|cm|mile|miles|foot|feet|ft|inch|inches|yard|yards)', query_lower)
        if dist_match:
            value = float(dist_match.group(1))
            from_unit = dist_match.group(2)
            to_unit = dist_match.group(3)
            result = convert_distance(value, from_unit, to_unit)
            return jsonify({"reply": f"📏 {value} {from_unit} = {result:.2f} {to_unit}"})
        
        weight_match = re.search(r'(\d+\.?\d*)\s*(kg|kilogram|kilograms|g|gram|grams|lb|pound|pounds|oz|ounce|ounces|ton|tons)\s*to\s*(kg|kilogram|kilograms|g|gram|grams|lb|pound|pounds|oz|ounce|ounces|ton|tons)', query_lower)
        if weight_match:
            value = float(weight_match.group(1))
            from_unit = weight_match.group(2)
            to_unit = weight_match.group(3)
            result = convert_weight(value, from_unit, to_unit)
            return jsonify({"reply": f"⚖️ {value} {from_unit} = {result:.2f} {to_unit}"})
        
        return jsonify({"reply": "I can convert temperatures (e.g., '32 F to C'), distances (e.g., '5 miles to km'), and weights (e.g., '10 pounds to kg')!"})

    # ── Time ──────────────────────────────────────────────────────────────────
    if "time" in query_lower and ("what" in query_lower or "current" in query_lower):
        t = datetime.datetime.now().strftime("%I:%M %p")
        return jsonify({"reply": f"⏰ The current time is {t}."})

    # ── Date ──────────────────────────────────────────────────────────────────
    if "date" in query_lower and ("what" in query_lower or "today" in query_lower or "current" in query_lower):
        d = datetime.datetime.now().strftime("%A, %B %d, %Y")
        return jsonify({"reply": f"📅 Today is {d}."})

    # ── Day ───────────────────────────────────────────────────────────────────
    if "what day" in query_lower or "which day" in query_lower:
        day = datetime.datetime.now().strftime("%A")
        return jsonify({"reply": f"📅 Today is {day}!"})

    # ── Play on YouTube ───────────────────────────────────────────────────────
    if "play" in query_lower:
        song = query_lower.replace("play", "").strip()
        if not song:
            return jsonify({"reply": "What song do you want to play? Say 'play [song name]'."})
        youtube_url = f"https://www.youtube.com/results?search_query={song.replace(' ', '+')}"
        return jsonify({"reply": f"🎵 Playing '{song}' on YouTube!", "open_url": youtube_url})

    # ── Search Google ─────────────────────────────────────────────────────────
    if "search" in query_lower or "google" in query_lower:
        term = query_lower.replace("search", "").replace("google", "").replace("for", "").strip()
        if not term:
            return jsonify({"reply": "What do you want me to search? Say 'search [topic]'."})
        search_url = f"https://www.google.com/search?q={term.replace(' ', '+')}"
        return jsonify({"reply": f"🔍 Searching for '{term}' on Google!", "open_url": search_url})

    # ── Locate on Google Maps ─────────────────────────────────────────────────
    if "where is" in query_lower or "location of" in query_lower or "locate" in query_lower:
        place = query_lower.replace("where is", "").replace("location of", "").replace("locate", "").strip()
        if not place:
            return jsonify({"reply": "Where do you want me to locate? Say 'where is [place]'."})
        maps_url = f"https://www.google.com/maps/place/{place.replace(' ', '+')}"
        return jsonify({"reply": f"📍 Locating '{place}' on Google Maps!", "open_url": maps_url})

    # ── Translation ───────────────────────────────────────────────────────────
    if "translate" in query_lower:
        match = re.search(r'translate\s+(.+?)\s+to\s+(\w+)', query_lower)
        if match:
            text = match.group(1)
            lang = match.group(2)
            translate_url = f"https://translate.google.com/?sl=auto&tl={lang}&text={quote(text)}"
            return jsonify({"reply": f"🌐 Translating '{text}' to {lang.title()}!", "open_url": translate_url})
        return jsonify({"reply": "Say 'translate [text] to [language]' (e.g., 'translate hello to hindi')"})

    # ── Flip Coin ─────────────────────────────────────────────────────────────
    if "flip" in query_lower and "coin" in query_lower:
        result = random.choice(["Heads", "Tails"])
        return jsonify({"reply": f"🪙 I flipped a coin and got: {result}!"})

    # ── Roll Dice ─────────────────────────────────────────────────────────────
    if "roll" in query_lower and ("dice" in query_lower or "die" in query_lower):
        result = random.randint(1, 6)
        return jsonify({"reply": f"🎲 You rolled a {result}!"})

    # ── Random Number ─────────────────────────────────────────────────────────
    if "random number" in query_lower:
        match = re.search(r'(\d+)\s*(?:to|and)\s*(\d+)', query_lower)
        if match:
            min_num = int(match.group(1))
            max_num = int(match.group(2))
            result = random.randint(min_num, max_num)
            return jsonify({"reply": f"🔢 Random number between {min_num} and {max_num}: {result}"})
        result = random.randint(1, 100)
        return jsonify({"reply": f"🔢 Random number (1-100): {result}"})

    # ── Write a Note ──────────────────────────────────────────────────────────
    if "write a note" in query_lower or "write note" in query_lower or "take a note" in query_lower:
        return jsonify({"reply": "📝 Sure! What do you want me to write down?", "action": "waiting_note"})

    # ── Show Notes ────────────────────────────────────────────────────────────
    if "show note" in query_lower or "my notes" in query_lower or "read note" in query_lower:
        if not notes:
            return jsonify({"reply": "📝 You have no notes saved yet. Say 'write a note' to add one!"})
        note_list = "\n".join(f"{i}. [{n['time']}] {n['text']}" for i, n in enumerate(notes, 1))
        return jsonify({"reply": f"📝 Your Notes:\n\n{note_list}"})

    # ── Delete Notes ──────────────────────────────────────────────────────────
    if "delete" in query_lower and "note" in query_lower:
        if "all" in query_lower:
            notes.clear()
            return jsonify({"reply": "📝 All notes deleted!"})
        return jsonify({"reply": "📝 Say 'delete all notes' to clear all notes."})

    # ── Reminders ─────────────────────────────────────────────────────────────
    if "remind me" in query_lower:
        task = query_lower.replace("remind me to", "").replace("remind me", "").strip()
        if not task:
            return jsonify({"reply": "What should I remind you about? Say 'remind me to [task]'."})
        reminders.append({
            "task": task,
            "time": datetime.datetime.now().strftime("%d/%m %I:%M %p")
        })
        return jsonify({"reply": f"⏰ Reminder set: '{task}'"})

    # ── Show Reminders ────────────────────────────────────────────────────────
    if "show reminder" in query_lower or "my reminders" in query_lower:
        if not reminders:
            return jsonify({"reply": "⏰ You have no reminders. Say 'remind me to [task]'!"})
        reminder_list = "\n".join(f"{i}. [{r['time']}] {r['task']}" for i, r in enumerate(reminders, 1))
        return jsonify({"reply": f"⏰ Your Reminders:\n\n{reminder_list}"})

    # ── To-Do List ────────────────────────────────────────────────────────────
    if ("add todo" in query_lower or "add task" in query_lower or "create todo" in query_lower):
        task = query_lower.replace("add todo", "").replace("add task", "").replace("create todo", "").strip()
        if not task:
            return jsonify({"reply": "What task should I add? Say 'add todo [task]'."})
        todos.append({
            "task": task,
            "done": False,
            "time": datetime.datetime.now().strftime("%d/%m %I:%M %p")
        })
        return jsonify({"reply": f"✅ Task added: '{task}'"})

    # ── Show To-Dos ───────────────────────────────────────────────────────────
    if "show todo" in query_lower or "my todos" in query_lower or "my tasks" in query_lower:
        if not todos:
            return jsonify({"reply": "✅ You have no tasks. Say 'add todo [task]' to create one!"})
        todo_list = []
        for i, t in enumerate(todos, 1):
            status = "✓" if t["done"] else "○"
            todo_list.append(f"{status} {i}. {t['task']}")
        return jsonify({"reply": f"✅ Your To-Do List:\n\n" + "\n".join(todo_list)})

    # ── Complete To-Do ────────────────────────────────────────────────────────
    if "complete" in query_lower and ("todo" in query_lower or "task" in query_lower):
        match = re.search(r'(\d+)', query)
        if match and todos:
            idx = int(match.group(1)) - 1
            if 0 <= idx < len(todos):
                todos[idx]["done"] = True
                return jsonify({"reply": f"✅ Marked as complete: '{todos[idx]['task']}'"})
        return jsonify({"reply": "Say 'complete task [number]' (e.g., 'complete task 1')"})

    # ── Clear To-Dos ──────────────────────────────────────────────────────────
    if "clear" in query_lower and ("todo" in query_lower or "tasks" in query_lower):
        todos.clear()
        return jsonify({"reply": "✅ All tasks cleared!"})

    # ── Rock Paper Scissors ───────────────────────────────────────────────────
    if "rock paper scissor" in query_lower or "rock paper scissors" in query_lower:
        return jsonify({"reply": "🎮 Let's play! Say 'rock', 'paper', or 'scissor'.", "action": "waiting_rps"})

    # ── Love/Compliments ──────────────────────────────────────────────────────
    if "i love you" in query_lower:
        return jsonify({"reply": "Aww, that's sweet! I'm here to help you anytime! 💙"})

    if "you are" in query_lower and any(word in query_lower for word in ["amazing", "awesome", "great", "smart", "intelligent", "best"]):
        return jsonify({"reply": "Thank you so much! You're pretty awesome too! 😊"})

    # ── Thank you ─────────────────────────────────────────────────────────────
    if "thank" in query_lower:
        responses = [
            "You're welcome! Happy to help! 😊",
            "No problem at all!",
            "Anytime! That's what I'm here for!",
            "My pleasure! Let me know if you need anything else!"
        ]
        return jsonify({"reply": random.choice(responses)})

    # ── Age ───────────────────────────────────────────────────────────────────
    if "how old are you" in query_lower or "your age" in query_lower:
        return jsonify({"reply": "I was born when Koushik and the team created me! I'm timeless in the digital world! 🤖"})

    # ── What is / Who is ──────────────────────────────────────────────────────
    if ("what is" in query_lower or "who is" in query_lower or "tell me about" in query_lower):
        topic = query_lower.replace("what is", "").replace("who is", "").replace("tell me about", "").strip()
        if not topic or len(topic) < 3:
            return jsonify({"reply": "What would you like to know about? Be more specific!"})
        try:
            result = wikipedia.summary(topic, sentences=2)
            return jsonify({"reply": f"📚 {result}"})
        
        except wikipedia.exceptions.DisambiguationError as e:
            options = e.options[:5]
            return jsonify({"reply": f"That topic is ambiguous. Did you mean:\n\n" + "\n".join(f"• {o}" for o in options)})
        except wikipedia.exceptions.PageError:
            return jsonify({"reply": f"Sorry, I couldn't find information about '{topic}' on Wikipedia."})
        except Exception as e:
            return jsonify({"reply": f"I couldn't find detailed info about '{topic}'. Try rephrasing or say 'search {topic}'!"})

    # ── System info ───────────────────────────────────────────────────────────
    if "your capabilities" in query_lower or "system info" in query_lower:
        info = (
            "🤖 WALL-E System Information:\n\n"
            "• Knowledge Base: Wikipedia, News APIs\n"
            "• Processing: Natural Language Understanding\n"
            "• Memory: In-session storage for notes & reminders\n"
            "• Skills: Math, Conversions, Weather, Entertainment\n"
            "• Languages: English (primary)\n"
            "• Status: Fully operational! 🚀"
        )
        return jsonify({"reply": info})

    # ── Exit ──────────────────────────────────────────────────────────────────
    if any(word in query_lower for word in ["exit", "bye", "goodbye", "see you", "quit"]):
        goodbyes = [
            "👋 Thanks for talking to me! Goodbye!",
            "👋 See you later! Come back anytime!",
            "👋 Goodbye! Have a wonderful day!",
            "👋 It was great chatting with you! Bye!"
        ]
        return jsonify({"reply": random.choice(goodbyes)})

    # ── Fallback ──────────────────────────────────────────────────────────────
    fallbacks = [
        "Hmm, I don't understand that yet. Try saying 'what can you do' to see what I can help with!",
        "I didn't quite get that. Say 'help' to see all my features!",
        "I'm not sure about that one. Want to see what I can do? Say 'what can you do'!",
        "That's a tricky one! Try asking something else, or say 'help' for ideas!"
    ]
    return jsonify({"reply": random.choice(fallbacks)})


# ─── Save Note endpoint ───────────────────────────────────────────────────────
@app.route("/api/save_note", methods=["POST"])
def save_note():
    data = request.get_json()
    text = data.get("note", "").strip()
    if not text:
        return jsonify({"reply": "You didn't say anything to save. Try again!"})
    notes.append({
        "text": text,
        "time": datetime.datetime.now().strftime("%d/%m %I:%M %p")
    })
    return jsonify({"reply": f"📝 Note saved: '{text}'"})


# ─── Rock Paper Scissors endpoint ─────────────────────────────────────────────
@app.route("/api/rps", methods=["POST"])
def rps():
    data       = request.get_json()
    player     = data.get("choice", "").strip().lower()
    valid      = ["rock", "paper", "scissor", "scissors"]
    if player not in valid:
        return jsonify({"reply": "Invalid choice! Say 'rock', 'paper', or 'scissor'."})
    if player == "scissors":
        player = "scissor"

    computer   = random.choice(["rock", "paper", "scissor"])
    beats      = {"rock": "scissor", "paper": "rock", "scissor": "paper"}

    if player == computer:
        result = "It's a draw! 🤝"
    elif beats[player] == computer:
        result = "You win! 🎉"
    else:
        result = "WALL-E wins! 🤖"

    return jsonify({"reply": f"🎮 You chose: {player.capitalize()}\nWALL-E chose: {computer.capitalize()}\n\n{result}"})


# ─── Run the server ───────────────────────────────────────────────────────────
if __name__ == "__main__":
    app.run(debug=False, host="0.0.0.0", port=5000)