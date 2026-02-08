import re
NUMBERS = {
    "ONE": "1",
    "TWO": "2",
    "THREE": "3",
    "FOUR": "4",
    "FIVE": "5",
    "SIX": "6",
    "SEVEN": "7",
    "EIGHT": "8",
    "NINE": "9",
    "ZERO": "0",
    "NUMPAD_0": "0",
    "NUMPAD_1": "1",
    "NUMPAD_2": "2",
    "NUMPAD_3": "3",
    "NUMPAD_4": "4",
    "NUMPAD_5": "5",
    "NUMPAD_6": "6",
    "NUMPAD_7": "7",
    "NUMPAD_8": "8",
    "NUMPAD_9": "9"
}
SIGNES = {
    "NUMPAD_SLASH": "/",
    "SLASH": "/",
    "BACK_SLASH": "/",
    "NUMPAD_ASTERIX": "*",
    "NUMPAD_PLUS": "+",
    "EIGHT": "*",
    "EQUAL": "+",
    "NUMPAD_MINUS": "-",
    "MINUS": "-",
}
def parse_my_num_str(calc,parse_num=5):
    return str(round(calc,parse_num)) if calc % 1 else str(int(calc))
def turn_on_typing(self,event):
    if not self.can_type:
        self.typing = False
        return False
    if not self.typing:
        self.typing = True
        self.my_num_str = str(parse_my_num_str(self.cur_value,3))
    return True
def resolve_typing_numbers(self, event):
    if not turn_on_typing(self, event): return
    if self.my_num_str == "0":
        self.my_num_str = str(NUMBERS[event.type])
    else:
        self.my_num_str += str(NUMBERS[event.type])
def resolve_typing_backspace(self, event):
    if not turn_on_typing(self, event): return
    self.my_num_str = self.my_num_str[:-1]
def resolve_typing_dot(self, event):
    if not turn_on_typing(self, event): return
    period_match = re.findall(r'\.', self.my_num_str)
    temp_string = self.my_num_str
    if temp_string and temp_string[0] == "-": temp_string = temp_string[1:]
    sign_match = re.search(r'[\/\*\+\-]', temp_string)
    if (sign_match and len(period_match) < 2) or len(period_match) == 0:
        self.my_num_str += "."
def resolve_typing_signes(self, event):
    if not turn_on_typing(self, event): return
    if event.type == "EIGHT" and not self.is_shift:
        resolve_typing_numbers(self, event)
        return
    temp_string = self.my_num_str
    if temp_string and temp_string[0] == "-": temp_string = temp_string[1:]
    if not re.search(r'[\/\*\+\-]', temp_string) and len(temp_string) > 0:
        self.my_num_str += SIGNES[event.type]
    elif len(self.my_num_str) == 0 and event.type in {"NUMPAD_MINUS", "MINUS"}:
        self.my_num_str += SIGNES[event.type]
def resolve_typing_enter(self, event):
    how_many = len(re.findall(r'\-', self.my_num_str))
    cond = self.my_num_str.find('-') > 0 or len(re.findall(r'\-', self.my_num_str)) > 1
    if self.my_num_str.find("+") != -1:
        parts = self.my_num_str.split("+")
        calc = float(parts[0]) if parts[1] == "" else float(parts[0]) + float(parts[1])
        self.my_num_str = parse_my_num_str(calc)
    elif self.my_num_str.find("-") > 0 or len(re.findall(r'\-', self.my_num_str)) > 1:
        parts = self.my_num_str.split("-")
        if len(parts) == 3:
            parts = [f"-{parts[1]}", parts[2]]
        calc = float(parts[0]) if parts[1] == "" else float(parts[0]) - float(parts[1])
        self.my_num_str = parse_my_num_str(calc)
    elif self.my_num_str.find("*") != -1:
        parts = self.my_num_str.split("*")
        calc = float(parts[0]) if parts[1] == "" else float(parts[0]) * float(parts[1])
        self.my_num_str = parse_my_num_str(calc)
    elif self.my_num_str.find("/") != -1:
        parts = self.my_num_str.split("/")
        if len(parts[1]) > 0:
            parts[1] = str(float(parts[1]))
        if parts[1] in {"","0","0.","0.0"}:
            calc = float(parts[0])
        else:
            calc = float(parts[0]) / float(parts[1])
        self.my_num_str = parse_my_num_str(calc)