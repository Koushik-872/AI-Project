from flask import Flask, request, jsonify
from flask_cors import CORS  
import wikipedia
import pyjokes
import requests
import datetime
import random
import re
from urllib.parse import quote
from typing import Dict, Callable, Optional, List
from dataclasses import dataclass

app = Flask(__name__)
CORS(app)

# ─── API KEYS ─────────────────────────────────────────────────────────────────
NEWS_API_KEY = "pub_e3df609c881044969cdcd075982d2ecc"
WEATHER_API_KEY = "1fafffd81374024b137ade9da419b569"
WOLFRAM_API_KEY = "7UAY2Y95E5"

# ─── In-memory storage ────────────────────────────────────────────────────────
notes = []
reminders = []
todos = []
conversation_history = []
current_riddle = None

# ─── Constants ────────────────────────────────────────────────────────────────
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


# ─── Response Data Class ──────────────────────────────────────────────────────
@dataclass
class Response:
    """Structured response from command handlers"""
    reply: str
    action: Optional[str] = None
    open_url: Optional[str] = None
    
    def to_dict(self):
        result = {"reply": self.reply}
        if self.action:
            result["action"] = self.action
        if self.open_url:
            result["open_url"] = self.open_url
        return result


# ─── Command Handler Base Class ───────────────────────────────────────────────
class CommandHandler:
    """Base class for all command handlers"""
    
    def __init__(self):
        self.keywords: List[str] = []
        self.priority: int = 5  # Lower number = higher priority (1-10)
        self.enabled: bool = True
    
    def matches(self, query: str) -> bool:
        """Check if this handler should process the query"""
        if not self.enabled:
            return False
        query_lower = query.lower()
        return any(keyword in query_lower for keyword in self.keywords)
    
    def handle(self, query: str, query_lower: str) -> Optional[Response]:
        """Process the query and return a response"""
        raise NotImplementedError
    
    def get_info(self) -> Dict:
        """Return handler information for debugging"""
        return {
            "name": self.__class__.__name__,
            "keywords": self.keywords,
            "priority": self.priority,
            "enabled": self.enabled
        }


# ─── Utility Functions ────────────────────────────────────────────────────────
class Utils:
    """Shared utility functions"""
    
    @staticmethod
    def convert_temperature(value: float, from_unit: str, to_unit: str) -> float:
        """Convert between Celsius, Fahrenheit, and Kelvin"""
        if from_unit in ['fahrenheit', 'f']:
            celsius = (value - 32) * 5/9
        elif from_unit in ['kelvin', 'k']:
            celsius = value - 273.15
        else:
            celsius = value
        
        if to_unit in ['fahrenheit', 'f']:
            return (celsius * 9/5) + 32
        elif to_unit in ['kelvin', 'k']:
            return celsius + 273.15
        else:
            return celsius

    @staticmethod
    def convert_distance(value: float, from_unit: str, to_unit: str) -> float:
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
        return meters / to_meters.get(to_unit.lower(), 1)

    @staticmethod
    def convert_weight(value: float, from_unit: str, to_unit: str) -> float:
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
        return kg / to_kg.get(to_unit.lower(), 1)

    @staticmethod
    def calculate(expression: str) -> Optional[float]:
        """Safely evaluate mathematical expressions"""
        try:
            expr = expression.lower().replace(' ', '')
            expr = expr.replace('x', '*').replace('×', '*').replace('÷', '/')
            expr = expr.replace('plus', '+').replace('minus', '-')
            expr = expr.replace('times', '*').replace('dividedby', '/')
            
            if not re.match(r'^[\d+\-*/().\s]+$', expr):
                return None
            
            return eval(expr)
        except:
            return None


# ─── GREETING HANDLERS ────────────────────────────────────────────────────────

class GreetingHandler(CommandHandler):
    def __init__(self):
        super().__init__()
        self.keywords = ["hello", "hi", "hey", "namaste", "good morning", "good evening"]
        self.priority = 1
    
    def handle(self, query: str, query_lower: str) -> Response:
        hour = datetime.datetime.now().hour
        if hour < 12:
            greeting = "Good Morning"
        elif hour < 18:
            greeting = "Good Afternoon"
        else:
            greeting = "Good Evening"
        return Response(f"{greeting}! I am WALL-E. How can I help you?")


class HowAreYouHandler(CommandHandler):
    def __init__(self):
        super().__init__()
        self.keywords = ["how are you"]
        self.priority = 1
    
    def handle(self, query: str, query_lower: str) -> Response:
        responses = [
            "I am fine, thank you! How are you doing?",
            "I'm doing great! Ready to help you with anything!",
            "I'm excellent! How about you?",
            "I'm functioning at optimal capacity! How can I help?"
        ]
        return Response(random.choice(responses))


class UserWellBeingHandler(CommandHandler):
    def __init__(self):
        super().__init__()
        self.keywords = ["fine", "good", "i am fine", "i am good", "great", "awesome"]
        self.priority = 2
    
    def matches(self, query: str) -> bool:
        return query.lower() in self.keywords
    
    def handle(self, query: str, query_lower: str) -> Response:
        responses = [
            "That's great to hear! How can I help you today?",
            "Wonderful! What would you like me to do?",
            "Excellent! I'm here if you need anything!",
            "That's fantastic! What can I do for you?"
        ]
        return Response(random.choice(responses))


# ─── IDENTITY HANDLERS ────────────────────────────────────────────────────────

class IdentityHandler(CommandHandler):
    def __init__(self):
        super().__init__()
        self.keywords = ["who are you", "what are you"]
        self.priority = 1
    
    def handle(self, query: str, query_lower: str) -> Response:
        return Response("I am WALL-E, your virtual AI assistant created by Koushik! I can help you with information, calculations, entertainment, and much more!")


class CreatorHandler(CommandHandler):
    def __init__(self):
        super().__init__()
        self.keywords = ["who made you", "who created you"]
        self.priority = 1
    
    def handle(self, query: str, query_lower: str) -> Response:
        return Response("I was created by Koushik! He built me as part of his project.")


class NameHandler(CommandHandler):
    def __init__(self):
        super().__init__()
        self.keywords = ["your name"]
        self.priority = 1
    
    def handle(self, query: str, query_lower: str) -> Response:
        return Response("My name is WALL-E! It stands for Waste Allocation Load Lifter - Earth-class, but I prefer to help with information rather than waste! 😊")


class AgeHandler(CommandHandler):
    def __init__(self):
        super().__init__()
        self.keywords = ["how old are you", "your age"]
        self.priority = 2
    
    def handle(self, query: str, query_lower: str) -> Response:
        return Response("I was born when Koushik created me! I'm timeless in the digital world! 🤖")


# ─── HELP HANDLER ─────────────────────────────────────────────────────────────

class HelpHandler(CommandHandler):
    def __init__(self):
        super().__init__()
        self.keywords = ["what can you do", "help me"]
        self.priority = 2
    
    def matches(self, query: str) -> bool:
        query_lower = query.lower()
        return query_lower == "help" or any(keyword in query_lower for keyword in self.keywords)
    
    def handle(self, query: str, query_lower: str) -> Response:
        reply = (
            "🤖 Here's what I can do:\n\n"
            "📚 INFORMATION:\n"
            "• Wikipedia — 'wikipedia [topic]'\n"
            "• News — 'news' or 'latest news'\n"
            "• Weather — 'weather in [city]'\n"
            "• Fun facts — 'tell me a fact'\n"
            "• Ask me — 'what is [topic]' or 'who is [person]'\n\n"
            "🧮 CALCULATIONS & ANALYSIS:\n"
            "• Basic Math — 'calculate 25 * 48'\n"
            "• Advanced Math — 'solve x^2 + 5x + 6 = 0' (via Wolfram)\n"
            "• Data Analysis — 'analyze population growth'\n"
            "• Scientific queries — 'chemical formula for water'\n"
            "• Unit conversions — 'convert 32 F to C'\n\n"
            "🎮 ENTERTAINMENT:\n"
            "• Jokes — 'tell me a joke'\n"
            "• Riddles — 'tell me a riddle'\n"
            "• Games — 'rock paper scissors'\n"
            "• Music — 'play [song name]'\n"
            "• Motivate me — 'motivate me'\n\n"
            "📝 PRODUCTIVITY:\n"
            "• Notes — 'write a note'\n"
            "• Reminders — 'remind me to [task]'\n"
            "• To-do list — 'add todo [task]'\n\n"
            "🌐 UTILITIES:\n"
            "• Search — 'search [topic]'\n"
            "• Location — 'where is [place]'\n"
            "• Time & Date — 'what time is it'\n"
            "• Translation — 'translate [text] to hindi'\n"
            "• Random — 'flip a coin', 'roll a dice'\n\n"
            "Say any of these to get started! 🚀"
        )
        return Response(reply)


class CapabilitiesHandler(CommandHandler):
    def __init__(self):
        super().__init__()
        self.keywords = ["your capabilities", "system info"]
        self.priority = 2
    
    def handle(self, query: str, query_lower: str) -> Response:
        info = (
            "🤖 WALL-E System Information:\n\n"
            "• Knowledge Base: Wikipedia, WolframAlpha, News APIs\n"
            "• Processing: Natural Language Understanding\n"
            "• Memory: In-session storage for notes & reminders\n"
            "• Skills: Math, Conversions, Weather, Entertainment\n"
            "• Advanced: WolframAlpha integration for complex queries\n"
            "• Languages: English (primary)\n"
            "• Status: Fully operational! 🚀"
        )
        return Response(info)


# ─── INFORMATION HANDLERS ─────────────────────────────────────────────────────

class WikipediaHandler(CommandHandler):
    def __init__(self):
        super().__init__()
        self.keywords = ["wikipedia"]
        self.priority = 2
    
    def handle(self, query: str, query_lower: str) -> Response:
        topic = query_lower.replace("wikipedia", "").strip()
        if not topic:
            return Response("Sure! What topic do you want me to search on Wikipedia?")
        
        try:
            result = wikipedia.summary(topic, sentences=3)
            return Response(f"📖 Wikipedia says:\n\n{result}")
        except wikipedia.exceptions.DisambiguationError as e:
            options = e.options[:5]
            return Response("That topic is ambiguous. Did you mean:\n\n" + "\n".join(f"• {o}" for o in options))
        except wikipedia.exceptions.PageError:
            return Response("Sorry, I couldn't find that topic on Wikipedia. Try different keywords.")
        except Exception as e:
            return Response(f"Something went wrong: {str(e)}")


class WhatIsHandler(CommandHandler):
    """Handles 'what is' and 'who is' questions"""
    def __init__(self):
        super().__init__()
        self.keywords = ["what is", "who is", "tell me about"]
        self.priority = 8  # Lower priority so other specific handlers go first
    
    def handle(self, query: str, query_lower: str) -> Response:
        topic = query_lower
        for keyword in ["what is", "who is", "tell me about"]:
            topic = topic.replace(keyword, "")
        topic = topic.strip()
        
        if not topic or len(topic) < 3:
            return Response("What would you like to know about? Be more specific!")
        
        try:
            result = wikipedia.summary(topic, sentences=2)
            return Response(f"📚 {result}")
        except wikipedia.exceptions.DisambiguationError as e:
            options = e.options[:5]
            return Response("That topic is ambiguous. Did you mean:\n\n" + "\n".join(f"• {o}" for o in options))
        except wikipedia.exceptions.PageError:
            return Response(f"Sorry, I couldn't find information about '{topic}' on Wikipedia.")
        except Exception:
            return Response(f"I couldn't find detailed info about '{topic}'. Try rephrasing or say 'search {topic}'!")


class NewsHandler(CommandHandler):
    def __init__(self):
        super().__init__()
        self.keywords = ["news", "headlines"]
        self.priority = 2
    
    def handle(self, query: str, query_lower: str) -> Response:
        try:
            url = f"https://newsdata.io/api/1/news?apikey={NEWS_API_KEY}&country=in&language=en"
            resp = requests.get(url, timeout=5)
            data = resp.json()
            
            if data.get("status") != "success":
                return Response(f"News API error: {data.get('message', 'Unknown error')}")
            
            articles = data.get("results", [])
            if not articles:
                return Response("No news articles found right now. Try again later!")
            
            headlines = []
            for i, art in enumerate(articles[:5], 1):
                title = art.get('title', 'No title')
                source = art.get('source_id', 'Unknown')
                headlines.append(f"{i}. {title}\n   📰 {source}")

            return Response("📰 Top News Headlines:\n\n" + "\n".join(headlines))
        except Exception as e:
            return Response(f"Error fetching news: {str(e)}")


class WeatherHandler(CommandHandler):
    def __init__(self):
        super().__init__()
        self.keywords = ["weather", "temperature"]
        self.priority = 2
    
    def handle(self, query: str, query_lower: str) -> Response:
        city = query_lower.replace("weather", "").replace("temperature", "").replace("in", "").replace("of", "").strip()
        if not city:
            return Response("Which city's weather do you want? Say 'weather in [city name]'.")
        
        try:
            url = f"https://api.openweathermap.org/data/2.5/weather?q={city}&appid={WEATHER_API_KEY}&units=metric"
            resp = requests.get(url, timeout=5)
            data = resp.json()
            
            if resp.status_code != 200:
                return Response(f"Couldn't find weather for '{city}'. Check the spelling!")
            
            desc = data["weather"][0]["description"].capitalize()
            temp = data["main"]["temp"]
            feels_like = data["main"]["feels_like"]
            hum = data["main"]["humidity"]
            wind = data["wind"]["speed"]
            
            return Response(
                f"🌤️ Weather in {city.title()}:\n\n"
                f"• Condition: {desc}\n"
                f"• Temperature: {temp}°C (feels like {feels_like}°C)\n"
                f"• Humidity: {hum}%\n"
                f"• Wind Speed: {wind} m/s"
            )
        except Exception as e:
            return Response(f"Error getting weather: {str(e)}")


# ─── WOLFRAM ALPHA HANDLER ────────────────────────────────────────────────────

class WolframAlphaHandler(CommandHandler):
    """Advanced computation and analysis using WolframAlpha - Direct API approach"""
    def __init__(self):
        super().__init__()
        self.keywords = [
            "solve", "wolfram", "analyze", "compute",
            "derivative", "integral", "equation",
            "chemical formula", "scientific",
            "population of", "distance between",
            "history of", "molecular"
        ]
        self.priority = 3
        self.api_key = WOLFRAM_API_KEY
        
        # Check if API key is valid
        if self.api_key and self.api_key != "YOUR_WOLFRAM_API_KEY_HERE":
            self.enabled = True
            print(f"✅ WolframAlpha: Using direct API approach (App ID: {self.api_key[:10]}...)")
        else:
            self.enabled = False
            print("⚠️ WolframAlpha: Disabled - No valid API key")
    
    def matches(self, query: str) -> bool:
        if not self.enabled:
            return False
        
        query_lower = query.lower()
        
        # Match specific patterns
        advanced_patterns = [
            r'solve .+ equation',
            r'what is .+ \+',
            r'derivative of',
            r'integral of',
            r'chemical formula',
            r'population of',
            r'distance between .+ and',
            r'molecular weight',
            r'square root of \d+',
        ]
        
        for pattern in advanced_patterns:
            if re.search(pattern, query_lower):
                return True
        
        # Match keywords
        return super().matches(query)
    
    def handle(self, query: str, query_lower: str) -> Response:
        if not self.enabled:
            return None
        
        try:
            # Clean up the query
            wolfram_query = query
            for prefix in ["wolfram", "ask wolfram", "compute", "solve"]:
                wolfram_query = wolfram_query.replace(prefix, "").strip()
            
            # Validate query length
            if not wolfram_query or len(wolfram_query) < 1:
                return Response("Please ask me a more specific question!")
            
            # Query WolframAlpha API directly using HTTP
            try:
                url = "https://api.wolframalpha.com/v2/query"
                params = {
                    'input': wolfram_query,
                    'appid': self.api_key,
                    'output': 'json'
                }
                
                print(f"\n{'='*60}")
                print(f"DEBUG: WolframAlpha Query")
                print(f"{'='*60}")
                print(f"Original: {query}")
                print(f"Cleaned: {wolfram_query}")
                print(f"URL: {url}")
                print(f"Params: {params}")
                
                response = requests.get(url, params=params, timeout=10)
                print(f"Response Status: {response.status_code}")
                
                if response.status_code != 200:
                    return Response("🤔 WolframAlpha service error. Try again later!")
                
                data = response.json()
                
                # WolframAlpha wraps response in 'queryresult'
                query_result = data.get('queryresult', data)
                
                print(f"Response Success: {query_result.get('success', False)}")
                print(f"Total Pods: {query_result.get('numpods', 0)}")
                
                # Check if query was successful
                if not query_result.get('success', False):
                    return Response("🤔 WolframAlpha couldn't understand that query. Try rephrasing!")
                
                # Extract results from pods
                pods = query_result.get('pods', [])
                print(f"DEBUG: Found {len(pods)} pods")
                
                if not pods or query_result.get('numpods', 0) == 0:
                    return Response("🤔 WolframAlpha found no results. Try a different question!")
                
                # Look for result-type pods
                results = []
                result_pod_titles = [
                    'Result', 'Solution', 'Output', 'Value', 'Decimal form', 'Answer',
                    'Exact result', 'Decimal approximation', 'Real solutions', 
                    'Integer solutions', 'Solutions'
                ]
                
                # First: Look for standard result pods
                for pod in pods:
                    pod_title = pod.get('title', '')
                    print(f"DEBUG: Pod - {pod_title}")
                    if pod_title in result_pod_titles:
                        subpods = pod.get('subpods', [])
                        for subpod in subpods:
                            plaintext = subpod.get('plaintext', '').strip()
                            if plaintext:
                                results.append(plaintext)
                                print(f"DEBUG: Found result: {plaintext[:60]}")
                
                # Second: If no standard result, get first non-input pod
                if not results:
                    for pod in pods:
                        pod_title = pod.get('title', '')
                        if pod_title not in ['Input', 'Input interpretation']:
                            subpods = pod.get('subpods', [])
                            for subpod in subpods:
                                plaintext = subpod.get('plaintext', '').strip()
                                if plaintext and len(plaintext) < 200:
                                    results.append(plaintext)
                                    print(f"DEBUG: Found fallback result: {plaintext[:60]}")
                                    break
                            if results:
                                break
                
                print(f"\nFinal Results: {results}")
                print(f"{'='*60}\n")
                
                if results:
                    response_text = results[0]
                    return Response(f"🧠 {response_text}")
                else:
                    return Response("🤔 No readable results found. Try rephrasing your question!")
                
            except requests.exceptions.Timeout:
                return Response("🤔 WolframAlpha took too long to respond. Try a simpler query!")
            except requests.exceptions.ConnectionError:
                return Response("🤔 Couldn't connect to WolframAlpha. Check your internet connection!")
            except ValueError as ve:
                print(f"JSON Parse Error: {ve}")
                return Response("🤔 Invalid response from WolframAlpha. Try again!")
            
        except Exception as e:
            import traceback
            error_msg = str(e)[:100]
            print(f"\nWolframAlpha Handler Error: {error_msg}")
            print(f"Traceback: {traceback.format_exc()}")
            return Response(f"🤔 An error occurred. Please try a different question!")


# ─── CALCULATION HANDLERS ─────────────────────────────────────────────────────

class BasicCalculationHandler(CommandHandler):
    def __init__(self):
        super().__init__()
        self.keywords = ["calculate", "compute"]
        self.priority = 4
    
    def matches(self, query: str) -> bool:
        query_lower = query.lower()
        # Check for keywords or pure math expression
        if any(keyword in query_lower for keyword in self.keywords):
            return True
        return bool(re.match(r'^[\d+\-*/().×÷\s]+$', query))
    
    def handle(self, query: str, query_lower: str) -> Response:
        # Extract expression after keyword
        expression = query
        for keyword in ["calculate", "compute", "what is"]:
            if keyword in query_lower:
                idx = query_lower.index(keyword)
                expression = query[idx + len(keyword):].strip()
                break
        
        result = Utils.calculate(expression)
        if result is not None:
            return Response(f"🧮 {expression} = {result}")
        return None


class ConversionHandler(CommandHandler):
    def __init__(self):
        super().__init__()
        self.keywords = ["convert"]
        self.priority = 2
    
    def handle(self, query: str, query_lower: str) -> Response:
        # Temperature conversion
        temp_match = re.search(
            r'(\d+\.?\d*)\s*(celsius|fahrenheit|kelvin|c|f|k)\s*to\s*(celsius|fahrenheit|kelvin|c|f|k)',
            query_lower
        )
        if temp_match:
            value = float(temp_match.group(1))
            from_unit = temp_match.group(2)
            to_unit = temp_match.group(3)
            result = Utils.convert_temperature(value, from_unit, to_unit)
            return Response(f"🌡️ {value}°{from_unit[0].upper()} = {result:.2f}°{to_unit[0].upper()}")
        
        # Distance conversion
        dist_match = re.search(
            r'(\d+\.?\d*)\s*(km|kilometer|m|meter|cm|mile|miles|foot|feet|ft|inch|inches|yard|yards)\s*to\s*(km|kilometer|m|meter|cm|mile|miles|foot|feet|ft|inch|inches|yard|yards)',
            query_lower
        )
        if dist_match:
            value = float(dist_match.group(1))
            from_unit = dist_match.group(2)
            to_unit = dist_match.group(3)
            result = Utils.convert_distance(value, from_unit, to_unit)
            return Response(f"📏 {value} {from_unit} = {result:.2f} {to_unit}")
        
        # Weight conversion
        weight_match = re.search(
            r'(\d+\.?\d*)\s*(kg|kilogram|g|gram|lb|pound|oz|ounce|ton|tons)\s*to\s*(kg|kilogram|g|gram|lb|pound|oz|ounce|ton|tons)',
            query_lower
        )
        if weight_match:
            value = float(weight_match.group(1))
            from_unit = weight_match.group(2)
            to_unit = weight_match.group(3)
            result = Utils.convert_weight(value, from_unit, to_unit)
            return Response(f"⚖️ {value} {from_unit} = {result:.2f} {to_unit}")
        
        return Response("I can convert temperatures (e.g., '32 F to C'), distances (e.g., '5 miles to km'), and weights (e.g., '10 pounds to kg')!")


# ─── ENTERTAINMENT HANDLERS ───────────────────────────────────────────────────

class JokeHandler(CommandHandler):
    def __init__(self):
        super().__init__()
        self.keywords = ["joke"]
        self.priority = 2
    
    def handle(self, query: str, query_lower: str) -> Response:
        return Response(f"😂 {pyjokes.get_joke()}")


class FunFactHandler(CommandHandler):
    def __init__(self):
        super().__init__()
        self.keywords = ["fact", "tell me something interesting"]
        self.priority = 2
    
    def handle(self, query: str, query_lower: str) -> Response:
        return Response(f"🧠 Fun Fact:\n\n{random.choice(FUN_FACTS)}")


class RiddleHandler(CommandHandler):
    def __init__(self):
        super().__init__()
        self.keywords = ["riddle"]
        self.priority = 2
    
    def handle(self, query: str, query_lower: str) -> Response:
        global current_riddle
        
        if "riddle" in query_lower and current_riddle is None:
            current_riddle = random.choice(RIDDLES)
            return Response(f"🤔 Riddle Time!\n\n{current_riddle['question']}\n\nThink you know the answer? Say it!")
        
        return None


class RiddleAnswerHandler(CommandHandler):
    def __init__(self):
        super().__init__()
        self.keywords = ["give up"]
        self.priority = 1
    
    def matches(self, query: str) -> bool:
        global current_riddle
        return current_riddle is not None
    
    def handle(self, query: str, query_lower: str) -> Response:
        global current_riddle
        
        if "give up" in query_lower:
            answer = current_riddle["answer"]
            current_riddle = None
            return Response(f"The answer was: '{answer}'. Want another riddle? Say 'tell me a riddle'!")
        
        # Check if answer is correct
        if query_lower.replace(" ", "") in current_riddle["answer"].replace(" ", ""):
            reply = f"🎉 Correct! The answer is '{current_riddle['answer']}'! Well done!"
            current_riddle = None
            return Response(reply)
        elif len(query_lower) < 30:
            return Response(f"❌ Not quite! Try again, or say 'give up' for the answer.\n\nRiddle: {current_riddle['question']}")
        
        return None


class MotivationHandler(CommandHandler):
    def __init__(self):
        super().__init__()
        self.keywords = ["motivate", "motivation", "inspire"]
        self.priority = 2
    
    def handle(self, query: str, query_lower: str) -> Response:
        return Response(f"💪 {random.choice(MOTIVATIONAL_QUOTES)}")


class RockPaperScissorsHandler(CommandHandler):
    def __init__(self):
        super().__init__()
        self.keywords = ["rock paper scissor"]
        self.priority = 2
    
    def handle(self, query: str, query_lower: str) -> Response:
        return Response("🎮 Let's play! Say 'rock', 'paper', or 'scissor'.", action="waiting_rps")


# ─── PRODUCTIVITY HANDLERS ────────────────────────────────────────────────────

class WriteNoteHandler(CommandHandler):
    def __init__(self):
        super().__init__()
        self.keywords = ["write a note", "write note", "take a note"]
        self.priority = 2
    
    def handle(self, query: str, query_lower: str) -> Response:
        return Response("📝 Sure! What do you want me to write down?", action="waiting_note")


class ShowNotesHandler(CommandHandler):
    def __init__(self):
        super().__init__()
        self.keywords = ["show note", "my notes", "read note"]
        self.priority = 2
    
    def handle(self, query: str, query_lower: str) -> Response:
        if not notes:
            return Response("📝 You have no notes saved yet. Say 'write a note' to add one!")
        
        note_list = "\n".join(f"{i}. [{n['time']}] {n['text']}" for i, n in enumerate(notes, 1))
        return Response(f"📝 Your Notes:\n\n{note_list}")


class DeleteNotesHandler(CommandHandler):
    def __init__(self):
        super().__init__()
        self.keywords = ["delete note"]
        self.priority = 2
    
    def handle(self, query: str, query_lower: str) -> Response:
        if "all" in query_lower:
            notes.clear()
            return Response("📝 All notes deleted!")
        return Response("📝 Say 'delete all notes' to clear all notes.")


class SetReminderHandler(CommandHandler):
    def __init__(self):
        super().__init__()
        self.keywords = ["remind me"]
        self.priority = 2
    
    def handle(self, query: str, query_lower: str) -> Response:
        task = query_lower.replace("remind me to", "").replace("remind me", "").strip()
        if not task:
            return Response("What should I remind you about? Say 'remind me to [task]'.")
        
        reminders.append({
            "task": task,
            "time": datetime.datetime.now().strftime("%d/%m %I:%M %p")
        })
        return Response(f"⏰ Reminder set: '{task}'")


class ShowRemindersHandler(CommandHandler):
    def __init__(self):
        super().__init__()
        self.keywords = ["show reminder", "my reminders"]
        self.priority = 2
    
    def handle(self, query: str, query_lower: str) -> Response:
        if not reminders:
            return Response("⏰ You have no reminders. Say 'remind me to [task]'!")
        
        reminder_list = "\n".join(f"{i}. [{r['time']}] {r['task']}" for i, r in enumerate(reminders, 1))
        return Response(f"⏰ Your Reminders:\n\n{reminder_list}")


class AddTodoHandler(CommandHandler):
    def __init__(self):
        super().__init__()
        self.keywords = ["add todo", "add task", "create todo"]
        self.priority = 2
    
    def handle(self, query: str, query_lower: str) -> Response:
        task = query_lower
        for keyword in ["add todo", "add task", "create todo"]:
            task = task.replace(keyword, "")
        task = task.strip()
        
        if not task:
            return Response("What task should I add? Say 'add todo [task]'.")
        
        todos.append({
            "task": task,
            "done": False,
            "time": datetime.datetime.now().strftime("%d/%m %I:%M %p")
        })
        return Response(f"✅ Task added: '{task}'")


class ShowTodosHandler(CommandHandler):
    def __init__(self):
        super().__init__()
        self.keywords = ["show todo", "my todos", "my tasks"]
        self.priority = 2
    
    def handle(self, query: str, query_lower: str) -> Response:
        if not todos:
            return Response("✅ You have no tasks. Say 'add todo [task]' to create one!")
        
        todo_list = []
        for i, t in enumerate(todos, 1):
            status = "✓" if t["done"] else "○"
            todo_list.append(f"{status} {i}. {t['task']}")
        
        return Response(f"✅ Your To-Do List:\n\n" + "\n".join(todo_list))


class CompleteTodoHandler(CommandHandler):
    def __init__(self):
        super().__init__()
        self.keywords = ["complete"]
        self.priority = 2
    
    def matches(self, query: str) -> bool:
        query_lower = query.lower()
        return "complete" in query_lower and ("todo" in query_lower or "task" in query_lower)
    
    def handle(self, query: str, query_lower: str) -> Response:
        match = re.search(r'(\d+)', query)
        
        if not match or not todos:
            return Response("Say 'complete task [number]' (e.g., 'complete task 1')")
        
        idx = int(match.group(1)) - 1
        if 0 <= idx < len(todos):
            todos[idx]["done"] = True
            return Response(f"✅ Marked as complete: '{todos[idx]['task']}'")
        
        return Response("Say 'complete task [number]' (e.g., 'complete task 1')")


class ClearTodosHandler(CommandHandler):
    def __init__(self):
        super().__init__()
        self.keywords = ["clear todo", "clear task"]
        self.priority = 2
    
    def handle(self, query: str, query_lower: str) -> Response:
        todos.clear()
        return Response("✅ All tasks cleared!")


# ─── UTILITY HANDLERS ─────────────────────────────────────────────────────────

class TimeHandler(CommandHandler):
    def __init__(self):
        super().__init__()
        self.keywords = ["time"]
        self.priority = 2
    
    def matches(self, query: str) -> bool:
        query_lower = query.lower()
        return "time" in query_lower and ("what" in query_lower or "current" in query_lower)
    
    def handle(self, query: str, query_lower: str) -> Response:
        t = datetime.datetime.now().strftime("%I:%M %p")
        return Response(f"⏰ The current time is {t}.")


class DateHandler(CommandHandler):
    def __init__(self):
        super().__init__()
        self.keywords = ["date"]
        self.priority = 2
    
    def matches(self, query: str) -> bool:
        query_lower = query.lower()
        return "date" in query_lower and ("what" in query_lower or "today" in query_lower or "current" in query_lower)
    
    def handle(self, query: str, query_lower: str) -> Response:
        d = datetime.datetime.now().strftime("%A, %B %d, %Y")
        return Response(f"📅 Today is {d}.")


class DayHandler(CommandHandler):
    def __init__(self):
        super().__init__()
        self.keywords = ["what day", "which day"]
        self.priority = 2
    
    def handle(self, query: str, query_lower: str) -> Response:
        day = datetime.datetime.now().strftime("%A")
        return Response(f"📅 Today is {day}!")


class PlayHandler(CommandHandler):
    def __init__(self):
        super().__init__()
        self.keywords = ["play"]
        self.priority = 2
    
    def handle(self, query: str, query_lower: str) -> Response:
        song = query_lower.replace("play", "").strip()
        if not song:
            return Response("What song do you want to play? Say 'play [song name]'.")
        youtube_url = f"https://www.youtube.com/results?search_query={song.replace(' ', '+')}"
        return Response(f"🎵 Playing '{song}' on YouTube!", open_url=youtube_url)


class SearchHandler(CommandHandler):
    def __init__(self):
        super().__init__()
        self.keywords = ["search", "google"]
        self.priority = 2
    
    def handle(self, query: str, query_lower: str) -> Response:
        term = query_lower.replace("search", "").replace("google", "").replace("for", "").strip()
        if not term:
            return Response("What do you want me to search? Say 'search [topic]'.")
        search_url = f"https://www.google.com/search?q={term.replace(' ', '+')}"
        return Response(f"🔍 Searching for '{term}' on Google!", open_url=search_url)


class LocationHandler(CommandHandler):
    def __init__(self):
        super().__init__()
        self.keywords = ["where is", "location of", "locate"]
        self.priority = 2
    
    def handle(self, query: str, query_lower: str) -> Response:
        place = query_lower.replace("where is", "").replace("location of", "").replace("locate", "").strip()
        if not place:
            return Response("Where do you want me to locate? Say 'where is [place]'.")
        maps_url = f"https://www.google.com/maps/place/{place.replace(' ', '+')}"
        return Response(f"📍 Locating '{place}' on Google Maps!", open_url=maps_url)


class TranslationHandler(CommandHandler):
    def __init__(self):
        super().__init__()
        self.keywords = ["translate"]
        self.priority = 2
    
    def handle(self, query: str, query_lower: str) -> Response:
        match = re.search(r'translate\s+(.+?)\s+to\s+(\w+)', query_lower)
        if not match:
            return Response("Say 'translate [text] to [language]' (e.g., 'translate hello to hindi')")
        
        text = match.group(1)
        lang = match.group(2)
        translate_url = f"https://translate.google.com/?sl=auto&tl={lang}&text={quote(text)}"
        return Response(f"🌐 Translating '{text}' to {lang.title()}!", open_url=translate_url)


class CoinFlipHandler(CommandHandler):
    def __init__(self):
        super().__init__()
        self.keywords = ["flip a coin", "coin flip"]
        self.priority = 2
    
    def handle(self, query: str, query_lower: str) -> Response:
        result = random.choice(["Heads", "Tails"])
        return Response(f"🪙 I flipped a coin and got: {result}!")


class DiceRollHandler(CommandHandler):
    def __init__(self):
        super().__init__()
        self.keywords = ["roll dice", "roll a dice"]
        self.priority = 2
    
    def handle(self, query: str, query_lower: str) -> Response:
        result = random.randint(1, 6)
        return Response(f"🎲 You rolled a {result}!")


class RandomNumberHandler(CommandHandler):
    def __init__(self):
        super().__init__()
        self.keywords = ["random number"]
        self.priority = 2
    
    def handle(self, query: str, query_lower: str) -> Response:
        match = re.search(r'(\d+)\s*(?:to|and|-)\s*(\d+)', query_lower)
        
        if match:
            min_num = int(match.group(1))
            max_num = int(match.group(2))
            if min_num > max_num:
                min_num, max_num = max_num, min_num
            result = random.randint(min_num, max_num)
            return Response(f"🔢 Random number between {min_num} and {max_num}: {result}")
        
        result = random.randint(1, 100)
        return Response(f"🔢 Random number (1-100): {result}")


# ─── SOCIAL HANDLERS ──────────────────────────────────────────────────────────

class LoveHandler(CommandHandler):
    def __init__(self):
        super().__init__()
        self.keywords = ["i love you"]
        self.priority = 1
    
    def handle(self, query: str, query_lower: str) -> Response:
        return Response("Aww, that's sweet! I'm here to help you anytime! 💙")


class ComplimentHandler(CommandHandler):
    def __init__(self):
        super().__init__()
        self.keywords = ["you are amazing", "you are awesome", "you are great", "you're amazing"]
        self.priority = 2
    
    def matches(self, query: str) -> bool:
        query_lower = query.lower()
        return "you are" in query_lower and any(word in query_lower for word in ["amazing", "awesome", "great", "smart", "intelligent", "best"])
    
    def handle(self, query: str, query_lower: str) -> Response:
        return Response("Thank you so much! You're pretty awesome too! 😊")


class ThankYouHandler(CommandHandler):
    def __init__(self):
        super().__init__()
        self.keywords = ["thank"]
        self.priority = 2
    
    def handle(self, query: str, query_lower: str) -> Response:
        responses = [
            "You're welcome! Happy to help! 😊",
            "No problem at all!",
            "Anytime! That's what I'm here for!",
            "My pleasure! Let me know if you need anything else!"
        ]
        return Response(random.choice(responses))


class ExitHandler(CommandHandler):
    def __init__(self):
        super().__init__()
        self.keywords = ["exit", "bye", "goodbye", "see you", "quit"]
        self.priority = 1
    
    def handle(self, query: str, query_lower: str) -> Response:
        goodbyes = [
            "👋 Thanks for talking to me! Goodbye!",
            "👋 See you later! Come back anytime!",
            "👋 Goodbye! Have a wonderful day!",
            "👋 It was great chatting with you! Bye!"
        ]
        return Response(random.choice(goodbyes))


# ─── Command Registry ─────────────────────────────────────────────────────────

class CommandRegistry:
    """Registry to manage all command handlers"""
    
    def __init__(self):
        self.handlers: List[CommandHandler] = []
        self.fallback_messages = [
            "Hmm, I don't understand that yet. Try saying 'what can you do' to see what I can help with!",
            "I didn't quite get that. Say 'help' to see all my features!",
            "I'm not sure about that one. Want to see what I can do? Say 'what can you do'!",
            "That's a tricky one! Try asking something else, or say 'help' for ideas!"
        ]
    
    def register(self, handler: CommandHandler):
        """Register a new command handler"""
        self.handlers.append(handler)
        self.handlers.sort(key=lambda h: h.priority)
    
    def register_multiple(self, handlers: List[CommandHandler]):
        """Register multiple handlers at once"""
        for handler in handlers:
            self.register(handler)
    
    def process(self, query: str) -> Response:
        """Process a query through all registered handlers"""
        query_lower = query.lower()
        
        for handler in self.handlers:
            if handler.matches(query):
                result = handler.handle(query, query_lower)
                if result is not None:
                    return result
        
        return Response(random.choice(self.fallback_messages))
    
    def get_handlers_info(self) -> List[Dict]:
        """Get information about all registered handlers"""
        return [h.get_info() for h in self.handlers]


# ─── Initialize Registry ──────────────────────────────────────────────────────

registry = CommandRegistry()

# Register all handlers
registry.register_multiple([
    # Greetings
    GreetingHandler(),
    HowAreYouHandler(),
    UserWellBeingHandler(),
    
    # Identity
    IdentityHandler(),
    CreatorHandler(),
    NameHandler(),
    AgeHandler(),
    
    # Help
    HelpHandler(),
    CapabilitiesHandler(),
    
    # Information
    WikipediaHandler(),
    NewsHandler(),
    WeatherHandler(),
    WhatIsHandler(),
    
    # Advanced Computation
    WolframAlphaHandler(),
    
    # Calculations
    BasicCalculationHandler(),
    ConversionHandler(),
    
    # Entertainment
    JokeHandler(),
    FunFactHandler(),
    RiddleHandler(),
    RiddleAnswerHandler(),
    MotivationHandler(),
    RockPaperScissorsHandler(),
    
    # Productivity
    WriteNoteHandler(),
    ShowNotesHandler(),
    DeleteNotesHandler(),
    SetReminderHandler(),
    ShowRemindersHandler(),
    AddTodoHandler(),
    ShowTodosHandler(),
    CompleteTodoHandler(),
    ClearTodosHandler(),
    
    # Utilities
    TimeHandler(),
    DateHandler(),
    DayHandler(),
    PlayHandler(),
    SearchHandler(),
    LocationHandler(),
    TranslationHandler(),
    CoinFlipHandler(),
    DiceRollHandler(),
    RandomNumberHandler(),
    
    # Social
    LoveHandler(),
    ComplimentHandler(),
    ThankYouHandler(),
    ExitHandler(),
])


# ─── API Routes ───────────────────────────────────────────────────────────────

@app.route("/")
def health():
    return jsonify({
        "status": "healthy",
        "service": "WALL-E Backend API v2.0",
        "architecture": "Command Handler Pattern",
        "handlers_registered": len(registry.handlers),
        "endpoints": ["/api/chat", "/api/save_note", "/api/rps", "/api/handlers"]
    })


@app.route("/api/handlers", methods=["GET"])
def list_handlers():
    """List all registered handlers for debugging"""
    return jsonify({
        "total": len(registry.handlers),
        "handlers": registry.get_handlers_info()
    })


@app.route("/api/chat", methods=["POST"])
def chat():
    data = request.get_json()
    query = data.get("message", "").strip()
    
    if not query or query.lower() == "none":
        return jsonify({"reply": "I didn't catch that. Can you say it again?"})
    
    conversation_history.append({"user": query, "time": datetime.datetime.now()})
    
    # Process query through registry
    response = registry.process(query)
    return jsonify(response.to_dict())


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


@app.route("/api/rps", methods=["POST"])
def rps():
    data = request.get_json()
    player = data.get("choice", "").strip().lower()
    valid = ["rock", "paper", "scissor", "scissors"]
    if player not in valid:
        return jsonify({"reply": "Invalid choice! Say 'rock', 'paper', or 'scissor'."})
    if player == "scissors":
        player = "scissor"

    computer = random.choice(["rock", "paper", "scissor"])
    beats = {"rock": "scissor", "paper": "rock", "scissor": "paper"}

    if player == computer:
        result = "It's a draw! 🤝"
    elif beats[player] == computer:
        result = "You win! 🎉"
    else:
        result = "WALL-E wins! 🤖"

    return jsonify({"reply": f"🎮 You chose: {player.capitalize()}\nWALL-E chose: {computer.capitalize()}\n\n{result}"})


if __name__ == "__main__":
    print("="*60)
    print("🤖 WALL-E v2.0 - Starting Server")
    print("="*60)
    print(f"✅ Registered {len(registry.handlers)} command handlers")
    print(f"✅ Architecture: Command Handler Pattern")
    print(f"✅ WolframAlpha: {'Enabled' if WOLFRAM_API_KEY != 'YOUR_WOLFRAM_API_KEY_HERE' else 'Disabled (add API key)'}")
    print("="*60)
    app.run(debug=False, host="0.0.0.0", port=5000)