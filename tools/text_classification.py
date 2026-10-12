"""Conservative exclusions: inline notes never exclude their surrounding text."""
import re

BRACES = re.compile(r'\{[^{}]*\}')
PRODUCTION = re.compile(r'(?i)^\[\s*(?:GP\s*[: ]|GP Note:|Gameplay (?:Programmer|scripter):|Scripting Placeholder:|VO Testing Lines\b|Scrap Nodes\b|Testing Node\b|Cut to\b|The scene cuts\b|As they walk\b|When Visas is defeated\b|Kreia (?:ignores|is not in the party)\b|Tobin (?:keeps walking|groans)\b|all NPCs become hostile\b|Initiate conversation again\b)')
SKILL_ONLY = re.compile(r'(?i)^\[(?:Awareness|Persuade|Demolitions|Stealth|Security|Repair|Computer(?: Use)?|Treat Injury|Force Persuade|Wisdom|Intelligence|Charisma|Strength|Dexterity|Constitution|Lie|Bluff|Intimidate|Success|Failure)\]$')

def structural_only(source):
    text=source.strip()
    if not text: return False
    if not re.sub(r'\{[^{}]*\}|<[^<>\r\n]+>|%[sdif]', '', text).strip(): return True
    if re.fullmatch(r'[A-Za-z0-9_]+',text) and '_' in text: return True
    # Skill/check labels are visible UI text, including labels without prose.
    if PRODUCTION.search(text): return True
    if re.match(r'(?i)^(?:SHOULD NOT BE TRANSLATED|Should not be translated|VO Testing Lines|.+?\*\*Do Not Translate This\*\*)',text): return True
    return False

def latin_designation(source):
    text=BRACES.sub('',source).strip()
    return bool(re.fullmatch(r'(?:[A-Z0-9]{1,4}-){1,2}[A-Z0-9]{1,4}[?!., ]*',text,re.I)
                or re.fullmatch(r'[0-9\W]+',text)
                or text in {'DirectX','OpenGL','Alt','CTRL','Shift','Tab','XP','Print Screen'}
                or re.fullmatch(r'(?i)(?:be+\w*|de+\w*|re+\w*|bwe+\w*|dwo+\w*|vre+\w*|gonk)[\W]*(?:(?:be+\w*|de+\w*|re+\w*|bwe+\w*|dwo+\w*|vre+\w*|gonk)[\W]*)*',text))
